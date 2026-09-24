import React from 'react';
import {
  Scale,
  Plus,
  Trash2,
  ExternalLink,
  Award,
  Sparkles,
  TrendingUp,
  ShieldCheck,
  Check,
} from 'lucide-react';
import { SavedProperty } from '../hooks/useSavedProperties';
import { ValuationResponse, UserObjective, ValuationRequest } from '../../../types/valuation';

interface PropertyComparisonViewProps {
  savedProperties: SavedProperty[];
  compareIds: string[];
  onToggleCompare: (id: string) => void;
  onClearCompare: () => void;
  onViewDetails: (request: ValuationRequest, result: ValuationResponse, objective: UserObjective) => void;
  onNewEstimate: () => void;
}

export const PropertyComparisonView: React.FC<PropertyComparisonViewProps> = ({
  savedProperties,
  compareIds,
  onToggleCompare,
  onClearCompare,
  onViewDetails,
  onNewEstimate,
}) => {
  const compared = savedProperties.filter((p) => compareIds.includes(p.id));

  const formatCurrency = (val: number | null | undefined): string => {
    if (!val) return 'No disponible';
    return new Intl.NumberFormat('es-CO', {
      style: 'currency',
      currency: 'COP',
      maximumFractionDigits: 0,
    }).format(val);
  };

  // Find best metrics among compared
  const lowestPriceM2 = compared.reduce<number | null>((min, p) => {
    const val = p.result?.avaluo?.venta?.precio_m2;
    if (!val) return min;
    return min === null || val < min ? val : min;
  }, null);

  const highestYield = compared.reduce<number | null>((max, p) => {
    const val = p.result?.avaluo?.['rentabilidad_bruta_anual_%'];
    if (!val) return max;
    return max === null || val > max ? val : max;
  }, null);

  if (compared.length < 2) {
    return (
      <div className="max-w-4xl mx-auto py-10 px-4 space-y-8 animate-fadeIn">
        <div className="text-center space-y-3">
          <div className="w-16 h-16 bg-chart-100 text-chart-600 rounded-2xl flex items-center justify-center mx-auto shadow-sm">
            <Scale className="w-8 h-8" />
          </div>
          <h1 className="text-[22px] sm:text-[24px] lg:text-[26px] font-bold text-ink-primary font-display">
            Comparador de Inmuebles
          </h1>
          <p className="text-[15px] text-ink-secondary max-w-md mx-auto leading-relaxed">
            Selecciona al menos 2 inmuebles para contrastar precios por m², cánones de arriendo, rentabilidad y características frente a frente.
          </p>
        </div>

        {savedProperties.length > 0 ? (
          <div className="bg-surface p-6 rounded-2xl border border-ink-border shadow-card space-y-4">
            <h3 className="text-[16px] font-bold text-ink-primary flex items-center justify-between">
              <span>Elige de tus inmuebles guardados:</span>
              <span className="text-[13px] font-normal text-ink-muted">
                {compareIds.length} de 4 seleccionados
              </span>
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {savedProperties.map((prop) => {
                const isChecked = compareIds.includes(prop.id);
                return (
                  <div
                    key={prop.id}
                    onClick={() => onToggleCompare(prop.id)}
                    className={`min-h-[52px] p-3.5 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                      isChecked
                        ? 'border-chart-500 bg-chart-50/50 ring-1 ring-chart-500'
                        : 'border-ink-border hover:border-ink-subtle bg-canvas/50'
                    }`}
                  >
                    <div className="min-w-0 pr-2">
                      <div className="text-[14px] font-bold text-ink-primary truncate">
                        {prop.request.sector}, {prop.request.ciudad}
                      </div>
                      <div className="text-[12px] text-ink-muted mt-0.5">
                        {prop.request.tipo} · {prop.request.area_m2} m² · Estrato {prop.request.estrato || '--'}
                      </div>
                    </div>
                    <div
                      className={`w-5 h-5 rounded-md flex items-center justify-center shrink-0 border ${
                        isChecked
                          ? 'bg-chart-500 border-chart-500 text-white'
                          : 'border-ink-subtle bg-white'
                      }`}
                    >
                      {isChecked && <Check className="w-3.5 h-3.5" />}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="text-center pt-2">
            <button
              type="button"
              onClick={onNewEstimate}
              className="inline-flex items-center gap-2 min-h-[48px] px-6 py-3 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-bold text-[15px] sm:text-[16px] shadow-card transition-all"
            >
              <Sparkles className="w-4 h-4" />
              <span>Realizar primera estimación</span>
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-surface p-5 sm:p-6 rounded-2xl border border-ink-border shadow-card">
        <div>
          <h1 className="text-[22px] sm:text-[24px] lg:text-[26px] font-bold text-ink-primary font-display flex items-center gap-2">
            <Scale className="w-6 h-6 text-chart-500" />
            <span>Comparativa Frente a Frente</span>
          </h1>
          <p className="text-[15px] text-ink-secondary mt-0.5">
            Analizando {compared.length} inmuebles simultáneamente para una decisión informada
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 sm:gap-3">
          <button
            type="button"
            onClick={onClearCompare}
            className="min-h-[44px] px-4 py-2 rounded-xl text-[14px] sm:text-[15px] font-semibold text-ink-secondary hover:text-ink-primary hover:bg-canvas transition-colors border border-ink-border"
          >
            Limpiar comparación
          </button>
          <button
            type="button"
            onClick={onNewEstimate}
            className="inline-flex items-center gap-1.5 min-h-[44px] px-4 py-2 rounded-xl text-[14px] sm:text-[15px] font-semibold bg-brand-500 hover:bg-brand-600 text-white transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>Evaluar otro inmueble</span>
          </button>
        </div>
      </div>

      {/* Comparison Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 items-stretch">
        {compared.map((prop, idx) => {
          const venta = prop.result?.avaluo?.venta?.estimado;
          const precioM2 = prop.result?.avaluo?.venta?.precio_m2;
          const arriendo = prop.result?.avaluo?.arriendo?.estimado;
          const rentabilidad = prop.result?.avaluo?.['rentabilidad_bruta_anual_%'];
          const comparablesSector = prop.result?.avaluo?.contexto?.n_comparables_sector || 0;

          const isBestM2 = lowestPriceM2 && precioM2 && precioM2 === lowestPriceM2;
          const isBestYield = highestYield && rentabilidad && rentabilidad === highestYield;

          return (
            <div
              key={prop.id}
              className="bg-surface rounded-2xl border border-ink-border shadow-card flex flex-col justify-between overflow-hidden"
            >
              {/* Card Top Title */}
              <div className="p-4 bg-canvas/70 border-b border-ink-border flex items-start justify-between">
                <div>
                  <span className="text-[11px] font-bold uppercase tracking-wider text-brand-700 bg-brand-100 px-2 py-0.5 rounded">
                    Opción {idx + 1} · {prop.request.tipo}
                  </span>
                  <h3 className="text-[17px] font-bold text-ink-primary mt-1 line-clamp-1">
                    {prop.request.sector}
                  </h3>
                  <p className="text-[14px] text-ink-secondary">{prop.request.ciudad}</p>
                </div>

                <button
                  type="button"
                  onClick={() => onToggleCompare(prop.id)}
                  className="min-h-[38px] min-w-[38px] flex items-center justify-center rounded-lg text-ink-muted hover:text-danger-500 hover:bg-danger-50 transition-colors"
                  title="Quitar de comparación"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>

              {/* Rows */}
              <div className="p-4 space-y-4 divide-y divide-ink-border/60 text-[14px] flex-1">
                {/* 1. Precio Venta */}
                <div className="pt-1">
                  <span className="text-[12px] text-ink-muted uppercase font-bold tracking-wider block">
                    Precio Estimado Venta
                  </span>
                  <div className="text-[20px] sm:text-[22px] font-black text-ink-primary tabular-nums mt-0.5">
                    {formatCurrency(venta)}
                  </div>
                  {prop.result?.avaluo?.venta?.rango && (
                    <span className="text-[12px] text-ink-secondary tabular-nums">
                      Rango: {formatCurrency(prop.result.avaluo.venta.rango[0])} - {formatCurrency(prop.result.avaluo.venta.rango[1])}
                    </span>
                  )}
                </div>

                {/* 2. Precio por M2 */}
                <div className="pt-3">
                  <span className="text-[12px] text-ink-muted uppercase font-bold tracking-wider block">
                    Precio por m²
                  </span>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[15px] font-bold text-ink-primary tabular-nums">
                      {formatCurrency(precioM2)} / m²
                    </span>
                    {isBestM2 && (
                      <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full bg-brand-100 text-brand-700 text-[11px] font-bold">
                        <Award className="w-3.5 h-3.5" /> Mejor m²
                      </span>
                    )}
                  </div>
                </div>

                {/* 3. Canon Arriendo Estimado */}
                <div className="pt-3">
                  <span className="text-[12px] text-ink-muted uppercase font-bold tracking-wider block">
                    Canon Estimado Mensual
                  </span>
                  <div className="text-[16px] font-bold text-brand-600 tabular-nums mt-0.5">
                    {formatCurrency(arriendo)} / mes
                  </div>
                </div>

                {/* 4. Rentabilidad Bruta Anual */}
                <div className="pt-3">
                  <span className="text-[12px] text-ink-muted uppercase font-bold tracking-wider block">
                    Rentabilidad Bruta Anual
                  </span>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[16px] font-bold text-chart-600 tabular-nums">
                      {rentabilidad ? `${rentabilidad.toFixed(2)} %` : 'N/D'}
                    </span>
                    {isBestYield && (
                      <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full bg-chart-100 text-chart-700 text-[11px] font-bold">
                        <TrendingUp className="w-3.5 h-3.5" /> Mayor Cap Rate
                      </span>
                    )}
                  </div>
                </div>

                {/* 5. Dimensiones */}
                <div className="pt-3 space-y-1.5">
                  <span className="text-[12px] text-ink-muted uppercase font-bold tracking-wider block">
                    Ficha Técnica
                  </span>
                  <div className="grid grid-cols-2 gap-1.5 text-ink-secondary text-[13px] sm:text-[14px]">
                    <span>Área: <strong className="text-ink-primary">{prop.request.area_m2} m²</strong></span>
                    <span>Estrato: <strong className="text-ink-primary">{prop.request.estrato || '--'}</strong></span>
                    <span>Habitaciones: <strong className="text-ink-primary">{prop.request.habitaciones}</strong></span>
                    <span>Baños: <strong className="text-ink-primary">{prop.request.banos}</strong></span>
                    <span>Parqueaderos: <strong className="text-ink-primary">{prop.request.parqueaderos}</strong></span>
                    {prop.request.piso && <span>Piso: <strong className="text-ink-primary">{prop.request.piso}</strong></span>}
                  </div>
                </div>

                {/* 6. Confianza del modelo */}
                <div className="pt-3">
                  <span className="text-[12px] text-ink-muted uppercase font-bold tracking-wider block">
                    Soporte Estadístico
                  </span>
                  <div className="flex items-center gap-1.5 text-ink-secondary mt-1 text-[13px]">
                    <ShieldCheck className="w-4 h-4 text-brand-500 shrink-0" />
                    <span>{comparablesSector} comparables en la zona</span>
                  </div>
                </div>
              </div>

              {/* Card Bottom CTA */}
              <div className="p-3 bg-canvas border-t border-ink-border">
                <button
                  type="button"
                  onClick={() => onViewDetails(prop.request, prop.result, prop.objective)}
                  className="w-full min-h-[44px] py-2.5 px-3 rounded-xl bg-surface hover:bg-white text-ink-primary hover:text-brand-600 font-bold text-[14px] sm:text-[15px] border border-ink-border hover:border-brand-500 shadow-xs flex items-center justify-center gap-1.5 transition-all"
                >
                  <ExternalLink className="w-4 h-4" />
                  <span>Ver avalúo completo</span>
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
