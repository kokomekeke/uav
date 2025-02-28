import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  },
  server: {
    proxy: {
      '/v1': {
        target: 'http://192.168.1.245:5000', // A backend szerver címe
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/v1/, '/v1') // Útvonal átirányítás
      }
    }
  }
})
