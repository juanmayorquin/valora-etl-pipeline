"""Reglas del transform (src/transform.py) sobre DataFrames mínimos."""
import numpy as np
import pandas as pd
import pytest

import transform


def test_es_relleno_detecta_digitos_repetidos_y_secuencias():
    serie = pd.Series(["$1.111.111", "$123.456.000", "$570.000.000", "$1.850.000.000"])
    assert transform.es_relleno(serie).tolist() == [True, True, False, False]


def test_a_entero_quita_separadores_de_miles():
    serie = pd.Series(["$1.850.000.000", "570000000", None])
    assert transform.a_entero(serie).tolist()[:2] == [1_850_000_000, 570_000_000]
    assert pd.isna(transform.a_entero(serie).iloc[2])


def test_vallas_iqr_log_en_escala_original():
    serie = pd.Series(np.exp(np.linspace(0, 4, 100)))
    inferior, superior = transform.vallas_iqr_log(serie)
    assert 0 < inferior < superior
    assert np.isnan(transform.vallas_iqr_log(pd.Series([1.0, 2.0]))[0])


def test_tipo_desde_url_lee_el_slug():
    urls = pd.Series(["https://x/inmueble/venta-apartaestudio-bogota-chico/1-M1",
                      "https://x/inmueble/arriendo-casa-cali-sur/2-M2",
                      "https://x/otra-cosa"])
    assert transform.tipo_desde_url(urls).tolist()[:2] == ["apartaestudio", "casa"]
    assert pd.isna(transform.tipo_desde_url(urls).iloc[2])


def test_comodidades_respetan_el_ancla_de_item():
    df = pd.DataFrame({"comodidades": [
        "Ascensor | Piscina | Depósito 0",
        "Tipo de piso en estudio laminado | Vigilancia 24hrs",
        "Estudio | Cuarto útil | Conjunto cerrado",
        None,
    ]})
    df = transform.derivar_comodidades(df)
    assert df["tiene_ascensor"].tolist() == [True, False, False, False]
    assert df["tiene_piscina"].tolist() == [True, False, False, False]
    # "Depósito 0" significa que NO hay depósito; "Cuarto útil" sí cuenta
    assert df["tiene_deposito"].tolist() == [False, False, True, False]
    # "tipo de piso en estudio" no es un estudio
    assert df["tiene_estudio"].tolist() == [False, False, True, False]
    assert df["tiene_vigilancia"].tolist() == [False, True, False, False]
    assert df["tiene_conjunto_cerrado"].tolist() == [False, False, True, False]
    assert all(df[c].dtype == bool for c in transform.COMODIDADES)


def _base_detalle(**columnas):
    base = {
        "estrato": [6, 7, None], "lat": [4.67, 4.67, 50.0], "lon": [-74.05, -74.05, 8.0],
        "area_m2": [38.0, 100.0, 60.0], "area_privada": [38.0, 120.0, None],
        "piso": [5, 0, 80], "administracion": [300_000, 5_000_000, None],
        "precio_arriendo": pd.array([1_700_000, 2_000_000, None], dtype="Int64"),
        "antiguedad": ["Entre 0 y 5 años", "Remodelado", None],
        "estado_inmueble": ["Nuevo", "Usado", None],
        "es_proyecto": [True, None, None], "tiene_video": [None, None, None],
        "destacado": [None, None, None], "ubicacion_aproximada": [False, None, True],
        "n_fotos": [16, None, 3],
    }
    base.update(columnas)
    return pd.DataFrame(base)


def test_sanear_detalle_anula_lo_imposible_y_lo_marca():
    df = transform.sanear_detalle(_base_detalle())
    assert df["estrato"].tolist()[0] == 6 and pd.isna(df["estrato"].iloc[1])
    assert df["estrato_invalido"].tolist() == [False, True, False]
    assert df["coordenada_invalida"].tolist() == [False, False, True]
    assert pd.isna(df["lat"].iloc[2]) and pd.isna(df["lon"].iloc[2])
    assert df["area_privada_invalida"].tolist() == [False, True, False]
    assert df["piso"].tolist()[0] == 5 and pd.isna(df["piso"].iloc[1]) and pd.isna(df["piso"].iloc[2])
    assert df["administracion_invalida"].tolist() == [False, True, False]
    assert df["antiguedad_ordinal"].tolist()[0] == 1 and pd.isna(df["antiguedad_ordinal"].iloc[1])
    assert df["es_nuevo"].tolist() == [True, False, False]
    assert df["es_proyecto"].tolist() == [True, False, False]


def test_sanear_detalle_no_revienta_con_valores_que_no_caben_en_el_tipo():
    df = transform.sanear_detalle(_base_detalle(estrato=[200, 3, None], piso=[99_999, 2, None],
                                                n_fotos=[70_000, 3, None]))
    assert pd.isna(df["estrato"].iloc[0]) and df["estrato_invalido"].iloc[0]
    assert pd.isna(df["piso"].iloc[0]) and pd.isna(df["n_fotos"].iloc[0])
    assert str(df["estrato"].dtype) == "Int8" and str(df["piso"].dtype) == "Int16"


def test_marcar_censuradas_acota_antes_de_castear():
    df = pd.DataFrame({"habitaciones": [None, 3, 150], "banos": [2, None, 1], "parqueaderos": [None, None, 9],
                       "habitaciones_detalle": [4, None, None], "banos_detalle": [None, 7, None],
                       "parqueaderos_detalle": [0, None, None]})
    df = transform.marcar_censuradas(df)
    assert df["habitaciones"].tolist() == [4, 3, 5]          # detalle rellena; 150 se acota al tope
    assert df["habitaciones_es_tope"].tolist() == [False, False, True]
    assert df["banos"].tolist() == [2, 5, 1]
    assert df["parqueaderos"].tolist()[0] == 0 and pd.isna(df["parqueaderos"].iloc[1])


def test_sin_precio_mira_el_precio_de_la_operacion():
    df = pd.DataFrame({"operacion": ["arriendo", "venta", "ambas"],
                       "precio_arriendo": pd.array([None, None, 2_000_000], dtype="Int64"),
                       "precio_venta": pd.array([500_000_000, None, None], dtype="Int64"),
                       "area_m2": [50.0, 60.0, 70.0]})
    df = transform.marcar_ausencias(df)
    # un arriendo sin canon no se salva por traer precio de venta; un dual sin venta tampoco
    assert df["sin_precio"].tolist() == [True, True, True]


def test_separar_precios_prefiere_el_detalle_y_marca_discrepancias():
    df = pd.DataFrame({
        "precio_texto": ["$570.000.000", "$1.700.000", "$900.000.000", "$2.000.000"],
        "operacion_feed": ["venta", "arriendo", "arriendo", "arriendo"],
        "es_dual": [False, False, True, False],
        "precio_venta_detalle": [570_000_000, None, 900_000_000, None],
        "precio_arriendo_detalle": [None, 1_750_000, 4_000_000, None],
    })
    df = transform.separar_precios(df)
    assert df["precio_venta"].tolist()[0] == 570_000_000
    assert df["precio_arriendo"].tolist()[1] == 1_750_000        # manda el detalle
    assert df["precio_discrepante"].tolist() == [False, True, False, False]
    # el dual ahora conoce su canon gracias al detalle
    assert df["precio_arriendo"].tolist()[2] == 4_000_000 and df["precio_venta"].tolist()[2] == 900_000_000
    # sin detalle, la tarjeta sigue mandando
    assert df["precio_arriendo"].tolist()[3] == 2_000_000 and not df["precio_desde_detalle"].iloc[3]


def test_precio_unificado_por_operacion():
    df = pd.DataFrame({
        "operacion": ["arriendo", "venta", "ambas"],
        "precio_arriendo": pd.array([1_000_000, None, 3_000_000], dtype="Int64"),
        "precio_venta": pd.array([None, 500_000_000, 800_000_000], dtype="Int64"),
    })
    assert transform.precio_unificado(df).tolist() == [1_000_000, 500_000_000, 800_000_000]


def test_near_duplicados_agrupan_misma_ciudad_sector_tipo_area_y_precio():
    df = pd.DataFrame({
        "ciudad_clave": ["bogota d.c."] * 3 + ["cali"],
        "sector_clave": ["chico"] * 3 + ["chico"],
        "tipo_inmueble": ["apartamento"] * 4,
        "area_m2": [80.0, 80.0, 81.0, 80.0],
        "operacion": ["venta"] * 4,
        "precio_arriendo": pd.array([None] * 4, dtype="Int64"),
        "precio_venta": pd.array([500_000_000] * 4, dtype="Int64"),
    })
    df = transform.marcar_near_duplicados(df)
    assert df["es_near_duplicado"].tolist() == [True, True, False, False]
    assert df["grupo_near_duplicado"].iloc[0] == df["grupo_near_duplicado"].iloc[1]
    assert df["grupo_near_duplicado"].nunique() == 3


def test_unir_detalle_no_cambia_el_numero_de_filas():
    crudo = pd.DataFrame({"id_inmueble": ["a", "b", "c"], "x": [1, 2, 3]})
    detalle = pd.DataFrame({"id_inmueble": ["a", "c"], **{
        c: [1, 2] for c in transform.COLUMNAS_DETALLE + transform.COLUMNAS_DETALLE_RECONCILIADAS}})
    unido = transform.unir_detalle(crudo, detalle)
    assert len(unido) == 3
    assert unido["con_detalle"].tolist() == [True, False, True]
    sin = transform.unir_detalle(crudo.copy(), None)
    assert sin["con_detalle"].tolist() == [False] * 3 and "estrato" in sin.columns


def test_unir_detalle_rechaza_ids_repetidos():
    crudo = pd.DataFrame({"id_inmueble": ["a"]})
    detalle = pd.DataFrame({"id_inmueble": ["a", "a"], **{
        c: [1, 2] for c in transform.COLUMNAS_DETALLE + transform.COLUMNAS_DETALLE_RECONCILIADAS}})
    with pytest.raises(Exception):
        transform.unir_detalle(crudo, detalle)
