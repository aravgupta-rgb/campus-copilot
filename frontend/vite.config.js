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
        ws: true, // live voice websocket (/run_live)
        rewrite: (p) => p.replace(/^\/api/, ''),
        // The agent server rejects browser Origins it doesn't know (403). This proxy is
        // local and same-machine, so forward requests and the voice socket without one.
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => proxyReq.removeHeader('origin'))
          proxy.on('proxyReqWs', (proxyReq) => proxyReq.removeHeader('origin'))
        },
      },
    },
  },
})
