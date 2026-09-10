"""Transformación de los anuncios crudos - segunda etapa (Transform) del flujo ETL.

Lee los CSV que dejó `extract.py` en `data/raw/` y produce dos stages en
`data/processed/`:

    anuncios.{csv,parquet}     stage limpio: lo que consume el análisis
    cuarentena.{csv,parquet}   rechazadas, cada una con su `motivo_rechazo`
    transform_resumen.json     conteos de la corrida, para monitoreo

La cuarentena no es un descarte sino una separación: queda en disco, auditable, y si
una regla resulta demasiado estricta se reprocesa desde ahí.

Las reglas (R2-R12 de parseo, D0-D7 de distribución) salieron del análisis exploratorio
en `notebooks/eda.ipynb`; el flujo se prototipó en `notebooks/transform.ipynb`.

El orden de aplicación importa y no es negociable:

    1. Normalizar esquema      ->  un solo contrato de columnas + tipo desde el slug (R3)
    2. Operación y duales      ->  R4 + D0: separa precio_venta / precio_arriendo
    3. Saneamiento de precio   ->  R5, R6
    4. Saneamiento de área     ->  R7 + D4 (area_posible_lote)
    5. Derivar precio_m2       ->  sólo sobre lo que sobrevivió a 3 y 4
    6. Outliers IQR log        ->  D1, D2, D3
    7. Consolidar y separar    ->  R11 + compuerta de calidad

Calcular `precio_m2` antes del paso 2 es el error clásico: se divide un precio de venta
que estaba en el feed de arriendo y el indicador nace roto.

Uso:
    python src/transform.py
    python src/transform.py --entrada-dir data/raw --salida-dir data/processed
    python src/transform.py --operaciones arriendo
    python src/transform.py --sin-validar      # no falla aunque las validaciones fallen

Códigos de salida:
    0  la transformación terminó y todas las validaciones pasaron
    1  no había datos de entrada, o al menos una validación falló
"""

import argparse
import json
import logging
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

OPERACIONES = ("arriendo", "venta")
RESIDENCIAL = ("apartaestudio", "apartamento", "casa")

log = logging.getLogger("transform")


# --------------------------------------------------------------------------------------
# Utilidades estadísticas
# --------------------------------------------------------------------------------------

def vallas_iqr_log(serie, k=1.5):
    """Vallas de Tukey sobre log(x), devueltas en la escala original.

    En log porque estas variables son log-normales: sobre la escala cruda la valla
    inferior da negativa y no detecta ni un outlier bajo (ver D1 en el EDA).
    """
    s = pd.to_numeric(serie, errors="coerce").dropna()
    s = s[s > 0]
    if len(s) < 4:
        return (np.nan, np.nan)
    x = np.log(s)
    q1, q3 = x.quantile(.25), x.quantile(.75)
    iqr = q3 - q1
    return float(np.exp(q1 - k * iqr)), float(np.exp(q3 + k * iqr))


# --------------------------------------------------------------------------------------
# 1. Normalización de esquema - R2 + R3
# --------------------------------------------------------------------------------------

PATRON_TITULO = re.compile(
    r"(?P<tipo>[A-Za-zÁÉÍÓÚÑáéíóúñ ]+?)\s+en\s+"
    r"(?P<operacion>(?:Venta|Arriendo)(?:\s+y\s+(?:Venta|Arriendo))?),"
    r"(?:\s*(?P<sector>[^,]+),)?\s*(?P<ciudad>[^,\n]+)$",
    flags=re.IGNORECASE,
)

# El tipo real vive en el slug de la URL, siempre en la misma posición:
#   /inmueble/arriendo-apartaestudio-bogota-chapinero-1-habitaciones/21601-M6844386
#             ^^^^^^^^ ^^^^^^^^^^^^^
#             operación   tipo
# Sin re.IGNORECASE a propósito: los slugs son minúscula y con pyarrow instalado las
# regex sin flags las resuelve RE2, que es más rápido.
PATRON_TIPO_SLUG = r"/inmueble/(?:arriendo|venta)-([a-z]+)-"

COLUMNAS_CONTRATO = [
    "id_inmueble", "url", "texto", "tipo_inmueble", "tipo_feed", "operacion_feed",
    "precio_texto", "area_m2", "habitaciones", "banos", "parqueaderos",
    "sector", "ciudad", "fecha_extraccion",
]


def sin_tilde(texto):
    if not isinstance(texto, str):
        return texto
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def normalizar_tipo(serie):
    return serie.map(sin_tilde).str.lower().str.strip()


def id_desde_url(serie):
    """Último segmento de la ruta, sin querystring. Formatos: '17548-M6886169' y 'MC6943773'."""
    return serie.str.split("?").str[0].str.rstrip("/").str.rsplit("/", n=1).str[-1]


def tipo_desde_url(serie):
    """R3 - tipo del anuncio según su propio slug. Fuente por anuncio, no por barrido."""
    return serie.str.extract(PATRON_TIPO_SLUG, expand=False).str.strip()


def cargar(ruta, operacion_feed):
    """Lee un CSV del extract (esquema viejo o nuevo) y devuelve el contrato normalizado."""
    df = pd.read_csv(ruta)
    # Tres generaciones del extract conviven en data/raw:
    #   v1  sin tipo: hay que sacarlo del título
    #   v2  `tipo_inmueble` = etiqueta del barrido (la que resultó no confiable)
    #   v3  `tipo_inmueble` = slug del anuncio, `tipo_barrido` = etiqueta del barrido
    esquema = ("v3" if "tipo_barrido" in df.columns
               else "v2" if "tipo_inmueble" in df.columns
               else "v1")

    if "id_inmueble" not in df.columns:
        df["id_inmueble"] = id_desde_url(df["url"])
    if "operacion" in df.columns:
        df["operacion_feed"] = df["operacion"]
    else:
        df["operacion_feed"] = operacion_feed
    if "fecha_extraccion" not in df.columns:
        df["fecha_extraccion"] = pd.NaT

    # Etiqueta de procedencia: se guarda para auditar, NO decide el tipo (ver resolver_tipo).
    # Ojo con el orden: en v3 la etiqueta del barrido ya no vive en `tipo_inmueble` sino en
    # `tipo_barrido`. Leerla del lugar equivocado haría que el acuerdo diera 100 % siempre
    # y el indicador dejaría de detectar nada.
    if esquema == "v3":
        df["tipo_feed"] = normalizar_tipo(df["tipo_barrido"])
    elif esquema == "v2":
        df["tipo_feed"] = normalizar_tipo(df["tipo_inmueble"])
    else:
        df["tipo_feed"] = normalizar_tipo(df["texto"].str.extract(PATRON_TITULO)["tipo"])

    df["tipo_inmueble"] = tipo_desde_url(df["url"])

    faltantes = [c for c in COLUMNAS_CONTRATO if c not in df.columns]
    if faltantes:
        raise ValueError(f"{ruta}: faltan columnas tras normalizar: {faltantes}")

    log.info("  %-28s esquema=%-3s filas=%6d", ruta.name, esquema, len(df))
    return df[COLUMNAS_CONTRATO].copy()


def cargar_crudo(entrada_dir, operaciones, prefijo="anuncios"):
    """Concatena los CSV de cada operación. Falla si no hay ninguno."""
    partes = []
    log.info("Cargando:")
    for operacion in operaciones:
        ruta = entrada_dir / f"{prefijo}_{operacion}.csv"
        if not ruta.exists():
            log.warning("  %-28s no existe, se omite", ruta.name)
            continue
        partes.append(cargar(ruta, operacion))

    if not partes:
        raise FileNotFoundError(
            f"No hay CSV de entrada en {entrada_dir}. Corré primero `python src/extract.py`."
        )
    return pd.concat(partes, ignore_index=True)


def resolver_tipo(df):
    """R3 - manda el slug. Marca lo que no es vivienda para que la compuerta lo saque.

    Un slug ilegible (sin match) también queda marcado: si no se puede afirmar que la
    fila es vivienda, no entra al stage limpio.
    """
    df["tipo_no_residencial"] = ~df["tipo_inmueble"].isin(RESIDENCIAL)

    coincide = df["tipo_inmueble"].eq(df["tipo_feed"])
    log.info("R3 - slug vs. etiqueta del barrido: coinciden %.2f %% (%s filas reetiquetadas)",
             coincide.mean() * 100, f"{int((~coincide).sum()):,}")

    fuera = df.loc[df["tipo_no_residencial"], "tipo_inmueble"]
    log.info("R3 - no residencial (a cuarentena): %s filas %s",
             f"{len(fuera):,}", fuera.value_counts(dropna=False).to_dict())
    return df


# --------------------------------------------------------------------------------------
# 2. Operación declarada y anuncios duales - R4 + D0
# --------------------------------------------------------------------------------------

UMBRAL_ARRIENDO_IMPOSIBLE = 100_000_000  # ningún canon residencial mensual llega acá


def a_entero(serie):
    """'$1.850.000.000' -> 1850000000. El punto es separador de miles, no decimal."""
    return pd.to_numeric(
        serie.astype(str).str.replace(r"[^\d]", "", regex=True).replace("", np.nan),
        errors="coerce",
    ).astype("Int64")


def resolver_operacion(df):
    partes = df["texto"].str.extract(PATRON_TITULO)
    declarada = partes["operacion"].str.lower().str.strip()

    df["es_dual"] = declarada.str.contains(" y ", na=False)
    df["operacion"] = np.where(df["es_dual"], "ambas", df["operacion_feed"])
    # Si el título no matcheó, la operación del feed sigue siendo válida
    df["titulo_sin_parsear"] = declarada.isna()

    # Sector y ciudad del título sólo si el extract no los trajo (esquema viejo con duales)
    df["sector"] = df["sector"].fillna(partes["sector"].str.strip())
    df["ciudad"] = df["ciudad"].fillna(partes["ciudad"].str.strip())
    return df


def separar_precios(df):
    """D0: en el feed de arriendo, el precio de un dual es de venta, no un canon.

    Los duales publican el precio de venta también en el feed de arriendo, con una
    mediana cientos de veces mayor que la de un canon real. Por eso el precio no puede
    quedar en una sola columna, y para un dual el canon queda en NaN: no lo conocemos.
    """
    precio = a_entero(df["precio_texto"])

    es_venta = df["operacion_feed"].eq("venta")
    df["precio_venta"] = precio.where(es_venta | df["es_dual"])
    df["precio_arriendo"] = precio.where(~es_venta & ~df["es_dual"])
    return df


# --------------------------------------------------------------------------------------
# 3. Saneamiento de precio - R5 + R6
# --------------------------------------------------------------------------------------

RANGO_PRECIO = {
    "arriendo": (300_000, 500_000_000),
    "venta": (20_000_000, 100_000_000_000),
}

# Un solo dígito repetido siete veces o más. Se escribe como alternación explícita y no
# como la retroreferencia (\d)\1{6,}: con pyarrow instalado, pandas resuelve las regex de
# strings con RE2, que no soporta retroreferencias y falla con ArrowInvalid.
PATRON_DIGITO_REPETIDO = "|".join(f"{d}{{7,}}" for d in "0123456789")


def es_relleno(serie_texto):
    """R6: dígito repetido 7+ veces, o la secuencia 123456."""
    digitos = serie_texto.astype(str).str.replace(r"[^\d]", "", regex=True)
    return (digitos.str.fullmatch(PATRON_DIGITO_REPETIDO).fillna(False)
            | digitos.str.contains("123456", na=False))


def sanear_precios(df):
    """R6 antes que R5: si no, el rango da por bueno un relleno que cae dentro."""
    df["precio_relleno"] = es_relleno(df["precio_texto"])
    log.info("R6 - precios de relleno: %d", int(df["precio_relleno"].sum()))
    df.loc[df["precio_relleno"], ["precio_venta", "precio_arriendo"]] = pd.NA

    log.info("R5 - rangos por operación:")
    for operacion, columna in (("arriendo", "precio_arriendo"), ("venta", "precio_venta")):
        minimo, maximo = RANGO_PRECIO[operacion]
        valores = df[columna]
        fuera = valores.notna() & ((valores < minimo) | (valores > maximo))
        df[f"{columna}_fuera_de_rango"] = fuera
        df.loc[fuera, columna] = pd.NA
        log.info("  %-17s fuera de rango: %4d | válidos: %6d",
                 columna, int(fuera.sum()), int(df[columna].notna().sum()))
    return df


# --------------------------------------------------------------------------------------
# 4. Saneamiento de área - R7 + D4
# --------------------------------------------------------------------------------------

RANGO_AREA = (20, 2000)


def sanear_areas(df):
    minimo, maximo = RANGO_AREA
    area = pd.to_numeric(df["area_m2"], errors="coerce")

    fuera = area.notna() & ((area < minimo) | (area > maximo))
    df["area_fuera_de_rango"] = fuera
    df["area_m2"] = area.where(~fuera)
    log.info("R7 - área fuera de [%d, %d]: %d (%.2f %%)",
             minimo, maximo, int(fuera.sum()), fuera.mean() * 100)
    return df


def precio_unificado(df):
    """El precio que corresponde a la operación de la fila."""
    return df["precio_arriendo"].astype("Float64").fillna(df["precio_venta"].astype("Float64"))


def marcar_area_posible_lote(df):
    """D4, en dos pasadas: el área sola no distingue casa grande de área de lote.

    Lo que la distingue es el precio/m² hundido. Se calcula un precio/m² provisional
    sobre el área declarada y se marcan las casas que caen bajo la valla inferior.

    La valla sale **sólo del universo residencial**: una bodega tiene precio/m²
    estructuralmente bajo y una oficina uno alto, y meterlas en el cálculo mueve el
    umbral que decide sobre las casas. Por eso esto va después de resolver el tipo.
    """
    provisional = precio_unificado(df) / df["area_m2"]
    es_residencial = ~df["tipo_no_residencial"]

    marca = pd.Series(False, index=df.index)
    for operacion, grupo in df.groupby("operacion"):
        base = grupo.index[es_residencial.loc[grupo.index].to_numpy()]
        inferior, _ = vallas_iqr_log(provisional.loc[base])
        if np.isnan(inferior):
            continue
        # fillna(False): la comparación sobre Float64 nullable devuelve NA donde no hay
        # dato, y un NA no entra en una serie booleana de numpy
        bajo_mercado = (provisional.loc[grupo.index] < inferior).fillna(False).astype(bool)
        es_casa = grupo["tipo_inmueble"].eq("casa").fillna(False).astype(bool)
        marca.loc[grupo.index] = es_casa & bajo_mercado
        log.info("D4 - %-9s valla inferior de precio/m²: %12s | base residencial: %7s"
                 " | casas marcadas: %d",
                 operacion, f"{inferior:,.0f}", f"{len(base):,}",
                 int((es_casa & bajo_mercado).sum()))

    df["area_posible_lote"] = marca
    casas = df["tipo_inmueble"].eq("casa")
    if casas.any():
        log.info("D4 - total: %d (%.1f %% de las casas) | área mediana marcadas: %s m²"
                 " | resto: %s m²",
                 int(marca.sum()), df.loc[casas, "area_posible_lote"].mean() * 100,
                 f"{df.loc[marca, 'area_m2'].median():,.0f}",
                 f"{df.loc[~marca, 'area_m2'].median():,.0f}")
    return df


# --------------------------------------------------------------------------------------
# 5. Variables censuradas - R8
# --------------------------------------------------------------------------------------

# El sitio agrupa en "5 o más" y "4 o más": `habitaciones = 5` significa `>= 5`.
# Nunca imputar con la media: hacia arriba el valor real es desconocido.
TOPES = {"habitaciones": 5, "banos": 5, "parqueaderos": 4}


def marcar_censuradas(df):
    for columna, tope in TOPES.items():
        valores = pd.to_numeric(df[columna], errors="coerce").astype("Int8")
        df[columna] = valores
        df[f"{columna}_es_tope"] = valores.eq(tope).fillna(False)
        log.info("R8 - %-13s tope=%d | en el tope: %5d | nulos: %5d | máximo observado: %s",
                 columna, tope, int(df[f"{columna}_es_tope"].sum()),
                 int(valores.isna().sum()), valores.max())
    return df


# --------------------------------------------------------------------------------------
# 6. Normalización de texto - R10
# --------------------------------------------------------------------------------------

def normalizar_lugar(serie):
    limpio = (serie.astype("string")
              .str.replace(r"\s+", " ", regex=True)
              .str.strip()
              .replace({"": pd.NA}))
    return limpio.str.title()


def normalizar_texto(df):
    """Colapsa espacios y unifica capitalización. NO hace fuzzy matching: juntar `Chico`
    con `Chico Norte` sería inventar información; son sectores distintos."""
    for columna in ("ciudad", "sector"):
        antes = df[columna].nunique()
        df[columna] = normalizar_lugar(df[columna])
        # Clave de agrupación insensible a tildes y mayúsculas
        df[f"{columna}_clave"] = df[columna].map(sin_tilde).str.lower()
        log.info("R10 - %-8s únicos: %5d -> %5d | por clave sin tilde: %5d | nulos: %d",
                 columna, antes, df[columna].nunique(),
                 df[f"{columna}_clave"].nunique(), int(df[columna].isna().sum()))
    return df


# --------------------------------------------------------------------------------------
# 7. Precio por m² y outliers - D1, D2, D3
# --------------------------------------------------------------------------------------

# Un segmento con menos observaciones que esto no da una valla confiable y cae al
# respaldo global de su operación.
N_MINIMO_SEGMENTO = 300


def derivar_precio_m2(df):
    """Precio/m² definitivo: excluye el área de las casas marcadas como lote (D4)."""
    area_utilizable = df["area_m2"].where(~df["area_posible_lote"])
    df["precio_m2"] = (precio_unificado(df) / area_utilizable).astype("Float64")
    return df


def marcar_outliers(df, columnas=("precio_arriendo", "precio_venta", "area_m2", "precio_m2")):
    """D1-D3. Las vallas describen el mercado residencial; las demás filas se miden
    contra él pero no participan de su cálculo.

    Las vallas van por (operacion, tipo_inmueble): un arriendo de apartaestudio y una
    venta de casa no comparten distribución.
    """
    es_residencial = ~df["tipo_no_residencial"]
    reporte = []
    for columna in columnas:
        marca = pd.Series(False, index=df.index)
        for (operacion, tipo), grupo in df.groupby(["operacion", "tipo_inmueble"], dropna=False):
            serie = grupo[columna]
            usable = pd.to_numeric(serie, errors="coerce").dropna()
            if len(usable) >= N_MINIMO_SEGMENTO:
                inf, sup = vallas_iqr_log(serie)
                origen = "segmento"
            else:
                respaldo = df["operacion"].eq(operacion) & es_residencial
                inf, sup = vallas_iqr_log(df.loc[respaldo, columna])
                origen = "global"
            if np.isnan(inf):
                continue
            valores = pd.to_numeric(serie, errors="coerce")
            fuera = (valores.notna() & ((valores < inf) | (valores > sup))).fillna(False).astype(bool)
            marca.loc[grupo.index] = fuera
            reporte.append({"columna": columna, "operacion": operacion, "tipo": tipo,
                            "n": len(usable), "umbral": origen,
                            "valla_inf": inf, "valla_sup": sup, "outliers": int(fuera.sum())})
        df[f"outlier_{columna}"] = marca
    return df, pd.DataFrame(reporte)


# --------------------------------------------------------------------------------------
# 8. Consolidación y compuerta de calidad - R11
# --------------------------------------------------------------------------------------

# Reglas que mandan la fila a cuarentena: el dato es incorrecto o no comparable
REGLAS_BLOQUEANTES = [
    "tipo_no_residencial",
    "precio_relleno",
    "precio_arriendo_fuera_de_rango",
    "precio_venta_fuera_de_rango",
    "area_fuera_de_rango",
    "area_posible_lote",
    "titulo_sin_parsear",
    "outlier_precio_arriendo",
    "outlier_precio_venta",
    "outlier_area_m2",
    "outlier_precio_m2",
    "sin_precio",
    "sin_area",
]

# Banderas que NO bloquean: describen el dato, no lo invalidan. Las tres `_es_tope`
# son censura del origen y están en el 27 % de las filas - bloquearlas se llevaría
# el segmento alto entero (mediana de área 340 m² vs. 85 m², 84 % casas) y fabricaría
# el sesgo que se quiere evitar. Un dato censurado sigue siendo correcto.
BANDERAS_INFORMATIVAS = [
    "es_dual", "habitaciones_es_tope", "banos_es_tope", "parqueaderos_es_tope",
]

CLAVE = ["id_inmueble", "operacion"]


def consolidar(df):
    antes = len(df)
    # Los duales llegan por los dos feeds: una sola fila por (id_inmueble, operacion)
    df = df.sort_values("operacion_feed").drop_duplicates(
        subset=CLAVE, keep="first").reset_index(drop=True)
    log.info("R11 - filas: %d -> %d (%d consolidadas)", antes, len(df), antes - len(df))
    return df


def marcar_ausencias(df):
    """Sin precio o sin área no hay análisis posible: son motivos de rechazo por derecho propio."""
    df["sin_precio"] = df["precio_arriendo"].isna() & df["precio_venta"].isna()
    df["sin_area"] = df["area_m2"].isna()
    return df


def componer_motivo(df):
    """'|' entre las reglas que disparó la fila, 'ok' si no disparó ninguna.

    Vectorizado a propósito: el boceto usaba `iterrows()`, que sobre ~50 000 filas es
    el paso más lento de todo el flujo.
    """
    motivo = pd.Series("", index=df.index, dtype="object")
    for regla in REGLAS_BLOQUEANTES:
        motivo = motivo.where(~df[regla], motivo + "|" + regla)
    return motivo.str.lstrip("|").replace("", "ok")


def separar_por_calidad(df):
    """Compuerta: devuelve (limpio, cuarentena). El motivo viaja con la fila rechazada."""
    for columna in REGLAS_BLOQUEANTES + BANDERAS_INFORMATIVAS:
        df[columna] = df[columna].fillna(False).astype(bool)

    rechaza = df[REGLAS_BLOQUEANTES].any(axis=1)
    df["n_motivos_rechazo"] = df[REGLAS_BLOQUEANTES].sum(axis=1)
    df["motivo_rechazo"] = componer_motivo(df)

    limpio = df[~rechaza].reset_index(drop=True)
    cuarentena = df[rechaza].reset_index(drop=True)

    log.info("Compuerta de calidad sobre %s filas:", f"{len(df):,}")
    log.info("  pasan      : %8s (%5.2f %%)", f"{len(limpio):,}", len(limpio) / len(df) * 100)
    log.info("  cuarentena : %8s (%5.2f %%)", f"{len(cuarentena):,}",
             len(cuarentena) / len(df) * 100)
    return limpio, cuarentena


# --------------------------------------------------------------------------------------
# 9. Validación
# --------------------------------------------------------------------------------------

def validar(limpio, cuarentena, consolidado):
    """Comprueba que el flujo hizo lo que dice. Devuelve la lista de fallas.

    Si alguna falla, el pipeline está roto y hay que enterarse acá, no en el análisis.
    """
    fallas = []

    def revisar(condicion, mensaje):
        condicion = bool(condicion)
        log.info("  [%s] %s", "OK  " if condicion else "FALLA", mensaje)
        if not condicion:
            fallas.append(mensaje)

    log.info("Contrato del stage LIMPIO:")
    revisar(limpio[CLAVE].duplicated().sum() == 0,
            "R2/R11 - la llave (id_inmueble, operacion) es única")
    revisar(limpio["id_inmueble"].notna().all(),
            "R2 - no hay id_inmueble nulo")
    revisar(not limpio["id_inmueble"].str.contains(r"[?&=]", na=False).any(),
            "R2 - el id_inmueble está limpio de querystring")

    # R3 se verifica contra la URL, no contra la columna: si se comparara `tipo_inmueble`
    # consigo mismo la prueba pasaría siempre - que es exactamente cómo se coló la fuga
    # de oficinas y bodegas cuando el tipo venía de la etiqueta del barrido.
    tipo_en_url = tipo_desde_url(limpio["url"])
    revisar(tipo_en_url.isin(RESIDENCIAL).all(),
            f"R3 - el slug de toda URL limpia es uno de {RESIDENCIAL}")
    revisar(limpio["tipo_inmueble"].eq(tipo_en_url).all(),
            "R3 - tipo_inmueble coincide con el slug de su propia URL")
    # Una cuarentena vacía satisface la propiedad de forma trivial. El boceto la daba por
    # fallida, que es lo contrario de lo que la regla afirma.
    revisar(cuarentena.empty
            or not tipo_desde_url(cuarentena.loc[cuarentena["tipo_no_residencial"], "url"])
            .isin(RESIDENCIAL).any(),
            "R3 - nada residencial quedó atrapado en tipo_no_residencial")

    # La compuerta: ninguna regla bloqueante puede sobrevivir en el stage limpio
    revisar(not limpio[REGLAS_BLOQUEANTES].any().any(),
            "Compuerta - ninguna fila limpia dispara una regla bloqueante")
    revisar((limpio["motivo_rechazo"] == "ok").all(),
            "Compuerta - toda fila limpia tiene motivo_rechazo = 'ok'")

    revisar(limpio["area_m2"].notna().all(),
            "Completitud - toda fila limpia tiene área")
    revisar((limpio["precio_arriendo"].notna() | limpio["precio_venta"].notna()).all(),
            "Completitud - toda fila limpia tiene al menos un precio")
    revisar(limpio["precio_m2"].notna().all(),
            "Completitud - toda fila limpia tiene precio_m2 calculable")

    arriendos = limpio.loc[limpio["precio_arriendo"].notna(), "precio_arriendo"]
    revisar(arriendos.between(*RANGO_PRECIO["arriendo"]).all(),
            "R5 - todo precio_arriendo está dentro de rango")
    ventas = limpio.loc[limpio["precio_venta"].notna(), "precio_venta"]
    revisar(ventas.between(*RANGO_PRECIO["venta"]).all(),
            "R5 - todo precio_venta está dentro de rango")
    revisar(not (limpio["es_dual"] & limpio["precio_arriendo"].notna()).any(),
            "D0 - ningún dual conserva canon de arriendo")
    revisar(limpio["area_m2"].between(*RANGO_AREA).all(),
            "R7 - toda área está dentro de rango")

    for columna, tope in TOPES.items():
        revisar(pd.to_numeric(limpio[columna], errors="coerce").max() <= tope,
                f"R8 - {columna} no supera el tope {tope}")

    # Si alguien convirtiera las `_es_tope` en bloqueantes, esta prueba lo detecta.
    censura = ["habitaciones_es_tope", "banos_es_tope", "parqueaderos_es_tope"]
    proporcion = limpio[censura].any(axis=1).mean()
    revisar(proporcion > 0.15,
            f"R8 - el stage limpio conserva las filas censuradas ({proporcion * 100:.1f} %)")

    log.info("Contrato del stage CUARENTENA:")
    revisar(cuarentena.empty or cuarentena[REGLAS_BLOQUEANTES].any(axis=1).all(),
            "Toda fila en cuarentena tiene al menos un motivo")
    revisar((cuarentena["motivo_rechazo"] != "ok").all(),
            "Ninguna fila en cuarentena quedó con motivo 'ok'")

    log.info("Conservación (nada se pierde, sólo se reparte):")
    revisar(len(limpio) + len(cuarentena) == len(consolidado),
            "La suma de los dos stages es el total consolidado")
    claves_limpio = set(map(tuple, limpio[CLAVE].to_numpy()))
    claves_cuarentena = set(map(tuple, cuarentena[CLAVE].to_numpy()))
    revisar(claves_limpio.isdisjoint(claves_cuarentena),
            "Ninguna clave aparece en los dos stages a la vez")
    revisar(claves_limpio | claves_cuarentena
            == set(map(tuple, consolidado[CLAVE].to_numpy())),
            "La unión de los stages reconstruye el consolidado")

    return fallas


# --------------------------------------------------------------------------------------
# 10. Salida - dos stages
# --------------------------------------------------------------------------------------

def escribir(df, directorio, nombre):
    """CSV para inspección rápida, Parquet porque preserva los tipos que el CSV degrada
    a texto (Int8 nullable, booleanos, fechas)."""
    directorio.mkdir(parents=True, exist_ok=True)
    df.to_csv(directorio / f"{nombre}.csv", index=False, encoding="utf-8-sig")
    df.to_parquet(directorio / f"{nombre}.parquet", index=False)
    log.info("  %-12s %8s filas x %2d columnas", nombre, f"{len(df):,}", len(df.columns))


def exportar(limpio, cuarentena, directorio):
    log.info("Escribiendo stages en %s:", directorio)
    escribir(limpio, directorio, "anuncios")
    escribir(cuarentena, directorio, "cuarentena")

    total = len(limpio) + len(cuarentena)
    todo = pd.concat([limpio, cuarentena], ignore_index=True)
    resumen = {
        "total_procesado": total,
        "limpio": len(limpio),
        "cuarentena": len(cuarentena),
        "tasa_rechazo_%": round(len(cuarentena) / total * 100, 2) if total else 0.0,
        "motivos_rechazo": {m: int(cuarentena[m].sum())
                            for m in REGLAS_BLOQUEANTES if cuarentena[m].sum() > 0},
        "limpio_por_operacion": limpio["operacion"].value_counts().to_dict(),
        "limpio_por_tipo": limpio["tipo_inmueble"].value_counts().to_dict(),
        "limpio_con_censura_%": round(
            limpio[["habitaciones_es_tope", "banos_es_tope", "parqueaderos_es_tope"]]
            .any(axis=1).mean() * 100, 2),
        # Salud de la fuente: cuánto discrepa el barrido del slug. Si esto se dispara,
        # el filtro del sitio cambió y hay que revisar el extract.
        "reetiquetadas_por_slug": int((~todo["tipo_inmueble"].eq(todo["tipo_feed"])).sum()),
        "acuerdo_slug_barrido_%": round(
            todo["tipo_inmueble"].eq(todo["tipo_feed"]).mean() * 100, 2),
    }
    ruta = directorio / "transform_resumen.json"
    ruta.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("  %s", ruta.name)
    return resumen


# --------------------------------------------------------------------------------------
# Orquestación
# --------------------------------------------------------------------------------------

def transformar(crudo):
    """Aplica el flujo completo sobre el crudo ya cargado. Devuelve (limpio, cuarentena,
    consolidado, reporte_vallas)."""
    crudo = resolver_tipo(crudo)

    crudo = resolver_operacion(crudo)
    crudo = separar_precios(crudo)
    log.info("Operación resuelta: %s | duales: %d | títulos sin parsear: %d",
             crudo["operacion"].value_counts(dropna=False).to_dict(),
             int(crudo["es_dual"].sum()), int(crudo["titulo_sin_parsear"].sum()))

    crudo = sanear_precios(crudo)
    crudo = sanear_areas(crudo)
    crudo = marcar_area_posible_lote(crudo)
    crudo = marcar_censuradas(crudo)
    crudo = normalizar_texto(crudo)

    crudo = derivar_precio_m2(crudo)
    crudo, reporte_vallas = marcar_outliers(crudo)
    log.info("precio_m2 calculable en %d de %d filas",
             int(crudo["precio_m2"].notna().sum()), len(crudo))

    consolidado = consolidar(crudo)
    consolidado = marcar_ausencias(consolidado)
    limpio, cuarentena = separar_por_calidad(consolidado)
    return limpio, cuarentena, consolidado, reporte_vallas


def parse_args():
    parser = argparse.ArgumentParser(
        description="Transforma los anuncios crudos en los stages limpio y cuarentena")
    parser.add_argument("--entrada-dir", default="data/raw",
                        help="Carpeta con los CSV del extract")
    parser.add_argument("--salida-dir", default="data/processed",
                        help="Carpeta de salida (se crea si no existe)")
    parser.add_argument("--entrada-prefijo", default="anuncios",
                        help="Prefijo de los CSV de entrada")
    parser.add_argument("--operaciones", nargs="+", choices=OPERACIONES,
                        default=list(OPERACIONES), help="Operaciones a procesar")
    parser.add_argument("--sin-validar", action="store_true",
                        help="Escribe las salidas aunque las validaciones fallen")
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        crudo = cargar_crudo(Path(args.entrada_dir), args.operaciones, args.entrada_prefijo)
    except FileNotFoundError as error:
        log.error("%s", error)
        return 1

    log.info("Total crudo: %s filas", f"{len(crudo):,}")
    limpio, cuarentena, consolidado, _ = transformar(crudo)

    log.info("Validación del flujo:")
    fallas = validar(limpio, cuarentena, consolidado)

    resumen = exportar(limpio, cuarentena, Path(args.salida_dir))
    log.info("Resumen: %s", json.dumps(resumen, ensure_ascii=False))

    if fallas:
        log.error("%d validaciones fallaron: %s", len(fallas), "; ".join(fallas))
        if not args.sin_validar:
            return 1
        log.warning("--sin-validar activo: se continúa pese a las fallas")

    log.info("Transformación completa: %s limpias, %s en cuarentena (%.2f %% de rechazo)",
             f"{len(limpio):,}", f"{len(cuarentena):,}", resumen["tasa_rechazo_%"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
