/** @type {import('tailwindcss').Config} */
const defaultTheme = require('tailwindcss/defaultTheme')

module.exports = {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx,vue}'
  ],
  theme: {
    extend: {
      colors: {
        'sgx-dark-blue': '#0A1F44',
        'sgx-blue': '#342484',
        'sgx-electric-blue': '#7DF9FF',
        'sgx-deep-blue': '#050457',
        'sgx-accent-blue': '#0071f2',
        'sgx-accent-light-blue': '#add8e6',
        'sgx-dark': '#0F0F0F',
        'sgx-blue-light': '#4c3d9e',
        'sgx-darker-blue': '#05040D'
      },
      fontFamily: {
        sans: ['Inter var', ...defaultTheme.fontFamily.sans]
      },
      boxShadow: {
        'inset-red': 'inset 4px 4px 30px 4px rgba(0, 0, 0, 0.5)'
      },
      animation: {
        glow: 'glow 1.5s infinite'
      },
      keyframes: {
        glow: {
          '0%, 100%': { boxShadow: '0 0 10px #ff00ff' },
          '50%': { boxShadow: '0 0 20px #ff00ff' }
        }
      }
    }
  },
  plugins: [
    require('@tailwindcss/typography'),
    require('@tailwindcss/forms'),
    require('@tailwindcss/aspect-ratio'),
    require('@tailwindcss/container-queries')
  ]
}
