"""Entrenamiento del modelo de precio - sexta etapa (Train) del flujo ETL.

Lee el gold (`data/processed/anuncios_enriquecido.parquet`, o `valora.anuncios` en
ClickHouse con `--desde-clickhouse`) y entrena dos modelos de precio, uno por operación,
que después consume `src/predict.py` y el sandbox del notebook 05.

Qué produce en `models/`:

    valora_modelo.joblib          el artefacto: seis modelos, features, gazetteer interno,
                                  centros de ciudad y métricas
    entrenamiento_resumen.json    métricas en los dos regímenes, por ciudad y por tipo
    predicciones_oof.parquet      predicción out-of-fold de cada anuncio, para diagnóstico

Y sube el artefacto a `s3://<bucket>/models/fecha=YYYY-MM-DD/` salvo `--sin-minio`.
El modelo y su resumen se versionan en el repo: un clon puede predecir sin entrenar.

Métricas que reporta, y qué mide cada una:

    entrenamiento    el modelo final evaluado sobre las filas con que se ajustó. NO mide
                     generalización; mide la brecha contra out-of-fold (sobreajuste).
    conocido         out-of-fold con GroupKFold por near-duplicado: la unidad republicada
                     nunca queda repartida entre train y test, pero el barrio sí se vio.
    frio             out-of-fold con GroupKFold por sector: el sector entero queda de un
                     solo lado. Es el número que se parece a producción.

    R²               fracción de la varianza de log(precio) que el modelo explica.
    MAE_log          error absoluto medio en log; ~ error relativo medio.
    MAPE / MdAPE     error porcentual medio / mediano sobre el precio real. El mediano es
                     robusto a los anuncios absurdos; el medio los sufre.
    dentro_10/20     % de anuncios cuyo error queda por debajo del 10 % / 20 %.
    cobertura        % de anuncios reales que caen dentro del rango p10-p90 (objetivo 80 %),
                     antes y después de calibrar el factor k sobre folds no vistos.

Decisiones de modelado, y por qué:

    Un modelo por operación   Canon mensual y precio de venta no comparten escala ni
                              elasticidades; un solo modelo con `operacion` como feature
                              obliga a los árboles a gastar splits en separarlas.
    Target log(precio)        El error relevante es relativo: 10 % en un apartaestudio y
                              10 % en una casa de 2.000 millones. En log, el MAE es
                              directamente ese error relativo.
    Tres modelos por operación   Mediana (p50) más cuantiles p10 y p90. Un avalúo sin
                              rango es un número seco; con el rango, el usuario sabe
                              cuánto confiar.
    Split agrupado, siempre   El 9 % de las filas son near-duplicados (misma unidad
                              republicada). Con split aleatorio el modelo ve la respuesta
                              en train y la métrica miente. Se evalúa en DOS regímenes:
                                conocido   GroupKFold por near-duplicado: barrios ya vistos
                                frio       GroupKFold por sector: un barrio que el modelo
                                           nunca vio. Es el que se parece a producción.
    Features del inmueble     Lo que describe al inmueble entra; lo que describe al
                              ANUNCIO (fotos, inmobiliaria, destacado) no. El sandbox tiene
                              que valuar un inmueble que no está publicado.
    HistGradientBoosting      Maneja nulos y categóricas sin imputar ni one-hot, entrena
                              en segundos y ya está en el stack. LightGBM o CatBoost no
                              mostraron ganancia que justifique otro compilado en la imagen.

Uso:
    python src/train.py
    python src/train.py --sin-busqueda            # hiperparámetros por defecto, más rápido
    python src/train.py --desde-clickhouse        # lee el gold del warehouse
    python src/train.py --sin-minio               # no sube el artefacto al lago

Códigos de salida:
    0  los dos modelos superaron --minimo-r2 en el régimen conocido
    1  faltaba el gold, o algún modelo quedó por debajo de la compuerta
"""

import argparse
import datetime as dt
import json
import logging
import os
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.model_selection import GroupKFold, RandomizedSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

log = logging.getLogger("train")

VERSION_ARTEFACTO = 1
OPERACIONES = {"arriendo": "precio_arriendo", "venta": "precio_venta"}

# Features del INMUEBLE. Las derivadas (log_*) se calculan igual acá y en predict.py.
# `area_privada` no entra: el sitio nunca la llena (0 % de cobertura) y la ablación del
# notebook 04 la midió en +0,000. Si algún día aparece, se vuelve a medir antes de sumarla.
NUMERICAS = [
    "log_area", "habitaciones", "banos", "parqueaderos", "estrato",
    "antiguedad_ordinal", "piso", "log_administracion", "lat", "lon", "distancia_centro_km",
]
BOOLEANAS = [
    "es_nuevo", "es_proyecto", "ubicacion_aproximada",
    "habitaciones_es_tope", "banos_es_tope", "parqueaderos_es_tope",
]
# Las mismas banderas que define transform.COMODIDADES (tests/test_consistencia.py lo
# comprueba). Entran todas; la ablación del notebook 04 decide el bloque completo.
COMODIDADES = [
    "tiene_ascensor", "tiene_piscina", "tiene_gimnasio", "tiene_conjunto_cerrado",
    "tiene_vigilancia", "tiene_cctv", "tiene_citofono", "tiene_salon_comunal",
    "tiene_zonas_verdes", "tiene_zona_ninos", "tiene_bbq", "tiene_canchas",
    "tiene_sauna_turco", "tiene_jacuzzi", "tiene_parqueadero_visitantes",
    "tiene_parqueadero_cubierto", "tiene_planta_electrica",
    "tiene_balcon", "tiene_terraza", "tiene_chimenea", "tiene_deposito", "tiene_estudio",
    "tiene_cocina_integral", "tiene_cuarto_servicio", "tiene_bano_servicio", "tiene_jardin",
    "tiene_vista_exterior", "tiene_vista_panoramica", "tiene_aire_acondicionado",
    "tiene_calefaccion", "tiene_walking_closet", "esta_amoblado", "es_monoambiente",
    "acepta_mascotas",
    "es_zona_rural", "cerca_transporte", "cerca_colegios", "cerca_parques",
    "cerca_supermercados", "cerca_centros_comerciales",
]
CATEGORICAS = ["tipo_inmueble", "ciudad_clave"]
FEATURES = CATEGORICAS + NUMERICAS + BOOLEANAS + COMODIDADES

# Describen la publicación, no el inmueble. Quedan fuera a propósito.
EXCLUIDAS = ["n_fotos", "tiene_video", "destacado", "inmobiliaria_id", "descripcion"]

# HistGradientBoosting admite hasta 255 categorías por feature; la cola de ciudades con
# pocos anuncios se agrupa en una sola categoría "infrecuente".
MAX_CATEGORIAS = 200
CUANTILES = {"p50": None, "p10": 0.1, "p90": 0.9}
FOLDS = 5
# Los primeros folds ajustan el factor del intervalo; los restantes lo evalúan.
FOLDS_CALIBRACION = 3

PARAMETROS_DEFECTO = {
    "learning_rate": 0.06, "max_leaf_nodes": 63, "min_samples_leaf": 20,
    "l2_regularization": 0.5, "max_iter": 500,
}
ESPACIO_BUSQUEDA = {
    "modelo__learning_rate": [0.03, 0.05, 0.08],
    "modelo__max_leaf_nodes": [31, 63, 127],
    "modelo__min_samples_leaf": [10, 20, 40],
    "modelo__l2_regularization": [0.0, 0.5, 2.0],
    "modelo__max_iter": [300, 500, 800],
}


# --------------------------------------------------------------------------------------
# 1. Datos
# --------------------------------------------------------------------------------------

def cargar_gold(args):
    if args.desde_clickhouse:
        import clickhouse_connect
        cliente = clickhouse_connect.get_client(
            host=os.environ.get("CLICKHOUSE_HOST", "localhost"),
            port=int(os.environ.get("CLICKHOUSE_PORT", "8123")),
            username=os.environ.get("CLICKHOUSE_USER", "valora"),
            password=os.environ.get("CLICKHOUSE_PASSWORD", "valora123"))
        base = os.environ.get("CLICKHOUSE_DB", "valora")
        # La última partición cargada: el warehouse guarda una por corrida.
        fecha = cliente.command(f"SELECT max(fecha_carga) FROM {base}.anuncios")
        df = cliente.query_df(f"SELECT * FROM {base}.anuncios WHERE fecha_carga = '{fecha}'")
        log.info("Gold desde ClickHouse: partición %s, %s filas", fecha, f"{len(df):,}")
        return df
    ruta = Path(args.datos_dir) / "processed" / "anuncios_enriquecido.parquet"
    if not ruta.exists():
        raise FileNotFoundError(f"No existe {ruta}: hay que correr el enrich primero")
    df = pd.read_parquet(ruta)
    log.info("Gold desde %s: %s filas x %d columnas", ruta, f"{len(df):,}", df.shape[1])
    return df


def derivar(df):
    """Las features derivadas. predict.py hace exactamente lo mismo con una fila."""
    df = df.copy()
    df["log_area"] = np.log(pd.to_numeric(df["area_m2"], errors="coerce").astype("float64"))
    df["log_administracion"] = np.log(
        pd.to_numeric(df["administracion"], errors="coerce").astype("float64"))
    return df


def matriz(df):
    """De las columnas del gold a la matriz de entrada: categóricas como texto, todo lo
    demás como float con NaN donde no hay dato (HistGradientBoosting los maneja)."""
    X = pd.DataFrame(index=df.index)
    for columna in CATEGORICAS:
        X[columna] = df[columna].astype("string").fillna("desconocido").astype(str)
    for columna in NUMERICAS + BOOLEANAS + COMODIDADES:
        if columna in df.columns:
            X[columna] = pd.to_numeric(df[columna], errors="coerce").astype("float64")
        else:
            X[columna] = np.nan
    return X


def preparar(df, operacion):
    """Filas con precio para la operación, su target en log y los grupos de los dos
    regímenes. Devuelve (sub, X, y, grupos)."""
    columna = OPERACIONES[operacion]
    sub = df[df[columna].notna() & df["area_m2"].notna()].copy()
    sub = derivar(sub).reset_index(drop=True)
    y = np.log(sub[columna].astype("float64").to_numpy())
    # El sector nulo se vuelve un string real ANTES de concatenar: con NA, la llave entera
    # queda NA y factorize manda todas las filas sin sector de todas las ciudades al mismo
    # grupo -1, que caería entero en un solo fold.
    llave_sector = (sub["ciudad_clave"].astype("string").fillna("sin_ciudad") + "|"
                    + sub["sector_clave"].astype("string").fillna("sin_sector"))
    grupos = {
        "conocido": pd.factorize(sub["grupo_near_duplicado"])[0],
        "frio": pd.factorize(llave_sector)[0],
    }
    return sub, matriz(sub), y, grupos


# --------------------------------------------------------------------------------------
# 2. Modelo
# --------------------------------------------------------------------------------------

def construir(parametros, cuantil=None):
    """Pipeline autocontenido: codificación de categóricas + boosting. Va entero al
    artefacto, así predict.py no tiene que replicar ninguna transformación."""
    codificador = ColumnTransformer(
        [("categoricas", OrdinalEncoder(
            handle_unknown="use_encoded_value", unknown_value=-1,
            encoded_missing_value=-1, max_categories=MAX_CATEGORIAS, dtype=np.float64),
          CATEGORICAS)],
        remainder="passthrough", verbose_feature_names_out=False)
    extra = {} if cuantil is None else {"loss": "quantile", "quantile": cuantil}
    modelo = HistGradientBoostingRegressor(
        categorical_features=list(range(len(CATEGORICAS))), random_state=0,
        early_stopping=False, **parametros, **extra)
    return Pipeline([("codificador", codificador), ("modelo", modelo)])


def buscar_parametros(X, y, grupos, n_iter, semilla=0):
    """Búsqueda aleatoria chica con split agrupado por near-duplicado."""
    busqueda = RandomizedSearchCV(
        construir(PARAMETROS_DEFECTO), ESPACIO_BUSQUEDA, n_iter=n_iter,
        cv=GroupKFold(3), scoring="neg_mean_absolute_error", random_state=semilla,
        n_jobs=1, refit=False, verbose=0)
    busqueda.fit(X, y, groups=grupos)
    mejores = {k.replace("modelo__", ""): v for k, v in busqueda.best_params_.items()}
    log.info("  mejores parámetros: %s (MAE log %.4f)", mejores, -busqueda.best_score_)
    return mejores


# --------------------------------------------------------------------------------------
# 3. Evaluación
# --------------------------------------------------------------------------------------

def metricas(y, pred, p10=None, p90=None):
    error = pred - y
    relativo = np.abs(np.expm1(error))
    resultado = {
        "n": int(len(y)),
        "R2": round(float(1 - (error ** 2).sum() / ((y - y.mean()) ** 2).sum()), 4),
        "MAE_log": round(float(np.abs(error).mean()), 4),
        "MAPE_%": round(float(relativo.mean() * 100), 2),
        "MdAPE_%": round(float(np.median(relativo) * 100), 2),
        "dentro_10_%": round(float((relativo <= 0.10).mean() * 100), 2),
        "dentro_20_%": round(float((relativo <= 0.20).mean() * 100), 2),
    }
    if p10 is not None:
        resultado["cobertura_p10_p90_%"] = round(float(((y >= p10) & (y <= p90)).mean() * 100), 2)
        resultado["ancho_relativo_mediano_%"] = round(
            float(np.median(np.exp(p90 - p10) - 1) * 100), 2)
    return resultado


def evaluar_oof(X, y, grupos, parametros, con_cuantiles):
    """Predicción out-of-fold con GroupKFold. Devuelve {p50, p10, p90, fold} (los cuantiles
    sólo si con_cuantiles) más las importancias por permutación del primer fold."""
    prediccion = {nombre: np.full(len(y), np.nan) for nombre in CUANTILES}
    prediccion["fold"] = np.full(len(y), -1)
    importancias = None
    for numero, (train, test) in enumerate(GroupKFold(FOLDS).split(X, y, grupos)):
        prediccion["fold"][test] = numero
        for nombre, cuantil in CUANTILES.items():
            if cuantil is not None and not con_cuantiles:
                continue
            modelo = construir(parametros, cuantil).fit(X.iloc[train], y[train])
            prediccion[nombre][test] = modelo.predict(X.iloc[test])
            if nombre == "p50" and numero == 0:
                resultado = permutation_importance(
                    modelo, X.iloc[test], y[test], n_repeats=3, random_state=0,
                    scoring="neg_mean_absolute_error")
                importancias = dict(sorted(
                    zip(X.columns, resultado.importances_mean.round(5)),
                    key=lambda par: -par[1]))
        log.info("    fold %d/%d listo", numero + 1, FOLDS)
    return prediccion, importancias


def calibrar_intervalo(y, p50, p10, p90, objetivo=0.80):
    """Factor k que ensancha [p10, p90] alrededor de p50 hasta que el 80 % de las filas
    out-of-fold caen dentro. Los cuantiles del boosting salen angostos (cubren ~71 %):
    es una calibración conformal simple, medida en datos que el modelo no vio."""
    for k in np.arange(1.0, 3.001, 0.05):
        bajo, alto = p50 - k * (p50 - p10), p50 + k * (p90 - p50)
        if ((y >= bajo) & (y <= alto)).mean() >= objetivo:
            return round(float(k), 2)
    return 3.0


def desglose(sub, y, pred, columna, minimo=200):
    """Métricas por grupo (ciudad, tipo) para ver dónde el modelo flaquea."""
    filas = {}
    for valor, indices in sub.groupby(columna).indices.items():
        if len(indices) >= minimo:
            filas[str(valor)] = metricas(y[indices], pred[indices])
    return dict(sorted(filas.items(), key=lambda par: -par[1]["n"]))


# --------------------------------------------------------------------------------------
# 4. Lo que el artefacto necesita para predecir un inmueble nuevo
# --------------------------------------------------------------------------------------

def gazetteer_interno(df):
    """Por (ciudad, sector): mediana de coordenada y estrato y cuántos anuncios lo
    respaldan. predict.py lo usa para resolver un barrio escrito a mano."""
    con_ubicacion = df[df["lat"].notna() & df["sector_clave"].notna()]
    sectores = (con_ubicacion.groupby(["ciudad_clave", "sector_clave"])
                .agg(lat=("lat", "median"), lon=("lon", "median"),
                     estrato=("estrato", "median"), n=("lat", "size"))
                .reset_index())
    sectores["lat"] = sectores["lat"].astype("float64")
    sectores["lon"] = sectores["lon"].astype("float64")
    sectores["estrato"] = sectores["estrato"].astype("float64").round()
    return sectores


def centros_ciudad(df):
    con_ubicacion = df[df["lat"].notna()]
    centros = (con_ubicacion.groupby("ciudad_clave")
               .agg(lat=("lat", "median"), lon=("lon", "median"),
                    estrato=("estrato", "median"), n=("lat", "size"))
               .reset_index())
    for columna in ("lat", "lon", "estrato"):
        centros[columna] = centros[columna].astype("float64")
    nombres = df.groupby("ciudad_clave")["ciudad"].agg(lambda s: s.mode().iloc[0])
    centros["ciudad"] = centros["ciudad_clave"].map(nombres)
    return centros


# --------------------------------------------------------------------------------------
# 5. Salida
# --------------------------------------------------------------------------------------

def subir_a_minio(ruta_artefacto, ruta_resumen, fecha):
    import boto3
    cliente = boto3.client(
        "s3", endpoint_url=os.environ.get("MINIO_ENDPOINT", "http://localhost:9000"),
        aws_access_key_id=os.environ.get("MINIO_ACCESS_KEY", "valora"),
        aws_secret_access_key=os.environ.get("MINIO_SECRET_KEY", "valora123"),
        region_name="us-east-1")
    bucket = os.environ.get("MINIO_BUCKET", "valora")
    for ruta in (ruta_artefacto, ruta_resumen):
        llave = f"models/fecha={fecha}/{ruta.name}"
        cliente.upload_file(str(ruta), bucket, llave)
        log.info("  s3://%s/%s (%.1f MB)", bucket, llave, ruta.stat().st_size / 2 ** 20)


def parse_args():
    parser = argparse.ArgumentParser(description="Entrena los modelos de precio de arriendo y venta")
    parser.add_argument("--datos-dir", default="data", help="Raíz de data/ (lee processed/)")
    parser.add_argument("--modelos-dir", default="models", help="Dónde dejar el artefacto")
    parser.add_argument("--desde-clickhouse", action="store_true",
                        help="Leer el gold desde el warehouse en vez del parquet")
    parser.add_argument("--sin-busqueda", action="store_true",
                        help="Usar los hiperparámetros por defecto, sin búsqueda")
    parser.add_argument("--candidatos", type=int, default=12,
                        help="Combinaciones a probar en la búsqueda de hiperparámetros")
    parser.add_argument("--minimo-r2", type=float, default=0.85,
                        help="R² mínimo en el régimen conocido para salir con 0")
    parser.add_argument("--sin-minio", action="store_true",
                        help="No subir el artefacto al lago")
    parser.add_argument("--fecha", default=dt.date.today().isoformat(),
                        help="Fecha del artefacto en el lago (YYYY-MM-DD)")
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
    try:
        df = cargar_gold(args)
    except FileNotFoundError as error:
        log.error("%s", error)
        return 1

    faltantes = [c for c in ["area_m2", "grupo_near_duplicado", "lat", "estrato"] if c not in df.columns]
    if faltantes:
        log.error("El gold no trae %s: hay que correr transform y enrich con el detalle", faltantes)
        return 1

    artefacto = {
        "version": VERSION_ARTEFACTO, "fecha": args.fecha,
        "sklearn": sklearn.__version__, "features": FEATURES, "categoricas": CATEGORICAS,
        "excluidas": EXCLUIDAS, "modelos": {}, "parametros": {}, "metricas": {},
        "importancias": {}, "ajuste_intervalo": {},
        "sectores": gazetteer_interno(df), "ciudades": centros_ciudad(df),
    }
    resumen = {"fecha": args.fecha, "filas_gold": int(len(df)), "features": FEATURES,
               "operaciones": {}}
    oof = []
    comienzo = time.monotonic()

    for operacion in OPERACIONES:
        sub, X, y, grupos = preparar(df, operacion)
        log.info("=== %s: %s filas, %d features ===", operacion.upper(), f"{len(y):,}", X.shape[1])

        parametros = dict(PARAMETROS_DEFECTO)
        if not args.sin_busqueda:
            log.info("  buscando hiperparámetros (%d candidatos, GroupKFold 3):", args.candidatos)
            parametros = buscar_parametros(X, y, grupos["conocido"], args.candidatos)
        artefacto["parametros"][operacion] = parametros

        evaluacion = {}
        for regimen in ("conocido", "frio"):
            log.info("  evaluando out-of-fold, régimen %s:", regimen)
            prediccion, importancias = evaluar_oof(
                X, y, grupos[regimen], parametros, con_cuantiles=(regimen == "conocido"))
            evaluacion[regimen] = metricas(y, prediccion["p50"],
                                           prediccion["p10"] if regimen == "conocido" else None,
                                           prediccion["p90"] if regimen == "conocido" else None)
            log.info("    %s", json.dumps(evaluacion[regimen]))
            if regimen == "conocido":
                # El factor se ajusta con los folds 0-2 y la cobertura se reporta sobre
                # los folds 3-4, que la calibración nunca vio: si se midiera sobre los
                # mismos datos daría 80 % por construcción y no diría nada.
                ajuste = prediccion["fold"] < FOLDS_CALIBRACION
                k = calibrar_intervalo(y[ajuste], prediccion["p50"][ajuste],
                                       prediccion["p10"][ajuste], prediccion["p90"][ajuste])
                bajo = prediccion["p50"] - k * (prediccion["p50"] - prediccion["p10"])
                alto = prediccion["p50"] + k * (prediccion["p90"] - prediccion["p50"])
                prueba = ~ajuste
                evaluacion[regimen]["factor_intervalo"] = k
                evaluacion[regimen]["cobertura_calibrada_%"] = round(
                    float(((y >= bajo) & (y <= alto))[prueba].mean() * 100), 2)
                evaluacion[regimen]["ancho_calibrado_mediano_%"] = round(
                    float(np.median(np.exp(alto - bajo)[prueba] - 1) * 100), 2)
                log.info("    intervalo calibrado con k=%.2f (folds 0-%d): cobertura %.1f %% "
                         "en los folds que no vio", k, FOLDS_CALIBRACION - 1,
                         evaluacion[regimen]["cobertura_calibrada_%"])
                artefacto["ajuste_intervalo"][operacion] = k
                artefacto["importancias"][operacion] = importancias
                evaluacion["por_ciudad"] = desglose(sub, y, prediccion["p50"], "ciudad_clave")
                evaluacion["por_tipo"] = desglose(sub, y, prediccion["p50"], "tipo_inmueble")
            oof.append(pd.DataFrame({
                "id_inmueble": sub["id_inmueble"], "operacion": operacion, "regimen": regimen,
                "ciudad_clave": sub["ciudad_clave"], "tipo_inmueble": sub["tipo_inmueble"],
                "y_log": y, "pred_log": prediccion["p50"],
                "p10_log": prediccion["p10"], "p90_log": prediccion["p90"],
                "fold": prediccion["fold"],
            }))

        log.info("  entrenando los tres modelos finales sobre todas las filas:")
        artefacto["modelos"][operacion] = {
            nombre: construir(parametros, cuantil).fit(X, y)
            for nombre, cuantil in CUANTILES.items()}
        # Métricas EN ENTRENAMIENTO del modelo final: las mismas filas con que se ajustó.
        # No miden capacidad de generalizar (para eso están las out-of-fold); miden la
        # brecha train/test, que es el termómetro del sobreajuste.
        en_train = {nombre: m.predict(X) for nombre, m in artefacto["modelos"][operacion].items()}
        evaluacion["entrenamiento"] = metricas(y, en_train["p50"], en_train["p10"], en_train["p90"])
        evaluacion["brecha_train_oof"] = {
            "R2": round(evaluacion["entrenamiento"]["R2"] - evaluacion["conocido"]["R2"], 4),
            "MAE_log": round(evaluacion["conocido"]["MAE_log"] - evaluacion["entrenamiento"]["MAE_log"], 4),
            "MdAPE_%": round(evaluacion["conocido"]["MdAPE_%"] - evaluacion["entrenamiento"]["MdAPE_%"], 2),
        }
        log.info("    en entrenamiento: %s", json.dumps(evaluacion["entrenamiento"]))
        log.info("    brecha train vs. out-of-fold: %s", json.dumps(evaluacion["brecha_train_oof"]))
        artefacto["metricas"][operacion] = evaluacion
        resumen["operaciones"][operacion] = {
            "filas": int(len(y)), "parametros": parametros, **evaluacion,
            "importancias": importancias}

    resumen["segundos"] = round(time.monotonic() - comienzo, 1)

    modelos_dir = Path(args.modelos_dir)
    modelos_dir.mkdir(parents=True, exist_ok=True)
    ruta_artefacto = modelos_dir / "valora_modelo.joblib"
    ruta_resumen = modelos_dir / "entrenamiento_resumen.json"
    joblib.dump(artefacto, ruta_artefacto, compress=3)
    ruta_resumen.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.concat(oof, ignore_index=True).to_parquet(modelos_dir / "predicciones_oof.parquet", index=False)
    log.info("Artefacto: %s (%.1f MB) | resumen: %s | OOF: predicciones_oof.parquet",
             ruta_artefacto, ruta_artefacto.stat().st_size / 2 ** 20, ruta_resumen.name)

    if not args.sin_minio:
        log.info("Subiendo el artefacto al lago:")
        try:
            subir_a_minio(ruta_artefacto, ruta_resumen, args.fecha)
        except Exception as error:   # noqa: BLE001 - boto3 tira de todo
            log.error("No se pudo subir a MinIO: %s (usá --sin-minio si no hay lakehouse)", error)
            return 1

    log.info("=== COMPUERTA (R² en régimen conocido, mínimo %.2f) ===", args.minimo_r2)
    pasa = True
    for operacion, evaluacion in artefacto["metricas"].items():
        r2 = evaluacion["conocido"]["R2"]
        frio = evaluacion["frio"]["R2"]
        veredicto = "PASA" if r2 >= args.minimo_r2 else "NO PASA"
        pasa &= r2 >= args.minimo_r2
        log.info("  %-9s R2 train = %.3f | conocido = %.3f | frío = %.3f | MdAPE = %.1f %% -> %s",
                 operacion, evaluacion["entrenamiento"]["R2"], r2, frio,
                 evaluacion["conocido"]["MdAPE_%"], veredicto)
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
