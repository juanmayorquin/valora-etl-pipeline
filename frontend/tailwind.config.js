/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        canvas: '#F5F7F4',       // Fondo general cálido
        surface: '#FFFFFF',      // Superficie principal / tarjetas
        brand: {
          50: '#F0FAF5',
          100: '#DDF3E8',        // Verde claro de marca
          200: '#BFE7D3',
          300: '#8DD3B0',
          400: '#4EB784',
          500: '#176B45',        // Verde de marca principal
          600: '#135838',
          700: '#0F442C',
          800: '#0B3321',
          900: '#082317',
          950: '#04130C',
        },
        ink: {
          primary: '#142B3A',    // Azul oscuro para títulos y texto principal
          secondary: '#63727A',  // Gris secundario
          muted: '#8E9CA3',      // Gris atenuado / placeholders
          subtle: '#CBD5DC',     // Bordes sutiles
          border: '#E3E8EC',     // Bordes generales de tarjetas
        },
        warning: {
          50: '#FEF9EE',
          100: '#FDF2DC',
          500: '#E9A83B',        // Amarillo para advertencias
          600: '#D39126',
        },
        danger: {
          50: '#FDF2F2',
          100: '#FCE6E6',
          500: '#C95757',        // Rojo para errores
          600: '#B24242',
        },
        chart: {
          50: '#F1F7FB',
          100: '#E2F0F7',
          500: '#3C82A8',        // Azul auxiliar para gráficos y contexto del modelo
          600: '#2F6C8D',
        },
        navy: {
          900: '#142B3A',
          950: '#0C1C27',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['"Plus Jakarta Sans"', 'Manrope', 'Inter', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      // Escala visual solicitada
      fontSize: {
        'hero': ['48px', { lineHeight: '1.15', fontWeight: '800' }],
        'hero-mobile': ['36px', { lineHeight: '1.2', fontWeight: '800' }],
        'section': ['24px', { lineHeight: '1.3', fontWeight: '700' }],
        'price': ['40px', { lineHeight: '1.1', fontWeight: '900' }],
        'price-mobile': ['34px', { lineHeight: '1.15', fontWeight: '900' }],
        'base-text': ['16px', { lineHeight: '1.6' }],
        'secondary-text': ['15px', { lineHeight: '1.55' }],
        'nav-text': ['15px', { lineHeight: '1.4', fontWeight: '500' }],
        'btn-text': ['15.5px', { lineHeight: '1.4', fontWeight: '600' }],
        'label-text': ['14px', { lineHeight: '1.4', fontWeight: '600' }],
      },
      boxShadow: {
        'subtle': '0 1px 3px 0 rgba(20, 43, 58, 0.04), 0 1px 2px -1px rgba(20, 43, 58, 0.02)',
        'card': '0 4px 12px -2px rgba(20, 43, 58, 0.05), 0 2px 6px -2px rgba(20, 43, 58, 0.03)',
        'card-hover': '0 10px 24px -4px rgba(20, 43, 58, 0.08), 0 4px 8px -3px rgba(20, 43, 58, 0.04)',
        'elevated': '0 20px 30px -8px rgba(20, 43, 58, 0.12), 0 8px 12px -4px rgba(20, 43, 58, 0.06)',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSlow: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
      },
      animation: {
        fadeIn: 'fadeIn 0.35s ease-out forwards',
        'pulse-slow': 'pulseSlow 2.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
    },
  },
  plugins: [],
}
