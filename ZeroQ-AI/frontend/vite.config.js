import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Backend for the dev proxy; override with VITE_API_TARGET (e.g. http://localhost:8010).
const apiTarget = process.env.VITE_API_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        ws: true,
      },
      '/uploads': {
        target: apiTarget,
        changeOrigin: true,
      }
    }
  }
})

