"""Parser de la página de detalle (src/detail.py), contra dos páginas reales guardadas
en tests/fixtures/ con los datos de contacto del anunciante enmascarados."""
import pytest

import detail
from conftest import FIXTURES


@pytest.fixture(scope="module")
def venta():
    return detail.extraer_objeto((FIXTURES / "detalle_venta.html").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def arriendo():
    return detail.extraer_objeto((FIXTURES / "detalle_arriendo.html").read_text(encoding="utf-8"))


def test_extrae_el_objeto_completo_no_la_copia_con_referencias(venta):
    # La página serializa el inmueble dos veces; la segunda tiene "$9:props:..." en vez
    # de subobjetos. Se tiene que elegir la completa.
    assert venta["propertyId"] == "22188-M6880659"
    assert isinstance(venta["city"], dict)
    assert isinstance(venta["coordinates"], dict)


def test_aplanar_venta(venta):
    fila = detail.aplanar(venta)
    assert fila["estrato"] == 6
    assert fila["precio_venta_detalle"] == 570_000_000
    assert fila["precio_arriendo_detalle"] is None       # rentPrice 0 = no aplica
    assert fila["area_construida"] == 38
    assert fila["parqueaderos_detalle"] == 0             # garages "0" sí es un dato
    assert fila["lat"] == pytest.approx(4.671905)
    assert fila["lon"] == pytest.approx(-74.057594)
    assert fila["ubicacion_aproximada"] is False
    assert fila["piso"] == 5                             # sale de "Número de piso 5"
    assert "Número de piso" not in fila["comodidades"]
    assert "Conjunto cerrado" in fila["comodidades"]
    assert fila["antiguedad"] == "Entre 0 y 5 años"
    assert fila["estado_inmueble"] == "Usado"
    assert fila["n_fotos"] == 16


def test_aplanar_arriendo(arriendo):
    fila = detail.aplanar(arriendo)
    assert fila["estrato"] == 3
    assert fila["precio_arriendo_detalle"] == 1_700_000
    assert fila["precio_venta_detalle"] is None
    assert fila["ubicacion_aproximada"] is None          # el sitio no lo dice
    assert fila["piso"] is None
    assert fila["tiene_video"] is True
    assert fila["zona"] is None


def test_no_guarda_datos_de_contacto(venta, arriendo):
    prohibidas = {"contactPhone", "whatsapp", "localPhone", "companyAddress", "companyName",
                  "whatsappMessage"}
    for data in (venta, arriendo):
        fila = detail.aplanar(data)
        assert prohibidas.isdisjoint(fila)
        assert set(fila) == set(detail.COLUMNAS) - {"estado", "fecha_detalle"}


def test_pagina_sin_objeto_devuelve_none():
    assert detail.extraer_objeto("<html><body>nada</body></html>") is None
    assert detail.extraer_objeto('self.__next_f.push([1,"sin el inmueble"])') is None


def test_objeto_balanceado_respeta_llaves_dentro_de_strings():
    texto = 'x{"a":"}","b":{"c":1}}y'
    assert detail.objeto_balanceado(texto, 1) == '{"a":"}","b":{"c":1}}'


def test_url_ascii_codifica_el_guion_suave():
    url = "https://www.metrocuadrado.com/inmueble/arriendo-vereda-normanda\xada-1/19474-M5633466"
    assert detail.url_ascii(url) == (
        "https://www.metrocuadrado.com/inmueble/arriendo-vereda-normanda%C2%ADa-1/19474-M5633466")
    assert detail.url_ascii("https://a.co/b?c=1&d=2") == "https://a.co/b?c=1&d=2"


def test_a_numero():
    assert detail.a_numero("6", entero=True) == 6
    assert detail.a_numero(0) is None
    assert detail.a_numero("0", entero=True, cero_valido=True) == 0
    assert detail.a_numero("no") is None
    assert detail.a_numero(-1) is None
    assert detail.a_coordenada("-74.05") == pytest.approx(-74.05)
    assert detail.a_coordenada(0) is None


def test_procesar_nunca_propaga_excepciones(monkeypatch):
    def explota(url):
        raise ValueError("url ilegible")
    monkeypatch.setattr(detail, "descargar", explota)
    registro = detail.procesar("X-1", "https://ejemplo/x", pausa=0)
    assert registro["estado"] == detail.ERROR
    assert registro["id_inmueble"] == "X-1"


def test_consolidar_tipa_las_columnas(venta):
    fila = detail.aplanar(venta)
    fila.update({"estado": detail.OK, "fecha_detalle": "2026-09-11T00:00:00+00:00"})
    df = detail.consolidar({fila["id_inmueble"]: fila})
    assert list(df.columns) == detail.COLUMNAS
    assert str(df["estrato"].dtype) == "Int8"
    assert str(df["lat"].dtype) == "Float64"
    assert str(df["ubicacion_aproximada"].dtype) == "boolean"
    assert df.loc[0, "precio_venta_detalle"] == 570_000_000
