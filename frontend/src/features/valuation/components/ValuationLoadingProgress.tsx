import { useState, useEffect } from 'react';
import { Database, Cpu, CheckCircle2, ShieldCheck } from 'lucide-react';

interface ValuationLoadingProgressProps {
  ciudad?: string;
  sector?: string;
}

export const ValuationLoadingProgress: React.FC<ValuationLoadingProgressProps> = ({
  ciudad = 'tu ciudad',
  sector = 'tu sector',
}) => {
  const [progress, setProgress] = useState(12);
  const [currentPhase, setCurrentPhase] = useState(0);

  const phases = [
    {
      title: 'Geolocalización y entorno',
      desc: `Buscando ofertas recientes en el vecindario de ${sector}, ${ciudad}...`,
      icon: Database,
    },
    {
      title: 'Extracción de comparables similares',
      desc: 'Filtrando metrajes, habitaciones, estratos y amenidades cercanas...',
      icon: CheckCircle2,
    },
    {
      title: 'Inferencia de Machine Learning',
      desc: 'Ejecutando algoritmos Gradient Boosting para venta y arriendo...',
      icon: Cpu,
    },
    {
      title: 'Calibración de intervalos p10 - p90',
      desc: 'Calculando rango de negociación con 80% de confianza estadística...',
      icon: ShieldCheck,
    },
  ];

  useEffect(() => {
    // Progress bar increments smoothly
    const progressTimer = setInterval(() => {
      setProgress((prev) => {
        if (prev < 30) return prev + 6;
        if (prev < 65) return prev + 4;
        if (prev < 88) return prev + 2;
        if (prev < 96) return prev + 0.5;
        return prev;
      });
    }, 400);

    // Phases progress sequentially
    const phase1 = setTimeout(() => setCurrentPhase(1), 1500);
    const phase2 = setTimeout(() => setCurrentPhase(2), 3500);
    const phase3 = setTimeout(() => setCurrentPhase(3), 6000);

    return () => {
      clearInterval(progressTimer);
      clearTimeout(phase1);
      clearTimeout(phase2);
      clearTimeout(phase3);
    };
  }, []);

  return (
    <div className="p-8 sm:p-10 rounded-2xl bg-surface border border-ink-border shadow-card space-y-8 animate-fadeIn text-center">
      {/* Icon with animated pulse */}
      <div className="relative mx-auto w-16 h-16 flex items-center justify-center">
        <div className="absolute inset-0 rounded-2xl bg-brand-500/20 animate-ping opacity-50"></div>
        <div className="relative w-16 h-16 rounded-2xl bg-brand-50 border border-brand-200 flex items-center justify-center p-2.5 shadow-xs">
          <img
            src="/logo-casa.png"
            alt="Valora Casa"
            className="w-full h-full object-contain animate-pulse"
          />
        </div>
      </div>

      {/* Main Title & Phase Status */}
      <div className="space-y-2.5 max-w-lg mx-auto">
        <h3 className="text-[22px] sm:text-[24px] font-bold text-ink-primary font-display">
          Analizando tu inmueble con Machine Learning
        </h3>
        <p className="text-[15px] sm:text-[16px] text-ink-secondary leading-relaxed transition-all duration-300">
          {phases[currentPhase].desc}
        </p>
      </div>

      {/* BARRITA DE LOAD (Progress Bar) */}
      <div className="space-y-2.5 max-w-lg mx-auto">
        <div className="flex items-center justify-between text-[14px] sm:text-[15px] font-semibold">
          <span className="text-brand-700 flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-brand-500"></span>
            </span>
            <span>{phases[currentPhase].title}</span>
          </span>
          <span className="text-ink-primary tabular-nums font-extrabold text-[16px]">
            {Math.round(progress)} %
          </span>
        </div>

        {/* Progress track */}
        <div className="w-full h-3.5 bg-slate-100 rounded-full overflow-hidden p-0.5 border border-ink-border relative">
          <div
            className="h-full bg-gradient-to-r from-brand-600 via-brand-500 to-emerald-400 rounded-full transition-all duration-500 ease-out relative"
            style={{ width: `${progress}%` }}
          >
            {/* Shimmer animation highlight */}
            <div className="absolute inset-0 bg-white/30 rounded-full animate-pulse"></div>
          </div>
        </div>
      </div>

      {/* Steps indicator chips */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 max-w-xl mx-auto pt-2">
        {phases.map((ph, idx) => {
          const isDone = currentPhase > idx;
          const isCurrent = currentPhase === idx;

          return (
            <div
              key={idx}
              className={`p-3 rounded-xl border text-left transition-all ${
                isDone
                  ? 'bg-brand-50/80 border-brand-300 text-brand-800'
                  : isCurrent
                  ? 'bg-surface border-brand-500 ring-2 ring-brand-500/20 text-ink-primary shadow-xs'
                  : 'bg-canvas/50 border-ink-border text-ink-muted'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-[11px] font-bold uppercase tracking-wider">
                  Paso {idx + 1}
                </span>
                {isDone ? (
                  <CheckCircle2 className="w-4 h-4 text-brand-600" />
                ) : isCurrent ? (
                  <div className="w-3.5 h-3.5 rounded-full border-2 border-brand-500 border-t-transparent animate-spin"></div>
                ) : (
                  <span className="w-1.5 h-1.5 rounded-full bg-ink-subtle"></span>
                )}
              </div>
              <div className="text-[13px] font-bold truncate leading-tight">
                {ph.title}
              </div>
            </div>
          );
        })}
      </div>

      {/* Trust reassurance footer */}
      <div className="text-[13px] text-ink-muted max-w-sm mx-auto pt-2">
        Cotejando en tiempo real contra 44.836 ofertas validadas en Colombia.
      </div>
    </div>
  );
};
