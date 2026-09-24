import React from 'react';
import { ComparableItem, OperationType } from '../../../types/valuation';
import { formatCOP, formatM2 } from '../../../shared/utils/formatters';
import {
  MapPin,
  ExternalLink,
  Bed,
  Bath,
  Car,
} from 'lucide-react';

interface ComparableCardProps {
  item: ComparableItem;
  isSelected: boolean;
  onSelect: () => void;
  operacion: OperationType;
}

export const ComparableCard: React.FC<ComparableCardProps> = ({
  item,
  isSelected,
  onSelect,
  operacion,
}) => {
  return (
    <div
      onClick={onSelect}
      className={`p-3.5 rounded-xl border text-left cursor-pointer transition-all relative overflow-hidden ${
        isSelected
          ? 'border-brand-500 bg-brand-50/80 ring-1 ring-brand-500 shadow-xs'
          : 'border-ink-border bg-surface hover:border-ink-subtle hover:bg-canvas/60 shadow-xs'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-1.5 text-[12px] text-ink-muted">
            <MapPin className="w-3.5 h-3.5 text-brand-500 shrink-0" />
            <span className="font-semibold text-ink-secondary">
              {item.distancia_km ? `a ${item.distancia_km.toFixed(2)} km` : 'En el sector'}
            </span>
            {item.sector && <span className="text-ink-muted">· {item.sector}</span>}
          </div>

          <div className="text-[16px] font-bold text-ink-primary mt-1 tabular-nums">
            {formatCOP(item.precio)}
            {operacion === 'arriendo' && <span className="text-[13px] text-ink-muted font-normal"> /mes</span>}
          </div>
        </div>

        {item.url && (
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="p-2 rounded-lg border border-ink-border bg-canvas text-ink-secondary hover:text-brand-700 hover:border-brand-500 transition-colors shrink-0"
            title="Abrir anuncio publicado original"
            aria-label="Ver anuncio original"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
        )}
      </div>

      <div className="flex items-center justify-between text-[14px] mt-2 pt-2 border-t border-ink-border/60 text-ink-secondary">
        <span className="font-bold text-brand-700">{formatM2(item.area_m2)}</span>
        <span className="tabular-nums font-semibold">{formatCOP(item.precio_m2)} / m²</span>
      </div>

      {/* Características secundarias */}
      <div className="flex items-center gap-3 text-[13px] text-ink-muted mt-2">
        {item.habitaciones !== null && (
          <span className="flex items-center gap-1">
            <Bed className="w-3.5 h-3.5 text-ink-muted" />
            {item.habitaciones} hab
          </span>
        )}
        {item.banos !== null && (
          <span className="flex items-center gap-1">
            <Bath className="w-3.5 h-3.5 text-ink-muted" />
            {item.banos} bñ
          </span>
        )}
        {item.parqueaderos != null && item.parqueaderos > 0 && (
          <span className="flex items-center gap-1">
            <Car className="w-3.5 h-3.5 text-ink-muted" />
            {item.parqueaderos} pq
          </span>
        )}
        {item.estrato !== null && (
          <span className="flex items-center gap-0.5 text-ink-muted font-medium">
            E{item.estrato}
          </span>
        )}
      </div>
    </div>
  );
};
