import { ValuationResponse, ConfidenceDetails } from '../../types/valuation';

export const formatCOP = (val: number | null | undefined): string => {
  if (val === null || val === undefined || isNaN(val)) return '$ 0';
  return new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    maximumFractionDigits: 0,
  }).format(val);
};

export const formatCompactCOP = (val: number | null | undefined): string => {
  if (val === null || val === undefined || isNaN(val)) return '$ 0';
  if (val >= 1_000_000_000) {
    return `$ ${(val / 1_000_000_000).toFixed(2).replace('.', ',')} mil millones`;
  }
  if (val >= 1_000_000) {
    return `$ ${(val / 1_000_000).toFixed(1).replace('.', ',')} M`;
  }
  return formatCOP(val);
};

export const formatM2 = (val: number | null | undefined): string => {
  if (val === null || val === undefined || isNaN(val)) return '0 m²';
  return `${Math.round(val).toLocaleString('es-CO')} m²`;
};

export const formatPercent = (val: number | null | undefined): string => {
  if (val === null || val === undefined || isNaN(val)) return '0 %';
  return `${val.toFixed(1).replace('.', ',')} %`;
};

export const calculateConfidence = (response: ValuationResponse): ConfidenceDetails => {
  const { avaluo, zona } = response;
  const { contexto } = avaluo;

  // Analizar respaldo de datos reales del backend
  const nSector = contexto.n_comparables_sector || 0;
  const sectorConocido = contexto.sector_conocido;
  const radio = zona.radio_km;
  
  // Total comparables en la zona (sumando venta y arriendo)
  const nParecidosVenta = zona.venta?.n_parecidos || 0;
  const nParecidosArriendo = zona.arriendo?.n_parecidos || 0;
  const totalParecidos = nParecidosVenta + nParecidosArriendo;

  // Dispersión del rango en venta: (alto - bajo) / estimado
  const rangoVenta = avaluo.venta.rango;
  const amplitudRangoPct = Math.round(
    ((rangoVenta[1] - rangoVenta[0]) / (avaluo.venta.estimado || 1)) * 100
  );

  const reasons: string[] = [];

  // Clasificación determinística rigurosa
  let score = 0;

  if (sectorConocido) {
    score += 35;
    reasons.push(`El sector "${contexto.sector || 'seleccionado'}" cuenta con historial activo en el modelo (${nSector} anuncios procesados).`);
  } else {
    reasons.push(`El sector es nuevo o poco frecuente; la estimación se basó en el contexto municipal de ${contexto.ciudad}.`);
  }

  if (totalParecidos >= 20) {
    score += 35;
    reasons.push(`Encontramos ${totalParecidos} inmuebles con área y características muy similares en un radio de ${radio ? radio.toFixed(1) : '1,5'} km.`);
  } else if (totalParecidos >= 8) {
    score += 20;
    reasons.push(`Se identificaron ${totalParecidos} inmuebles similares en el radio de análisis.`);
  } else {
    reasons.push(`Baja densidad de anuncios idénticos en la zona inmediata (${totalParecidos} comparables).`);
  }

  if (amplitudRangoPct <= 35) {
    score += 30;
    reasons.push(`El rango de referencia tiene baja dispersión (${amplitudRangoPct}%), lo que refleja alta consistencia en precios.`);
  } else if (amplitudRangoPct <= 55) {
    score += 15;
    reasons.push(`Dispersión moderada en la zona (${amplitudRangoPct}% entre límites p10 y p90).`);
  } else {
    reasons.push(`Alta dispersión de valores en este segmento (${amplitudRangoPct}% de amplitud de rango).`);
  }

  let level: 'alta' | 'media' | 'limitada' = 'media';
  let title = 'Confianza Media';
  let explanation = '';

  if (score >= 70) {
    level = 'alta';
    title = 'Confianza Alta';
    explanation = `Esta estimación tiene un respaldo local sólido porque encontramos ${totalParecidos} propiedades similares dentro de un radio de ${radio ? radio.toFixed(1) : '1,5'} km en ${contexto.sector || contexto.ciudad}.`;
  } else if (score >= 40) {
    level = 'media';
    title = 'Confianza Media';
    explanation = `Estimación con buen respaldo general en ${contexto.ciudad}, con ${totalParecidos} comparables cercanos.`;
  } else {
    level = 'limitada';
    title = 'Confianza Limitada';
    explanation = `Estimación orientativa. La zona presenta baja muestra directa o alta heterogeneidad en anuncios.`;
  }

  return {
    level,
    title,
    explanation,
    reasons,
    metrics: {
      comparablesDirectos: totalParecidos,
      radioAnalisisKm: radio,
      origenCoords: contexto.origen_coordenada,
      origenEstrato: contexto.origen_estrato,
      amplitudRangoPct,
    },
  };
};
