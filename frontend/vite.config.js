import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, /api goes to the ADK agent server (adk web / adk api_server on :8000),
// so the browser never needs CORS. In production set VITE_API_URL to the Cloud Run URL.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
})
