import React, { useEffect, useRef, useState } from 'react';
import { ValuationResponse, ComparableItem, OperationType, UserObjective } from '../../../types/valuation';
import { ComparableCard } from './ComparableCard';
import { formatCOP } from '../../../shared/utils/formatters';
import {
  Compass,
  Radio,
} from 'lucide-react';
import L from 'leaflet';

interface ComparablesMapViewProps {
  result: ValuationResponse;
  objective?: UserObjective;
}

export const ComparablesMapView: React.FC<ComparablesMapViewProps> = ({
  result,
  objective = 'ambas',
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersRef = useRef<{ [key: number]: L.Marker }>({});
  const cardListRef = useRef<HTMLDivElement>(null);

  const initialOp: OperationType = objective === 'arrendar' ? 'arriendo' : 'venta';
  const [operacion, setOperacion] = useState<OperationType>(initialOp);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  const { zona, avaluo } = result;
  const datosZona = operacion === 'venta' ? zona.venta : zona.arriendo;
  const comparables = (datosZona?.comparables || []) as ComparableItem[];
  const centro = zona.centro;
  const radioKm = zona.radio_km || 1.5;

  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
      mapInstanceRef.current = null;
      markersRef.current = {};
    }

    const lat = centro.lat || 4.6097;
    const lon = centro.lon || -74.0817;

    const map = L.map(mapContainerRef.current, {
      center: [lat, lon],
      zoom: 14,
      zoomControl: true,
    });

    // Base pública OpenStreetMap
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map);

    // Círculo del radio de análisis
    L.circle([lat, lon], {
      radius: radioKm * 1000,
      color: '#176B45',
      fillColor: '#176B45',
      fillOpacity: 0.08,
      weight: 1.5,
      dashArray: '4, 6',
    }).addTo(map);

    // Marcador del inmueble evaluado (estrella verde)
    const propertyIcon = L.divIcon({
      className: 'custom-property-pin',
      html: `
        <div style="
          background-color: #176B45;
          width: 32px;
          height: 32px;
          border-radius: 50%;
          border: 3px solid #ffffff;
          box-shadow: 0 4px 12px rgba(23, 107, 69, 0.45);
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          font-size: 16px;
          font-weight: bold;
        ">
          ★
        </div>
      `,
      iconSize: [32, 32],
      iconAnchor: [16, 16],
    });

    const propMarker = L.marker([lat, lon], { icon: propertyIcon, zIndexOffset: 1000 }).addTo(map);
    propMarker.bindPopup(`
      <div style="color: #142B3A; font-family: Inter, sans-serif; padding: 4px;">
        <strong style="display: block; font-size: 13px;">Inmueble Evaluado</strong>
        <span style="font-size: 11px; color: #63727A;">${avaluo.contexto.sector || 'Sector'} · ${avaluo.contexto.ciudad}</span>
        <div style="margin-top: 6px; font-weight: 800; font-size: 14px; color: #176B45;">
          ${formatCOP(operacion === 'venta' ? avaluo.venta.estimado : avaluo.arriendo.estimado)}
        </div>
      </div>
    `);

    // Marcadores de comparables
    const bounds = L.latLngBounds([[lat, lon]]);

    comparables.forEach((comp, idx) => {
      if (comp.lat && comp.lon) {
        const compIcon = L.divIcon({
          className: 'custom-comp-pin',
          html: `
            <div id="pin-${idx}" style="
              background-color: #142B3A;
              color: #ffffff;
              width: 26px;
              height: 26px;
              border-radius: 50%;
              border: 2px solid #ffffff;
              box-shadow: 0 2px 8px rgba(20, 43, 58, 0.35);
              display: flex;
              align-items: center;
              justify-content: center;
              font-size: 11px;
              font-weight: 700;
              transition: transform 0.2s;
            ">
              ${idx + 1}
            </div>
          `,
          iconSize: [26, 26],
          iconAnchor: [13, 13],
        });

        const m = L.marker([comp.lat, comp.lon], { icon: compIcon }).addTo(map);
        m.bindPopup(`
          <div style="color: #142B3A; font-family: Inter, sans-serif; padding: 4px; min-width: 140px;">
            <div style="font-size: 10px; color: #63727A; font-weight: 600;">Comparable #${idx + 1} · ${comp.distancia_km?.toFixed(2) || '0'} km</div>
            <strong style="display: block; font-size: 13px; margin-top: 2px;">${formatCOP(comp.precio)}</strong>
            <div style="font-size: 11px; color: #63727A; margin-top: 2px;">${comp.area_m2} m² · ${formatCOP(comp.precio_m2)}/m²</div>
            ${comp.url ? `<a href="${comp.url}" target="_blank" rel="noreferrer" style="display: inline-block; margin-top: 6px; font-size: 11px; color: #176B45; text-decoration: underline; font-weight: 600;">Ver anuncio original →</a>` : ''}
          </div>
        `);

        m.on('click', () => {
          setSelectedIdx(idx);
        });

        markersRef.current[idx] = m;
        bounds.extend([comp.lat, comp.lon]);
      }
    });

    if (comparables.length > 0) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
    }

    mapInstanceRef.current = map;
  }, [centro.lat, centro.lon, comparables, operacion, radioKm]);

  const handleSelectCard = (idx: number) => {
    setSelectedIdx(idx);
    const m = markersRef.current[idx];
    if (m && mapInstanceRef.current) {
      mapInstanceRef.current.setView(m.getLatLng(), 15, { animate: true });
      m.openPopup();
    }
  };

  return (
    <div className="rounded-2xl bg-surface border border-ink-border p-6 sm:p-7 shadow-card space-y-6">
      {/* Encabezado */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3.5 pb-4 border-b border-ink-border/70">
        <div>
          <span className="text-[12px] font-bold text-brand-600 uppercase tracking-wider flex items-center gap-1.5">
            <Compass className="w-4 h-4" />
            Geolocalización y Entorno
          </span>
          <h3 className="text-[22px] sm:text-[24px] lg:text-[26px] font-bold text-ink-primary font-display mt-0.5">
            Mapa de Inmuebles Comparables
          </h3>
        </div>

        {/* Selector Venta / Arriendo */}
        <div className="flex items-center gap-1.5 p-1 bg-canvas rounded-xl border border-ink-border self-start sm:self-auto">
          <button
            type="button"
            onClick={() => {
              setOperacion('venta');
              setSelectedIdx(null);
            }}
            className={`min-h-[42px] px-4 py-2 rounded-lg text-[15px] font-bold transition-all ${
              operacion === 'venta'
                ? 'bg-brand-500 text-white shadow-xs'
                : 'text-ink-secondary hover:text-ink-primary'
            }`}
          >
            Comparables Venta
          </button>
          <button
            type="button"
            onClick={() => {
              setOperacion('arriendo');
              setSelectedIdx(null);
            }}
            className={`min-h-[42px] px-4 py-2 rounded-lg text-[15px] font-bold transition-all ${
              operacion === 'arriendo'
                ? 'bg-brand-500 text-white shadow-xs'
                : 'text-ink-secondary hover:text-ink-primary'
            }`}
          >
            Comparables Arriendo
          </button>
        </div>
      </div>

      {/* Leyenda y Radio */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-[14px] sm:text-[15px] bg-canvas p-3.5 rounded-xl border border-ink-border">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="w-3.5 h-3.5 rounded-full bg-brand-500 border-2 border-white inline-block"></span>
            <span className="font-semibold text-ink-primary">Inmueble evaluado</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-ink-primary border-2 border-white inline-block"></span>
            <span className="text-ink-secondary">Anuncios comparables ({comparables.length})</span>
          </div>
        </div>

        <div className="flex items-center gap-2 text-ink-secondary">
          <Radio className="w-4 h-4 text-brand-500" />
          <span>Radio de análisis: <strong>{radioKm} km</strong></span>
        </div>
      </div>

      {/* Grid: Mapa (7 cols) + Lista de Comparables (5 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Contenedor del Mapa */}
        <div className="lg:col-span-7 rounded-2xl overflow-hidden border border-ink-border relative z-0 h-[340px] sm:h-[450px] shadow-xs">
          <div ref={mapContainerRef} className="w-full h-full"></div>
        </div>

        {/* Lista de Tarjetas de Comparables */}
        <div className="lg:col-span-5 space-y-3">
          <div className="flex items-center justify-between text-[14px] sm:text-[15px] font-semibold text-ink-secondary">
            <span>Propiedades similares ({comparables.length})</span>
            <span className="text-[12px] text-ink-muted">Toca para enfocar</span>
          </div>

          <div
            ref={cardListRef}
            className="space-y-2.5 max-h-[390px] overflow-y-auto pr-1"
          >
            {comparables.length === 0 ? (
              <div className="p-6 text-center text-xs text-ink-muted bg-canvas rounded-xl border border-ink-border">
                No hay comparables directos con coordenadas en este radio.
              </div>
            ) : (
              comparables.map((item, idx) => (
                <ComparableCard
                  key={idx}
                  item={item}
                  isSelected={selectedIdx === idx}
                  onSelect={() => handleSelectCard(idx)}
                  operacion={operacion}
                />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
