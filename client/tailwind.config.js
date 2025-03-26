/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx,vue}'
  ],
  theme: {
    extend: {
      boxShadow: {
        'inset-red': 'inset 4px 4px 30px 4px rgba(0, 0, 0, 0.5)'
      }
    }
  },
  plugins: []
}
