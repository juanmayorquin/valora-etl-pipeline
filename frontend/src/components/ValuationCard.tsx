import React from 'react';
import { ValuationResponse } from '../types/valuation';
import { TrendingUp, DollarSign, KeyRound, Compass, Shield, MapPin, Database } from 'lucide-react';

interface ValuationCardProps {
  result: ValuationResponse;
}

const formatCOP = (val: number): string => {
  return new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    maximumFractionDigits: 0,
  }).format(val);
};

export const ValuationCard: React.FC<ValuationCardProps> = ({ result }) => {
  const { avaluo } = result;
  const { venta, arriendo, contexto } = avaluo;
  const rentabilidad = avaluo["rentabilidad_bruta_anual_%"];

  // Calculate percentage marker inside the 80% range bar
  const calcPercent = (val: number, min: number, max: number): number => {
    if (max <= min) return 50;
    const pct = ((val - min) / (max - min)) * 100;
    return Math.min(Math.max(pct, 5), 95);
  };

  const ventaPct = calcPercent(venta.estimado, venta.rango[0], venta.rango[1]);
  const arriendoPct = calcPercent(arriendo.estimado, arriendo.rango[0], arriendo.rango[1]);

  return (
    <div className="space-y-4">
      {/* Cabecera del Avalúo */}
      <div className="flex flex-wrap items-center justify-between gap-2 p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80">
        <div>
          <span className="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider">
            Dictamen del Modelo
          </span>
          <h3 className="text-base font-bold text-white flex items-center gap-1.5">
            Avalúo Integral: Venta y Arriendo Mensual
          </h3>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
            <Compass className="w-3 h-3 text-emerald-400" />
            <span>Coord: <strong>{contexto.origen_coordenada}</strong></span>
          </span>
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
            <Shield className="w-3 h-3 text-emerald-400" />
            <span>Estrato: <strong>{contexto.estrato_usado}</strong> ({contexto.origen_estrato})</span>
          </span>
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
            <MapPin className="w-3 h-3 text-emerald-400" />
            <span>{contexto.distancia_centro_km.toFixed(1)} km del centro</span>
          </span>
          {contexto.n_comparables_sector > 0 && (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
              <Database className="w-3 h-3 text-emerald-400" />
              <span>{contexto.n_comparables_sector} en sector</span>
            </span>
          )}
        </div>
      </div>

      {/* Grid de Venta y Arriendo */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Tarjeta Venta */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-b from-slate-900 to-slate-950 border border-slate-800 p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
              <DollarSign className="w-4 h-4" />
              Precio de Venta Estimado
            </span>
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Mediana (p50)
            </span>
          </div>

          <div>
            <div className="text-3xl font-extrabold text-white tracking-tight">
              {formatCOP(venta.estimado)}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              <strong>{formatCOP(venta.precio_m2)}</strong> por m²
            </div>
          </div>

          {/* Rango de Confianza 80% */}
          <div className="pt-2 border-t border-slate-800/80 space-y-2">
            <div className="flex items-center justify-between text-[11px] text-slate-400 font-medium">
              <span>Rango 80% de Confianza</span>
              <span className="text-emerald-400 font-semibold">
                p10 — p90
              </span>
            </div>

            {/* Barra visual de rango */}
            <div className="h-2.5 bg-slate-800 rounded-full relative overflow-hidden">
              <div className="absolute inset-y-0 bg-gradient-to-r from-emerald-600/40 via-emerald-500 to-emerald-600/40 rounded-full w-full"></div>
              {/* Marcador mediana */}
              <div
                className="absolute top-0 bottom-0 w-1.5 bg-white rounded-full shadow-sm ring-2 ring-emerald-400"
                style={{ left: `${ventaPct}%` }}
              ></div>
            </div>

            <div className="flex justify-between text-[11px] text-slate-400 font-medium">
              <span>Min: {formatCOP(venta.rango[0])}</span>
              <span>Max: {formatCOP(venta.rango[1])}</span>
            </div>
          </div>
        </div>

        {/* Tarjeta Arriendo */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-b from-slate-900 to-slate-950 border border-slate-800 p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-teal-400 flex items-center gap-1.5">
              <KeyRound className="w-4 h-4" />
              Canon Mensual de Arriendo
            </span>
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-teal-500/10 text-teal-400 border border-teal-500/20">
              Mediana (p50)
            </span>
          </div>

          <div>
            <div className="text-3xl font-extrabold text-white tracking-tight">
              {formatCOP(arriendo.estimado)}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              <strong>{formatCOP(arriendo.precio_m2)}</strong> por m²
            </div>
          </div>

          {/* Rango de Confianza 80% */}
          <div className="pt-2 border-t border-slate-800/80 space-y-2">
            <div className="flex items-center justify-between text-[11px] text-slate-400 font-medium">
              <span>Rango 80% de Confianza</span>
              <span className="text-teal-400 font-semibold">
                p10 — p90
              </span>
            </div>

            {/* Barra visual de rango */}
            <div className="h-2.5 bg-slate-800 rounded-full relative overflow-hidden">
              <div className="absolute inset-y-0 bg-gradient-to-r from-teal-600/40 via-teal-500 to-teal-600/40 rounded-full w-full"></div>
              {/* Marcador mediana */}
              <div
                className="absolute top-0 bottom-0 w-1.5 bg-white rounded-full shadow-sm ring-2 ring-teal-400"
                style={{ left: `${arriendoPct}%` }}
              ></div>
            </div>

            <div className="flex justify-between text-[11px] text-slate-400 font-medium">
              <span>Min: {formatCOP(arriendo.rango[0])}</span>
              <span>Max: {formatCOP(arriendo.rango[1])}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Rentabilidad Implícita (Cap Rate) */}
      <div className="p-4 rounded-2xl bg-emerald-950/20 border border-emerald-500/20 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <TrendingUp className="w-5 h-5" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-white">Rentabilidad Bruta Anual Implícita (Cap Rate)</h4>
            <p className="text-xs text-slate-400">
              Relación entre canon mensual anualizado (12 meses) y precio de venta proyectado.
            </p>
          </div>
        </div>
        <div className="text-2xl font-black text-emerald-400">
          {rentabilidad.toFixed(2)} %
        </div>
      </div>
    </div>
  );
};
