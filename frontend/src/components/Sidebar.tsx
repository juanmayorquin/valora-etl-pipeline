import React from 'react';
import {
  Sparkles,
  Bookmark,
  Scale,
  MapPin,
  HelpCircle,
  ShieldCheck,
  Settings,
  X,
  Database,
} from 'lucide-react';
import { Logo } from './Logo';

export type NavigationTab =
  | 'nueva-estimacion'
  | 'mis-inmuebles'
  | 'comparar-inmuebles'
  | 'mercado-zona'
  | 'como-funciona'
  | 'metodologia'
  | 'configuracion';

interface SidebarProps {
  activeTab: NavigationTab;
  onSelectTab: (tab: NavigationTab) => void;
  isOpenMobile?: boolean;
  onCloseMobile?: () => void;
  savedCount?: number;
  compareCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
  isOpenMobile = false,
  onCloseMobile,
  savedCount = 0,
  compareCount = 0,
}) => {
  const navItemClass = (tab: NavigationTab) => {
    const isActive = activeTab === tab;
    return `w-full flex items-center justify-between px-3.5 py-3 rounded-xl text-[15px] font-medium min-h-[46px] transition-all duration-150 ${
      isActive
        ? 'bg-brand-100 text-brand-700 font-semibold shadow-xs'
        : 'text-ink-secondary hover:text-ink-primary hover:bg-canvas'
    }`;
  };

  const content = (
    <div className="h-full flex flex-col justify-between p-4 sm:p-5 select-none">
      <div className="space-y-6">
        {/* Header with Logo */}
        <div className="flex items-center justify-between pb-2 border-b border-ink-border/60">
          <div
            className="cursor-pointer"
            onClick={() => {
              onSelectTab('nueva-estimacion');
              onCloseMobile?.();
            }}
          >
            <Logo variant="primary" size="md" />
          </div>
          {onCloseMobile && (
            <button
              type="button"
              onClick={onCloseMobile}
              className="lg:hidden p-2 rounded-xl text-ink-muted hover:text-ink-primary hover:bg-canvas"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Section 1: Main Action */}
        <div className="space-y-1">
          <button
            type="button"
            onClick={() => {
              onSelectTab('nueva-estimacion');
              onCloseMobile?.();
            }}
            className={navItemClass('nueva-estimacion')}
          >
            <div className="flex items-center gap-3">
              <Sparkles className={`w-4 h-4 ${activeTab === 'nueva-estimacion' ? 'text-brand-600' : 'text-brand-500'}`} />
              <span>Nueva estimación</span>
            </div>
            <span className="text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-brand-500 text-white">
              Inicio
            </span>
          </button>
        </div>

        {/* Section 2: Management & Decision Tools */}
        <div className="space-y-1">
          <div className="px-3 pb-1.5 text-[12px] font-bold uppercase tracking-wider text-ink-muted">
            Herramientas
          </div>

          <button
            type="button"
            onClick={() => {
              onSelectTab('mis-inmuebles');
              onCloseMobile?.();
            }}
            className={navItemClass('mis-inmuebles')}
          >
            <div className="flex items-center gap-3">
              <Bookmark className={`w-4 h-4 ${activeTab === 'mis-inmuebles' ? 'text-brand-600' : 'text-ink-secondary'}`} />
              <span>Mis inmuebles</span>
            </div>
            {savedCount > 0 && (
              <span className="px-2 py-0.5 rounded-full text-[12px] font-bold bg-brand-200/80 text-brand-800">
                {savedCount}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => {
              onSelectTab('comparar-inmuebles');
              onCloseMobile?.();
            }}
            className={navItemClass('comparar-inmuebles')}
          >
            <div className="flex items-center gap-3">
              <Scale className={`w-4 h-4 ${activeTab === 'comparar-inmuebles' ? 'text-chart-600' : 'text-ink-secondary'}`} />
              <span>Comparar inmuebles</span>
            </div>
            {compareCount > 0 && (
              <span className="px-2 py-0.5 rounded-full text-[12px] font-bold bg-chart-100 text-chart-600">
                {compareCount}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => {
              onSelectTab('mercado-zona');
              onCloseMobile?.();
            }}
            className={navItemClass('mercado-zona')}
          >
            <div className="flex items-center gap-3">
              <MapPin className={`w-4 h-4 ${activeTab === 'mercado-zona' ? 'text-brand-600' : 'text-ink-secondary'}`} />
              <span>Mercado por zona</span>
            </div>
          </button>
        </div>

        {/* Section 3: Knowledge & Transparency */}
        <div className="space-y-1">
          <div className="px-3 pb-1.5 text-[12px] font-bold uppercase tracking-wider text-ink-muted">
            Transparencia
          </div>

          <button
            type="button"
            onClick={() => {
              onSelectTab('como-funciona');
              onCloseMobile?.();
            }}
            className={navItemClass('como-funciona')}
          >
            <div className="flex items-center gap-3">
              <HelpCircle className={`w-4 h-4 ${activeTab === 'como-funciona' ? 'text-brand-600' : 'text-ink-secondary'}`} />
              <span>Cómo funciona</span>
            </div>
          </button>

          <button
            type="button"
            onClick={() => {
              onSelectTab('metodologia');
              onCloseMobile?.();
            }}
            className={navItemClass('metodologia')}
          >
            <div className="flex items-center gap-3">
              <ShieldCheck className={`w-4 h-4 ${activeTab === 'metodologia' ? 'text-brand-600' : 'text-ink-secondary'}`} />
              <span>Metodología</span>
            </div>
          </button>
        </div>
      </div>

      {/* Bottom Section: Settings & Model Status */}
      <div className="space-y-3 pt-4 border-t border-ink-border/60">
        <button
          type="button"
          onClick={() => {
            onSelectTab('configuracion');
            onCloseMobile?.();
          }}
          className={navItemClass('configuracion')}
        >
          <div className="flex items-center gap-3">
            <Settings className={`w-4 h-4 ${activeTab === 'configuracion' ? 'text-brand-600' : 'text-ink-secondary'}`} />
            <span>Configuración</span>
          </div>
        </button>

        {/* Subtle trust badge */}
        <div className="p-3.5 rounded-xl bg-canvas border border-ink-border/60 space-y-1">
          <div className="flex items-center gap-1.5 text-[13px] font-bold text-ink-primary">
            <Database className="w-3.5 h-3.5 text-brand-500" />
            <span>44.836 Ofertas Validadas</span>
          </div>
          <p className="text-[12px] text-ink-muted leading-tight">
            Algoritmo calibrado con datos urbanos en Colombia.
          </p>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar (Permanent) */}
      <aside className="hidden lg:flex flex-col w-64 shrink-0 bg-surface border-r border-ink-border min-h-[calc(100vh-4rem)]">
        {content}
      </aside>

      {/* Mobile Drawer (Collapsible Modal) */}
      {isOpenMobile && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-ink-primary/30 backdrop-blur-xs transition-opacity"
            onClick={onCloseMobile}
          />
          {/* Drawer content */}
          <div className="relative w-72 max-w-[85vw] bg-surface h-full shadow-2xl z-10 flex flex-col">
            {content}
          </div>
        </div>
      )}
    </>
  );
};
