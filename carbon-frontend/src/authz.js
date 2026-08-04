// src/authz.js — Unified Authorization Gate
// =============================================================================
// THE SINGLE SOURCE OF TRUTH for all frontend access decisions.
// Every component, route guard, menu filter, and button MUST use `can()`.
// Adding a new capability? Add it to capabilities.js — nothing else changes.
//
// Pattern: can(user, action, resource, context) → boolean
//   - action:  'view' | 'manage' | 'access_route' | 'view_app'
//   - resource: app ID (e.g. 'carbon'), route path (e.g. '/carbon/calculations'),
//               or menu label (e.g. 'Calculations')
//   - context:  { perspectives, capabilities, modules, ... }
//
// Migration path:
//   Phase 2 (current):  capabilities checked first, perspectives as fallback
//   Phase 3 (future):   perspectives removed, capabilities only
// =============================================================================

import {
  // Capability constants
  PLATFORM_ADMIN,
  CARBON_VIEW_CONSOLE, CARBON_VIEW_DASHBOARD, CARBON_VIEW_ANALYTICS,
  CARBON_VIEW_MY_DATA, CARBON_ENTER_DATA,
  CARBON_VIEW_CALCULATIONS, CARBON_VIEW_VERIFICATION, CARBON_VIEW_REPORTING_PERIODS,
  CARBON_MANAGE_EMISSION_FACTORS, CARBON_MANAGE_CALCULATION_RULES,
  CARBON_MANAGE_GWP, CARBON_MANAGE_SBTI_TARGETS, CARBON_MANAGE_REPORTING_PERIODS,
  CARBON_TRIGGER_CALCULATIONS, CARBON_VERIFY_DATA, CARBON_GENERATE_REPORTS,
  CATALOG_VIEW, CATALOG_MANAGE_PRODUCTS, CATALOG_MANAGE_METADATA,
  CATALOG_MANAGE_POLICIES, CATALOG_VIEW_GOVERNANCE,
  DQ_VIEW, DQ_MANAGE_RULES,
  MDM_VIEW, MDM_MANAGE,
  CONNECTIONS_VIEW, CONNECTIONS_MANAGE,
  IMPORTEXPORT_VIEW, IMPORTEXPORT_MANAGE,
  DATASCHEMA_VIEW, DATASCHEMA_MANAGE,
  // Utility
  expandCapabilities, hasCap, hasAnyCap, hasAllCaps,
  initCapabilities, getCapableApps,
  // Route/manifest maps
  ROUTE_CAPABILITIES, MENU_ITEM_CAPABILITIES,
} from './capabilities';

// ═══════════════════════════════════════════════════════════════════
// Resource → action → required capability map
// The ONE place where "what do you need to view/manage X" is defined.
// ═══════════════════════════════════════════════════════════════════

// Which capability grants visibility to an entire domain app
const APP_VIEW_CAP = {
  carbon:      CARBON_VIEW_CONSOLE,
  catalog:     CATALOG_VIEW,
  dq:          DQ_VIEW,
  mdm:         MDM_VIEW,
  connections: CONNECTIONS_VIEW,
  importexport: IMPORTEXPORT_VIEW,
  dataschema:  DATASCHEMA_VIEW,
};

// Which capability is needed to manage an app's admin area
const APP_ADMIN_CAP = {
  carbon:      CARBON_MANAGE_EMISSION_FACTORS, // any manage cap gates admin
  catalog:     CATALOG_MANAGE_PRODUCTS,
  dq:          DQ_MANAGE_RULES,
  mdm:         MDM_MANAGE,
  connections: CONNECTIONS_MANAGE,
  importexport: IMPORTEXPORT_MANAGE,
  dataschema:  DATASCHEMA_MANAGE,
};

// Route → action → capability (auto-resolved from ROUTE_CAPABILITIES + known patterns)
const ROUTE_ACTION_CAP = {
  '/carbon/admin':        'manage',
  '/carbon/analytics':    CARBON_VIEW_ANALYTICS,
  '/carbon/calculations': CARBON_VIEW_CALCULATIONS,
  '/carbon/verification': CARBON_VIEW_VERIFICATION,
  '/carbon/reporting':    CARBON_GENERATE_REPORTS,
  '/carbon/admin/factors':    CARBON_MANAGE_EMISSION_FACTORS,
  '/carbon/admin/rules':      CARBON_MANAGE_CALCULATION_RULES,
  '/carbon/admin/gwp':        CARBON_MANAGE_GWP,
  '/carbon/admin/targets':    CARBON_MANAGE_SBTI_TARGETS,
  '/carbon/reporting/generate': CARBON_GENERATE_REPORTS,
  '/carbon/reporting/saved':    CARBON_GENERATE_REPORTS,
  '/carbon/reporting/periods':  CARBON_MANAGE_REPORTING_PERIODS,
  // Catalog
  '/catalog':              CATALOG_VIEW,
  '/catalog/products':     CATALOG_MANAGE_PRODUCTS,
  '/catalog/metadata':     CATALOG_MANAGE_METADATA,
  '/catalog/policies':     CATALOG_MANAGE_POLICIES,
  '/catalog/governance':   CATALOG_VIEW_GOVERNANCE,
  // DQ
  '/dq':                   DQ_VIEW,
  '/dq/rules':             DQ_MANAGE_RULES,
  // MDM
  '/mdm':                  MDM_VIEW,
  '/mdm/manage':           MDM_MANAGE,
  // Connections
  '/connections':          CONNECTIONS_VIEW,
  '/connections/manage':   CONNECTIONS_MANAGE,
  // Import/Export
  '/importexport':         IMPORTEXPORT_VIEW,
  '/importexport/manage':  IMPORTEXPORT_MANAGE,
  // Dataschema
  '/dataschema':           DATASCHEMA_VIEW,
  '/dataschema/manage':    DATASCHEMA_MANAGE,
};

// ═══════════════════════════════════════════════════════════════════
// THE ONE FUNCTION — can(user, action, resource, context) → boolean
// ═══════════════════════════════════════════════════════════════════

/**
 * Unified authorization check. Every access decision must go through here.
 *
 * @param {object|null} user — user object from AuthContext
 * @param {string} action — 'view_app' | 'view_page' | 'manage' | 'access_route' | 'view_menu'
 * @param {string} resource — app ID, route path, or menu label
 * @param {object} ctx — { perspectives: [], capabilities: [], modules: [], ... }
 * @returns {boolean}
 */
export function can(user, action, resource, ctx = {}) {
  if (!user) return false;

  const {
    perspectives = [],
    isGlobalAdminFlag = null,
    capabilities = null,
    modules = [],
  } = ctx;

  // ── Global admin bypass ──────────────────────────────────────
  if (isGlobalAdmin__(user, perspectives, isGlobalAdminFlag)) {
    return true;
  }

  // ── Capability-based check (authoritative) ────────────────────
  const capResult = checkCapabilities(action, resource, capabilities);
  if (capResult !== null) return capResult;

  // ── Legacy perspective falls back (during migration) ──────────
  return checkLegacy(action, resource, perspectives, modules);
}

// ═══════════════════════════════════════════════════════════════════
// Internal: capability check
// ═══════════════════════════════════════════════════════════════════

function checkCapabilities(action, resource, rawCapabilities) {
  if (!rawCapabilities || rawCapabilities.length === 0) return null; // no caps → fall through

  const keys = rawCapabilities.map(c => typeof c === 'string' ? c : (c?.key || c?.capability));
  const expanded = expandCapabilities(keys);

  switch (action) {
    case 'view_app': {
      const viewCap = APP_VIEW_CAP[resource];
      return viewCap ? hasCap(expanded, viewCap) : null;
    }

    case 'view_page': {
      // Check specific route capability first
      const routeCap = ROUTE_ACTION_CAP[resource];
      if (routeCap) return hasCap(expanded, routeCap);
      // Check from ROUTE_CAPABILITIES map
      const fromMap = ROUTE_CAPABILITIES[resource];
      if (fromMap) return hasCap(expanded, fromMap);
      // Try prefix match
      for (const [pattern, cap] of Object.entries(ROUTE_CAPABILITIES)) {
        if (resource.startsWith(pattern) && hasCap(expanded, cap)) return true;
      }
      return null; // no capability requirement → fall through
    }

    case 'access_route': {
      // Exact or prefix match from ROUTE_CAPABILITIES
      const exact = ROUTE_CAPABILITIES[resource];
      if (exact) return hasCap(expanded, exact);
      for (const [pattern, cap] of Object.entries(ROUTE_CAPABILITIES)) {
        if (resource.startsWith(pattern) && hasCap(expanded, cap)) return true;
      }
      return null;
    }

    case 'manage': {
      const adminCap = APP_ADMIN_CAP[resource];
      if (adminCap) return hasCap(expanded, adminCap);
      const viewCap = APP_VIEW_CAP[resource];
      if (viewCap) return hasCap(expanded, viewCap);
      return null;
    }

    case 'view_menu': {
      const menuCap = MENU_ITEM_CAPABILITIES[resource];
      if (menuCap) return hasCap(expanded, menuCap);
      return null;
    }

    default:
      return null;
  }
}

// ═══════════════════════════════════════════════════════════════════
// Internal: legacy perspective/mode fallback
// ═══════════════════════════════════════════════════════════════════

function checkLegacy(action, resource, perspectives, modules) {
  switch (action) {
    case 'view_app': {
      // Domain lead perspective: {app}-admin
      if (perspectives.includes(`${resource}-admin`)) return true;
      // Module-based: user has modules for this app
      if (modules.some(m => m.app_id === resource || m.scope === resource)) return true;
      return false;
    }

    case 'view_page':
    case 'access_route': {
      // Platform admin routes
      if (resource.startsWith('/admin')) {
        return perspectives.includes('admin');
      }
      // Catalog routes
      if (resource.startsWith('/catalog')) {
        return perspectives.includes('admin') || perspectives.includes('catalog-admin');
      }
      // Carbon admin routes — domain lead can access
      if (resource.startsWith('/carbon/admin') ||
          resource.startsWith('/carbon/calculations') ||
          resource.startsWith('/carbon/verification') ||
          resource.startsWith('/carbon/reporting') ||
          resource.startsWith('/carbon/analytics')) {
        if (perspectives.includes('carbon-admin')) return true;
      }
      // General carbon access
      if (resource.startsWith('/carbon')) {
        return perspectives.includes('carbon-admin') ||
               modules.some(m => m.app_id === 'carbon' || m.scope === 'carbon');
      }
      return true; // ungate unknown routes
    }

    case 'manage':
      return perspectives.includes(`${resource}-admin`);

    case 'view_menu':
      return true; // let it through — capability check already returned null

    default:
      return true;
  }
}

// ═══════════════════════════════════════════════════════════════════
// Global admin check (used by can() internally, also exported for use)
// ═══════════════════════════════════════════════════════════════════

function isGlobalAdmin__(user, perspectives, isGlobalAdminFlag) {
  // Backend-authoritative flag (from me_context) — most reliable
  if (isGlobalAdminFlag === true) return true;
  if (isGlobalAdminFlag === false) return false;

  // Fallback: check perspectives
  if (perspectives.includes('admin')) return true;

  // Fallback: role-based
  const roles = (user?.roles || []).map(r => r?.role).filter(Boolean).map(r => r.toLowerCase());
  if (roles.includes('admin')) return true;

  return false;
}

// ═══════════════════════════════════════════════════════════════════
// Exported convenience predicates (thin wrappers around can())
// Components import from here, not from rbac.js
// ═══════════════════════════════════════════════════════════════════

/**
 * Is this user a platform-level admin?
 */
export function isGlobalAdmin(user, perspectives = [], isGlobalAdminFlag = null) {
  return isGlobalAdmin__(user, perspectives, isGlobalAdminFlag);
}

/**
 * Is this user a Domain Lead for a specific app?
 */
export function isDomainLead(appId, perspectives = []) {
  return perspectives.includes(`${appId}-admin`);
}

/**
 * Does this user have catalog admin access?
 */
export function isCatalogAdmin(user, ctx = {}) {
  return can(user, 'manage', 'catalog', ctx) ||
         can(user, 'view_page', '/catalog', ctx);
}

/**
 * Does this user have access to this app (visible on Platform Home)?
 */
export function hasAppAccess(appId, user, ctx = {}) {
  return can(user, 'view_app', appId, ctx);
}

/**
 * Can this user access this route/page?
 */
export function canAccessRoute(path, user, ctx = {}) {
  return can(user, 'access_route', path, ctx);
}

/**
 * Re-export capability utilities
 */
export { expandCapabilities, hasCap, hasAnyCap, hasAllCaps, initCapabilities, getCapableApps };
export { ROUTE_CAPABILITIES, MENU_ITEM_CAPABILITIES, APP_VIEW_CAP as _APP_VIEW_CAP };
