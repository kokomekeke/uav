// vite.config.ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],

  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@leaflet': 'leaflet/dist/leaflet.js'
    }
  },

  server: {
    proxy: {
      '/v1': {
        target: 'http://192.168.0.82:5000',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/v1/, '/v1')
      }
    }
  }
})
