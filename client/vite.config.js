import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      '@leaflet': 'leaflet/dist/leaflet.js'
    }
  },
  server: {
    proxy: {
      '/v1': {
        target: 'http://192.168.0.82:5000', // A backend szerver címe
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/v1/, '/v1') // Útvonal átirányítás
      }
    }
  }
})
