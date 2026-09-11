"""Las partes sin red del enriquecimiento (src/enrich.py)."""
import numpy as np
import pandas as pd
import pytest

import enrich


def test_normalizar_quita_tildes_y_puntuacion():
    assert enrich.normalizar("Chicó Norte") == "chico norte"
    assert enrich.normalizar("  El   Poblado - 2 ") == "el poblado 2"
    assert enrich.normalizar(None) == ""
    assert enrich.normalizar(float("nan")) == ""


def test_dividir_bbox_parte_lo_grande_y_deja_lo_chico():
    chico = (4.5, -74.2, 4.7, -74.0)          # ~22 x 22 km
    assert enrich.dividir_bbox(chico) == [chico]
    grande = (4.3, -74.4, 4.9, -73.8)         # ~67 x 67 km
    mosaicos = enrich.dividir_bbox(grande)
    assert len(mosaicos) > 1
    assert min(m[0] for m in mosaicos) == pytest.approx(4.3)
    assert max(m[2] for m in mosaicos) == pytest.approx(4.9)


def test_distancia_vectorizada_coincide_con_la_escalar():
    escalar = enrich.distancia_km(4.60, -74.08, 4.70, -74.05)
    vector = enrich.distancia_km_vector([4.60], [-74.08], [4.70], [-74.05])[0]
    assert vector == pytest.approx(escalar)
    assert 11 < escalar < 12


def _anuncios():
    return pd.DataFrame({
        "ciudad_clave": ["bogota d.c."] * 6,
        "sector_norm": ["chico"] * 4 + ["raro", "chico"],
        "lat": pd.array([4.67, 4.68, 4.66, None, None, 10.0], dtype="Float64"),
        "lon": pd.array([-74.05, -74.04, -74.06, None, None, -74.0], dtype="Float64"),
        "ubicacion_aproximada": pd.array([False, False, None, None, None, False], dtype="boolean"),
        "lat_barrio": [np.nan, np.nan, np.nan, np.nan, 4.60, np.nan],
        "lon_barrio": [np.nan, np.nan, np.nan, np.nan, -74.10, np.nan],
        "estrato": pd.array([6, None, 6, None, None, 3], dtype="Int8"),
        "estrato_modal": [np.nan, 5.0, np.nan, 4.0, np.nan, np.nan],
    })


def test_cascada_de_coordenadas_y_estrato():
    df = _anuncios()
    df["origen_coordenada"] = np.where(df["lat"].notna(), "anuncio", "ninguna")
    centros = enrich.centros_de_ciudad(df, {})
    assert centros == {}                       # menos de N_MINIMO_CIUDAD anuncios
    centros = {"bogota d.c.": (4.65, -74.06)}

    df = enrich.anular_coordenadas_lejanas(df, centros)
    assert df["coordenada_lejana"].tolist() == [False] * 5 + [True]
    assert df["origen_coordenada"].iloc[5] == "ninguna" and pd.isna(df["lat"].iloc[5])

    sectores = enrich.construir_gazetteer_interno(df)
    assert len(sectores) == 1 and sectores.loc[0, "n_sector"] == 3
    assert sectores.loc[0, "lat_sector"] == pytest.approx(4.67)

    df = enrich.completar_coordenadas(df, sectores)
    assert df["origen_coordenada"].tolist() == [
        "anuncio", "anuncio", "anuncio", "sector_propio", "barrio_osm", "sector_propio"]
    assert df["lat"].iloc[3] == pytest.approx(4.67)
    assert df["lat"].iloc[4] == pytest.approx(4.60)

    df = enrich.agregar_distancia_centro(df, centros)
    assert df["distancia_centro_km"].notna().all()
    assert df["distancia_centro_km"].iloc[4] > df["distancia_centro_km"].iloc[3]

    df = enrich.completar_estrato(df)
    assert df["origen_estrato"].tolist() == [
        "anuncio", "barrio_osm", "anuncio", "barrio_osm", "ninguno", "anuncio"]
    assert df["estrato"].tolist()[1] == 5
