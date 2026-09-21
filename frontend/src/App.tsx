import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { postValuar } from './services/api';
import { ValuationRequest, ValuationResponse } from './types/valuation';
import { Header } from './components/Header';
import { ValuationForm } from './components/ValuationForm';
import { ValuationCard } from './components/ValuationCard';
import { ZoneComparison } from './components/ZoneComparison';
import { ComparablesMap } from './components/ComparablesMap';
import { Sparkles, AlertCircle, BarChart2, ShieldCheck, Database } from 'lucide-react';

export function App() {
  const [valuationResult, setValuationResult] = useState<ValuationResponse | null>(null);

  const mutation = useMutation({
    mutationFn: (data: ValuationRequest) => postValuar(data),
    onSuccess: (data) => {
      setValuationResult(data);
    },
  });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Header />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Columna Izquierda: Formulario de Ficha (5 cols) */}
          <div className="lg:col-span-5 lg:sticky lg:top-24">
            <ValuationForm
              onSubmit={(data) => mutation.mutate(data)}
              isLoading={mutation.isPending}
            />
          </div>

          {/* Columna Derecha: Reporte y Resultados (7 cols) */}
          <div className="lg:col-span-7 space-y-6">
            {/* Estado de Error */}
            {mutation.isError && (
              <div className="p-4 rounded-2xl bg-red-950/40 border border-red-800/80 text-red-200 text-sm flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-bold">Error al procesar la valuación</h4>
                  <p className="text-xs text-red-300 mt-1">
                    {(mutation.error as any)?.response?.data?.detail ||
                      'Ocurrió un error de comunicación con el motor de inferencia.'}
                  </p>
                </div>
              </div>
            )}

            {/* Skeleton Loading */}
            {mutation.isPending && (
              <div className="space-y-4 animate-pulse">
                <div className="h-44 rounded-2xl bg-slate-900 border border-slate-800"></div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="h-40 rounded-2xl bg-slate-900 border border-slate-800"></div>
                  <div className="h-40 rounded-2xl bg-slate-900 border border-slate-800"></div>
                </div>
                <div className="h-64 rounded-2xl bg-slate-900 border border-slate-800"></div>
              </div>
            )}

            {/* Estado Inicial: Portada / Bienvenida */}
            {!mutation.isPending && !valuationResult && (
              <div className="p-8 sm:p-10 rounded-2xl bg-slate-900/60 border border-slate-800/80 shadow-2xl relative overflow-hidden space-y-6">
                <div className="absolute -right-10 -bottom-10 w-64 h-64 bg-emerald-500/5 rounded-full blur-3xl pointer-events-none"></div>

                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-xs font-semibold border border-emerald-500/20">
                  <Sparkles className="w-3.5 h-3.5" />
                  Estimación con rango, y la evidencia al lado
                </div>

                <div className="space-y-3">
                  <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight leading-tight">
                    Cuánto vale un inmueble,<br />
                    <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-teal-200">
                      y cuánto vale alrededor.
                    </span>
                  </h1>
                  <p className="text-sm text-slate-400 leading-relaxed max-w-xl">
                    Describe el inmueble en el panel izquierdo. El modelo de Machine Learning devuelve el precio de venta y el canon de arriendo con un rango del 80 %, y los compara frente a los anuncios reales publicados en la misma zona.
                  </p>
                </div>

                {/* Métricas clave del Lakehouse */}
                <div className="grid grid-cols-3 gap-4 pt-4 border-t border-slate-800">
                  <div className="space-y-1">
                    <span className="text-[11px] font-semibold uppercase text-slate-500 flex items-center gap-1">
                      <Database className="w-3 h-3 text-emerald-400" /> Anuncios
                    </span>
                    <div className="text-2xl font-black text-white">44.836</div>
                    <p className="text-[10px] text-slate-400">Dataset Gold depurado</p>
                  </div>

                  <div className="space-y-1">
                    <span className="text-[11px] font-semibold uppercase text-slate-500 flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3 text-emerald-400" /> R² Modelo
                    </span>
                    <div className="text-2xl font-black text-emerald-400">0.92</div>
                    <p className="text-[10px] text-slate-400">En sectores no vistos</p>
                  </div>

                  <div className="space-y-1">
                    <span className="text-[11px] font-semibold uppercase text-slate-500 flex items-center gap-1">
                      <BarChart2 className="w-3 h-3 text-emerald-400" /> Confianza
                    </span>
                    <div className="text-2xl font-black text-white">80 %</div>
                    <p className="text-[10px] text-slate-400">Rango calibrado p10-p90</p>
                  </div>
                </div>
              </div>
            )}

            {/* Resultados de Valuación */}
            {!mutation.isPending && valuationResult && (
              <div className="space-y-6">
                <ValuationCard result={valuationResult} />
                <ZoneComparison result={valuationResult} />
                <ComparablesMap result={valuationResult} />
              </div>
            )}
          </div>
        </div>
      </main>

      <footer className="border-t border-slate-800/80 py-6 text-center text-xs text-slate-500">
        <p>Valora ETL Pipeline · Lakehouse + Machine Learning Inmobiliario</p>
      </footer>
    </div>
  );
}

export default App;
