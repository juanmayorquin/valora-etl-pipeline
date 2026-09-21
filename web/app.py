"""Interfaz web de valuación: la API y la página que la consume.

    uvicorn web.app:app --host 0.0.0.0 --port 8000        # desde la raíz del repo
    docker compose up -d web                              # con el artefacto versionado

Carga una vez el artefacto de `src/train.py` y el gold, y expone:

    GET  /                    la página (web/static/index.html)
    GET  /api/ciudades        ciudades del modelo, con cuántos anuncios respaldan a cada una
    GET  /api/sectores        sectores de una ciudad, para autocompletar (?ciudad=&q=)
    POST /api/valuar          el avalúo de venta y arriendo, con rango, más los comparables
                              de la zona y dónde cae el avalúo entre ellos

Los comparables salen del gold: anuncios del mismo tipo a menos de 1,5 km de la coordenada
resuelta (3 km si hay pocos), con área parecida. No es parte del modelo: es la evidencia que
un usuario querría ver al lado del número.
"""

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from scipy.spatial import cKDTree

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
import predict  # noqa: E402

RUTA_MODELO = RAIZ / "models" / "valora_modelo.joblib"
RUTA_GOLD = RAIZ / "data" / "processed" / "anuncios_enriquecido.parquet"
COLUMNAS_GOLD = ["id_inmueble", "url", "ciudad", "ciudad_clave", "sector", "sector_clave",
                 "tipo_inmueble", "operacion", "precio_venta", "precio_arriendo", "area_m2",
                 "precio_m2", "estrato", "habitaciones", "banos", "parqueaderos", "lat", "lon",
                 "antiguedad", "piso"]
RADIO_KM = 1.5
RADIO_AMPLIO_KM = 3.0
TOLERANCIA_AREA = 0.35
MINIMO_COMPARABLES = 8
MAXIMO_COMPARABLES = 8
GRADO_KM = 111.32

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="valora", docs_url="/api/docs", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
estado = {}


# --------------------------------------------------------------------------------------
# Arranque: modelo, gold e índice espacial
# --------------------------------------------------------------------------------------

def cargar():
    modelo = predict.cargar_modelo(RUTA_MODELO)
    gold = pd.read_parquet(RUTA_GOLD, columns=[c for c in COLUMNAS_GOLD])
    con_coordenada = gold[gold["lat"].notna()].reset_index(drop=True)
    puntos = np.column_stack([
        con_coordenada["lat"].astype("float64") * GRADO_KM,
        con_coordenada["lon"].astype("float64") * GRADO_KM * math.cos(math.radians(4.6))])
    nombres_sector = (gold.dropna(subset=["sector_clave"])
                          .groupby(["ciudad_clave", "sector_clave"])["sector"]
                          .agg(lambda s: s.mode().iloc[0]))
    estado.update({"modelo": modelo, "gold": gold, "con_coordenada": con_coordenada,
                   "arbol": cKDTree(puntos), "nombres_sector": nombres_sector})


@app.on_event("startup")
def al_arrancar():
    if not RUTA_MODELO.exists():
        raise RuntimeError(f"No existe {RUTA_MODELO}: correr `python src/train.py`")
    cargar()


# --------------------------------------------------------------------------------------
# Catálogos para el formulario
# --------------------------------------------------------------------------------------

@app.get("/api/ciudades")
def ciudades():
    tabla = estado["modelo"]["ciudades"].sort_values("n", ascending=False)
    return [{"ciudad": fila.ciudad, "clave": fila.ciudad_clave, "anuncios": int(fila.n)}
            for fila in tabla.itertuples(index=False)]


@app.get("/api/sectores")
def sectores(ciudad: str = Query(..., min_length=1), q: str = "", limite: int = 12):
    clave_ciudad = predict.clave(ciudad)
    tabla = estado["modelo"]["sectores"]
    tabla = tabla[tabla["ciudad_clave"] == clave_ciudad]
    consulta = predict.clave(q) or ""
    if consulta:
        tabla = tabla[tabla["sector_clave"].str.contains(consulta, regex=False)]
    tabla = tabla.sort_values("n", ascending=False).head(limite)
    nombres = estado["nombres_sector"]
    salida = []
    for fila in tabla.itertuples(index=False):
        nombre = nombres.get((fila.ciudad_clave, fila.sector_clave), fila.sector_clave.title())
        salida.append({"sector": nombre, "clave": fila.sector_clave, "anuncios": int(fila.n),
                       "estrato": None if math.isnan(fila.estrato) else int(fila.estrato)})
    return salida


# --------------------------------------------------------------------------------------
# Valuación + comparables
# --------------------------------------------------------------------------------------

class Inmueble(BaseModel):
    ciudad: str = Field(..., min_length=1)
    sector: str | None = None
    tipo: str = Field("apartamento", pattern="^(apartaestudio|apartamento|casa)$")
    area_m2: float = Field(..., gt=15, lt=3000)
    habitaciones: int | None = Field(None, ge=0, le=20)
    banos: int | None = Field(None, ge=0, le=20)
    parqueaderos: int | None = Field(None, ge=0, le=20)
    estrato: int | None = Field(None, ge=1, le=6)
    antiguedad: str | None = None
    piso: int | None = Field(None, ge=1, le=60)
    administracion: int | None = Field(None, ge=0)
    comodidades: list[str] = []
    lat: float | None = None
    lon: float | None = None


def buscar_comparables(lat, lon, tipo, area, sector_clave, ciudad_clave):
    """Anuncios parecidos alrededor de la coordenada. Radio corto primero; si no alcanza,
    radio amplio; si tampoco, el sector entero aunque no tenga coordenada."""
    base = estado["con_coordenada"]
    punto = np.array([lat * GRADO_KM, lon * GRADO_KM * math.cos(math.radians(4.6))])
    radio_usado = None
    for radio in (RADIO_KM, RADIO_AMPLIO_KM):
        indices = estado["arbol"].query_ball_point(punto, r=radio)
        cerca = base.iloc[indices]
        cerca = cerca[cerca["tipo_inmueble"].eq(tipo)]
        if len(cerca) >= MINIMO_COMPARABLES:
            radio_usado = radio
            break
    if radio_usado is None:
        gold = estado["gold"]
        cerca = gold[gold["ciudad_clave"].eq(ciudad_clave) & gold["sector_clave"].eq(sector_clave)
                     & gold["tipo_inmueble"].eq(tipo)]
    cerca = cerca.copy()
    cerca["distancia_km"] = np.hypot(
        (cerca["lat"].astype("float64") - lat) * GRADO_KM,
        (cerca["lon"].astype("float64") - lon) * GRADO_KM * math.cos(math.radians(4.6))).round(2)
    return cerca, radio_usado


def percentil(valor, serie):
    serie = serie.dropna()
    return None if serie.empty or valor is None else round(float((serie < valor).mean() * 100))


def histograma(serie, valor, bins=12):
    """Distribución de precio/m² de la zona en escala log, y en qué barra cae el avalúo."""
    serie = serie.dropna().astype("float64")
    if len(serie) < 5:
        return None
    limites = np.logspace(np.log10(serie.quantile(0.02)), np.log10(serie.quantile(0.98)), bins + 1)
    conteos, _ = np.histogram(serie.clip(limites[0], limites[-1]), bins=limites)
    barra = int(np.clip(np.searchsorted(limites, valor, side="right") - 1, 0, bins - 1)) if valor else None
    return {"limites": [round(float(x)) for x in limites], "conteos": conteos.tolist(), "barra_avaluo": barra}


def resumen_zona(cerca, area, resultado):
    salida = {}
    for operacion, columna in (("venta", "precio_venta"), ("arriendo", "precio_arriendo")):
        sub = cerca[cerca[columna].notna()].copy()
        sub["precio"] = sub[columna].astype("float64")
        sub["m2"] = sub["precio"] / sub["area_m2"].astype("float64")
        parecidos = sub[(sub["area_m2"] >= area * (1 - TOLERANCIA_AREA)) & (sub["area_m2"] <= area * (1 + TOLERANCIA_AREA))]
        avaluo_m2 = resultado[operacion]["estimado"] / area
        lista = (parecidos.assign(diferencia_area=(parecidos["area_m2"] - area).abs())
                          .sort_values(["distancia_km", "diferencia_area"]).head(MAXIMO_COMPARABLES))
        salida[operacion] = {
            "n_zona": int(len(sub)),
            "n_parecidos": int(len(parecidos)),
            "mediana_m2": None if sub.empty else round(float(sub["m2"].median())),
            "p25_m2": None if sub.empty else round(float(sub["m2"].quantile(0.25))),
            "p75_m2": None if sub.empty else round(float(sub["m2"].quantile(0.75))),
            "mediana_precio_parecidos": None if parecidos.empty else round(float(parecidos["precio"].median())),
            "percentil_avaluo": percentil(avaluo_m2, sub["m2"]),
            "histograma_m2": histograma(sub["m2"], avaluo_m2),
            "comparables": [{
                "precio": int(fila.precio), "area_m2": float(fila.area_m2),
                "precio_m2": round(float(fila.m2)),
                "estrato": None if pd.isna(fila.estrato) else int(fila.estrato),
                "habitaciones": None if pd.isna(fila.habitaciones) else int(fila.habitaciones),
                "banos": None if pd.isna(fila.banos) else int(fila.banos),
                "parqueaderos": None if pd.isna(fila.parqueaderos) else int(fila.parqueaderos),
                "antiguedad": None if pd.isna(fila.antiguedad) else str(fila.antiguedad),
                "sector": None if pd.isna(fila.sector) else str(fila.sector),
                "distancia_km": None if pd.isna(fila.distancia_km) else float(fila.distancia_km),
                "lat": None if pd.isna(fila.lat) else float(fila.lat),
                "lon": None if pd.isna(fila.lon) else float(fila.lon),
                "url": str(fila.url),
            } for fila in lista.itertuples(index=False)],
        }
    return salida


@app.post("/api/valuar")
def valuar(inmueble: Inmueble):
    entrada = inmueble.model_dump()
    try:
        resultado = predict.predecir(estado["modelo"], entrada)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    lat, lon = resultado["contexto"]["coordenada_usada"]
    cerca, radio = buscar_comparables(lat, lon, inmueble.tipo, inmueble.area_m2,
                                      predict.clave(inmueble.sector), predict.clave(inmueble.ciudad))
    return {
        "avaluo": resultado,
        "zona": {"radio_km": radio, "centro": {"lat": lat, "lon": lon},
                 **resumen_zona(cerca, inmueble.area_m2, resultado)},
    }


# --------------------------------------------------------------------------------------
# La página
# --------------------------------------------------------------------------------------

FRONTEND_DIST = RAIZ / "frontend" / "dist"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"
FRONTEND_ASSETS.mkdir(parents=True, exist_ok=True)
ESTATICOS = Path(__file__).resolve().parent / "static"

app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS), name="assets")
app.mount("/static", StaticFiles(directory=ESTATICOS), name="static")


@app.get("/")
def pagina():
    if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
        return FileResponse(FRONTEND_DIST / "index.html")
    return FileResponse(ESTATICOS / "index.html")
