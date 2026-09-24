import React, { useState } from 'react';
import { ValuationResponse, OperationType, UserObjective } from '../../../types/valuation';
import { formatCOP, formatCompactCOP } from '../../../shared/utils/formatters';
import { PriceHistogram } from './PriceHistogram';
import {
  BarChart3,
  AlertCircle,
} from 'lucide-react';

interface ZoneComparisonViewProps {
  result: ValuationResponse;
  objective?: UserObjective;
}

export const ZoneComparisonView: React.FC<ZoneComparisonViewProps> = ({
  result,
  objective = 'ambas',
}) => {
  const initialOp: OperationType = objective === 'arrendar' ? 'arriendo' : 'venta';
  const [operacion, setOperacion] = useState<OperationType>(initialOp);

  const { zona } = result;
  const datosZona = operacion === 'venta' ? zona.venta : zona.arriendo;
  const radio = zona.radio_km;

  // Si no hay datos suficientes de la zona
  if (!datosZona || datosZona.n_zona === 0) {
    return (
      <div className="rounded-2xl bg-surface border border-ink-border p-6 shadow-card space-y-4">
        <div className="flex items-center gap-2 text-warning-600">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <h3 className="text-base font-bold text-ink-primary">Comparación de Zona Limitada</h3>
        </div>
        <p className="text-xs text-ink-secondary leading-relaxed">
          No se encontraron suficientes anuncios inmobiliarios en el radio inmediato de{' '}
          {radio ? `${radio} km` : 'este sector'} para generar una curva de distribución representativa. El avalúo se calculó a partir de los patrones consolidados de la ciudad.
        </p>
      </div>
    );
  }

  const {
    n_zona,
    n_parecidos,
    mediana_m2,
    p25_m2,
    p75_m2,
    percentil_avaluo,
    histograma_m2,
  } = datosZona;

  const getPercentileExplanation = (pct: number | null) => {
    if (pct === null) return 'No hay datos suficientes para calcular la posición relativa.';
    if (pct < 50) {
      return 'La estimación está por debajo de la mediana de propiedades similares de la zona.';
    }
    if (pct <= 75) {
      return 'La estimación está dentro del rango habitual de la zona.';
    }
    return 'La estimación está por encima de la mediana de propiedades similares de la zona.';
  };

  const explicacion = getPercentileExplanation(percentil_avaluo);

  return (
    <div className="rounded-2xl bg-surface border border-ink-border p-6 sm:p-7 shadow-card space-y-6">
      {/* Encabezado con selector Venta / Arriendo */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-ink-border/70">
        <div>
          <span className="text-[12px] font-bold text-brand-600 uppercase tracking-wider flex items-center gap-1.5">
            <BarChart3 className="w-4 h-4" />
            Evidencia de Mercado Local
          </span>
          <h3 className="text-[22px] sm:text-[24px] lg:text-[26px] font-bold text-ink-primary font-display mt-0.5">
            Comparación con el Entorno ({radio ? `Radio ${radio} km` : 'Sector'})
          </h3>
        </div>

        <div className="flex items-center gap-1.5 p-1 bg-canvas rounded-xl border border-ink-border self-start sm:self-auto">
          <button
            type="button"
            onClick={() => setOperacion('venta')}
            className={`min-h-[42px] px-4 py-2 rounded-lg text-[15px] font-bold transition-all ${
              operacion === 'venta'
                ? 'bg-brand-500 text-white shadow-xs'
                : 'text-ink-secondary hover:text-ink-primary'
            }`}
          >
            Mercado Venta
          </button>
          <button
            type="button"
            onClick={() => setOperacion('arriendo')}
            className={`min-h-[42px] px-4 py-2 rounded-lg text-[15px] font-bold transition-all ${
              operacion === 'arriendo'
                ? 'bg-brand-500 text-white shadow-xs'
                : 'text-ink-secondary hover:text-ink-primary'
            }`}
          >
            Mercado Arriendo
          </button>
        </div>
      </div>

      {/* Tarjeta de diagnóstico automatizado según percentil */}
      <div className="p-4 sm:p-5 rounded-xl bg-canvas border border-ink-border flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="space-y-1">
          <span className="text-[12px] font-bold uppercase tracking-wider text-ink-muted">
            Diagnóstico frente al Mercado
          </span>
          <p className="text-[15px] sm:text-[16px] font-semibold text-ink-primary leading-snug">
            {explicacion}
          </p>
        </div>

        {percentil_avaluo !== null && (
          <div className="flex items-center gap-2.5 shrink-0">
            <span className="text-[14px] text-ink-secondary">Percentil estimado:</span>
            <span className="text-[16px] font-bold px-3 py-1 rounded-lg bg-brand-100 text-brand-800 border border-brand-200 tabular-nums">
              P{percentil_avaluo}
            </span>
          </div>
        )}
      </div>

      {/* Grid de Métricas de la Zona */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        {/* Mediana m2 */}
        <div className="p-3.5 sm:p-4 rounded-xl bg-canvas border border-ink-border space-y-1">
          <span className="text-[12px] font-bold text-ink-muted uppercase block">
            Mediana Zona / m²
          </span>
          <div className="text-[18px] sm:text-[20px] font-bold text-ink-primary tabular-nums">
            {formatCOP(mediana_m2)}
          </div>
          <span className="text-[13px] text-ink-secondary block">De ofertas en el radio</span>
        </div>

        {/* Rango típico p25 - p75 */}
        <div className="p-3.5 sm:p-4 rounded-xl bg-canvas border border-ink-border space-y-1">
          <span className="text-[12px] font-bold text-ink-muted uppercase block">
            Rango Típico m² (p25 - p75)
          </span>
          <div className="text-[15px] sm:text-[16px] font-bold text-brand-700 tabular-nums">
            {formatCompactCOP(p25_m2)} — {formatCompactCOP(p75_m2)}
          </div>
          <span className="text-[13px] text-ink-secondary block">50% central de la zona</span>
        </div>

        {/* Anuncios en la zona */}
        <div className="p-3.5 sm:p-4 rounded-xl bg-canvas border border-ink-border space-y-1">
          <span className="text-[12px] font-bold text-ink-muted uppercase block">
            Anuncios en Radio
          </span>
          <div className="text-[18px] sm:text-[20px] font-bold text-ink-primary tabular-nums">
            {n_zona.toLocaleString()}
          </div>
          <span className="text-[13px] text-ink-secondary block">En radio de {radio || 1.5} km</span>
        </div>

        {/* Inmuebles parecidos */}
        <div className="p-3.5 sm:p-4 rounded-xl bg-canvas border border-ink-border space-y-1">
          <span className="text-[12px] font-bold text-ink-muted uppercase block">
            Área Similar (±35%)
          </span>
          <div className="text-[18px] sm:text-[20px] font-bold text-chart-600 tabular-nums">
            {n_parecidos.toLocaleString()}
          </div>
          <span className="text-[13px] text-ink-secondary block">Metraje comparable</span>
        </div>
      </div>

      {/* Histograma de Precios */}
      <PriceHistogram histograma={histograma_m2} />
    </div>
  );
};
