/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          dark: '#030507',
          darkSecondary: '#05070A',
          darkTertiary: '#080A0E',
          panel: '#0B0D12',
          gold: '#D9A441',
          goldLight: '#F6C76B',
          goldPulsing: '#FFD88A',
          goldDark: '#B8860B',
          champagne: '#E8C98F',
          champagneLight: '#F2D9A0',
          textPrimary: '#F7F3EA',
          textSecondary: '#A8A8A8',
          textMuted: '#777777',
        }
      },
      fontFamily: {
        serif: ['"Playfair Display"', '"Cormorant Garamond"', 'Georgia', 'serif'],
        sans: ['Inter', 'Manrope', 'system-ui', 'sans-serif'],
      },
      lineHeight: {
        tightest: '0.95',
        tight: '1.08',
      }
    },
  },
  plugins: [],
}
