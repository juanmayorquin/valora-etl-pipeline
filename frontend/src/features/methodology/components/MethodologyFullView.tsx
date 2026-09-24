import React from 'react';
import {
  ShieldCheck,
  Database,
  BarChart2,
  Cpu,
  Layers,
  CheckCircle2,
  AlertTriangle,
  Scale,
} from 'lucide-react';

export const MethodologyFullView: React.FC = () => {
  return (
    <div className="max-w-4xl mx-auto space-y-8 py-4 animate-fadeIn">
      {/* Header */}
      <div className="bg-surface p-6 sm:p-8 rounded-2xl border border-ink-border shadow-card space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-100 text-brand-700 text-[13px] font-semibold">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Rigor Estadístico y Metodológico</span>
        </div>
        <h1 className="text-[26px] sm:text-[32px] lg:text-[36px] font-extrabold text-ink-primary font-display">
          Metodología de Valoración Analítica
        </h1>
        <p className="text-[15px] sm:text-[16px] text-ink-secondary leading-relaxed max-w-2xl">
          Valora combina métodos comparativos de mercado tradicionales con técnicas avanzadas de Machine Learning supervisado y regresión por cuantiles para estimar el valor comercial y canon de arriendo.
        </p>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-surface p-5 rounded-2xl border border-ink-border shadow-card space-y-1.5">
          <div className="text-[13px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5">
            <Database className="w-4 h-4 text-brand-500" />
            <span>Base Depurada</span>
          </div>
          <div className="text-[32px] sm:text-[36px] font-black text-ink-primary font-display">
            44.836
          </div>
          <p className="text-[13px] sm:text-[14px] text-ink-secondary">
            Ofertas inmobiliarias activas y verificadas en Colombia
          </p>
        </div>

        <div className="bg-surface p-5 rounded-2xl border border-ink-border shadow-card space-y-1.5">
          <div className="text-[13px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5">
            <BarChart2 className="w-4 h-4 text-brand-500" />
            <span>Precisión R²</span>
          </div>
          <div className="text-[32px] sm:text-[36px] font-black text-brand-600 font-display">
            0.92
          </div>
          <p className="text-[13px] sm:text-[14px] text-ink-secondary">
            En validación cruzada con zonas y sectores no vistos
          </p>
        </div>

        <div className="bg-surface p-5 rounded-2xl border border-ink-border shadow-card space-y-1.5">
          <div className="text-[13px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1.5">
            <Cpu className="w-4 h-4 text-brand-500" />
            <span>Cobertura p10 - p90</span>
          </div>
          <div className="text-[32px] sm:text-[36px] font-black text-ink-primary font-display">
            80.0 %
          </div>
          <p className="text-[13px] sm:text-[14px] text-ink-secondary">
            Intervalo empírico calibrado para negociación realista
          </p>
        </div>
      </div>

      {/* Section 1: ETL Pipeline */}
      <div className="bg-surface p-6 sm:p-8 rounded-2xl border border-ink-border shadow-card space-y-4">
        <h2 className="text-[22px] sm:text-[24px] lg:text-[26px] font-bold text-ink-primary font-display flex items-center gap-2">
          <Layers className="w-5 h-5 text-brand-500" />
          <span>1. Ingesta y Limpieza de Datos (Pipeline ETL)</span>
        </h2>
        <div className="text-[15px] sm:text-[16px] text-ink-secondary leading-relaxed space-y-3">
          <p>
            Los datos inmobiliarios en bruto suelen presentar duplicados, precios erróneos (como valores en dólares sin convertir o precios de separación) y áreas inconsistentes. Nuestro pipeline aplica filtros automáticos de calidad:
          </p>
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-2.5 pt-1">
            <li className="flex items-start gap-2 text-[14px] sm:text-[15px]">
              <CheckCircle2 className="w-4 h-4 text-brand-500 shrink-0 mt-0.5" />
              <span>Detección y remoción de duplicados por huella de texto y geolocalización.</span>
            </li>
            <li className="flex items-start gap-2 text-[14px] sm:text-[15px]">
              <CheckCircle2 className="w-4 h-4 text-brand-500 shrink-0 mt-0.5" />
              <span>Filtrado de valores atípicos mediante rangos intercuartílicos por sector.</span>
            </li>
            <li className="flex items-start gap-2 text-[14px] sm:text-[15px]">
              <CheckCircle2 className="w-4 h-4 text-brand-500 shrink-0 mt-0.5" />
              <span>Normalización de estratos, amenidades y áreas construidas.</span>
            </li>
            <li className="flex items-start gap-2 text-[14px] sm:text-[15px]">
              <CheckCircle2 className="w-4 h-4 text-brand-500 shrink-0 mt-0.5" />
              <span>Geocodificación y validación de coordenadas contra centros urbanos.</span>
            </li>
          </ul>
        </div>
      </div>

      {/* Section 2: Machine Learning Architecture */}
      <div className="bg-surface p-6 sm:p-8 rounded-2xl border border-ink-border shadow-card space-y-4">
        <h2 className="text-[22px] sm:text-[24px] lg:text-[26px] font-bold text-ink-primary font-display flex items-center gap-2">
          <Cpu className="w-5 h-5 text-brand-500" />
          <span>2. Arquitectura de Machine Learning y Comparables</span>
        </h2>
        <div className="text-[15px] sm:text-[16px] text-ink-secondary leading-relaxed space-y-3">
          <p>
            El sistema opera en dos capas complementarias:
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            <div className="p-4 rounded-xl bg-canvas border border-ink-border space-y-2">
              <h4 className="font-bold text-ink-primary text-[15px] sm:text-[16px]">
                Árbol espacial cKDTree (Vecindario)
              </h4>
              <p className="text-[14px] text-ink-secondary leading-relaxed">
                Calcula la distancia geodésica exacta frente a ofertas del mismo sector y tipo de inmueble para extraer comparables directos y construir el histograma de precios por m².
              </p>
            </div>
            <div className="p-4 rounded-xl bg-canvas border border-ink-border space-y-2">
              <h4 className="font-bold text-ink-primary text-[15px] sm:text-[16px]">
                Gradient Boosting Cuantílico
              </h4>
              <p className="text-[14px] text-ink-secondary leading-relaxed">
                Entrena tres modelos simultáneos para cada operación: cuantil 0.10 (límite inferior), cuantil 0.50 (mediana / valor más probable) y cuantil 0.90 (límite superior).
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Section 3: Legal & Regulatory Framework */}
      <div className="bg-surface p-6 sm:p-8 rounded-2xl border border-ink-border shadow-card space-y-4">
        <h2 className="text-[22px] sm:text-[24px] lg:text-[26px] font-bold text-ink-primary font-display flex items-center gap-2">
          <Scale className="w-5 h-5 text-brand-500" />
          <span>3. Marco de Referencia Inmobiliario en Colombia</span>
        </h2>
        <div className="text-[15px] sm:text-[16px] text-ink-secondary leading-relaxed space-y-3">
          <p>
            La lógica de Valora se alinea con las mejores prácticas del mercado colombiano:
          </p>
          <ul className="space-y-2 text-[14px] sm:text-[15px]">
            <li className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-brand-500 shrink-0 mt-0.5" />
              <div>
                <strong className="text-ink-primary">Resolución 620 de 2008 (IGAC):</strong> Principios del método de comparación de mercado, considerando características intrínsecas (área, edad, comodidades) y extrínsecas (ubicación, estrato).
              </div>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-brand-500 shrink-0 mt-0.5" />
              <div>
                <strong className="text-ink-primary">Ley 820 de 2003 (Arrendamiento de Vivienda Urbana):</strong> El canon de arriendo no puede superar el 1% del valor comercial del inmueble (Artículo 18). El modelo verifica y respeta este marco de consistencia.
              </div>
            </li>
          </ul>
        </div>
      </div>

      {/* Disclaimer Alert */}
      <div className="p-5 sm:p-6 rounded-2xl bg-canvas border border-ink-border flex items-start gap-3 text-[14px] text-ink-secondary">
        <AlertTriangle className="w-5 h-5 text-warning-500 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <h4 className="font-bold text-ink-primary text-[15px]">
            Aviso de uso y alcance legal
          </h4>
          <p className="leading-relaxed">
            Valora es un modelo estadístico automatizado (AVM) de apoyo analítico a la decisión. No reemplaza un dictamen pericial emitido por un avaluador colegiado registrado en el RAA (Registro Abierto de Avaluadores) bajo la Ley 1673 de 2013 para trámites notariales, créditos hipotecarios o expropiaciones.
          </p>
        </div>
      </div>
    </div>
  );
};
