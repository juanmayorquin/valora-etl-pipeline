"""Scraper de Metrocuadrado - primera etapa (Extract) del flujo ETL.

Extrae los anuncios de arriendo Y de venta publicados en metrocuadrado.com
(BASE_URL/arriendo y BASE_URL/venta) usando Playwright (los anuncios se cargan
dinámicamente con JavaScript) y guarda el resultado de cada uno en CSV y Excel.

Uso:
    python extract.py
    python extract.py --tipos arriendo
    python extract.py --tipos arriendo venta --max-paginas 50 --salida-prefijo anuncios

Variables de entorno:
    HEADLESS=true|false   Corre Chromium sin/con ventana (por defecto true, útil en Docker).
"""

import argparse
import asyncio
import os
import re
import sys
from urllib.parse import urljoin

import pandas as pd
from playwright.async_api import async_playwright

BASE_URL = "https://www.metrocuadrado.com"
URLS_POR_TIPO = {
    "arriendo": f"{BASE_URL}/arriendo/?search=form",
    "venta": f"{BASE_URL}/venta/?search=form",
}
DEFAULT_MAX_SCROLLS = 6000
PAUSA_ENTRE_SCROLLS_MS = 500
DEFAULT_MAX_PAGINAS = 199  # None para recorrer todas las páginas del paginador


def limpiar_texto(texto):
    return " ".join((texto or "").split())


def extraer_campos(texto, alt=""):
    """Extrae precio, área, habitaciones, baños, parqueaderos, tipo, sector y ciudad.

    El texto visible del enlace (inner_text) NO incluye habitaciones/baños/área/
    garajes: esos datos los renderiza un web component (<pt-main-specs>) sin
    texto accesible. Sí aparecen, en cambio, en el atributo `alt` de la foto de
    la tarjeta, con un formato consistente, p. ej.:
    "Foto de Casa en Venta en PANCE, Cali con 4 habitaciones, 5 baños,
    área 350 m2, 4 garaje - 3566-M5719054". Por eso se combinan ambas fuentes.

    El sector y la ciudad se extraen del título del anuncio, que sigue el
    patrón "<Tipo> en Venta, <Sector>, <Ciudad>" (p. ej. "Casa en Venta,
    PANCE AV LA MARIA, Cali").
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

    ubicacion = re.search(r"en (?:Arriendo|Venta),\s*([^,]+),\s*([^,\n]+)", combinado, flags=re.IGNORECASE)
    sector = ubicacion.group(1).strip() if ubicacion else None
    ciudad = ubicacion.group(2).strip() if ubicacion else None

    return {
        "precio_texto": buscar(r"(\$\s*[\d\.,]+)"),
        "area_m2": buscar(r"área\s*([\d\.,]+)\s*m[²2]", r"([\d\.,]+)\s*m[²2]"),
        "habitaciones": buscar(r"(\d+)\s*habitac"),
        "banos": buscar(r"(\d+)\s*ba[ñn]o"),
        "parqueaderos": buscar(r"(\d+)\s*garaje", r"(\d+)\s*par(?:queadero)?"),
        "tipo": buscar(r"((?:Apartamento|Casa|Apartaestudio|Finca)\s+en\s+(?:Arriendo|Venta))"),
        "sector": sector,
        "ciudad": ciudad,
    }


async def recolectar_anuncios_de_pagina(page, anuncios, max_scrolls):
    """Recorre la página actual con scroll hasta que dejan de aparecer anuncios nuevos.

    Los anuncios ya vistos (por href) se saltan sin volver a pedirle al navegador
    su inner_text ni el alt de la imagen: esas dos llamadas son las que más
    tardan (van y vuelven al proceso del navegador), y repetirlas en cada
    scroll para anuncios que no cambian es lo que hacía lenta cada página.
    """
    sin_cambios = 0
    cantidad_anterior = len(anuncios)
    hrefs_vistos = set(anuncios.keys())

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
                if url_anuncio in hrefs_vistos:
                    continue

                texto = await enlace.inner_text(timeout=5_000)
                try:
                    alt = await enlace.locator("img").first.get_attribute("alt", timeout=1_000)
                except Exception:
                    alt = ""

                texto = limpiar_texto(texto)
                anuncios[url_anuncio] = {
                    "url": url_anuncio,
                    "texto": texto,
                    **extraer_campos(texto, alt),
                }
                hrefs_vistos.add(url_anuncio)
            except Exception as exc:
                print(f"  Aviso: se omitió el anuncio {i} por un error ({exc.__class__.__name__})")
                continue

        print(f"  Intento {intento + 1}: {len(anuncios)} anuncios en total")
        await page.evaluate("window.scrollBy(0, 1200)")
        await page.wait_for_timeout(PAUSA_ENTRE_SCROLLS_MS)

        if len(anuncios) == cantidad_anterior:
            sin_cambios += 1
        else:
            sin_cambios = 0

        cantidad_anterior = len(anuncios)
        if sin_cambios >= 2:
            break


async def ir_a_siguiente_pagina(page):
    """Hace clic en el botón "siguiente" del paginador. Devuelve False si no hay más páginas."""
    boton_siguiente = page.locator(".rc-pagination-next")

    if await boton_siguiente.count() == 0:
        return False

    deshabilitado = await boton_siguiente.get_attribute("aria-disabled")
    if deshabilitado == "true":
        return False

    try:
        await boton_siguiente.locator("button").click(timeout=5_000)
    except Exception:
        return False

    await page.wait_for_timeout(2_000)
    await page.evaluate("window.scrollTo(0, 0)")
    return True


async def scrapear_anuncios(url, max_scrolls=30, max_paginas=None, headless=True):
    anuncios = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page(
            viewport={"width": 1440, "height": 900},
            locale="es-CO",
        )

        print("Abriendo la página...")
        await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(5_000)

        try:
            await page.get_by_role("button", name="Aceptar").click(timeout=3_000)
        except Exception:
            pass

        numero_pagina = 1
        while True:
            if max_paginas is not None and numero_pagina > max_paginas:
                print(f"Se alcanzó el límite de {max_paginas} páginas.")
                break

            print(f"--- Página {numero_pagina} ---")
            try:
                await recolectar_anuncios_de_pagina(page, anuncios, max_scrolls)
                hay_siguiente = await ir_a_siguiente_pagina(page)
            except Exception as exc:
                print(f"Aviso: se detuvo la paginación por un error en la página {numero_pagina} ({exc.__class__.__name__}: {exc})")
                break

            if not hay_siguiente:
                print("No hay más páginas.")
                break

            numero_pagina += 1

        await browser.close()

    return pd.DataFrame(anuncios.values())


def parse_args():
    parser = argparse.ArgumentParser(description="Scraper de anuncios de Metrocuadrado")
    parser.add_argument(
        "--tipos",
        nargs="+",
        choices=sorted(URLS_POR_TIPO),
        default=sorted(URLS_POR_TIPO),
        help="Tipos de anuncio a scrapear (por defecto arriendo y venta)",
    )
    parser.add_argument("--max-scrolls", type=int, default=DEFAULT_MAX_SCROLLS, help="Máximo de scrolls por página")
    parser.add_argument(
        "--max-paginas",
        type=int,
        default=DEFAULT_MAX_PAGINAS,
        help="Máximo de páginas del paginador a recorrer (usa 0 para no limitar)",
    )
    parser.add_argument(
        "--salida-prefijo",
        default="anuncios",
        help="Prefijo de los archivos de salida (se generan <prefijo>.csv y <prefijo>.xlsx)",
    )
    parser.add_argument(
        "--salida-dir",
        default="data/raw",
        help="Carpeta donde se guardan los archivos de salida (se crea si no existe)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    max_paginas = None if args.max_paginas == 0 else args.max_paginas
    headless = os.environ.get("HEADLESS", "true").strip().lower() not in ("0", "false", "no")

    os.makedirs(args.salida_dir, exist_ok=True)

    for tipo in args.tipos:
        print(f"=== Scrapeando {tipo} ===")
        url = URLS_POR_TIPO[tipo]
        try:
            df = asyncio.run(
                scrapear_anuncios(url, args.max_scrolls, max_paginas, headless=headless)
            )
        except Exception as exc:
            print(f"Error scrapeando {tipo}, se omite este tipo: {exc.__class__.__name__}: {exc}")
            continue
        print(f"Total de anuncios de {tipo}: {len(df)}")

        ruta_csv = os.path.join(args.salida_dir, f"{args.salida_prefijo}_{tipo}.csv")
        ruta_xlsx = os.path.join(args.salida_dir, f"{args.salida_prefijo}_{tipo}.xlsx")

        df.to_csv(ruta_csv, index=False, encoding="utf-8-sig")
        df.to_excel(ruta_xlsx, index=False)
        print(f"Archivos creados: {ruta_csv} y {ruta_xlsx}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    main()
