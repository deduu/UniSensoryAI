/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        sidebar: {
          bg: '#0f172a',
          hover: '#1e293b',
          active: '#1e293b',
          text: '#94a3b8',
          'text-active': '#f1f5f9',
        },
        brand: {
          DEFAULT: '#6366f1',
          hover: '#4f46e5',
          light: '#e0e7ff',
        },
        surface: {
          DEFAULT: '#ffffff',
          muted: '#f8fafc',
          subtle: '#f1f5f9',
          border: '#e2e8f0',
        },
        status: {
          pending: '#94a3b8',
          processing: '#f59e0b',
          completed: '#10b981',
          failed: '#ef4444',
        },
        ink: {
          DEFAULT: '#0f172a',
          muted: '#64748b',
          faint: '#94a3b8',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 3px 0 rgba(0,0,0,0.06), 0 1px 2px -1px rgba(0,0,0,0.04)',
        'card-hover': '0 4px 12px 0 rgba(0,0,0,0.08)',
        modal: '0 20px 60px -10px rgba(0,0,0,0.3)',
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
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
      },
      animation: {
        'pulse-ring': 'pulse-ring 1.5s ease-in-out infinite',
        'slide-in': 'slide-in 0.25s ease-out',
        'fade-in': 'fade-in 0.2s ease-out',
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
}
