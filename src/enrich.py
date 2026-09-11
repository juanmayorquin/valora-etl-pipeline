"""Enriquecimiento geoespacial de los anuncios - tercera etapa (Enrich) del flujo ETL.

Lee el stage limpio que dejó `transform.py` y le agrega el contexto del barrio, que es
la información que más le falta al modelo de precio:

    anuncios_enriquecido.{csv,parquet}   stage limpio + columnas de ubicación
    enrich_resumen.json                  cobertura y salud de la corrida

Por qué existe esta etapa (medido en `notebooks/eda.ipynb`):

    De las cinco features del stage limpio sólo unas dos aportan información
    independiente - `banos` y `habitaciones` correlacionan 0,84 y 0,82 con el área, o
    sea que son proxies del tamaño. La ubicación es la señal grande que falta, pero
    `sector` es un string de 7.001 valores únicos con 3.948 sectores de UNA fila: da
    R² 0,638 dentro de muestra y 0,320 fuera. Memoriza, no aprende.

    La salida no es limpiar mejor el string, es convertir la ubicación en variables
    NUMÉRICAS Y DENSAS - coordenadas, estrato, jerarquía administrativa - donde miles
    de sectores colapsan en pocas dimensiones que sí generalizan. El prototipo midió
    +0,041 de R² en arriendo y +0,034 en venta sólo por agregar lat/lon.

Fuentes, todas públicas y cacheadas en `data/external/`:

    OpenStreetMap (Overpass)   barrios y jerarquía administrativa
    Esri Colombia (ArcGIS)     estrato socioeconómico predominante por manzana
    Nominatim                  bounding box de cada ciudad

El orden importa: sin el gazetteer no hay coordenada, y sin coordenada no hay estrato.

    1. Bounding box por ciudad   ->  Nominatim, una vez por ciudad
    2. Gazetteer de barrios      ->  Overpass, un request por familia de tags
    3. Match sector -> barrio    ->  exacto sobre el nombre normalizado
    4. Estrato                   ->  ArcGIS, envelope alrededor del centroide
    5. Derivadas sin red         ->  distancia al centro de la ciudad

Qué NO produce esta etapa, y por qué. Los números salen de la ablación en
`notebooks/modelo_baseline.ipynb`, midiendo R² con GroupKFold POR BARRIO - el régimen de
arranque en frío, que es el que se parece a producción:

    puntos de interés   -0,021 en arriendo. `coordenadas + POIs` queda por DEBAJO de las
                        coordenadas solas: no son neutros, meten ruido.
    localidad / zona    -0,010 en arriendo y -0,020 en venta. Sobreajustan.
    criminalidad        -0,001 / +0,003 / +0,001 / +0,000. Indistinguible de cero.

Con el barrio ya conocido, las tres representaciones de la ubicación -coordenadas,
estrato y POIs- son intercambiables (~+0,03 cada una por separado, y sumarlas no da más
que cualquiera sola): alcanza con UNA. Recién en arranque en frío se separan, y ahí
ganan las coordenadas (+0,072 en venta) y el estrato (+0,012 en arriendo, el único
positivo en las dos operaciones). Por eso quedan esos dos, y nada más.

Uso:
    python src/enrich.py
    python src/enrich.py --ciudades 5
    python src/enrich.py --sin-validar      # no falla aunque las validaciones fallen

Códigos de salida:
    0  el enriquecimiento terminó y todas las validaciones pasaron
    1  no había datos de entrada, o al menos una validación falló
"""

import argparse
import gc
import hashlib
import json
import logging
import math
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

# Mirrors de Overpass, medidos el 2026-09-10 con la query de barrios de Bogotá:
#   private.coffee    57,6 s  OK   <- el más rápido, va primero
#   kumi.systems     164,7 s  OK   <- funciona, pero al filo de cualquier timeout corto
#   overpass-api.de       --  SSL: certificate has expired
# `overpass.osm.jp` queda fuera: su certificado no coincide con el hostname.
MIRRORS_OVERPASS = (
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
)
NOMINATIM = "https://nominatim.openstreetmap.org/search"
ESTRATO_ARCGIS = ("https://ags.esri.co/arcgis/rest/services/LivingAtlas"
                  "/Estrato_predominante_por_manzana_2018/MapServer/0")

AGENTE = {"User-Agent": "valora-etl-pipeline/0.1 (proyecto academico; contacto via repo)"}
PAUSA_OVERPASS_S = 5
PAUSA_NOMINATIM_S = 1.2
PAUSA_ARCGIS_S = 0.3
ESPERAS_REINTENTO = (0, 30, 90, 180)

GRADO_EN_METROS = 111_320.0
RADIO_MAX_CIUDAD_KM = 25
# Overpass se cae con 504 por encima de cierto tamaño de consulta. Medido sobre la
# familia `landuse=residential` de Bogotá, que es la más pesada:
#   43,0 x 27,0 km  = 1.161 km²  -> OK (~5 min)
#   40,9 x 23,7 km  =   969 km²  -> OK
#   45,4 x 35,8 km  = 1.625 km²  -> 504 en los dos mirrors
# 1.000 km² deja margen y sólo obliga a partir Bogotá, Cartagena y Pereira.
AREA_MAX_CONSULTA_KM2 = 1000

# Nominatim devuelve cualquier cosa que matchee el texto: para una ciudad hay que
# quedarse con la entidad administrativa, no con el negocio que se llama igual.
CLASES_CIUDAD = ("boundary", "place")
TIPOS_CIUDAD = ("administrative", "city", "town", "municipality", "village")

log = logging.getLogger("enrich")


# --------------------------------------------------------------------------------------
# 1. Infraestructura: normalización, red y caché en disco
# --------------------------------------------------------------------------------------

def normalizar(texto):
    """Sin tildes, minúsculas, sólo alfanumérico. Para comparar nombres de barrio."""
    if texto is None or (isinstance(texto, float) and math.isnan(texto)):
        return ""
    sin_tildes = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    solo_alfanumerico = "".join(c if c.isalnum() else " " for c in sin_tildes.lower())
    return " ".join(solo_alfanumerico.split())


def ruta_cache(directorio, nombre, firma_de):
    """Un archivo por consulta. La firma va en el nombre para que cambiar la consulta
    invalide el caché sin tener que borrarlo a mano."""
    firma = hashlib.sha1(firma_de.encode("utf-8")).hexdigest()[:10]
    return directorio / f"{nombre}_{firma}.json"


def leer_cache(destino):
    if not destino.exists():
        return None
    try:
        return json.loads(destino.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # Un archivo truncado (corrida interrumpida a mitad de escritura) no debe
        # envenenar todas las corridas siguientes.
        log.warning("  caché corrupto, se descarta: %s", destino.name)
        destino.unlink()
        return None


def pedir_json(url, cuerpo=None, espera=240):
    peticion = urllib.request.Request(url, data=cuerpo, headers=AGENTE)
    with urllib.request.urlopen(peticion, timeout=espera) as respuesta:
        return json.load(respuesta)


def consultar_overpass(consulta, directorio, nombre):
    """Ejecuta una query Overpass con caché en disco. Devuelve (datos, desde_cache).

    Overpass asigna *slots* por IP: una query pesada consume el slot y las siguientes
    rebotan por unos segundos. No es un fallo permanente, así que se reintenta con
    backoff en vez de abortar la corrida entera. Y como cada respuesta se cachea apenas
    llega, si la corrida se corta, volver a ejecutarla retoma donde quedó.
    """
    destino = ruta_cache(directorio, nombre, consulta)
    cacheado = leer_cache(destino)
    if cacheado is not None:
        return cacheado, True

    cuerpo = urllib.parse.urlencode({"data": consulta}).encode()
    for vuelta, pausa in enumerate(ESPERAS_REINTENTO):
        if pausa:
            log.warning("  mirrors ocupados; reintento %d en %d s", vuelta, pausa)
            time.sleep(pausa)
        for mirror in MIRRORS_OVERPASS:
            try:
                datos = pedir_json(mirror, cuerpo)
                destino.write_text(json.dumps(datos), encoding="utf-8")
                time.sleep(PAUSA_OVERPASS_S)
                return datos, False
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                detalle = getattr(error, "code", type(error).__name__)
                log.debug("  %s -> %s", urllib.parse.urlparse(mirror).netloc, detalle)
    raise RuntimeError(
        f"Overpass no respondió para '{nombre}' tras {len(ESPERAS_REINTENTO)} vueltas. "
        "Lo ya descargado quedó en data/external/: volver a correr retoma desde ahí.")


def consultar_arcgis(base, parametros, directorio, nombre, pausa=PAUSA_ARCGIS_S):
    """Consulta un layer de ArcGIS REST con caché. Devuelve (features, desde_cache)."""
    consulta = urllib.parse.urlencode(dict(parametros, f="json"))
    destino = ruta_cache(directorio, nombre, base + "?" + consulta)
    cacheado = leer_cache(destino)
    if cacheado is not None:
        return cacheado.get("features", []), True

    datos = pedir_json(f"{base}/query?{consulta}", espera=90)
    if "error" in datos:
        raise RuntimeError(f"ArcGIS respondió con error en '{nombre}': {datos['error']}")
    destino.write_text(json.dumps(datos), encoding="utf-8")
    time.sleep(pausa)
    return datos.get("features", []), False


def bbox_ciudad(ciudad, directorio):
    """Bounding box (sur, oeste, norte, este) de una ciudad, vía Nominatim.

    Se filtra por class/type porque Nominatim, con query libre, devuelve el primer
    resultado que matchee el TEXTO: para 'medellin, laureles' llega a devolver un salón
    de belleza. Para una ciudad hay que exigir que sea una entidad administrativa.
    """
    consulta = urllib.parse.urlencode(
        {"q": f"{ciudad}, Colombia", "format": "json", "limit": 8})
    destino = ruta_cache(directorio, f"bbox_{normalizar(ciudad).replace(' ', '_')}", consulta)
    resultados = leer_cache(destino)
    if resultados is None:
        resultados = pedir_json(f"{NOMINATIM}?{consulta}", espera=45)
        destino.write_text(json.dumps(resultados), encoding="utf-8")
        time.sleep(PAUSA_NOMINATIM_S)

    candidatos = [x for x in resultados
                  if x.get("class") in CLASES_CIUDAD and x.get("type") in TIPOS_CIUDAD
                  and x.get("boundingbox")]
    if not candidatos:
        return None

    def area_grados(item):
        sur, norte, oeste, este = (float(v) for v in item["boundingbox"])
        return (norte - sur) * (este - oeste)

    # 1. Mayor `importance` desambigua homónimos: para "retiro" Nominatim devuelve
    #    primero una vereda de Urrao (0,187) antes que El Retiro de Antioquia (0,460),
    #    que es el municipio con 646 anuncios.
    mejor = max(x.get("importance", 0.0) for x in candidatos)
    empatados = [x for x in candidatos if x.get("importance", 0.0) >= mejor - 1e-9]

    # 2. UNIÓN de los bboxes empatados, no el más chico. Quedarse con el más chico parece
    #    razonable -elige el "Perímetro Urbano" en vez del municipio- pero se midió y es
    #    peor: recortó Chía a 3,1 x 3,4 km (6,4 % de cobertura sobre 1.356 anuncios) y
    #    Pereira a 5,2 x 12,5 km (4,8 %). Los anuncios no respetan el perímetro urbano.
    cajas = [[float(v) for v in x["boundingbox"]] for x in empatados]
    sur = min(caja[0] for caja in cajas)
    norte = max(caja[1] for caja in cajas)
    oeste = min(caja[2] for caja in cajas)
    este = max(caja[3] for caja in cajas)

    # 3. Recorte alrededor del PUNTO del candidato más chico. Dos razones para elegir ese
    #    punto: el del perímetro urbano cae confiablemente en el centro de la ciudad,
    #    mientras que el centroide del municipio entero puede caer en zona rural (el de
    #    Bogotá D.C. se va al sur por Sumapaz y dejaría fuera todo el norte de la ciudad).
    #    Sin este recorte Cartagena pide 148 x 101 km y Overpass devuelve 504.
    referencia = min(empatados, key=area_grados)
    centro_lat, centro_lon = float(referencia["lat"]), float(referencia["lon"])
    lado = RADIO_MAX_CIUDAD_KM / 111.32
    lado_lon = lado / max(math.cos(math.radians(centro_lat)), 0.1)
    return (max(sur, centro_lat - lado), max(oeste, centro_lon - lado_lon),
            min(norte, centro_lat + lado), min(este, centro_lon + lado_lon))


# --------------------------------------------------------------------------------------
# 2. Gazetteer: los barrios de cada ciudad, con su centroide
# --------------------------------------------------------------------------------------

# Una familia por request. El combinado (place + landuse + boundary sobre el bbox de
# Bogotá) devuelve 504: Overpass no lo aguanta en una sola consulta.
FAMILIAS_GAZETTEER = {
    "place": '["place"~"^(suburb|neighbourhood|quarter|borough|city_block'
             '|hamlet|village|town|locality)$"]',
    # En Colombia muchísimas urbanizaciones y conjuntos se mapean como uso de suelo.
    "residencial": '["landuse"="residential"]["name"]',
    # La que más aporta: en Bogotá suma 315 barrios de admin_level 10 que `place` no ve,
    # más 92 localidades (nivel 8) y 139 UPZ (nivel 9).
    "administrativo": '["boundary"="administrative"]["admin_level"~"^(8|9|10)$"]',
}

# El anunciante escribe el barrio como se le canta. Indexar por todos los alias que OSM
# conozca multiplica las chances de pegarle sin recurrir a un match difuso.
CLAVES_NOMBRE = ("name", "alt_name", "official_name", "short_name", "name:es", "loc_name")


def nombres_de(etiquetas):
    """Todos los alias normalizados de un elemento, separando los que vienen con ';'."""
    encontrados = []
    for clave in CLAVES_NOMBRE:
        valor = etiquetas.get(clave)
        if not valor:
            continue
        for parte in str(valor).split(";"):
            normalizado = normalizar(parte)
            if normalizado:
                encontrados.append(normalizado)
    return encontrados


def dividir_bbox(bbox, area_max=AREA_MAX_CONSULTA_KM2):
    """Parte un bounding box en mosaicos que Overpass sí aguante.

    Devuelve una lista de bbox; si el original ya es chico, la lista tiene sólo ese.
    Cada mosaico se cachea por separado, así que además hace la descarga reanudable:
    un 504 en el mosaico 4 no obliga a repetir los tres anteriores.
    """
    sur, oeste, norte, este = bbox
    alto_km = (norte - sur) * 111.32
    ancho_km = (este - oeste) * 111.32 * math.cos(math.radians((sur + norte) / 2))
    if alto_km * ancho_km <= area_max:
        return [bbox]

    divisiones = math.ceil(math.sqrt(alto_km * ancho_km / area_max))
    filas = max(1, math.ceil(alto_km / (alto_km / divisiones)))
    paso_lat = (norte - sur) / divisiones
    paso_lon = (este - oeste) / divisiones
    return [(sur + i * paso_lat, oeste + j * paso_lon,
             sur + (i + 1) * paso_lat, oeste + (j + 1) * paso_lon)
            for i in range(divisiones) for j in range(divisiones)]


def elementos_de_bbox(bbox, filtros, directorio, apodo, salida="out center tags;"):
    """Corre una consulta Overpass sobre un bbox, partiéndolo en mosaicos si hace falta.

    `filtros` es una lista: todos van en la MISMA consulta por mosaico. Agruparlos importa
    -mandar un request por filtro multiplicaría por ocho la carga contra un servicio
    público gratuito, y por ocho el tiempo de corrida.

    Deduplica por (tipo, id): un polígono que cruza el borde entre dos mosaicos vuelve en
    los dos, porque Overpass devuelve todo lo que INTERSECA el bbox, no sólo lo contenido.
    """
    mosaicos = dividir_bbox(bbox)
    elementos, vistos, desde_cache = [], set(), True
    for numero, mosaico in enumerate(mosaicos):
        caja = ",".join(f"{v:.5f}" for v in mosaico)
        partes = []
        for filtro in filtros:
            partes.append(f"node({caja}){filtro};")
            partes.append(f"way({caja}){filtro};")
            partes.append(f"relation({caja}){filtro};")
        consulta = f"[out:json][timeout:270];({''.join(partes)});{salida}"
        sufijo = apodo if len(mosaicos) == 1 else f"{apodo}_m{numero}"
        datos, cacheado = consultar_overpass(consulta, directorio, sufijo)
        desde_cache = desde_cache and cacheado
        for elemento in datos.get("elements", []):
            llave = (elemento.get("type"), elemento.get("id"))
            if llave not in vistos:
                vistos.add(llave)
                elementos.append(elemento)
    return elementos, desde_cache, len(mosaicos)


def descargar_familia(ciudad, bbox, familia, filtro, directorio):
    apodo = f"osm_{familia}_{normalizar(ciudad).replace(' ', '_')}"
    elementos, desde_cache, mosaicos = elementos_de_bbox(
        bbox, [filtro], directorio, apodo)

    filas = []
    for elemento in elementos:
        etiquetas = elemento.get("tags", {})
        centro = elemento.get("center", elemento)
        if centro.get("lat") is None or not etiquetas.get("name"):
            continue
        filas.append({
            "ciudad_clave": ciudad,
            "barrio_osm": etiquetas["name"],
            "alias": nombres_de(etiquetas),
            "lat_barrio": float(centro["lat"]),
            "lon_barrio": float(centro["lon"]),
            "admin_level": etiquetas.get("admin_level"),
        })
    return filas, desde_cache, mosaicos


def construir_gazetteer(ciudades, directorio):
    """Devuelve (indice, cajas).

    `indice` mapea (ciudad, alias) -> (lat, lon, barrio_osm), y gana el primer alias que
    aparece. Se construye INCREMENTALMENTE, descartando cada familia apenas se indexa:
    juntar las 45 respuestas en un DataFrame con una columna de listas de Python era el
    pico de memoria de toda la etapa, y en una máquina justa el sistema mataba el proceso.

    Sin match difuso, y es una decisión MEDIDA, no una omisión: con cutoff 0,92 difflib
    aportaba 0,7 % de cobertura y BAJABA el R² de arriendo (0,877 -> 0,874). Compara
    caracteres, no geografía, así que resuelve 'ciudad salitre nororiental' contra
    'suroriental', y 'rio negro' contra 'rionegro', que es otro municipio. Un centroide
    equivocado no es ruido: es un dato falso, y es peor que un nulo.
    """
    indice, cajas = {}, {}
    for ciudad in ciudades:
        bbox = bbox_ciudad(ciudad, directorio)
        if bbox is None:
            log.warning("  %-22s sin bounding box en Nominatim: se omite", ciudad)
            continue
        cajas[ciudad] = bbox
        sur, oeste, norte, este = bbox
        centro_lat, centro_lon = (sur + norte) / 2, (oeste + este) / 2

        for familia, filtro in FAMILIAS_GAZETTEER.items():
            filas, desde_cache, mosaicos = descargar_familia(
                ciudad, bbox, familia, filtro, directorio)
            for fila in filas:
                # El nivel 10 sí es barrio -en Bogotá son 315 que `place` no devuelve-
                # y por eso la familia `administrativo` se sigue descargando: sube la
                # cobertura. Los niveles 8 y 9 (localidad y UPZ) se descartan: como
                # features medían -0,010 en arriendo y -0,020 en venta en arranque en frío.
                if fila["admin_level"] in ("8", "9"):
                    continue
                # Desempate por cercanía al centro, no por orden de llegada. El bbox de
                # una ciudad grande se mete en los municipios vecinos: el de Bogotá toca
                # Soacha y Chía, que tienen barrios con los mismos nombres. Quedarse con
                # el primero que apareciera hacía que un anuncio bogotano se llevara la
                # coordenada de Soacha, la compuerta de municipio lo descartara, y la
                # cobertura de Bogotá CAYERA de 40,5 % a 35,9 % al ampliar el bbox.
                distancia = distancia_km(centro_lat, centro_lon,
                                         fila["lat_barrio"], fila["lon_barrio"])
                destino = (fila["lat_barrio"], fila["lon_barrio"],
                           fila["barrio_osm"], distancia)
                for alias in fila["alias"]:
                    previo = indice.get((ciudad, alias))
                    if previo is None or distancia < previo[3]:
                        indice[(ciudad, alias)] = destino
            log.info("  %-22s %-14s %5d elementos en %d mosaico(s) %s",
                     ciudad, familia, len(filas), mosaicos,
                     "(cache)" if desde_cache else "(red)")
            del filas

    return indice, cajas


# --------------------------------------------------------------------------------------
# 3. Geometría
# --------------------------------------------------------------------------------------


# --------------------------------------------------------------------------------------
# 4. Match sector -> barrio
# --------------------------------------------------------------------------------------

def resolver_barrios(df, indice):
    """Pega a cada anuncio el barrio de OSM cuyo nombre coincide exactamente."""
    resueltos = [indice.get(llave)
                 for llave in zip(df["ciudad_clave"], df["sector_norm"])]
    df = df.copy()
    df["lat_barrio"] = [r[0] if r else np.nan for r in resueltos]
    df["lon_barrio"] = [r[1] if r else np.nan for r in resueltos]
    df["barrio_osm"] = [r[2] if r else None for r in resueltos]
    df["match_barrio"] = ["exacto" if r else "sin_match" for r in resueltos]
    return df


# --------------------------------------------------------------------------------------
# 5. Estrato socioeconómico - servicio nacional de Esri Colombia
# --------------------------------------------------------------------------------------

def estrato_de_barrio(lat, lon, radio_m, directorio):
    """Estrato predominante alrededor de un centroide. Devuelve (modal, promedio,
    dispersión, n_manzanas, municipios).

    NO se consulta por punto: el centroide de un barrio suele caer en una calle y el
    servicio devuelve cero manzanas (le pasa a El Poblado). Con un envelope alrededor y
    tomando la MODA, el resultado se validó 8/8 contra conocimiento del terreno:
    El Poblado 6, Chico Norte 6, Ciudad Bolívar 1, Laureles 5, Alto Prado 6.
    """
    delta = radio_m / GRADO_EN_METROS
    envelope = {"xmin": lon - delta, "ymin": lat - delta,
                "xmax": lon + delta, "ymax": lat + delta,
                "spatialReference": {"wkid": 4326}}
    parametros = {
        "geometry": json.dumps(envelope),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "ESTRATO_PREDOMINANTE_INT,MPIO",
        "returnGeometry": "false",
    }
    apodo = f"estrato_{lat:.4f}_{lon:.4f}_{radio_m}"
    features, _ = consultar_arcgis(ESTRATO_ARCGIS, parametros, directorio, apodo)

    valores, municipios = [], set()
    for feature in features:
        atributos = feature.get("attributes", {})
        if atributos.get("MPIO"):
            municipios.add(normalizar(atributos["MPIO"]))
        estrato = atributos.get("ESTRATO_PREDOMINANTE_INT")
        if estrato:
            valores.append(int(estrato))
    if not valores:
        return None, np.nan, np.nan, len(features), municipios
    serie = pd.Series(valores)
    return (int(Counter(valores).most_common(1)[0][0]),
            float(serie.mean()), float(serie.std(ddof=0)), len(valores), municipios)


def agregar_estrato(barrios, radio_m, directorio):
    """Estrato por barrio, más la verificación de municipio que sale gratis.

    El campo MPIO de las manzanas dice en qué municipio cayó el envelope. Si no coincide
    con la ciudad del anuncio, el match del gazetteer fue falso: mejor quedarse sin
    coordenada que con una coordenada mentirosa.
    """
    barrios = barrios.copy()
    columnas = {"estrato_modal": [], "estrato_promedio": [], "estrato_dispersion": [],
                "n_manzanas_estrato": [], "match_verificado": []}
    total = len(barrios)
    for posicion, fila in enumerate(barrios.itertuples(index=False), start=1):
        modal, promedio, dispersion, n, municipios = estrato_de_barrio(
            fila.lat_barrio, fila.lon_barrio, radio_m, directorio)
        columnas["estrato_modal"].append(modal)
        columnas["estrato_promedio"].append(promedio)
        columnas["estrato_dispersion"].append(dispersion)
        columnas["n_manzanas_estrato"].append(n)
        # Sin manzanas alrededor no hay con qué contradecir el match: se da por bueno.
        columnas["match_verificado"].append(
            True if not municipios else normalizar(fila.ciudad_clave) in municipios)
        if posicion % 100 == 0 or posicion == total:
            log.info("  estrato %d/%d", posicion, total)
    for nombre, valores in columnas.items():
        barrios[nombre] = valores
    return barrios


# --------------------------------------------------------------------------------------
# 8. Derivadas sin red
# --------------------------------------------------------------------------------------

def agregar_distancia_centro(barrios, cajas):
    """Distancia del barrio al centro de su ciudad. Proxy barato de centralidad, y no
    cuesta un solo request: el centro sale del bounding box que ya se descargó."""
    barrios = barrios.copy()
    barrios["distancia_centro_km"] = np.nan
    for ciudad, (sur, oeste, norte, este) in cajas.items():
        destino = barrios["ciudad_clave"] == ciudad
        if not destino.any():
            continue
        centro_lat, centro_lon = (sur + norte) / 2, (oeste + este) / 2
        barrios.loc[destino, "distancia_centro_km"] = [
            round(distancia_km(centro_lat, centro_lon, lat, lon), 3)
            for lat, lon in zip(barrios.loc[destino, "lat_barrio"],
                                barrios.loc[destino, "lon_barrio"])]
    return barrios


def distancia_km(lat1, lon1, lat2, lon2):
    escala_lon = math.cos(math.radians(lat1)) * 111.32
    return math.hypot((lat2 - lat1) * 111.32, (lon2 - lon1) * escala_lon)


# --------------------------------------------------------------------------------------
# 9. Orquestación del enriquecimiento
# --------------------------------------------------------------------------------------

COLUMNAS_BARRIO = ["barrio_osm", "estrato_modal", "estrato_promedio", "estrato_dispersion",
                   "n_manzanas_estrato", "match_verificado", "distancia_centro_km"]


def ciudades_principales(df, cuantas):
    """Las N ciudades con más anuncios. El resto queda sin enriquecer, y el resumen lo
    dice: es mejor un nulo honesto que una coordenada inventada."""
    return list(df["ciudad_clave"].value_counts().head(cuantas).index)


def enriquecer(df, args, directorio):
    """Aplica el flujo completo. Devuelve (enriquecido, barrios_usados)."""
    df = df.copy()
    df["sector_norm"] = df["sector_clave"].map(normalizar)
    ciudades = ciudades_principales(df, args.ciudades)
    cubiertas = df["ciudad_clave"].isin(ciudades)
    log.info("Ciudades a enriquecer: %d (%s de las filas)",
             len(ciudades), f"{cubiertas.mean() * 100:.1f} %")

    log.info("Descargando gazetteer de OpenStreetMap:")
    indice, cajas = construir_gazetteer(ciudades, directorio)
    log.info("Gazetteer: %s nombres indexados en %d ciudades",
             f"{len(indice):,}", len(cajas))

    df = resolver_barrios(df, indice)

    # Sólo se enriquecen los barrios que algún anuncio realmente usa: enriquecer los
    # 2.000 del gazetteer sería pagar miles de requests para nada.
    usados = (df.loc[df["match_barrio"] == "exacto",
                     ["ciudad_clave", "barrio_osm", "lat_barrio", "lon_barrio"]]
              .drop_duplicates().reset_index(drop=True))

    # El índice ya cumplió: de acá en adelante sólo se usa `usados`.
    del indice
    gc.collect()
    log.info("Barrios efectivamente usados por algún anuncio: %s", f"{len(usados):,}")

    if usados.empty:
        log.warning("Ningún anuncio matcheó con un barrio: no hay nada que enriquecer")
        return df.drop(columns=["sector_norm"]), usados

    usados = agregar_distancia_centro(usados, cajas)

    log.info("Consultando estrato socioeconómico (envelope de %d m):", args.radio_estrato)
    usados = agregar_estrato(usados, args.radio_estrato, directorio)

    # El match verificado contra el MPIO de las manzanas es la última compuerta: si el
    # barrio cayó en otro municipio, se descarta la coordenada entera en vez de propagar
    # una ubicación falsa a todas las columnas derivadas.
    falsos = (~usados["match_verificado"]).sum()
    if falsos:
        log.warning("  %d barrios cayeron en otro municipio: se les quita la coordenada",
                    int(falsos))

    enriquecido = df.merge(usados.drop(columns=["barrio_osm"]),
                           on=["ciudad_clave", "lat_barrio", "lon_barrio"], how="left")
    sospechoso = enriquecido["match_verificado"].eq(False)
    columnas_a_anular = ["lat_barrio", "lon_barrio", "barrio_osm"] + COLUMNAS_BARRIO
    for columna in columnas_a_anular:
        if columna in enriquecido.columns:
            enriquecido.loc[sospechoso, columna] = np.nan
    enriquecido.loc[sospechoso, "match_barrio"] = "descartado_por_municipio"

    return enriquecido.drop(columns=["sector_norm"]), usados


# --------------------------------------------------------------------------------------
# 10. Validación
# --------------------------------------------------------------------------------------

def validar(original, enriquecido):
    """Comprueba que el enriquecimiento no rompió nada de lo que ya estaba bien.

    Una etapa que agrega columnas nunca debe cambiar la cantidad de filas ni tocar el
    contrato del stage limpio. Si eso pasa, hay que enterarse acá.
    """
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

    log.info("Coherencia de las columnas nuevas:")
    con_coordenada = enriquecido["lat_barrio"].notna()
    revisar(con_coordenada.any(), "Al menos un anuncio quedó con coordenada")
    revisar(enriquecido.loc[con_coordenada, "lat_barrio"].between(-4.3, 13.5).all(),
            "Toda latitud cae dentro de Colombia")
    revisar(enriquecido.loc[con_coordenada, "lon_barrio"].between(-82.0, -66.8).all(),
            "Toda longitud cae dentro de Colombia")

    estratos = enriquecido["estrato_modal"].dropna()
    revisar(estratos.empty or estratos.between(1, 6).all(),
            "Todo estrato está en el rango 1-6")
    revisar((~enriquecido["match_verificado"].eq(False) | ~con_coordenada).all(),
            "Ningún anuncio conserva coordenada tras fallar la verificación de municipio")
    revisar(enriquecido.loc[~con_coordenada, "estrato_modal"].isna().all(),
            "Sin coordenada no hay estrato: no se inventó ubicación")
    return fallas


# --------------------------------------------------------------------------------------
# 11. Salida
# --------------------------------------------------------------------------------------

def escribir(df, directorio, nombre):
    """CSV para inspección rápida, Parquet porque preserva los tipos que el CSV degrada
    a texto (Int8 nullable, booleanos, fechas)."""
    directorio.mkdir(parents=True, exist_ok=True)
    df.to_csv(directorio / f"{nombre}.csv", index=False, encoding="utf-8-sig")
    df.to_parquet(directorio / f"{nombre}.parquet", index=False)
    log.info("  %-22s %8s filas x %2d columnas", nombre, f"{len(df):,}", len(df.columns))


def exportar(enriquecido, usados, directorio, ciudades):
    log.info("Escribiendo el stage enriquecido en %s:", directorio)
    escribir(enriquecido, directorio, "anuncios_enriquecido")

    con_coordenada = enriquecido["lat_barrio"].notna()
    en_recorte = enriquecido["ciudad_clave"].isin(ciudades)
    cobertura_por_ciudad = (
        enriquecido[en_recorte].groupby("ciudad_clave")["lat_barrio"]
        .apply(lambda s: round(s.notna().mean() * 100, 1))
        .sort_values(ascending=False).to_dict())

    resumen = {
        "filas": len(enriquecido),
        "ciudades_enriquecidas": len(ciudades),
        "filas_en_ciudades_enriquecidas": int(en_recorte.sum()),
        "barrios_usados": len(usados),
        # El número que decide si esta etapa sirvió. La línea base del prototipo del EDA,
        # con sólo place=suburb|neighbourhood|quarter y 5 ciudades, fue 43,9 %.
        "cobertura_%": round(con_coordenada.mean() * 100, 2),
        "cobertura_en_recorte_%": round(
            enriquecido.loc[en_recorte, "lat_barrio"].notna().mean() * 100, 2)
        if en_recorte.any() else 0.0,
        "cobertura_por_ciudad_%": cobertura_por_ciudad,
        "match": enriquecido["match_barrio"].value_counts().to_dict(),
        "con_estrato_%": round(enriquecido["estrato_modal"].notna().mean() * 100, 2),
        "estrato_distribucion": (enriquecido["estrato_modal"].dropna().astype(int)
                                 .value_counts().sort_index().to_dict()),
        "nulos_por_columna_nueva_%": {
            columna: round(enriquecido[columna].isna().mean() * 100, 2)
            for columna in COLUMNAS_BARRIO
            if columna in enriquecido.columns},
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
        description="Enriquece el stage limpio con el contexto geoespacial del barrio")
    parser.add_argument("--entrada-dir", default="data/processed",
                        help="Carpeta con el stage limpio del transform")
    parser.add_argument("--salida-dir", default="data/processed",
                        help="Carpeta de salida (se crea si no existe)")
    parser.add_argument("--cache-dir", default="data/external",
                        help="Carpeta del caché de respuestas externas")
    parser.add_argument("--ciudades", type=int, default=15,
                        help="Cuántas ciudades enriquecer, por volumen de anuncios")
    parser.add_argument("--radio-estrato", type=int, default=400,
                        help="Radio en metros del envelope de estrato")
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

    directorio_cache = Path(args.cache_dir)
    directorio_cache.mkdir(parents=True, exist_ok=True)
    original = pd.read_parquet(entrada)
    log.info("Stage limpio: %s filas x %d columnas", f"{len(original):,}",
             original.shape[1])

    # El pico de esta etapa ronda los 700 MB. Si la máquina está al límite, el sistema
    # mata el proceso a mitad y el mensaje de error no dice nada útil: mejor avisar acá.
    try:
        import shutil  # noqa: F401  (sólo para saber si psutil está disponible)
        import psutil
        libre_gb = psutil.virtual_memory().available / 2 ** 30
        if libre_gb < 1.5:
            log.warning("Sólo hay %.1f GB de RAM libre. Esta etapa puede necesitar ~0,7 GB; "
                        "si el proceso muere sin mensaje, esa es la causa.", libre_gb)
    except ImportError:
        pass

    try:
        enriquecido, usados = enriquecer(original, args, directorio_cache)
    except RuntimeError as error:
        log.error("%s", error)
        return 1

    log.info("Validación del enriquecimiento:")
    fallas = validar(original, enriquecido)

    ciudades = ciudades_principales(original, args.ciudades)
    resumen = exportar(enriquecido, usados, Path(args.salida_dir), ciudades)

    if fallas:
        log.error("%d validaciones fallaron: %s", len(fallas), "; ".join(fallas))
        if not args.sin_validar:
            return 1
        log.warning("--sin-validar activo: se continúa pese a las fallas")

    # La comparación honesta es por ciudad: el 43,9 % del prototipo del EDA era el
    # promedio de 5 ciudades con Barranquilla al 82,9 % y Bogotá al 32,0 %. Contrastar
    # un recorte de otro tamaño contra ese número global no dice nada.
    log.info("Enriquecimiento completo: %s %% de cobertura global, %s %% en el recorte",
             resumen["cobertura_%"], resumen["cobertura_en_recorte_%"])
    log.info("Cobertura por ciudad (línea base del prototipo entre paréntesis): %s",
             json.dumps(resumen["cobertura_por_ciudad_%"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
