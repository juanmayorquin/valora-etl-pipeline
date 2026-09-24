export const COMODIDADES_LISTA = [
  { id: 'ascensor', label: 'Ascensor', category: 'edificio' },
  { id: 'conjunto_cerrado', label: 'Conjunto cerrado', category: 'seguridad' },
  { id: 'vigilancia', label: 'Vigilancia 24/7', category: 'seguridad' },
  { id: 'gimnasio', label: 'Gimnasio', category: 'social' },
  { id: 'piscina', label: 'Piscina', category: 'social' },
  { id: 'balcon', label: 'Balcón', category: 'inmueble' },
  { id: 'terraza', label: 'Terraza', category: 'inmueble' },
  { id: 'estudio', label: 'Estudio / Home Office', category: 'inmueble' },
  { id: 'deposito', label: 'Depósito / Locker', category: 'inmueble' },
  { id: 'chimenea', label: 'Chimenea', category: 'inmueble' },
  { id: 'amoblado', label: 'Amoblado', category: 'inmueble' },
  { id: 'cocina_integral', label: 'Cocina integral', category: 'inmueble' },
  { id: 'parqueadero_visitantes', label: 'Parq. visitantes', category: 'edificio' },
  { id: 'zonas_verdes', label: 'Zonas verdes / Parque', category: 'social' },
  { id: 'transporte', label: 'Cerca a transporte', category: 'ubicacion' },
  { id: 'colegios', label: 'Cerca a colegios', category: 'ubicacion' },
];

export const ANTIGUEDADES_OPCIONES = [
  { id: '', label: 'Sin especificar (promedio)' },
  { id: 'Menos de 1 año', label: 'Nuevo (menos de 1 año)' },
  { id: 'Entre 0 y 5 años', label: 'Entre 0 y 5 años' },
  { id: 'Entre 5 y 10 años', label: 'Entre 5 y 10 años' },
  { id: 'Entre 10 y 20 años', label: 'Entre 10 y 20 años' },
  { id: 'Más de 20 años', label: 'Más de 20 años' },
];

export const OBJETIVOS_USUARIO = [
  {
    id: 'vender',
    titulo: 'Quiero vender',
    descripcion: 'Conocer precio sugerido de venta, valor por m² y rango de mercado.',
  },
  {
    id: 'arrendar',
    titulo: 'Quiero arrendar',
    descripcion: 'Estimar el canon mensual competitivo y evitar tiempos desocupado.',
  },
  {
    id: 'ambas',
    titulo: 'Comparar ambas',
    descripcion: 'Evaluar venta vs arriendo y calcular la rentabilidad bruta anual.',
  },
] as const;

export const TIPOS_INMUEBLE = [
  { id: 'apartamento', label: 'Apartamento', desc: 'En edificio o conjunto residencial' },
  { id: 'casa', label: 'Casa', desc: 'Unifamiliar o en condominio' },
  { id: 'apartaestudio', label: 'Apartaestudio', desc: '1 ambiente o monoambiente' },
] as const;
