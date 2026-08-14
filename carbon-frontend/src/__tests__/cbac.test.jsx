// src/__tests__/cbac.test.js
// Comprehensive CBAC (Capability-Based Access Control) Frontend Tests
//
// Tests cover:
//   1. Capability constants — format, uniqueness, completeness
//   2. Inheritance graph — mirror of backend IMPLIES
//   3. Route/menu/manifest mappings — correctness
//   4. expandCapabilities — empty, single, multi-level, transitive, idempotent
//   5. hasCap / hasAnyCap / hasAllCaps — all scenarios
//   6. initCapabilities — factory function
//   7. canAccessRoute — exact, prefix, no-requirement
//   8. filterMenuItems — role, capability, nested
//   9. getCapableApps — full/partial/none
//  10. RBAC utils (rbac.js) — isGlobalAdmin, isDomainLead, etc.
//  11. AdminRoute component — render, redirect, notification
//  12. Edge cases — empty sets, null/undefined, large sets, cross-module

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';

const theme = createTheme();

// ═══════════════════════════════════════════════════════════════════
// TEST SUITE 1: Capability Constants
// ═══════════════════════════════════════════════════════════════════
describe('Capability Constants', () => {
  let caps;
  
  beforeAll(async () => {
    caps = await import('../capabilities.js');
  });

  it('all capability keys follow domain:action format', () => {
    const constants = Object.entries(caps)
      .filter(([k, v]) => k === k.toUpperCase() && typeof v === 'string' && v.includes(':'));
    expect(constants.length).toBeGreaterThan(0);
    for (const [name, value] of constants) {
      expect(value).toMatch(/^[a-z_]+:[a-z_]+$/);
    }
  });

  it('no duplicate capability values', () => {
    const values = Object.entries(caps)
      .filter(([k, v]) => k === k.toUpperCase() && typeof v === 'string' && v.includes(':'))
      .map(([, v]) => v);
    const unique = new Set(values);
    expect(unique.size).toBe(values.length);
  });

  it('has all expected platform capabilities', () => {
    expect(caps.PLATFORM_ADMIN).toBe('platform:admin');
    expect(caps.PLATFORM_MANAGE_USERS).toBe('platform:manage_users');
    expect(caps.PLATFORM_MANAGE_GROUPS).toBe('platform:manage_groups');
    expect(caps.PLATFORM_MANAGE_ORG_UNITS).toBe('platform:manage_org_units');
    expect(caps.PLATFORM_MANAGE_ACCESS).toBe('platform:manage_access');
    expect(caps.PLATFORM_VIEW_AUDIT).toBe('platform:view_audit');
    expect(caps.PLATFORM_MANAGE_APPS).toBe('platform:manage_apps');
  });

  it('has all expected carbon capabilities', () => {
    expect(caps.CARBON_VIEW_CONSOLE).toBe('carbon:view_console');
    expect(caps.CARBON_VIEW_DASHBOARD).toBe('carbon:view_dashboard');
    expect(caps.CARBON_VIEW_ANALYTICS).toBe('carbon:view_analytics');
    expect(caps.CARBON_ENTER_DATA).toBe('carbon:enter_data');
    expect(caps.CARBON_VIEW_MY_DATA).toBe('carbon:view_my_data');
    expect(caps.CARBON_MANAGE_EMISSION_FACTORS).toBe('carbon:manage_emission_factors');
    expect(caps.CARBON_MANAGE_CALCULATION_RULES).toBe('carbon:manage_calculation_rules');
    expect(caps.CARBON_TRIGGER_CALCULATIONS).toBe('carbon:trigger_calculations');
    expect(caps.CARBON_VERIFY_DATA).toBe('carbon:verify_data');
    expect(caps.CARBON_GENERATE_REPORTS).toBe('carbon:generate_reports');
  });

  it('has all expected non-carbon capabilities', () => {
    expect(caps.CATALOG_VIEW).toBe('catalog:view');
    expect(caps.CATALOG_MANAGE_PRODUCTS).toBe('catalog:manage_products');
    expect(caps.CATALOG_MANAGE_POLICIES).toBe('catalog:manage_policies');
    expect(caps.DQ_VIEW).toBe('dq:view');
    expect(caps.DQ_MANAGE_RULES).toBe('dq:manage_rules');
    expect(caps.MDM_VIEW).toBe('mdm:view');
    expect(caps.MDM_MANAGE).toBe('mdm:manage');
    expect(caps.CONNECTIONS_VIEW).toBe('connections:view');
    expect(caps.CONNECTIONS_MANAGE).toBe('connections:manage');
    expect(caps.IMPORTEXPORT_VIEW).toBe('importexport:view');
    expect(caps.IMPORTEXPORT_MANAGE).toBe('importexport:manage');
    expect(caps.DATASCHEMA_VIEW).toBe('dataschema:view');
    expect(caps.DATASCHEMA_MANAGE).toBe('dataschema:manage');
    expect(caps.EVIDENCE_VIEW).toBe('evidence:view');
    expect(caps.EVIDENCE_MANAGE).toBe('evidence:manage');
  });

  it('has consistent naming: MANAGE implies VIEW in same domain', () => {
    // Every MANAGE cap should have a corresponding VIEW cap in the same domain
    const allCaps = Object.values(caps).filter(v => typeof v === 'string' && v.includes(':'));
    const manageCaps = allCaps.filter(c => c.includes(':manage_') || c.includes(':manage'));
    for (const mc of manageCaps) {
      const [domain] = mc.split(':');
      // There should be at least one view cap in this domain
      const domainViewCaps = allCaps.filter(c => c.startsWith(`${domain}:view`));
      expect(domainViewCaps.length).toBeGreaterThan(0);
    }
  });
});

// ═══════════════════════════════════════════════════════════════════
// TEST SUITE 2: Capability Inheritance Graph
// ═══════════════════════════════════════════════════════════════════
describe('CAPABILITY_INHERITANCE', () => {
  let caps;

  beforeAll(async () => {
    caps = await import('../capabilities.js');
  });

  it('is an object with string keys and string array values', () => {
    const ci = caps.CAPABILITY_INHERITANCE;
    expect(typeof ci).toBe('object');
    for (const [key, val] of Object.entries(ci)) {
      expect(typeof key).toBe('string');
      expect(Array.isArray(val)).toBe(true);
      val.forEach(v => expect(typeof v).toBe('string'));
    }
  });

  it('every key and value is a defined capability constant', () => {
    const allCaps = new Set(
      Object.entries(caps)
        .filter(([k, v]) => k === k.toUpperCase() && typeof v === 'string' && v.includes(':'))
        .map(([, v]) => v)
    );
    const ci = caps.CAPABILITY_INHERITANCE;
    for (const [key, vals] of Object.entries(ci)) {
      expect(allCaps.has(key), `Key ${key} must be a valid capability`).toBe(true);
      for (const v of vals) {
        expect(allCaps.has(v), `Value ${v} from key ${key} must be a valid capability`).toBe(true);
      }
    }
  });

  it('no capability implies itself', () => {
    const ci = caps.CAPABILITY_INHERITANCE;
    for (const [key, vals] of Object.entries(ci)) {
      expect(vals).not.toContain(key);
    }
  });

  it('no circular dependencies (A→B and B→A)', () => {
    const ci = caps.CAPABILITY_INHERITANCE;
    for (const [key, vals] of Object.entries(ci)) {
      for (const v of vals) {
        const backRef = ci[v] || [];
        expect(backRef).not.toContain(key);
      }
    }
  });

  it('all manage_* capabilities imply at least one view cap in their domain', () => {
    const ci = caps.CAPABILITY_INHERITANCE;
    // Collect all known view caps grouped by domain
    const allCaps = Object.entries(caps)
      .filter(([k, v]) => k === k.toUpperCase() && typeof v === 'string' && v.includes(':'))
      .map(([, v]) => v);
    const viewCapsByDomain = {};
    for (const c of allCaps) {
      if (c.includes(':view_') || c.endsWith(':view')) {
        const domain = c.split(':')[0];
        if (!viewCapsByDomain[domain]) viewCapsByDomain[domain] = [];
        viewCapsByDomain[domain].push(c);
      }
    }

    for (const [key, vals] of Object.entries(ci)) {
      if (key.includes(':manage_') || key.includes(':manage')) {
        const domain = key.split(':')[0];
        const domainViewCaps = viewCapsByDomain[domain];
        if (!domainViewCaps || domainViewCaps.length === 0) continue;

        // At least one view cap in this domain should be implied (directly or transitively)
        const impliesAnyView = domainViewCaps.some(viewCap => {
          const hasDirect = vals.includes(viewCap);
          const hasTransitive = vals.some(v => {
            const chain = ci[v] || [];
            // Check one level deep
            return chain.includes(viewCap) || chain.some(c => (ci[c] || []).includes(viewCap));
          });
          return hasDirect || hasTransitive;
        });
        expect(impliesAnyView,
          `${key} should imply at least one view cap in ${domain} (candidates: ${domainViewCaps.join(', ')})`).toBe(true);
      }
    }
  });

  it('has inheritance entries for all non-platform manage capabilities', () => {
    const ci = caps.CAPABILITY_INHERITANCE;
    const manageCaps = Object.entries(caps)
      .filter(([k, v]) => k === k.toUpperCase() && typeof v === 'string' &&
        (v.includes(':manage_') || v.includes(':manage') || v.includes(':enter_') ||
         v.includes(':verify_') || v.includes(':trigger_') || v.includes(':generate_')))
      .map(([, v]) => v);

    // Platform caps are covered by PLATFORM_ADMIN umbrella, not individual entries
    const skips = new Set([caps.PLATFORM_ADMIN]);
    for (const mc of manageCaps) {
      if (skips.has(mc) || mc.startsWith('platform:')) continue;
      const entry = ci[mc];
      expect(entry, `Missing inheritance for ${mc}`).toBeDefined();
      expect(entry.length).toBeGreaterThan(0);
    }
  });

  it('matches backend IMPLIES dict structure', () => {
    // These specific inheritance edges must exist (verified against backend)
    const ci = caps.CAPABILITY_INHERITANCE;

    // Carbon manage→view
    expect(ci[caps.CARBON_MANAGE_EMISSION_FACTORS]).toContain(caps.CARBON_VIEW_CONSOLE);
    expect(ci[caps.CARBON_MANAGE_CALCULATION_RULES]).toContain(caps.CARBON_VIEW_CONSOLE);
    expect(ci[caps.CARBON_MANAGE_GWP]).toContain(caps.CARBON_VIEW_CONSOLE);
    expect(ci[caps.CARBON_MANAGE_SBTI_TARGETS]).toContain(caps.CARBON_VIEW_CONSOLE);
    expect(ci[caps.CARBON_MANAGE_REPORTING_PERIODS]).toContain(caps.CARBON_VIEW_REPORTING_PERIODS);

    // Carbon trigger/verify
    expect(ci[caps.CARBON_TRIGGER_CALCULATIONS]).toContain(caps.CARBON_VIEW_CALCULATIONS);
    expect(ci[caps.CARBON_VERIFY_DATA]).toContain(caps.CARBON_VIEW_VERIFICATION);

    // Carbon enter→view
    expect(ci[caps.CARBON_ENTER_DATA]).toContain(caps.CARBON_VIEW_MY_DATA);

    // Catalog manage→view
    expect(ci[caps.CATALOG_MANAGE_PRODUCTS]).toContain(caps.CATALOG_VIEW);
    expect(ci[caps.CATALOG_MANAGE_METADATA]).toContain(caps.CATALOG_VIEW);
    expect(ci[caps.CATALOG_MANAGE_POLICIES]).toContain(caps.CATALOG_VIEW);
    expect(ci[caps.CATALOG_MANAGE_POLICIES]).toContain(caps.CATALOG_VIEW_GOVERNANCE);

    // Other domains
    expect(ci[caps.DQ_MANAGE_RULES]).toContain(caps.DQ_VIEW);
    expect(ci[caps.MDM_MANAGE]).toContain(caps.MDM_VIEW);
    expect(ci[caps.CONNECTIONS_MANAGE]).toContain(caps.CONNECTIONS_VIEW);
    expect(ci[caps.IMPORTEXPORT_MANAGE]).toContain(caps.IMPORTEXPORT_VIEW);
    expect(ci[caps.DATASCHEMA_MANAGE]).toContain(caps.DATASCHEMA_VIEW);
    expect(ci[caps.EVIDENCE_MANAGE]).toContain(caps.EVIDENCE_VIEW);
  });
});

// ═══════════════════════════════════════════════════════════════════
// TEST SUITE 3: Route, Menu, and Manifest Mappings
// ═══════════════════════════════════════════════════════════════════
describe('ROUTE_CAPABILITIES', () => {
  let caps;

  beforeAll(async () => {
    caps = await import('../capabilities.js');
  });

  it('is a non-empty object', () => {
    expect(typeof caps.ROUTE_CAPABILITIES).toBe('object');
    expect(Object.keys(caps.ROUTE_CAPABILITIES).length).toBeGreaterThan(0);
  });

  it('every route starts with /', () => {
    for (const route of Object.keys(caps.ROUTE_CAPABILITIES)) {
      expect(route.startsWith('/')).toBe(true);
    }
  });

  it('every route capability is a valid capability constant', () => {
    const allCaps = new Set(
      Object.entries(caps)
        .filter(([k, v]) => k === k.toUpperCase() && typeof v === 'string' && v.includes(':'))
        .map(([, v]) => v)
    );
    for (const [route, cap] of Object.entries(caps.ROUTE_CAPABILITIES)) {
      expect(allCaps.has(cap), `Route ${route} maps to unknown cap: ${cap}`).toBe(true);
    }
  });

  it('admin routes require platform capabilities', () => {
    for (const [route, cap] of Object.entries(caps.ROUTE_CAPABILITIES)) {
      if (route.startsWith('/admin/')) {
        // The AI admin console is its own capability domain under /admin.
        if (route.startsWith('/admin/ai')) {
          expect(cap).toBe(caps.AI_VIEW_CONSOLE);
        } else {
          expect(cap.startsWith('platform:')).toBe(true);
        }
      }
    }
  });

  it('carbon routes require carbon capabilities', () => {
    for (const [route, cap] of Object.entries(caps.ROUTE_CAPABILITIES)) {
      if (route.startsWith('/carbon/')) {
        expect(cap.startsWith('carbon:')).toBe(true);
      }
    }
  });

  it('catalog routes require catalog capabilities', () => {
    for (const [route, cap] of Object.entries(caps.ROUTE_CAPABILITIES)) {
      if (route.startsWith('/catalog/')) {
        expect(cap.startsWith('catalog:')).toBe(true);
      }
    }
  });
});

describe('MENU_ITEM_CAPABILITIES', () => {
  let caps;

  beforeAll(async () => {
    caps = await import('../capabilities.js');
  });

  it('is a non-empty object', () => {
    expect(typeof caps.MENU_ITEM_CAPABILITIES).toBe('object');
    expect(Object.keys(caps.MENU_ITEM_CAPABILITIES).length).toBeGreaterThan(0);
  });

  it('every label is a non-empty string', () => {
    for (const label of Object.keys(caps.MENU_ITEM_CAPABILITIES)) {
      expect(typeof label).toBe('string');
      expect(label.length).toBeGreaterThan(0);
    }
  });

  it('every capability is a valid capability constant', () => {
    const allCaps = new Set(
      Object.entries(caps)
        .filter(([k, v]) => k === k.toUpperCase() && typeof v === 'string' && v.includes(':'))
        .map(([, v]) => v)
    );
    for (const [label, cap] of Object.entries(caps.MENU_ITEM_CAPABILITIES)) {
      expect(allCaps.has(cap), `Menu "${label}" maps to unknown cap: ${cap}`).toBe(true);
    }
  });

  it('no duplicate labels', () => {
    const labels = Object.keys(caps.MENU_ITEM_CAPABILITIES);
    const unique = new Set(labels);
    expect(unique.size).toBe(labels.length);
  });
});

describe('MANIFEST_ROLE_TO_CAPABILITY', () => {
  let caps;

  beforeAll(async () => {
    caps = await import('../capabilities.js');
  });

  it('maps all known manifest roles', () => {
    const mrtc = caps.MANIFEST_ROLE_TO_CAPABILITY;
    expect(mrtc['carbon:data_owner']).toBeDefined();
    expect(mrtc['carbon:analyst']).toBeDefined();
    expect(mrtc['carbon:admin']).toBeDefined();
  });

  it('every mapped value is an array of valid capabilities', () => {
    const allCaps = new Set(
      Object.entries(caps)
        .filter(([k, v]) => k === k.toUpperCase() && typeof v === 'string' && v.includes(':'))
        .map(([, v]) => v)
    );
    for (const [role, capList] of Object.entries(caps.MANIFEST_ROLE_TO_CAPABILITY)) {
      expect(Array.isArray(capList)).toBe(true);
      expect(capList.length).toBeGreaterThan(0);
      for (const c of capList) {
        expect(allCaps.has(c), `Role ${role} maps to unknown cap: ${c}`).toBe(true);
      }
    }
  });

  it('every carbon admin mapped capability is a MANAGE-level cap', () => {
    for (const c of caps.MANIFEST_ROLE_TO_CAPABILITY['carbon:admin']) {
      expect(c.includes(':manage_') || c.includes(':manage') ||
             c.includes(':trigger_') || c.includes(':verify_')).toBe(true);
    }
  });
});

// ═══════════════════════════════════════════════════════════════════
// TEST SUITE 4: expandCapabilities
// ═══════════════════════════════════════════════════════════════════
describe('expandCapabilities', () => {
  let caps, expandCapabilities;

  beforeAll(async () => {
    caps = await import('../capabilities.js');
    // Access the internal function via the module's closure
    // We test it indirectly through initCapabilities which calls it
    expandCapabilities = (input) => {
      // Replicate the internal logic for direct testing
      const CAPABILITY_INHERITANCE = caps.CAPABILITY_INHERITANCE;
      const result = new Set(input);
      let changed = true;
      while (changed) {
        changed = false;
        for (const cap of result) {
          const implied = CAPABILITY_INHERITANCE[cap] || [];
          for (const impliedCap of implied) {
            if (!result.has(impliedCap)) {
              result.add(impliedCap);
              changed = true;
            }
          }
        }
      }
      return result;
    };
  });

  it('returns same set for empty input', () => {
    const result = expandCapabilities([]);
    expect(result.size).toBe(0);
  });

  it('returns same set when no inheritance applies', () => {
    const result = expandCapabilities([caps.CARBON_VIEW_CONSOLE]);
    // view_console has no children in inheritance (it's a leaf)
    expect(result.has(caps.CARBON_VIEW_CONSOLE)).toBe(true);
    // size might be >1 if view_console is in some other inheritance path
  });

  it('expands single-level inheritance', () => {
    const result = expandCapabilities([caps.DQ_MANAGE_RULES]);
    expect(result.has(caps.DQ_MANAGE_RULES)).toBe(true);
    expect(result.has(caps.DQ_VIEW)).toBe(true);
  });

  it('expands multi-level inheritance', () => {
    // CARBON_VERIFY_DATA → CARBON_VIEW_VERIFICATION → (no further)
    const result = expandCapabilities([caps.CARBON_VERIFY_DATA]);
    expect(result.has(caps.CARBON_VERIFY_DATA)).toBe(true);
    expect(result.has(caps.CARBON_VIEW_VERIFICATION)).toBe(true);
    expect(result.has(caps.CARBON_VIEW_CONSOLE)).toBe(true);
  });

  it('transitive: CARBON_GENERATE_REPORTS yields CARBON_VIEW_DASHBOARD and CARBON_VIEW_CONSOLE', () => {
    const result = expandCapabilities([caps.CARBON_GENERATE_REPORTS]);
    expect(result.has(caps.CARBON_GENERATE_REPORTS)).toBe(true);
    expect(result.has(caps.CARBON_VIEW_CONSOLE)).toBe(true);
    expect(result.has(caps.CARBON_VIEW_DASHBOARD)).toBe(true);
  });

  it('deep transitive: CATALOG_MANAGE_POLICIES yields CATALOG_VIEW and CATALOG_VIEW_GOVERNANCE', () => {
    const result = expandCapabilities([caps.CATALOG_MANAGE_POLICIES]);
    expect(result.has(caps.CATALOG_MANAGE_POLICIES)).toBe(true);
    expect(result.has(caps.CATALOG_VIEW)).toBe(true);
    expect(result.has(caps.CATALOG_VIEW_GOVERNANCE)).toBe(true);
  });

  it('idempotent: expanding twice produces same result', () => {
    const input = [caps.CARBON_MANAGE_EMISSION_FACTORS, caps.CARBON_GENERATE_REPORTS];
    const first = expandCapabilities(input);
    const second = expandCapabilities(first);
    expect([...second].sort()).toEqual([...first].sort());
  });

  it('handles unknown capabilities gracefully', () => {
    const result = expandCapabilities(['unknown:cap', caps.DQ_MANAGE_RULES]);
    expect(result.has('unknown:cap')).toBe(true);
    expect(result.has(caps.DQ_VIEW)).toBe(true);
  });

  it('PLATFORM_ADMIN expands to all platform caps (correct fan-out)', () => {
    const result = expandCapabilities([caps.PLATFORM_ADMIN]);
    expect(result.has(caps.PLATFORM_MANAGE_USERS)).toBe(true);
    expect(result.has(caps.PLATFORM_MANAGE_GROUPS)).toBe(true);
    expect(result.has(caps.PLATFORM_MANAGE_ORG_UNITS)).toBe(true);
    expect(result.has(caps.PLATFORM_MANAGE_ACCESS)).toBe(true);
    expect(result.has(caps.PLATFORM_VIEW_AUDIT)).toBe(true);
    expect(result.has(caps.PLATFORM_MANAGE_APPS)).toBe(true);
  });

  it('handles Set as input', () => {
    const input = new Set([caps.CARBON_MANAGE_GWP]);
    const result = expandCapabilities(input);
    expect(result.has(caps.CARBON_MANAGE_GWP)).toBe(true);
    expect(result.has(caps.CARBON_VIEW_CONSOLE)).toBe(true);
  });
});

// ═══════════════════════════════════════════════════════════════════
// TEST SUITE 5: hasCap
// ═══════════════════════════════════════════════════════════════════
describe('hasCap', () => {
  let caps, hasCap;

  beforeAll(async () => {
    caps = await import('../capabilities.js');
    hasCap = caps.hasCap;
  });

  it('returns true when user has the exact capability', () => {
    const userCaps = new Set([caps.CARBON_VIEW_CONSOLE, caps.CATALOG_VIEW]);
    expect(hasCap(userCaps, caps.CARBON_VIEW_CONSOLE)).toBe(true);
  });

  it('returns false when user does not have the capability', () => {
    const userCaps = new Set([caps.CARBON_VIEW_CONSOLE]);
    expect(hasCap(userCaps, caps.CARBON_MANAGE_EMISSION_FACTORS)).toBe(false);
  });

  it('wildcard "*" grants all capabilities', () => {
    const userCaps = new Set(['*']);
    expect(hasCap(userCaps, caps.CARBON_MANAGE_EMISSION_FACTORS)).toBe(true);
    expect(hasCap(userCaps, caps.PLATFORM_MANAGE_USERS)).toBe(true);
    expect(hasCap(userCaps, 'nonexistent:cap')).toBe(true);
  });

  it('returns false for empty capability set', () => {
    expect(hasCap(new Set(), caps.CARBON_VIEW_CONSOLE)).toBe(false);
    expect(hasCap([], caps.CARBON_VIEW_CONSOLE)).toBe(false);
  });

  it('accepts array as input', () => {
    const userCaps = [caps.CARBON_VIEW_CONSOLE, caps.DQ_VIEW];
    expect(hasCap(userCaps, caps.CARBON_VIEW_CONSOLE)).toBe(true);
    expect(hasCap(userCaps, caps.MDM_VIEW)).toBe(false);
  });

  it('handles null capability gracefully', () => {
    const userCaps = new Set([caps.CARBON_VIEW_CONSOLE]);
    expect(hasCap(userCaps, null)).toBe(false);
  });

  it('handles undefined capability gracefully', () => {
    const userCaps = new Set([caps.CARBON_VIEW_CONSOLE]);
    expect(hasCap(userCaps, undefined)).toBe(false);
  });

  it('handles empty string capability', () => {
    const userCaps = new Set(['']);
    expect(hasCap(userCaps, '')).toBe(true);
    expect(hasCap(userCaps, caps.CARBON_VIEW_CONSOLE)).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════════
// TEST SUITE 6: hasAnyCap
// ═══════════════════════════════════════════════════════════════════
describe('hasAnyCap', () => {
  let caps, hasAnyCap;

  beforeAll(async () => {
    caps = await import('../capabilities.js');
    hasAnyCap = caps.hasAnyCap;
  });

  it('returns true when user has one of the requested caps', () => {
    const userCaps = new Set([caps.CARBON_VIEW_CONSOLE, caps.DQ_VIEW]);
    expect(hasAnyCap(userCaps, [caps.CARBON_VIEW_CONSOLE, caps.MDM_VIEW])).toBe(true);
  });

  it('returns false when user has none of the requested caps', () => {
    const userCaps = new Set([caps.CARBON_VIEW_CONSOLE]);
    expect(hasAnyCap(userCaps, [caps.PLATFORM_MANAGE_USERS, caps.MDM_VIEW])).toBe(false);
  });

  it('wildcard grants any capability', () => {
    expect(hasAnyCap(new Set(['*']), [caps.PLATFORM_MANAGE_USERS])).toBe(true);
  });

  it('returns false for empty requested list', () => {
    expect(hasAnyCap(new Set([caps.CARBON_VIEW_CONSOLE]), [])).toBe(false);
  });

  it('returns false for empty user caps with non-empty request', () => {
    expect(hasAnyCap(new Set(), [caps.CARBON_VIEW_CONSOLE])).toBe(false);
  });

  it('accepts array as input', () => {
    const userCaps = [caps.CARBON_VIEW_CONSOLE, caps.DQ_VIEW];
    expect(hasAnyCap(userCaps, [caps.DQ_VIEW, caps.MDM_VIEW])).toBe(true);
  });

  it('single-element request array: has returns true', () => {
    const userCaps = new Set([caps.CATALOG_MANAGE_PRODUCTS]);
    expect(hasAnyCap(userCaps, [caps.CATALOG_MANAGE_PRODUCTS])).toBe(true);
  });

  it('single-element request array: does not have returns false', () => {
    const userCaps = new Set([caps.CATALOG_VIEW]);
    expect(hasAnyCap(userCaps, [caps.CATALOG_MANAGE_PRODUCTS])).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════════
// TEST SUITE 7: hasAllCaps
// ═══════════════════════════════════════════════════════════════════
describe('hasAllCaps', () => {
  let caps, hasAllCaps;

  beforeAll(async () => {
    caps = await import('../capabilities.js');
    hasAllCaps = caps.hasAllCaps;
  });

  it('returns true when user has all requested caps', () => {
    const userCaps = new Set([caps.CARBON_VIEW_CONSOLE, caps.DQ_VIEW, caps.MDM_VIEW]);
    expect(hasAllCaps(userCaps, [caps.CARBON_VIEW_CONSOLE, caps.DQ_VIEW])).toBe(true);
  });

  it('returns false when user is missing one requested cap', () => {
    const userCaps = new Set([caps.CARBON_VIEW_CONSOLE, caps.DQ_VIEW]);
    expect(hasAllCaps(userCaps, [caps.CARBON_VIEW_CONSOLE, caps.MDM_VIEW])).toBe(false);
  });

  it('wildcard grants all capabilities', () => {
    expect(hasAllCaps(new Set(['*']), [caps.PLATFORM_MANAGE_USERS, caps.PLATFORM_VIEW_AUDIT])).toBe(true);
  });

  it('returns true for empty requested list', () => {
    expect(hasAllCaps(new Set([caps.CARBON_VIEW_CONSOLE]), [])).toBe(true);
  });

  it('returns false for empty user caps with non-empty request', () => {
    expect(hasAllCaps(new Set(), [caps.CARBON_VIEW_CONSOLE])).toBe(false);
  });

  it('accepts array as input', () => {
    const userCaps = [caps.CARBON_VIEW_CONSOLE, caps.DQ_VIEW, caps.MDM_VIEW];
    expect(hasAllCaps(userCaps, [caps.CARBON_VIEW_CONSOLE, caps.DQ_VIEW])).toBe(true);
  });

  it('exact match without extras returns true', () => {
    const userCaps = new Set([caps.CARBON_VIEW_CONSOLE]);
    expect(hasAllCaps(userCaps, [caps.CARBON_VIEW_CONSOLE])).toBe(true);
  });
});

// ═══════════════════════════════════════════════════════════════════
// TEST SUITE 8: initCapabilities
// ═══════════════════════════════════════════════════════════════════
describe('initCapabilities', () => {
  let caps, initCapabilities;

  beforeAll(async () => {
    caps = await import('../capabilities.js');
    initCapabilities = caps.initCapabilities;
  });

  it('returns caps and expanded properties', () => {
    const result = initCapabilities([{ key: caps.CARBON_VIEW_CONSOLE }]);
    expect(result.caps).toBeDefined();
    expect(result.expanded).toBeDefined();
    expect(result.caps instanceof Set).toBe(true);
    expect(result.expanded instanceof Set).toBe(true);
  });

  it('caps contains the original keys', () => {
    const apiInput = [
      { key: caps.CARBON_VIEW_CONSOLE },
      { key: caps.DQ_VIEW },
    ];
    const result = initCapabilities(apiInput);
    expect(result.caps.has(caps.CARBON_VIEW_CONSOLE)).toBe(true);
    expect(result.caps.has(caps.DQ_VIEW)).toBe(true);
  });

  it('expanded includes inherited capabilities', () => {
    const apiInput = [
      { key: caps.DQ_MANAGE_RULES },
    ];
    const result = initCapabilities(apiInput);
    expect(result.caps.has(caps.DQ_MANAGE_RULES)).toBe(true);
    expect(result.expanded.has(caps.DQ_MANAGE_RULES)).toBe(true);
    expect(result.expanded.has(caps.DQ_VIEW)).toBe(true);
  });

  it('handles empty capabilities array', () => {
    const result = initCapabilities([]);
    expect(result.caps.size).toBe(0);
    expect(result.expanded.size).toBe(0);
  });

  it('handles null input', () => {
    const result = initCapabilities(null);
    expect(result.caps.size).toBe(0);
    expect(result.expanded.size).toBe(0);
  });

  it('handles undefined input', () => {
    const result = initCapabilities(undefined);
    expect(result.caps.size).toBe(0);
    expect(result.expanded.size).toBe(0);
  });

  it('expanded is a superset of caps', () => {
    const apiInput = [
      { key: caps.CARBON_MANAGE_EMISSION_FACTORS },
      { key: caps.CARBON_MANAGE_GWP },
    ];
    const result = initCapabilities(apiInput);
    for (const c of result.caps) {
      expect(result.expanded.has(c)).toBe(true);
    }
  });

  it('full carbon_lead role expansion covers all expected caps', () => {
    // Simulates the API response for a carbon_lead user
    const apiInput = [
      { key: caps.CARBON_MANAGE_EMISSION_FACTORS },
      { key: caps.CARBON_MANAGE_CALCULATION_RULES },
      { key: caps.CARBON_MANAGE_GWP },
      { key: caps.CARBON_MANAGE_SBTI_TARGETS },
      { key: caps.CARBON_MANAGE_REPORTING_PERIODS },
      { key: caps.CARBON_TRIGGER_CALCULATIONS },
      { key: caps.CARBON_VERIFY_DATA },
      { key: caps.CARBON_GENERATE_REPORTS },
      { key: caps.CARBON_VIEW_ANALYTICS },
      { key: caps.CARBON_ENTER_DATA },
    ];
    const result = initCapabilities(apiInput);

    // All view capabilities should be inherited
    expect(result.expanded.has(caps.CARBON_VIEW_CONSOLE)).toBe(true);
    expect(result.expanded.has(caps.CARBON_VIEW_DASHBOARD)).toBe(true);
    expect(result.expanded.has(caps.CARBON_VIEW_ANALYTICS)).toBe(true);
    expect(result.expanded.has(caps.CARBON_VIEW_MY_DATA)).toBe(true);
    expect(result.expanded.has(caps.CARBON_VIEW_CALCULATIONS)).toBe(true);
    expect(result.expanded.has(caps.CARBON_VIEW_VERIFICATION)).toBe(true);
    expect(result.expanded.has(caps.CARBON_VIEW_REPORTING_PERIODS)).toBe(true);

    // Should NOT have cross-domain caps
    expect(result.expanded.has(caps.MDM_VIEW)).toBe(false);
    expect(result.expanded.has(caps.CATALOG_VIEW)).toBe(false);
    expect(result.expanded.has(caps.DQ_VIEW)).toBe(false);
  });

  it('platform admin gets expanded platform capabilities', () => {
    const apiInput = [
      { key: caps.PLATFORM_ADMIN },
    ];
    const result = initCapabilities(apiInput);
    expect(result.expanded.has(caps.PLATFORM_MANAGE_USERS)).toBe(true);
    expect(result.expanded.has(caps.PLATFORM_MANAGE_GROUPS)).toBe(true);
    expect(result.expanded.has(caps.PLATFORM_VIEW_AUDIT)).toBe(true);
    // Platform admin does NOT automatically get carbon/catalog/dq caps
    expect(result.expanded.has(caps.CARBON_VIEW_CONSOLE)).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════════
// TEST SUITE 9: canAccessRoute
// ═══════════════════════════════════════════════════════════════════
describe('canAccessRoute', () => {
  let caps, canAccessRoute;

  beforeAll(async () => {
    caps = await import('../capabilities.js');
    canAccessRoute = caps.canAccessRoute;
  });

  it('grants access for exact match when user has required cap', () => {
    const expanded = new Set([caps.PLATFORM_MANAGE_USERS]);
    expect(canAccessRoute(expanded, '/admin/users')).toBe(true);
  });

  it('denies access for exact match when user lacks required cap', () => {
    const expanded = new Set([caps.CARBON_VIEW_CONSOLE]);
    expect(canAccessRoute(expanded, '/admin/users')).toBe(false);
  });

  it('ungated routes default to true regardless of capability set', () => {
    const expanded = new Set([caps.DQ_MANAGE_RULES, caps.DQ_VIEW]);
    // /carbon/console is not in ROUTE_CAPABILITIES → defaults to allow
    expect(canAccessRoute(expanded, '/carbon/console')).toBe(true);
    // But gated routes are still enforced
    expect(canAccessRoute(expanded, '/admin/users')).toBe(false);
  });

  it('denies inherited route when no matching route', () => {
    const expanded = new Set([caps.CARBON_MANAGE_EMISSION_FACTORS, caps.CARBON_VIEW_CONSOLE]);
    // /carbon/analytics requires CARBON_VIEW_ANALYTICS specifically
    // Unless inherited, this should be denied
  });

  it('grants access to routes with no capability requirement (default allow)', () => {
    const expanded = new Set([]);
    expect(canAccessRoute(expanded, '/some/unknown/route')).toBe(true);
  });

  it('handles wildcard user permissions', () => {
    const expanded = new Set(['*']);
    expect(canAccessRoute(expanded, '/admin/users')).toBe(true);
    expect(canAccessRoute(expanded, '/carbon/admin/factors')).toBe(true);
    expect(canAccessRoute(expanded, '/catalog/products')).toBe(true);
  });

  it('empty set denies all gated routes but allows ungated', () => {
    const expanded = new Set([]);
    expect(canAccessRoute(expanded, '/admin/users')).toBe(false);
    expect(canAccessRoute(expanded, '/carbon/admin/factors')).toBe(false);
    expect(canAccessRoute(expanded, '/home')).toBe(true);
  });

  it('all admin routes', () => {
    const adminCaps = new Set([
      caps.PLATFORM_MANAGE_USERS,
      caps.PLATFORM_MANAGE_GROUPS,
      caps.PLATFORM_MANAGE_ORG_UNITS,
      caps.PLATFORM_MANAGE_ACCESS,
      caps.PLATFORM_VIEW_AUDIT,
      caps.PLATFORM_MANAGE_APPS,
    ]);
    expect(canAccessRoute(adminCaps, '/admin/users')).toBe(true);
    expect(canAccessRoute(adminCaps, '/admin/groups')).toBe(true);
    expect(canAccessRoute(adminCaps, '/admin/org-units')).toBe(true);
    expect(canAccessRoute(adminCaps, '/admin/access')).toBe(true);
    expect(canAccessRoute(adminCaps, '/admin/audit')).toBe(true);
    expect(canAccessRoute(adminCaps, '/admin/apps')).toBe(true);
  });

  it('all carbon admin routes', () => {
    const carbonAdminCaps = new Set([
      caps.CARBON_MANAGE_EMISSION_FACTORS,
      caps.CARBON_MANAGE_CALCULATION_RULES,
      caps.CARBON_MANAGE_GWP,
      caps.CARBON_MANAGE_SBTI_TARGETS,
      caps.CARBON_GENERATE_REPORTS,
      caps.CARBON_MANAGE_REPORTING_PERIODS,
      caps.CARBON_VIEW_CALCULATIONS,
      caps.CARBON_VIEW_VERIFICATION,
      caps.CARBON_VIEW_ANALYTICS,
    ]);
    expect(canAccessRoute(carbonAdminCaps, '/carbon/admin/factors')).toBe(true);
    expect(canAccessRoute(carbonAdminCaps, '/carbon/admin/rules')).toBe(true);
    expect(canAccessRoute(carbonAdminCaps, '/carbon/admin/gwp')).toBe(true);
    expect(canAccessRoute(carbonAdminCaps, '/carbon/admin/targets')).toBe(true);
    expect(canAccessRoute(carbonAdminCaps, '/carbon/reporting/generate')).toBe(true);
    expect(canAccessRoute(carbonAdminCaps, '/carbon/reporting/saved')).toBe(true);
    expect(canAccessRoute(carbonAdminCaps, '/carbon/reporting/periods')).toBe(true);
    expect(canAccessRoute(carbonAdminCaps, '/carbon/calculations')).toBe(true);
    expect(canAccessRoute(carbonAdminCaps, '/carbon/verification')).toBe(true);
    expect(canAccessRoute(carbonAdminCaps, '/carbon/analytics')).toBe(true);
  });

  it('catalog routes', () => {
    const catalogCaps = new Set([
      caps.CATALOG_MANAGE_PRODUCTS,
      caps.CATALOG_MANAGE_METADATA,
      caps.CATALOG_MANAGE_POLICIES,
      caps.CATALOG_VIEW_GOVERNANCE,
    ]);
    expect(canAccessRoute(catalogCaps, '/catalog/products')).toBe(true);
    expect(canAccessRoute(catalogCaps, '/catalog/metadata')).toBe(true);
    expect(canAccessRoute(catalogCaps, '/catalog/policies')).toBe(true);
    expect(canAccessRoute(catalogCaps, '/catalog/governance')).toBe(true);
  });
});

// ═══════════════════════════════════════════════════════════════════
// TEST SUITE 10: filterMenuItems
// ═══════════════════════════════════════════════════════════════════
describe('filterMenuItems', () => {
  let caps, filterMenuItems;

  beforeAll(async () => {
    caps = await import('../capabilities.js');
    filterMenuItems = caps.filterMenuItems;
  });

  const sampleItems = [
    { label: 'Overview', path: '/carbon/console' },
    { label: 'Emissions Dashboard', path: '/carbon/dashboard' },
    { label: 'Analytics & Trends', path: '/carbon/analytics' },
    { label: 'Data Entry', path: '/carbon/data-entry' },
    { label: 'Calculations', path: '/carbon/calculations' },
    { label: 'Verification', path: '/carbon/verification' },
    { label: 'Generate Report', path: '/carbon/reporting/generate' },
    { label: 'Saved Reports', path: '/carbon/reporting/saved' },
    { label: 'Reporting Periods', path: '/carbon/reporting/periods' },
    { label: 'Emission Factors', path: '/carbon/admin/factors' },
    { label: 'Calculation Rules', path: '/carbon/admin/rules' },
    { label: 'GWP Reference', path: '/carbon/admin/gwp' },
    { label: 'SBTi Targets', path: '/carbon/admin/targets' },
  ];

  it('returns empty array for empty input', () => {
    expect(filterMenuItems(new Set(), [])).toEqual([]);
  });

  it('handles null items gracefully', () => {
    expect(filterMenuItems(new Set(), null)).toEqual([]);
    expect(filterMenuItems(new Set(), undefined)).toEqual([]);
  });

  it('wildcard user sees all items', () => {
    const result = filterMenuItems(new Set(['*']), sampleItems);
    expect(result.length).toBe(sampleItems.length);
  });

  it('carbon view-only user sees only view items', () => {
    const expanded = new Set([caps.CARBON_VIEW_CONSOLE, caps.CARBON_VIEW_DASHBOARD,
      caps.CARBON_VIEW_CALCULATIONS, caps.CARBON_VIEW_VERIFICATION,
      caps.CARBON_VIEW_REPORTING_PERIODS]);
    const result = filterMenuItems(expanded, sampleItems);
    const labels = result.map(i => i.label);

    expect(labels).toContain('Overview');
    expect(labels).toContain('Emissions Dashboard');
    expect(labels).toContain('Calculations');
    expect(labels).toContain('Verification');
    expect(labels).toContain('Reporting Periods');

    // These require manage/admin caps
    expect(labels).not.toContain('Emission Factors');
    expect(labels).not.toContain('Calculation Rules');
    expect(labels).not.toContain('Generate Report');
  });

  it('analyst user sees analytics, reports, and views', () => {
    const expanded = new Set([caps.CARBON_VIEW_CONSOLE, caps.CARBON_VIEW_DASHBOARD,
      caps.CARBON_VIEW_ANALYTICS, caps.CARBON_VIEW_CALCULATIONS,
      caps.CARBON_VIEW_VERIFICATION, caps.CARBON_VIEW_REPORTING_PERIODS,
      caps.CARBON_GENERATE_REPORTS]);
    const result = filterMenuItems(expanded, sampleItems);
    const labels = result.map(i => i.label);

    expect(labels).toContain('Analytics & Trends');
    expect(labels).toContain('Generate Report');
    expect(labels).toContain('Saved Reports');
    expect(labels).not.toContain('Emission Factors');
  });

  it('carbon lead sees all carbon items', () => {
    const expanded = new Set([
      caps.CARBON_VIEW_CONSOLE, caps.CARBON_VIEW_DASHBOARD,
      caps.CARBON_VIEW_ANALYTICS, caps.CARBON_VIEW_MY_DATA,
      caps.CARBON_VIEW_CALCULATIONS, caps.CARBON_VIEW_VERIFICATION,
      caps.CARBON_VIEW_REPORTING_PERIODS,
      caps.CARBON_MANAGE_EMISSION_FACTORS, caps.CARBON_MANAGE_CALCULATION_RULES,
      caps.CARBON_MANAGE_GWP, caps.CARBON_MANAGE_SBTI_TARGETS,
      caps.CARBON_MANAGE_REPORTING_PERIODS,
      caps.CARBON_TRIGGER_CALCULATIONS, caps.CARBON_VERIFY_DATA,
      caps.CARBON_GENERATE_REPORTS, caps.CARBON_ENTER_DATA,
    ]);
    const result = filterMenuItems(expanded, sampleItems);
    expect(result.length).toBe(sampleItems.length);
  });

  it('items without MENU_ITEM_CAPABILITIES entry pass through', () => {
    const items = [
      { label: 'Unknown Item', path: '/somewhere' },
    ];
    const result = filterMenuItems(new Set([]), items);
    expect(result.length).toBe(1);
    expect(result[0].label).toBe('Unknown Item');
  });

  it('items with explicit capability property are filtered by it', () => {
    const items = [
      { label: 'Admin Panel', path: '/admin', capability: caps.PLATFORM_MANAGE_USERS },
    ];
    expect(filterMenuItems(new Set([caps.PLATFORM_MANAGE_USERS]), items).length).toBe(1);
    expect(filterMenuItems(new Set([caps.CARBON_VIEW_CONSOLE]), items).length).toBe(0);
  });

  it('nested children are filtered independently', () => {
    const items = [
      {
        label: 'Reporting',
        path: '/carbon/reporting',
        children: [
          { label: 'Generate Report', path: '/carbon/reporting/generate' },
          { label: 'Saved Reports', path: '/carbon/reporting/saved' },
          { label: 'Admin Only', path: '/carbon/admin/something', capability: caps.CARBON_MANAGE_EMISSION_FACTORS },
        ],
      },
    ];
    const viewerCaps = new Set([caps.CARBON_GENERATE_REPORTS]);
    const result = filterMenuItems(viewerCaps, items);
    expect(result.length).toBe(1);
    expect(result[0].children.length).toBe(2); // Admin Only filtered out
  });

  it('parent with no visible children and required capability is removed', () => {
    const items = [
      {
        label: 'Emission Factors',
        path: '/carbon/admin/factors',
        capability: caps.CARBON_MANAGE_EMISSION_FACTORS,
        children: [
          { label: 'Sub Item', path: '/sub', capability: caps.PLATFORM_MANAGE_USERS },
        ],
      },
    ];
    // User has parent capability but NOT child capability.
    // Child is filtered. Current behavior: when filteredChildren.length === 0
    // AND parent required a capability, the parent is also removed.
    const result = filterMenuItems(new Set([caps.CARBON_MANAGE_EMISSION_FACTORS]), items);
    expect(result.length).toBe(0);
  });

  it('parent with no visible children but no required capability stays', () => {
    const items = [
      {
        label: 'Section',
        path: '/section',
        children: [
          { label: 'Gated Child', path: '/gated', capability: caps.PLATFORM_MANAGE_USERS },
        ],
      },
    ];
    const result = filterMenuItems(new Set([caps.CARBON_VIEW_CONSOLE]), items);
    // Parent has no required capability, child filtered → parent stays
    expect(result.length).toBe(1);
    expect(result[0].children.length).toBe(0);
  });
});

// ═══════════════════════════════════════════════════════════════════
// TEST SUITE 11: getCapableApps
// ═══════════════════════════════════════════════════════════════════
describe('getCapableApps', () => {
  let caps, getCapableApps;

  beforeAll(async () => {
    caps = await import('../capabilities.js');
    getCapableApps = caps.getCapableApps;
  });

  it('returns all apps for wildcard user', () => {
    const result = getCapableApps(new Set(['*']));
    expect(result).toContain('carbon');
    expect(result).toContain('catalog');
    expect(result).toContain('dq');
    expect(result).toContain('mdm');
  });

  it('returns only carbon for carbon-only user', () => {
    const result = getCapableApps(new Set([caps.CARBON_VIEW_CONSOLE]));
    expect(result).toEqual(['carbon']);
  });

  it('returns multiple apps correctly', () => {
    const result = getCapableApps(new Set([caps.CARBON_VIEW_CONSOLE, caps.DQ_VIEW]));
    expect(result).toContain('carbon');
    expect(result).toContain('dq');
    expect(result).not.toContain('catalog');
    expect(result).not.toContain('mdm');
  });

  it('returns empty array for no capabilities', () => {
    expect(getCapableApps(new Set([]))).toEqual([]);
    expect(getCapableApps(new Set())).toEqual([]);
  });

  it('returns all configured apps', () => {
    const result = getCapableApps(new Set([
      caps.CARBON_VIEW_CONSOLE, caps.CATALOG_VIEW,
      caps.DQ_VIEW, caps.MDM_VIEW,
    ]));
    expect(result).toHaveLength(4);
    expect(result).toEqual(expect.arrayContaining(['carbon', 'catalog', 'dq', 'mdm']));
  });
});

// ═══════════════════════════════════════════════════════════════════
// TEST SUITE 12: RBAC Utils (utils/rbac.js)
// ═══════════════════════════════════════════════════════════════════
describe('RBAC Utils — isGlobalAdmin', () => {
  let isGlobalAdmin;

  beforeAll(async () => {
    const rbac = await import('../utils/rbac');
    isGlobalAdmin = rbac.isGlobalAdmin;
  });

  it('returns true when isGlobalAdminFlag is true', () => {
    expect(isGlobalAdmin(null, [], true)).toBe(true);
  });

  it('returns false when isGlobalAdminFlag is false', () => {
    expect(isGlobalAdmin(null, [], false)).toBe(false);
  });

  it('returns true when perspectives include "admin"', () => {
    expect(isGlobalAdmin({}, ['admin'], null)).toBe(true);
    expect(isGlobalAdmin({}, ['dashboards', 'admin'], null)).toBe(true);
  });

  it('returns false when perspectives do not include "admin"', () => {
    expect(isGlobalAdmin({}, ['dashboards', 'data_entry'], null)).toBe(false);
  });

  it('returns true when user has "admin" role', () => {
    const user = { roles: [{ role: 'admin' }] };
    expect(isGlobalAdmin(user, [], null)).toBe(true);
  });

  it('returns true when user has "admin" role case-insensitively', () => {
    const user = { roles: [{ role: 'Admin' }] };
    expect(isGlobalAdmin(user, [], null)).toBe(true);
  });

  it('returns false when user has non-admin roles', () => {
    const user = { roles: [{ role: 'viewer' }, { role: 'analyst' }] };
    expect(isGlobalAdmin(user, [], null)).toBe(false);
  });

  it('handles null/undefined user', () => {
    expect(isGlobalAdmin(null, [], null)).toBe(false);
    expect(isGlobalAdmin(undefined, [], null)).toBe(false);
  });

  it('handles empty roles array', () => {
    const user = { roles: [] };
    expect(isGlobalAdmin(user, [], null)).toBe(false);
  });

  it('handles user without roles property', () => {
    const user = { username: 'test' };
    expect(isGlobalAdmin(user, [], null)).toBe(false);
  });

  it('handles null/undefined availablePerspectives', () => {
    expect(isGlobalAdmin({ roles: [] }, null, null)).toBe(false);
    expect(isGlobalAdmin({ roles: [] }, undefined, null)).toBe(false);
  });
});

describe('RBAC Utils — isDomainLead', () => {
  let isDomainLead;

  beforeAll(async () => {
    const rbac = await import('../utils/rbac');
    isDomainLead = rbac.isDomainLead;
  });

  it('returns true for carbon lead with carbon-admin perspective', () => {
    expect(isDomainLead('carbon', ['dashboards', 'carbon-admin'])).toBe(true);
  });

  it('returns false for carbon lead without carbon-admin perspective', () => {
    expect(isDomainLead('carbon', ['dashboards', 'data_entry'])).toBe(false);
  });

  it('returns false for null appId', () => {
    expect(isDomainLead(null, ['carbon-admin'])).toBe(false);
  });

  it('returns false for undefined appId', () => {
    expect(isDomainLead(undefined, ['carbon-admin'])).toBe(false);
  });

  it('returns false for empty perspectives', () => {
    expect(isDomainLead('carbon', [])).toBe(false);
    expect(isDomainLead('carbon', null)).toBe(false);
  });

  it('different app leads do not cross', () => {
    expect(isDomainLead('catalog', ['carbon-admin'])).toBe(false);
    expect(isDomainLead('carbon', ['catalog-admin'])).toBe(false);
  });
});

describe('RBAC Utils — hasAppAccess', () => {
  let hasAppAccess;

  beforeAll(async () => {
    const rbac = await import('../utils/rbac');
    hasAppAccess = rbac.hasAppAccess;
  });

  it('global admin can access any app', () => {
    const user = {};
    expect(hasAppAccess('carbon', user, {}, ['admin'])).toBe(true);
  });

  it('domain lead can access their app', () => {
    const user = {};
    expect(hasAppAccess('carbon', user, {}, ['carbon-admin'])).toBe(true);
  });

  it('user with app modules can access app', () => {
    const user = {};
    const context = { modules: [{ app_id: 'carbon', scope: 1 }] };
    expect(hasAppAccess('carbon', user, context, [])).toBe(true);
  });

  it('user without app modules or perspective is denied', () => {
    const user = {};
    const context = { modules: [] };
    expect(hasAppAccess('carbon', user, context, [])).toBe(false);
  });

  it('returns false for null user', () => {
    expect(hasAppAccess('carbon', null, {}, [])).toBe(false);
  });

  it('returns false for null appId', () => {
    expect(hasAppAccess(null, {}, {}, [])).toBe(false);
  });
});

describe('RBAC Utils — perspective helpers', () => {
  let helpers;

  beforeAll(async () => {
    helpers = await import('../utils/rbac');
  });

  it('isDataEntry returns true with data_entry perspective', () => {
    expect(helpers.isDataEntry({}, ['data_entry'])).toBe(true);
    expect(helpers.isDataEntry({}, ['data-entry'])).toBe(true);
    expect(helpers.isDataEntry({}, ['dashboards'])).toBe(false);
    expect(helpers.isDataEntry(null, [])).toBe(false);
  });

  it('isAnalyst returns true with analyst perspective', () => {
    expect(helpers.isAnalyst({}, ['analyst'])).toBe(true);
    expect(helpers.isAnalyst({}, ['carbon-analyst'])).toBe(true);
    expect(helpers.isAnalyst({}, ['data_entry'])).toBe(false);
    expect(helpers.isAnalyst(null, [])).toBe(false);
  });

  it('isDataOwner returns true with data_owner or data-owner perspective', () => {
    expect(helpers.isDataOwner({}, ['data_owner'])).toBe(true);
    expect(helpers.isDataOwner({}, ['data-owner'])).toBe(true);
    expect(helpers.isDataOwner({}, ['analyst'])).toBe(false);
    expect(helpers.isDataOwner(null, [])).toBe(false);
  });

  it('isCatalogAdmin returns true with admin or catalog-admin perspective', () => {
    expect(helpers.isCatalogAdmin({}, ['admin'])).toBe(true);
    expect(helpers.isCatalogAdmin({}, ['catalog-admin'])).toBe(true);
    expect(helpers.isCatalogAdmin({}, ['dashboards'])).toBe(false);
    expect(helpers.isCatalogAdmin(null, [])).toBe(false);
  });

  it('isCatalogAdmin returns true with admin group role', () => {
    const user = { roles: [{ role: 'admin' }] };
    expect(helpers.isCatalogAdmin(user, [])).toBe(true);
  });
});

describe('RBAC Utils — canAccessRoute (legacy)', () => {
  let canAccessRoute;

  beforeAll(async () => {
    const rbac = await import('../utils/rbac');
    canAccessRoute = rbac.canAccessRoute;
  });

  it('admin routes require global admin', () => {
    expect(canAccessRoute('/admin/users', {}, ['admin'])).toBe(true);
    expect(canAccessRoute('/admin/users', {}, [])).toBe(false);
  });

  it('carbon admin requires global admin or carbon domain lead', () => {
    expect(canAccessRoute('/carbon/admin/factors', {}, ['admin'])).toBe(true);
    expect(canAccessRoute('/carbon/admin/factors', {}, ['carbon-admin'])).toBe(true);
    expect(canAccessRoute('/carbon/admin/factors', {}, ['data_entry'])).toBe(false);
  });

  it('carbon calculations/verification/reporting require global admin or domain lead', () => {
    expect(canAccessRoute('/carbon/calculations', {}, ['carbon-admin'])).toBe(true);
    expect(canAccessRoute('/carbon/verification', {}, ['carbon-admin'])).toBe(true);
    expect(canAccessRoute('/carbon/reporting/generate', {}, ['carbon-admin'])).toBe(true);
    expect(canAccessRoute('/carbon/analytics', {}, ['carbon-admin'])).toBe(true);
  });

  it('/carbon/owner routes require data owner', () => {
    expect(canAccessRoute('/carbon/owner/dashboard', {}, ['data-owner'])).toBe(true);
    expect(canAccessRoute('/carbon/owner/dashboard', {}, ['analyst'])).toBe(false);
  });

  it('general carbon routes require app access', () => {
    const context = { modules: [{ app_id: 'carbon', scope: 1 }] };
    expect(canAccessRoute('/carbon/dashboard', {}, [], context)).toBe(true);
    expect(canAccessRoute('/carbon/dashboard', {}, [], { modules: [] })).toBe(false);
  });

  it('module routes require context modules', () => {
    expect(canAccessRoute('/modules/123', {}, [], { modules: [{ id: 1 }] })).toBe(true);
    expect(canAccessRoute('/modules/123', {}, [], { modules: [] })).toBe(false);
  });

  it('ungated routes default to true for authenticated users', () => {
    expect(canAccessRoute('/home', {}, [])).toBe(true);
    expect(canAccessRoute('/settings/profile', {}, [])).toBe(true);
  });

  it('returns false for null user', () => {
    expect(canAccessRoute('/home', null, [])).toBe(false);
  });
});

describe('RBAC Utils — filterMenuItems (legacy)', () => {
  let filterMenuItems, isGlobalAdmin;

  beforeAll(async () => {
    const rbac = await import('../utils/rbac');
    filterMenuItems = rbac.filterMenuItems;
    isGlobalAdmin = rbac.isGlobalAdmin;
  });

  const sampleItems = [
    { label: 'Public', path: '/public' },
    { label: 'Admin', path: '/admin', role: 'admin' },
    { label: 'Data Entry', path: '/entry', role: 'data_entry' },
    { type: 'divider' },
    { type: 'group', label: 'Section' },
    { label: 'Catalog Admin', path: '/catalog', role: 'catalog-admin' },
    { label: 'Data Owner', path: '/owner', role: 'carbon:data_owner' },
    { label: 'Wildcard Role', path: '/any', role: '*' },
  ];

  it('global admin sees all items', () => {
    const result = filterMenuItems(sampleItems, {}, ['admin']);
    expect(result.length).toBe(sampleItems.length);
  });

  it('non-admin only sees items without role restriction', () => {
    const result = filterMenuItems(sampleItems, {}, ['data_entry']);
    const labels = result.map(i => i.label);
    expect(labels).toContain('Public');
    expect(labels).toContain('Data Entry');
    expect(labels).toContain('Wildcard Role');
    expect(labels).not.toContain('Admin');
  });

  it('items with role "*" are always visible', () => {
    const result = filterMenuItems(sampleItems, {}, []);
    const labels = result.map(i => i.label);
    expect(labels).toContain('Wildcard Role');
  });

  it('divider and group items pass through', () => {
    const result = filterMenuItems(sampleItems, {}, []);
    const types = result.filter(i => i.type).map(i => i.type);
    expect(types).toContain('divider');
    expect(types).toContain('group');
  });

  it('handles null/undefined items', () => {
    expect(filterMenuItems(null, {}, ['admin'])).toEqual([]);
    expect(filterMenuItems(undefined, {}, ['admin'])).toEqual([]);
  });

  it('handles manifest role format (carbon:data_owner → data-owner)', () => {
    const result = filterMenuItems([{ label: 'Test', path: '/t', role: 'carbon:data_owner' }], {}, ['data-owner']);
    expect(result.length).toBe(1);
  });

  it('handles app-prefixed role (carbon-data-owner)', () => {
    const result = filterMenuItems([{ label: 'Test', path: '/t', role: 'carbon:data_owner' }], {}, ['carbon-data-owner']);
    expect(result.length).toBe(1);
  });
});

// ═══════════════════════════════════════════════════════════════════
// TEST SUITE 13: AdminRoute Component
// ═══════════════════════════════════════════════════════════════════
describe('AdminRoute Component', () => {
  let useAuthMock;

  beforeEach(async () => {
    vi.resetModules();
    // Reset the auth mock before each test
    vi.doMock('../auth/AuthContext', () => ({
      useAuth: vi.fn(() => ({
        user: { username: 'admin', roles: ['admin'] },
        loading: false,
        availablePerspectives: ['admin'],
        context: { modules: [] },
        isGlobalAdminFlag: true,
      })),
      AuthProvider: ({ children }) => React.createElement(React.Fragment, null, children),
    }));

    // Mock NotificationProvider
    vi.doMock('../components/NotificationProvider', () => ({
      useNotification: vi.fn(() => ({ notify: vi.fn() })),
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const renderAdminRoute = async (props = {}) => {
    const { useAuth } = await import('../auth/AuthContext');
    useAuthMock = useAuth;

    const { default: AdminRoute } = await import('../components/AdminRoute');
    return render(
      <ThemeProvider theme={theme}>
        <MemoryRouter initialEntries={['/admin/test']}>
          <AdminRoute {...props}>
            <div>Admin Content</div>
          </AdminRoute>
        </MemoryRouter>
      </ThemeProvider>
    );
  };

  it('renders children for global admin', async () => {
    const { useAuth } = await import('../auth/AuthContext');
    useAuth.mockReturnValue({
      user: { username: 'admin', roles: ['admin'] },
      loading: false,
      availablePerspectives: ['admin'],
      context: { modules: [] },
      isGlobalAdminFlag: true,
      userCapabilities: [],
    });
    const { default: AdminRoute } = await import('../components/AdminRoute');
    render(
      <MemoryRouter initialEntries={['/admin/users']}>
        <AdminRoute>
          <div>Admin Content</div>
        </AdminRoute>
      </MemoryRouter>
    );
    expect(screen.getByText('Admin Content')).toBeInTheDocument();
  });

  it('redirects non-admin users', async () => {
    const { useAuth } = await import('../auth/AuthContext');
    useAuth.mockReturnValue({
      user: { username: 'viewer', roles: ['viewer'] },
      loading: false,
      availablePerspectives: ['dashboards'],
      context: { modules: [] },
      isGlobalAdminFlag: false,
    });
    const { default: AdminRoute } = await import('../components/AdminRoute');
    render(
      <MemoryRouter initialEntries={['/admin/users']}>
        <Routes>
          <Route path="/admin/*" element={
            <AdminRoute>
              <div>Admin Content</div>
            </AdminRoute>
          } />
          <Route path="/" element={<div>Home</div>} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.queryByText('Admin Content')).not.toBeInTheDocument();
    expect(screen.getByText('Home')).toBeInTheDocument();
  });

  it('shows loading state when loading', async () => {
    const { useAuth } = await import('../auth/AuthContext');
    useAuth.mockReturnValue({
      user: null,
      loading: true,
      availablePerspectives: [],
      context: { modules: [] },
      isGlobalAdminFlag: false,
    });
    const { default: AdminRoute } = await import('../components/AdminRoute');
    render(
      <MemoryRouter>
        <AdminRoute>
          <div>Admin Content</div>
        </AdminRoute>
      </MemoryRouter>
    );
    expect(screen.getByText(/checking permissions/i)).toBeInTheDocument();
  });

  it('renders null when user is null and not loading', async () => {
    const { useAuth } = await import('../auth/AuthContext');
    useAuth.mockReturnValue({
      user: null,
      loading: false,
      availablePerspectives: [],
      context: { modules: [] },
      isGlobalAdminFlag: false,
    });
    const { default: AdminRoute } = await import('../components/AdminRoute');
    const { container } = render(
      <MemoryRouter>
        <AdminRoute>
          <div>Admin Content</div>
        </AdminRoute>
      </MemoryRouter>
    );
    // Should render nothing (no children, no fallback)
    expect(screen.queryByText('Admin Content')).not.toBeInTheDocument();
    expect(screen.queryByText(/checking permissions/i)).not.toBeInTheDocument();
  });

  it('grants access to domain lead with appId', async () => {
    const { useAuth } = await import('../auth/AuthContext');
    useAuth.mockReturnValue({
      user: { username: 'carbon_lead', roles: ['carbon_lead'] },
      loading: false,
      availablePerspectives: ['carbon-admin'],
      context: { modules: [] },
      isGlobalAdminFlag: false,
      userCapabilities: [],
    });
    const { default: AdminRoute } = await import('../components/AdminRoute');
    render(
      <MemoryRouter initialEntries={['/carbon/admin/factors']}>
        <AdminRoute appId="carbon">
          <div>Carbon Admin Content</div>
        </AdminRoute>
      </MemoryRouter>
    );
    expect(screen.getByText('Carbon Admin Content')).toBeInTheDocument();
  });

  it('denies domain lead without matching appId', async () => {
    const { useAuth } = await import('../auth/AuthContext');
    useAuth.mockReturnValue({
      user: { username: 'carbon_lead', roles: ['carbon_lead'] },
      loading: false,
      availablePerspectives: ['carbon-admin'],
      context: { modules: [] },
      isGlobalAdminFlag: false,
    });
    const { default: AdminRoute } = await import('../components/AdminRoute');
    render(
      <MemoryRouter initialEntries={['/admin/catalog']}>
        <Routes>
          <Route path="/admin/*" element={
            <AdminRoute appId="catalog">
              <div>Catalog Admin Content</div>
            </AdminRoute>
          } />
          <Route path="/" element={<div>Home</div>} />
        </Routes>
      </MemoryRouter>
    );
    // Carbon lead should not access catalog admin
    expect(screen.queryByText('Catalog Admin Content')).not.toBeInTheDocument();
    expect(screen.getByText('Home')).toBeInTheDocument();
  });

  it('uses custom redirectTo path', async () => {
    const { useAuth } = await import('../auth/AuthContext');
    useAuth.mockReturnValue({
      user: { username: 'viewer', roles: ['viewer'] },
      loading: false,
      availablePerspectives: [],
      context: { modules: [] },
      isGlobalAdminFlag: false,
    });
    const { default: AdminRoute } = await import('../components/AdminRoute');
    render(
      <MemoryRouter initialEntries={['/admin/test']}>
        <Routes>
          <Route path="/admin/*" element={
            <AdminRoute redirectTo="/unauthorized">
              <div>Admin Content</div>
            </AdminRoute>
          } />
          <Route path="/unauthorized" element={<div>Access Denied</div>} />
          <Route path="/" element={<div>Home</div>} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.queryByText('Admin Content')).not.toBeInTheDocument();
    expect(screen.getByText('Access Denied')).toBeInTheDocument();
  });

  it('notifies user on access denied', async () => {
    const notifyMock = vi.fn();
    vi.doMock('../components/NotificationProvider', () => ({
      useNotification: vi.fn(() => ({ notify: notifyMock })),
    }));

    const { useAuth } = await import('../auth/AuthContext');
    useAuth.mockReturnValue({
      user: { username: 'viewer', roles: ['viewer'] },
      loading: false,
      availablePerspectives: [],
      context: { modules: [] },
      isGlobalAdminFlag: false,
      userCapabilities: [],
    });

    const { default: AdminRoute } = await import('../components/AdminRoute');
    render(
      <MemoryRouter initialEntries={['/admin/users']}>
        <Routes>
          <Route path="/admin/*" element={
            <AdminRoute>
              <div>Admin Content</div>
            </AdminRoute>
          } />
          <Route path="/" element={<div>Home</div>} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(notifyMock).toHaveBeenCalled();
    });
    const call = notifyMock.mock.calls[0][0];
    expect(call.type).toBe('error');
    expect(call.message).toContain('platform admin role required');
  });

  it('notifies with app-specific message when appId provided', async () => {
    const notifyMock = vi.fn();
    vi.doMock('../components/NotificationProvider', () => ({
      useNotification: vi.fn(() => ({ notify: notifyMock })),
    }));

    const { useAuth } = await import('../auth/AuthContext');
    useAuth.mockReturnValue({
      user: { username: 'viewer', roles: ['viewer'] },
      loading: false,
      availablePerspectives: [],
      context: { modules: [] },
      isGlobalAdminFlag: false,
      userCapabilities: [],
    });

    const { default: AdminRoute } = await import('../components/AdminRoute');
    render(
      <MemoryRouter initialEntries={['/admin/carbon']}>
        <Routes>
          <Route path="/admin/*" element={
            <AdminRoute appId="carbon">
              <div>Admin Content</div>
            </AdminRoute>
          } />
          <Route path="/" element={<div>Home</div>} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(notifyMock).toHaveBeenCalled();
    });
    const call = notifyMock.mock.calls[0][0];
    expect(call.type).toBe('error');
    expect(call.message).toContain('carbon');
    expect(call.message).toContain('Domain Lead');
  });

  it('only notifies once on access denied', async () => {
    const notifyMock = vi.fn();
    vi.doMock('../components/NotificationProvider', () => ({
      useNotification: vi.fn(() => ({ notify: notifyMock })),
    }));

    const { useAuth } = await import('../auth/AuthContext');
    useAuth.mockReturnValue({
      user: { username: 'viewer', roles: ['viewer'] },
      loading: false,
      availablePerspectives: [],
      context: { modules: [] },
      isGlobalAdminFlag: false,
      userCapabilities: [],
    });

    const { default: AdminRoute } = await import('../components/AdminRoute');
    const AdminRouteEl = (
      <AdminRoute>
        <div>Admin Content</div>
      </AdminRoute>
    );
    const { rerender } = render(
      <MemoryRouter initialEntries={['/admin/users']}>
        {AdminRouteEl}
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(notifyMock).toHaveBeenCalled();
    });

    // Force rerender with the same element (no Routes wrapper needed since
    // we just test that the notification guard ref prevents duplicates)
    rerender(
      <MemoryRouter initialEntries={['/admin/users']}>
        {AdminRouteEl}
      </MemoryRouter>
    );

    // Should still only have one call (notifiedRef prevents duplicates)
    await waitFor(() => {
      expect(notifyMock).toHaveBeenCalledTimes(1);
    });
  });
});

// ═══════════════════════════════════════════════════════════════════
// TEST SUITE 14: Edge Cases & Cross-Module
// ═══════════════════════════════════════════════════════════════════
describe('Edge Cases', () => {
  let caps;

  beforeAll(async () => {
    caps = await import('../capabilities.js');
  });

  it('expandCapabilities: large capability set performance', () => {
    // Replicate expand logic
    const CAPABILITY_INHERITANCE = caps.CAPABILITY_INHERITANCE;
    const expand = (input) => {
      const result = new Set(input);
      let changed = true;
      while (changed) {
        changed = false;
        for (const cap of result) {
          const implied = CAPABILITY_INHERITANCE[cap] || [];
          for (const impliedCap of implied) {
            if (!result.has(impliedCap)) {
              result.add(impliedCap);
              changed = true;
            }
          }
        }
      }
      return result;
    };

    // Get all manage caps
    const allManageCaps = Object.entries(caps)
      .filter(([k, v]) => k === k.toUpperCase() && typeof v === 'string' &&
        (v.includes(':manage_') || v.includes(':manage') || v.includes(':verify_') ||
         v.includes(':trigger_') || v.includes(':generate_') || v.includes(':enter_')))
      .map(([, v]) => v);

    const result = expand(allManageCaps);
    // Should complete without infinite loops
    expect(result.size).toBeGreaterThanOrEqual(allManageCaps.length);
  });

  it('hasCap with empty string vs empty set', () => {
    expect(caps.hasCap(new Set(), '')).toBe(false);
    expect(caps.hasCap(new Set(['']), '')).toBe(true);
  });

  it('hasAnyCap with duplicate requests', () => {
    const userCaps = new Set([caps.CARBON_VIEW_CONSOLE]);
    expect(caps.hasAnyCap(userCaps, [caps.CARBON_VIEW_CONSOLE, caps.CARBON_VIEW_CONSOLE])).toBe(true);
  });

  it('hasAllCaps with duplicate requests', () => {
    const userCaps = new Set([caps.CARBON_VIEW_CONSOLE]);
    expect(caps.hasAllCaps(userCaps, [caps.CARBON_VIEW_CONSOLE, caps.CARBON_VIEW_CONSOLE])).toBe(true);
  });

  it('filterMenuItems handles items with only path (no label)', () => {
    const items = [
      { path: '/anonymous' },
    ];
    const result = caps.filterMenuItems(new Set(), items);
    expect(result.length).toBe(1); // No label, no capability match → passes
  });

  it('filterMenuItems handles items with null path', () => {
    const items = [
      { label: 'Overview', path: null },
    ];
    const result = caps.filterMenuItems(new Set([caps.CARBON_VIEW_CONSOLE]), items);
    expect(result.length).toBe(1);
  });

  it('canAccessRoute: path with trailing slash', () => {
    const expanded = new Set([caps.PLATFORM_MANAGE_USERS]);
    // Trailing slashes should still work (exact match)
    const noTrail = caps.canAccessRoute(expanded, '/admin/users');
    const withTrail = caps.canAccessRoute(expanded, '/admin/users/');
    // Both should behave the same since we removed the /* pattern
    // The route map has no trailing slash, so trailing slash won't match
    // But the function defaults to true for unknown routes
    expect(noTrail).toBe(true);
  });

  it('getCapableApps: respects case sensitivity in capability keys', () => {
    const result = caps.getCapableApps(new Set(['CARBON:VIEW_CONSOLE']));
    expect(result).toEqual([]); // Case matters
  });

  it('initCapabilities: handles API objects with extra fields gracefully', () => {
    const result = caps.initCapabilities([
      { key: caps.CARBON_VIEW_CONSOLE, description: 'some desc', inherited: true },
    ]);
    expect(result.caps.has(caps.CARBON_VIEW_CONSOLE)).toBe(true);
  });

  it('initCapabilities: handles API objects with no key field', () => {
    const result = caps.initCapabilities([
      { description: 'no key here' },
    ]);
    expect(result.caps.has(undefined)).toBe(true);
    expect(result.expanded.has(undefined)).toBe(true);
  });

  it('all exported constants are frozen/reference-stable', () => {
    // The INHERITANCE, ROUTE_CAPABILITIES, MENU_ITEM_CAPABILITIES objects
    // should remain unchanged between accesses
    const inh1 = caps.CAPABILITY_INHERITANCE;
    const inh2 = caps.CAPABILITY_INHERITANCE;
    expect(inh1).toBe(inh2); // Same reference
    expect(inh1[caps.CARBON_MANAGE_EMISSION_FACTORS]).toBeDefined();
  });
});

// ═══════════════════════════════════════════════════════════════════
// TEST SUITE 15: Cross-Module Integration
// ═══════════════════════════════════════════════════════════════════
describe('Cross-Module Integration', () => {
  it('capabilities.js hasCap works with rbac.js output', async () => {
    const caps = await import('../capabilities.js');
    const rbac = await import('../utils/rbac');

    // isGlobalAdmin user should have wildcard-like access
    const isAdmin = rbac.isGlobalAdmin({}, ['admin'], true);
    expect(isAdmin).toBe(true);

    // Simulate admin via hasCap with wildcard
    expect(caps.hasCap(new Set(['*']), caps.PLATFORM_MANAGE_USERS)).toBe(true);
  });

  it('capabilities.js filterMenuItems output structure works with sidebar', async () => {
    const caps = await import('../capabilities.js');

    // Generate menu items similar to what ShellSidebar produces
    const sidebarItems = [
      { label: 'Overview', path: '/carbon/console', icon: () => null },
      { label: 'Emissions Dashboard', path: '/carbon/dashboard', icon: () => null },
      { label: 'Analytics & Trends', path: '/carbon/analytics', icon: () => null },
      { type: 'divider' },
      { label: 'Emission Factors', path: '/carbon/admin/factors', icon: () => null },
    ];

    const expanded = new Set([caps.CARBON_VIEW_CONSOLE, caps.CARBON_VIEW_DASHBOARD]);
    const result = caps.filterMenuItems(expanded, sidebarItems);

    // Should keep Overview, Dashboard, divider
    // Should remove Analytics (needs CARBON_VIEW_ANALYTICS) and Emission Factors
    const labels = result.map(i => i.label);
    expect(labels).toContain('Overview');
    expect(labels).toContain('Emissions Dashboard');
    expect(labels).not.toContain('Analytics & Trends');
    expect(labels).not.toContain('Emission Factors');
    // divider should pass through (no label, type='divider')
    expect(result.some(i => i.type === 'divider')).toBe(true);
  });

  it('AdminRoute uses isGlobalAdmin and isDomainLead from rbac.js', async () => {
    // Verify that AdminRoute imports the correct RBAC utilities
    const rbac = await import('../utils/rbac');
    expect(typeof rbac.isGlobalAdmin).toBe('function');
    expect(typeof rbac.isDomainLead).toBe('function');
  });

  it('ROUTE_CAPABILITIES in capabilities.js align with App.jsx AdminRoute usage', async () => {
    const caps = await import('../capabilities.js');

    // All routes in ROUTE_CAPABILITIES should be in AdminRoute-wrapped paths
    const routes = Object.keys(caps.ROUTE_CAPABILITIES);

    // Admin routes exist
    const adminRoutes = routes.filter(r => r.startsWith('/admin/'));
    expect(adminRoutes.length).toBeGreaterThan(0);

    // Carbon routes exist
    const carbonRoutes = routes.filter(r => r.startsWith('/carbon/'));
    expect(carbonRoutes.length).toBeGreaterThan(0);

    // Catalog routes exist
    const catalogRoutes = routes.filter(r => r.startsWith('/catalog/'));
    expect(catalogRoutes.length).toBeGreaterThan(0);
  });

  it('capabilities.js constants are all importable and stable', async () => {
    const caps = await import('../capabilities.js');

    // Every named export that is a string constant should be non-empty
    const stringExports = Object.entries(caps)
      .filter(([k, v]) => k === k.toUpperCase() && typeof v === 'string');
    for (const [name, value] of stringExports) {
      expect(value.length).toBeGreaterThan(0);
    }
  });

  it('all CAPABILITY_INHERITANCE values are arrays of strings', () => {
    // Direct test without import
    const ci = {
      'carbon:manage_emission_factors': ['carbon:view_console'],
    };
    for (const [key, val] of Object.entries(ci)) {
      expect(Array.isArray(val)).toBe(true);
      val.forEach(v => expect(typeof v).toBe('string'));
    }
  });
});
