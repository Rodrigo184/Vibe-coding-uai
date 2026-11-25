import type { Config } from 'tailwindcss'

// Tokens visuales del SPEC (sección 10.1) — misma paleta de la presentación.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        ink: '#1B2430',
        muted: '#5B6B82',
        teal: { DEFAULT: '#00B4D8', dk: '#0097B5', tx: '#00738A' },
        amber: { DEFAULT: '#E6A100', tx: '#8A6100' },
        violet: { DEFAULT: '#7C6CF0', tx: '#5B4BD1' },
        red: { DEFAULT: '#E63946', tx: '#C1242F' },
        green: { DEFAULT: '#2EA66B', tx: '#1E7A4D' },
        panel: '#F7F9FC',
        line: '#DCE3EC',
        console: '#0F1A14',
        night: { DEFAULT: '#0F141B', card: '#161D27', line: '#273244', text: '#E6EDF5', muted: '#9AA8BB' },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(27,36,48,.06), 0 1px 3px rgba(27,36,48,.08)',
        pop: '0 8px 24px rgba(27,36,48,.16)',
      },
      keyframes: {
        pulsering: { '0%,100%': { boxShadow: '0 0 0 0 rgba(230,57,70,.45)' }, '50%': { boxShadow: '0 0 0 8px rgba(230,57,70,0)' } },
        blink: { '0%,100%': { opacity: '1' }, '50%': { opacity: '.35' } },
      },
      animation: { pulsering: 'pulsering 1.2s ease-in-out infinite', blink: 'blink .6s ease-in-out 3' },
    },
  },
  plugins: [],
} satisfies Config
