"""El enriquecimiento (src/enrich.py): cascada de coordenada sobre un DataFrame mínimo."""
import numpy as np
import pandas as pd
import pytest

import enrich


def test_normalizar_quita_tildes_y_puntuacion():
    assert enrich.normalizar("Chicó Norte") == "chico norte"
    assert enrich.normalizar("  El   Poblado - 2 ") == "el poblado 2"
    assert enrich.normalizar(None) == ""
    assert enrich.normalizar(float("nan")) == ""


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
        "estrato": pd.array([6, None, 6, None, None, 3], dtype="Int8"),
    })


def test_cascada_de_coordenadas():
    df = _anuncios()
    df["origen_coordenada"] = np.where(df["lat"].notna(), "anuncio", "ninguna")
    assert enrich.centros_de_ciudad(df) == {}          # menos de N_MINIMO_CIUDAD anuncios
    centros = {"bogota d.c.": (4.65, -74.06)}

    df = enrich.anular_coordenadas_lejanas(df, centros)
    assert df["coordenada_lejana"].tolist() == [False] * 5 + [True]
    assert df["origen_coordenada"].iloc[5] == "ninguna" and pd.isna(df["lat"].iloc[5])

    sectores = enrich.construir_gazetteer_interno(df)
    assert len(sectores) == 1 and sectores.loc[0, "n_sector"] == 3
    assert sectores.loc[0, "lat_sector"] == pytest.approx(4.67)

    df = enrich.completar_coordenadas(df, sectores)
    assert df["origen_coordenada"].tolist() == [
        "anuncio", "anuncio", "anuncio", "sector_propio", "ninguna", "sector_propio"]
    assert df["lat"].iloc[3] == pytest.approx(4.67)
    assert pd.isna(df["lat"].iloc[4])                  # sector "raro": nulo honesto

    df = enrich.agregar_distancia_centro(df, centros)
    assert df["distancia_centro_km"].notna().sum() == 5
    assert pd.isna(df["distancia_centro_km"].iloc[4])


def test_enriquecer_de_punta_a_punta_conserva_filas_y_anota_origenes():
    df = _anuncios().rename(columns={"sector_norm": "sector_clave"})
    df["ciudad_clave"] = ["bogota d.c."] * 6
    enriquecido, sectores = enrich.enriquecer(df)
    assert len(enriquecido) == 6
    assert "sector_norm" not in enriquecido.columns
    assert enriquecido["origen_estrato"].tolist() == [
        "anuncio", "ninguno", "anuncio", "ninguno", "ninguno", "anuncio"]
    assert set(enrich.COLUMNAS_NUEVAS) <= set(enriquecido.columns)
