import { useState } from 'react';
import {
  Bookmark,
  Scale,
  Trash2,
  ExternalLink,
  Calendar,
  Sparkles,
  Search,
  PlusCircle,
} from 'lucide-react';
import { SavedProperty } from '../hooks/useSavedProperties';
import { ValuationResponse, UserObjective, ValuationRequest } from '../../../types/valuation';

interface SavedPropertiesViewProps {
  properties: SavedProperty[];
  compareIds: string[];
  onToggleCompare: (id: string) => void;
  onRemoveProperty: (id: string) => void;
  onViewDetails: (request: ValuationRequest, result: ValuationResponse, objective: UserObjective) => void;
  onNewEstimate: () => void;
  onGoToCompare: () => void;
}

export const SavedPropertiesView: React.FC<SavedPropertiesViewProps> = ({
  properties,
  compareIds,
  onToggleCompare,
  onRemoveProperty,
  onViewDetails,
  onNewEstimate,
  onGoToCompare,
}) => {
  const [searchTerm, setSearchTerm] = useState('');

  const formatCurrency = (val: number | null | undefined): string => {
    if (!val) return '$ --';
    return new Intl.NumberFormat('es-CO', {
      style: 'currency',
      currency: 'COP',
      maximumFractionDigits: 0,
    }).format(val);
  };

  const filteredProperties = properties.filter((p) => {
    const term = searchTerm.toLowerCase();
    return (
      p.title.toLowerCase().includes(term) ||
      p.request.ciudad.toLowerCase().includes(term) ||
      p.request.sector.toLowerCase().includes(term)
    );
  });

  if (properties.length === 0) {
    return (
      <div className="max-w-4xl mx-auto py-12 px-4 text-center space-y-6">
        <div className="w-16 h-16 bg-brand-100 text-brand-600 rounded-2xl flex items-center justify-center mx-auto shadow-sm">
          <Bookmark className="w-8 h-8" />
        </div>
        <div className="space-y-2 max-w-md mx-auto">
          <h2 className="text-[22px] sm:text-[24px] lg:text-[26px] font-bold text-ink-primary font-display">
            Aún no tienes inmuebles guardados
          </h2>
          <p className="text-[15px] text-ink-secondary leading-relaxed">
            Realiza una estimación para tu apartamento o casa y guárdala aquí para comparar alternativas, hacer seguimiento y tomar decisiones con tranquilidad.
          </p>
        </div>
        <div>
          <button
            type="button"
            onClick={onNewEstimate}
            className="inline-flex items-center gap-2 min-h-[48px] px-6 py-3 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-bold text-[15px] sm:text-[16px] shadow-card hover:shadow-card-hover transition-all"
          >
            <Sparkles className="w-4 h-4" />
            <span>Hacer mi primera estimación</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-surface p-5 sm:p-6 rounded-2xl border border-ink-border shadow-card">
        <div>
          <h1 className="text-[22px] sm:text-[24px] lg:text-[26px] font-bold text-ink-primary font-display">
            Mis Inmuebles Guardados
          </h1>
          <p className="text-[15px] text-ink-secondary mt-0.5">
            {properties.length} {properties.length === 1 ? 'inmueble registrado' : 'inmuebles registrados'} para consulta y comparación
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 sm:gap-3">
          {compareIds.length >= 2 && (
            <button
              type="button"
              onClick={onGoToCompare}
              className="inline-flex items-center gap-2 min-h-[44px] px-4 py-2.5 rounded-xl bg-chart-500 hover:bg-chart-600 text-white font-bold text-[14px] sm:text-[15px] shadow-sm transition-all"
            >
              <Scale className="w-4 h-4" />
              <span>Comparar ({compareIds.length}) seleccionados</span>
            </button>
          )}

          <button
            type="button"
            onClick={onNewEstimate}
            className="inline-flex items-center gap-2 min-h-[44px] px-4 py-2.5 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-bold text-[14px] sm:text-[15px] shadow-sm transition-all"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Nueva estimación</span>
          </button>
        </div>
      </div>

      {/* Filter / Search */}
      {properties.length > 2 && (
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-muted" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Buscar por sector, ciudad o tipo de inmueble..."
            className="w-full min-h-[48px] pl-10 pr-4 py-3 rounded-xl bg-surface border border-ink-border text-[16px] text-ink-primary placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 shadow-xs"
          />
        </div>
      )}

      {/* Property Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        {filteredProperties.map((prop) => {
          const isSelected = compareIds.includes(prop.id);
          const formattedDate = new Date(prop.createdAt).toLocaleDateString('es-CO', {
            day: 'numeric',
            month: 'short',
            year: 'numeric',
          });

          const ventaEstimada = prop.result?.avaluo?.venta?.estimado;
          const arriendoEstimado = prop.result?.avaluo?.arriendo?.estimado;
          const precioM2 = prop.result?.avaluo?.venta?.precio_m2;

          return (
            <div
              key={prop.id}
              className={`bg-surface rounded-2xl border transition-all duration-200 flex flex-col justify-between overflow-hidden ${
                isSelected
                  ? 'border-chart-500 ring-2 ring-chart-500/20 shadow-card'
                  : 'border-ink-border hover:border-ink-subtle shadow-card hover:shadow-card-hover'
              }`}
            >
              <div className="p-5 space-y-4">
                {/* Header with Title & Date */}
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-[12px] font-bold uppercase tracking-wider text-brand-600 bg-brand-100 px-2 py-0.5 rounded-md inline-block mb-1">
                      {prop.request.tipo}
                    </span>
                    <h3 className="text-[17px] sm:text-[18px] font-bold text-ink-primary line-clamp-1">
                      {prop.request.sector}
                    </h3>
                    <p className="text-[14px] text-ink-secondary">{prop.request.ciudad}</p>
                  </div>

                  <span className="text-[12px] text-ink-muted flex items-center gap-1 shrink-0 pt-0.5">
                    <Calendar className="w-3.5 h-3.5" />
                    {formattedDate}
                  </span>
                </div>

                {/* Specs chips */}
                <div className="flex flex-wrap gap-2 text-[13px] sm:text-[14px] text-ink-secondary py-1.5 border-y border-ink-border/60">
                  <span className="font-semibold text-ink-primary">{prop.request.area_m2} m²</span>
                  <span>·</span>
                  <span>{prop.request.habitaciones} hab</span>
                  <span>·</span>
                  <span>{prop.request.banos} baños</span>
                  {prop.request.parqueaderos > 0 && (
                    <>
                      <span>·</span>
                      <span>{prop.request.parqueaderos} pqr</span>
                    </>
                  )}
                  {prop.request.estrato && (
                    <>
                      <span>·</span>
                      <span className="bg-canvas px-1.5 py-0.5 rounded text-[12px] font-medium">
                        Estrato {prop.request.estrato}
                      </span>
                    </>
                  )}
                </div>

                {/* Pricing Estimates */}
                <div className="space-y-2.5 pt-1">
                  {ventaEstimada && (
                    <div>
                      <span className="text-[12px] text-ink-muted block font-medium">Estimado de venta</span>
                      <div className="text-[20px] sm:text-[22px] font-black text-ink-primary tabular-nums">
                        {formatCurrency(ventaEstimada)}
                      </div>
                      {precioM2 && (
                        <span className="text-[13px] text-ink-secondary tabular-nums">
                          {formatCurrency(precioM2)} / m²
                        </span>
                      )}
                    </div>
                  )}

                  {arriendoEstimado && (
                    <div className="pt-1">
                      <span className="text-[12px] text-ink-muted block font-medium">Canon estimado mensual</span>
                      <div className="text-[17px] sm:text-[18px] font-bold text-brand-600 tabular-nums">
                        {formatCurrency(arriendoEstimado)} / mes
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Card Footer Actions */}
              <div className="px-5 py-3 bg-canvas border-t border-ink-border/60 flex items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={() => onToggleCompare(prop.id)}
                  className={`inline-flex items-center gap-1.5 min-h-[42px] px-3.5 py-2 rounded-xl text-[14px] sm:text-[15px] font-semibold transition-colors ${
                    isSelected
                      ? 'bg-chart-500 text-white'
                      : 'bg-surface text-ink-secondary hover:text-ink-primary border border-ink-border hover:border-ink-subtle'
                  }`}
                >
                  <Scale className="w-3.5 h-3.5" />
                  <span>{isSelected ? 'Seleccionado' : 'Comparar'}</span>
                </button>

                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => onViewDetails(prop.request, prop.result, prop.objective)}
                    className="min-h-[42px] min-w-[42px] flex items-center justify-center rounded-xl text-brand-600 hover:text-brand-700 hover:bg-brand-100 transition-colors"
                    title="Ver ficha completa"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      if (confirm(`¿Eliminar ${prop.title} de tus inmuebles guardados?`)) {
                        onRemoveProperty(prop.id);
                      }
                    }}
                    className="min-h-[42px] min-w-[42px] flex items-center justify-center rounded-xl text-ink-muted hover:text-danger-500 hover:bg-danger-50 transition-colors"
                    title="Eliminar"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
