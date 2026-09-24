import React from 'react';
import { ValuationRequest, UserObjective } from '../../../types/valuation';
import { Building2, Edit3, CheckCircle2 } from 'lucide-react';

interface PropertySummaryBadgeProps {
  request: ValuationRequest;
  objective?: UserObjective;
  onEditClick: () => void;
}

export const PropertySummaryBadge: React.FC<PropertySummaryBadgeProps> = ({
  request,
  objective = 'ambas',
  onEditClick,
}) => {
  const objectiveLabel =
    objective === 'vender'
      ? 'Objetivo: Vender'
      : objective === 'arrendar'
      ? 'Objetivo: Arrendar'
      : 'Comparación: Venta y Arriendo';

  return (
    <div className="p-4 sm:p-5 rounded-2xl bg-surface border border-ink-border shadow-card flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
      <div className="flex items-start gap-3.5">
        <div className="w-11 h-11 rounded-xl bg-brand-100 border border-brand-200 flex items-center justify-center text-brand-600 shrink-0 mt-0.5">
          <Building2 className="w-5 h-5" />
        </div>
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[12px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-brand-100 text-brand-700 border border-brand-200 flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" /> Ficha Ingresada
            </span>
            <span className="text-[13px] font-semibold text-ink-secondary">
              {objectiveLabel}
            </span>
          </div>

          <div className="text-[17px] sm:text-[18px] font-bold text-ink-primary tracking-tight flex flex-wrap items-center gap-x-2">
            <span className="capitalize">{request.tipo}</span>
            <span className="text-ink-muted">·</span>
            <span>{request.area_m2} m²</span>
            <span className="text-ink-muted">·</span>
            <span>{request.habitaciones} {request.habitaciones === 1 ? 'habitación' : 'habitaciones'}</span>
            <span className="text-ink-muted">·</span>
            <span>{request.banos} {request.banos === 1 ? 'baño' : 'baños'}</span>
          </div>

          <p className="text-[15px] text-ink-secondary flex flex-wrap items-center gap-x-2">
            <span className="font-semibold text-brand-700">{request.sector}</span>
            <span className="text-ink-muted">({request.ciudad})</span>
            {request.estrato && (
              <>
                <span className="text-ink-muted">·</span>
                <span>Estrato {request.estrato}</span>
              </>
            )}
            <span className="text-ink-muted">·</span>
            <span>{request.parqueaderos} {request.parqueaderos === 1 ? 'parqueadero' : 'parqueaderos'}</span>
            {request.antiguedad && (
              <>
                <span className="text-ink-muted">·</span>
                <span>{request.antiguedad}</span>
              </>
            )}
          </p>
        </div>
      </div>

      <button
        type="button"
        onClick={onEditClick}
        className="min-h-[44px] px-4 py-2 rounded-xl bg-canvas hover:bg-slate-100 text-ink-primary text-[15px] font-semibold border border-ink-border hover:border-ink-subtle transition-colors flex items-center gap-2 shrink-0 self-stretch sm:self-auto justify-center"
      >
        <Edit3 className="w-4 h-4 text-brand-600" />
        <span>Modificar datos</span>
      </button>
    </div>
  );
};
