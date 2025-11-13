/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./frontend/index.html', './frontend/src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif']
      },
      backgroundImage: {
        'grid-dots':
          'radial-gradient(rgba(255,255,255,0.05) 1px, transparent 1px)'
      },
      backgroundSize: {
        'grid-dots': '20px 20px'
      }
    }
  },
  plugins: []
};


