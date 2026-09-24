import { useState } from 'react';
import {
  Settings,
  Database,
  Trash2,
  Download,
  CheckCircle,
  Server,
} from 'lucide-react';
import { SavedProperty } from '../../valuation/hooks/useSavedProperties';

interface SettingsViewProps {
  savedProperties: SavedProperty[];
  onClearAllSaved: () => void;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  savedProperties,
  onClearAllSaved,
}) => {
  const [clearedToast, setClearedToast] = useState(false);

  const handleExportData = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(savedProperties, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `valora_inmuebles_${new Date().toISOString().slice(0, 10)}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const handleClear = () => {
    if (confirm('¿Estás seguro de que deseas eliminar todos los inmuebles guardados? Esta acción no se puede deshacer.')) {
      onClearAllSaved();
      setClearedToast(true);
      setTimeout(() => setClearedToast(false), 3000);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 py-4 animate-fadeIn">
      {/* Header */}
      <div className="bg-surface p-5 sm:p-6 rounded-2xl border border-ink-border shadow-card space-y-2">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-brand-100 text-brand-700 text-[13px] font-semibold">
          <Settings className="w-3.5 h-3.5" />
          <span>Preferencias y Datos</span>
        </div>
        <h1 className="text-[22px] sm:text-[24px] lg:text-[26px] font-bold text-ink-primary font-display">
          Configuración
        </h1>
        <p className="text-[15px] text-ink-secondary">
          Gestiona los datos guardados en tu navegador y consulta los parámetros del motor Valora.
        </p>
      </div>

      {clearedToast && (
        <div className="p-4 rounded-xl bg-brand-50 border border-brand-200 text-brand-800 text-[14px] flex items-center gap-2">
          <CheckCircle className="w-4 h-4 text-brand-600" />
          <span>Se ha limpiado el historial de inmuebles guardados correctamente.</span>
        </div>
      )}

      {/* Storage Management Section */}
      <div className="bg-surface p-5 sm:p-6 rounded-2xl border border-ink-border shadow-card space-y-4">
        <h2 className="text-[18px] sm:text-[20px] font-bold text-ink-primary font-display flex items-center gap-2">
          <Database className="w-4 h-4 text-brand-500" />
          <span>Gestión de Inmuebles Guardados</span>
        </h2>
        <p className="text-[14px] text-ink-secondary leading-relaxed">
          Tus estimaciones se guardan localmente en tu navegador para proteger tu privacidad. No enviamos datos personales a servidores externos.
        </p>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl bg-canvas border border-ink-border">
          <div>
            <div className="text-[15px] font-bold text-ink-primary">
              {savedProperties.length} {savedProperties.length === 1 ? 'inmueble guardado' : 'inmuebles guardados'}
            </div>
            <div className="text-[13px] text-ink-muted mt-0.5">
              Almacenamiento seguro en LocalStorage
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              type="button"
              onClick={handleExportData}
              disabled={savedProperties.length === 0}
              className="inline-flex items-center gap-1.5 min-h-[44px] px-4 py-2 rounded-xl text-[14px] sm:text-[15px] font-semibold bg-surface hover:bg-white text-ink-primary border border-ink-border shadow-xs disabled:opacity-40 transition-colors"
            >
              <Download className="w-4 h-4 text-brand-500" />
              <span>Exportar JSON</span>
            </button>

            <button
              type="button"
              onClick={handleClear}
              disabled={savedProperties.length === 0}
              className="inline-flex items-center gap-1.5 min-h-[44px] px-4 py-2 rounded-xl text-[14px] sm:text-[15px] font-semibold text-danger-500 hover:text-danger-600 bg-danger-50 hover:bg-danger-100/80 disabled:opacity-40 transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              <span>Limpiar todo</span>
            </button>
          </div>
        </div>
      </div>

      {/* Engine & Diagnostics Section */}
      <div className="bg-surface p-5 sm:p-6 rounded-2xl border border-ink-border shadow-card space-y-4">
        <h2 className="text-[18px] sm:text-[20px] font-bold text-ink-primary font-display flex items-center gap-2">
          <Server className="w-4 h-4 text-brand-500" />
          <span>Información del Sistema</span>
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-[14px]">
          <div className="p-4 rounded-xl bg-canvas border border-ink-border space-y-1">
            <span className="text-ink-muted text-[12px] block">Modelo Predictivo</span>
            <span className="font-bold text-ink-primary block text-[15px]">LightGBM Gradient Boosting Cuantílico</span>
            <span className="text-[12px] text-ink-secondary">Cuantiles p10, p50 y p90</span>
          </div>

          <div className="p-4 rounded-xl bg-canvas border border-ink-border space-y-1">
            <span className="text-ink-muted text-[12px] block">Base de Comparables</span>
            <span className="font-bold text-ink-primary block text-[15px]">44.836 ofertas curadas</span>
            <span className="text-[12px] text-ink-secondary">Colombia (Bogotá, Medellín, Cali, etc.)</span>
          </div>

          <div className="p-4 rounded-xl bg-canvas border border-ink-border space-y-1">
            <span className="text-ink-muted text-[12px] block">Moneda de Cálculo</span>
            <span className="font-bold text-ink-primary block text-[15px]">Pesos Colombianos (COP)</span>
            <span className="text-[12px] text-ink-secondary">Formato estándar nacional ($)</span>
          </div>

          <div className="p-4 rounded-xl bg-canvas border border-ink-border space-y-1">
            <span className="text-ink-muted text-[12px] block">Versión de la Interfaz</span>
            <span className="font-bold text-ink-primary block text-[15px]">Valora Web 1.2 (Diseño Claro)</span>
            <span className="text-[12px] text-ink-secondary">Build 2026 · Vite + React + Tailwind</span>
          </div>
        </div>
      </div>
    </div>
  );
};
