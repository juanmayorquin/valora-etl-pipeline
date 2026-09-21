import React, { useState } from 'react';
import { ValuationResponse, OperationType } from '../types/valuation';
import { BarChart3, Users, Gauge } from 'lucide-react';

interface ZoneComparisonProps {
  result: ValuationResponse;
}

const formatCOP = (val: number): string => {
  return new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    maximumFractionDigits: 0,
  }).format(val);
};

export const ZoneComparison: React.FC<ZoneComparisonProps> = ({ result }) => {
  const [opcion, setOpcion] = useState<OperationType>('venta');
  const { zona } = result;

  const datosZona = opcion === 'venta' ? zona.venta : zona.arriendo;

  if (!datosZona || datosZona.n_zona === 0) {
    return (
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 text-center text-slate-400 text-sm">
        No se encontraron suficientes anuncios comparables en la zona para graficar la distribución.
      </div>
    );
  }

  const { n_zona, n_parecidos, mediana_m2, p25_m2, p75_m2, percentil_avaluo, histograma_m2 } = datosZona;

  // Max count in histogram for scaling bars
  const maxConteo = Math.max(...histograma_m2.conteos, 1);

  return (
    <div className="p-6 rounded-2xl bg-slate-900/70 border border-slate-800 shadow-xl space-y-5">
      {/* Header & Toggle */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-emerald-400" />
            Comportamiento Frente a la Zona
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Distribución de precios por m² a menos de {zona.radio_km} km ({n_zona} anuncios en zona · {n_parecidos} de área parecida)
          </p>
        </div>

        {/* Venta / Arriendo Toggle */}
        <div className="flex p-1 rounded-xl bg-slate-950 border border-slate-800 text-xs font-semibold">
          <button
            type="button"
            onClick={() => setOpcion('venta')}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              opcion === 'venta'
                ? 'bg-emerald-500 text-slate-950 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Venta
          </button>
          <button
            type="button"
            onClick={() => setOpcion('arriendo')}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              opcion === 'arriendo'
                ? 'bg-teal-500 text-slate-950 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Arriendo
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
        <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1">
          <span className="text-slate-400 font-medium flex items-center gap-1">
            <Users className="w-3.5 h-3.5 text-emerald-400" /> Mediana de la Zona
          </span>
          <div className="text-lg font-bold text-white">
            {formatCOP(mediana_m2)} <span className="text-xs font-normal text-slate-400">/ m²</span>
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1">
          <span className="text-slate-400 font-medium flex items-center gap-1">
            <Gauge className="w-3.5 h-3.5 text-emerald-400" /> Rango Típico (p25 - p75)
          </span>
          <div className="text-sm font-semibold text-slate-200 pt-0.5">
            {formatCOP(p25_m2)} — {formatCOP(p75_m2)}
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1">
          <span className="text-slate-400 font-medium">Percentil del Avalúo</span>
          <div className="text-lg font-bold text-emerald-400">
            {percentil_avaluo.toFixed(0)} %
          </div>
        </div>
      </div>

      {/* Explicación del Percentil */}
      <div className="p-3 rounded-xl bg-slate-950/40 border border-slate-800/60 text-xs text-slate-300">
        El avalúo estimado se ubica en el <strong>percentil {percentil_avaluo.toFixed(0)}%</strong> de los anuncios del mismo tipo y área similar en el sector ({percentil_avaluo < 50 ? 'más asequible que la mediana' : 'por encima de la mediana'}).
      </div>

      {/* Histograma Visual */}
      <div className="space-y-2">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          Histograma de Precios por m² (Mercado Local)
        </span>
        <div className="h-32 flex items-end gap-1.5 pt-4 pb-2 px-3 rounded-xl bg-slate-950/60 border border-slate-800">
          {histograma_m2.conteos.map((conteo, idx) => {
            const esInmueble = idx === histograma_m2.barra_avaluo;
            const alturaPct = Math.max((conteo / maxConteo) * 100, 4);

            return (
              <div
                key={idx}
                className="flex-1 flex flex-col items-center h-full justify-end group relative"
              >
                {/* Tooltip on hover */}
                <div className="absolute -top-7 scale-0 group-hover:scale-100 transition-all bg-slate-800 text-white text-[10px] px-2 py-0.5 rounded shadow whitespace-nowrap z-10 pointer-events-none">
                  {conteo} anuncios
                </div>

                <div
                  className={`w-full rounded-t transition-all duration-300 ${
                    esInmueble
                      ? 'bg-emerald-400 ring-2 ring-emerald-300 shadow-lg shadow-emerald-500/50'
                      : 'bg-slate-700/60 hover:bg-slate-600'
                  }`}
                  style={{ height: `${alturaPct}%` }}
                ></div>
              </div>
            );
          })}
        </div>

        {/* Ejes del Histograma */}
        <div className="flex justify-between text-[10px] text-slate-500 font-mono">
          <span>{formatCOP(histograma_m2.limites[0])}/m²</span>
          <span className="text-emerald-400 font-semibold">▲ Tu avalúo</span>
          <span>{formatCOP(histograma_m2.limites[histograma_m2.limites.length - 1])}/m²</span>
        </div>
      </div>
    </div>
  );
};
