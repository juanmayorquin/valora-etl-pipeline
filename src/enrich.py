"""Enriquecimiento de la ubicación - cuarta etapa (Enrich) del flujo ETL.

Lee el stage limpio que dejó `transform.py` y deja a cada anuncio con una coordenada, un
estrato y su distancia al centro de la ciudad, diciendo de dónde salió cada dato:

    anuncios_enriquecido.{csv,parquet}   stage limpio + ubicación resuelta
    enrich_resumen.json                  cobertura por origen y salud de la corrida

Por qué la ubicación (medido en `notebooks/03_eda_modelado.ipynb`):

    De las cinco features de la tarjeta sólo unas dos aportan información independiente
    - `banos` y `habitaciones` correlacionan 0,84 y 0,82 con el área. La ubicación es la
    señal grande, pero `sector` es un string de 7.001 valores con 3.948 sectores de UNA
    fila: R² 0,638 dentro de muestra y 0,320 fuera. Memoriza, no aprende. La salida es
    convertirla en variables NUMÉRICAS Y DENSAS: coordenada y estrato.

De dónde sale la coordenada, en cascada, sin un solo request de red:

    1. anuncio          la coordenada que publica el propio anuncio (detail.py). Cubre el
                        91 % de las filas.
    2. sector_propio    mediana de las coordenadas de los OTROS anuncios del mismo sector:
                        el mejor gazetteer posible, porque usa los nombres tal como los
                        escriben los anunciantes. Cubre otro 7 %.
    3. ninguna          el 2 % restante: sectores raros o mal escritos. Un nulo honesto es
                        mejor que una coordenada inventada.

El estrato sale del anuncio (98 % de cobertura). Antes de las medianas se anula toda
coordenada a más de 60 km del centro de su ciudad: el anuncio dice Bogotá y el punto cae
en Medellín, y un solo punto así arrastraría la mediana de su sector.

Lo que esta etapa YA NO hace, y por qué. Hubo un respaldo con OpenStreetMap (gazetteer de
barrios por Overpass + Nominatim) y Esri Colombia (estrato predominante por manzana). Con
la tarjeta sola llegó al 47 % de cobertura y aportó +0,03 de R²; con el detalle del
anuncio en la mesa, `notebooks/04_ablacion_features.ipynb` lo midió cara a cara:

    sumar OSM/Esri al dato del anuncio     +0,002 de R² como máximo
    estrato modal en arranque en frío      -0,002 / -0,003 (resta)
    filas que rescataba                    0,7 % (72 coordenadas, 233 estratos de 44.836)
    costo                                  1-2 horas de red en cada máquina nueva

Se borró entero. La historia y los números quedan en el notebook 04 y en el historial de
git (commits cb50b1f a 0beca8e).

Uso:
    python src/enrich.py
    python src/enrich.py --sin-validar      # no falla aunque las validaciones fallen

Códigos de salida:
    0  el enriquecimiento terminó y todas las validaciones pasaron
    1  no había datos de entrada, o al menos una validación falló
"""

import argparse
import json
import logging
import math
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("enrich")

# Mínimo de anuncios con coordenada exacta para que la mediana de un sector sea un
# centroide creíble. Con menos, un solo anuncio mal ubicado arrastra a los demás.
N_MINIMO_SECTOR = 3
# Mínimo de anuncios geolocalizados para calcular el centro de una ciudad.
N_MINIMO_CIUDAD = 10
# Una coordenada a más de esto del centro de su ciudad no es de esa ciudad.
RADIO_MAX_DESDE_CENTRO_KM = 60
BBOX_COLOMBIA = {"lat": (-4.3, 13.6), "lon": (-82.0, -66.8)}

COLUMNAS_NUEVAS = ["origen_coordenada", "origen_estrato", "coordenada_lejana",
                   "distancia_centro_km"]


# --------------------------------------------------------------------------------------
# 1. Utilidades
# --------------------------------------------------------------------------------------

def normalizar(texto):
    """Sin tildes, minúsculas, sólo alfanumérico. Para agrupar nombres de sector."""
    if texto is None or (isinstance(texto, float) and math.isnan(texto)):
        return ""
    sin_tildes = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    solo_alfanumerico = "".join(c if c.isalnum() else " " for c in sin_tildes.lower())
    return " ".join(solo_alfanumerico.split())


def distancia_km(lat1, lon1, lat2, lon2):
    """Proyección plana local: sobra para distancias urbanas de decenas de km."""
    escala_lon = math.cos(math.radians(lat1)) * 111.32
    return math.hypot((lat2 - lat1) * 111.32, (lon2 - lon1) * escala_lon)


def distancia_km_vector(lat1, lon1, lat2, lon2):
    """La misma proyección que distancia_km, vectorizada para 50.000 filas."""
    lat1, lon1, lat2, lon2 = (np.asarray(x, dtype="float64") for x in (lat1, lon1, lat2, lon2))
    escala_lon = np.cos(np.radians(lat1)) * 111.32
    return np.hypot((lat2 - lat1) * 111.32, (lon2 - lon1) * escala_lon)


# --------------------------------------------------------------------------------------
# 2. Coordenada en cascada
# --------------------------------------------------------------------------------------

def centros_de_ciudad(df):
    """Centro de cada ciudad: la mediana de las coordenadas de sus anuncios. La mediana
    es robusta a los pocos anuncios mal ubicados, que se anulan recién después."""
    con_anuncio = df[df["origen_coordenada"].eq("anuncio")]
    medianas = (con_anuncio.groupby("ciudad_clave")
                           .agg(lat=("lat", "median"), lon=("lon", "median"), n=("lat", "size")))
    return {ciudad: (float(fila.lat), float(fila.lon))
            for ciudad, fila in medianas.iterrows() if fila.n >= N_MINIMO_CIUDAD}


def anular_coordenadas_lejanas(df, centros):
    lat_centro = df["ciudad_clave"].map(lambda c: centros.get(c, (np.nan, np.nan))[0])
    lon_centro = df["ciudad_clave"].map(lambda c: centros.get(c, (np.nan, np.nan))[1])
    distancia = distancia_km_vector(lat_centro, lon_centro,
                                    df["lat"].astype("float64"), df["lon"].astype("float64"))
    lejana = pd.Series(distancia > RADIO_MAX_DESDE_CENTRO_KM, index=df.index) & df["lat"].notna()
    df["coordenada_lejana"] = lejana.astype(bool)
    df.loc[lejana, ["lat", "lon"]] = pd.NA
    df.loc[lejana, "origen_coordenada"] = "ninguna"
    if lejana.any():
        log.warning("  %d anuncios con coordenada a más de %d km del centro de su ciudad: "
                    "se anula", int(lejana.sum()), RADIO_MAX_DESDE_CENTRO_KM)
    return df


def construir_gazetteer_interno(df):
    """Mediana de lat/lon por (ciudad, sector) sobre los anuncios con coordenada exacta.
    Un sector con N_MINIMO_SECTOR o más anuncios geolocalizados le presta su centroide a
    los vecinos que no traen coordenada."""
    exacta = (df["origen_coordenada"].eq("anuncio")
              & ~df["ubicacion_aproximada"].fillna(False).astype(bool)
              & df["sector_norm"].ne(""))
    base = df.loc[exacta, ["ciudad_clave", "sector_norm", "lat", "lon"]].astype(
        {"lat": "float64", "lon": "float64"})
    sectores = (base.groupby(["ciudad_clave", "sector_norm"])
                    .agg(lat_sector=("lat", "median"), lon_sector=("lon", "median"),
                         n_sector=("lat", "size"))
                    .reset_index())
    return sectores[sectores["n_sector"] >= N_MINIMO_SECTOR].reset_index(drop=True)


def completar_coordenadas(df, sectores):
    """Rellena lat/lon con el centroide del sector propio, anotando el origen. Las filas
    que ya tienen coordenada no se tocan."""
    df = df.merge(sectores, on=["ciudad_clave", "sector_norm"], how="left",
                  validate="many_to_one")
    por_sector = df["lat"].isna() & df["lat_sector"].notna()
    df.loc[por_sector, "lat"] = df.loc[por_sector, "lat_sector"]
    df.loc[por_sector, "lon"] = df.loc[por_sector, "lon_sector"]
    df.loc[por_sector, "origen_coordenada"] = "sector_propio"
    return df.drop(columns=["lat_sector", "lon_sector", "n_sector"])


def agregar_distancia_centro(df, centros):
    """Distancia de la coordenada final al centro de su ciudad: proxy de centralidad."""
    lat_centro = df["ciudad_clave"].map(lambda c: centros.get(c, (np.nan, np.nan))[0])
    lon_centro = df["ciudad_clave"].map(lambda c: centros.get(c, (np.nan, np.nan))[1])
    distancia = distancia_km_vector(lat_centro, lon_centro,
                                    df["lat"].astype("float64"), df["lon"].astype("float64"))
    df["distancia_centro_km"] = np.round(distancia, 3)
    return df


def enriquecer(df):
    """Aplica el flujo completo. Devuelve (enriquecido, sectores del gazetteer interno)."""
    df = df.copy()
    df["sector_norm"] = df["sector_clave"].map(normalizar)
    df["origen_coordenada"] = np.where(df["lat"].notna(), "anuncio", "ninguna")
    df["origen_estrato"] = np.where(df["estrato"].notna(), "anuncio", "ninguno")
    log.info("Coordenada publicada por el anuncio: %s de %s filas (%.1f %%)",
             f"{int(df['lat'].notna().sum()):,}", f"{len(df):,}", df["lat"].notna().mean() * 100)

    log.info("Coordenada final, en cascada:")
    centros = centros_de_ciudad(df)
    log.info("  centros de ciudad calculados: %d", len(centros))
    df = anular_coordenadas_lejanas(df, centros)
    sectores = construir_gazetteer_interno(df)
    log.info("  gazetteer interno: %s sectores con al menos %d anuncios geolocalizados",
             f"{len(sectores):,}", N_MINIMO_SECTOR)
    df = completar_coordenadas(df, sectores)
    df = agregar_distancia_centro(df, centros)
    log.info("  coordenada por origen: %s", df["origen_coordenada"].value_counts().to_dict())
    log.info("  estrato por origen:    %s", df["origen_estrato"].value_counts().to_dict())
    return df.drop(columns=["sector_norm"]), sectores


# --------------------------------------------------------------------------------------
# 3. Validación
# --------------------------------------------------------------------------------------

def validar(original, enriquecido):
    """Comprueba que el enriquecimiento no rompió nada de lo que ya estaba bien. Una
    etapa que agrega columnas nunca debe cambiar la cantidad de filas ni tocar el
    contrato del stage limpio."""
    fallas = []

    def revisar(condicion, mensaje):
        condicion = bool(condicion)
        log.info("  [%s] %s", "OK  " if condicion else "FALLA", mensaje)
        if not condicion:
            fallas.append(mensaje)

    log.info("Conservación del stage limpio:")
    revisar(len(enriquecido) == len(original),
            "El enriquecimiento no agregó ni perdió filas")
    revisar(enriquecido[["id_inmueble", "operacion"]].duplicated().sum() == 0,
            "La llave (id_inmueble, operacion) sigue siendo única")
    revisar(set(original.columns).issubset(enriquecido.columns),
            "Ninguna columna del stage limpio desapareció")
    for columna in ("precio_m2", "area_m2"):
        revisar(enriquecido[columna].notna().all(),
                f"'{columna}' sigue sin nulos tras el merge")

    log.info("Coherencia de la coordenada final:")
    con_coordenada = enriquecido["lat"].notna()
    revisar(con_coordenada.any(), "Al menos un anuncio quedó con coordenada")
    revisar(con_coordenada.eq(enriquecido["lon"].notna()).all(),
            "lat y lon van juntas: nunca una sin la otra")
    revisar(enriquecido.loc[con_coordenada, "lat"].between(*BBOX_COLOMBIA["lat"]).all()
            and enriquecido.loc[con_coordenada, "lon"].between(*BBOX_COLOMBIA["lon"]).all(),
            "Toda coordenada cae dentro de Colombia")
    revisar(con_coordenada.eq(enriquecido["origen_coordenada"].ne("ninguna")).all(),
            "origen_coordenada dice 'ninguna' exactamente donde no hay coordenada")
    del_anuncio = enriquecido["origen_coordenada"].eq("anuncio")
    revisar(np.allclose(enriquecido.loc[del_anuncio, "lat"].astype("float64"),
                        original.loc[del_anuncio.to_numpy(), "lat"].astype("float64"))
            and np.allclose(enriquecido.loc[del_anuncio, "lon"].astype("float64"),
                            original.loc[del_anuncio.to_numpy(), "lon"].astype("float64")),
            "La coordenada de origen 'anuncio' es la que publicó el anuncio, sin tocar")
    distancias = enriquecido.loc[con_coordenada, "distancia_centro_km"].dropna()
    revisar(distancias.empty or (distancias <= RADIO_MAX_DESDE_CENTRO_KM).all(),
            f"Ninguna coordenada queda a más de {RADIO_MAX_DESDE_CENTRO_KM} km del centro "
            "de su ciudad")
    revisar(con_coordenada.mean() > 0.9,
            f"Más del 90 % de las filas tienen coordenada ({con_coordenada.mean() * 100:.1f} %)")

    log.info("Coherencia del estrato:")
    estratos = enriquecido["estrato"].dropna()
    revisar(estratos.empty or estratos.between(1, 6).all(),
            "Todo estrato está en el rango 1-6")
    revisar(enriquecido["estrato"].notna().eq(enriquecido["origen_estrato"].ne("ninguno")).all(),
            "origen_estrato dice 'ninguno' exactamente donde no hay estrato")
    return fallas


# --------------------------------------------------------------------------------------
# 4. Salida
# --------------------------------------------------------------------------------------

def escribir(df, directorio, nombre):
    """CSV para inspección rápida, Parquet porque preserva los tipos que el CSV degrada
    a texto (Int8 nullable, booleanos, fechas)."""
    directorio.mkdir(parents=True, exist_ok=True)
    df.to_csv(directorio / f"{nombre}.csv", index=False, encoding="utf-8-sig")
    df.to_parquet(directorio / f"{nombre}.parquet", index=False)
    log.info("  %-22s %8s filas x %2d columnas", nombre, f"{len(df):,}", len(df.columns))


def exportar(enriquecido, sectores, directorio):
    log.info("Escribiendo el stage enriquecido en %s:", directorio)
    escribir(enriquecido, directorio, "anuncios_enriquecido")

    con_coordenada = enriquecido["lat"].notna()
    principales = enriquecido["ciudad_clave"].value_counts().head(15).index
    resumen = {
        "filas": len(enriquecido),
        "cobertura_coordenada_%": round(con_coordenada.mean() * 100, 2),
        "coordenada_por_origen": enriquecido["origen_coordenada"].value_counts().to_dict(),
        "coordenadas_lejanas_anuladas": int(enriquecido["coordenada_lejana"].sum()),
        "cobertura_estrato_%": round(enriquecido["estrato"].notna().mean() * 100, 2),
        "estrato_por_origen": enriquecido["origen_estrato"].value_counts().to_dict(),
        "estrato_distribucion": {str(int(k)): int(v) for k, v in
                                 enriquecido["estrato"].value_counts().sort_index().items()},
        "sectores_gazetteer_interno": int(len(sectores)),
        "cobertura_por_ciudad_%": (
            enriquecido[enriquecido["ciudad_clave"].isin(principales)]
            .groupby("ciudad_clave")["lat"]
            .apply(lambda s: round(s.notna().mean() * 100, 1))
            .sort_values(ascending=False).to_dict()),
        "nulos_por_columna_nueva_%": {
            columna: round(enriquecido[columna].isna().mean() * 100, 2)
            for columna in ["lat", "estrato"] + COLUMNAS_NUEVAS},
    }
    ruta = directorio / "enrich_resumen.json"
    ruta.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("  %s", ruta.name)
    return resumen


# --------------------------------------------------------------------------------------
# Punto de entrada
# --------------------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Resuelve la coordenada, el estrato y la distancia al centro de cada anuncio")
    parser.add_argument("--entrada-dir", default="data/processed",
                        help="Carpeta con el stage limpio del transform")
    parser.add_argument("--salida-dir", default="data/processed",
                        help="Carpeta de salida (se crea si no existe)")
    parser.add_argument("--sin-validar", action="store_true",
                        help="Escribe la salida aunque las validaciones fallen")
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    entrada = Path(args.entrada_dir) / "anuncios.parquet"
    if not entrada.exists():
        log.error("No existe %s: hay que correr src/transform.py primero", entrada)
        return 1
    original = pd.read_parquet(entrada)
    log.info("Stage limpio: %s filas x %d columnas", f"{len(original):,}", original.shape[1])
    for columna in ("lat", "lon", "estrato", "ubicacion_aproximada"):
        if columna not in original.columns:
            log.error("El stage limpio no tiene la columna '%s': hay que correr el transform "
                      "con el detalle (src/detail.py) antes de enriquecer", columna)
            return 1

    enriquecido, sectores = enriquecer(original)

    log.info("Validación del enriquecimiento:")
    fallas = validar(original, enriquecido)
    resumen = exportar(enriquecido, sectores, Path(args.salida_dir))

    if fallas:
        log.error("%d validaciones fallaron: %s", len(fallas), "; ".join(fallas))
        if not args.sin_validar:
            return 1
        log.warning("--sin-validar activo: se continúa pese a las fallas")

    log.info("Enriquecimiento completo: %s %% de las filas con coordenada %s | %s %% con "
             "estrato %s", resumen["cobertura_coordenada_%"],
             json.dumps(resumen["coordenada_por_origen"]), resumen["cobertura_estrato_%"],
             json.dumps(resumen["estrato_por_origen"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
