"""Detalle de cada anuncio - segunda etapa (Detail) del flujo ETL.

Lee los CSV que dejó `extract.py` en `data/raw/`, visita la página de detalle de cada
anuncio y extrae el JSON que la página trae embebido. No hace falta navegador: la página
responde por HTTP plano en medio segundo, así que 50.000 anuncios a 8 hilos son menos de
una hora, no las horas que tarda el barrido con Chromium.

De dónde sale el dato: la página es una app de React Server Components y serializa el
inmueble en chunks `self.__next_f.push([1,"..."])`. Uno de esos chunks contiene el objeto
`"data":{"propertyId":...}` con 83 campos: coordenadas, estrato, antigüedad, administración,
área privada, comodidades, precios como número, estado (usado / nuevo / proyecto)...

Qué se guarda y qué no: se conservan los atributos del inmueble y del anuncio. Teléfonos,
WhatsApp y dirección del anunciante se descartan en el parser y no se escriben nunca. De la
inmobiliaria queda sólo su id.

Produce en `data/raw/`:

    detalle.parquet          una fila por anuncio (se versiona: es dato de origen)
    detalle_resumen.json     éxito / no disponibles / errores, cobertura, frecuencias
    detalle/partes.jsonl     caché reanudable, una línea por anuncio (no se versiona)

La etapa es reanudable: cada resultado se anexa al JSONL apenas llega, y al arrancar se
saltan los anuncios ya resueltos. Un corte a mitad de camino cuesta segundos, no la corrida.

Uso:
    python src/detail.py
    python src/detail.py --muestra 200            # para probar el entorno
    python src/detail.py --hilos 4 --pausa 0.3    # más suave con el sitio

Códigos de salida:
    0  terminó y la tasa de éxito superó --minimo-exito
    1  no había CSV de entrada, el sitio bloqueó la corrida, o la tasa quedó por debajo
"""

import argparse
import gzip
import json
import logging
import os
import re
import sys
import threading
import time
import traceback
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

log = logging.getLogger("detail")

# El sitio está detrás de Incapsula y sirve la página completa a un navegador común. Se
# firma además con el nombre del proyecto para que quede identificado en sus logs.
AGENTE = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/128.0 Safari/537.36 valora-etl-pipeline/0.1"),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "es-CO,es;q=0.9",
    "Accept-Encoding": "gzip",
}
TIEMPO_ESPERA_S = 30
ESPERAS_REINTENTO_S = (0, 5, 20, 60)
# Si el sitio empieza a responder 403/429, TODOS los hilos frenan este tiempo antes de
# seguir. Insistir contra un bloqueo sólo lo alarga.
ENFRIAMIENTO_S = 90
# Cortar la corrida si se encadenan tantos fallos seguidos: es un bloqueo o una caída,
# no mala suerte, y el JSONL permite retomar después.
FALLOS_SEGUIDOS_MAXIMO = 40
# Watchdog: si en este tiempo no termina ningún anuncio, algo se trabó. Primero se vuelcan
# los stacks de todos los hilos al log (para saber DÓNDE), y si sigue sin progreso se
# aborta con código 1: el JSONL ya tiene todo lo bajado y la corrida siguiente retoma.
SIN_PROGRESO_AVISO_S = 120
SIN_PROGRESO_ABORTO_S = 300
# Una respuesta que gotea bytes cada pocos segundos nunca dispara el timeout por
# operación del socket; por eso hay además un techo total por descarga.
DESCARGA_MAXIMA_S = 60

INICIO_CHUNK = 'self.__next_f.push([1,"'
MARCA_OBJETO = '"data":{"propertyId"'
PATRON_PISO = re.compile(r"^n[uú]mero de piso\s+(\d+)$", re.IGNORECASE)

# Estados finales por anuncio. `error` es transitorio: la corrida siguiente lo reintenta.
OK, NO_DISPONIBLE, SIN_DATOS, ERROR = "ok", "no_disponible", "sin_datos", "error"
ESTADOS_FINALES = (OK, NO_DISPONIBLE, SIN_DATOS)


# --------------------------------------------------------------------------------------
# Entrada
# --------------------------------------------------------------------------------------

def cargar_urls(entrada_dir, prefijo="anuncios"):
    """Ids únicos con su URL, desde los CSV del extract. Un inmueble puede estar en los
    dos feeds (dual): se visita una sola vez."""
    partes = []
    for ruta in sorted(Path(entrada_dir).glob(f"{prefijo}_*.csv")):
        partes.append(pd.read_csv(ruta, usecols=["id_inmueble", "url"], dtype=str))
        log.info("  %-28s %s filas", ruta.name, f"{len(partes[-1]):,}")
    if not partes:
        raise FileNotFoundError(f"No hay CSV '{prefijo}_*.csv' en {entrada_dir}")
    urls = (pd.concat(partes, ignore_index=True)
              .dropna(subset=["id_inmueble", "url"])
              .drop_duplicates(subset="id_inmueble")
              .reset_index(drop=True))
    return urls


def leer_partes(ruta):
    """Lee el JSONL de corridas anteriores. Devuelve {id: registro}, quedándose con el
    último registro de cada id."""
    registros = {}
    if not ruta.exists():
        return registros
    with open(ruta, encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip()
            if not linea:
                continue
            try:
                registro = json.loads(linea)
            except json.JSONDecodeError:
                continue   # línea cortada por una interrupción: se ignora y se rehace
            registros[registro["id_inmueble"]] = registro
    return registros


# --------------------------------------------------------------------------------------
# Descarga
# --------------------------------------------------------------------------------------

_enfriamiento_hasta = 0.0
_candado = threading.Lock()


def esperar_enfriamiento():
    """Si otro hilo detectó un bloqueo, todos esperan a que pase."""
    while True:
        with _candado:
            restante = _enfriamiento_hasta - time.monotonic()
        if restante <= 0:
            return
        time.sleep(min(restante, 5))


def activar_enfriamiento(segundos=ENFRIAMIENTO_S):
    """Sólo si no hay uno en curso: si cada 403 lo extendiera, ocho hilos reintentando
    a la vez lo prolongarían entre todos para siempre."""
    global _enfriamiento_hasta
    with _candado:
        if _enfriamiento_hasta <= time.monotonic():
            _enfriamiento_hasta = time.monotonic() + segundos
            log.warning("El sitio respondió 403/429: todos los hilos esperan %d s", segundos)


def url_ascii(url):
    """urllib exige URLs ASCII y el sitio publica slugs con tildes o guiones suaves
    (U+00AD). Se percent-codifica lo que haga falta y se deja el resto intacto."""
    return urllib.parse.quote(url, safe="/:?=&%#+@,;")


def descargar(url):
    """Devuelve (estado, html). `estado` es OK, NO_DISPONIBLE o ERROR."""
    url = url_ascii(url)
    for intento, espera in enumerate(ESPERAS_REINTENTO_S):
        if espera:
            time.sleep(espera)
        esperar_enfriamiento()
        peticion = urllib.request.Request(url, headers=AGENTE)
        try:
            comienzo = time.monotonic()
            with urllib.request.urlopen(peticion, timeout=TIEMPO_ESPERA_S) as respuesta:
                partes = []
                while True:
                    parte = respuesta.read1(65536)
                    if not parte:
                        break
                    partes.append(parte)
                    if time.monotonic() - comienzo > DESCARGA_MAXIMA_S:
                        raise TimeoutError(f"descarga de más de {DESCARGA_MAXIMA_S} s")
                cuerpo = b"".join(partes)
                if respuesta.headers.get("Content-Encoding") == "gzip":
                    cuerpo = gzip.decompress(cuerpo)
            return OK, cuerpo.decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            if error.code in (404, 410):
                return NO_DISPONIBLE, None   # el anuncio se bajó: es dato, no error
            if error.code in (403, 429):
                activar_enfriamiento()
            log.debug("HTTP %s en %s (intento %d)", error.code, url, intento + 1)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            log.debug("%s en %s (intento %d)", error, url, intento + 1)
    return ERROR, None


# --------------------------------------------------------------------------------------
# Parser del JSON embebido
# --------------------------------------------------------------------------------------

def leer_cadena_js(texto, inicio):
    """Devuelve el contenido del string JS que empieza en texto[inicio] (la comilla de
    apertura), respetando escapes. Los chunks de Next.js son strings JSON válidos."""
    i = inicio + 1
    while i < len(texto):
        c = texto[i]
        if c == "\\":
            i += 2
            continue
        if c == '"':
            return json.loads(texto[inicio:i + 1])
        i += 1
    return None


def objeto_balanceado(texto, inicio):
    """Substring del objeto JSON que abre en texto[inicio] == '{'. Un JSON de 7 KB
    incrustado en 50 KB de HTML no justifica un parser de verdad."""
    profundidad, en_cadena, escapado = 0, False, False
    for i in range(inicio, len(texto)):
        c = texto[i]
        if en_cadena:
            if escapado:
                escapado = False
            elif c == "\\":
                escapado = True
            elif c == '"':
                en_cadena = False
            continue
        if c == '"':
            en_cadena = True
        elif c == "{":
            profundidad += 1
        elif c == "}":
            profundidad -= 1
            if profundidad == 0:
                return texto[inicio:i + 1]
    return None


def extraer_objeto(html):
    """Encuentra el objeto `data` del inmueble dentro de los chunks de la página.

    La página lo serializa dos veces: una completa y otra donde los subobjetos son
    referencias ("$9:props:...") a la primera. Se toma la primera que tenga `city` como
    objeto, que es la completa."""
    posicion = html.find(INICIO_CHUNK)
    while posicion != -1:
        chunk = leer_cadena_js(html, posicion + len(INICIO_CHUNK) - 1)
        if chunk and MARCA_OBJETO in chunk:
            for coincidencia in re.finditer(re.escape(MARCA_OBJETO), chunk):
                crudo = objeto_balanceado(chunk, coincidencia.start() + len('"data":'))
                if crudo is None:
                    continue
                try:
                    data = json.loads(crudo)
                except json.JSONDecodeError:
                    continue
                if isinstance(data.get("city"), (dict, type(None))):
                    return data
        posicion = html.find(INICIO_CHUNK, posicion + 1)
    return None


def limpiar_texto(texto):
    if not isinstance(texto, str):
        return None
    texto = unicodedata.normalize("NFC", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto or None


def a_numero(valor, entero=False, cero_valido=False):
    """'1' -> 1, None -> None. El sitio usa 0 como 'no aplica' en precios, áreas y
    estrato, así que por defecto 0 también es None; en parqueaderos 0 sí es un dato."""
    if valor in (None, ""):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    if numero < 0 or (numero == 0 and not cero_valido):
        return None
    return int(round(numero)) if entero else numero


def a_coordenada(valor):
    """Coordenadas: cualquier número vale, incluido el negativo. 0 es 'sin dato'."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return None if numero == 0 else numero


def nombre_de(valor):
    """Los campos de ubicación vienen como {'id':..,'nombre':..} o como texto."""
    if isinstance(valor, dict):
        return limpiar_texto(valor.get("nombre"))
    return limpiar_texto(valor)


def aplanar(data):
    """Del objeto de 83 campos a la fila que se guarda. Acá se decide qué NO entra:
    teléfonos, WhatsApp, dirección y nombre del anunciante quedan afuera."""
    comodidades, piso = [], None
    for seccion in data.get("featured") or []:
        for item in seccion.get("items") or []:
            item = limpiar_texto(item)
            if not item:
                continue
            coincidencia = PATRON_PISO.match(item)
            if coincidencia:
                piso = int(coincidencia.group(1))
            else:
                comodidades.append(item)
    coordenadas = data.get("coordinates") or {}
    aproximada = data.get("ubicacionaproximada")
    return {
        "id_inmueble": data.get("propertyId"),
        "estrato": a_numero(data.get("stratum"), entero=True),
        "antiguedad": limpiar_texto(data.get("builtTime")),
        "estado_inmueble": limpiar_texto(data.get("propertyState")),
        "es_proyecto": bool(data.get("isProject")),
        "precio_venta_detalle": a_numero(data.get("salePrice"), entero=True),
        "precio_arriendo_detalle": a_numero(data.get("rentPrice"), entero=True),
        "precio_arriendo_total": a_numero(data.get("rentTotalPrice"), entero=True),
        "administracion": a_numero((data.get("detail") or {}).get("adminPrice"), entero=True),
        "area_construida": a_numero(data.get("areac")),
        "area_privada": a_numero(data.get("areaPrivada")),
        "habitaciones_detalle": a_numero(data.get("rooms"), entero=True),
        "banos_detalle": a_numero(data.get("bathrooms"), entero=True),
        "parqueaderos_detalle": a_numero(data.get("garages"), entero=True, cero_valido=True),
        "lat": a_coordenada(coordenadas.get("lat")) if isinstance(coordenadas, dict) else None,
        "lon": a_coordenada(coordenadas.get("lon")) if isinstance(coordenadas, dict) else None,
        # 'S' = aproximada, 'N' = exacta, ausente = el sitio no lo dice.
        "ubicacion_aproximada": (None if aproximada in (None, "") else aproximada == "S"),
        "barrio": limpiar_texto(data.get("neighborhood")),
        "barrio_comun": limpiar_texto(data.get("commonNeighborhood")),
        "zona": nombre_de(data.get("zone")),
        "sector_detalle": nombre_de(data.get("sector")),
        "piso": piso,
        "comodidades": " | ".join(dict.fromkeys(comodidades)) or None,
        "n_fotos": len(data.get("images") or []),
        "tiene_video": bool(data.get("video")),
        "descripcion": limpiar_texto(data.get("comment")),
        "inmobiliaria_id": limpiar_texto(data.get("companyId")),
        "destacado": bool(data.get("highlight")),
    }


# --------------------------------------------------------------------------------------
# Orquestación de la descarga
# --------------------------------------------------------------------------------------

def procesar(id_inmueble, url, pausa):
    """Un anuncio: descarga + parseo. Devuelve el registro que va al JSONL.

    Nunca propaga una excepción: un anuncio raro (URL ilegible, HTML inesperado) se
    registra como error y la corrida sigue. La primera versión dejaba escapar la
    excepción, el hilo principal moría y los workers seguían bajando páginas a la nada.
    """
    registro = {"id_inmueble": id_inmueble, "estado": ERROR,
                "fecha_detalle": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        return _procesar(registro, url, pausa)
    except Exception as error:   # noqa: BLE001 - acá sí se quiere atrapar todo
        log.warning("%s: %s: %s", id_inmueble, type(error).__name__, error)
        return registro


def _procesar(registro, url, pausa):
    id_inmueble = registro["id_inmueble"]
    if pausa:
        time.sleep(pausa)
    estado, html = descargar(url)
    registro["estado"] = estado
    if estado != OK:
        return registro
    data = extraer_objeto(html)
    if data is None:
        registro["estado"] = SIN_DATOS   # respondió 200 pero sin el objeto: página distinta
        return registro
    fila = aplanar(data)
    if fila["id_inmueble"] != id_inmueble:
        # El sitio redirigió a otro anuncio. Se guarda bajo el id pedido, marcado.
        fila["id_inmueble"] = id_inmueble
        registro["estado"] = SIN_DATOS
        return registro
    registro.update(fila)
    return registro


def volcar_stacks():
    """Qué está haciendo cada hilo, al log. Es lo que se quiere leer cuando la corrida
    se queda quieta sin errores."""
    nombres = {h.ident: h.name for h in threading.enumerate()}
    for ident, marco in sys._current_frames().items():
        if ident == threading.get_ident():
            continue
        pila = "".join(traceback.format_stack(marco)[-4:])
        log.warning("hilo %s:\n%s", nombres.get(ident, ident), pila.rstrip())


def vigilar(progreso, detener):
    """Hilo watchdog. Mira cada 15 s cuándo fue el último anuncio terminado: a los
    SIN_PROGRESO_AVISO_S vuelca los stacks al log, a los SIN_PROGRESO_ABORTO_S aborta el
    proceso entero. Lo bajado ya está en el JSONL, así que abortar no pierde nada.

    Ojo: no sirve el `timeout` de `as_completed`, que cuenta desde que arranca la
    iteración y no desde el último resultado; con él una corrida sana abortaba a los
    dos minutos."""
    avisado = False
    while not detener.wait(15):
        parado = time.monotonic() - progreso["ultimo"]
        if parado >= SIN_PROGRESO_ABORTO_S:
            log.error("Sin progreso en %d s: se aborta. Volver a correr retoma desde el "
                      "JSONL.", int(parado))
            logging.shutdown()
            os._exit(1)
        if parado >= SIN_PROGRESO_AVISO_S and not avisado:
            log.warning("Sin progreso en %d s. Stacks de los hilos:", int(parado))
            volcar_stacks()
            avisado = True
        elif parado < SIN_PROGRESO_AVISO_S:
            avisado = False


def descargar_todo(pendientes, ruta_partes, hilos, pausa):
    """Recorre los pendientes en paralelo y anexa cada resultado al JSONL apenas llega.
    Un solo escritor (este hilo), así no hace falta candado sobre el archivo."""
    ruta_partes.parent.mkdir(parents=True, exist_ok=True)
    conteo = {OK: 0, NO_DISPONIBLE: 0, SIN_DATOS: 0, ERROR: 0}
    fallos_seguidos, hechos, inicio = 0, 0, time.monotonic()
    ultimo_reporte = inicio
    bloqueado = False

    progreso = {"ultimo": time.monotonic()}
    detener = threading.Event()
    threading.Thread(target=vigilar, args=(progreso, detener), daemon=True,
                     name="watchdog").start()

    # Sin `with`: si hay que cortar, shutdown(wait=False) no espera a los hilos en curso.
    ejecutor = ThreadPoolExecutor(max_workers=hilos)
    with open(ruta_partes, "a", encoding="utf-8") as archivo:
        futuros = {ejecutor.submit(procesar, fila.id_inmueble, fila.url, pausa): fila.id_inmueble
                   for fila in pendientes.itertuples(index=False)}
        for futuro in as_completed(futuros):
            registro = futuro.result()
            progreso["ultimo"] = time.monotonic()
            archivo.write(json.dumps(registro, ensure_ascii=False) + "\n")
            archivo.flush()
            conteo[registro["estado"]] += 1
            hechos += 1

            fallos_seguidos = fallos_seguidos + 1 if registro["estado"] == ERROR else 0
            if fallos_seguidos >= FALLOS_SEGUIDOS_MAXIMO:
                log.error("%d fallos seguidos: el sitio está bloqueando o caído. Se corta; "
                          "volver a correr retoma desde acá.", fallos_seguidos)
                bloqueado = True
                break

            ahora = time.monotonic()
            if ahora - ultimo_reporte >= 30:
                ritmo = hechos / (ahora - inicio)
                restante = (len(pendientes) - hechos) / ritmo if ritmo else float("inf")
                log.info("  %s / %s (%.1f/s, ~%d min restantes) | ok %s | no disponibles %s"
                         " | sin datos %s | errores %s",
                         f"{hechos:,}", f"{len(pendientes):,}", ritmo, restante / 60,
                         f"{conteo[OK]:,}", conteo[NO_DISPONIBLE], conteo[SIN_DATOS],
                         conteo[ERROR])
                ultimo_reporte = ahora
    detener.set()
    ejecutor.shutdown(wait=not bloqueado, cancel_futures=True)
    return conteo, bloqueado


# --------------------------------------------------------------------------------------
# Consolidación y resumen
# --------------------------------------------------------------------------------------

TIPOS = {
    "estrato": "Int8", "es_proyecto": "boolean", "precio_venta_detalle": "Int64",
    "precio_arriendo_detalle": "Int64", "precio_arriendo_total": "Int64",
    "administracion": "Int64", "area_construida": "Float64", "area_privada": "Float64",
    "habitaciones_detalle": "Int8", "banos_detalle": "Int8", "parqueaderos_detalle": "Int8",
    "lat": "Float64", "lon": "Float64", "ubicacion_aproximada": "boolean", "piso": "Int16",
    "n_fotos": "Int16", "tiene_video": "boolean", "destacado": "boolean",
}
COLUMNAS = ["id_inmueble", "estado", "fecha_detalle"] + [
    "estrato", "antiguedad", "estado_inmueble", "es_proyecto", "precio_venta_detalle",
    "precio_arriendo_detalle", "precio_arriendo_total", "administracion", "area_construida",
    "area_privada", "habitaciones_detalle", "banos_detalle", "parqueaderos_detalle", "lat",
    "lon", "ubicacion_aproximada", "barrio", "barrio_comun", "zona", "sector_detalle", "piso",
    "comodidades", "n_fotos", "tiene_video", "descripcion", "inmobiliaria_id", "destacado",
]


RANGOS_ENTEROS = {"Int8": (-128, 127), "Int16": (-32_768, 32_767),
                  "Int64": (-2 ** 63, 2 ** 63 - 1)}


def a_entero_acotado(serie, tipo):
    """`astype("Int8")` revienta con un solo valor fuera de rango, y un anuncio con 200
    habitaciones mal cargadas no puede tirar abajo una corrida de una hora: lo que no
    cabe en el tipo se vuelve nulo."""
    numeros = pd.to_numeric(serie, errors="coerce")
    minimo, maximo = RANGOS_ENTEROS[tipo]
    return numeros.where(numeros.between(minimo, maximo)).astype(tipo)


def consolidar(registros):
    """Del {id: registro} al DataFrame tipado con una fila por anuncio."""
    df = pd.DataFrame(list(registros.values()))
    for columna in COLUMNAS:
        if columna not in df.columns:
            df[columna] = None
    df = df[COLUMNAS]
    for columna, tipo in TIPOS.items():
        if tipo == "boolean":
            df[columna] = df[columna].astype("boolean")
        elif tipo in RANGOS_ENTEROS:
            df[columna] = a_entero_acotado(df[columna], tipo)
        else:
            df[columna] = pd.to_numeric(df[columna], errors="coerce").astype(tipo)
    for columna in df.columns:
        if df[columna].dtype == object:
            df[columna] = df[columna].astype("string")
    return df.sort_values("id_inmueble").reset_index(drop=True)


def frecuencia_comodidades(df, minimo=20):
    """Cuántos anuncios mencionan cada comodidad. De acá salen las banderas `tiene_*`
    del transform: sólo vale la pena una columna para lo que aparece seguido."""
    series = (df["comodidades"].dropna().str.split(r" \| ", regex=True).explode()
                .str.strip().str.lower())
    conteo = series.value_counts()
    return {k: int(v) for k, v in conteo.items() if v >= minimo}


def escribir(df, directorio):
    """Parquet por un temporal y rename atómico: una etapa siguiente nunca lee un
    archivo a medio escribir."""
    ruta = directorio / "detalle.parquet"
    temporal = directorio / "detalle.parquet.tmp"
    df.to_parquet(temporal, index=False)
    temporal.replace(ruta)
    log.info("  %-20s %s filas x %d columnas", ruta.name, f"{len(df):,}", len(df.columns))
    return ruta


def resumir(df, conteo_corrida, urls_total, directorio):
    ok = df[df["estado"] == OK]
    resumen = {
        "anuncios_en_raw": int(urls_total),
        "anuncios_resueltos": int(len(df)),
        "por_estado": df["estado"].value_counts().to_dict(),
        "tasa_exito_%": round(len(ok) / len(df) * 100, 2) if len(df) else 0.0,
        "corrida": conteo_corrida,
        "cobertura_%": {
            columna: round(float(ok[columna].notna().mean() * 100), 2)
            for columna in ("lat", "estrato", "antiguedad", "administracion", "area_privada",
                            "piso", "comodidades", "barrio", "descripcion")
        } if len(ok) else {},
        "ubicacion_aproximada_%": (round(float(ok["ubicacion_aproximada"].fillna(False)
                                                .mean() * 100), 2) if len(ok) else None),
        "estrato_distribucion": {str(int(k)): int(v) for k, v in
                                 ok["estrato"].value_counts().sort_index().items()},
        "antiguedad_distribucion": ok["antiguedad"].value_counts(dropna=False).to_dict(),
        "estado_inmueble_distribucion": ok["estado_inmueble"].value_counts(dropna=False).to_dict(),
        "comodidades_frecuentes": frecuencia_comodidades(ok) if len(ok) else {},
    }
    resumen["antiguedad_distribucion"] = {str(k): int(v) for k, v in
                                          resumen["antiguedad_distribucion"].items()}
    resumen["estado_inmueble_distribucion"] = {str(k): int(v) for k, v in
                                               resumen["estado_inmueble_distribucion"].items()}
    ruta = directorio / "detalle_resumen.json"
    ruta.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("  %s", ruta.name)
    return resumen


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Descarga el detalle de cada anuncio y lo consolida en detalle.parquet")
    parser.add_argument("--entrada-dir", default="data/raw",
                        help="Carpeta con los CSV del extract; ahí mismo se escribe la salida")
    parser.add_argument("--entrada-prefijo", default="anuncios",
                        help="Prefijo de los CSV de entrada")
    parser.add_argument("--hilos", type=int, default=8, help="Descargas en paralelo")
    parser.add_argument("--pausa", type=float, default=0.1,
                        help="Segundos de espera por hilo antes de cada descarga")
    parser.add_argument("--muestra", type=int, default=0,
                        help="Procesar sólo N anuncios al azar (0 = todos). Para probar")
    parser.add_argument("--minimo-exito", type=float, default=0.95,
                        help="Tasa mínima de anuncios con detalle para salir con 0")
    parser.add_argument("--rehacer", action="store_true",
                        help="Ignorar el JSONL previo y descargar todo de nuevo")
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    entrada = Path(args.entrada_dir)
    ruta_partes = entrada / "detalle" / "partes.jsonl"

    log.info("Anuncios a visitar, desde %s:", entrada)
    try:
        urls = cargar_urls(entrada, args.entrada_prefijo)
    except FileNotFoundError as error:
        log.error("%s", error)
        return 1
    log.info("  %s ids únicos", f"{len(urls):,}")

    if args.muestra:
        urls = urls.sample(min(args.muestra, len(urls)), random_state=0).reset_index(drop=True)
        log.info("  --muestra: se procesan %d al azar", len(urls))

    previos = {} if args.rehacer else leer_partes(ruta_partes)
    previos = {k: v for k, v in previos.items() if k in set(urls["id_inmueble"])}
    resueltos = {k for k, v in previos.items() if v["estado"] in ESTADOS_FINALES}
    pendientes = urls[~urls["id_inmueble"].isin(resueltos)].reset_index(drop=True)
    log.info("Ya resueltos en corridas previas: %s | pendientes: %s (de ellos, %s errores a "
             "reintentar)", f"{len(resueltos):,}", f"{len(pendientes):,}",
             f"{len(previos) - len(resueltos):,}")

    conteo, bloqueado = {OK: 0, NO_DISPONIBLE: 0, SIN_DATOS: 0, ERROR: 0}, False
    if len(pendientes):
        log.info("Descargando con %d hilos y %.2f s de pausa:", args.hilos, args.pausa)
        conteo, bloqueado = descargar_todo(pendientes, ruta_partes, args.hilos, args.pausa)
        log.info("Corrida: %s", conteo)

    registros = leer_partes(ruta_partes)
    registros = {k: v for k, v in registros.items() if k in set(urls["id_inmueble"])}
    if not registros:
        log.error("No hay ningún anuncio resuelto")
        return 1

    log.info("Escribiendo en %s:", entrada)
    df = consolidar(registros)
    escribir(df, entrada)
    resumen = resumir(df, conteo, len(urls), entrada)
    log.info("Resumen: %s", json.dumps({k: v for k, v in resumen.items()
                                        if k != "comodidades_frecuentes"}, ensure_ascii=False))

    if bloqueado:
        # Puede haber hilos colgados en una descarga que no termina; un exit normal
        # esperaría por ellos. Lo bajado ya está en disco.
        logging.shutdown()
        os._exit(1)
    if resumen["tasa_exito_%"] < args.minimo_exito * 100:
        log.error("Tasa de éxito %.2f %% por debajo del mínimo %.0f %%",
                  resumen["tasa_exito_%"], args.minimo_exito * 100)
        return 1
    log.info("Detalle completo: %s anuncios con datos de %s (%.2f %%)",
             f"{resumen['por_estado'].get(OK, 0):,}", f"{len(df):,}", resumen["tasa_exito_%"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
