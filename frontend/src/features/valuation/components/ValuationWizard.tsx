import { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getCiudades, getSectores } from '../../../services/api';
import { PropertyType, ValuationRequest, UserObjective } from '../../../types/valuation';
import {
  OBJETIVOS_USUARIO,
  TIPOS_INMUEBLE,
  COMODIDADES_LISTA,
  ANTIGUEDADES_OPCIONES,
} from '../../../shared/constants/propertyOptions';
import {
  Building2,
  Home,
  Key,
  MapPin,
  ArrowRight,
  ArrowLeft,
  Sparkles,
  Check,
  Plus,
  Minus,
  Search,
  DollarSign,
  KeyRound,
  Scale,
  Layers,
} from 'lucide-react';
import { ValuationLoadingProgress } from './ValuationLoadingProgress';

interface ValuationWizardProps {
  onSubmit: (data: ValuationRequest, objective: UserObjective) => void;
  isLoading: boolean;
  initialValues?: Partial<ValuationRequest>;
  initialObjective?: UserObjective;
  onEditChange?: () => void;
  backendReady?: boolean;
}

export const ValuationWizard: React.FC<ValuationWizardProps> = ({
  onSubmit,
  isLoading,
  initialValues,
  initialObjective = 'ambas',
  backendReady = true,
}) => {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [objective, setObjective] = useState<UserObjective>(initialObjective);

  // Form states
  const [tipo, setTipo] = useState<PropertyType>(initialValues?.tipo || 'apartamento');
  const [ciudad, setCiudad] = useState<string>(initialValues?.ciudad || 'Bogotá D.C.');
  const [sector, setSector] = useState<string>(initialValues?.sector || 'Chicó Norte');
  const [sectorQuery, setSectorQuery] = useState<string>(initialValues?.sector || 'Chicó Norte');
  const [isSectorOpen, setIsSectorOpen] = useState<boolean>(false);

  const [area, setArea] = useState<number>(initialValues?.area_m2 || 85);
  const [habitaciones, setHabitaciones] = useState<number>(initialValues?.habitaciones ?? 2);
  const [banos, setBanos] = useState<number>(initialValues?.banos ?? 2);
  const [parqueaderos, setParqueaderos] = useState<number>(initialValues?.parqueaderos ?? 1);

  const [estrato, setEstrato] = useState<number | null>(initialValues?.estrato ?? 6);
  const [antiguedad, setAntiguedad] = useState<string>(initialValues?.antiguedad ?? 'Entre 5 y 10 años');
  const [piso, setPiso] = useState<string>(initialValues?.piso ? String(initialValues.piso) : '');
  const [administracion, setAdministracion] = useState<string>(
    initialValues?.administracion ? String(initialValues.administracion) : ''
  );
  const [comodidades, setComodidades] = useState<string[]>(
    initialValues?.comodidades || ['ascensor', 'gimnasio']
  );

  const sectorRef = useRef<HTMLDivElement>(null);

  // Catalog queries
  const { data: ciudades = [] } = useQuery({
    queryKey: ['ciudades'],
    queryFn: getCiudades,
    enabled: backendReady,
    staleTime: 1000 * 60 * 30,
  });

  const { data: sectores = [], isLoading: isLoadingSectores } = useQuery({
    queryKey: ['sectores', ciudad, sectorQuery],
    queryFn: () => getSectores(ciudad, sectorQuery),
    enabled: backendReady && ciudad.length > 0 && isSectorOpen,
    staleTime: 1000 * 60 * 5,
  });

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (sectorRef.current && !sectorRef.current.contains(e.target as Node)) {
        setIsSectorOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelectSector = (nombre: string, estratoSugerido: number | null) => {
    setSector(nombre);
    setSectorQuery(nombre);
    setIsSectorOpen(false);
    if (estratoSugerido && estrato === null) {
      setEstrato(estratoSugerido);
    }
  };

  const toggleComodidad = (id: string) => {
    setComodidades((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleFinalSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!backendReady || !ciudad || !sector || area <= 15) return;

    onSubmit(
      {
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
      },
      objective
    );
  };

  const isStep1Valid = ciudad.trim().length > 0 && sector.trim().length > 0;
  const isStep2Valid = area >= 16 && area <= 3000;

  if (isLoading) {
    return <ValuationLoadingProgress ciudad={ciudad} sector={sector} />;
  }

  return (
    <div className="bg-surface border border-ink-border rounded-2xl shadow-card overflow-hidden transition-all">
      {/* Steps Progress Header */}
      <div className="p-4 sm:p-5 bg-canvas/70 border-b border-ink-border">
        <div className="flex items-center justify-between max-w-md mx-auto">
          {[
            { num: 1, title: 'Objetivo y Lugar' },
            { num: 2, title: 'Dimensiones' },
            { num: 3, title: 'Detalles' },
          ].map((s) => {
            const isCurrent = step === s.num;
            const isCompleted = step > s.num;
            return (
              <div key={s.num} className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    if (s.num === 1) setStep(1);
                    if (s.num === 2 && isStep1Valid) setStep(2);
                    if (s.num === 3 && isStep1Valid && isStep2Valid) setStep(3);
                  }}
                  className={`w-9 h-9 rounded-full flex items-center justify-center font-bold text-[14px] transition-all ${
                    isCurrent
                      ? 'bg-brand-500 text-white shadow-xs'
                      : isCompleted
                      ? 'bg-brand-100 text-brand-700 border border-brand-200'
                      : 'bg-white text-ink-muted border border-ink-border'
                  }`}
                  aria-label={`Ir al paso ${s.num}: ${s.title}`}
                >
                  {isCompleted ? <Check className="w-4 h-4 text-brand-600" /> : s.num}
                </button>
                <span
                  className={`text-[15px] hidden sm:inline ${
                    isCurrent ? 'text-ink-primary font-bold' : 'text-ink-secondary font-medium'
                  }`}
                >
                  {s.title}
                </span>
                {s.num < 3 && <div className="w-8 sm:w-12 h-0.5 bg-ink-border mx-1"></div>}
              </div>
            );
          })}
        </div>
      </div>

      <form onSubmit={handleFinalSubmit} className="p-6 sm:p-7 space-y-6">
        {!backendReady && (
          <div className="p-3.5 rounded-xl bg-warning-50 border border-warning-100 text-warning-800 text-[14px] flex items-center gap-2" role="status" aria-live="polite">
            <span className="w-2 h-2 rounded-full bg-warning-500 animate-pulse" />
            <span>Estamos preparando el motor de valoración. Podrás calcular en unos segundos.</span>
          </div>
        )}
        {/* ===================== PASO 1: OBJETIVO, UBICACIÓN Y TIPO ===================== */}
        {step === 1 && (
          <div className="space-y-6 animate-fadeIn">
            {/* 1.1 Objetivo del usuario */}
            <div className="space-y-2">
              <label className="text-[14px] font-semibold text-ink-primary flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-brand-500" />
                <span>¿Qué deseas consultar hoy?</span>
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                {OBJETIVOS_USUARIO.map((item) => {
                  const active = objective === item.id;
                  const Icon =
                    item.id === 'vender'
                      ? DollarSign
                      : item.id === 'arrendar'
                      ? KeyRound
                      : Scale;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setObjective(item.id as UserObjective)}
                      className={`min-h-[68px] p-3.5 sm:p-4 rounded-xl border text-left transition-all flex flex-col justify-between ${
                        active
                          ? 'border-brand-500 bg-brand-50/70 text-ink-primary ring-1 ring-brand-500 shadow-xs'
                          : 'border-ink-border bg-surface text-ink-secondary hover:border-ink-subtle hover:bg-canvas/50'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <Icon className={`w-4 h-4 ${active ? 'text-brand-600' : 'text-ink-muted'}`} />
                        <span className={`text-[15px] font-bold ${active ? 'text-brand-800' : 'text-ink-primary'}`}>
                          {item.titulo}
                        </span>
                      </div>
                      <p className="text-[14px] text-ink-secondary leading-snug mt-1">
                        {item.descripcion}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 1.2 Tipo de Inmueble */}
            <div className="space-y-2">
              <label className="text-[14px] font-semibold text-ink-primary block">
                Tipo de Inmueble
              </label>
              <div className="grid grid-cols-3 gap-2.5">
                {TIPOS_INMUEBLE.map((item) => {
                  const active = tipo === item.id;
                  const Icon =
                    item.id === 'apartamento'
                      ? Building2
                      : item.id === 'casa'
                      ? Home
                      : Key;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setTipo(item.id as PropertyType)}
                      className={`min-h-[60px] p-3 rounded-xl border flex flex-col items-center justify-center text-center transition-all ${
                        active
                          ? 'border-brand-500 bg-brand-50/80 text-brand-800 font-bold ring-1 ring-brand-500'
                          : 'border-ink-border bg-surface text-ink-secondary hover:border-ink-subtle hover:bg-canvas/50'
                      }`}
                    >
                      <Icon className={`w-4 h-4 mb-1 ${active ? 'text-brand-600' : 'text-ink-muted'}`} />
                      <span className="text-[15px] font-semibold">{item.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 1.3 Ubicación: Ciudad y Sector */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-[14px] font-semibold text-ink-primary flex items-center gap-1.5">
                  <MapPin className="w-4 h-4 text-brand-500" />
                  <span>Ciudad</span>
                </label>
                <select
                  value={ciudad}
                  onChange={(e) => {
                    setCiudad(e.target.value);
                    setSector('');
                    setSectorQuery('');
                  }}
                  className="w-full min-h-[48px] bg-surface border border-ink-border rounded-xl px-3.5 py-2.5 text-[16px] text-ink-primary focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors"
                >
                  {ciudades.map((c) => (
                    <option key={c.clave} value={c.ciudad}>
                      {c.ciudad} ({c.anuncios.toLocaleString()} anuncios)
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5 relative" ref={sectorRef}>
                <label className="text-[14px] font-semibold text-ink-primary flex items-center justify-between">
                  <span>Sector o Barrio</span>
                  <span className="text-[12px] text-ink-muted font-normal">Autocompleta con datos reales</span>
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={sectorQuery}
                    placeholder="Chicó, Laureles, El Poblado..."
                    onFocus={() => setIsSectorOpen(true)}
                    onChange={(e) => {
                      setSectorQuery(e.target.value);
                      setSector(e.target.value);
                      setIsSectorOpen(true);
                    }}
                    className="w-full min-h-[48px] bg-surface border border-ink-border rounded-xl pl-3.5 pr-9 py-2.5 text-[16px] text-ink-primary placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-colors"
                  />
                  <Search className="w-4 h-4 text-ink-muted absolute right-3.5 top-4 pointer-events-none" />
                </div>

                {isSectorOpen && (
                  <div className="absolute left-0 right-0 top-full mt-1 bg-surface border border-ink-border rounded-xl shadow-elevated max-h-56 overflow-y-auto z-50 divide-y divide-ink-border">
                    {isLoadingSectores ? (
                      <div className="p-3.5 text-[14px] text-ink-muted text-center">
                        Buscando sectores en {ciudad}...
                      </div>
                    ) : sectores.length === 0 ? (
                      <div className="p-3.5 text-[14px] text-ink-muted text-center">
                        No encontramos coincidencias. Se usará como sector nuevo.
                      </div>
                    ) : (
                      sectores.map((s) => (
                        <button
                          key={s.clave}
                          type="button"
                          onClick={() => handleSelectSector(s.sector, s.estrato)}
                          className="w-full text-left px-3.5 py-3 text-[14px] hover:bg-brand-50 hover:text-brand-800 flex items-center justify-between transition-colors text-ink-primary"
                        >
                          <span className="font-semibold">{s.sector}</span>
                          <span className="text-[13px] text-ink-secondary">
                            {s.anuncios} anuncios {s.estrato ? `· Estrato ${s.estrato}` : ''}
                          </span>
                        </button>
                      ))
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Next Step 1 Button */}
            <div className="pt-2 flex justify-end">
              <button
                type="button"
                disabled={!isStep1Valid}
                onClick={() => setStep(2)}
                className="min-h-[48px] px-6 py-3 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-bold text-[15px] sm:text-[16px] tracking-wide shadow-card hover:shadow-card-hover disabled:opacity-40 disabled:pointer-events-none transition-all flex items-center gap-2"
              >
                <span>Continuar a Dimensiones</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* ===================== PASO 2: CARACTERÍSTICAS PRINCIPALES ===================== */}
        {step === 2 && (
          <div className="space-y-6 animate-fadeIn">
            {/* Area in m² */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-[14px] font-semibold text-ink-primary uppercase tracking-wider">
                  Área Construida (m²)
                </label>
                <span className="text-[15px] font-bold text-brand-700 bg-brand-100 px-3.5 py-1 rounded-full border border-brand-200 tabular-nums">
                  {area} m²
                </span>
              </div>
              <input
                type="range"
                min={20}
                max={450}
                step={1}
                value={area}
                onChange={(e) => setArea(Number(e.target.value))}
                className="w-full accent-brand-500 cursor-pointer h-2 bg-slate-200 rounded-lg"
              />
              <div className="flex flex-wrap gap-2 pt-1">
                {[45, 65, 85, 120, 180, 250].map((quickArea) => (
                  <button
                    key={quickArea}
                    type="button"
                    onClick={() => setArea(quickArea)}
                    className={`text-[14px] sm:text-[15px] px-3.5 py-1.5 rounded-lg border transition-all ${
                      area === quickArea
                        ? 'border-brand-500 bg-brand-100 text-brand-800 font-bold'
                        : 'border-ink-border bg-canvas text-ink-secondary hover:border-ink-subtle hover:text-ink-primary'
                    }`}
                  >
                    {quickArea} m²
                  </button>
                ))}
              </div>
            </div>

            {/* Habitaciones, Baños, Parqueaderos */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* Habitaciones */}
              <div className="space-y-1.5 p-3.5 rounded-xl bg-canvas border border-ink-border">
                <span className="text-[14px] font-semibold text-ink-primary uppercase block">
                  Habitaciones
                </span>
                <div className="flex items-center justify-between pt-1">
                  <button
                    type="button"
                    onClick={() => setHabitaciones((prev) => Math.max(0, prev - 1))}
                    className="w-11 h-11 rounded-lg border border-ink-border bg-surface text-ink-primary hover:bg-white hover:border-brand-500 flex items-center justify-center transition-all shadow-xs text-lg"
                    aria-label="Disminuir habitaciones"
                  >
                    <Minus className="w-4 h-4" />
                  </button>
                  <span className="text-[18px] sm:text-[20px] font-bold text-ink-primary tabular-nums">{habitaciones}</span>
                  <button
                    type="button"
                    onClick={() => setHabitaciones((prev) => Math.min(10, prev + 1))}
                    className="w-11 h-11 rounded-lg border border-ink-border bg-surface text-ink-primary hover:bg-white hover:border-brand-500 flex items-center justify-center transition-all shadow-xs text-lg"
                    aria-label="Aumentar habitaciones"
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Baños */}
              <div className="space-y-1.5 p-3.5 rounded-xl bg-canvas border border-ink-border">
                <span className="text-[14px] font-semibold text-ink-primary uppercase block">
                  Baños
                </span>
                <div className="flex items-center justify-between pt-1">
                  <button
                    type="button"
                    onClick={() => setBanos((prev) => Math.max(1, prev - 1))}
                    className="w-11 h-11 rounded-lg border border-ink-border bg-surface text-ink-primary hover:bg-white hover:border-brand-500 flex items-center justify-center transition-all shadow-xs text-lg"
                    aria-label="Disminuir baños"
                  >
                    <Minus className="w-4 h-4" />
                  </button>
                  <span className="text-[18px] sm:text-[20px] font-bold text-ink-primary tabular-nums">{banos}</span>
                  <button
                    type="button"
                    onClick={() => setBanos((prev) => Math.min(8, prev + 1))}
                    className="w-11 h-11 rounded-lg border border-ink-border bg-surface text-ink-primary hover:bg-white hover:border-brand-500 flex items-center justify-center transition-all shadow-xs text-lg"
                    aria-label="Aumentar baños"
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Parqueaderos */}
              <div className="space-y-1.5 p-3.5 rounded-xl bg-canvas border border-ink-border">
                <span className="text-[14px] font-semibold text-ink-primary uppercase block">
                  Parqueaderos
                </span>
                <div className="flex items-center justify-between pt-1">
                  <button
                    type="button"
                    onClick={() => setParqueaderos((prev) => Math.max(0, prev - 1))}
                    className="w-11 h-11 rounded-lg border border-ink-border bg-surface text-ink-primary hover:bg-white hover:border-brand-500 flex items-center justify-center transition-all shadow-xs text-lg"
                    aria-label="Disminuir parqueaderos"
                  >
                    <Minus className="w-4 h-4" />
                  </button>
                  <span className="text-[18px] sm:text-[20px] font-bold text-ink-primary tabular-nums">{parqueaderos}</span>
                  <button
                    type="button"
                    onClick={() => setParqueaderos((prev) => Math.min(6, prev + 1))}
                    className="w-11 h-11 rounded-lg border border-ink-border bg-surface text-ink-primary hover:bg-white hover:border-brand-500 flex items-center justify-center transition-all shadow-xs text-lg"
                    aria-label="Aumentar parqueaderos"
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* Navigation Step 2 Buttons */}
            <div className="pt-2 flex items-center justify-between">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="min-h-[48px] px-5 py-3 rounded-xl border border-ink-border bg-surface text-ink-secondary text-[15px] font-semibold hover:border-ink-subtle hover:text-ink-primary transition-colors flex items-center gap-2"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Paso anterior</span>
              </button>
              <button
                type="button"
                disabled={!isStep2Valid}
                onClick={() => setStep(3)}
                className="min-h-[48px] px-6 py-3 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-bold text-[15px] sm:text-[16px] tracking-wide shadow-card hover:shadow-card-hover disabled:opacity-40 disabled:pointer-events-none transition-all flex items-center gap-2"
              >
                <span>Continuar a Detalles</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* ===================== PASO 3: DETALLES ADICIONALES Y AMENIDADES ===================== */}
        {step === 3 && (
          <div className="space-y-6 animate-fadeIn">
            {/* Estrato y Antigüedad */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-[14px] font-semibold text-ink-primary uppercase tracking-wider block">
                  Estrato Socioeconómico
                </label>
                <div className="grid grid-cols-6 gap-1.5">
                  {[1, 2, 3, 4, 5, 6].map((est) => {
                    const active = estrato === est;
                    return (
                      <button
                        key={est}
                        type="button"
                        onClick={() => setEstrato(active ? null : est)}
                        className={`min-h-[46px] rounded-xl border text-[15px] font-bold transition-all ${
                          active
                            ? 'bg-brand-500 text-white border-brand-500 shadow-xs'
                            : 'bg-canvas border-ink-border text-ink-secondary hover:border-ink-subtle hover:text-ink-primary'
                        }`}
                      >
                        {est}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-[14px] font-semibold text-ink-primary uppercase tracking-wider block">
                  Antigüedad
                </label>
                <select
                  value={antiguedad}
                  onChange={(e) => setAntiguedad(e.target.value)}
                  className="w-full min-h-[48px] bg-surface border border-ink-border rounded-xl px-3.5 py-2.5 text-[16px] text-ink-primary focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                >
                  {ANTIGUEDADES_OPCIONES.map((opt) => (
                    <option key={opt.id} value={opt.id}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Piso y Administración */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-[14px] font-semibold text-ink-primary uppercase tracking-wider block">
                  Piso del Inmueble (Opcional)
                </label>
                <input
                  type="number"
                  min={1}
                  max={60}
                  placeholder="Ej: 5"
                  value={piso}
                  onChange={(e) => setPiso(e.target.value)}
                  className="w-full min-h-[48px] bg-surface border border-ink-border rounded-xl px-3.5 py-2.5 text-[16px] text-ink-primary placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[14px] font-semibold text-ink-primary uppercase tracking-wider block">
                  Cuota Administración Mensual (COP)
                </label>
                <input
                  type="number"
                  min={0}
                  step={50000}
                  placeholder="Ej: 450000"
                  value={administracion}
                  onChange={(e) => setAdministracion(e.target.value)}
                  className="w-full min-h-[48px] bg-surface border border-ink-border rounded-xl px-3.5 py-2.5 text-[16px] text-ink-primary placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                />
              </div>
            </div>

            {/* Amenidades y Comodidades */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-[14px] font-semibold text-ink-primary uppercase tracking-wider">
                  Comodidades y amenidades
                </label>
                <span className="text-[13px] text-brand-600 font-semibold">
                  {comodidades.length} seleccionadas
                </span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 max-h-52 overflow-y-auto p-1">
                {COMODIDADES_LISTA.map((item) => {
                  const selected = comodidades.includes(item.id);
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => toggleComodidad(item.id)}
                      className={`min-h-[44px] px-3 py-2 rounded-xl border text-left text-[14px] transition-all flex items-center justify-between ${
                        selected
                          ? 'bg-brand-100 text-brand-800 border-brand-300 font-semibold'
                          : 'bg-canvas text-ink-secondary border-ink-border hover:border-ink-subtle hover:text-ink-primary'
                      }`}
                    >
                      <span className="truncate mr-1">{item.label}</span>
                      {selected && <Check className="w-3.5 h-3.5 text-brand-600 shrink-0" />}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Final Submit Button */}
            <div className="pt-2 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
              <button
                type="button"
                onClick={() => setStep(2)}
                className="min-h-[48px] px-5 py-3 rounded-xl border border-ink-border bg-surface text-ink-secondary text-[15px] font-semibold hover:border-ink-subtle hover:text-ink-primary transition-colors flex items-center justify-center gap-2"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Paso anterior</span>
              </button>
              <button
                type="submit"
                disabled={isLoading || !backendReady || !isStep1Valid || !isStep2Valid}
                className="min-h-[52px] flex-1 py-3 px-6 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-bold text-[16px] tracking-wide shadow-card hover:shadow-card-hover active:scale-[0.99] disabled:opacity-50 disabled:pointer-events-none transition-all flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    <span>Analizando inmueble y comparables...</span>
                    <span className="text-[13px] opacity-80 font-normal ml-1">(calibrando modelo)</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>Calcular Avalúo Valora</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </form>
    </div>
  );
};
