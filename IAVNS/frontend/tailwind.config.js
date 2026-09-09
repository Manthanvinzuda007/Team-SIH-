/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        polaris: {
          dark: '#020617', // slate-950
          panel: '#0f172a', // slate-900
          border: '#1e293b', // slate-800
          accent: '#0ea5e9', // sky-500
          text: '#94a3b8', // slate-400
          text_bright: '#f1f5f9', // slate-100
          danger: '#ef4444', // red-500
          warning: '#f59e0b', // amber-500
          success: '#10b981', // emerald-500
        }
      }
    },
  },
  plugins: [],
}
