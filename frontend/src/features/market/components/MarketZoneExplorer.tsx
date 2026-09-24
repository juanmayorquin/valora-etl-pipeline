import { useState, useEffect } from 'react';
import {
  MapPin,
  Search,
  Building,
  Database,
  ArrowRight,
  Loader2,
} from 'lucide-react';
import { getCiudades, getSectores } from '../../../services/api';
import { CiudadCatalogItem, SectorCatalogItem } from '../../../types/valuation';

interface MarketZoneExplorerProps {
  onSelectSectorForEstimate: (ciudad: string, sector: string) => void;
}

export const MarketZoneExplorer: React.FC<MarketZoneExplorerProps> = ({
  onSelectSectorForEstimate,
}) => {
  const [ciudades, setCiudades] = useState<CiudadCatalogItem[]>([]);
  const [selectedCiudad, setSelectedCiudad] = useState<string>('Bogota D.C.');
  const [sectores, setSectores] = useState<SectorCatalogItem[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoadingSectores, setIsLoadingSectores] = useState(false);

  useEffect(() => {
    let isMounted = true;
    getCiudades()
      .then((data) => {
        if (isMounted) {
          setCiudades(data);
          if (data.length > 0 && !data.some((c) => c.ciudad === selectedCiudad)) {
            setSelectedCiudad(data[0].ciudad);
          }
        }
      })
      .catch((err) => console.error('Error cargando ciudades:', err));

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedCiudad) return;
    let isMounted = true;
    setIsLoadingSectores(true);

    getSectores(selectedCiudad, searchTerm)
      .then((data) => {
        if (isMounted) {
          setSectores(data);
          setIsLoadingSectores(false);
        }
      })
      .catch((err) => {
        console.error('Error cargando sectores:', err);
        if (isMounted) setIsLoadingSectores(false);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedCiudad, searchTerm]);

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="bg-surface p-5 sm:p-6 rounded-2xl border border-ink-border shadow-card space-y-2">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-brand-100 text-brand-700 text-[13px] font-semibold">
          <MapPin className="w-3.5 h-3.5" />
          <span>Cobertura Geográfica</span>
        </div>
        <h1 className="text-[22px] sm:text-[24px] lg:text-[26px] font-bold text-ink-primary font-display">
          Mercado Inmobiliario por Zonas
        </h1>
        <p className="text-[15px] sm:text-[16px] text-ink-secondary max-w-2xl leading-relaxed">
          Explora los sectores con datos históricos procesados en Colombia. Conoce la densidad de ofertas, estratos predominantes y lanza una estimación directa.
        </p>
      </div>

      {/* City Selector Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none">
        {ciudades.map((c) => {
          const isSelected = selectedCiudad.toLowerCase() === c.ciudad.toLowerCase();
          return (
            <button
              key={c.clave}
              type="button"
              onClick={() => {
                setSelectedCiudad(c.ciudad);
                setSearchTerm('');
              }}
              className={`min-h-[44px] px-4 py-2.5 rounded-xl text-[14px] sm:text-[15px] font-semibold shrink-0 transition-all flex items-center gap-2 ${
                isSelected
                  ? 'bg-brand-500 text-white shadow-sm'
                  : 'bg-surface text-ink-secondary hover:text-ink-primary border border-ink-border hover:border-ink-subtle'
              }`}
            >
              <Building className="w-4 h-4" />
              <span>{c.ciudad}</span>
              <span className={`text-[12px] px-2 py-0.5 rounded-full font-bold ${isSelected ? 'bg-brand-600 text-white' : 'bg-canvas text-ink-muted'}`}>
                {c.anuncios.toLocaleString('es-CO')}
              </span>
            </button>
          );
        })}
      </div>

      {/* Search Input within Selected City */}
      <div className="relative">
        <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-muted" />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder={`Buscar sector o barrio en ${selectedCiudad}...`}
          className="w-full min-h-[48px] pl-10 pr-4 py-3 rounded-xl bg-surface border border-ink-border text-[16px] text-ink-primary placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 shadow-xs"
        />
      </div>

      {/* Sectors Cards Grid */}
      {isLoadingSectores ? (
        <div className="py-16 text-center text-ink-secondary flex items-center justify-center gap-2">
          <Loader2 className="w-5 h-5 animate-spin text-brand-500" />
          <span className="text-[15px]">Consultando sectores en {selectedCiudad}...</span>
        </div>
      ) : sectores.length === 0 ? (
        <div className="py-12 text-center bg-surface rounded-2xl border border-ink-border p-6 space-y-2">
          <p className="text-[16px] font-semibold text-ink-primary">
            No encontramos sectores coincidentes con "{searchTerm}" en {selectedCiudad}
          </p>
          <p className="text-[14px] text-ink-muted">
            Intenta con otro término o selecciona otra ciudad.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {sectores.map((s) => (
            <div
              key={s.clave}
              className="bg-surface rounded-2xl border border-ink-border hover:border-brand-500/50 p-4 sm:p-5 shadow-card hover:shadow-card-hover transition-all flex flex-col justify-between group"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-1">
                  <h3 className="text-[15px] sm:text-[16px] font-bold text-ink-primary group-hover:text-brand-600 transition-colors line-clamp-1">
                    {s.sector}
                  </h3>
                  {s.estrato && (
                    <span className="text-[11px] font-bold px-1.5 py-0.5 rounded bg-canvas text-ink-secondary border border-ink-border shrink-0">
                      Estrato {s.estrato}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-1.5 text-[13px] sm:text-[14px] text-ink-muted">
                  <Database className="w-3.5 h-3.5 text-brand-500" />
                  <span>
                    <strong className="text-ink-primary font-semibold">
                      {s.anuncios.toLocaleString('es-CO')}
                    </strong>{' '}
                    ofertas registradas
                  </span>
                </div>
              </div>

              <div className="pt-4 mt-2 border-t border-ink-border/60">
                <button
                  type="button"
                  onClick={() => onSelectSectorForEstimate(selectedCiudad, s.sector)}
                  className="w-full min-h-[42px] py-2 px-3 rounded-xl text-[14px] sm:text-[15px] font-semibold text-brand-600 bg-brand-50 hover:bg-brand-100 flex items-center justify-center gap-1.5 transition-colors"
                >
                  <span>Estimar en este sector</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
