import React, { useState } from 'react';
import { ValuationResponse, UserObjective, ValuationRequest } from '../../../types/valuation';
import { formatCOP, formatPercent } from '../../../shared/utils/formatters';
import {
  DollarSign,
  KeyRound,
  TrendingUp,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Bookmark,
  Scale,
  Check,
  Share2,
} from 'lucide-react';

interface ValuationResultCardProps {
  result: ValuationResponse;
  objective?: UserObjective;
  lastRequest?: ValuationRequest | null;
  onSave?: () => void;
  isSaved?: boolean;
  onCompare?: () => void;
}

export const ValuationResultCard: React.FC<ValuationResultCardProps> = ({
  result,
  objective = 'ambas',
  lastRequest,
  onSave,
  isSaved = false,
  onCompare,
}) => {
  const { avaluo, zona } = result;
  const { venta, arriendo } = avaluo;
  const rentabilidad = avaluo["rentabilidad_bruta_anual_%"];
  const [copiedToast, setCopiedToast] = useState(false);

  // Difference vs zone median m2
  const calcDiffMediana = (estimadoM2: number | null, medianaM2: number | null | undefined) => {
    if (!estimadoM2 || !medianaM2) return null;
    const diff = ((estimadoM2 - medianaM2) / medianaM2) * 100;
    return Math.round(diff);
  };

  const diffVenta = calcDiffMediana(venta.precio_m2, zona.venta?.mediana_m2);
  const diffArriendo = calcDiffMediana(arriendo.precio_m2, zona.arriendo?.mediana_m2);

  const handleShare = () => {
    if (navigator.share) {
      navigator.share({
        title: `Avalúo Valora: ${lastRequest?.sector || 'Inmueble'}`,
        text: `Estimación de venta: ${formatCOP(venta.estimado)}. Estimado con Valora.`,
        url: window.location.href,
      }).catch(() => {});
    } else {
      navigator.clipboard.writeText(window.location.href);
      setCopiedToast(true);
      setTimeout(() => setCopiedToast(false), 2500);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Action Bar (Guardar, Comparar, Compartir) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3.5 p-4 sm:p-5 rounded-2xl bg-surface border border-ink-border shadow-card">
        <div className="text-[15px] text-ink-secondary leading-snug">
          <span>¿Te sirve este resultado? Guárdalo en tu portafolio o contrástalo con otros.</span>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {onSave && (
            <button
              type="button"
              onClick={onSave}
              className={`inline-flex items-center justify-center gap-2 min-h-[46px] px-4 py-2.5 rounded-xl text-[15px] sm:text-[16px] font-semibold transition-all ${
                isSaved
                  ? 'bg-brand-100 text-brand-700 border border-brand-200'
                  : 'bg-brand-500 hover:bg-brand-600 text-white shadow-xs'
              }`}
            >
              {isSaved ? <Check className="w-4 h-4 text-brand-600" /> : <Bookmark className="w-4 h-4" />}
              <span>{isSaved ? 'Inmueble guardado' : 'Guardar inmueble'}</span>
            </button>
          )}

          {onCompare && (
            <button
              type="button"
              onClick={onCompare}
              className="inline-flex items-center justify-center gap-2 min-h-[46px] px-4 py-2.5 rounded-xl text-[15px] sm:text-[16px] font-semibold bg-canvas hover:bg-slate-100 text-ink-primary border border-ink-border transition-colors"
            >
              <Scale className="w-4 h-4 text-chart-500" />
              <span>Comparar con otros</span>
            </button>
          )}

          <button
            type="button"
            onClick={handleShare}
            className="w-11 h-11 flex items-center justify-center rounded-xl text-ink-secondary hover:text-ink-primary hover:bg-canvas border border-ink-border transition-colors relative"
            title="Compartir estimación"
            aria-label="Compartir estimación"
          >
            <Share2 className="w-4 h-4" />
            {copiedToast && (
              <span className="absolute -top-8 right-0 bg-ink-primary text-white text-[12px] px-2 py-0.5 rounded shadow">
                Enlace copiado
              </span>
            )}
          </button>
        </div>
      </div>

      {/* ======================= TARJETA VENTA ======================= */}
      {(objective === 'vender' || objective === 'ambas') && (
        <div className="relative overflow-hidden rounded-2xl bg-surface border border-ink-border p-6 sm:p-7 shadow-card space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-ink-border/70">
            <div>
              <span className="text-[12px] font-bold text-brand-600 uppercase tracking-wider flex items-center gap-1.5">
                <DollarSign className="w-4 h-4" />
                Valor de Venta en Mercado
              </span>
              <h3 className="text-[22px] sm:text-[24px] lg:text-[26px] font-bold text-ink-primary font-display mt-0.5">
                Estimación de Venta
              </h3>
            </div>
            {venta.precio_m2 && (
              <div className="text-left sm:text-right">
                <span className="text-[13px] text-ink-muted block">Precio por m²</span>
                <span className="text-[15px] sm:text-[16px] font-bold text-ink-primary tabular-nums">
                  {formatCOP(venta.precio_m2)} / m²
                </span>
              </div>
            )}
          </div>

          {/* Cifra principal: 36-44px */}
          <div className="space-y-2">
            <div className="flex flex-wrap items-baseline gap-3">
              <span className="text-[36px] sm:text-[42px] lg:text-[44px] font-black text-ink-primary font-display tracking-tight tabular-nums leading-none">
                {formatCOP(venta.estimado)}
              </span>
              <span className="text-[14px] px-3 py-1 rounded-full bg-brand-100 text-brand-700 font-semibold border border-brand-200">
                Precio más probable
              </span>
            </div>

            <p className="text-[16px] text-ink-secondary leading-relaxed font-normal">
              El valor central más probable para esta propiedad se sitúa en{' '}
              <strong className="text-ink-primary font-semibold">{formatCOP(venta.estimado)}</strong>.
            </p>
          </div>

          {/* Rango de referencia */}
          <div className="p-4 sm:p-5 rounded-xl bg-canvas border border-ink-border space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-[15px]">
              <span className="text-ink-secondary font-medium">
                Rango de negociación estimado:
              </span>
              <span className="font-bold text-ink-primary tabular-nums">
                {formatCOP(venta.rango[0])} — {formatCOP(venta.rango[1])}
              </span>
            </div>

            {/* Barra visual del rango */}
            <div className="relative h-2.5 bg-slate-200 rounded-full overflow-hidden">
              <div className="absolute inset-y-0 bg-brand-500 rounded-full w-full"></div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-1 text-[13px] sm:text-[14px] text-ink-muted">
              <span>Mínimo competitivo ({formatCOP(venta.rango[0])})</span>
              <span className="text-brand-700 font-semibold">80% de confianza estadística</span>
              <span>Máximo razonable ({formatCOP(venta.rango[1])})</span>
            </div>

            <p className="text-[15px] text-ink-secondary leading-relaxed pt-1">
              El 80% de los inmuebles comparables en este sector se cierran dentro de este intervalo, según estado de acabados y piso.
            </p>
          </div>

          {/* Comparación frente a la mediana de la zona */}
          {diffVenta !== null && (
            <div className="flex items-center gap-2 text-[15px] pt-1 text-ink-secondary">
              <span className="font-medium text-ink-muted">Frente al sector:</span>
              <span
                className={`inline-flex items-center gap-1 font-semibold ${
                  diffVenta > 5
                    ? 'text-brand-600'
                    : diffVenta < -5
                    ? 'text-chart-600'
                    : 'text-ink-secondary'
                }`}
              >
                {diffVenta > 0 ? (
                  <ArrowUpRight className="w-4 h-4" />
                ) : diffVenta < 0 ? (
                  <ArrowDownRight className="w-4 h-4" />
                ) : (
                  <Minus className="w-4 h-4" />
                )}
                {diffVenta > 0 ? `+${diffVenta}%` : `${diffVenta}%`} frente a la mediana del sector ({zona.venta?.mediana_m2 ? formatCOP(zona.venta.mediana_m2) + '/m²' : 'la zona'})
              </span>
            </div>
          )}
        </div>
      )}

      {/* ======================= TARJETA ARRIENDO ======================= */}
      {(objective === 'arrendar' || objective === 'ambas') && (
        <div className="relative overflow-hidden rounded-2xl bg-surface border border-ink-border p-6 sm:p-7 shadow-card space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-ink-border/70">
            <div>
              <span className="text-[12px] font-bold text-brand-600 uppercase tracking-wider flex items-center gap-1.5">
                <KeyRound className="w-4 h-4" />
                Canon Mensual de Arriendo
              </span>
              <h3 className="text-[22px] sm:text-[24px] lg:text-[26px] font-bold text-ink-primary font-display mt-0.5">
                Estimación de Arriendo
              </h3>
            </div>
            {arriendo.precio_m2 && (
              <div className="text-left sm:text-right">
                <span className="text-[13px] text-ink-muted block">Canon por m²</span>
                <span className="text-[15px] sm:text-[16px] font-bold text-ink-primary tabular-nums">
                  {formatCOP(arriendo.precio_m2)} / m²
                </span>
              </div>
            )}
          </div>

          {/* Cifra principal: 36-44px */}
          <div className="space-y-2">
            <div className="flex flex-wrap items-baseline gap-3">
              <span className="text-[36px] sm:text-[42px] lg:text-[44px] font-black text-ink-primary font-display tracking-tight tabular-nums leading-none">
                {formatCOP(arriendo.estimado)}
                <span className="text-[18px] sm:text-[20px] font-semibold text-ink-muted ml-2">/ mes</span>
              </span>
              <span className="text-[14px] px-3 py-1 rounded-full bg-brand-100 text-brand-700 font-semibold border border-brand-200">
                Canon más probable
              </span>
            </div>

            <p className="text-[16px] text-ink-secondary leading-relaxed font-normal">
              El canon mensual de arriendo recomendado está alrededor de{' '}
              <strong className="text-ink-primary font-semibold">{formatCOP(arriendo.estimado)}</strong> al mes.
            </p>
          </div>

          {/* Rango de referencia */}
          <div className="p-4 sm:p-5 rounded-xl bg-canvas border border-ink-border space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-[15px]">
              <span className="text-ink-secondary font-medium">
                Rango de canon estimado:
              </span>
              <span className="font-bold text-ink-primary tabular-nums">
                {formatCOP(arriendo.rango[0])} — {formatCOP(arriendo.rango[1])}
              </span>
            </div>

            <div className="relative h-2.5 bg-slate-200 rounded-full overflow-hidden">
              <div className="absolute inset-y-0 bg-brand-500 rounded-full w-full"></div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-1 text-[13px] sm:text-[14px] text-ink-muted">
              <span>Canon competitivo ({formatCOP(arriendo.rango[0])})</span>
              <span className="text-brand-700 font-semibold">80% de confianza estadística</span>
              <span>Canon máximo ({formatCOP(arriendo.rango[1])})</span>
            </div>

            <p className="text-[15px] text-ink-secondary leading-relaxed pt-1">
              Rango sugerido para fijar el canon considerando administración y dotación del inmueble.
            </p>
          </div>

          {/* Comparación frente a la mediana de la zona */}
          {diffArriendo !== null && (
            <div className="flex items-center gap-2 text-[15px] pt-1 text-ink-secondary">
              <span className="font-medium text-ink-muted">Frente al sector:</span>
              <span
                className={`inline-flex items-center gap-1 font-semibold ${
                  diffArriendo > 5
                    ? 'text-brand-600'
                    : diffArriendo < -5
                    ? 'text-chart-600'
                    : 'text-ink-secondary'
                }`}
              >
                {diffArriendo > 0 ? (
                  <ArrowUpRight className="w-4 h-4" />
                ) : diffArriendo < 0 ? (
                  <ArrowDownRight className="w-4 h-4" />
                ) : (
                  <Minus className="w-4 h-4" />
                )}
                {diffArriendo > 0 ? `+${diffArriendo}%` : `${diffArriendo}%`} frente a la mediana del sector ({zona.arriendo?.mediana_m2 ? formatCOP(zona.arriendo.mediana_m2) + '/m²' : 'la zona'})
              </span>
            </div>
          )}
        </div>
      )}

      {/* ======================= RENTABILIDAD BRUTA ANUAL ======================= */}
      {rentabilidad && (
        <div className="p-5 sm:p-6 rounded-2xl bg-surface border border-ink-border flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-card">
          <div className="flex items-start gap-3.5">
            <div className="w-12 h-12 rounded-xl bg-chart-100 border border-chart-200 flex items-center justify-center text-chart-600 shrink-0">
              <TrendingUp className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-[14px] font-bold text-ink-primary uppercase tracking-wider">
                  Rentabilidad Bruta Anual Estimada
                </span>
                <span className="text-[13px] text-ink-muted" title="Relación canon anual / valor venta">(Cap Rate Implícito)</span>
              </div>
              <p className="text-[15px] text-ink-secondary leading-relaxed max-w-lg">
                Por cada $ 100 millones de valor comercial, este inmueble genera aproximadamente{' '}
                <strong className="text-ink-primary font-semibold">{formatCOP((100_000_000 * rentabilidad) / 100)}</strong> al año en cánones brutos.
              </p>
            </div>
          </div>

          <div className="text-left sm:text-right shrink-0">
            <span className="text-[32px] sm:text-[38px] font-extrabold text-chart-600 font-display tabular-nums">
              {formatPercent(rentabilidad)}
            </span>
            <span className="text-[13px] text-ink-muted block font-medium">bruto anual</span>
          </div>
        </div>
      )}
    </div>
  );
};
