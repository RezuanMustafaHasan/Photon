/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#FFF7ED',
        primary: '#0F172A',
        secondary: '#475569',
        accent: '#22C55E',
        'cta-start': '#FF4D4D',
        'cta-end': '#FF9F1C',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        bangla: ['Hind Siliguri', 'Noto Sans Bengali', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
