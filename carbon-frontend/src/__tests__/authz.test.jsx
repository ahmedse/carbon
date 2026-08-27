// src/__tests__/authz.test.jsx — Comprehensive AuthZ Test Suite
// =============================================================================
// Covers: can(), isGlobalAdmin, isDomainLead, isCatalogAdmin, hasAppAccess,
//         expandCapabilities, hasCap, initCapabilities, getCapableApps,
//         legacy perspective fallback, edge cases, and capability inheritance.
// =============================================================================

import { describe, it, expect } from 'vitest';
import {
  can,
  isGlobalAdmin,
  isDomainLead,
  isCatalogAdmin,
  hasAppAccess,
  hasCap,
  expandCapabilities,
  initCapabilities,
  getCapableApps,
} from '../authz';

// ── Shared test fixtures ──────────────────────────────────────────

const mockUser = { id: 1, username: 'testuser', roles: [] };

// ───────────────────────────────────────────────────────────────────
// Test Suite 1: can() — basic guardrails
// ───────────────────────────────────────────────────────────────────

describe('can() — basic guardrails', () => {
  it('returns false for null user on any action', () => {
    expect(can(null, 'view_app', 'carbon')).toBe(false);
    expect(can(null, 'view_page', '/carbon/calculations')).toBe(false);
    expect(can(null, 'access_route', '/admin/users')).toBe(false);
    expect(can(null, 'manage', 'carbon')).toBe(false);
  });

  it('view_app with global admin perspective → true', () => {
    expect(can(mockUser, 'view_app', 'carbon', {
      perspectives: ['admin'],
    })).toBe(true);
  });

  it('view_app with correct capability → true', () => {
    expect(can(mockUser, 'view_app', 'carbon', {
      capabilities: ['carbon:view_console'],
    })).toBe(true);
  });

  it('view_app with wrong capability → false', () => {
    expect(can(mockUser, 'view_app', 'carbon', {
      capabilities: ['dq:view'],
    })).toBe(false);
  });

  it('access_route ungated path → true (falls through to legacy default-allow)', () => {
    // Unknown route not in any capability map → legacy returns true
    expect(can(mockUser, 'access_route', '/some-random-page', {})).toBe(true);
  });

  it('access_route with no user → false', () => {
    expect(can(null, 'access_route', '/carbon/calculations')).toBe(false);
  });
});

// ───────────────────────────────────────────────────────────────────
// Test Suite 2: can() — view_app for all 7 domains
// ───────────────────────────────────────────────────────────────────

describe('can() — view_app for all domains', () => {
  const domains = [
    { id: 'carbon',      cap: 'carbon:view_console',      wrongCap: 'catalog:view' },
    { id: 'catalog',     cap: 'catalog:view',              wrongCap: 'carbon:view_console' },
    { id: 'dq',          cap: 'dq:view',                   wrongCap: 'carbon:view_console' },
    { id: 'mdm',         cap: 'mdm:view',                  wrongCap: 'carbon:view_console' },
    { id: 'connections', cap: 'connections:view',          wrongCap: 'carbon:view_console' },
    { id: 'importexport',cap: 'importexport:view',         wrongCap: 'carbon:view_console' },
    { id: 'dataschema',  cap: 'dataschema:view',           wrongCap: 'carbon:view_console' },
  ];

  domains.forEach(({ id, cap }) => {
    it(`view_app '${id}' with correct capability → true`, () => {
      expect(can(mockUser, 'view_app', id, { capabilities: [cap] })).toBe(true);
    });
  });

  domains.forEach(({ id, wrongCap }) => {
    it(`view_app '${id}' with wrong capability → false`, () => {
      expect(can(mockUser, 'view_app', id, { capabilities: [wrongCap] })).toBe(false);
    });
  });
});

// ───────────────────────────────────────────────────────────────────
// Test Suite 3: can() — view_page
// ───────────────────────────────────────────────────────────────────

describe('can() — view_page', () => {
  const pageTests = [
    { path: '/carbon/calculations',        cap: 'carbon:view_calculations' },
    { path: '/carbon/verification',        cap: 'carbon:view_verification' },
    { path: '/carbon/analytics',           cap: 'carbon:view_analytics' },
    { path: '/carbon/admin/factors',       cap: 'carbon:manage_emission_factors' },
    { path: '/carbon/admin/rules',         cap: 'carbon:manage_calculation_rules' },
    { path: '/carbon/admin/gwp',           cap: 'carbon:manage_gwp' },
    { path: '/carbon/admin/targets',       cap: 'carbon:manage_sbti_targets' },
    { path: '/carbon/reporting/generate',  cap: 'carbon:generate_reports' },
    { path: '/carbon/reporting/periods',   cap: 'carbon:manage_reporting_periods' },
  ];

  pageTests.forEach(({ path, cap }) => {
    it(`${path} with ${cap} → true`, () => {
      expect(can(mockUser, 'view_page', path, { capabilities: [cap] })).toBe(true);
    });
  });

  pageTests.forEach(({ path }) => {
    it(`${path} with wrong capability → falls back to legacy (false without perspectives)`, () => {
      // wrong capability won't match → capability check returns null
      // legacy checks for carbon-admin perspective → not present → false
      expect(can(mockUser, 'view_page', path, { capabilities: ['dq:view'] })).toBe(false);
    });
  });
});

// ───────────────────────────────────────────────────────────────────
// Test Suite 4: can() — access_route
// ───────────────────────────────────────────────────────────────────

describe('can() — access_route', () => {
  it('/admin/users with platform:manage_users → true', () => {
    expect(can(mockUser, 'access_route', '/admin/users', {
      capabilities: ['platform:manage_users'],
    })).toBe(true);
  });

  it('/admin/groups with platform:manage_groups → true', () => {
    expect(can(mockUser, 'access_route', '/admin/groups', {
      capabilities: ['platform:manage_groups'],
    })).toBe(true);
  });

  it('/admin/users without capability → false (no perspectives fallback)', () => {
    expect(can(mockUser, 'access_route', '/admin/users', {})).toBe(false);
  });

  it('prefix match: /carbon/admin/factors covered by exact ROUTE_CAPABILITIES entry', () => {
    // ROUTE_CAPABILITIES has an exact entry for /carbon/admin/factors
    expect(can(mockUser, 'access_route', '/carbon/admin/factors', {
      capabilities: ['carbon:manage_emission_factors'],
    })).toBe(true);
  });

  it('unknown route with no cap requirement → true (default allow)', () => {
    // Route not in any capability map → capability check returns null
    // Legacy: doesn't match admin/catalog/carbon → returns true
    expect(can(mockUser, 'access_route', '/some/unknown/path', {})).toBe(true);
  });

  it('/carbon/calculations with correct capability → true', () => {
    expect(can(mockUser, 'access_route', '/carbon/calculations', {
      capabilities: ['carbon:view_calculations'],
    })).toBe(true);
  });

  it('/catalog/products with correct capability via expanded inheritance → true', () => {
    // catalog:manage_products implies catalog:view via CAPABILITY_INHERITANCE
    // access_route checks ROUTE_CAPABILITIES which has /catalog/products → CATALOG_MANAGE_PRODUCTS
    expect(can(mockUser, 'access_route', '/catalog/products', {
      capabilities: ['catalog:manage_products'],
    })).toBe(true);
  });

  it('/catalog/governance with catalog:manage_policies → true (inheritance)', () => {
    // catalog:manage_policies implies catalog:view_governance
    expect(can(mockUser, 'view_page', '/catalog/governance', {
      capabilities: ['catalog:manage_policies'],
    })).toBe(true);
  });
});

// ───────────────────────────────────────────────────────────────────
// Test Suite 5: can() — manage
// ───────────────────────────────────────────────────────────────────

describe('can() — manage', () => {
  const manageTests = [
    { app: 'carbon',      cap: 'carbon:manage_emission_factors' },
    { app: 'catalog',     cap: 'catalog:manage_products' },
    { app: 'dq',          cap: 'dq:manage_rules' },
    { app: 'mdm',         cap: 'mdm:manage' },
    { app: 'connections', cap: 'connections:manage' },
    { app: 'importexport',cap: 'importexport:manage' },
    { app: 'dataschema',  cap: 'dataschema:manage' },
  ];

  manageTests.forEach(({ app, cap }) => {
    it(`manage '${app}' with admin cap → true`, () => {
      expect(can(mockUser, 'manage', app, { capabilities: [cap] })).toBe(true);
    });
  });

  it('manage carbon with non-admin view cap → false', () => {
    // carbon:view_console does NOT imply carbon:manage_emission_factors
    expect(can(mockUser, 'manage', 'carbon', {
      capabilities: ['carbon:view_console'],
    })).toBe(false);
  });
});

// ───────────────────────────────────────────────────────────────────
// Test Suite 6: Convenience exports
// ───────────────────────────────────────────────────────────────────

describe('Convenience exports', () => {
  it('isGlobalAdmin with perspectives admin → true', () => {
    expect(isGlobalAdmin(mockUser, ['admin'])).toBe(true);
  });

  it('isGlobalAdmin with empty perspectives, backend flag true → true', () => {
    expect(isGlobalAdmin(mockUser, [], true)).toBe(true);
  });

  it('isGlobalAdmin with empty perspectives, backend flag false → false', () => {
    expect(isGlobalAdmin(mockUser, [], false)).toBe(false);
  });

  it('isGlobalAdmin with neither → false', () => {
    expect(isGlobalAdmin(mockUser, [])).toBe(false);
  });

  it('isDomainLead carbon with carbon-admin → true', () => {
    expect(isDomainLead('carbon', ['carbon-admin'])).toBe(true);
  });

  it('isDomainLead carbon with catalog-admin → false', () => {
    expect(isDomainLead('carbon', ['catalog-admin'])).toBe(false);
  });

  it('isCatalogAdmin with catalog-admin perspective → true', () => {
    expect(isCatalogAdmin(mockUser, {
      perspectives: ['catalog-admin'],
    })).toBe(true);
  });

  it('isCatalogAdmin without permissions → false', () => {
    expect(isCatalogAdmin(mockUser, {})).toBe(false);
  });

  it('hasAppAccess carbon with correct capability → true', () => {
    expect(hasAppAccess('carbon', mockUser, {
      capabilities: [{ key: 'carbon:view_console' }],
    })).toBe(true);
  });

  it('hasAppAccess dq with wrong capability → false', () => {
    expect(hasAppAccess('dq', mockUser, {
      capabilities: [{ key: 'carbon:view_console' }],
    })).toBe(false);
  });

  it('hasAppAccess with global admin → true', () => {
    expect(hasAppAccess('carbon', mockUser, {
      perspectives: ['admin'],
    })).toBe(true);
  });
});

// ───────────────────────────────────────────────────────────────────
// Test Suite 7: Capability expansion
// ───────────────────────────────────────────────────────────────────

describe('Capability expansion', () => {
  it('carbon:manage_emission_factors → implies carbon:view_console', () => {
    const expanded = expandCapabilities(['carbon:manage_emission_factors']);
    expect(hasCap(expanded, 'carbon:view_console')).toBe(true);
  });

  it('platform:admin → implies all platform caps', () => {
    const expanded = expandCapabilities(['platform:admin']);
    expect(hasCap(expanded, 'platform:manage_users')).toBe(true);
    expect(hasCap(expanded, 'platform:manage_groups')).toBe(true);
    expect(hasCap(expanded, 'platform:manage_org_units')).toBe(true);
    expect(hasCap(expanded, 'platform:manage_access')).toBe(true);
    expect(hasCap(expanded, 'platform:view_audit')).toBe(true);
    expect(hasCap(expanded, 'platform:manage_apps')).toBe(true);
  });

  it('carbon:enter_data → implies carbon:view_my_data and carbon:view_console', () => {
    const expanded = expandCapabilities(['carbon:enter_data']);
    expect(hasCap(expanded, 'carbon:view_my_data')).toBe(true);
    expect(hasCap(expanded, 'carbon:view_console')).toBe(true);
  });

  it('carbon:trigger_calculations → implies carbon:view_calculations and carbon:view_console', () => {
    const expanded = expandCapabilities(['carbon:trigger_calculations']);
    expect(hasCap(expanded, 'carbon:view_calculations')).toBe(true);
    expect(hasCap(expanded, 'carbon:view_console')).toBe(true);
  });

  it('catalog:manage_products → implies catalog:view', () => {
    const expanded = expandCapabilities(['catalog:manage_products']);
    expect(hasCap(expanded, 'catalog:view')).toBe(true);
  });

  it('unknown capability → no expansion (just itself)', () => {
    const expanded = expandCapabilities(['unknown:cap']);
    expect(hasCap(expanded, 'unknown:cap')).toBe(true);
    expect(expanded.size).toBe(1);
  });

  it('transitive closure: carbon:manage_reporting_periods → view_reporting_periods → view_console', () => {
    // carbon:manage_reporting_periods → carbon:view_reporting_periods AND carbon:view_console
    // carbon:view_reporting_periods has no further implications
    const expanded = expandCapabilities(['carbon:manage_reporting_periods']);
    expect(hasCap(expanded, 'carbon:view_reporting_periods')).toBe(true);
    expect(hasCap(expanded, 'carbon:view_console')).toBe(true);
  });

  it('carbon:verify_data → implies carbon:view_verification and carbon:view_console', () => {
    const expanded = expandCapabilities(['carbon:verify_data']);
    expect(hasCap(expanded, 'carbon:view_verification')).toBe(true);
    expect(hasCap(expanded, 'carbon:view_console')).toBe(true);
  });

  it('catalog:manage_policies → implies catalog:view and catalog:view_governance', () => {
    const expanded = expandCapabilities(['catalog:manage_policies']);
    expect(hasCap(expanded, 'catalog:view')).toBe(true);
    expect(hasCap(expanded, 'catalog:view_governance')).toBe(true);
  });
});

// ───────────────────────────────────────────────────────────────────
// Test Suite 8: Legacy fallback
// ───────────────────────────────────────────────────────────────────

describe('Legacy fallback (perspectives)', () => {
  it('capabilities null → perspective check works for view_app', () => {
    expect(can(mockUser, 'view_app', 'carbon', {
      capabilities: null,
      perspectives: ['carbon-admin'],
    })).toBe(true);
  });

  it('capabilities [] → perspective check works for view_app', () => {
    expect(can(mockUser, 'view_app', 'carbon', {
      capabilities: [],
      perspectives: ['carbon-admin'],
    })).toBe(true);
  });

  it('perspective carbon-admin → can view_app carbon', () => {
    expect(can(mockUser, 'view_app', 'carbon', {
      perspectives: ['carbon-admin'],
    })).toBe(true);
  });

  it('perspective admin → can access_route /admin/users', () => {
    expect(can(mockUser, 'access_route', '/admin/users', {
      perspectives: ['admin'],
    })).toBe(true);
  });

  it('perspective carbon-admin → can access_route /carbon/calculations', () => {
    expect(can(mockUser, 'access_route', '/carbon/calculations', {
      perspectives: ['carbon-admin'],
    })).toBe(true);
  });

  it('perspective carbon-admin → can manage carbon', () => {
    expect(can(mockUser, 'manage', 'carbon', {
      perspectives: ['carbon-admin'],
    })).toBe(true);
  });

  it('no matching perspective → cannot view_app', () => {
    expect(can(mockUser, 'view_app', 'carbon', {
      perspectives: ['catalog-admin'],
    })).toBe(false);
  });
});

// ───────────────────────────────────────────────────────────────────
// Test Suite 9: Edge cases
// ───────────────────────────────────────────────────────────────────

describe('Edge cases', () => {
  it('empty capabilities array → falls through to legacy', () => {
    // With no perspectives, legacy returns false for view_app
    expect(can(mockUser, 'view_app', 'carbon', { capabilities: [] })).toBe(false);
  });

  it('capability object with {key} shape → parsed correctly', () => {
    expect(can(mockUser, 'view_app', 'carbon', {
      capabilities: [{ key: 'carbon:view_console' }],
    })).toBe(true);
  });

  it('capability as plain string in array → works', () => {
    expect(can(mockUser, 'view_app', 'carbon', {
      capabilities: ['carbon:view_console'],
    })).toBe(true);
  });

  it('capability object with {capability} shape → parsed correctly', () => {
    expect(can(mockUser, 'view_app', 'carbon', {
      capabilities: [{ capability: 'carbon:view_console' }],
    })).toBe(true);
  });

  it('unknown app ID returns false for view_app', () => {
    // No APP_VIEW_CAP entry for 'nonexistent'
    expect(can(mockUser, 'view_app', 'nonexistent', {
      capabilities: ['carbon:view_console'],
    })).toBe(false);
  });

  it('unknown app ID returns false for manage', () => {
    // No APP_ADMIN_CAP entry, no APP_VIEW_CAP entry → capability check returns null
    // legacy: perspectives.includes('nonexistent-admin') → false
    expect(can(mockUser, 'manage', 'nonexistent', {
      capabilities: ['platform:admin'],
    })).toBe(false);
  });

  it('can() with missing context fields does not crash', () => {
    // No ctx at all
    expect(() => can(mockUser, 'view_app', 'carbon')).not.toThrow();
    // Partial ctx — missing perspectives defaults to []
    expect(() => can(mockUser, 'access_route', '/carbon/calculations', {})).not.toThrow();
    // null perspectives
    expect(() => can(mockUser, 'view_app', 'carbon', { perspectives: null })).not.toThrow();
  });

  it('global admin bypass works regardless of capabilities', () => {
    // Even with capabilities that don't grant access, global admin wins
    expect(can(mockUser, 'view_app', 'carbon', {
      perspectives: ['admin'],
      capabilities: ['dq:view'], // wrong capability for carbon
    })).toBe(true);
  });

  it('hasCap with wildcard * → true for any capability', () => {
    expect(hasCap(['*'], 'carbon:view_console')).toBe(true);
    expect(hasCap(new Set(['*']), 'some:random:cap')).toBe(true);
  });

  it('isGlobalAdmin with user.roles containing admin → true', () => {
    const adminUser = { id: 2, username: 'admin', roles: [{ role: 'admin' }] };
    expect(isGlobalAdmin(adminUser, [])).toBe(true);
  });

  it('initCapabilities returns expanded set from API response', () => {
    const result = initCapabilities([
      { key: 'carbon:manage_emission_factors' },
    ]);
    expect(result.caps.has('carbon:manage_emission_factors')).toBe(true);
    expect(result.expanded.has('carbon:view_console')).toBe(true);
    expect(result.expanded.has('carbon:manage_emission_factors')).toBe(true);
  });

  it('initCapabilities with empty array → empty sets', () => {
    const result = initCapabilities([]);
    expect(result.caps.size).toBe(0);
    expect(result.expanded.size).toBe(0);
  });

  it('initCapabilities with null/undefined → empty sets', () => {
    const result = initCapabilities(null);
    expect(result.caps.size).toBe(0);
    expect(result.expanded.size).toBe(0);
  });

  it('getCapableApps returns correct app IDs', () => {
    const expanded = expandCapabilities([
      'carbon:manage_emission_factors', // → implies carbon:view_console
      'catalog:view',
      'dq:manage_rules',              // → implies dq:view
      'mdm:manage',                   // → implies mdm:view
    ]);
    const apps = getCapableApps(expanded);
    expect(apps).toContain('carbon');
    expect(apps).toContain('catalog');
    expect(apps).toContain('dq');
    expect(apps).toContain('mdm');
    // connections, importexport, dataschema not included
    expect(apps).not.toContain('connections');
    expect(apps).not.toContain('importexport');
    expect(apps).not.toContain('dataschema');
  });

  it('can() view_app with module-based access (legacy)', () => {
    expect(can(mockUser, 'view_app', 'carbon', {
      modules: [{ app_id: 'carbon', scope: 'carbon' }],
    })).toBe(true);
  });
});

// ═══════════════════════════════════════════════════════════════════
// Test Suite 10: can() — view_menu (CBAC sidebar gating)
// ═══════════════════════════════════════════════════════════════════

describe('can() — view_menu (sidebar capability-gating)', () => {
  it('Overview with carbon:view_console → true', () => {
    expect(can(mockUser, 'view_menu', 'Overview', {
      capabilities: ['carbon:view_console'],
    })).toBe(true);
  });

  it('Emission Factors with carbon:manage_emission_factors → true', () => {
    expect(can(mockUser, 'view_menu', 'Emission Factors', {
      capabilities: ['carbon:manage_emission_factors'],
    })).toBe(true);
  });

  it('Emission Factors with only carbon:view_console → false', () => {
    expect(can(mockUser, 'view_menu', 'Emission Factors', {
      capabilities: ['carbon:view_console'],
    })).toBe(false);
  });

  it('Calculation Rules with carbon:manage_calculation_rules → true', () => {
    expect(can(mockUser, 'view_menu', 'Calculation Rules', {
      capabilities: ['carbon:manage_calculation_rules'],
    })).toBe(true);
  });

  it('GWP Reference with carbon:manage_gwp → true', () => {
    expect(can(mockUser, 'view_menu', 'GWP Reference', {
      capabilities: ['carbon:manage_gwp'],
    })).toBe(true);
  });

  it('SBTi Targets with carbon:manage_sbti_targets → true', () => {
    expect(can(mockUser, 'view_menu', 'SBTi Targets', {
      capabilities: ['carbon:manage_sbti_targets'],
    })).toBe(true);
  });

  it('Reporting Periods with only carbon:view_reporting_periods → false (admin-only)', () => {
    expect(can(mockUser, 'view_menu', 'Reporting Periods', {
      capabilities: ['carbon:view_reporting_periods'],
    })).toBe(false);
  });

  it('Reporting Periods via manage inheritance → true', () => {
    // carbon:manage_reporting_periods implies carbon:view_reporting_periods
    expect(can(mockUser, 'view_menu', 'Reporting Periods', {
      capabilities: ['carbon:manage_reporting_periods'],
    })).toBe(true);
  });

  it('Generate Report with carbon:generate_reports → true', () => {
    expect(can(mockUser, 'view_menu', 'Generate Report', {
      capabilities: ['carbon:generate_reports'],
    })).toBe(true);
  });

  it('Saved Reports with carbon:generate_reports → true', () => {
    expect(can(mockUser, 'view_menu', 'Saved Reports', {
      capabilities: ['carbon:generate_reports'],
    })).toBe(true);
  });

  it('Verification with carbon:verify_data → true (inheritance)', () => {
    // carbon:verify_data implies carbon:view_verification
    expect(can(mockUser, 'view_menu', 'Verification', {
      capabilities: ['carbon:verify_data'],
    })).toBe(true);
  });

  it('Data Entry with carbon:enter_data → true (inheritance)', () => {
    // carbon:enter_data implies carbon:view_my_data
    expect(can(mockUser, 'view_menu', 'Data Entry', {
      capabilities: ['carbon:enter_data'],
    })).toBe(true);
  });

  it('Analytics & Trends with carbon:view_analytics → true', () => {
    expect(can(mockUser, 'view_menu', 'Analytics & Trends', {
      capabilities: ['carbon:view_analytics'],
    })).toBe(true);
  });

  it('Analytics & Trends inheritance: carbon:view_analytics implies view_console', () => {
    // carbon:view_analytics → carbon:view_console (not tested by view_menu itself,
    // but Overview check confirms inherited view_console works)
    expect(can(mockUser, 'view_menu', 'Overview', {
      capabilities: ['carbon:view_analytics'],
    })).toBe(true);
  });

  it('Emissions Dashboard with carbon:view_dashboard → true', () => {
    expect(can(mockUser, 'view_menu', 'Emissions Dashboard', {
      capabilities: ['carbon:view_dashboard'],
    })).toBe(true);
  });

  it('Unknown menu label → capability check returns null, legacy default true', () => {
    expect(can(mockUser, 'view_menu', 'Some Unknown Menu Item', {
      capabilities: [],
    })).toBe(true);
  });

  it('view_menu with no capabilities → legacy fallback true', () => {
    // No capabilities at all → capability check returns null → legacy returns true for view_menu
    expect(can(mockUser, 'view_menu', 'Emission Factors', {})).toBe(true);
  });

  it('view_menu with global admin → true regardless of capabilities', () => {
    expect(can(mockUser, 'view_menu', 'Emission Factors', {
      perspectives: ['admin'],
      capabilities: [], // no carbon caps
    })).toBe(true);
  });

  it('Calculations with carbon:view_calculations → true', () => {
    expect(can(mockUser, 'view_menu', 'Calculations', {
      capabilities: ['carbon:view_calculations'],
    })).toBe(true);
  });
});

// ═══════════════════════════════════════════════════════════════════
// Test Suite 11: can() — AdminRoute wiring patterns
// ═══════════════════════════════════════════════════════════════════

describe('can() — AdminRoute wiring patterns', () => {
  const adminUser = { id: 1, username: 'admin', roles: [{ role: 'admin' }] };
  const carbonLeadUser = { id: 2, username: 'carbon_lead', roles: [] };
  const catalogLeadUser = { id: 3, username: 'catalog_lead', roles: [] };

  it('platform admin routes: /admin/users with platform:manage_users → true', () => {
    expect(can(adminUser, 'access_route', '/admin/users', {
      capabilities: ['platform:manage_users'],
    })).toBe(true);
  });

  it('platform admin routes: /admin/users with perspectives admin → true', () => {
    expect(can(adminUser, 'access_route', '/admin/users', {
      perspectives: ['admin'],
    })).toBe(true);
  });

  it('platform admin routes: /admin/users with platform:admin → all admin routes accessible', () => {
    expect(can(adminUser, 'access_route', '/admin/groups', {
      capabilities: ['platform:admin'],
    })).toBe(true);
    expect(can(adminUser, 'access_route', '/admin/org-units', {
      capabilities: ['platform:admin'],
    })).toBe(true);
    expect(can(adminUser, 'access_route', '/admin/access', {
      capabilities: ['platform:admin'],
    })).toBe(true);
    expect(can(adminUser, 'access_route', '/admin/audit', {
      capabilities: ['platform:admin'],
    })).toBe(true);
  });

  it('domain admin: manage carbon with carbon:manage_emission_factors → true', () => {
    expect(can(carbonLeadUser, 'manage', 'carbon', {
      capabilities: ['carbon:manage_emission_factors'],
    })).toBe(true);
  });

  it('domain admin: manage carbon with carbon-admin perspective → true', () => {
    expect(can(carbonLeadUser, 'manage', 'carbon', {
      perspectives: ['carbon-admin'],
    })).toBe(true);
  });

  it('domain admin: manage catalog with catalog:manage_products → true', () => {
    expect(can(catalogLeadUser, 'manage', 'catalog', {
      capabilities: ['catalog:manage_products'],
    })).toBe(true);
  });

  it('AdminRoute combo: manage + access_route for carbon admin pages', () => {
    // AdminRoute checks: can(user, 'manage', 'carbon') || can(user, 'access_route', path)
    // Domain lead manages carbon AND can access /carbon/admin/factors
    expect(can(carbonLeadUser, 'manage', 'carbon', {
      capabilities: ['carbon:manage_emission_factors'],
    })).toBe(true);
    expect(can(carbonLeadUser, 'access_route', '/carbon/admin/factors', {
      capabilities: ['carbon:manage_emission_factors'],
    })).toBe(true);
  });

  it('AdminRoute: non-admin user fails both manage and access_route', () => {
    expect(can(mockUser, 'manage', 'carbon', {
      capabilities: ['carbon:view_console'],
    })).toBe(false);
    expect(can(mockUser, 'access_route', '/carbon/admin/factors', {
      capabilities: ['carbon:view_console'],
    })).toBe(false);
  });

  it('AdminRoute with isGlobalAdminFlag: backend-authoritative bypass → true', () => {
    expect(can(mockUser, 'access_route', '/admin/users', {
      isGlobalAdminFlag: true,
      perspectives: [],
      capabilities: [],
    })).toBe(true);
  });

  it('AdminRoute with isGlobalAdminFlag false → no bypass, falls through', () => {
    expect(can(mockUser, 'access_route', '/admin/users', {
      isGlobalAdminFlag: false,
      perspectives: [],
      capabilities: [],
    })).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════════
// Test Suite 12: canAccessRoute wrapper
// ═══════════════════════════════════════════════════════════════════

describe('canAccessRoute wrapper', () => {
  it('delegates to can() with access_route for a known route', async () => {
    const { canAccessRoute } = await import('../authz');
    expect(canAccessRoute('/carbon/calculations', mockUser, {
      capabilities: ['carbon:view_calculations'],
    })).toBe(true);
  });

  it('denies a known admin route without capabilities', async () => {
    const { canAccessRoute } = await import('../authz');
    expect(canAccessRoute('/admin/users', mockUser, {
      capabilities: [],
      perspectives: [],
    })).toBe(false);
  });

  it('allows unknown routes (default-allow legacy)', async () => {
    const { canAccessRoute } = await import('../authz');
    // Unknown routes like /settings/profile are default-allow
    // (they are not gated by AdminRoute in production — only admin/* paths go through it)
    expect(canAccessRoute('/settings/profile', mockUser, {
      capabilities: [],
      perspectives: [],
    })).toBe(true);
  });

  it('denies with null user', async () => {
    const { canAccessRoute } = await import('../authz');
    expect(canAccessRoute('/admin/users', null, {})).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════════
// Test Suite 13: checkLegacy default behavior
// ═══════════════════════════════════════════════════════════════════

describe('checkLegacy — default allow for ungated routes', () => {
  it('home path (/) is accessible to any authenticated user', () => {
    expect(can(mockUser, 'access_route', '/', {
      capabilities: [],
      perspectives: [],
    })).toBe(true);
  });

  it('/settings/profile is accessible (ungated route)', () => {
    expect(can(mockUser, 'access_route', '/settings/profile', {
      capabilities: [],
      perspectives: [],
    })).toBe(true);
  });

  it('/help is accessible (ungated route)', () => {
    expect(can(mockUser, 'access_route', '/help', {
      capabilities: [],
      perspectives: [],
    })).toBe(true);
  });
});
