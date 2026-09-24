import React, { useState } from 'react';
import { ValuationResponse } from '../../../types/valuation';
import { calculateConfidence } from '../../../shared/utils/formatters';
import {
  ShieldCheck,
  ShieldAlert,
  Shield,
  ChevronDown,
  ChevronUp,
  MapPin,
  Database,
  Info,
} from 'lucide-react';

interface ConfidenceIndicatorProps {
  result: ValuationResponse;
}

export const ConfidenceIndicator: React.FC<ConfidenceIndicatorProps> = ({ result }) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const confidence = calculateConfidence(result);

  const badgeConfig = {
    alta: {
      color: 'bg-brand-100 text-brand-700 border-brand-200',
      icon: ShieldCheck,
      iconColor: 'text-brand-600',
    },
    media: {
      color: 'bg-warning-50 text-amber-800 border-warning-100',
      icon: Shield,
      iconColor: 'text-warning-500',
    },
    limitada: {
      color: 'bg-danger-50 text-danger-600 border-danger-100',
      icon: ShieldAlert,
      iconColor: 'text-danger-500',
    },
  }[confidence.level];

  const Icon = badgeConfig.icon;

  return (
    <div className="rounded-2xl bg-surface border border-ink-border p-4 sm:p-5 space-y-3.5 shadow-card">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className={`w-11 h-11 rounded-xl flex items-center justify-center border ${badgeConfig.color} shrink-0`}>
            <Icon className={`w-5 h-5 ${badgeConfig.iconColor}`} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[14px] font-bold text-ink-primary uppercase tracking-wider">
                Nivel de Confianza
              </span>
              <span
                className={`text-[12px] font-bold px-2.5 py-0.5 rounded-full border ${badgeConfig.color}`}
              >
                {confidence.title}
              </span>
            </div>
            <p className="text-[15px] text-ink-secondary mt-0.5 leading-relaxed">
              {confidence.explanation}
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-[15px] font-semibold text-brand-600 hover:text-brand-700 flex items-center gap-1.5 shrink-0 self-start sm:self-auto min-h-[44px] px-3.5 py-2 rounded-xl hover:bg-brand-50 transition-colors"
          aria-expanded={isExpanded}
        >
          <span>{isExpanded ? 'Ocultar respaldo' : 'Ver respaldo técnico'}</span>
          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {/* Expandable details */}
      {isExpanded && (
        <div className="pt-3.5 border-t border-ink-border/60 space-y-3.5 animate-fadeIn">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            <div className="p-3.5 rounded-xl bg-canvas border border-ink-border">
              <span className="text-[12px] text-ink-muted block uppercase font-bold">
                Radio de Búsqueda
              </span>
              <span className="text-[16px] font-bold text-ink-primary flex items-center gap-1.5 mt-0.5">
                <MapPin className="w-4 h-4 text-brand-500" />
                {confidence.metrics.radioAnalisisKm ? `${confidence.metrics.radioAnalisisKm} km` : 'Sector'}
              </span>
            </div>

            <div className="p-3.5 rounded-xl bg-canvas border border-ink-border">
              <span className="text-[12px] text-ink-muted block uppercase font-bold">
                Inmuebles Parecidos
              </span>
              <span className="text-[16px] font-bold text-ink-primary flex items-center gap-1.5 mt-0.5">
                <Database className="w-4 h-4 text-brand-500" />
                {confidence.metrics.comparablesDirectos} activos
              </span>
            </div>

            <div className="p-3.5 rounded-xl bg-canvas border border-ink-border">
              <span className="text-[12px] text-ink-muted block uppercase font-bold">
                Origen Coordenadas
              </span>
              <span className="text-[16px] font-bold text-ink-primary truncate block mt-0.5 capitalize">
                {confidence.metrics.origenCoords.replace('_', ' ')}
              </span>
            </div>

            <div className="p-3.5 rounded-xl bg-canvas border border-ink-border">
              <span className="text-[12px] text-ink-muted block uppercase font-bold">
                Amplitud del Rango
              </span>
              <span className="text-[16px] font-bold text-ink-primary block mt-0.5">
                ± {(confidence.metrics.amplitudRangoPct / 2).toFixed(0)} % ({confidence.metrics.amplitudRangoPct}%)
              </span>
            </div>
          </div>

          <div className="space-y-2 p-3.5 rounded-xl bg-canvas border border-ink-border">
            <span className="text-[13px] font-bold text-ink-primary flex items-center gap-1.5">
              <Info className="w-4 h-4 text-brand-500" /> Criterios analizados por el modelo:
            </span>
            <ul className="text-[15px] text-ink-secondary space-y-1.5 list-disc list-inside">
              {confidence.reasons.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};
