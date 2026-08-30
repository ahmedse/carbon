// src/__tests__/PeopleManifest.test.jsx
// Regression guard for the People app manifest registration.

import { describe, it, expect } from 'vitest';
import peopleManifest from '../apps/people/manifest';
import { APP_REGISTRY } from '../apps/registry';

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
});
