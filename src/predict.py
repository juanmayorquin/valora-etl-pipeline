"""Predicción de precio con el artefacto de `train.py`: venta y arriendo a la vez.

Se usa de dos formas:

    desde Python (el sandbox del notebook 05):
        from predict import cargar_modelo, predecir
        modelo = cargar_modelo("models/valora_modelo.joblib")
        predecir(modelo, {"ciudad": "Bogotá D.C.", "sector": "Chicó Norte",
                          "tipo": "apartamento", "area_m2": 85, "habitaciones": 2,
                          "banos": 2, "parqueaderos": 1, "estrato": 6,
                          "antiguedad": "Entre 5 y 10 años", "comodidades": ["ascensor"]})

    por línea de comandos:
        python src/predict.py --ciudad "Bogotá D.C." --sector "Chicó Norte" \\
            --tipo apartamento --area 85 --habitaciones 2 --banos 2 --parqueaderos 1 \\
            --estrato 6 --antiguedad "Entre 5 y 10 años" --comodidades ascensor,gimnasio

Lo que el usuario no da, se resuelve: sin coordenada se busca el sector en el gazetteer
interno del artefacto (y si tampoco está, el centro de la ciudad); sin estrato se usa la
mediana del sector. El resultado dice de dónde salió cada cosa.

Códigos de salida:
    0  predicción hecha
    1  no se encontró el artefacto o la ciudad no existe en el modelo
"""

import argparse
import json
import math
import sys
import unicodedata
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

RUTA_MODELO = Path("models/valora_modelo.joblib")

ANTIGUEDAD_ORDINAL = {
    "Menos de 1 año": 0, "Entre 0 y 5 años": 1, "Entre 5 y 10 años": 2,
    "Entre 10 y 20 años": 3, "Más de 20 años": 4,
}
TOPES = {"habitaciones": 5, "banos": 5, "parqueaderos": 4}
# Los mismos límites que aplica el transform (R13): lo que el modelo vio como nulo en
# entrenamiento tiene que llegarle como nulo acá, no como un valor que nunca aprendió.
RANGO_ESTRATO = (1, 6)
RANGO_PISO = (1, 60)
BBOX_COLOMBIA = {"lat": (-4.3, 13.6), "lon": (-82.0, -66.8)}
# Nombres cortos aceptados en `comodidades`, además del nombre completo de la columna y
# de los cortos que se resuelven solos con el prefijo tiene_/cerca_ ("ascensor",
# "transporte").
ALIAS_COMODIDADES = {
    "amoblado": "esta_amoblado", "amueblado": "esta_amoblado", "equipado": "esta_amoblado",
    "monoambiente": "es_monoambiente", "mascotas": "acepta_mascotas", "rural": "es_zona_rural",
    "sauna": "tiene_sauna_turco", "turco": "tiene_sauna_turco", "aire": "tiene_aire_acondicionado",
    "vista": "tiene_vista_exterior", "cancha": "tiene_canchas", "closet": "tiene_walking_closet",
}


def resolver_comodidad(nombre, features):
    """'ascensor' -> tiene_ascensor, 'transporte' -> cerca_transporte, 'amoblado' ->
    esta_amoblado; el nombre completo de la columna también vale."""
    nombre = clave(nombre).replace(" ", "_")
    if nombre in ALIAS_COMODIDADES:
        return ALIAS_COMODIDADES[nombre]
    for candidato in (nombre, f"tiene_{nombre}", f"cerca_{nombre}"):
        if candidato in features:
            return candidato
    return None


def sin_tilde(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def clave(texto):
    """La misma normalización que usa el transform para `ciudad_clave` y `sector_clave`:
    espacios colapsados, sin tildes, minúsculas."""
    if texto is None:
        return None
    return sin_tilde(" ".join(str(texto).split())).lower() or None


def cargar_modelo(ruta=RUTA_MODELO):
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"No existe {ruta}: hay que correr `python src/train.py`")
    return joblib.load(ruta)


# --------------------------------------------------------------------------------------
# Resolver la ubicación
# --------------------------------------------------------------------------------------

def resolver_ubicacion(modelo, inmueble):
    """Coordenada, estrato y distancia al centro para el inmueble, con su origen."""
    ciudad = clave(inmueble.get("ciudad"))
    sector = clave(inmueble.get("sector"))
    ciudades = modelo["ciudades"]
    fila_ciudad = ciudades[ciudades["ciudad_clave"] == ciudad]
    if fila_ciudad.empty:
        raise ValueError(f"La ciudad '{inmueble.get('ciudad')}' no está en el modelo. "
                         f"Hay {len(ciudades)} ciudades; las más frecuentes: "
                         + ", ".join(ciudades.sort_values("n", ascending=False)["ciudad"].head(8)))
    fila_ciudad = fila_ciudad.iloc[0]

    sectores = modelo["sectores"]
    coincidencia = sectores[(sectores["ciudad_clave"] == ciudad) & (sectores["sector_clave"] == sector)]
    contexto = {"ciudad": fila_ciudad["ciudad"], "sector": inmueble.get("sector"),
                "sector_conocido": not coincidencia.empty,
                "n_comparables_sector": int(coincidencia["n"].iloc[0]) if not coincidencia.empty else 0}

    lat_usuario, lon_usuario = inmueble.get("lat"), inmueble.get("lon")
    coordenada_valida = (lat_usuario is not None and lon_usuario is not None
                         and BBOX_COLOMBIA["lat"][0] <= float(lat_usuario) <= BBOX_COLOMBIA["lat"][1]
                         and BBOX_COLOMBIA["lon"][0] <= float(lon_usuario) <= BBOX_COLOMBIA["lon"][1])
    if lat_usuario is not None and not coordenada_valida:
        contexto["aviso_coordenada"] = "la coordenada dada cae fuera de Colombia: se ignora"
    if coordenada_valida:
        lat, lon, origen = float(lat_usuario), float(lon_usuario), "usuario"
    elif not coincidencia.empty:
        lat, lon, origen = float(coincidencia["lat"].iloc[0]), float(coincidencia["lon"].iloc[0]), "sector"
    else:
        lat, lon, origen = float(fila_ciudad["lat"]), float(fila_ciudad["lon"]), "centro de la ciudad"
    contexto["origen_coordenada"] = origen

    estrato_usuario = inmueble.get("estrato")
    if estrato_usuario is not None and not RANGO_ESTRATO[0] <= float(estrato_usuario) <= RANGO_ESTRATO[1]:
        contexto["aviso_estrato"] = f"estrato {estrato_usuario} fuera de 1-6: se ignora"
        estrato_usuario = None
    if estrato_usuario is not None:
        estrato, origen_estrato = float(estrato_usuario), "usuario"
    elif not coincidencia.empty and not math.isnan(coincidencia["estrato"].iloc[0]):
        estrato, origen_estrato = float(coincidencia["estrato"].iloc[0]), "mediana del sector"
    elif not math.isnan(fila_ciudad["estrato"]):
        estrato, origen_estrato = float(fila_ciudad["estrato"]), "mediana de la ciudad"
    else:
        estrato, origen_estrato = np.nan, "desconocido"
    contexto["origen_estrato"] = origen_estrato

    escala_lon = math.cos(math.radians(fila_ciudad["lat"])) * 111.32
    distancia = math.hypot((lat - fila_ciudad["lat"]) * 111.32, (lon - fila_ciudad["lon"]) * escala_lon)
    return {"ciudad_clave": ciudad, "lat": lat, "lon": lon, "estrato": estrato,
            "distancia_centro_km": round(distancia, 3)}, contexto


# --------------------------------------------------------------------------------------
# Armar la fila y predecir
# --------------------------------------------------------------------------------------

def a_ordinal_antiguedad(valor):
    if valor is None:
        return np.nan
    if isinstance(valor, (int, float)):
        return float(valor)
    return float(ANTIGUEDAD_ORDINAL.get(valor, np.nan))


def log_o_nan(valor):
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return np.nan
    return math.log(valor) if valor > 0 else np.nan


def armar_fila(modelo, inmueble, ubicacion):
    """Una fila con las mismas features y derivaciones que usó train.py."""
    comodidades, desconocidas = set(), []
    for nombre in (inmueble.get("comodidades") or []):
        columna = resolver_comodidad(nombre, modelo["features"])
        (comodidades.add if columna else desconocidas.append)(columna or nombre)
    if desconocidas:
        validas = sorted(f for f in modelo["features"]
                         if f.startswith(("tiene_", "cerca_", "esta_", "es_zona", "es_mono", "acepta_")))
        raise ValueError(f"Comodidades que el modelo no conoce: {desconocidas}. "
                         f"Válidas: {', '.join(validas)}")
    piso = inmueble.get("piso")
    if piso is not None and not RANGO_PISO[0] <= float(piso) <= RANGO_PISO[1]:
        piso = None   # el transform anula los pisos fuera de 1-60; acá igual
    conteos = {}
    for columna, tope in TOPES.items():
        valor = inmueble.get(columna)
        conteos[columna] = np.nan if valor is None else min(float(valor), tope)
        conteos[f"{columna}_es_tope"] = float(valor is not None and float(valor) >= tope)
    valores = {
        "tipo_inmueble": inmueble.get("tipo", "apartamento"),
        "ciudad_clave": ubicacion["ciudad_clave"],
        "log_area": log_o_nan(inmueble.get("area_m2")),
        "log_administracion": log_o_nan(inmueble.get("administracion")),
        "estrato": ubicacion["estrato"],
        "antiguedad_ordinal": a_ordinal_antiguedad(inmueble.get("antiguedad")),
        "piso": np.nan if piso is None else float(piso),
        "lat": ubicacion["lat"], "lon": ubicacion["lon"],
        "distancia_centro_km": ubicacion["distancia_centro_km"],
        "es_nuevo": float(bool(inmueble.get("es_nuevo", False))),
        "es_proyecto": float(bool(inmueble.get("es_proyecto", False))),
        "ubicacion_aproximada": 0.0,
        **conteos,
    }
    # Toda feature que no sea un atributo explícito es una bandera de comodidad: 1 si el
    # usuario la nombró, 0 si no. Así una comodidad nueva en el artefacto no necesita
    # cambios acá.
    fila = {feature: valores[feature] if feature in valores else float(feature in comodidades)
            for feature in modelo["features"]}
    return pd.DataFrame([fila])[modelo["features"]]


def predecir(modelo, inmueble):
    """Devuelve el avalúo de venta y de arriendo, con rango p10-p90 y precio por m²,
    más la rentabilidad bruta anual que implican y el contexto de la resolución."""
    ubicacion, contexto = resolver_ubicacion(modelo, inmueble)
    fila = armar_fila(modelo, inmueble, ubicacion)
    area = float(inmueble.get("area_m2") or np.nan)

    resultado = {"contexto": contexto}
    for operacion, modelos in modelo["modelos"].items():
        en_log = {nombre: float(m.predict(fila)[0]) for nombre, m in modelos.items()}
        # El rango se ensancha con el factor calibrado en train.py para cubrir el 80 %
        k = modelo.get("ajuste_intervalo", {}).get(operacion, 1.0)
        bajo = en_log["p50"] - k * max(en_log["p50"] - en_log["p10"], 0.0)
        alto = en_log["p50"] + k * max(en_log["p90"] - en_log["p50"], 0.0)
        estimado = math.exp(en_log["p50"])
        resultado[operacion] = {
            "estimado": round(estimado),
            "rango": [round(math.exp(bajo)), round(math.exp(alto))],
            "precio_m2": round(estimado / area) if area and not math.isnan(area) else None,
        }
    if "venta" in resultado and "arriendo" in resultado:
        resultado["rentabilidad_bruta_anual_%"] = round(
            12 * resultado["arriendo"]["estimado"] / resultado["venta"]["estimado"] * 100, 2)
    resultado["contexto"]["estrato_usado"] = None if math.isnan(ubicacion["estrato"]) else int(ubicacion["estrato"])
    resultado["contexto"]["coordenada_usada"] = [round(ubicacion["lat"], 5), round(ubicacion["lon"], 5)]
    resultado["contexto"]["distancia_centro_km"] = ubicacion["distancia_centro_km"]
    return resultado


def pesos(valor):
    return f"$ {valor:,.0f}".replace(",", ".")


def formatear(resultado):
    contexto = resultado["contexto"]
    lineas = [
        f"{contexto['ciudad']} - {contexto['sector'] or 'sin sector'} "
        f"({'sector conocido, ' + str(contexto['n_comparables_sector']) + ' comparables' if contexto['sector_conocido'] else 'sector no visto'})",
        f"  coordenada: {contexto['origen_coordenada']} | estrato {contexto['estrato_usado']} "
        f"({contexto['origen_estrato']}) | {contexto['distancia_centro_km']} km del centro",
    ]
    for operacion in ("venta", "arriendo"):
        if operacion not in resultado:
            continue
        r = resultado[operacion]
        m2 = f" | {pesos(r['precio_m2'])}/m²" if r["precio_m2"] else ""
        lineas.append(f"  {operacion:9} {pesos(r['estimado'])}   rango {pesos(r['rango'][0])} - "
                      f"{pesos(r['rango'][1])}{m2}")
    if "rentabilidad_bruta_anual_%" in resultado:
        lineas.append(f"  rentabilidad bruta anual implícita: {resultado['rentabilidad_bruta_anual_%']} %")
    return "\n".join(lineas)


def parse_args():
    parser = argparse.ArgumentParser(description="Estima el precio de venta y el canon de un inmueble")
    parser.add_argument("--modelo", default=str(RUTA_MODELO))
    parser.add_argument("--ciudad", required=True)
    parser.add_argument("--sector", default=None)
    parser.add_argument("--tipo", choices=("apartaestudio", "apartamento", "casa"), default="apartamento")
    parser.add_argument("--area", type=float, required=True, help="Área construida en m²")
    parser.add_argument("--habitaciones", type=int, default=None)
    parser.add_argument("--banos", type=int, default=None)
    parser.add_argument("--parqueaderos", type=int, default=None)
    parser.add_argument("--estrato", type=int, default=None)
    parser.add_argument("--antiguedad", default=None,
                        help="Texto del sitio: 'Menos de 1 año', 'Entre 0 y 5 años', ...")
    parser.add_argument("--piso", type=int, default=None)
    parser.add_argument("--administracion", type=int, default=None)
    parser.add_argument("--comodidades", default="",
                        help="Separadas por coma: ascensor,piscina,gimnasio,conjunto_cerrado,...")
    parser.add_argument("--nuevo", action="store_true", help="Inmueble nuevo o en proyecto")
    parser.add_argument("--lat", type=float, default=None)
    parser.add_argument("--lon", type=float, default=None)
    parser.add_argument("--json", action="store_true", help="Salida en JSON")
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        modelo = cargar_modelo(args.modelo)
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return 1
    inmueble = {
        "ciudad": args.ciudad, "sector": args.sector, "tipo": args.tipo, "area_m2": args.area,
        "habitaciones": args.habitaciones,
        "banos": args.banos, "parqueaderos": args.parqueaderos, "estrato": args.estrato,
        "antiguedad": args.antiguedad, "piso": args.piso, "administracion": args.administracion,
        "comodidades": [c.strip() for c in args.comodidades.split(",") if c.strip()],
        "es_nuevo": args.nuevo, "lat": args.lat, "lon": args.lon,
    }
    try:
        resultado = predecir(modelo, inmueble)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    print(json.dumps(resultado, ensure_ascii=False, indent=2) if args.json else formatear(resultado))
    return 0


if __name__ == "__main__":
    sys.exit(main())
