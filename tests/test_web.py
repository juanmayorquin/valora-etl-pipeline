"""La API de la interfaz web (web/app.py), contra el artefacto y el gold reales."""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from conftest import RAIZ  # noqa: E402

if not (RAIZ / "models" / "valora_modelo.joblib").exists() or not (RAIZ / "data" / "processed" / "anuncios_enriquecido.parquet").exists():
    pytest.skip("hace falta el artefacto y el gold: correr transform, enrich y train", allow_module_level=True)

import sys  # noqa: E402

sys.path.insert(0, str(RAIZ))
from web.app import app  # noqa: E402


@pytest.fixture(scope="module")
def cliente():
    with TestClient(app) as c:
        yield c


def test_ciudades_ordenadas_por_anuncios(cliente):
    ciudades = cliente.get("/api/ciudades").json()
    assert ciudades[0]["clave"] == "bogota d.c."
    assert ciudades[0]["anuncios"] >= ciudades[1]["anuncios"]


def test_sectores_autocompletan_sin_tildes(cliente):
    sectores = cliente.get("/api/sectores", params={"ciudad": "Bogotá D.C.", "q": "chicó no"}).json()
    assert sectores and sectores[0]["clave"] == "chico norte"
    assert sectores[0]["anuncios"] > 100


def test_valuar_devuelve_avaluo_y_zona(cliente):
    r = cliente.post("/api/valuar", json={
        "ciudad": "Bogotá D.C.", "sector": "Chicó Norte", "tipo": "apartamento", "area_m2": 85,
        "habitaciones": 2, "banos": 2, "parqueaderos": 1, "estrato": 6,
        "antiguedad": "Entre 5 y 10 años", "comodidades": ["ascensor", "gimnasio"]})
    assert r.status_code == 200
    d = r.json()
    venta, arriendo = d["avaluo"]["venta"], d["avaluo"]["arriendo"]
    assert venta["rango"][0] <= venta["estimado"] <= venta["rango"][1]
    assert arriendo["estimado"] < venta["estimado"]
    zona = d["zona"]
    assert zona["radio_km"] in (1.5, 3.0)
    assert zona["venta"]["n_zona"] > 50 and 0 <= zona["venta"]["percentil_avaluo"] <= 100
    assert len(zona["venta"]["comparables"]) == 8
    assert all(c["url"].startswith("https://") for c in zona["venta"]["comparables"])
    assert zona["venta"]["histograma_m2"]["conteos"]


def test_valuar_rechaza_lo_invalido(cliente):
    assert cliente.post("/api/valuar", json={"ciudad": "Bogotá D.C.", "area_m2": 5}).status_code == 422
    assert cliente.post("/api/valuar", json={"ciudad": "Atlantis", "area_m2": 80}).status_code == 422
    assert cliente.post("/api/valuar", json={"ciudad": "Bogotá D.C.", "area_m2": 80, "tipo": "oficina"}).status_code == 422


def test_sector_desconocido_usa_el_centro_de_la_ciudad(cliente):
    d = cliente.post("/api/valuar", json={"ciudad": "Medellín", "sector": "Barrio Inventado", "area_m2": 70}).json()
    assert d["avaluo"]["contexto"]["origen_coordenada"] == "centro de la ciudad"


def test_la_pagina_se_sirve(cliente):
    r = cliente.get("/")
    assert r.status_code == 200 and "valora" in r.text
    assert cliente.get("/static/app.js").status_code == 200
