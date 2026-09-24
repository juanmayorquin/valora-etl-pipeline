import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getHealth } from '../services/api';
import { useValuation } from '../features/valuation/hooks/useValuation';
import { useSavedProperties } from '../features/valuation/hooks/useSavedProperties';
import { ValuationWizard } from '../features/valuation/components/ValuationWizard';
import { PropertySummaryBadge } from '../features/valuation/components/PropertySummaryBadge';
import { ValuationResultCard } from '../features/valuation/components/ValuationResultCard';
import { ConfidenceIndicator } from '../features/valuation/components/ConfidenceIndicator';
import { InteractiveScenarios } from '../features/valuation/components/InteractiveScenarios';
import { ZoneComparisonView } from '../features/market/components/ZoneComparisonView';
import { ComparablesMapView } from '../features/geography/components/ComparablesMapView';
import { MethodologySection } from '../features/methodology/components/MethodologySection';
import { SavedPropertiesView } from '../features/valuation/components/SavedPropertiesView';
import { PropertyComparisonView } from '../features/valuation/components/PropertyComparisonView';
import { MarketZoneExplorer } from '../features/market/components/MarketZoneExplorer';
import { HowItWorksView } from '../features/methodology/components/HowItWorksView';
import { MethodologyFullView } from '../features/methodology/components/MethodologyFullView';
import { SettingsView } from '../features/settings/components/SettingsView';
import { Header } from '../components/Header';
import { Sidebar, NavigationTab } from '../components/Sidebar';
import {
  Sparkles,
  AlertCircle,
  Database,
  ShieldCheck,
  BarChart2,
  Search,
  CheckCircle2,
  PlusCircle,
} from 'lucide-react';

export function App() {
  const [activeTab, setActiveTab] = useState<NavigationTab>('nueva-estimacion');
  const [isSidebarOpenMobile, setIsSidebarOpenMobile] = useState<boolean>(false);
  const [prefilledLocation, setPrefilledLocation] = useState<{ ciudad: string; sector: string } | null>(null);
  const [saveToast, setSaveToast] = useState<string | null>(null);
  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    retry: false,
    refetchInterval: 2000,
    staleTime: 3000,
  });
  const backendStatus = healthQuery.isError || healthQuery.data?.status === 'error'
    ? 'error'
    : healthQuery.data?.status === 'ready'
      ? 'ready'
      : 'loading';

  const {
    objective,
    lastRequest,
    valuationResult,
    isEditing,
    setIsEditing,
    errorMessage,
    isLoading,
    isError,
    startValuation,
    recalculateScenario,
    toggleEdit,
    loadExistingValuation,
    resetValuation,
  } = useValuation();

  const {
    savedProperties,
    compareIds,
    saveProperty,
    removeProperty,
    isSaved,
    toggleCompare,
    clearCompare,
    clearAllSaved,
  } = useSavedProperties();

  // Save current valuation handler
  const handleSaveCurrentProperty = () => {
    if (!lastRequest || !valuationResult) return;
    const saved = saveProperty(lastRequest, valuationResult, objective);
    setSaveToast(`¡"${saved.title}" se guardó en Mis Inmuebles!`);
    setTimeout(() => setSaveToast(null), 3500);
  };

  // Compare current property handler
  const handleCompareCurrentProperty = () => {
    if (!lastRequest || !valuationResult) return;
    const saved = saveProperty(lastRequest, valuationResult, objective);
    if (!compareIds.includes(saved.id)) {
      toggleCompare(saved.id);
    }
    setActiveTab('comparar-inmuebles');
  };

  // From Market Explorer to Estimate
  const handleEstimateInSector = (ciudad: string, sector: string) => {
    setPrefilledLocation({ ciudad, sector });
    resetValuation();
    setActiveTab('nueva-estimacion');
  };

  // From Saved Properties to View Details
  const handleViewSavedDetails = (req: any, res: any, obj: any) => {
    loadExistingValuation(req, res, obj);
    setActiveTab('nueva-estimacion');
  };

  // Check if current result is saved
  const currentlySaved = isSaved(lastRequest);

  const tabTitles: Record<NavigationTab, string> = {
    'nueva-estimacion': 'Nueva Estimación',
    'mis-inmuebles': 'Mis Inmuebles Guardados',
    'comparar-inmuebles': 'Comparador de Inmuebles',
    'mercado-zona': 'Mercado por Zona',
    'como-funciona': 'Cómo Funciona',
    'metodologia': 'Metodología Analítica',
    'configuracion': 'Configuración',
  };

  return (
    <div className="min-h-screen bg-canvas text-ink-primary flex flex-col font-sans selection:bg-brand-100 selection:text-brand-800">
      {/* Top Header */}
      <Header
        onToggleSidebar={() => setIsSidebarOpenMobile(!isSidebarOpenMobile)}
        isSidebarOpen={isSidebarOpenMobile}
        savedCount={savedProperties.length}
        compareCount={compareIds.length}
        onNavigate={(tab) => setActiveTab(tab as NavigationTab)}
        activeTitle={tabTitles[activeTab]}
        backendStatus={backendStatus}
        isLoading={isLoading}
      />

      {/* Main Container with Sidebar + Content */}
      <div className="flex-1 flex max-w-7xl w-full mx-auto">
        {/* Navigation Sidebar */}
        <Sidebar
          activeTab={activeTab}
          onSelectTab={(tab) => {
            setActiveTab(tab);
            setIsSidebarOpenMobile(false);
          }}
          isOpenMobile={isSidebarOpenMobile}
          onCloseMobile={() => setIsSidebarOpenMobile(false)}
          savedCount={savedProperties.length}
          compareCount={compareIds.length}
        />

        {/* Content Area */}
        <main className="flex-1 min-w-0 p-3.5 sm:p-6 lg:p-8 space-y-6">
          {/* Toast Notification */}
          {saveToast && (
            <div className="p-4 rounded-xl bg-brand-50 border border-brand-200 text-brand-800 text-[15px] font-semibold flex items-center justify-between shadow-card animate-fadeIn">
              <div className="flex items-center gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-brand-600 shrink-0" />
                <span>{saveToast}</span>
              </div>
              <button
                type="button"
                onClick={() => setActiveTab('mis-inmuebles')}
                className="underline hover:text-brand-900 text-[15px] font-bold"
              >
                Ver guardados →
              </button>
            </div>
          )}

          {/* ===================== TAB: NUEVA ESTIMACIÓN ===================== */}
          {activeTab === 'nueva-estimacion' && (
            <div className="space-y-6 animate-fadeIn">
              {/* Error Message */}
              {isError && (
                <div className="p-4 sm:p-5 rounded-2xl bg-danger-50 border border-danger-100 text-danger-600 text-[15px] flex items-start gap-3 shadow-xs">
                  <AlertCircle className="w-5 h-5 text-danger-500 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <h4 className="font-bold text-ink-primary text-[16px]">No se pudo procesar la estimación</h4>
                    <p className="text-[14px] text-ink-secondary">
                      {errorMessage ||
                        'No pudimos calcular la estimación. Verifica la ciudad y el sector o intenta nuevamente.'}
                    </p>
                    <button
                      type="button"
                      onClick={() => setIsEditing(true)}
                      className="mt-2 text-[14px] font-semibold px-3.5 py-2 rounded-lg bg-surface border border-ink-border text-ink-primary hover:bg-white transition-colors"
                    >
                      Revisar formulario
                    </button>
                  </div>
                </div>
              )}

              {/* Initial State: Hero + Centered Form */}
              {!valuationResult && (
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
                  {/* Left Column: Presentation & Value Proposition (5 cols) */}
                  <div className="lg:col-span-5 space-y-6">
                    <div className="p-7 sm:p-8 rounded-2xl bg-surface border border-ink-border shadow-card space-y-5">
                      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-100 text-brand-700 text-xs font-semibold">
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>Valoración Inmobiliaria Inteligente</span>
                      </div>

                      <div className="space-y-4">
                        <h1 className="text-[34px] sm:text-[44px] lg:text-[48px] font-extrabold text-ink-primary font-display tracking-tight leading-[1.15]">
                          ¿Cuánto vale tu inmueble hoy en Colombia?
                        </h1>
                        <p className="text-[16px] text-ink-secondary leading-relaxed">
                          Conoce el precio estimado de venta y canon de arriendo con respaldo estadístico real. Comparamos tu propiedad frente al mercado de su vecindario inmediato.
                        </p>
                      </div>

                      {/* Engine Trust Metrics */}
                      <div className="grid grid-cols-3 gap-3 pt-5 border-t border-ink-border">
                        <div className="space-y-0.5">
                          <span className="text-[12px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1">
                            <Database className="w-3.5 h-3.5 text-brand-500" /> Ofertas
                          </span>
                          <div className="text-[22px] sm:text-[24px] font-extrabold text-ink-primary tabular-nums">44.836</div>
                          <p className="text-[13px] sm:text-[14px] text-ink-secondary">Datos limpios</p>
                        </div>

                        <div className="space-y-0.5">
                          <span className="text-[12px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1">
                            <ShieldCheck className="w-3.5 h-3.5 text-brand-500" /> Precisión
                          </span>
                          <div className="text-[22px] sm:text-[24px] font-extrabold text-brand-600 tabular-nums">R² 0.92</div>
                          <p className="text-[13px] sm:text-[14px] text-ink-secondary">Zonas nuevas</p>
                        </div>

                        <div className="space-y-0.5">
                          <span className="text-[12px] font-bold uppercase tracking-wider text-ink-muted flex items-center gap-1">
                            <BarChart2 className="w-3.5 h-3.5 text-brand-500" /> Rango
                          </span>
                          <div className="text-[22px] sm:text-[24px] font-extrabold text-ink-primary tabular-nums">80 %</div>
                          <p className="text-[13px] sm:text-[14px] text-ink-secondary">p10 a p90</p>
                        </div>
                      </div>
                    </div>

                    {/* How It Works Brief Card */}
                    <div className="p-6 rounded-2xl bg-surface border border-ink-border shadow-card space-y-3.5">
                      <h3 className="text-[18px] sm:text-[20px] font-bold text-ink-primary font-display">
                        El flujo de decisión Valora:
                      </h3>
                      <div className="space-y-2.5 text-[15px] text-ink-secondary leading-relaxed">
                        <div className="flex items-start gap-2.5">
                          <span className="w-6 h-6 rounded-full bg-brand-100 text-brand-700 font-bold flex items-center justify-center text-[12px] shrink-0 mt-0.5">
                            1
                          </span>
                          <span><strong>Estimar:</strong> Ingresa las especificaciones de tu propiedad.</span>
                        </div>
                        <div className="flex items-start gap-2.5">
                          <span className="w-6 h-6 rounded-full bg-brand-100 text-brand-700 font-bold flex items-center justify-center text-[12px] shrink-0 mt-0.5">
                            2
                          </span>
                          <span><strong>Guardar:</strong> Conserva la ficha en tu historial privado.</span>
                        </div>
                        <div className="flex items-start gap-2.5">
                          <span className="w-6 h-6 rounded-full bg-brand-100 text-brand-700 font-bold flex items-center justify-center text-[12px] shrink-0 mt-0.5">
                            3
                          </span>
                          <span><strong>Comparar:</strong> Contrasta precios por m² y rentabilidades.</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Right Column: Step-by-step Wizard Form (7 cols) */}
                  <div className="lg:col-span-7">
                      <ValuationWizard
                        onSubmit={startValuation}
                        isLoading={isLoading}
                        backendReady={backendStatus === 'ready'}
                        initialObjective={objective}
                      initialValues={prefilledLocation ? { ciudad: prefilledLocation.ciudad, sector: prefilledLocation.sector } : undefined}
                    />
                  </div>
                </div>
              )}

              {/* State with Results Active */}
              {valuationResult && lastRequest && (
                <div className="space-y-6 animate-fadeIn">
                  {/* Top action: new estimate button */}
                  <div className="flex items-center justify-between pb-2">
                    <button
                      type="button"
                      onClick={resetValuation}
                      className="inline-flex items-center gap-2 min-h-[44px] px-4 py-2.5 rounded-xl bg-surface border border-ink-border text-[15px] font-semibold text-ink-secondary hover:text-ink-primary hover:bg-canvas transition-colors shadow-xs"
                    >
                      <PlusCircle className="w-4 h-4 text-brand-500" />
                      <span>Calcular otro inmueble</span>
                    </button>
                  </div>

                  {/* 1. Resumen de datos ingresados */}
                  <PropertySummaryBadge
                    request={lastRequest}
                    objective={objective}
                    onEditClick={toggleEdit}
                  />

                  {/* 2. Formulario en modo edición si se desea modificar */}
                  {isEditing && (
                    <div className="p-6 rounded-2xl bg-surface border border-brand-500/30 shadow-card animate-fadeIn">
                      <div className="flex items-center justify-between pb-4 border-b border-ink-border mb-6">
                        <h3 className="text-base font-bold text-ink-primary flex items-center gap-2 font-display">
                          <Search className="w-4 h-4 text-brand-500" /> Modificar especificaciones de la ficha
                        </h3>
                        <button
                          type="button"
                          onClick={toggleEdit}
                          className="text-xs text-ink-secondary hover:text-ink-primary"
                        >
                          Cerrar edición
                        </button>
                      </div>
                      <ValuationWizard
                        onSubmit={startValuation}
                        isLoading={isLoading}
                        backendReady={backendStatus === 'ready'}
                        initialValues={lastRequest}
                        initialObjective={objective}
                      />
                    </div>
                  )}

                  {/* 3. Indicador de Calidad y Confianza */}
                  <ConfidenceIndicator result={valuationResult} />

                  {/* 4. Dictamen principal de precio */}
                  <ValuationResultCard
                    result={valuationResult}
                    objective={objective}
                    lastRequest={lastRequest}
                    onSave={handleSaveCurrentProperty}
                    isSaved={currentlySaved}
                    onCompare={handleCompareCurrentProperty}
                  />

                  {/* 5. Escenarios interactivos */}
                  <InteractiveScenarios
                    currentRequest={lastRequest}
                    result={valuationResult}
                    objective={objective}
                    onRecalculate={recalculateScenario}
                    isRecalculating={isLoading}
                  />

                  {/* 6. Comparación con la zona e Histograma */}
                  <ZoneComparisonView result={valuationResult} objective={objective} />

                  {/* 7. Mapa interactivo de comparables georreferenciados */}
                  <ComparablesMapView result={valuationResult} objective={objective} />

                  {/* 8. Metodología y alcance */}
                  <MethodologySection />
                </div>
              )}
            </div>
          )}

          {/* ===================== TAB: MIS INMUEBLES ===================== */}
          {activeTab === 'mis-inmuebles' && (
            <SavedPropertiesView
              properties={savedProperties}
              compareIds={compareIds}
              onToggleCompare={toggleCompare}
              onRemoveProperty={removeProperty}
              onViewDetails={handleViewSavedDetails}
              onNewEstimate={() => {
                resetValuation();
                setActiveTab('nueva-estimacion');
              }}
              onGoToCompare={() => setActiveTab('comparar-inmuebles')}
            />
          )}

          {/* ===================== TAB: COMPARAR INMUEBLES ===================== */}
          {activeTab === 'comparar-inmuebles' && (
            <PropertyComparisonView
              savedProperties={savedProperties}
              compareIds={compareIds}
              onToggleCompare={toggleCompare}
              onClearCompare={clearCompare}
              onViewDetails={handleViewSavedDetails}
              onNewEstimate={() => {
                resetValuation();
                setActiveTab('nueva-estimacion');
              }}
            />
          )}

          {/* ===================== TAB: MERCADO POR ZONA ===================== */}
          {activeTab === 'mercado-zona' && (
            <MarketZoneExplorer onSelectSectorForEstimate={handleEstimateInSector} />
          )}

          {/* ===================== TAB: CÓMO FUNCIONA ===================== */}
          {activeTab === 'como-funciona' && (
            <HowItWorksView
              onStartEstimate={() => {
                resetValuation();
                setActiveTab('nueva-estimacion');
              }}
            />
          )}

          {/* ===================== TAB: METODOLOGÍA ===================== */}
          {activeTab === 'metodologia' && <MethodologyFullView />}

          {/* ===================== TAB: CONFIGURACIÓN ===================== */}
          {activeTab === 'configuracion' && (
            <SettingsView
              savedProperties={savedProperties}
              onClearAllSaved={clearAllSaved}
            />
          )}
        </main>
      </div>

      {/* Clean Corporate Footer */}
      <footer className="border-t border-ink-border py-8 bg-surface mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-[14px] text-ink-secondary">
          <p>© 2026 VALORA · Valoración Inteligente de Inmuebles en Colombia</p>
          <p>
            Herramienta analítica de apoyo a la decisión inmobiliaria · Cobertura residencial urbana
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
