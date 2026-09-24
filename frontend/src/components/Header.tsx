import React from 'react';
import { Menu, X, Bookmark, Scale } from 'lucide-react';

interface HeaderProps {
  onToggleSidebar?: () => void;
  isSidebarOpen?: boolean;
  savedCount?: number;
  compareCount?: number;
  onNavigate?: (tab: string) => void;
  activeTitle?: string;
  backendStatus?: 'loading' | 'ready' | 'error';
  isLoading?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  onToggleSidebar,
  isSidebarOpen,
  savedCount = 0,
  compareCount = 0,
  onNavigate,
  activeTitle = 'Valoración Inteligente',
  backendStatus = 'loading',
  isLoading = false,
}) => {
  const statusCopy = backendStatus === 'ready' ? 'Motor listo' : backendStatus === 'error' ? 'Motor no disponible' : 'Conectando con el motor';
  const statusColor = backendStatus === 'ready' ? 'bg-brand-500' : backendStatus === 'error' ? 'bg-danger-500' : 'bg-warning-500';
  return (
    <header className="sticky top-0 z-40 bg-surface/95 backdrop-blur-md border-b border-ink-border transition-colors relative">
      {/* Top Progress Loading Bar */}
      {isLoading && (
        <div className="absolute top-0 left-0 right-0 h-1 bg-brand-100 overflow-hidden z-50">
          <div className="h-full bg-gradient-to-r from-brand-600 via-brand-500 to-emerald-400 w-full animate-pulse"></div>
        </div>
      )}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Left: Mobile Toggle, Imagen de la Casa (Isotipo) y Título de Sección */}
        <div className="flex items-center gap-3">
          {onToggleSidebar && (
            <button
              type="button"
              onClick={onToggleSidebar}
              className="lg:hidden p-2.5 min-h-[44px] min-w-[44px] flex items-center justify-center rounded-xl text-ink-secondary hover:text-ink-primary hover:bg-canvas transition-colors border border-ink-border"
              aria-label="Abrir menú"
            >
              {isSidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          )}

          {/* Logo de la casa del encabezado solicitado por el usuario */}
          <div
            className="flex items-center gap-2.5 cursor-pointer select-none group"
            onClick={() => onNavigate?.('nueva-estimacion')}
            title="Valora - Ir al inicio"
          >
            <img
              src="/logo-casa.png"
              alt="Valora"
              className="h-9 sm:h-10 w-auto object-contain transition-transform group-hover:scale-105"
            />

            <div className="flex items-center gap-2">
              <span className="hidden sm:inline-flex font-bold text-[15px] text-brand-700 font-display">
                Valora
              </span>
              <span className="hidden sm:inline text-ink-subtle">|</span>
              <span className="text-[15px] font-bold text-ink-primary">
                {activeTitle}
              </span>
            </div>
          </div>
        </div>

        {/* Right: Quick shortcuts & Real-time status */}
        <div className="flex items-center gap-2 sm:gap-4 text-[15px]">
          {onNavigate && (
            <div className="flex items-center gap-1.5 sm:gap-2">
              <button
                type="button"
                onClick={() => onNavigate('mis-inmuebles')}
                className="inline-flex items-center gap-1.5 min-h-[44px] px-3.5 py-2 rounded-xl text-ink-secondary hover:text-ink-primary hover:bg-canvas transition-colors border border-transparent hover:border-ink-border text-[15px] font-medium"
                title="Mis Inmuebles Guardados"
              >
                <Bookmark className="w-4 h-4 text-brand-500" />
                <span className="hidden sm:inline">Mis Inmuebles</span>
                {savedCount > 0 && (
                  <span className="ml-0.5 px-2 py-0.5 rounded-full bg-brand-100 text-brand-700 font-bold text-[13px]">
                    {savedCount}
                  </span>
                )}
              </button>

              <button
                type="button"
                onClick={() => onNavigate('comparar-inmuebles')}
                className="inline-flex items-center gap-1.5 min-h-[44px] px-3.5 py-2 rounded-xl text-ink-secondary hover:text-ink-primary hover:bg-canvas transition-colors border border-transparent hover:border-ink-border text-[15px] font-medium"
                title="Comparar Inmuebles"
              >
                <Scale className="w-4 h-4 text-chart-500" />
                <span className="hidden sm:inline">Comparar</span>
                {compareCount > 0 && (
                  <span className="ml-0.5 px-2 py-0.5 rounded-full bg-chart-100 text-chart-600 font-bold text-[13px]">
                    {compareCount}
                  </span>
                )}
              </button>
            </div>
          )}

          {/* Real-time backend status badge */}
          <div className="flex items-center gap-2 pl-3 border-l border-ink-border text-[13px]">
            <span className="relative flex h-2.5 w-2.5">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${statusColor} opacity-75`}></span>
              <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${statusColor}`}></span>
            </span>
            <span className="text-ink-secondary font-medium hidden md:inline">
              {statusCopy}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};
