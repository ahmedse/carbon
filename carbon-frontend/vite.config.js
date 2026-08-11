/* eslint-env node */
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  // Load env file based on `mode` (e.g. 'production')
  const env = loadEnv(mode, process.cwd(), '')
  return {
    base: env.VITE_BASE || '/',
    plugins: [react()],
    // Persist dep cache outside node_modules/.vite so manage.sh's cache-clear doesn't
    // force a full re-optimization on every restart (which causes the WS startup errors).
    cacheDir: '.vite',
    server: {
      port: Number(env.VITE_PORT || env.PORT || 5179),
      strictPort: true,   // fail loudly if port is taken rather than silently switching
      // No explicit hmr block — Vite auto-derives host/port/protocol from base + server config.
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            mui: ['@mui/material', '@mui/icons-material', '@mui/x-date-pickers'],
            vendor: ['react', 'react-dom', 'react-router-dom'],
          },
        },
      },
    },
  }
})