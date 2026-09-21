import React, { useEffect, useRef, useState } from 'react';
import { ValuationResponse, ComparableItem } from '../types/valuation';
import { MapPin, ExternalLink, Bed, Bath, Car, Maximize2 } from 'lucide-react';
import L from 'leaflet';

interface ComparablesMapProps {
  result: ValuationResponse;
}

const formatCOP = (val: number): string => {
  return new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    maximumFractionDigits: 0,
  }).format(val);
};

export const ComparablesMap: React.FC<ComparablesMapProps> = ({ result }) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const [selectedListing, setSelectedListing] = useState<ComparableItem | null>(null);

  const { zona } = result;
  const comparables = (zona.venta?.comparables || zona.arriendo?.comparables || []) as ComparableItem[];
  const centro = zona.centro;

  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Destroy existing instance if present
    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
      mapInstanceRef.current = null;
    }

    const lat = centro.lat || 4.6097;
    const lon = centro.lon || -74.0817;

    const map = L.map(mapContainerRef.current, {
      center: [lat, lon],
      zoom: 14,
      zoomControl: true,
    });

    // Dark tiles using CartoDB Dark Matter
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
      maxZoom: 19,
    }).addTo(map);

    // Marker for the evaluated property
    const propertyIcon = L.divIcon({
      className: 'custom-property-pin',
      html: `
        <div style="
          background-color: #10b981;
          width: 24px;
          height: 24px;
          border-radius: 50%;
          border: 3px solid #ffffff;
          box-shadow: 0 0 15px rgba(16,185,129,0.7);
          display: flex;
          align-items: center;
          justify-content: center;
        ">
          <div style="width: 6px; height: 6px; background: white; border-radius: 50%;"></div>
        </div>
      `,
      iconSize: [24, 24],
      iconAnchor: [12, 12],
    });

    L.marker([lat, lon], { icon: propertyIcon })
      .addTo(map)
      .bindPopup(`<strong>Inmueble Valuado</strong><br/>Coordenada resuelta`);

    // Markers for comparables
    comparables.forEach((item, index) => {
      if (!item.lat || !item.lon) return;

      const compIcon = L.divIcon({
        className: 'custom-comp-pin',
        html: `
          <div style="
            background-color: #0284c7;
            color: #ffffff;
            font-size: 11px;
            font-weight: bold;
            width: 22px;
            height: 22px;
            border-radius: 50%;
            border: 2px solid #ffffff;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            display: flex;
            align-items: center;
            justify-content: center;
          ">
            ${index + 1}
          </div>
        `,
        iconSize: [22, 22],
        iconAnchor: [11, 11],
      });

      const marker = L.marker([item.lat, item.lon], { icon: compIcon }).addTo(map);

      marker.bindPopup(`
        <div style="color: #0f172a; font-family: sans-serif; font-size: 12px; min-width: 160px;">
          <div style="font-weight: bold; font-size: 13px; margin-bottom: 2px;">#${index + 1} · ${formatCOP(item.precio)}</div>
          <div style="color: #64748b; margin-bottom: 6px;">${item.area_m2} m² · ${formatCOP(item.precio_m2)}/m²</div>
          <div style="margin-bottom: 6px;">${item.sector || 'Sector no disponible'} (${item.distancia_km?.toFixed(2)} km)</div>
          <a href="${item.url}" target="_blank" rel="noopener noreferrer" style="color: #0284c7; font-weight: 600; text-decoration: underline;">
            Ver anuncio en Metrocuadrado &rarr;
          </a>
        </div>
      `);

      marker.on('click', () => {
        setSelectedListing(item);
      });
    });

    mapInstanceRef.current = map;

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [centro, comparables]);

  return (
    <div className="p-6 rounded-2xl bg-slate-900/70 border border-slate-800 shadow-xl space-y-5">
      <div>
        <h3 className="text-base font-bold text-white flex items-center gap-2">
          <MapPin className="w-5 h-5 text-emerald-400" />
          Mapa de Evidencia Inmobiliaria
        </h3>
        <p className="text-xs text-slate-400 mt-0.5">
          Inmuebles comparables reales más cercanos en el dataset Gold
        </p>
      </div>

      {/* Map Container */}
      <div
        ref={mapContainerRef}
        className="w-full h-80 rounded-xl overflow-hidden border border-slate-800 shadow-inner"
      />

      {/* Grid de las 8 tarjetas de comparables */}
      <div className="space-y-3 pt-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
            8 Anuncios Más Cercanos y Parecidos
          </span>
          <span className="text-xs text-slate-500">
            Tolerancia de área ±35%
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {comparables.map((item, index) => {
            const isSelected = selectedListing?.url === item.url;
            return (
              <a
                key={item.url || index}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`p-3.5 rounded-xl border text-xs flex flex-col justify-between transition-all group ${
                  isSelected
                    ? 'border-emerald-500 bg-emerald-500/10'
                    : 'border-slate-800 bg-slate-950/60 hover:border-slate-700 hover:bg-slate-950'
                }`}
              >
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="w-5 h-5 rounded-full bg-slate-800 text-slate-300 font-bold flex items-center justify-center text-[10px]">
                      {index + 1}
                    </span>
                    <span className="text-[10px] text-slate-500 font-medium">
                      a {item.distancia_km?.toFixed(2)} km
                    </span>
                  </div>

                  <div className="text-sm font-bold text-white group-hover:text-emerald-400 transition-colors">
                    {formatCOP(item.precio)}
                  </div>

                  <div className="text-[11px] text-slate-400">
                    <strong>{formatCOP(item.precio_m2)}</strong> / m²
                  </div>
                </div>

                <div className="mt-3 pt-2 border-t border-slate-800/80 flex items-center justify-between text-slate-400 text-[10px]">
                  <span className="flex items-center gap-1">
                    <Maximize2 className="w-3 h-3 text-slate-500" /> {item.area_m2} m²
                  </span>
                  {item.habitaciones !== null && (
                    <span className="flex items-center gap-1">
                      <Bed className="w-3 h-3 text-slate-500" /> {item.habitaciones}
                    </span>
                  )}
                  {item.banos !== null && (
                    <span className="flex items-center gap-1">
                      <Bath className="w-3 h-3 text-slate-500" /> {item.banos}
                    </span>
                  )}
                  {item.parqueaderos !== null && (
                    <span className="flex items-center gap-1">
                      <Car className="w-3 h-3 text-slate-500" /> {item.parqueaderos}
                    </span>
                  )}
                  <ExternalLink className="w-3.5 h-3.5 text-emerald-400 group-hover:translate-x-0.5 transition-transform" />
                </div>
              </a>
            );
          })}
        </div>
      </div>
    </div>
  );
};
