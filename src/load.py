"""Carga al lakehouse - quinta etapa (Load) del flujo ETL.

Sube las capas del pipeline a MinIO y puebla ClickHouse leyendo el gold desde el lago:

    s3://<bucket>/bronze/<tabla>/fecha=YYYY-MM-DD/datos.parquet   <- data/raw (extract + detail)
    s3://<bucket>/silver/<tabla>/fecha=YYYY-MM-DD/datos.parquet   <- transform
    s3://<bucket>/gold/<tabla>/fecha=YYYY-MM-DD/datos.parquet     <- enrich

    ClickHouse  <db>.anuncios   MergeTree, PARTITION BY fecha_carga

El esquema de la tabla EVOLUCIONA: si el gold trae columnas nuevas declaradas en
ESQUEMA_GOLD, se agregan con ALTER TABLE en vez de recrear la tabla y perder las
particiones anteriores.

El reparto de responsabilidades es deliberado: **MinIO es el lago y la fuente de verdad**,
ClickHouse es el warehouse. La data queda en dos lugares a propósito. Si mañana cambia el
esquema o hay que reprocesar, el lago tiene los Parquet originales y ClickHouse se
reconstruye desde ahí; al revés no se puede.

Sobre la idempotencia: la partición se borra antes de insertar, así que re-correr la carga
el mismo día reemplaza esa partición en vez de duplicar filas. Es lo que permite encadenar
la etapa en el pipeline periódico sin que la tabla crezca sola.

Sobre los tipos: el gold se normaliza a un esquema DECLARADO antes de subirlo, en vez de
dejar que Parquet y ClickHouse infieran cada uno por su cuenta. Sin eso, una columna que
hoy llega como `object` con nulos y mañana como `bool` rompe la inserción sin avisar.

Uso:
    python src/load.py
    python src/load.py --capas gold
    python src/load.py --fecha 2026-09-10
    python src/load.py --sin-clickhouse       # sólo sube al lago
    python src/load.py --recrear-tablas       # DROP + CREATE antes de insertar

Códigos de salida:
    0  la carga terminó y todas las validaciones pasaron
    1  faltaban archivos de entrada, no se pudo conectar, o una validación falló
"""

import argparse
import datetime as dt
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd

log = logging.getLogger("load")

CAPAS = ("bronze", "silver", "gold")

# Qué archivo alimenta cada tabla de cada capa. El bronze son los CSV del extract: se
# convierten a Parquet al subirlos, porque el lago guarda columnar, no texto.
FUENTES = {
    "bronze": {
        "anuncios_arriendo": ("raw", "anuncios_arriendo.csv"),
        "anuncios_venta": ("raw", "anuncios_venta.csv"),
        "detalle": ("raw", "detalle.parquet"),
    },
    "silver": {
        "anuncios": ("processed", "anuncios.parquet"),
        "cuarentena": ("processed", "cuarentena.parquet"),
    },
    "gold": {
        "anuncios_enriquecido": ("processed", "anuncios_enriquecido.parquet"),
    },
}

TABLA_CLICKHOUSE = "anuncios"
FUENTE_CLICKHOUSE = ("gold", "anuncios_enriquecido")

# Esquema declarado del gold. El orden es el de las columnas en la tabla.
# LowCardinality no es cosmético: sobre 45.000 filas con 3 valores distintos, la diferencia
# de tamaño y de velocidad en los GROUP BY es de un orden de magnitud.
# Quedan afuera las banderas BLOQUEANTES del transform (outlier_*, *_fuera_de_rango...):
# en el stage limpio son todas False por construcción y sólo sirven para auditar la
# cuarentena, que vive en el silver.
# Las mismas banderas que define transform.COMODIDADES, en el mismo orden. Un test
# (tests/test_consistencia.py) comprueba que las tres copias no se desincronicen.
COMODIDADES = [
    "tiene_ascensor", "tiene_piscina", "tiene_gimnasio", "tiene_conjunto_cerrado",
    "tiene_vigilancia", "tiene_cctv", "tiene_citofono", "tiene_salon_comunal",
    "tiene_zonas_verdes", "tiene_zona_ninos", "tiene_bbq", "tiene_canchas",
    "tiene_sauna_turco", "tiene_jacuzzi", "tiene_parqueadero_visitantes",
    "tiene_parqueadero_cubierto", "tiene_planta_electrica",
    "tiene_balcon", "tiene_terraza", "tiene_chimenea", "tiene_deposito", "tiene_estudio",
    "tiene_cocina_integral", "tiene_cuarto_servicio", "tiene_bano_servicio", "tiene_jardin",
    "tiene_vista_exterior", "tiene_vista_panoramica", "tiene_aire_acondicionado",
    "tiene_calefaccion", "tiene_walking_closet", "esta_amoblado", "es_monoambiente",
    "acepta_mascotas",
    "es_zona_rural", "cerca_transporte", "cerca_colegios", "cerca_parques",
    "cerca_supermercados", "cerca_centros_comerciales",
]
ESQUEMA_GOLD = [
    # Identidad y procedencia
    ("id_inmueble", "String", "str"),
    ("url", "String", "str"),
    ("texto", "String", "str"),
    ("tipo_inmueble", "LowCardinality(String)", "str"),
    ("tipo_feed", "LowCardinality(String)", "str"),
    ("operacion_feed", "LowCardinality(String)", "str"),
    ("operacion", "LowCardinality(String)", "str"),
    ("precio_texto", "String", "str"),
    ("fecha_extraccion", "LowCardinality(String)", "str"),
    ("ciudad", "LowCardinality(String)", "str"),
    ("ciudad_clave", "LowCardinality(String)", "str"),
    ("sector", "String", "str"),
    ("sector_clave", "String", "str"),
    # El inmueble
    ("area_m2", "Nullable(Float64)", "float"),
    ("area_privada", "Nullable(Float64)", "float"),
    ("habitaciones", "Nullable(Int8)", "int8"),
    ("banos", "Nullable(Int8)", "int8"),
    ("parqueaderos", "Nullable(Int8)", "int8"),
    # Las columnas que llegaron con el detalle van Nullable aunque el gold las traiga
    # siempre: en las particiones cargadas ANTES de que existieran, un ALTER ADD COLUMN
    # deja el default del tipo (false, ''), que se leería como dato. NULL dice la verdad.
    ("estrato", "Nullable(UInt8)", "uint8"),
    ("origen_estrato", "LowCardinality(Nullable(String))", "str_nulo"),
    ("antiguedad", "LowCardinality(Nullable(String))", "str_nulo"),
    ("antiguedad_ordinal", "Nullable(Int8)", "int8"),
    ("estado_inmueble", "LowCardinality(Nullable(String))", "str_nulo"),
    ("es_nuevo", "Nullable(Bool)", "bool_nulo"),
    ("es_proyecto", "Nullable(Bool)", "bool_nulo"),
    ("piso", "Nullable(Int16)", "int16"),
    ("administracion", "Nullable(Int64)", "int64"),
    ("comodidades", "Nullable(String)", "str_nulo"),
    *[(columna, "Nullable(Bool)", "bool_nulo") for columna in COMODIDADES],
    # El precio
    ("precio_venta", "Nullable(Int64)", "int64"),
    ("precio_arriendo", "Nullable(Int64)", "int64"),
    ("precio_m2", "Nullable(Float64)", "float"),
    ("precio_desde_detalle", "Nullable(Bool)", "bool_nulo"),
    ("precio_discrepante", "Nullable(Bool)", "bool_nulo"),
    # La ubicación: la coordenada final con su origen, y el respaldo OSM/Esri por detrás
    ("lat", "Nullable(Float64)", "float"),
    ("lon", "Nullable(Float64)", "float"),
    ("origen_coordenada", "LowCardinality(Nullable(String))", "str_nulo"),
    ("ubicacion_aproximada", "Nullable(Bool)", "bool_nulo"),
    ("distancia_centro_km", "Nullable(Float64)", "float"),
    ("barrio", "LowCardinality(Nullable(String))", "str_nulo"),
    ("zona", "LowCardinality(Nullable(String))", "str_nulo"),
    ("barrio_osm", "LowCardinality(Nullable(String))", "str_nulo"),
    ("match_barrio", "LowCardinality(String)", "str"),
    ("match_verificado", "Nullable(Bool)", "bool_nulo"),
    ("lat_barrio", "Nullable(Float64)", "float"),
    ("lon_barrio", "Nullable(Float64)", "float"),
    ("estrato_modal", "Nullable(UInt8)", "uint8"),
    ("estrato_promedio", "Nullable(Float64)", "float"),
    ("estrato_dispersion", "Nullable(Float64)", "float"),
    ("n_manzanas_estrato", "Nullable(UInt16)", "uint16"),
    # El anuncio (describe la publicación, no el inmueble: no entra al modelo)
    ("n_fotos", "Nullable(Int16)", "int16"),
    ("tiene_video", "Nullable(Bool)", "bool_nulo"),
    ("destacado", "Nullable(Bool)", "bool_nulo"),
    ("inmobiliaria_id", "LowCardinality(Nullable(String))", "str_nulo"),
    ("descripcion", "Nullable(String)", "str_nulo"),
    ("con_detalle", "Nullable(Bool)", "bool_nulo"),
    # Calidad: banderas informativas y trazabilidad
    ("es_dual", "Bool", "bool"),
    ("habitaciones_es_tope", "Bool", "bool"),
    ("banos_es_tope", "Bool", "bool"),
    ("parqueaderos_es_tope", "Bool", "bool"),
    ("estrato_invalido", "Nullable(Bool)", "bool_nulo"),
    ("coordenada_invalida", "Nullable(Bool)", "bool_nulo"),
    ("coordenada_lejana", "Nullable(Bool)", "bool_nulo"),
    ("area_privada_invalida", "Nullable(Bool)", "bool_nulo"),
    ("administracion_invalida", "Nullable(Bool)", "bool_nulo"),
    ("grupo_near_duplicado", "Nullable(Int32)", "int32_nulo"),
    ("es_near_duplicado", "Nullable(Bool)", "bool_nulo"),
    ("motivo_rechazo", "LowCardinality(String)", "str"),
    ("n_motivos_rechazo", "Int32", "int32"),
]

ORDEN_CLICKHOUSE = "(ciudad_clave, operacion, id_inmueble)"


# --------------------------------------------------------------------------------------
# 1. Configuración desde el entorno
# --------------------------------------------------------------------------------------

def configuracion():
    """Endpoints y credenciales. Los defaults sirven para correr desde el host.

    `MINIO_ENDPOINT` es la URL que usa ESTE proceso; `MINIO_ENDPOINT_CLICKHOUSE` es la que
    usa ClickHouse desde su propio contenedor. No son la misma: corriendo load.py en el
    host, el primero es localhost y el segundo tiene que seguir siendo el nombre del
    servicio, porque ClickHouse resuelve dentro de la red de Docker.
    """
    return {
        "minio_endpoint": os.environ.get("MINIO_ENDPOINT", "http://localhost:9000"),
        "minio_endpoint_ch": os.environ.get("MINIO_ENDPOINT_CLICKHOUSE",
                                            "http://minio:9000"),
        "minio_access": os.environ.get("MINIO_ACCESS_KEY", "valora"),
        "minio_secret": os.environ.get("MINIO_SECRET_KEY", "valora123"),
        "bucket": os.environ.get("MINIO_BUCKET", "valora"),
        "ch_host": os.environ.get("CLICKHOUSE_HOST", "localhost"),
        "ch_port": int(os.environ.get("CLICKHOUSE_PORT", "8123")),
        "ch_user": os.environ.get("CLICKHOUSE_USER", "valora"),
        "ch_password": os.environ.get("CLICKHOUSE_PASSWORD", "valora123"),
        "ch_db": os.environ.get("CLICKHOUSE_DB", "valora"),
    }


# --------------------------------------------------------------------------------------
# 2. Normalización al esquema declarado
# --------------------------------------------------------------------------------------

def normalizar_tipos(df):
    """Lleva el gold al esquema de ESQUEMA_GOLD, en ese orden y con esos tipos.

    Se hace acá y no al escribir el Parquet del enrich porque el esquema del lago es un
    contrato de la capa de carga: si el enrich agrega una columna, esta etapa lo tiene que
    decidir explícitamente, no arrastrarla sin revisar.
    """
    convertidores = {
        "str": lambda s: s.astype("string").fillna("").astype(str),
        "str_nulo": lambda s: s.astype("string"),
        "float": lambda s: pd.to_numeric(s, errors="coerce").astype("float64"),
        "int8": lambda s: pd.to_numeric(s, errors="coerce").astype("Int8"),
        "int16": lambda s: pd.to_numeric(s, errors="coerce").astype("Int16"),
        "int32": lambda s: pd.to_numeric(s, errors="coerce").fillna(0).astype("int32"),
        "int32_nulo": lambda s: pd.to_numeric(s, errors="coerce").astype("Int32"),
        "int64": lambda s: pd.to_numeric(s, errors="coerce").astype("Int64"),
        "uint8": lambda s: pd.to_numeric(s, errors="coerce").astype("UInt8"),
        "uint16": lambda s: pd.to_numeric(s, errors="coerce").astype("UInt16"),
        "bool": lambda s: s.fillna(False).astype(bool),
        "bool_nulo": lambda s: s.astype("boolean"),
    }
    faltantes = [c for c, _, _ in ESQUEMA_GOLD if c not in df.columns]
    if faltantes:
        raise ValueError(f"El gold no trae las columnas declaradas: {faltantes}")

    salida = pd.DataFrame(index=df.index)
    for columna, _, convertidor in ESQUEMA_GOLD:
        salida[columna] = convertidores[convertidor](df[columna])

    sobrantes = [c for c in df.columns if c not in salida.columns]
    if sobrantes:
        log.info("  columnas del gold que no entran al warehouse: %s", ", ".join(sobrantes))
    return salida


# --------------------------------------------------------------------------------------
# 3. Subida al lago
# --------------------------------------------------------------------------------------

def cliente_minio(config):
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=config["minio_endpoint"],
        aws_access_key_id=config["minio_access"],
        aws_secret_access_key=config["minio_secret"],
        region_name="us-east-1",
    )


def asegurar_bucket(cliente, bucket):
    from botocore.exceptions import ClientError
    try:
        cliente.head_bucket(Bucket=bucket)
    except ClientError:
        cliente.create_bucket(Bucket=bucket)
        log.info("  bucket '%s' creado", bucket)


def llave_de(capa, tabla, fecha):
    return f"{capa}/{tabla}/fecha={fecha}/datos.parquet"


def subir_capa(cliente, config, capa, raiz_datos, fecha):
    """Sube las tablas de una capa. Devuelve {tabla: filas}."""
    subidas = {}
    for tabla, (carpeta, archivo) in FUENTES[capa].items():
        origen = raiz_datos / carpeta / archivo
        if not origen.exists():
            log.warning("  %-24s falta %s: se omite", tabla, origen)
            continue

        df = (pd.read_csv(origen) if origen.suffix == ".csv"
              else pd.read_parquet(origen))
        if capa == "gold":
            df = normalizar_tipos(df)

        with tempfile.TemporaryDirectory() as temporal:
            intermedio = Path(temporal) / "datos.parquet"
            df.to_parquet(intermedio, index=False)
            llave = llave_de(capa, tabla, fecha)
            cliente.upload_file(str(intermedio), config["bucket"], llave)
            tamano = intermedio.stat().st_size

        subidas[tabla] = len(df)
        log.info("  %-24s %8s filas x %2d columnas -> s3://%s/%s (%.1f MB)",
                 tabla, f"{len(df):,}", df.shape[1], config["bucket"], llave,
                 tamano / 2 ** 20)
    return subidas


# --------------------------------------------------------------------------------------
# 4. Warehouse
# --------------------------------------------------------------------------------------

def cliente_clickhouse(config):
    import clickhouse_connect
    return clickhouse_connect.get_client(
        host=config["ch_host"], port=config["ch_port"],
        username=config["ch_user"], password=config["ch_password"],
    )


def crear_tablas(cliente, config, recrear=False):
    cliente.command(f"CREATE DATABASE IF NOT EXISTS {config['ch_db']}")
    destino = f"{config['ch_db']}.{TABLA_CLICKHOUSE}"
    if recrear:
        cliente.command(f"DROP TABLE IF EXISTS {destino}")
        log.info("  tabla %s eliminada (--recrear-tablas)", destino)

    columnas = ",\n    ".join(f"{nombre} {tipo}" for nombre, tipo, _ in ESQUEMA_GOLD)
    cliente.command(f"""
        CREATE TABLE IF NOT EXISTS {destino} (
            fecha_carga Date,
            {columnas}
        )
        ENGINE = MergeTree
        PARTITION BY fecha_carga
        ORDER BY {ORDEN_CLICKHOUSE}
    """)
    evolucionar_esquema(cliente, config, destino)
    log.info("  tabla %s lista (%d columnas + fecha_carga)", destino, len(ESQUEMA_GOLD))
    return destino


def evolucionar_esquema(cliente, config, destino):
    """Agrega a una tabla existente las columnas que el esquema declarado tiene y ella no.

    Es lo que permite que el pipeline sume columnas (como pasó con el detalle) sin obligar
    a un DROP. En las particiones cargadas antes del cambio la columna nueva queda en
    NULL, que es exactamente lo que significa "ese dato no existía cuando se cargó"; por
    eso las columnas nuevas se declaran Nullable aunque el gold las traiga siempre. Un
    cambio de TIPO de una columna existente no se aplica solo: se avisa y se resuelve con
    --recrear-tablas, porque puede perder datos.
    """
    existentes = dict(cliente.query(
        "SELECT name, type FROM system.columns WHERE database = %(db)s AND table = %(tabla)s",
        parameters={"db": config["ch_db"], "tabla": TABLA_CLICKHOUSE}).result_rows)
    nuevas = [(nombre, tipo) for nombre, tipo, _ in ESQUEMA_GOLD if nombre not in existentes]
    for nombre, tipo in nuevas:
        cliente.command(f"ALTER TABLE {destino} ADD COLUMN IF NOT EXISTS {nombre} {tipo}")
    if nuevas:
        log.info("  esquema evolucionado: %d columnas nuevas (%s)", len(nuevas),
                 ", ".join(nombre for nombre, _ in nuevas))
    distintas = [(nombre, existentes[nombre], tipo) for nombre, tipo, _ in ESQUEMA_GOLD
                 if nombre in existentes and existentes[nombre] != tipo]
    for nombre, actual, declarado in distintas:
        log.warning("  la columna %s es %s en la tabla y %s en el esquema: se deja como "
                    "está (usá --recrear-tablas para aplicar el tipo nuevo)",
                    nombre, actual, declarado)


def poblar_desde_lago(cliente, config, destino, fecha):
    """Borra la partición del día y la vuelve a insertar leyendo el Parquet desde MinIO.

    Borrar antes de insertar es lo que hace la carga idempotente: sin eso, correr el
    pipeline dos veces el mismo día duplicaría las 45.000 filas.
    """
    cliente.command(f"ALTER TABLE {destino} DROP PARTITION '{fecha}'")

    capa, tabla = FUENTE_CLICKHOUSE
    url = (f"{config['minio_endpoint_ch']}/{config['bucket']}/"
           f"{llave_de(capa, tabla, fecha)}")
    columnas = ", ".join(nombre for nombre, _, _ in ESQUEMA_GOLD)
    cliente.command(f"""
        INSERT INTO {destino} (fecha_carga, {columnas})
        SELECT toDate('{fecha}'), {columnas}
        FROM s3('{url}', '{config['minio_access']}', '{config['minio_secret']}', 'Parquet')
    """)
    return int(cliente.command(
        f"SELECT count() FROM {destino} WHERE fecha_carga = toDate('{fecha}')"))


# --------------------------------------------------------------------------------------
# 5. Validación
# --------------------------------------------------------------------------------------

def validar(cliente, config, destino, fecha, filas_esperadas):
    """Comprueba que lo que quedó en el warehouse es lo que se subió al lago."""
    fallas = []

    def revisar(condicion, mensaje):
        condicion = bool(condicion)
        log.info("  [%s] %s", "OK  " if condicion else "FALLA", mensaje)
        if not condicion:
            fallas.append(mensaje)

    en_clickhouse = int(cliente.command(
        f"SELECT count() FROM {destino} WHERE fecha_carga = toDate('{fecha}')"))
    revisar(en_clickhouse == filas_esperadas,
            f"ClickHouse tiene las mismas filas que el gold ({en_clickhouse:,} "
            f"vs {filas_esperadas:,})")

    duplicados = int(cliente.command(f"""
        SELECT count() FROM (
            SELECT id_inmueble, operacion, count() AS n
            FROM {destino} WHERE fecha_carga = toDate('{fecha}')
            GROUP BY id_inmueble, operacion HAVING n > 1)
    """))
    revisar(duplicados == 0,
            f"La llave (id_inmueble, operacion) es única en el warehouse ({duplicados} "
            f"duplicadas)")

    particiones = int(cliente.command(
        f"SELECT uniqExact(fecha_carga) FROM {destino}"))
    revisar(particiones >= 1, f"La tabla tiene {particiones} partición(es) de fecha")

    sin_precio = int(cliente.command(f"""
        SELECT count() FROM {destino}
        WHERE fecha_carga = toDate('{fecha}')
          AND precio_venta IS NULL AND precio_arriendo IS NULL
    """))
    revisar(sin_precio == 0, f"Toda fila tiene al menos un precio ({sin_precio} sin ninguno)")
    return fallas


# --------------------------------------------------------------------------------------
# Punto de entrada
# --------------------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Carga las capas del pipeline a MinIO y puebla ClickHouse")
    parser.add_argument("--datos-dir", default="data",
                        help="Raíz de los datos locales")
    parser.add_argument("--salida-dir", default="data/processed",
                        help="Dónde se escribe load_resumen.json")
    parser.add_argument("--capas", nargs="+", choices=CAPAS, default=list(CAPAS),
                        help="Capas a subir al lago")
    # Ojo con la zona horaria: el contenedor corre en UTC y el host en hora local, así
    # que la misma corrida a las 23:56 de Colombia escribe la partición de hoy desde el
    # host y la de mañana desde Docker. No rompe nada -son dos particiones válidas- pero
    # si querés que coincidan, pasá --fecha explícita.
    parser.add_argument("--fecha", default=dt.date.today().isoformat(),
                        help="Partición a escribir (YYYY-MM-DD). Por defecto, hoy "
                             "según el reloj del proceso (UTC dentro de Docker)")
    parser.add_argument("--sin-clickhouse", action="store_true",
                        help="Sube al lago y no toca el warehouse")
    parser.add_argument("--recrear-tablas", action="store_true",
                        help="DROP + CREATE de la tabla antes de insertar")
    parser.add_argument("--sin-validar", action="store_true",
                        help="No falla aunque las validaciones fallen")
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    config = configuracion()
    raiz_datos = Path(args.datos_dir)

    log.info("Lago: %s/%s | Warehouse: %s:%s/%s | partición: %s",
             config["minio_endpoint"], config["bucket"],
             config["ch_host"], config["ch_port"], config["ch_db"], args.fecha)

    try:
        cliente_lago = cliente_minio(config)
        asegurar_bucket(cliente_lago, config["bucket"])
    except ImportError:
        log.error("Falta boto3. Instalar con: pip install -r requirements.txt")
        return 1
    except Exception as error:
        log.error("No se pudo conectar a MinIO en %s: %s", config["minio_endpoint"], error)
        return 1

    subidas = {}
    for capa in args.capas:
        log.info("Subiendo la capa %s:", capa)
        try:
            subidas[capa] = subir_capa(cliente_lago, config, capa, raiz_datos, args.fecha)
        except (ValueError, FileNotFoundError) as error:
            log.error("%s", error)
            return 1

    capa_gold, tabla_gold = FUENTE_CLICKHOUSE
    filas_gold = subidas.get(capa_gold, {}).get(tabla_gold)
    resumen = {"fecha": args.fecha, "bucket": config["bucket"],
               "filas_por_capa": subidas, "clickhouse": None}
    fallas = []

    if args.sin_clickhouse:
        log.info("--sin-clickhouse activo: el warehouse queda sin tocar")
    elif filas_gold is None:
        log.warning("No se subió el gold en esta corrida: no hay con qué poblar ClickHouse")
    else:
        try:
            cliente_warehouse = cliente_clickhouse(config)
        except ImportError:
            log.error("Falta clickhouse-connect. Instalar con: pip install -r requirements.txt")
            return 1
        except Exception as error:
            log.error("No se pudo conectar a ClickHouse en %s:%s: %s",
                      config["ch_host"], config["ch_port"], error)
            return 1

        log.info("Poblando el warehouse:")
        destino = crear_tablas(cliente_warehouse, config, args.recrear_tablas)
        insertadas = poblar_desde_lago(cliente_warehouse, config, destino, args.fecha)
        log.info("  %s filas en la partición %s", f"{insertadas:,}", args.fecha)
        resumen["clickhouse"] = {"tabla": destino, "filas": insertadas}

        log.info("Validación de la carga:")
        fallas = validar(cliente_warehouse, config, destino, args.fecha, filas_gold)

    salida = Path(args.salida_dir)
    salida.mkdir(parents=True, exist_ok=True)
    ruta = salida / "load_resumen.json"
    ruta.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("  %s", ruta.name)

    if fallas:
        log.error("%d validaciones fallaron: %s", len(fallas), "; ".join(fallas))
        if not args.sin_validar:
            return 1
        log.warning("--sin-validar activo: se continúa pese a las fallas")

    total = sum(sum(tablas.values()) for tablas in subidas.values())
    log.info("Carga completa: %s filas subidas al lago en %d capa(s)",
             f"{total:,}", len(subidas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
