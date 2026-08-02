/* eslint-env node */
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  // Load env file based on `mode` (e.g. 'production')
  const env = loadEnv(mode, process.cwd(), '')
  return {
    base: env.VITE_BASE || '/',
    plugins: [react()],
    server: {
      port: Number(env.VITE_PORT || env.PORT || 5179),
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