import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  studioFromPath,
  REGISTERED_ROUTE_PREFIXES,
  APP_SCOPED_ROUTE_PREFIXES,
} from '../studioFromPath';

describe('studioFromPath — app-scoped route prefixes', () => {
  it('keeps the Carbon studio on /carbon, /guide/carbon and /journey/carbon', () => {
    expect(studioFromPath('/carbon/my-data')).toBe('carbon');
    expect(studioFromPath('/carbon/dashboard')).toBe('carbon');
    expect(studioFromPath('/guide/carbon')).toBe('carbon');
    expect(studioFromPath('/guide/carbon/D2')).toBe('carbon');
    expect(studioFromPath('/journey/carbon')).toBe('carbon');
    expect(studioFromPath('/journey/carbon/D2')).toBe('carbon');
    expect(studioFromPath('/journey/carbon/station-4')).toBe('carbon');
  });

  it('keeps the Carbon studio on every carbon route the sidebar links to', () => {
    // The Coverage and Campus intake entries must not empty the Carbon sidebar.
    expect(studioFromPath('/carbon/admin/inventory-coverage')).toBe('carbon');
    expect(studioFromPath('/carbon/admin/inventory-coverage/')).toBe('carbon');
    expect(studioFromPath('/carbon/admin/coverage-targets')).toBe('carbon');
    expect(studioFromPath('/carbon/admin/coverage-targets/5')).toBe('carbon');
    expect(studioFromPath('/carbon/onboarding/intake')).toBe('carbon');
    expect(studioFromPath('/carbon/onboarding/intake?source=42')).toBe('carbon');
    expect(studioFromPath('/carbon/onboarding')).toBe('carbon');
    expect(studioFromPath('/carbon/reporting/periods')).toBe('carbon');
  });

  it('maps any app-scoped router to the app id in the path', () => {
    expect(studioFromPath('/journey/people')).toBe('people');
    expect(studioFromPath('/guide/healthy')).toBe('healthy');
    expect(studioFromPath('/apps/gradevance/qa')).toBe('gradevance');
    expect(studioFromPath('/journey/team')).toBe('team');
  });

  it('does not invent a studio for the shared pack or unregistered apps', () => {
    expect(studioFromPath('/guide/_platform')).toBe('home');
    expect(studioFromPath('/journey/_platform')).toBe('home');
    expect(studioFromPath('/journey/not-an-app')).toBe('home');
  });

  it('still maps platform studios and other app namespaces', () => {
    expect(studioFromPath('/')).toBe('home');
    expect(studioFromPath('/login')).toBe('home');
    expect(studioFromPath('/catalog/products')).toBe('catalog');
    expect(studioFromPath('/admin/ai/domain')).toBe('ai-admin');
    expect(studioFromPath('/admin/users')).toBe('admin');
    expect(studioFromPath('/people/employees')).toBe('people');
    expect(studioFromPath('/my/leave')).toBe('my');
    expect(studioFromPath('/team/history')).toBe('team');
    expect(studioFromPath('/settings/profile')).toBe('settings');
    expect(studioFromPath('/help/carbon')).toBe('help');
  });
});

describe('studioFromPath — route registration gate (RULE_15)', () => {
  it('covers every top-level route prefix declared in App.jsx', () => {
    const appPath = path.resolve(process.cwd(), 'src/App.jsx');
    const source = fs.readFileSync(appPath, 'utf8');
    const prefixes = new Set();
    for (const match of source.matchAll(/path="([^"]*)"/g)) {
      const first = match[1].split('/').filter(Boolean)[0];
      if (!first || first === '*') continue;
      prefixes.add(first);
    }

    const unregistered = [...prefixes].filter((p) => !REGISTERED_ROUTE_PREFIXES.has(p));
    expect(
      unregistered,
      `Register these route prefixes in src/shell/studioFromPath.js `
        + `(PLATFORM_ROUTE_STUDIOS / HOME_ROUTE_PREFIXES / APP_SCOPED_ROUTE_PREFIXES) `
        + `or in the app manifest routePrefix. Unregistered app-scoped prefixes empty the sidebar.`,
    ).toEqual([]);
  });

  it('documents the app-scoped router registration point', () => {
    // If you add an app-scoped router to App.jsx, add it here — this assertion
    // is the reminder that the router list is a deliberate registry, not a
    // string match. Update both lists together.
    expect(APP_SCOPED_ROUTE_PREFIXES).toContain('journey');
    expect(APP_SCOPED_ROUTE_PREFIXES).toContain('guide');
  });
});
