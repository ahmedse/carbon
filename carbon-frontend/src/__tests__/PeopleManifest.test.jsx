// src/__tests__/PeopleManifest.test.jsx
// Regression guard for the People app manifest registration.
// NSR-6A Path H: Attendance + Rotation out of go-live nav; Certifications stay.

import { describe, it, expect } from 'vitest';
import peopleManifest from '../apps/people/manifest';
import { APP_REGISTRY } from '../apps/registry';
import { PEOPLE_HOME_MODULES } from '../apps/people/PeopleHome';

const GO_LIVE_PATHS = PEOPLE_HOME_MODULES.map((m) => m.path);

describe('People app manifest', () => {
  it('registers with id "people"', () => {
    expect(peopleManifest.id).toBe('people');
    expect(APP_REGISTRY.some((m) => m.id === 'people')).toBe(true);
  });

  it('uses /people as its route prefix', () => {
    expect(peopleManifest.routePrefix).toBe('/people');
  });

  it('declares a role:* landing navigation item at /people', () => {
    const landing = peopleManifest.navigation.items.find(
      (i) => i.role === '*' && i.path === '/people',
    );
    expect(landing).toBeTruthy();
  });

  it('includes NSR-6A go-live module paths in navigation', () => {
    const paths = peopleManifest.navigation.items.map((i) => i.path).filter(Boolean);
    for (const path of GO_LIVE_PATHS) {
      expect(paths).toContain(path);
    }
  });

  it('keeps Certifications in go-live navigation', () => {
    const paths = peopleManifest.navigation.items.map((i) => i.path).filter(Boolean);
    expect(paths).toContain('/people/certifications');
  });

  it('does not expose Attendance or Rotation in go-live navigation (Path H)', () => {
    const paths = peopleManifest.navigation.items.map((i) => i.path).filter(Boolean);
    expect(paths).not.toContain('/people/attendance');
    expect(paths).not.toContain('/people/rotation');
  });

  it('does not register a ghost /people/benefits nav target', () => {
    const paths = peopleManifest.navigation.items.map((i) => i.path).filter(Boolean);
    expect(paths).not.toContain('/people/benefits');
  });
});
