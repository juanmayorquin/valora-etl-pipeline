"""Transformación de los anuncios crudos - tercera etapa (Transform) del flujo ETL.

Lee los CSV que dejó `extract.py` y el `detalle.parquet` que dejó `detail.py`, ambos en
`data/raw/`, y produce dos stages en `data/processed/`:

    anuncios.{csv,parquet}     stage limpio: lo que consume el análisis
    cuarentena.{csv,parquet}   rechazadas, cada una con su `motivo_rechazo`
    transform_resumen.json     conteos de la corrida, para monitoreo

La cuarentena no es un descarte sino una separación: queda en disco, auditable, y si
una regla resulta demasiado estricta se reprocesa desde ahí.

Las reglas (R2-R12 de parseo, D0-D7 de distribución) salieron del análisis exploratorio
en `notebooks/01_eda_datos_crudos.ipynb`; el flujo se prototipó en
`notebooks/02_transform_prototipo.ipynb`. R13 y R14 llegaron con el detalle.

El orden de aplicación importa y no es negociable:

    1. Normalizar esquema      ->  un solo contrato de columnas + tipo desde el slug (R3)
    2. Unir el detalle         ->  estrato, coordenada, antigüedad, administración... por id
    3. Operación y duales      ->  R4 + D0: separa precio_venta / precio_arriendo. El
                                   número del detalle manda sobre el texto de la tarjeta
    4. Saneamiento de precio   ->  R5, R6
    5. Saneamiento de área     ->  R7 + D4 (area_posible_lote)
    6. Saneamiento del detalle ->  R13: estrato 1-6, coordenada en Colombia, área privada,
                                   piso y administración plausibles
    7. Comodidades             ->  R14: una bandera por comodidad frecuente
    8. Derivar precio_m2       ->  sólo sobre lo que sobrevivió a 4 y 5
    9. Outliers IQR log        ->  D1, D2, D3
   10. Consolidar y separar    ->  R11 + near-duplicados + compuerta de calidad

Calcular `precio_m2` antes del paso 3 es el error clásico: se divide un precio de venta
que estaba en el feed de arriendo y el indicador nace roto.

Uso:
    python src/transform.py
    python src/transform.py --entrada-dir data/raw --salida-dir data/processed
    python src/transform.py --operaciones arriendo
    python src/transform.py --sin-detalle       # sólo con la tarjeta, sin detalle.parquet
    python src/transform.py --sin-validar       # no falla aunque las validaciones fallen

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


# --------------------------------------------------------------------------------------
# 1b. El detalle de cada anuncio - lo que dejó detail.py
# --------------------------------------------------------------------------------------

# Columnas del detalle que entran al contrato tal cual.
COLUMNAS_DETALLE = [
    "estrato", "antiguedad", "estado_inmueble", "es_proyecto", "administracion",
    "area_privada", "lat", "lon", "ubicacion_aproximada", "barrio", "zona", "piso",
    "comodidades", "n_fotos", "tiene_video", "descripcion", "inmobiliaria_id", "destacado",
]
# Columnas del detalle que se RECONCILIAN con la tarjeta (precio, conteos) y después se
# descartan: en el stage queda una sola versión de cada dato, no dos.
COLUMNAS_DETALLE_RECONCILIADAS = [
    "precio_venta_detalle", "precio_arriendo_detalle",
    "habitaciones_detalle", "banos_detalle", "parqueaderos_detalle",
]


def cargar_detalle(ruta):
    """Lee detalle.parquet y se queda con los anuncios que trajeron datos."""
    detalle = pd.read_parquet(ruta)
    con_datos = detalle[detalle["estado"].eq("ok")]
    if con_datos["id_inmueble"].duplicated().any():
        raise ValueError(f"{ruta}: hay id_inmueble repetidos en el detalle")
    log.info("  %-28s %s anuncios con detalle de %s resueltos %s", ruta.name,
             f"{len(con_datos):,}", f"{len(detalle):,}",
             detalle["estado"].value_counts().to_dict())
    return con_datos[["id_inmueble"] + COLUMNAS_DETALLE + COLUMNAS_DETALLE_RECONCILIADAS]


def unir_detalle(crudo, detalle):
    """Left join por id: ninguna fila se pierde ni se duplica. Un anuncio sin detalle
    (bajado del sitio entre el extract y el detail) sigue con lo que trajo la tarjeta,
    con las columnas nuevas en nulo y `con_detalle = False`."""
    if detalle is None:
        for columna in COLUMNAS_DETALLE + COLUMNAS_DETALLE_RECONCILIADAS:
            crudo[columna] = pd.NA
        crudo["con_detalle"] = False
        return crudo
    antes = len(crudo)
    unido = crudo.merge(detalle, on="id_inmueble", how="left", validate="many_to_one")
    unido["con_detalle"] = unido["id_inmueble"].isin(detalle["id_inmueble"]).astype(bool)
    if len(unido) != antes:
        raise ValueError(f"El join con el detalle cambió el número de filas: {antes} -> {len(unido)}")
    log.info("Detalle unido: %.2f %% de las filas lo tienen", unido["con_detalle"].mean() * 100)
    return unido


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
    quedar en una sola columna.

    El detalle trae los dos precios como número y manda sobre el texto de la tarjeta.
    Para un dual, el canon que antes quedaba en NaN ("no lo conocemos") ahora se conoce.
    `precio_discrepante` marca las filas donde tarjeta y detalle difieren más de 1 %: es
    información sobre la fuente, no un motivo de rechazo.
    """
    tarjeta = a_entero(df["precio_texto"])
    es_venta = df["operacion_feed"].eq("venta")
    venta_tarjeta = tarjeta.where(es_venta | df["es_dual"])
    arriendo_tarjeta = tarjeta.where(~es_venta & ~df["es_dual"])

    venta_detalle = pd.to_numeric(df["precio_venta_detalle"], errors="coerce").astype("Int64")
    arriendo_detalle = pd.to_numeric(df["precio_arriendo_detalle"], errors="coerce").astype("Int64")
    df["precio_venta"] = venta_detalle.fillna(venta_tarjeta)
    df["precio_arriendo"] = arriendo_detalle.fillna(arriendo_tarjeta)
    df["precio_desde_detalle"] = (venta_detalle.notna() | arriendo_detalle.notna()).astype(bool)

    # Lo que muestra la tarjeta, comparado con el mismo precio en el detalle
    detalle = venta_detalle.where(es_venta | df["es_dual"], arriendo_detalle)
    diferencia = (tarjeta.astype("Float64") - detalle.astype("Float64")).abs()
    df["precio_discrepante"] = (
        (diferencia > detalle.astype("Float64") * 0.01).fillna(False).astype(bool))
    log.info("D0 - precio desde el detalle: %s filas | discrepa con la tarjeta: %s",
             f"{int(df['precio_desde_detalle'].sum()):,}",
             f"{int(df['precio_discrepante'].sum()):,}")
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
    """R6 antes que R5: si no, el rango da por bueno un relleno que cae dentro.

    El relleno se busca sobre el precio ya elegido (detalle o tarjeta), no sobre el texto
    de la tarjeta: un anuncio con "$1.111.111" en la tarjeta y un número real en el
    detalle se rescata en vez de irse a cuarentena.
    """
    df["precio_relleno"] = (es_relleno(df["precio_venta"].astype("string").fillna(""))
                            | es_relleno(df["precio_arriendo"].astype("string").fillna("")))
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
    """El precio que corresponde a la operación de la fila. Un dual ('ambas') se mide por
    su precio de venta: es el que tiene siempre y el que publica en los dos feeds. Su
    canon, cuando el detalle lo trae, queda en `precio_arriendo` para el modelo."""
    arriendo = df["precio_arriendo"].astype("Float64")
    venta = df["precio_venta"].astype("Float64")
    return arriendo.where(df["operacion"].eq("arriendo"), venta)


# --------------------------------------------------------------------------------------
# 4b. Saneamiento de las columnas del detalle - R13
# --------------------------------------------------------------------------------------

# Colombia entera, islas incluidas. Una coordenada fuera de acá es un error de carga del
# anunciante (lat/lon invertidas, 0/0, otro país), no un inmueble.
BBOX_COLOMBIA = {"lat": (-4.3, 13.6), "lon": (-82.0, -66.8)}
RANGO_ESTRATO = (1, 6)
RANGO_PISO = (1, 60)
# El área privada puede ser igual a la construida (el sitio a veces repite el valor) pero
# no mayor: si lo es, alguien cargó los campos al revés.
TOLERANCIA_AREA_PRIVADA = 1.05

# Del texto del sitio a un ordinal. "Remodelado" no es una edad: queda sin ordinal y
# conserva el texto.
ANTIGUEDAD_ORDINAL = {
    "Menos de 1 año": 0,
    "Entre 0 y 5 años": 1,
    "Entre 5 y 10 años": 2,
    "Entre 10 y 20 años": 3,
    "Más de 20 años": 4,
}


def sanear_detalle(df):
    """Reglas informativas: anulan el valor imposible y lo marcan, la fila sigue. Un
    estrato 7 no existe en Colombia, pero el anuncio sigue siendo un inmueble válido."""
    # Se acota ANTES de castear: `astype("Int8")` revienta con un solo valor fuera de
    # rango, y un estrato "200" mal cargado no puede tirar abajo la transformación.
    estrato = pd.to_numeric(df["estrato"], errors="coerce").astype("float64")
    fuera = (estrato.notna() & ~estrato.between(*RANGO_ESTRATO)).astype(bool)
    df["estrato_invalido"] = fuera
    df["estrato"] = estrato.where(~fuera).astype("Int8")

    lat = pd.to_numeric(df["lat"], errors="coerce").astype("Float64")
    lon = pd.to_numeric(df["lon"], errors="coerce").astype("Float64")
    dentro = lat.between(*BBOX_COLOMBIA["lat"]) & lon.between(*BBOX_COLOMBIA["lon"])
    fuera = ((lat.notna() | lon.notna()) & ~dentro).fillna(False).astype(bool)
    df["coordenada_invalida"] = fuera
    df["lat"] = lat.where(~fuera)
    df["lon"] = lon.where(~fuera)

    privada = pd.to_numeric(df["area_privada"], errors="coerce").astype("Float64")
    fuera = (privada.notna()
             & (privada > df["area_m2"] * TOLERANCIA_AREA_PRIVADA)).fillna(False).astype(bool)
    df["area_privada_invalida"] = fuera
    df["area_privada"] = privada.where(~fuera)

    piso = pd.to_numeric(df["piso"], errors="coerce").astype("float64")
    df["piso"] = piso.where(piso.between(*RANGO_PISO)).astype("Int16")

    # Una administración mayor que el canon es un error de carga (o el total mensual
    # puesto en el campo equivocado). En venta no hay contra qué compararla.
    admin = pd.to_numeric(df["administracion"], errors="coerce").astype("Int64")
    fuera = (admin.notna() & df["precio_arriendo"].notna()
             & (admin > df["precio_arriendo"])).fillna(False).astype(bool)
    df["administracion_invalida"] = fuera
    df["administracion"] = admin.where(~fuera)

    df["antiguedad_ordinal"] = df["antiguedad"].map(ANTIGUEDAD_ORDINAL).astype("Int8")
    df["es_nuevo"] = df["estado_inmueble"].eq("Nuevo").fillna(False).astype(bool)
    for columna in ("es_proyecto", "tiene_video", "destacado"):
        df[columna] = df[columna].fillna(False).astype(bool)
    df["ubicacion_aproximada"] = df["ubicacion_aproximada"].astype("boolean")
    n_fotos = pd.to_numeric(df["n_fotos"], errors="coerce").astype("float64")
    df["n_fotos"] = n_fotos.where(n_fotos.between(0, 32_767)).astype("Int16")

    for columna in ("estrato_invalido", "coordenada_invalida", "area_privada_invalida",
                    "administracion_invalida"):
        log.info("R13 - %-24s anulados: %d", columna, int(df[columna].sum()))
    log.info("R13 - con estrato: %s | con coordenada: %s | con antigüedad: %s",
             f"{int(df['estrato'].notna().sum()):,}", f"{int(df['lat'].notna().sum()):,}",
             f"{int(df['antiguedad_ordinal'].notna().sum()):,}")
    return df


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
        tarjeta = pd.to_numeric(df[columna], errors="coerce").astype("float64")
        detalle = pd.to_numeric(df[f"{columna}_detalle"], errors="coerce").astype("float64")
        # El detalle rellena lo que la tarjeta no trae: el sitio omite el dato en la
        # tarjeta cuando es 0 (un quinto de los parqueaderos). Sigue censurado en el
        # tope, porque la ficha también publica "5 o más". El clip va antes del cast a
        # Int8: un "150" mal cargado no cabe en el tipo y tiraría la corrida.
        valores = tarjeta.fillna(detalle).clip(lower=0, upper=tope).astype("Int8")
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
    # El barrio y la zona del detalle vienen en mayúsculas o como los cargó el anunciante
    for columna in ("barrio", "zona"):
        df[columna] = normalizar_lugar(df[columna])
    return df


# --------------------------------------------------------------------------------------
# 6b. Comodidades - R14
# --------------------------------------------------------------------------------------

# Una bandera por comodidad frecuente. La clave es la columna; el valor, lo que se busca
# al INICIO de cada ítem del detalle, ya en minúscula y sin tildes. Los ítems van unidos
# por " | ", así que el ancla `(?:^|\| )` evita que "tipo de piso en estudio" cuente como
# estudio o que "cerca a gimnasio" cuente como gimnasio. La lista y las expresiones salen
# del vocabulario real de detalle_resumen.json (3.687 ítems distintos): entra lo que
# aparece en más del 4 % de los anuncios y describe algo que mueve el precio.
COMODIDADES = {
    # Del edificio o del conjunto
    "tiene_ascensor": r"ascensor(?=$| \|)|numero de ascensores [1-9]",
    "tiene_piscina": r"piscina",
    "tiene_gimnasio": r"gimnasio(?=$| \|)",
    "tiene_conjunto_cerrado": r"(?:conjunto|unidad) cerrad",
    "tiene_vigilancia": r"vigilancia|porteria",
    "tiene_cctv": r"circuito cerrado de tv",
    "tiene_citofono": r"citofono",
    "tiene_salon_comunal": r"salon (?:comunal|social)",
    "tiene_zonas_verdes": r"zonas? verdes?",
    "tiene_zona_ninos": r"zona (?:para|de) ninos|parque infantil|juegos infantiles",
    "tiene_bbq": r"(?:zona de )?bbq|asador",
    "tiene_canchas": r"cancha",
    "tiene_sauna_turco": r"sauna|turco",
    "tiene_jacuzzi": r"jacuzzi",
    "tiene_parqueadero_visitantes": r"parqueadero (?:de )?visitantes",
    "tiene_parqueadero_cubierto": r"(?:caracteristicas del )?parqueadero cubierto",
    "tiene_planta_electrica": r"planta electrica",
    # Del inmueble
    "tiene_balcon": r"terraza/balcon balcon|balcon(?=$| \|)",
    "tiene_terraza": r"terraza/balcon terraza|con terraza|terraza rooftop|terraza(?=$| \|)",
    "tiene_chimenea": r"(?:con )?chimenea",
    "tiene_deposito": r"deposito(?! 0\b)|cuarto util",
    "tiene_estudio": r"estudio o biblioteca|estudio(?=$| \|)",
    "tiene_cocina_integral": r"cocina integral",
    "tiene_cuarto_servicio": r"cuarto de servicio",
    "tiene_bano_servicio": r"bano de servicio",
    "tiene_jardin": r"jardin(?=$| \|)|jardin interior",
    "tiene_vista_exterior": r"vista exterior",
    "tiene_vista_panoramica": r"vista panoramica",
    "tiene_aire_acondicionado": r"aire acondicionado",
    "tiene_calefaccion": r"(?:con )?calefaccion",
    "tiene_walking_closet": r"walking closet",
    "esta_amoblado": r"(?:equipado / )?amoblado|amueblado",
    "es_monoambiente": r"monoambiente",
    "acepta_mascotas": r"se permiten mascotas",
    # Del entorno, según lo declara el anunciante. Son los "puntos de interés" que en la
    # ablación de OSM no aportaron; acá vuelven a medirse en su versión autorreportada.
    "es_zona_rural": r"area rural",
    "cerca_transporte": r"cerca transporte publico",
    "cerca_colegios": r"cerca colegios|cerca a jardines y colegios",
    "cerca_parques": r"cerca parques",
    "cerca_supermercados": r"cerca supermercados",
    "cerca_centros_comerciales": r"cerca centros comerciales",
}


def derivar_comodidades(df):
    """Una columna booleana por comodidad. Se busca en el texto completo con el ancla de
    ítem, vectorizado: 50.000 filas por 40 patrones son segundos."""
    items = df["comodidades"].astype("string").fillna("").map(sin_tilde).str.lower()
    for columna, patron in COMODIDADES.items():
        df[columna] = items.str.contains(rf"(?:^|\| ){patron}", regex=True).astype(bool)
    frecuencias = {c: round(float(df[c].mean() * 100), 1) for c in COMODIDADES}
    log.info("R14 - comodidades (%% de filas): %s", frecuencias)
    return df


# --------------------------------------------------------------------------------------
# 7. Precio por m² y outliers - D1, D2, D3
# --------------------------------------------------------------------------------------

# Un segmento con menos observaciones que esto no da una valla confiable y cae al
# respaldo global de su operación.
N_MINIMO_SEGMENTO = 300
OPERACION_DE_COLUMNA = {"precio_arriendo": "arriendo", "precio_venta": "venta"}


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
                # El respaldo es la operación dueña de la columna: el canon de un dual se
                # mide contra los arriendos, no contra los otros pocos duales.
                duena = OPERACION_DE_COLUMNA.get(columna, operacion)
                respaldo = df["operacion"].eq(duena) & es_residencial
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
    "con_detalle", "precio_desde_detalle", "precio_discrepante", "estrato_invalido",
    "coordenada_invalida", "area_privada_invalida", "administracion_invalida",
    "es_near_duplicado",
]

CLAVE = ["id_inmueble", "operacion"]


def consolidar(df):
    antes = len(df)
    # Los duales llegan por los dos feeds: una sola fila por (id_inmueble, operacion)
    df = df.sort_values("operacion_feed").drop_duplicates(
        subset=CLAVE, keep="first").reset_index(drop=True)
    log.info("R11 - filas: %d -> %d (%d consolidadas)", antes, len(df), antes - len(df))
    return df


def marcar_near_duplicados(df):
    """Mismo proyecto o anuncio republicado con otro id: misma ciudad, sector, tipo, área
    y precio. El grupo viaja en el dataset para que el split del modelo no vea la
    respuesta en train y la pregunte en test (GroupKFold), y para que el warehouse pueda
    deduplicar. Antes este cálculo vivía en un notebook, donde nadie lo reproduce."""
    llave = (df["ciudad_clave"].astype("string").fillna("") + "|"
             + df["sector_clave"].astype("string").fillna("") + "|"
             + df["tipo_inmueble"].astype("string").fillna("") + "|"
             + df["area_m2"].astype("string").fillna("") + "|"
             + precio_unificado(df).astype("string").fillna(""))
    df["grupo_near_duplicado"] = pd.factorize(llave)[0].astype("int32")
    tamano = df.groupby("grupo_near_duplicado")["grupo_near_duplicado"].transform("size")
    df["es_near_duplicado"] = (tamano > 1).astype(bool)
    log.info("Near-duplicados: %s filas (%.2f %%) repiten ciudad, sector, tipo, área y precio",
             f"{int(df['es_near_duplicado'].sum()):,}", df["es_near_duplicado"].mean() * 100)
    return df


def marcar_ausencias(df):
    """Sin precio o sin área no hay análisis posible: son motivos de rechazo por derecho
    propio. El precio que cuenta es el de la operación de la fila: un arriendo cuyo canon
    se anuló no se salva porque el detalle traiga un precio de venta."""
    df["sin_precio"] = precio_unificado(df).isna()
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
    revisar(not (limpio["es_dual"] & limpio["precio_arriendo"].notna()
                 & ~limpio["precio_desde_detalle"]).any(),
            "D0 - ningún dual conserva un canon que no venga del detalle")
    revisar(limpio["area_m2"].between(*RANGO_AREA).all(),
            "R7 - toda área está dentro de rango")

    log.info("Contrato del detalle (R13/R14):")
    revisar(limpio["estrato"].dropna().between(*RANGO_ESTRATO).all(),
            "R13 - todo estrato está entre 1 y 6")
    revisar(limpio["lat"].dropna().between(*BBOX_COLOMBIA["lat"]).all()
            and limpio["lon"].dropna().between(*BBOX_COLOMBIA["lon"]).all(),
            "R13 - toda coordenada cae dentro de Colombia")
    revisar(limpio["lat"].notna().eq(limpio["lon"].notna()).all(),
            "R13 - lat y lon van juntas: nunca una sin la otra")
    con_privada = limpio["area_privada"].notna()
    revisar((limpio.loc[con_privada, "area_privada"]
             <= limpio.loc[con_privada, "area_m2"] * TOLERANCIA_AREA_PRIVADA).all(),
            "R13 - ninguna área privada supera la construida")
    revisar(not (limpio["administracion"].notna() & limpio["precio_arriendo"].notna()
                 & (limpio["administracion"] > limpio["precio_arriendo"])).any(),
            "R13 - ninguna administración supera el canon")
    revisar(limpio["piso"].dropna().between(*RANGO_PISO).all(),
            "R13 - todo piso está entre 1 y 60")
    if limpio["con_detalle"].any():
        cobertura = limpio["con_detalle"].mean()
        revisar(cobertura > 0.9,
                f"Detalle - más del 90 % del stage limpio tiene detalle ({cobertura * 100:.1f} %)")
        con_estrato = limpio.loc[limpio["con_detalle"], "estrato"].notna().mean()
        revisar(con_estrato > 0.9,
                f"Detalle - más del 90 % de las filas con detalle tienen estrato "
                f"({con_estrato * 100:.1f} %)")
    revisar(limpio[list(COMODIDADES)].dtypes.eq(bool).all(),
            "R14 - toda bandera de comodidad es booleana")
    revisar(limpio["grupo_near_duplicado"].notna().all(),
            "Near-duplicados - toda fila limpia tiene grupo")

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
        # Salud del detalle: si `con_detalle` cae, el sitio cambió la página de detalle y
        # hay que revisar el parser de detail.py, no este script.
        "con_detalle_%": round(todo["con_detalle"].mean() * 100, 2),
        "precio_desde_detalle_%": round(todo["precio_desde_detalle"].mean() * 100, 2),
        "precio_discrepante_%": round(todo["precio_discrepante"].mean() * 100, 2),
        "invalidos_detalle": {c: int(todo[c].sum()) for c in (
            "estrato_invalido", "coordenada_invalida", "area_privada_invalida",
            "administracion_invalida")},
        "cobertura_limpio_%": {c: round(float(limpio[c].notna().mean() * 100), 2) for c in (
            "estrato", "lat", "antiguedad_ordinal", "administracion", "area_privada",
            "piso")},
        "estrato_limpio": {str(int(k)): int(v) for k, v in
                           limpio["estrato"].value_counts().sort_index().items()},
        "near_duplicados_limpio_%": round(limpio["es_near_duplicado"].mean() * 100, 2),
        "comodidades_limpio_%": {c: round(float(limpio[c].mean() * 100), 1)
                                 for c in COMODIDADES},
    }
    ruta = directorio / "transform_resumen.json"
    ruta.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("  %s", ruta.name)
    return resumen


# --------------------------------------------------------------------------------------
# Orquestación
# --------------------------------------------------------------------------------------

def transformar(crudo, detalle=None):
    """Aplica el flujo completo sobre el crudo ya cargado. Devuelve (limpio, cuarentena,
    consolidado, reporte_vallas)."""
    crudo = unir_detalle(crudo, detalle)
    crudo = resolver_tipo(crudo)

    crudo = resolver_operacion(crudo)
    crudo = separar_precios(crudo)
    log.info("Operación resuelta: %s | duales: %d | títulos sin parsear: %d",
             crudo["operacion"].value_counts(dropna=False).to_dict(),
             int(crudo["es_dual"].sum()), int(crudo["titulo_sin_parsear"].sum()))

    crudo = sanear_precios(crudo)
    crudo = sanear_areas(crudo)
    crudo = sanear_detalle(crudo)
    crudo = marcar_area_posible_lote(crudo)
    crudo = marcar_censuradas(crudo)
    crudo = normalizar_texto(crudo)
    crudo = derivar_comodidades(crudo)

    crudo = derivar_precio_m2(crudo)
    crudo, reporte_vallas = marcar_outliers(crudo)
    log.info("precio_m2 calculable en %d de %d filas",
             int(crudo["precio_m2"].notna().sum()), len(crudo))
    # Lo reconciliado ya vive en las columnas del contrato; no se publica por duplicado
    crudo = crudo.drop(columns=COLUMNAS_DETALLE_RECONCILIADAS)

    consolidado = consolidar(crudo)
    consolidado = marcar_near_duplicados(consolidado)
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
    parser.add_argument("--detalle", default="data/raw/detalle.parquet",
                        help="Parquet con el detalle de cada anuncio (salida de detail.py)")
    parser.add_argument("--sin-detalle", action="store_true",
                        help="Procesar sólo con la tarjeta, sin unir el detalle")
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

    detalle = None
    if not args.sin_detalle:
        ruta_detalle = Path(args.detalle)
        if not ruta_detalle.exists():
            log.error("No existe %s. Corré `python src/detail.py` o pasá --sin-detalle",
                      ruta_detalle)
            return 1
        detalle = cargar_detalle(ruta_detalle)

    log.info("Total crudo: %s filas", f"{len(crudo):,}")
    limpio, cuarentena, consolidado, _ = transformar(crudo, detalle)

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
