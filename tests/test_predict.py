"""predict.py sobre un artefacto diminuto entrenado en el test: no depende de la data."""
import numpy as np
import pandas as pd
import pytest

import predict
import train


@pytest.fixture(scope="module")
def artefacto():
    """Un gold sintético de 600 filas en dos ciudades, con precio = f(área, estrato)."""
    rng = np.random.default_rng(0)
    n = 600
    ciudad = rng.choice(["bogota d.c.", "medellin"], n)
    sector = rng.choice(["chico", "laureles", "centro"], n)
    estrato = rng.integers(1, 7, n).astype(float)
    area = rng.uniform(30, 200, n)
    lat = np.where(ciudad == "bogota d.c.", 4.65, 6.25) + rng.normal(0, 0.02, n)
    lon = np.where(ciudad == "bogota d.c.", -74.06, -75.57) + rng.normal(0, 0.02, n)
    gold = pd.DataFrame({
        "id_inmueble": [f"id-{i}" for i in range(n)],
        "ciudad": np.where(ciudad == "bogota d.c.", "Bogotá D.C.", "Medellín"),
        "ciudad_clave": ciudad, "sector_clave": sector, "tipo_inmueble": "apartamento",
        "area_m2": area, "area_privada": np.nan, "administracion": np.nan,
        "habitaciones": 2.0, "banos": 2.0, "parqueaderos": 1.0, "estrato": estrato,
        "antiguedad_ordinal": 2.0, "piso": 3.0, "lat": lat, "lon": lon,
        "distancia_centro_km": 2.0, "es_nuevo": False, "es_proyecto": False,
        "ubicacion_aproximada": False, "habitaciones_es_tope": False,
        "banos_es_tope": False, "parqueaderos_es_tope": False,
        "grupo_near_duplicado": np.arange(n),
    })
    for columna in train.COMODIDADES:
        gold[columna] = False
    gold["precio_venta"] = (3_000_000 * area * (1 + 0.2 * estrato)).round()
    gold["precio_arriendo"] = (15_000 * area * (1 + 0.2 * estrato)).round()

    modelos = {}
    for operacion in train.OPERACIONES:
        _, X, y, _ = train.preparar(gold, operacion)
        parametros = dict(train.PARAMETROS_DEFECTO, max_iter=60)
        modelos[operacion] = {nombre: train.construir(parametros, cuantil).fit(X, y)
                              for nombre, cuantil in train.CUANTILES.items()}
    return {
        "version": 1, "features": train.FEATURES, "modelos": modelos,
        "ajuste_intervalo": {"venta": 1.5, "arriendo": 1.5},
        "sectores": train.gazetteer_interno(gold), "ciudades": train.centros_ciudad(gold),
    }


def test_predice_venta_y_arriendo_con_rango(artefacto):
    resultado = predict.predecir(artefacto, {
        "ciudad": "Bogotá D.C.", "sector": "Chicó", "tipo": "apartamento", "area_m2": 100,
        "habitaciones": 2, "banos": 2, "parqueaderos": 1, "estrato": 6,
        "antiguedad": "Entre 5 y 10 años", "comodidades": ["ascensor"]})
    venta, arriendo = resultado["venta"], resultado["arriendo"]
    # precio sintético: 3 M x 100 m² x 2,2 = 660 M; se acepta 25 % de margen
    assert 500_000_000 < venta["estimado"] < 820_000_000
    assert venta["rango"][0] <= venta["estimado"] <= venta["rango"][1]
    assert arriendo["rango"][0] <= arriendo["estimado"] <= arriendo["rango"][1]
    assert venta["precio_m2"] == round(venta["estimado"] / 100)
    assert 3 < resultado["rentabilidad_bruta_anual_%"] < 9
    assert resultado["contexto"]["sector_conocido"] is True
    assert resultado["contexto"]["origen_coordenada"] == "sector"
    assert resultado["contexto"]["estrato_usado"] == 6


def test_resuelve_sector_desconocido_y_estrato_faltante(artefacto):
    resultado = predict.predecir(artefacto, {
        "ciudad": "Medellín", "sector": "Barrio Inventado", "area_m2": 60})
    contexto = resultado["contexto"]
    assert contexto["sector_conocido"] is False
    assert contexto["origen_coordenada"] == "centro de la ciudad"
    assert contexto["origen_estrato"] == "mediana de la ciudad"
    assert contexto["estrato_usado"] in range(1, 7)


def test_el_estrato_mueve_el_precio_en_la_direccion_correcta(artefacto):
    base = {"ciudad": "Bogotá D.C.", "sector": "Chicó", "area_m2": 80}
    barato = predict.predecir(artefacto, {**base, "estrato": 2})["venta"]["estimado"]
    caro = predict.predecir(artefacto, {**base, "estrato": 6})["venta"]["estimado"]
    assert caro > barato


def test_comodidades_con_alias_y_nombre_completo(artefacto):
    base = {"ciudad": "Bogotá D.C.", "sector": "Chicó", "area_m2": 80, "estrato": 4}
    ubicacion, _ = predict.resolver_ubicacion(artefacto, base)
    fila = predict.armar_fila(artefacto, {**base, "comodidades": [
        "amoblado", "monoambiente", "ascensor", "tiene_piscina", "Conjunto cerrado", "transporte"]},
        ubicacion)
    assert fila.loc[0, "esta_amoblado"] == 1.0
    assert fila.loc[0, "es_monoambiente"] == 1.0
    assert fila.loc[0, "tiene_ascensor"] == 1.0
    assert fila.loc[0, "tiene_piscina"] == 1.0
    assert fila.loc[0, "tiene_conjunto_cerrado"] == 1.0
    assert fila.loc[0, "cerca_transporte"] == 1.0
    assert fila.loc[0, "tiene_gimnasio"] == 0.0
    with pytest.raises(ValueError, match="no conoce"):
        predict.armar_fila(artefacto, {**base, "comodidades": ["helipuerto"]}, ubicacion)


def test_valores_fuera_de_rango_se_ignoran_como_en_el_transform(artefacto):
    resultado = predict.predecir(artefacto, {
        "ciudad": "Bogotá D.C.", "sector": "Chicó", "area_m2": 80, "estrato": 9, "piso": 0,
        "lat": 40.4, "lon": -3.7})
    contexto = resultado["contexto"]
    assert "aviso_estrato" in contexto and contexto["origen_estrato"] == "mediana del sector"
    assert "aviso_coordenada" in contexto and contexto["origen_coordenada"] == "sector"
    ubicacion, _ = predict.resolver_ubicacion(artefacto, {"ciudad": "Bogotá D.C.", "sector": "Chicó"})
    fila = predict.armar_fila(artefacto, {"ciudad": "Bogotá D.C.", "area_m2": 80, "piso": 0}, ubicacion)
    assert np.isnan(fila.loc[0, "piso"])


def test_ciudad_desconocida_es_error_claro(artefacto):
    with pytest.raises(ValueError, match="no está en el modelo"):
        predict.predecir(artefacto, {"ciudad": "Atlantis", "area_m2": 50})


def test_clave_normaliza_como_el_transform():
    assert predict.clave("  Chicó   Norte ") == "chico norte"
    assert predict.clave("Bogotá D.C.") == "bogota d.c."
    assert predict.clave(None) is None


def test_formatear_es_legible(artefacto):
    texto = predict.formatear(predict.predecir(artefacto, {
        "ciudad": "Bogotá D.C.", "sector": "Chicó", "area_m2": 100, "estrato": 5}))
    assert "venta" in texto and "arriendo" in texto and "rentabilidad" in texto
