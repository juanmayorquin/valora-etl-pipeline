export type PropertyType = 'apartamento' | 'casa' | 'apartaestudio';
export type OperationType = 'venta' | 'arriendo';

export interface CiudadCatalogItem {
  ciudad: string;
  clave: string;
  anuncios: number;
}

export interface SectorCatalogItem {
  sector: string;
  clave: string;
  anuncios: number;
  estrato: number | null;
}

export interface ValuationRequest {
  tipo: PropertyType;
  ciudad: string;
  sector: string;
  area_m2: number;
  habitaciones: number;
  banos: number;
  parqueaderos: number;
  estrato?: number | null;
  antiguedad?: string | null;
  piso?: number | null;
  administracion?: number | null;
  comodidades: string[];
}

export interface ComparableItem {
  precio: number;
  area_m2: number;
  precio_m2: number;
  estrato?: number | null;
  habitaciones?: number | null;
  banos?: number | null;
  parqueaderos?: number | null;
  antiguedad?: string | null;
  sector?: string | null;
  distancia_km?: number | null;
  lat?: number | null;
  lon?: number | null;
  url: string;
}

export interface HistogramaM2 {
  limites: number[];
  conteos: number[];
  barra_avaluo: number;
}

export interface OperacionZona {
  n_zona: number;
  n_parecidos: number;
  mediana_m2: number;
  p25_m2: number;
  p75_m2: number;
  mediana_precio_parecidos: number;
  percentil_avaluo: number;
  histograma_m2: HistogramaM2;
  comparables: ComparableItem[];
}

export interface OperacionEstimado {
  estimado: number;
  rango: [number, number];
  precio_m2: number;
}

export interface ContextoEstimado {
  ciudad: string;
  sector: string;
  sector_conocido: boolean;
  n_comparables_sector: number;
  origen_coordenada: string;
  origen_estrato: string;
  estrato_usado: number;
  coordenada_usada: [number, number];
  distancia_centro_km: number;
}

export interface ValuationResponse {
  avaluo: {
    contexto: ContextoEstimado;
    arriendo: OperacionEstimado;
    venta: OperacionEstimado;
    "rentabilidad_bruta_anual_%": number;
  };
  zona: {
    radio_km: number;
    centro: { lat: number; lon: number };
    venta?: OperacionZona;
    arriendo?: OperacionZona;
  };
}
