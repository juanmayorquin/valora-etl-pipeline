import React, { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getCiudades, getSectores } from '../services/api';
import { PropertyType, ValuationRequest } from '../types/valuation';
import { Building, Home, Key, MapPin, Sparkles, Plus, Minus, Search, Check } from 'lucide-react';

const COMODIDADES_OPCIONES = [
  { id: 'ascensor', label: 'Ascensor' },
  { id: 'conjunto_cerrado', label: 'Conjunto cerrado' },
  { id: 'vigilancia', label: 'Vigilancia 24/7' },
  { id: 'gimnasio', label: 'Gimnasio' },
  { id: 'piscina', label: 'Piscina' },
  { id: 'balcon', label: 'Balcón' },
  { id: 'terraza', label: 'Terraza' },
  { id: 'estudio', label: 'Estudio' },
  { id: 'deposito', label: 'Depósito' },
  { id: 'chimenea', label: 'Chimenea' },
  { id: 'amoblado', label: 'Amoblado' },
  { id: 'cocina_integral', label: 'Cocina integral' },
  { id: 'parqueadero_visitantes', label: 'Parq. visitantes' },
  { id: 'zonas_verdes', label: 'Zonas verdes' },
  { id: 'transporte', label: 'Cerca a transporte' },
  { id: 'colegios', label: 'Cerca a colegios' },
];

const ANTIGUEDADES = [
  { id: '', label: 'No especificada' },
  { id: 'Menos de 1 año', label: 'Menos de 1 año' },
  { id: 'Entre 0 y 5 años', label: 'Entre 0 y 5 años' },
  { id: 'Entre 5 y 10 años', label: 'Entre 5 y 10 años' },
  { id: 'Entre 10 y 20 años', label: 'Entre 10 y 20 años' },
  { id: 'Más de 20 años', label: 'Más de 20 años' },
];

interface ValuationFormProps {
  onSubmit: (data: ValuationRequest) => void;
  isLoading: boolean;
}

export const ValuationForm: React.FC<ValuationFormProps> = ({ onSubmit, isLoading }) => {
  const [tipo, setTipo] = useState<PropertyType>('apartamento');
  const [ciudad, setCiudad] = useState<string>('Bogotá D.C.');
  const [sector, setSector] = useState<string>('Chicó Norte');
  const [sectorQuery, setSectorQuery] = useState<string>('Chicó Norte');
  const [isSectorOpen, setIsSectorOpen] = useState<boolean>(false);
  const [area, setArea] = useState<number>(85);
  const [habitaciones, setHabitaciones] = useState<number>(2);
  const [banos, setBanos] = useState<number>(2);
  const [parqueaderos, setParqueaderos] = useState<number>(1);
  const [estrato, setEstrato] = useState<number | null>(6);
  const [antiguedad, setAntiguedad] = useState<string>('Entre 5 y 10 años');
  const [piso, setPiso] = useState<string>('');
  const [administracion, setAdministracion] = useState<string>('');
  const [comodidades, setComodidades] = useState<string[]>(['ascensor', 'gimnasio']);

  const sectorRef = useRef<HTMLDivElement>(null);

  // Fetch ciudades
  const { data: ciudades = [] } = useQuery({
    queryKey: ['ciudades'],
    queryFn: getCiudades,
    staleTime: 1000 * 60 * 30,
  });

  // Fetch sectores for autocomplete
  const { data: sectores = [], isLoading: isLoadingSectores } = useQuery({
    queryKey: ['sectores', ciudad, sectorQuery],
    queryFn: () => getSectores(ciudad, sectorQuery),
    enabled: isSectorOpen && !!ciudad,
    staleTime: 1000 * 60 * 5,
  });

  // Close autocomplete on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (sectorRef.current && !sectorRef.current.contains(e.target as Node)) {
        setIsSectorOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const toggleComodidad = (id: string) => {
    setComodidades((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      tipo,
      ciudad,
      sector,
      area_m2: Number(area),
      habitaciones: Number(habitaciones),
      banos: Number(banos),
      parqueaderos: Number(parqueaderos),
      estrato: estrato ? Number(estrato) : null,
      antiguedad: antiguedad || null,
      piso: piso ? Number(piso) : null,
      administracion: administracion ? Number(administracion) : null,
      comodidades,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="bg-slate-900/70 border border-slate-800/80 rounded-2xl p-6 shadow-xl backdrop-blur-sm space-y-6">
      <div>
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <Building className="w-5 h-5 text-emerald-400" />
          Ficha del Inmueble
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Ingresa las especificaciones del inmueble para obtener la tasación de mercado.
        </p>
      </div>

      {/* Tipo de Inmueble Selector */}
      <div className="space-y-1.5">
        <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
          Tipo de Inmueble
        </label>
        <div className="grid grid-cols-3 gap-2">
          {[
            { id: 'apartamento', label: 'Apartamento', icon: Building },
            { id: 'casa', label: 'Casa', icon: Home },
            { id: 'apartaestudio', label: 'Apartaestudio', icon: Key },
          ].map((item) => {
            const Icon = item.icon;
            const active = tipo === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setTipo(item.id as PropertyType)}
                className={`flex flex-col items-center justify-center p-3 rounded-xl border text-xs font-medium transition-all ${
                  active
                    ? 'border-emerald-500 bg-emerald-500/10 text-emerald-400 shadow-md shadow-emerald-950'
                    : 'border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                }`}
              >
                <Icon className="w-4 h-4 mb-1" />
                {item.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Ubicación: Ciudad y Sector */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1">
            <MapPin className="w-3.5 h-3.5 text-emerald-400" />
            Ciudad
          </label>
          <select
            value={ciudad}
            onChange={(e) => {
              setCiudad(e.target.value);
              setSector('');
              setSectorQuery('');
            }}
            className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 transition-colors"
          >
            {ciudades.map((c) => (
              <option key={c.clave} value={c.ciudad}>
                {c.ciudad} ({c.anuncios.toLocaleString()} anuncios)
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1.5 relative" ref={sectorRef}>
          <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
            Sector / Barrio
          </label>
          <div className="relative">
            <input
              type="text"
              value={sectorQuery}
              onChange={(e) => {
                setSectorQuery(e.target.value);
                setSector(e.target.value);
                setIsSectorOpen(true);
              }}
              onFocus={() => setIsSectorOpen(true)}
              placeholder="Ej. Chicó Norte, Rosales..."
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl pl-3 pr-8 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 transition-colors"
              required
            />
            <Search className="w-4 h-4 text-slate-500 absolute right-3 top-3 pointer-events-none" />
          </div>

          {/* Autocomplete Dropdown */}
          {isSectorOpen && sectores.length > 0 && (
            <div className="absolute z-20 left-0 right-0 mt-1 max-h-56 overflow-y-auto bg-slate-900 border border-slate-700/80 rounded-xl shadow-2xl divide-y divide-slate-800">
              {isLoadingSectores ? (
                <div className="p-3 text-xs text-slate-400">Buscando sectores...</div>
              ) : (
                sectores.map((s) => (
                  <button
                    key={s.clave}
                    type="button"
                    onClick={() => {
                      setSector(s.sector);
                      setSectorQuery(s.sector);
                      if (s.estrato) setEstrato(s.estrato);
                      setIsSectorOpen(false);
                    }}
                    className="w-full text-left px-3 py-2 text-xs hover:bg-emerald-500/10 hover:text-emerald-300 flex items-center justify-between transition-colors"
                  >
                    <span className="font-medium text-slate-200">{s.sector}</span>
                    <span className="text-[10px] text-slate-400">
                      {s.anuncios} anuncios {s.estrato ? `· Est. ${s.estrato}` : ''}
                    </span>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* Características Numéricas */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {/* Área */}
        <div className="space-y-1">
          <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            Área (m²)
          </label>
          <input
            type="number"
            min={15}
            max={1000}
            value={area}
            onChange={(e) => setArea(Number(e.target.value))}
            className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-sm text-slate-100 font-semibold focus:outline-none focus:border-emerald-500"
            required
          />
        </div>

        {/* Habitaciones Stepper */}
        <div className="space-y-1">
          <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            Habitaciones
          </label>
          <div className="flex items-center bg-slate-950/80 border border-slate-800 rounded-xl">
            <button
              type="button"
              onClick={() => setHabitaciones((p) => Math.max(0, p - 1))}
              className="px-2.5 py-2 text-slate-400 hover:text-white"
            >
              <Minus className="w-3.5 h-3.5" />
            </button>
            <span className="flex-1 text-center text-sm font-semibold text-slate-100">
              {habitaciones}
            </span>
            <button
              type="button"
              onClick={() => setHabitaciones((p) => Math.min(10, p + 1))}
              className="px-2.5 py-2 text-slate-400 hover:text-white"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Baños Stepper */}
        <div className="space-y-1">
          <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            Baños
          </label>
          <div className="flex items-center bg-slate-950/80 border border-slate-800 rounded-xl">
            <button
              type="button"
              onClick={() => setBanos((p) => Math.max(1, p - 1))}
              className="px-2.5 py-2 text-slate-400 hover:text-white"
            >
              <Minus className="w-3.5 h-3.5" />
            </button>
            <span className="flex-1 text-center text-sm font-semibold text-slate-100">
              {banos}
            </span>
            <button
              type="button"
              onClick={() => setBanos((p) => Math.min(10, p + 1))}
              className="px-2.5 py-2 text-slate-400 hover:text-white"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Parqueaderos Stepper */}
        <div className="space-y-1">
          <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            Parqueaderos
          </label>
          <div className="flex items-center bg-slate-950/80 border border-slate-800 rounded-xl">
            <button
              type="button"
              onClick={() => setParqueaderos((p) => Math.max(0, p - 1))}
              className="px-2.5 py-2 text-slate-400 hover:text-white"
            >
              <Minus className="w-3.5 h-3.5" />
            </button>
            <span className="flex-1 text-center text-sm font-semibold text-slate-100">
              {parqueaderos}
            </span>
            <button
              type="button"
              onClick={() => setParqueaderos((p) => Math.min(10, p + 1))}
              className="px-2.5 py-2 text-slate-400 hover:text-white"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Estrato Selector */}
      <div className="space-y-1.5">
        <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
          Estrato Socioeconómico
        </label>
        <div className="grid grid-cols-6 gap-2">
          {[1, 2, 3, 4, 5, 6].map((num) => {
            const active = estrato === num;
            return (
              <button
                key={num}
                type="button"
                onClick={() => setEstrato(num)}
                className={`py-2 rounded-xl text-xs font-bold transition-all ${
                  active
                    ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
                    : 'bg-slate-950/70 border border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                }`}
              >
                {num}
              </button>
            );
          })}
        </div>
      </div>

      {/* Antigüedad, Piso y Administración */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="space-y-1">
          <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            Antigüedad
          </label>
          <select
            value={antiguedad}
            onChange={(e) => setAntiguedad(e.target.value)}
            className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-2.5 py-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
          >
            {ANTIGUEDADES.map((a) => (
              <option key={a.id} value={a.id}>
                {a.label}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1">
          <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            Piso (opcional)
          </label>
          <input
            type="number"
            min={1}
            max={60}
            value={piso}
            onChange={(e) => setPiso(e.target.value)}
            placeholder="—"
            className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
          >
          </input>
        </div>

        <div className="space-y-1">
          <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            Administración ($)
          </label>
          <input
            type="number"
            step={10000}
            value={administracion}
            onChange={(e) => setAdministracion(e.target.value)}
            placeholder="—"
            className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
          >
          </input>
        </div>
      </div>

      {/* Comodidades Chips */}
      <div className="space-y-2">
        <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
          Comodidades & Amenidades
        </label>
        <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto p-1 border border-slate-800/60 rounded-xl bg-slate-950/40">
          {COMODIDADES_OPCIONES.map((c) => {
            const selected = comodidades.includes(c.id);
            return (
              <button
                key={c.id}
                type="button"
                onClick={() => toggleComodidad(c.id)}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all ${
                  selected
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                    : 'bg-slate-900 border border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-300'
                }`}
              >
                {selected && <Check className="w-3 h-3 text-emerald-400" />}
                {c.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Botón de envío */}
      <button
        type="submit"
        disabled={isLoading || !ciudad || !sector}
        className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 text-slate-950 font-bold text-sm tracking-wide shadow-lg shadow-emerald-500/20 hover:from-emerald-400 hover:to-teal-500 active:scale-[0.99] disabled:opacity-50 disabled:pointer-events-none transition-all flex items-center justify-center gap-2"
      >
        {isLoading ? (
          <>
            <div className="w-4 h-4 border-2 border-slate-950 border-t-transparent rounded-full animate-spin"></div>
            <span>Calculando Valuación...</span>
          </>
        ) : (
          <>
            <Sparkles className="w-4 h-4" />
            <span>Valuar Inmueble y Comparar Zona</span>
          </>
        )}
      </button>
    </form>
  );
};
