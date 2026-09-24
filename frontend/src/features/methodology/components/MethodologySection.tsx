import React, { useState } from 'react';
import {
  HelpCircle,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  Brain,
  MapPin,
  Database,
  Scale,
  FileText,
} from 'lucide-react';

export const MethodologySection: React.FC = () => {
  const [isOpen, setIsOpen] = useState<boolean>(false);

  const steps = [
    {
      num: 1,
      title: 'Ingreso de Características',
      desc: 'El usuario especifica tipología, área, ubicación y equipamiento del inmueble.',
      icon: FileText,
    },
    {
      num: 2,
      title: 'Resolución Espacial e Imputación',
      desc: 'El sistema geolocaliza el sector, calcula distancias y valida estrato en cascada.',
      icon: MapPin,
    },
    {
      num: 3,
      title: 'Inferencia de Machine Learning',
      desc: 'Modelos LightGBM especializados estiman el valor en logaritmo con split anti-leakage.',
      icon: Brain,
    },
    {
      num: 4,
      title: 'Calibración de Intervalos al 80%',
      desc: 'Se calcula el rango p10–p90 ajustado con factor empírico sobre folds no vistos.',
      icon: Scale,
    },
    {
      num: 5,
      title: 'Búsqueda Espacial de Comparables',
      desc: 'Un árbol KD-Tree extrae en milisegundos las propiedades reales activas en el radio.',
      icon: Database,
    },
  ];

  return (
    <div className="rounded-2xl bg-surface border border-ink-border p-6 sm:p-7 space-y-5 shadow-card">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-brand-100 border border-brand-200 flex items-center justify-center text-brand-600 shrink-0">
            <HelpCircle className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-ink-primary font-display tracking-tight">
              Metodología Analítica y Alcance
            </h3>
            <p className="text-xs text-ink-secondary">
              Conoce el paso a paso del modelo, fuentes de datos y consideraciones técnicas.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="text-xs font-semibold px-3 py-1.5 rounded-xl border border-ink-border bg-canvas text-ink-secondary hover:text-ink-primary hover:border-ink-subtle transition-colors flex items-center gap-1.5 self-start sm:self-auto"
          aria-expanded={isOpen}
        >
          <span>{isOpen ? 'Ocultar metodología' : '¿Cómo funciona?'}</span>
          {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Declaración de advertencia siempre visible */}
      <div className="p-4 rounded-xl bg-canvas border border-ink-border flex items-start gap-2.5 text-xs text-ink-secondary">
        <ShieldAlert className="w-4 h-4 text-warning-500 shrink-0 mt-0.5" />
        <p className="leading-relaxed">
          <strong className="text-ink-primary">Aviso Legal y Profesional: </strong>
          Valora es una herramienta analítica de apoyo a la decisión informada. No sustituye un avalúo comercial profesional, peritaje catastral o avalúo corporativo certificado emitido por un perito inscrito en el RAA (Registro Abierto de Avaluadores).
        </p>
      </div>

      {/* Contenido expandible */}
      {isOpen && (
        <div className="pt-4 border-t border-ink-border space-y-6 animate-fadeIn">
          {/* Pasos */}
          <div className="space-y-3">
            <span className="text-xs font-bold text-ink-primary uppercase tracking-wider block">
              El Proceso de Estimación en 5 Pasos
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
              {steps.map((st) => {
                const Icon = st.icon;
                return (
                  <div
                    key={st.num}
                    className="p-3.5 rounded-xl bg-canvas border border-ink-border space-y-1.5"
                  >
                    <div className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-brand-100 text-brand-700 text-[11px] font-black flex items-center justify-center border border-brand-200">
                        {st.num}
                      </span>
                      <Icon className="w-4 h-4 text-brand-500" />
                    </div>
                    <div className="text-xs font-bold text-ink-primary leading-tight">
                      {st.title}
                    </div>
                    <p className="text-[11px] text-ink-secondary leading-tight">
                      {st.desc}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Limitaciones y Supuestos */}
          <div className="p-4 rounded-xl bg-canvas border border-ink-border space-y-2 text-xs">
            <span className="font-bold text-ink-primary block uppercase tracking-wider text-[11px]">
              Alcance y Limitaciones del Modelo:
            </span>
            <ul className="space-y-1.5 text-ink-secondary list-disc list-inside">
              <li>
                <strong className="text-ink-primary">Precios de Oferta:</strong> Las fuentes corresponden a precios publicados en portales inmobiliarios colombianos, que pueden incluir márgenes de negociación (entre 3% y 8% respecto al precio de cierre final).
              </li>
              <li>
                <strong className="text-ink-primary">Densidad Muestral:</strong> La precisión de la estimación es significativamente mayor en zonas urbanas consolidadas con alta oferta de comparables.
              </li>
              <li>
                <strong className="text-ink-primary">Horizonte Temporal:</strong> El modelo refleja el valor presente del mercado y no constituye una predicción de plusvalía o valorización futura.
              </li>
              <li>
                <strong className="text-ink-primary">Tipología Exclusiva:</strong> Valora está diseñado específicamente para vivienda urbana (apartamentos, casas y apartaestudios). No abarca inmuebles rurales, fincas, lotes, bodegas, oficinas ni locales comerciales.
              </li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};
