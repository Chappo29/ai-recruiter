import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/auth': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/vacancies': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/candidates': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/screenings': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/bots': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/questions': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/media': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
