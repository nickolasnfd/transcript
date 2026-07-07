import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy para o backend FastAPI em localhost:8000
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
