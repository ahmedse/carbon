// Playwright E2E configuration for Carbon Platform production simulation.
// Simulates real user journeys across 2 branches (Alamein, Smart Village),
// RBAC enforcement, data entry, DQ violations, governance, and reports.
import { defineConfig, devices } from '@playwright/test';

const BASE_URL = process.env.CARBON_BASE_URL || 'http://127.0.0.1:5179';
const API_URL = process.env.CARBON_API_URL || 'http://127.0.0.1:8009';

export default defineConfig({
  testDir: './journeys',
  fullyParallel: false,          // Sequential for realistic multi-user simulation
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,                    // Single worker to avoid auth conflicts
  reporter: [
    ['list'],
    ['json', { outputFile: 'e2e-results.json' }],
    ['html', { outputFolder: 'e2e-report', open: 'never' }],
  ],
  timeout: 60_000,
  expect: { timeout: 10_000 },

  use: {
    baseURL: BASE_URL,
    apiURL: API_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
        launchOptions: {
          args: ['--disable-web-security'], // CORS for local dev
        },
      },
    },
  ],

  // Start the dev server if not already running
  webServer: process.env.CI ? undefined : [
    {
      command: 'cd ../backend && python manage.py runserver 0.0.0.0:8009 --noreload 2>&1',
      port: 8009,
      reuseExistingServer: true,
      timeout: 30_000,
    },
    {
      command: 'npm run dev',
      port: 5179,
      reuseExistingServer: true,
      timeout: 30_000,
    },
  ],
});
