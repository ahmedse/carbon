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
            // Split MUI into separate chunks — the combined chunk was 643 kB (over the
            // 500 kB warning limit). Keeping @mui/material, the icons set, and the date
            // pickers apart lets the browser cache and load each independently.
            'mui-core': ['@mui/material'],
            'mui-icons': ['@mui/icons-material'],
            'mui-date-pickers': ['@mui/x-date-pickers'],
            vendor: ['react', 'react-dom', 'react-router-dom'],
          },
        },
      },
    },
  }
})