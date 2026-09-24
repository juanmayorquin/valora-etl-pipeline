import { useState } from 'react';
import { ValuationRequest, ValuationResponse, UserObjective } from '../../../types/valuation';
import { formatCompactCOP } from '../../../shared/utils/formatters';
import {
  SlidersHorizontal,
  RefreshCw,
  Zap,
  Tag,
  Clock,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

interface InteractiveScenariosProps {
  currentRequest: ValuationRequest;
  result: ValuationResponse;
  objective: UserObjective;
  onRecalculate: (modifiedRequest: ValuationRequest) => void;
  isRecalculating: boolean;
}

export const InteractiveScenarios: React.FC<InteractiveScenariosProps> = ({
  currentRequest,
  result,
  objective,
  onRecalculate,
  isRecalculating,
}) => {
  const [area, setArea] = useState<number>(currentRequest.area_m2);
  const [habitaciones, setHabitaciones] = useState<number>(currentRequest.habitaciones);
  const [parqueaderos, setParqueaderos] = useState<number>(currentRequest.parqueaderos);
  const [estrato, setEstrato] = useState<number | null>(currentRequest.estrato ?? 4);
  const [showTweaker, setShowTweaker] = useState<boolean>(false);

  const hasModifications =
    area !== currentRequest.area_m2 ||
    habitaciones !== currentRequest.habitaciones ||
    parqueaderos !== currentRequest.parqueaderos ||
    estrato !== currentRequest.estrato;

  const handleApplyChanges = () => {
    onRecalculate({
      ...currentRequest,
      area_m2: Number(area),
      habitaciones: Number(habitaciones),
      parqueaderos: Number(parqueaderos),
      estrato: estrato ? Number(estrato) : null,
    });
  };

  const venta = result.avaluo.venta;
  const arriendo = result.avaluo.arriendo;

  // Strategic pricing derived from range
  const precioVentaRapida = Math.round(venta.rango[0] + (venta.estimado - venta.rango[0]) * 0.4);
  const precioVentaMercado = venta.estimado;
  const precioVentaMaximo = venta.rango[1];

  const canonCompetitivo = Math.round(arriendo.rango[0] + (arriendo.estimado - arriendo.rango[0]) * 0.35);
  const canonMercado = arriendo.estimado;
  const canonMaximo = arriendo.rango[1];

  return (
    <div className="rounded-2xl bg-surface border border-ink-border p-6 sm:p-7 space-y-6 shadow-card">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3.5 pb-4 border-b border-ink-border/70">
        <div>
          <span className="text-[12px] font-bold text-brand-600 uppercase tracking-wider flex items-center gap-1.5">
            <SlidersHorizontal className="w-4 h-4" />
            Estrategia de Precio y Simulación
          </span>
          <h3 className="text-[22px] sm:text-[24px] lg:text-[26px] font-bold text-ink-primary font-display mt-0.5">
            Escenarios de Mercado
          </h3>
        </div>

        <button
          type="button"
          onClick={() => setShowTweaker(!showTweaker)}
          className="text-[15px] font-semibold min-h-[44px] px-4 py-2 rounded-xl border border-ink-border bg-canvas text-ink-primary hover:border-brand-500 hover:text-brand-600 transition-colors flex items-center gap-2 shrink-0 self-start sm:self-auto"
        >
          <SlidersHorizontal className="w-4 h-4 text-brand-500" />
          <span>{showTweaker ? 'Ocultar ajustador' : 'Simular cambios en el inmueble'}</span>
          {showTweaker ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {/* ===================== SIMULADOR RÁPIDO (WHAT-IF) ===================== */}
      {showTweaker && (
        <div className="p-5 rounded-xl bg-canvas border border-ink-border space-y-4 animate-fadeIn">
          <div className="flex items-center justify-between">
            <span className="text-[15px] font-bold text-ink-primary flex items-center gap-2">
              <Zap className="w-4 h-4 text-brand-500" /> Modificar características y simular nuevo avalúo
            </span>
            {hasModifications && (
              <span className="text-[12px] font-semibold text-warning-700 bg-warning-50 px-2.5 py-0.5 rounded-full border border-warning-200">
                Cambios pendientes
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3.5 text-[14px]">
            {/* Área Slider */}
            <div className="space-y-1.5">
              <div className="flex justify-between font-semibold text-ink-primary text-[14px]">
                <span>Área:</span>
                <span className="text-brand-700 font-bold">{area} m²</span>
              </div>
              <input
                type="range"
                min={25}
                max={350}
                value={area}
                onChange={(e) => setArea(Number(e.target.value))}
                className="w-full accent-brand-500 cursor-pointer h-2 bg-slate-200 rounded-lg"
              />
            </div>

            {/* Habitaciones */}
            <div className="space-y-1.5">
              <div className="flex justify-between font-semibold text-ink-primary text-[14px]">
                <span>Habitaciones:</span>
                <span className="text-brand-700 font-bold">{habitaciones}</span>
              </div>
              <div className="flex gap-1.5">
                {[1, 2, 3, 4, 5].map((h) => (
                  <button
                    key={h}
                    type="button"
                    onClick={() => setHabitaciones(h)}
                    className={`flex-1 min-h-[38px] rounded-lg border font-bold text-[14px] transition-all ${
                      habitaciones === h
                        ? 'bg-brand-500 text-white border-brand-500'
                        : 'bg-surface border-ink-border text-ink-secondary hover:text-ink-primary'
                    }`}
                  >
                    {h}
                  </button>
                ))}
              </div>
            </div>

            {/* Parqueaderos */}
            <div className="space-y-1.5">
              <div className="flex justify-between font-semibold text-ink-primary text-[14px]">
                <span>Parqueaderos:</span>
                <span className="text-brand-700 font-bold">{parqueaderos}</span>
              </div>
              <div className="flex gap-1.5">
                {[0, 1, 2, 3].map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setParqueaderos(p)}
                    className={`flex-1 min-h-[38px] rounded-lg border font-bold text-[14px] transition-all ${
                      parqueaderos === p
                        ? 'bg-brand-500 text-white border-brand-500'
                        : 'bg-surface border-ink-border text-ink-secondary hover:text-ink-primary'
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>

            {/* Estrato */}
            <div className="space-y-1.5">
              <div className="flex justify-between font-semibold text-ink-primary text-[14px]">
                <span>Estrato:</span>
                <span className="text-brand-700 font-bold">E{estrato ?? '-'}</span>
              </div>
              <div className="flex gap-1">
                {[1, 2, 3, 4, 5, 6].map((e) => (
                  <button
                    key={e}
                    type="button"
                    onClick={() => setEstrato(e)}
                    className={`flex-1 min-h-[38px] rounded-lg border font-bold text-[13px] sm:text-[14px] transition-all ${
                      estrato === e
                        ? 'bg-brand-500 text-white border-brand-500'
                        : 'bg-surface border-ink-border text-ink-secondary hover:text-ink-primary'
                    }`}
                  >
                    {e}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="pt-2 flex justify-end">
            <button
              type="button"
              onClick={handleApplyChanges}
              disabled={isRecalculating || !hasModifications}
              className="min-h-[46px] px-6 py-2.5 rounded-xl bg-brand-500 hover:bg-brand-600 disabled:opacity-40 disabled:pointer-events-none text-white font-bold text-[15px] sm:text-[16px] shadow-xs transition-all flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${isRecalculating ? 'animate-spin' : ''}`} />
              <span>{isRecalculating ? 'Recalculando modelo...' : 'Recalcular escenario'}</span>
            </button>
          </div>
        </div>
      )}

      {/* ===================== ESCENARIOS DERIVADOS ===================== */}
      <div className="space-y-4">
        {/* VENTA ESCENARIOS */}
        {(objective === 'vender' || objective === 'ambas') && (
          <div className="space-y-2.5">
            <span className="text-[14px] font-bold text-ink-muted uppercase tracking-wider block">
              Escenarios Estratégicos de Venta
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
              {/* Venta rápida */}
              <div className="p-4 sm:p-5 rounded-xl bg-canvas border border-ink-border space-y-2 hover:border-ink-subtle transition-colors">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-bold text-warning-700 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5" /> Vender Rápido
                  </span>
                  <span className="text-[12px] text-ink-muted">&lt; 60 días</span>
                </div>
                <div className="text-[20px] sm:text-[22px] font-extrabold text-ink-primary tabular-nums">
                  {formatCompactCOP(precioVentaRapida)}
                </div>
                <p className="text-[15px] text-ink-secondary leading-relaxed">
                  Colocación ágil en el mercado. Atrae mayor volumen de compradores calificados.
                </p>
              </div>

              {/* Precio de mercado */}
              <div className="p-4 sm:p-5 rounded-xl bg-brand-50/70 border border-brand-300 ring-1 ring-brand-500/20 space-y-2 relative overflow-hidden shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-bold text-brand-700 flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5" /> Precio de Mercado
                  </span>
                  <span className="text-[11px] text-brand-700 font-bold bg-brand-100 px-2 py-0.5 rounded">Recomendado</span>
                </div>
                <div className="text-[20px] sm:text-[22px] font-extrabold text-ink-primary tabular-nums">
                  {formatCompactCOP(precioVentaMercado)}
                </div>
                <p className="text-[15px] text-ink-secondary leading-relaxed">
                  Mediana estadística del modelo. Balance óptimo entre tiempo de cierre y retorno.
                </p>
              </div>

              {/* Techo razonable */}
              <div className="p-4 sm:p-5 rounded-xl bg-canvas border border-ink-border space-y-2 hover:border-ink-subtle transition-colors">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-bold text-chart-600 flex items-center gap-1.5">
                    <Tag className="w-3.5 h-3.5" /> Techo Razonable
                  </span>
                  <span className="text-[12px] text-ink-muted">Excelente estado</span>
                </div>
                <div className="text-[20px] sm:text-[22px] font-extrabold text-ink-primary tabular-nums">
                  {formatCompactCOP(precioVentaMaximo)}
                </div>
                <p className="text-[15px] text-ink-secondary leading-relaxed">
                  Aplica si el inmueble cuenta con acabados de lujo, piso alto y vista privilegiada.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ARRIENDO ESCENARIOS */}
        {(objective === 'arrendar' || objective === 'ambas') && (
          <div className="space-y-2.5 pt-2">
            <span className="text-[14px] font-bold text-ink-muted uppercase tracking-wider block">
              Escenarios Estratégicos de Arriendo
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
              {/* Canon Competitivo */}
              <div className="p-4 sm:p-5 rounded-xl bg-canvas border border-ink-border space-y-2 hover:border-ink-subtle transition-colors">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-bold text-warning-700 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5" /> Ocupación Inmediata
                  </span>
                  <span className="text-[12px] text-ink-muted">&lt; 30 días</span>
                </div>
                <div className="text-[20px] sm:text-[22px] font-extrabold text-ink-primary tabular-nums">
                  {formatCompactCOP(canonCompetitivo)} <span className="text-[14px] font-normal text-ink-muted">/mes</span>
                </div>
                <p className="text-[15px] text-ink-secondary leading-relaxed">
                  Canon atractivo que minimiza el tiempo de vacancia del inmueble.
                </p>
              </div>

              {/* Canon de Mercado */}
              <div className="p-4 sm:p-5 rounded-xl bg-brand-50/70 border border-brand-300 ring-1 ring-brand-500/20 space-y-2 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-bold text-brand-700 flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5" /> Canon de Mercado
                  </span>
                  <span className="text-[11px] text-brand-700 font-bold bg-brand-100 px-2 py-0.5 rounded">Equilibrio</span>
                </div>
                <div className="text-[20px] sm:text-[22px] font-extrabold text-ink-primary tabular-nums">
                  {formatCompactCOP(canonMercado)} <span className="text-[14px] font-normal text-ink-muted">/mes</span>
                </div>
                <p className="text-[15px] text-ink-secondary leading-relaxed">
                  Canon justo que refleja las amenidades y características medias del sector.
                </p>
              </div>

              {/* Canon Techo */}
              <div className="p-4 sm:p-5 rounded-xl bg-canvas border border-ink-border space-y-2 hover:border-ink-subtle transition-colors">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-bold text-chart-600 flex items-center gap-1.5">
                    <Tag className="w-3.5 h-3.5" /> Canon Máximo
                  </span>
                  <span className="text-[12px] text-ink-muted">Amoblado / VIP</span>
                </div>
                <div className="text-[20px] sm:text-[22px] font-extrabold text-ink-primary tabular-nums">
                  {formatCompactCOP(canonMaximo)} <span className="text-[14px] font-normal text-ink-muted">/mes</span>
                </div>
                <p className="text-[15px] text-ink-secondary leading-relaxed">
                  Viable con amoblamiento integral o contratos de estancia media corporativa.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
