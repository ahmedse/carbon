// Throwaway watch config — records video + trace for every test so the run can
// be "watched" after the fact (this remote has no live X server, so a real
// visible browser window is not possible). Reuses the base config as-is.
import { defineConfig } from '@playwright/test';
import baseConfig from './playwright.config';

export default defineConfig({
  ...baseConfig,
  use: {
    ...baseConfig.use,
    video: 'on',
    trace: 'on',
  },
});
