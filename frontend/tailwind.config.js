/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Sidebar tokens — alias to surface/ink for theme awareness.
        // (`sidebar.text` and `sidebar.text-active` only used in legacy spots.)
        sidebar: {
          bg: 'rgb(var(--surface) / <alpha-value>)',
          hover: 'rgb(var(--surface-subtle))',
          active: 'rgb(var(--surface-border))',
          text: 'rgb(var(--ink-muted) / <alpha-value>)',
          'text-active': 'rgb(var(--ink) / <alpha-value>)',
        },
        // Brand stays static — looks the same in both themes.
        brand: {
          DEFAULT: '#6366f1', // Indigo 500
          hover: '#818cf8', // Indigo 400
          light: 'rgba(99, 102, 241, 0.15)',
          glow: 'rgba(99, 102, 241, 0.5)',
        },
        surface: {
          DEFAULT: 'rgb(var(--surface) / <alpha-value>)',
          muted: 'rgb(var(--surface-muted) / <alpha-value>)',
          subtle: 'rgb(var(--surface-subtle))',
          border: 'rgb(var(--surface-border))',
          glass: 'rgb(var(--surface-glass))',
        },
        // Status colors stay static — semantic meaning is theme-agnostic.
        status: {
          pending: '#a1a1aa',
          processing: '#f59e0b',
          completed: '#10b981',
          failed: '#ef4444',
        },
        ink: {
          DEFAULT: 'rgb(var(--ink) / <alpha-value>)',
          muted: 'rgb(var(--ink-muted) / <alpha-value>)',
          faint: 'rgb(var(--ink-faint) / <alpha-value>)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        card: '0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -2px rgba(0, 0, 0, 0.3)',
        'card-hover': '0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -4px rgba(0, 0, 0, 0.4), 0 0 20px rgba(99, 102, 241, 0.15)',
        modal: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
        glow: '0 0 15px rgba(99, 102, 241, 0.5)',
      },
      cursor: {
        'col-resize': 'col-resize',
        'row-resize': 'row-resize',
      },
      keyframes: {
        'pulse-ring': {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.5', transform: 'scale(1.4)' },
        },
        'slide-in': {
          from: { transform: 'translateX(100%)', opacity: '0' },
          to: { transform: 'translateX(0)', opacity: '1' },
        },
        'slide-in-right': {
          from: { transform: 'translateX(20px)', opacity: '0' },
          to: { transform: 'translateX(0)', opacity: '1' },
        },
        'slide-up-panel': {
          from: { transform: 'translateY(20px)', opacity: '0' },
          to: { transform: 'translateY(0)', opacity: '1' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'slide-up-fade': {
          from: { transform: 'translateY(16px)', opacity: '0' },
          to: { transform: 'translateY(0)', opacity: '1' },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-5px)' },
        },
        'shimmer': {
          from: { backgroundPosition: '200% 0' },
          to: { backgroundPosition: '-200% 0' },
        }
      },
      animation: {
        'pulse-ring': 'pulse-ring 1.5s ease-in-out infinite',
        'slide-in': 'slide-in 0.25s ease-out',
        'slide-in-right': 'slide-in-right 0.2s ease-out',
        'slide-up-panel': 'slide-up-panel 0.2s ease-out',
        'fade-in': 'fade-in 0.2s ease-out',
        'slide-up-fade': 'slide-up-fade 0.5s ease-out forwards',
        'float': 'float 3s ease-in-out infinite',
        'shimmer': 'shimmer 8s ease-in-out infinite',
      },
    },
  },
  plugins: [require('@tailwindcss/forms'), require('@tailwindcss/typography')],
}
