import {
  FileText,
  Search,
  Cpu,
  BarChart3,
  ShieldCheck,
  CheckCircle2,
  Sparkles,
  ArrowRight,
} from 'lucide-react';

interface HowItWorksViewProps {
  onStartEstimate: () => void;
}

export const HowItWorksView: React.FC<HowItWorksViewProps> = ({ onStartEstimate }) => {
  const steps = [
    {
      number: '01',
      title: 'Ingresas las características básicas',
      desc: 'Elige la ciudad, el sector y las dimensiones de tu inmueble (área, habitaciones, baños, parqueaderos, estrato y amenidades). No necesitas documentos técnicos ni avalúos previos.',
      icon: FileText,
      color: 'bg-brand-100 text-brand-700',
    },
    {
      number: '02',
      title: 'Buscamos comparables en tu vecindario',
      desc: 'Nuestro motor busca ofertas reales recientes en un radio inmediato a tu inmueble. Consideramos la distancia exacta, el tipo de construcción y el nivel socioeconómico de la zona.',
      icon: Search,
      color: 'bg-chart-100 text-chart-700',
    },
    {
      number: '03',
      title: 'Ajuste fino con Machine Learning',
      desc: 'Un ensamble de Gradient Boosting evalúa factores que un promedio simple ignora: piso, ascensor, antigüedad, conjunto cerrado y comodidades, aislando el valor neto de cada característica.',
      icon: Cpu,
      color: 'bg-brand-100 text-brand-700',
    },
    {
      number: '04',
      title: 'Dictamen de precio con rango calibrado',
      desc: 'En lugar de darte un número rígido, te entregamos el precio central más probable y un rango entre el percentil 10 y 90. Así sabes el margen de negociación real al vender o arrendar.',
      icon: BarChart3,
      color: 'bg-warning-100 text-warning-600',
    },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-10 py-4 animate-fadeIn">
      {/* Hero Header */}
      <div className="text-center space-y-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-100 text-brand-700 text-[13px] font-semibold">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Fácil · Preciso · Sin Costo</span>
        </div>
        <h1 className="text-[30px] sm:text-[40px] lg:text-[44px] font-extrabold text-ink-primary font-display tracking-tight leading-tight">
          ¿Cómo estima Valora el precio de tu inmueble?
        </h1>
        <p className="text-[16px] text-ink-secondary max-w-2xl mx-auto leading-relaxed">
          Diseñado para personas que necesitan saber con honestidad y respaldo estadístico cuánto pedir por su propiedad o cuánto pagar de arriendo en Colombia.
        </p>
      </div>

      {/* Steps Flow */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {steps.map((step) => {
          const Icon = step.icon;
          return (
            <div
              key={step.number}
              className="bg-surface rounded-2xl border border-ink-border p-6 shadow-card hover:shadow-card-hover transition-all space-y-4 relative overflow-hidden"
            >
              <div className="flex items-center justify-between">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${step.color}`}>
                  <Icon className="w-6 h-6" />
                </div>
                <span className="text-[26px] font-black text-ink-subtle/50 font-display">
                  {step.number}
                </span>
              </div>

              <div className="space-y-2">
                <h3 className="text-[18px] sm:text-[20px] font-bold text-ink-primary font-display">
                  {step.title}
                </h3>
                <p className="text-[15px] text-ink-secondary leading-relaxed">
                  {step.desc}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Why Valora is Different */}
      <div className="bg-surface rounded-2xl border border-ink-border p-6 sm:p-8 shadow-card space-y-6">
        <h2 className="text-[22px] sm:text-[24px] lg:text-[26px] font-bold text-ink-primary font-display flex items-center gap-2">
          <ShieldCheck className="w-6 h-6 text-brand-500" />
          <span>Por qué confiar en las estimaciones de Valora</span>
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 pt-2">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-[15px] font-bold text-ink-primary">
              <CheckCircle2 className="w-4 h-4 text-brand-500 shrink-0" />
              <span>44.836 ofertas reales</span>
            </div>
            <p className="text-[14px] text-ink-secondary leading-relaxed">
              Base de datos curada y desduplicada en las principales capitales colombianas.
            </p>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2 text-[15px] font-bold text-ink-primary">
              <CheckCircle2 className="w-4 h-4 text-brand-500 shrink-0" />
              <span>R² de 0.92 en zonas nuevas</span>
            </div>
            <p className="text-[14px] text-ink-secondary leading-relaxed">
              Alta correlación validada estadísticamente en pruebas ciegas fuera de muestra.
            </p>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2 text-[15px] font-bold text-ink-primary">
              <CheckCircle2 className="w-4 h-4 text-brand-500 shrink-0" />
              <span>Transparencia total</span>
            </div>
            <p className="text-[14px] text-ink-secondary leading-relaxed">
              Te mostramos los inmuebles comparables exactos y el nivel de confianza de cada dictamen.
            </p>
          </div>
        </div>
      </div>

      {/* Call to action */}
      <div className="text-center pt-2">
        <button
          type="button"
          onClick={onStartEstimate}
          className="inline-flex items-center gap-2 min-h-[50px] px-7 py-3.5 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-bold text-[15px] sm:text-[16px] shadow-card hover:shadow-card-hover transition-all"
        >
          <Sparkles className="w-4 h-4" />
          <span>Estimar mi inmueble ahora</span>
          <ArrowRight className="w-4 h-4 ml-1" />
        </button>
      </div>
    </div>
  );
};
