"""Las partes de src/train.py que se pueden probar sin entrenar de verdad."""
import numpy as np
import pandas as pd

import train


def test_grupos_frio_no_mezclan_ciudades_cuando_el_sector_es_nulo():
    df = pd.DataFrame({
        "precio_venta": pd.array([1, 2, 3, 4, 5], dtype="Int64") * 100_000_000,
        "area_m2": [50.0] * 5, "area_privada": [None] * 5, "administracion": [None] * 5,
        "ciudad_clave": ["bogota d.c.", "medellin", "bogota d.c.", "cali", "medellin"],
        "sector_clave": pd.array(["chico", None, "poblado", None, "laureles"], dtype="string"),
        "grupo_near_duplicado": [0, 1, 2, 3, 4], "tipo_inmueble": ["casa"] * 5,
    })
    _, _, _, grupos = train.preparar(df, "venta")
    frio = grupos["frio"]
    # las dos filas sin sector son de ciudades distintas: NO pueden compartir grupo
    assert frio[1] != frio[3]
    assert len(set(frio)) == 5
    assert (frio >= 0).all()


def test_calibrar_intervalo_alcanza_la_cobertura_pedida():
    rng = np.random.default_rng(0)
    y = rng.normal(0, 1, 5000)
    p50 = np.zeros(5000)
    p10, p90 = np.full(5000, -0.5), np.full(5000, 0.5)      # angosto a propósito
    k = train.calibrar_intervalo(y, p50, p10, p90, objetivo=0.80)
    cobertura = ((y >= p50 - k * 0.5) & (y <= p50 + k * 0.5)).mean()
    assert 1.0 < k <= 3.0
    assert cobertura >= 0.80


def test_metricas_basicas():
    y = np.log(np.array([100.0, 200.0, 400.0]))
    m = train.metricas(y, y)
    assert m["R2"] == 1.0 and m["MAE_log"] == 0.0 and m["dentro_10_%"] == 100.0
    m = train.metricas(y, y + np.log(1.1))
    assert abs(m["MdAPE_%"] - 10.0) < 0.01
