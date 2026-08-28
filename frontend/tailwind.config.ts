import type { Config } from 'tailwindcss'

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        risk: {
          safe: '#22c55e',
          suspicious: '#eab308',
          critical: '#ef4444',
        },
      },
      boxShadow: {
        glow: '0 0 40px rgba(56, 189, 248, 0.14)',
      },
    },
  },
  plugins: [],
} satisfies Config
