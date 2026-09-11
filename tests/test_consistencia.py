"""Las tres copias de la lista de comodidades (transform, load, train) tienen que ser la
misma: cada script es standalone por convención, así que la única defensa es un test."""
import load
import train
import transform


def test_comodidades_iguales_en_las_tres_etapas():
    assert list(transform.COMODIDADES) == load.COMODIDADES
    assert list(transform.COMODIDADES) == train.COMODIDADES


def test_toda_columna_del_warehouse_sale_del_transform_o_del_enrich():
    del_transform = set(transform.COLUMNAS_CONTRATO) | set(transform.COLUMNAS_DETALLE) | {
        "con_detalle", "tipo_no_residencial", "es_dual", "operacion", "titulo_sin_parsear",
        "precio_venta", "precio_arriendo", "precio_desde_detalle", "precio_discrepante",
        "precio_relleno", "estrato_invalido", "coordenada_invalida", "area_privada_invalida",
        "administracion_invalida", "antiguedad_ordinal", "es_nuevo", "ciudad_clave",
        "sector_clave", "precio_m2", "grupo_near_duplicado", "es_near_duplicado",
        "n_motivos_rechazo", "motivo_rechazo",
    } | set(transform.COMODIDADES) | {f"{c}_es_tope" for c in transform.TOPES}
    del_enrich = {"origen_coordenada", "origen_estrato", "coordenada_lejana",
                  "distancia_centro_km", "lat_barrio", "lon_barrio", "barrio_osm", "match_barrio",
                  "match_verificado", "estrato_modal", "estrato_promedio", "estrato_dispersion",
                  "n_manzanas_estrato"}
    declaradas = {nombre for nombre, _, _ in load.ESQUEMA_GOLD}
    assert declaradas <= del_transform | del_enrich, declaradas - (del_transform | del_enrich)
