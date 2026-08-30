// This test reads App.jsx from the filesystem (Node `fs`/`path`/`process` are
// enabled for `src/__tests__/**` via `globals.node` in eslint.config.js).
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// Regression guard for RULE_22: every top-level route namespace must declare a
// bare-root index redirect so a bare namespace path (e.g. the `/carbon/`
// deployment mount path) never falls through to <Route path="*"> → NotFound.
// See TASK playbook PB-25 for the original bug.

const appSrc = readFileSync(resolve(process.cwd(), 'src/App.jsx'), 'utf8');

/** Extract `path` -> `to` pairs from `<Route path="..." element={<Navigate to="..." .../>} />`. */
function navigateRedirects(src) {
  const re = /<Route\s+path=\{?["']([^"']+)["']\}?\s+element=\{\s*<Navigate\s+to=\{?["']([^"']+)["']\}?\s+replace\s*\/>\s*\}/g;
  const map = new Map();
  let m;
  while ((m = re.exec(src)) !== null) map.set(m[1], m[2]);
  return map;
}

const redirects = navigateRedirects(appSrc);

describe('namespace-root index redirects (RULE_22)', () => {
  it('redirects bare /carbon to /carbon/chairman', () => {
    expect(redirects.get('/carbon')).toBe('/carbon/chairman');
  });

  it('redirects bare /admin to /admin/users', () => {
    expect(redirects.get('/admin')).toBe('/admin/users');
  });

  it('redirects /settings/profile and /settings/preferences to /settings', () => {
    expect(redirects.get('/settings/profile')).toBe('/settings');
    expect(redirects.get('/settings/preferences')).toBe('/settings');
  });

  it('redirects legacy /emissions/dashboard to the canonical dashboard', () => {
    expect(redirects.get('/emissions/dashboard')).toBe('/carbon/dashboard');
  });

  it('redirects /data-owner/reports/generate to /carbon/reporting/generate', () => {
    expect(redirects.get('/data-owner/reports/generate')).toBe('/carbon/reporting/generate');
  });

  it('redirects bare /modules, /scopes, /dashboards, /schema-admin', () => {
    expect(redirects.get('/modules')).toBe('/carbon/my-data');
    expect(redirects.get('/scopes')).toBe('/carbon/console');
    expect(redirects.get('/dashboards')).toBe('/carbon/dashboard');
    expect(redirects.get('/schema-admin')).toBe('/catalog/products');
  });
});
