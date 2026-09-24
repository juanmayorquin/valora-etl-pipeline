import React from 'react';
import { HistogramaM2 } from '../../../types/valuation';
import { formatCompactCOP } from '../../../shared/utils/formatters';

interface PriceHistogramProps {
  histograma: HistogramaM2 | null;
  unidad?: string;
}

export const PriceHistogram: React.FC<PriceHistogramProps> = ({
  histograma,
  unidad = '/m²',
}) => {
  if (!histograma || !histograma.conteos || histograma.conteos.length === 0) {
    return (
      <div className="p-4 text-center text-xs text-ink-muted bg-canvas rounded-xl border border-ink-border">
        No hay suficiente densidad de anuncios para construir el histograma de distribución.
      </div>
    );
  }

  const { limites, conteos, barra_avaluo } = histograma;
  const maxConteo = Math.max(...conteos, 1);

  return (
    <div className="space-y-3 pt-2">
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold text-ink-primary">
          Distribución de Precios por m² en la Zona
        </span>
        <span className="text-[11px] text-brand-700 font-bold flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-xs bg-brand-500 ring-2 ring-brand-300 inline-block"></span>
          Tu inmueble
        </span>
      </div>

      {/* Histogram bars */}
      <div className="h-28 flex items-end gap-1 sm:gap-1.5 pt-4 px-2 bg-canvas rounded-xl border border-ink-border">
        {conteos.map((count, idx) => {
          const isUserBar = barra_avaluo === idx;
          const heightPct = Math.max(Math.round((count / maxConteo) * 100), 6);
          const minLim = limites[idx];
          const maxLim = limites[idx + 1];

          return (
            <div
              key={idx}
              className="flex-1 flex flex-col items-center h-full justify-end group relative"
            >
              {/* Tooltip on hover */}
              <div className="absolute -top-10 hidden group-hover:flex flex-col items-center z-20 pointer-events-none">
                <div className="bg-ink-primary text-white text-[10px] px-2 py-1 rounded shadow-md whitespace-nowrap">
                  {count} anuncios · {formatCompactCOP(minLim)} - {formatCompactCOP(maxLim)}
                </div>
                <div className="w-1.5 h-1.5 bg-ink-primary rotate-45 -mt-0.5"></div>
              </div>

              {/* Bar */}
              <div
                style={{ height: `${heightPct}%` }}
                className={`w-full rounded-t-md transition-all ${
                  isUserBar
                    ? 'bg-brand-500 ring-2 ring-brand-300 shadow-xs'
                    : 'bg-slate-300 group-hover:bg-slate-400'
                }`}
              ></div>

              {/* User indicator dot */}
              {isUserBar && (
                <div className="w-1.5 h-1.5 rounded-full bg-brand-600 mt-1"></div>
              )}
            </div>
          );
        })}
      </div>

      <div className="flex items-center justify-between text-[11px] text-ink-muted px-1">
        <span>Menor valor: {formatCompactCOP(limites[0])}{unidad}</span>
        <span>Mayor valor: {formatCompactCOP(limites[limites.length - 1])}{unidad}</span>
      </div>
    </div>
  );
};
