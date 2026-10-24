/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0a0a0f',
        panel: 'rgba(255, 255, 255, 0.03)',
        'panel-border': 'rgba(255, 255, 255, 0.08)',
        accent: {
          purple: '#b061ff',
          cyan: '#3bd4ff',
        }
      },
      fontFamily: {
        sans: ['"Inter Variable"', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
