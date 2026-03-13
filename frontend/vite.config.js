import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // Proxy API calls to FastAPI backend during development
      '/chat': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/tools': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
  build: {
    outDir: '../backend/frontend',  // Build directly into backend/frontend
    emptyOutDir: true,
  },
})
