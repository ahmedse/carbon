import fs from 'node:fs';
import path from 'node:path';
import { describe, it, expect } from 'vitest';

import manifest from '../manifest';

const read = (rel) => fs.readFileSync(path.resolve(process.cwd(), rel), 'utf8');

const items = manifest.navigation.items.filter((item) => item.label);
const labels = items.map((item) => item.label);
const paths = items.map((item) => item.path);

describe('Carbon navigation after retiring "My guide"', () => {
  it('no longer offers a "My guide" entry, and no nav item points at the retired hub', () => {
    expect(labels).not.toContain('My guide');
    expect(paths.some((p) => String(p).startsWith('/guide'))).toBe(false);
  });

  it('keeps Journey and Campus intake as the teaching entry points', () => {
    expect(paths).toContain('/carbon/onboarding');
    expect(paths).toContain('/carbon/onboarding/intake');
  });

  it('adds Coverage as the driver entry, gated to the coverage capability', () => {
    const coverage = items.find((item) => item.label === 'Coverage');
    expect(coverage).toBeTruthy();
    expect(coverage.path).toBe('/carbon/admin/inventory-coverage');
    expect(coverage.role).toBe('carbon:admin');
  });

  it('keeps exactly one nav item pointing at the coverage page (no double highlight)', () => {
    const atCoverage = paths.filter((p) => p === '/carbon/admin/inventory-coverage');
    expect(atCoverage).toHaveLength(1);
  });

  it('drops the retired label and its icon mapping from the shell', () => {
    expect(read('src/shell/ShellSidebar.jsx')).not.toContain('My guide');
    expect(read('src/i18n/shellLabels.js')).not.toContain('myGuide');
    expect(read('src/i18n/locales/en/shell.json')).not.toContain('myGuide');
    expect(read('src/i18n/locales/ar/shell.json')).not.toContain('myGuide');
  });

  it('keeps the generic guide hub for other apps while Carbon aliases to Journey', () => {
    const page = read('src/pages/guide/GuidePage.jsx');
    // Carbon redirects; any other app still renders the shared hub.
    expect(page).toContain("appId === 'carbon'");
    expect(page).toContain('GuideHub');
    // The retired hub is not dead code: the generic path still uses it.
    expect(fs.existsSync(path.resolve(process.cwd(), 'src/components/guide/GuideHub.jsx'))).toBe(true);
  });
});
