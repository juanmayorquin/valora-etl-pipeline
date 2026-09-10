"""Scraper de Metrocuadrado - primera etapa (Extract) del flujo ETL.

Recorre metrocuadrado.com con Playwright (los anuncios se cargan dinámicamente con
JavaScript) y guarda el resultado en CSV y Excel.

La extracción se hace en **barridos**: una combinación de tipo de inmueble y operación,
cada uno con su propia URL. Con tres tipos y dos operaciones son seis barridos:

    /apartaestudio/arriendo   /apartamento/arriendo   /casa/arriendo
    /apartaestudio/venta      /apartamento/venta      /casa/venta

Barrer por tipo, en vez de pedir los tres juntos, evita que las categorías con menos
oferta (apartaestudio) queden sepultadas por las de más volumen dentro del límite de
paginación del sitio.

La **operación** sí es autoritativa por barrido: se escribe como columna en vez de
deducirse del texto. Eso importa porque el título de un anuncio publicado en las dos
modalidades dice "Casa en Venta y Arriendo", y cualquier regex que espere una sola
operación falla ahí.

El **tipo, en cambio, sale del slug de cada anuncio**, no del barrido. La etiqueta del
barrido resultó no ser confiable por dos vías:

  1. Es por lote, no por anuncio. Un inmueble que aparece en dos barridos se quedaba con
     la etiqueta del primero que corrió, y así una casa de 300 m² terminaba marcada como
     apartaestudio.
  2. El filtro del sitio se cae en las páginas profundas: el barrido de apartaestudios en
     arriendo devolvía oficinas, bodegas y locales comerciales.

El slug (`/inmueble/arriendo-apartaestudio-bogota-.../21601-M6844386`) es por anuncio y no
tiene ninguno de los dos problemas. Lo que no cae en los tres tipos residenciales se
descarta al momento de recolectarlo — antes de pedirle al navegador el texto y el `alt`,
que son las llamadas caras. La etiqueta del barrido se conserva en `tipo_barrido` para
poder medir cuánto discrepa la fuente.

Uso:
    python extract.py
    python extract.py --tipos apartaestudio --operaciones arriendo
    python extract.py --max-paginas 20 --sin-excel
    python extract.py --snapshot          # guarda además una copia con fecha

Variables de entorno:
    HEADLESS=true|false   Corre Chromium sin/con ventana (por defecto true, útil en Docker).

Códigos de salida:
    0  todos los barridos pedidos terminaron bien
    1  al menos un barrido falló o volvió vacío
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

import pandas as pd
from playwright.async_api import async_playwright

BASE_URL = "https://www.metrocuadrado.com"
TIPOS_INMUEBLE = ("apartaestudio", "apartamento", "casa")
OPERACIONES = ("arriendo", "venta")

# Tipo del anuncio según su propio slug. Sin re.IGNORECASE: los slugs son minúscula.
PATRON_TIPO_SLUG = re.compile(r"/inmueble/(?:arriendo|venta)-([a-z]+)-")

DEFAULT_MAX_SCROLLS = 6000
PAUSA_ENTRE_SCROLLS_MS = 500
DEFAULT_MAX_PAGINAS = 199  # 0 para recorrer todas las páginas del paginador
REINTENTOS_POR_BARRIDO = 2
PAUSA_ENTRE_REINTENTOS_S = 10

log = logging.getLogger("extract")


def url_barrido(tipo, operacion):
    return f"{BASE_URL}/{tipo}/{operacion}/?search=form"


def limpiar_texto(texto):
    return " ".join((texto or "").split())


def clave_anuncio(url):
    """Identidad de un anuncio: su ruta, sin querystring.

    El sitio sirve el mismo inmueble con distintos `?src_url=` (cambia el orden de los
    tipos en la ruta de origen a mitad de la paginación). Deduplicar por la URL completa
    deja pasar duplicados; hay que hacerlo por la ruta.
    """
    return urlsplit(url)._replace(query="", fragment="").geturl()


def id_inmueble(url):
    """Último segmento de la ruta. Dos formatos conviven: '17548-M6886169' y 'MC6943773'."""
    return clave_anuncio(url).rstrip("/").rsplit("/", 1)[-1]


def tipo_desde_url(url):
    """Tipo real del anuncio, leído de su propio slug. None si el slug no calza.

    El slug tiene forma fija:
        /inmueble/arriendo-apartaestudio-bogota-chapinero-1-habitaciones/21601-M6844386
                  ^^^^^^^^ ^^^^^^^^^^^^^
                  operación   tipo
    """
    coincidencia = PATRON_TIPO_SLUG.search(url or "")
    return coincidencia.group(1).lower() if coincidencia else None


def extraer_campos(texto, alt=""):
    """Extrae precio, área, habitaciones, baños, parqueaderos, sector y ciudad.

    El texto visible del enlace (inner_text) NO incluye habitaciones/baños/área/garajes:
    esos datos los renderiza un web component (<pt-main-specs>) sin texto accesible. Sí
    aparecen en el atributo `alt` de la foto, con formato consistente, p. ej.:
    "Foto de Casa en Venta en PANCE, Cali con 4 habitaciones, 5 baños, área 350 m2,
    4 garaje - 3566-M5719054". Por eso se combinan ambas fuentes para los numéricos.

    Sector y ciudad salen del título, que sigue el patrón
    "<Tipo> en <Operación>, <Sector>, <Ciudad>".
    """
    texto = limpiar_texto(texto)
    alt = limpiar_texto(alt)
    combinado = f"{texto} {alt}".strip()

    def buscar(*patrones):
        for patron in patrones:
            coincidencia = re.search(patron, combinado, flags=re.IGNORECASE)
            if coincidencia:
                return coincidencia.group(1)
        return None

    # Sector y ciudad se buscan sólo en `texto`, nunca en `combinado`: el `alt` no trae
    # coma después de la ciudad, así que el grupo de ciudad seguiría consumiendo hasta el
    # final del `alt` y se tragaría su "Foto de ..." completo.
    # La conjunción opcional cubre los anuncios duales ("en Venta y Arriendo, ...").
    ubicacion = re.search(
        r"en\s+(?:Arriendo|Venta)(?:\s+y\s+(?:Arriendo|Venta))?,\s*([^,]+),\s*([^,\n]+)",
        texto,
        flags=re.IGNORECASE,
    )

    return {
        "precio_texto": buscar(r"(\$\s*[\d\.,]+)"),
        "area_m2": buscar(r"área\s*([\d\.,]+)\s*m[²2]", r"([\d\.,]+)\s*m[²2]"),
        "habitaciones": buscar(r"(\d+)\s*habitac"),
        "banos": buscar(r"(\d+)\s*ba[ñn]o"),
        "parqueaderos": buscar(r"(\d+)\s*garaje", r"(\d+)\s*par(?:queadero)?"),
        "sector": ubicacion.group(1).strip() if ubicacion else None,
        "ciudad": ubicacion.group(2).strip() if ubicacion else None,
    }


async def recolectar_anuncios_de_pagina(page, anuncios, descartados, max_scrolls):
    """Recorre la página actual con scroll hasta que dejan de aparecer anuncios nuevos.

    Los anuncios ya vistos se saltan sin volver a pedirle al navegador su inner_text ni
    el alt de la imagen: esas dos llamadas son las que más tardan (van y vuelven al
    proceso del navegador), y repetirlas en cada scroll para anuncios que no cambian es
    lo que hacía lenta cada página.

    Lo que el slug delata como no residencial se descarta acá mismo, por la misma razón:
    el href ya lo teníamos, y así nos ahorramos las dos llamadas caras por cada oficina o
    bodega que el filtro del sitio dejó pasar. `descartados` los acumula para el reporte.
    """
    sin_cambios = 0
    cantidad_anterior = len(anuncios) + len(descartados)

    for intento in range(max_scrolls):
        enlaces = page.locator('a[href*="/inmueble/"]')
        cantidad = await enlaces.count()

        for i in range(cantidad):
            try:
                enlace = enlaces.nth(i)
                href = await enlace.get_attribute("href", timeout=5_000)
                if not href:
                    continue

                url_anuncio = urljoin(BASE_URL, href)
                clave = clave_anuncio(url_anuncio)
                if clave in anuncios or clave in descartados:
                    continue

                tipo = tipo_desde_url(clave)
                if tipo not in TIPOS_INMUEBLE:
                    # Un slug ilegible (tipo None) también se va: si no se puede afirmar
                    # que el anuncio es vivienda, no entra al dataset.
                    descartados[clave] = tipo
                    continue

                texto = await enlace.inner_text(timeout=5_000)
                try:
                    alt = await enlace.locator("img").first.get_attribute("alt", timeout=1_000)
                except Exception:
                    alt = ""

                texto = limpiar_texto(texto)
                anuncios[clave] = {
                    "url": clave,
                    "id_inmueble": id_inmueble(clave),
                    "tipo_inmueble": tipo,
                    "texto": texto,
                    **extraer_campos(texto, alt),
                }
            except Exception as exc:
                log.debug("Se omitió el anuncio %s por %s", i, exc.__class__.__name__)
                continue

        log.info("  scroll %s: %s anuncios acumulados (%s descartados)",
                 intento + 1, len(anuncios), len(descartados))
        await page.evaluate("window.scrollBy(0, 900)")
        await page.wait_for_timeout(PAUSA_ENTRE_SCROLLS_MS)

        # El corte mira el total visto, no sólo lo aceptado: si no, una tanda de anuncios
        # no residenciales seguidos parecería "página sin novedades" y cortaría de más.
        vistos = len(anuncios) + len(descartados)
        sin_cambios = sin_cambios + 1 if vistos == cantidad_anterior else 0
        cantidad_anterior = vistos
        if sin_cambios >= 2:
            break


async def ir_a_siguiente_pagina(page):
    """Hace clic en el botón "siguiente" del paginador. Devuelve False si no hay más páginas."""
    boton_siguiente = page.locator(".rc-pagination-next")

    if await boton_siguiente.count() == 0:
        return False
    if await boton_siguiente.get_attribute("aria-disabled") == "true":
        return False

    try:
        await boton_siguiente.locator("button").click(timeout=5_000)
    except Exception:
        return False

    await page.wait_for_timeout(2_000)
    await page.evaluate("window.scrollTo(0, 0)")
    return True


async def scrapear_anuncios(url, max_scrolls=30, max_paginas=None, headless=True):
    """Devuelve (DataFrame de anuncios residenciales, conteo de descartes por tipo)."""
    anuncios = {}
    descartados = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page(viewport={"width": 1440, "height": 900}, locale="es-CO")

        try:
            log.info("Abriendo %s", url)
            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(5_000)

            try:
                await page.get_by_role("button", name="Aceptar").click(timeout=3_000)
            except Exception:
                pass

            numero_pagina = 1
            while True:
                if max_paginas is not None and numero_pagina > max_paginas:
                    log.info("Se alcanzó el límite de %s páginas", max_paginas)
                    break

                log.info("--- página %s ---", numero_pagina)
                try:
                    await recolectar_anuncios_de_pagina(page, anuncios, descartados, max_scrolls)
                    hay_siguiente = await ir_a_siguiente_pagina(page)
                except Exception as exc:
                    log.warning("Paginación detenida en la página %s (%s: %s)",
                                numero_pagina, exc.__class__.__name__, exc)
                    break

                if not hay_siguiente:
                    log.info("No hay más páginas")
                    break
                numero_pagina += 1
        finally:
            await browser.close()

    conteo = Counter(tipo or "slug_ilegible" for tipo in descartados.values())
    return pd.DataFrame(anuncios.values()), dict(conteo)


def ejecutar_barrido(tipo, operacion, max_scrolls, max_paginas, headless):
    """Corre un barrido con reintentos.

    Devuelve (DataFrame, descartes por tipo). El DataFrame va vacío si falló todo.
    """
    url = url_barrido(tipo, operacion)

    for intento in range(1, REINTENTOS_POR_BARRIDO + 2):
        try:
            df, descartes = asyncio.run(
                scrapear_anuncios(url, max_scrolls, max_paginas, headless=headless))
            if len(df) > 0:
                return df, descartes
            log.warning("Barrido %s/%s devolvió 0 anuncios (intento %s)", tipo, operacion, intento)
        except Exception as exc:
            log.error("Barrido %s/%s falló (intento %s): %s: %s",
                      tipo, operacion, intento, exc.__class__.__name__, exc)

        if intento <= REINTENTOS_POR_BARRIDO:
            log.info("Reintentando en %ss...", PAUSA_ENTRE_REINTENTOS_S)
            time.sleep(PAUSA_ENTRE_REINTENTOS_S)

    return pd.DataFrame(), {}


def guardar(df, ruta, con_excel=True):
    """Escribe primero a un temporal y después renombra.

    Un `to_csv` interrumpido a mitad deja un archivo truncado que parece válido; el
    rename es atómico y evita que la etapa siguiente lea datos incompletos.
    """
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)

    tmp = f"{ruta}.tmp"
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    os.replace(tmp, ruta)
    log.info("Escrito %s (%s filas)", ruta, len(df))

    if con_excel:
        ruta_xlsx = os.path.splitext(ruta)[0] + ".xlsx"
        tmp_xlsx = f"{ruta_xlsx}.tmp.xlsx"
        df.to_excel(tmp_xlsx, index=False)
        os.replace(tmp_xlsx, ruta_xlsx)
        log.info("Escrito %s", ruta_xlsx)


def parse_args():
    parser = argparse.ArgumentParser(description="Scraper de anuncios de Metrocuadrado")
    parser.add_argument("--tipos", nargs="+", choices=TIPOS_INMUEBLE, default=list(TIPOS_INMUEBLE),
                        help="Tipos de inmueble a barrer")
    parser.add_argument("--operaciones", nargs="+", choices=OPERACIONES, default=list(OPERACIONES),
                        help="Operaciones a barrer")
    parser.add_argument("--max-scrolls", type=int, default=DEFAULT_MAX_SCROLLS,
                        help="Máximo de scrolls por página")
    parser.add_argument("--max-paginas", type=int, default=DEFAULT_MAX_PAGINAS,
                        help="Máximo de páginas del paginador (0 = sin límite)")
    parser.add_argument("--salida-prefijo", default="anuncios", help="Prefijo de los archivos de salida")
    parser.add_argument("--salida-dir", default="data/raw", help="Carpeta de salida (se crea si no existe)")
    parser.add_argument("--sin-excel", action="store_true", help="No generar los .xlsx (más rápido)")
    parser.add_argument("--snapshot", action="store_true",
                        help="Guardar además una copia con fecha en <salida-dir>/historico/")
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    max_paginas = None if args.max_paginas == 0 else args.max_paginas
    headless = os.environ.get("HEADLESS", "true").strip().lower() not in ("0", "false", "no")
    inicio_run = datetime.now(timezone.utc)
    sello = inicio_run.strftime("%Y%m%d_%H%M")

    resultados = {operacion: [] for operacion in args.operaciones}
    barridos = []
    fallidos = []

    for operacion in args.operaciones:
        for tipo in args.tipos:
            log.info("=== barrido %s / %s ===", tipo, operacion)
            comienzo = time.monotonic()
            df, descartes = ejecutar_barrido(tipo, operacion, args.max_scrolls,
                                             max_paginas, headless)
            duracion = round(time.monotonic() - comienzo, 1)

            if df.empty:
                fallidos.append(f"{tipo}/{operacion}")
                log.error("Barrido %s/%s SIN DATOS tras los reintentos", tipo, operacion)
            else:
                # La operación sí la sabe el barrido. El tipo ya vino del slug de cada
                # anuncio; acá sólo se guarda la etiqueta del barrido para auditarla.
                df["tipo_barrido"] = tipo
                df["operacion"] = operacion
                df["fecha_extraccion"] = inicio_run.isoformat(timespec="seconds")
                resultados[operacion].append(df)

                fuera_de_tipo = int((df["tipo_inmueble"] != tipo).sum())
                log.info("Barrido %s/%s: %s anuncios en %ss"
                         " | %s de otro tipo | %s no residenciales descartados",
                         tipo, operacion, len(df), duracion,
                         fuera_de_tipo, sum(descartes.values()))
                if descartes:
                    log.info("  descartes por slug: %s", descartes)

            barridos.append({"tipo": tipo, "operacion": operacion,
                             "anuncios": int(len(df)), "segundos": duracion,
                             "descartados_no_residencial": sum(descartes.values()),
                             "descartes_por_tipo": descartes})

    manifiesto = {
        "inicio_utc": inicio_run.isoformat(timespec="seconds"),
        "fin_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "barridos": barridos,
        "fallidos": fallidos,
        "archivos": [],
    }

    for operacion, partes in resultados.items():
        if not partes:
            continue

        df = pd.concat(partes, ignore_index=True)
        antes = len(df)
        # Un inmueble puede aparecer en varios barridos de tipo distinto. Antes esto era
        # un problema: con `keep="first"` sobrevivía la copia del barrido que corrió
        # primero y le imponía su etiqueta. Ahora el tipo viene del slug, así que las
        # copias son idénticas en lo que importa. Igual se ordena para que gane la del
        # barrido que coincide con el tipo real: hace el resultado determinista y deja
        # `tipo_barrido` diciendo algo útil.
        df = (df.assign(_coincide=(df["tipo_barrido"] != df["tipo_inmueble"]))
                .sort_values(["_coincide", "tipo_barrido"], kind="stable")
                .drop(columns="_coincide")
                .drop_duplicates(subset="id_inmueble", keep="first")
                .sort_index()
                .reset_index(drop=True))
        if antes != len(df):
            log.info("%s: %s duplicados por id_inmueble descartados", operacion, antes - len(df))

        acuerdo = float(df["tipo_barrido"].eq(df["tipo_inmueble"]).mean() * 100)
        log.info("%s: acuerdo slug vs. barrido %.2f %% | tipos: %s",
                 operacion, acuerdo, df["tipo_inmueble"].value_counts().to_dict())

        ruta = os.path.join(args.salida_dir, f"{args.salida_prefijo}_{operacion}.csv")
        guardar(df, ruta, con_excel=not args.sin_excel)
        manifiesto["archivos"].append({
            "operacion": operacion,
            "ruta": ruta,
            "filas": int(len(df)),
            "filas_por_tipo": df["tipo_inmueble"].value_counts().to_dict(),
            # Salud de la fuente: si esto baja, el filtro del sitio se está degradando
            # y hay que revisar acá, no en el transform.
            "acuerdo_slug_barrido_%": round(acuerdo, 2),
        })

        if args.snapshot:
            ruta_hist = os.path.join(args.salida_dir, "historico",
                                     f"{args.salida_prefijo}_{operacion}_{sello}.csv")
            guardar(df, ruta_hist, con_excel=False)

    ruta_manifiesto = os.path.join(args.salida_dir, "ultima_extraccion.json")
    os.makedirs(args.salida_dir, exist_ok=True)
    with open(ruta_manifiesto, "w", encoding="utf-8") as f:
        json.dump(manifiesto, f, ensure_ascii=False, indent=2)
    log.info("Manifiesto escrito en %s", ruta_manifiesto)

    if fallidos:
        log.error("Barridos sin datos: %s", ", ".join(fallidos))
        return 1
    log.info("Extracción completa: %s barridos, %s archivos, %s no residenciales descartados",
             len(barridos), len(manifiesto["archivos"]),
             sum(b["descartados_no_residencial"] for b in barridos))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    sys.exit(main())
