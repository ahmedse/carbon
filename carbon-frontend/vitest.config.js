import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { readFileSync } from 'fs';
import { resolve } from 'path';

// Load .env manually so import.meta.env.VITE_* works in tests
function loadEnv() {
  try {
    const envPath = resolve(import.meta.dirname, '.env');
    const content = readFileSync(envPath, 'utf-8');
    const vars = {};
    for (const line of content.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) continue;
      const eq = trimmed.indexOf('=');
      if (eq === -1) continue;
      vars[trimmed.slice(0, eq)] = trimmed.slice(eq + 1);
    }
    return vars;
  } catch {
    return {};
  }
}

const envVars = loadEnv();

export default defineConfig({
  plugins: [
    react(),
    // Stub `.css` imports (e.g. `@mui/x-data-grid/esm/index.css`) so tests
    // don't fail with "Unknown file extension .css". RULE: tests never need
    // real stylesheets — jsdom only.
    {
      name: 'stub-css-imports',
      enforce: 'pre',
      load(id) {
        if (id.endsWith('.css')) return '';
      },
    },
  ],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/setupTests.js',
    css: false,
    server: {
      deps: {
        // @mui/x-data-grid imports `esm/index.css`; Node's native ESM loader
        // can't parse CSS, so inline the package and let Vite + the css stub
        // (plugin above) handle it instead of externalizing it.
        inline: ['@mui/x-data-grid'],
      },
    },
    exclude: [
      '**/node_modules/**',
      '**/dist/**',
      '**/e2e/**',
      '**/test-results/**',
      // Playwright E2E specs (tests/*.spec.cjs) — not vitest units
      '**/tests/**',
    ],
    testTimeout: 15000,
    env: {
      VITE_API_BASE_URL: envVars.VITE_API_BASE_URL || 'http://127.0.0.1:8000/carbon-api/',
      VITE_API_TIMEOUT: envVars.VITE_API_TIMEOUT || '30000',
      VITE_BASE: envVars.VITE_BASE || '/',
      VITE_PULSE_HOST: envVars.VITE_PULSE_HOST || 'http://127.0.0.1:9100',
      VITE_PULSE_INSTANCE_ID: envVars.VITE_PULSE_INSTANCE_ID || 'carbon',
    },
  },
});
