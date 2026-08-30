// src/capabilities.js
// Capability-Based Access Control (CBAC) — Frontend Mirror
//
// THIS IS THE SINGLE SOURCE OF TRUTH for all frontend permission checks.
// Every menu item, route, button, and action MUST use these capabilities.
// Adding a new app? Add its capabilities here. No other file changes needed.
//
// Mirrors: backend/accounts/capabilities.py
// Synced via: me_context → capabilities[] field

// ── Platform ───────────────────────────────────────────────────────
export const PLATFORM_ADMIN          = 'platform:admin';
export const PLATFORM_MANAGE_USERS   = 'platform:manage_users';
export const PLATFORM_MANAGE_GROUPS  = 'platform:manage_groups';
export const PLATFORM_MANAGE_ORG_UNITS = 'platform:manage_org_units';
export const PLATFORM_MANAGE_ACCESS  = 'platform:manage_access';
export const PLATFORM_VIEW_AUDIT     = 'platform:view_audit';
export const PLATFORM_MANAGE_APPS    = 'platform:manage_apps';

// ── Carbon ─────────────────────────────────────────────────────────
export const CARBON_VIEW_CONSOLE            = 'carbon:view_console';
export const CARBON_VIEW_DASHBOARD          = 'carbon:view_dashboard';
export const CARBON_VIEW_ANALYTICS          = 'carbon:view_analytics';
export const CARBON_ENTER_DATA              = 'carbon:enter_data';
export const CARBON_VIEW_MY_DATA            = 'carbon:view_my_data';
export const CARBON_MANAGE_EMISSION_FACTORS = 'carbon:manage_emission_factors';
export const CARBON_MANAGE_CALCULATION_RULES = 'carbon:manage_calculation_rules';
export const CARBON_MANAGE_GWP              = 'carbon:manage_gwp';
export const CARBON_MANAGE_SBTI_TARGETS     = 'carbon:manage_sbti_targets';
export const CARBON_MANAGE_REPORTING_PERIODS = 'carbon:manage_reporting_periods';
export const CARBON_MANAGE_INVENTORY_COVERAGE = 'carbon:manage_inventory_coverage';
export const CARBON_TRIGGER_CALCULATIONS    = 'carbon:trigger_calculations';
export const CARBON_VERIFY_DATA             = 'carbon:verify_data';
export const CARBON_GENERATE_REPORTS        = 'carbon:generate_reports';
export const CARBON_VIEW_CALCULATIONS       = 'carbon:view_calculations';
export const CARBON_VIEW_VERIFICATION       = 'carbon:view_verification';
export const CARBON_VIEW_REPORTING_PERIODS  = 'carbon:view_reporting_periods';

// ── People ────────────────────────────────────────────────────────
export const PEOPLE_VIEW   = 'people:view';
export const PEOPLE_MANAGE = 'people:manage';

// ── Catalog ────────────────────────────────────────────────────────
export const CATALOG_VIEW              = 'catalog:view';
export const CATALOG_MANAGE_PRODUCTS   = 'catalog:manage_products';
export const CATALOG_MANAGE_METADATA   = 'catalog:manage_metadata';
export const CATALOG_MANAGE_POLICIES   = 'catalog:manage_policies';
export const CATALOG_VIEW_GOVERNANCE   = 'catalog:view_governance';

// ── DQ ─────────────────────────────────────────────────────────────
export const DQ_VIEW         = 'dq:view';
export const DQ_MANAGE_RULES = 'dq:manage_rules';

// ── MDM ────────────────────────────────────────────────────────────
export const MDM_VIEW   = 'mdm:view';
export const MDM_MANAGE = 'mdm:manage';

// ── Connections ────────────────────────────────────────────────────
export const CONNECTIONS_VIEW   = 'connections:view';
export const CONNECTIONS_MANAGE = 'connections:manage';

// ── Import/Export ──────────────────────────────────────────────────
export const IMPORTEXPORT_VIEW   = 'importexport:view';
export const IMPORTEXPORT_MANAGE = 'importexport:manage';

// ── Dataschema ─────────────────────────────────────────────────────
export const DATASCHEMA_VIEW   = 'dataschema:view';
export const DATASCHEMA_MANAGE = 'dataschema:manage';

// ── Evidence ───────────────────────────────────────────────────────
export const EVIDENCE_VIEW   = 'evidence:view';
export const EVIDENCE_MANAGE = 'evidence:manage';

// ── AI (Pulse) ─────────────────────────────────────────────────────
export const AI_VIEW_CONSOLE   = 'ai:view_console';
export const AI_MANAGE_CONSOLE = 'ai:manage_console';

// ── Manifest role → capability mapping ─────────────────────────────
// Maps manifest role keys (carbon:data_owner) to capability keys.
// Used by filterMenuItems and canAccessRoute for backward compatibility.
export const MANIFEST_ROLE_TO_CAPABILITY = {
  'carbon:data_owner': [CARBON_VIEW_CONSOLE, CARBON_VIEW_DASHBOARD, CARBON_VIEW_MY_DATA, CARBON_ENTER_DATA, CARBON_VIEW_CALCULATIONS, CARBON_VIEW_VERIFICATION],
  'carbon:analyst':    [CARBON_VIEW_CONSOLE, CARBON_VIEW_DASHBOARD, CARBON_VIEW_ANALYTICS, CARBON_VIEW_MY_DATA, CARBON_VIEW_CALCULATIONS, CARBON_VIEW_VERIFICATION, CARBON_VIEW_REPORTING_PERIODS, CARBON_GENERATE_REPORTS],
  'carbon:admin':      [CARBON_MANAGE_EMISSION_FACTORS, CARBON_MANAGE_CALCULATION_RULES, CARBON_MANAGE_GWP, CARBON_MANAGE_SBTI_TARGETS, CARBON_MANAGE_REPORTING_PERIODS, CARBON_MANAGE_INVENTORY_COVERAGE, CARBON_TRIGGER_CALCULATIONS, CARBON_VERIFY_DATA],
};

// ── Route → required capability mapping ────────────────────────────
// Used by AdminRoute and canAccessRoute for declarative route gating.
export const ROUTE_CAPABILITIES = {
  // Platform
  '/admin/users':        PLATFORM_MANAGE_USERS,
  '/admin/groups':       PLATFORM_MANAGE_GROUPS,
  '/admin/org-units':    PLATFORM_MANAGE_ORG_UNITS,
  '/admin/access':       PLATFORM_MANAGE_ACCESS,
  '/admin/audit':        PLATFORM_VIEW_AUDIT,
  '/admin/apps':         PLATFORM_MANAGE_APPS,
  '/admin/catalog/field-policies': DATASCHEMA_MANAGE,

  // Carbon — admin
  '/carbon/admin/factors':    CARBON_MANAGE_EMISSION_FACTORS,
  '/carbon/admin/rules':      CARBON_MANAGE_CALCULATION_RULES,
  '/carbon/admin/gwp':        CARBON_MANAGE_GWP,
  '/carbon/admin/targets':    CARBON_MANAGE_SBTI_TARGETS,
  '/carbon/admin/boundaries': CARBON_MANAGE_REPORTING_PERIODS,
  '/carbon/admin/base-years': CARBON_MANAGE_REPORTING_PERIODS,
  '/carbon/admin/inventory-coverage': CARBON_MANAGE_INVENTORY_COVERAGE,

  // Carbon — reporting
  '/carbon/reporting':          CARBON_GENERATE_REPORTS,
  '/carbon/reporting/generate': CARBON_GENERATE_REPORTS,
  '/carbon/reporting/saved':    CARBON_GENERATE_REPORTS,
  '/carbon/reporting/periods':  CARBON_MANAGE_REPORTING_PERIODS,

  // Carbon — data
  '/carbon/calculations':  CARBON_VIEW_CALCULATIONS,
  '/carbon/verification':  CARBON_VIEW_VERIFICATION,
  '/carbon/analytics':     CARBON_VIEW_ANALYTICS,

  // Catalog
  '/catalog/products':    CATALOG_MANAGE_PRODUCTS,
  '/catalog/metadata':    CATALOG_MANAGE_METADATA,
  '/catalog/policies':    CATALOG_MANAGE_POLICIES,
  '/catalog/governance':  CATALOG_VIEW_GOVERNANCE,

  // AI (Pulse) admin console — prefix-matched for every /admin/ai/* route
  '/admin/ai':            AI_VIEW_CONSOLE,
};

// ── Menu item manifest role → capability ───────────────────────────
// Used by filterMenuItems to check if user can see a menu item.
export const MENU_ITEM_CAPABILITIES = {
  // Carbon — overview
  'Overview':             CARBON_VIEW_CONSOLE,
  'Emissions Dashboard':  CARBON_VIEW_DASHBOARD,
  'Analytics & Trends':   CARBON_VIEW_ANALYTICS,

  // Carbon — my data
  'Data Entry':           CARBON_VIEW_MY_DATA,
  'Calculations':         CARBON_VIEW_CALCULATIONS,
  'Verification':         CARBON_VIEW_VERIFICATION,

  // Carbon — reporting
  'Reports':              CARBON_GENERATE_REPORTS,
  'Generate Report':      CARBON_GENERATE_REPORTS,
  'Saved Reports':        CARBON_GENERATE_REPORTS,
  'Reporting Periods':    CARBON_MANAGE_REPORTING_PERIODS,

  // Carbon — configuration
  'Emission Factors':     CARBON_MANAGE_EMISSION_FACTORS,
  'Calculation Rules':    CARBON_MANAGE_CALCULATION_RULES,
  'GWP Reference':        CARBON_MANAGE_GWP,
  'SBTi Targets':         CARBON_MANAGE_SBTI_TARGETS,
  'Organizational Boundaries': CARBON_MANAGE_REPORTING_PERIODS,
  'Base Years':               CARBON_MANAGE_REPORTING_PERIODS,
  'Inventory Coverage':       CARBON_MANAGE_INVENTORY_COVERAGE,
};

// ═══════════════════════════════════════════════════════════════════
// CAPABILITY INHERITANCE (mirrors backend IMPLIES)
// ═══════════════════════════════════════════════════════════════════
//
// When a user has capability X, they automatically also have all
// capabilities listed here. This eliminates redundant checks.
//
// Rule: admin capabilities imply their view counterparts.
// Example: carbon:manage_emission_factors → carbon:view_console

export const CAPABILITY_INHERITANCE = {
  [PLATFORM_ADMIN]: [PLATFORM_MANAGE_USERS, PLATFORM_MANAGE_GROUPS, PLATFORM_MANAGE_ORG_UNITS, PLATFORM_MANAGE_ACCESS, PLATFORM_VIEW_AUDIT, PLATFORM_MANAGE_APPS],

  [CARBON_MANAGE_EMISSION_FACTORS]: [CARBON_VIEW_CONSOLE],
  [CARBON_MANAGE_CALCULATION_RULES]: [CARBON_VIEW_CONSOLE],
  [CARBON_MANAGE_GWP]: [CARBON_VIEW_CONSOLE],
  [CARBON_MANAGE_SBTI_TARGETS]: [CARBON_VIEW_CONSOLE],
  [CARBON_MANAGE_INVENTORY_COVERAGE]: [CARBON_VIEW_CONSOLE],
  [CARBON_MANAGE_REPORTING_PERIODS]: [CARBON_VIEW_REPORTING_PERIODS, CARBON_VIEW_CONSOLE],
  [CARBON_TRIGGER_CALCULATIONS]: [CARBON_VIEW_CALCULATIONS, CARBON_VIEW_CONSOLE],
  [CARBON_VERIFY_DATA]: [CARBON_VIEW_VERIFICATION, CARBON_VIEW_CONSOLE],

  [CARBON_ENTER_DATA]: [CARBON_VIEW_MY_DATA, CARBON_VIEW_CONSOLE],

  [CARBON_GENERATE_REPORTS]: [CARBON_VIEW_CONSOLE, CARBON_VIEW_DASHBOARD],
  [CARBON_VIEW_ANALYTICS]: [CARBON_VIEW_CONSOLE, CARBON_VIEW_DASHBOARD],

  [CATALOG_MANAGE_PRODUCTS]: [CATALOG_VIEW],
  [CATALOG_MANAGE_METADATA]: [CATALOG_VIEW],
  [CATALOG_MANAGE_POLICIES]: [CATALOG_VIEW, CATALOG_VIEW_GOVERNANCE],

  [DQ_MANAGE_RULES]: [DQ_VIEW],
  [MDM_MANAGE]: [MDM_VIEW],
  [CONNECTIONS_MANAGE]: [CONNECTIONS_VIEW],
  [IMPORTEXPORT_MANAGE]: [IMPORTEXPORT_VIEW],
  [DATASCHEMA_MANAGE]: [DATASCHEMA_VIEW],
  [EVIDENCE_MANAGE]: [EVIDENCE_VIEW],
  [AI_MANAGE_CONSOLE]: [AI_VIEW_CONSOLE],
  [PEOPLE_MANAGE]: [PEOPLE_VIEW],
};


// ═══════════════════════════════════════════════════════════════════
// CORE UTILITY FUNCTIONS
// ═══════════════════════════════════════════════════════════════════

/**
 * Expand a set of capability keys to include all implied capabilities.
 * Uses transitive closure: if A→B and B→C, then A→C too.
 */
export function expandCapabilities(caps) {
  const result = new Set(caps);
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
}

/**
 * Check if a user's capability set grants a specific capability.
 * @param {Set<string>|string[]} userCaps - user's capability keys (already expanded)
 * @param {string} cap - capability key to check
 * @returns {boolean}
 */
export function hasCap(userCaps, cap) {
  const caps = userCaps instanceof Set ? userCaps : new Set(userCaps);
  return caps.has('*') || caps.has(cap);
}

/**
 * Check if a user's capability set grants ANY of the given capabilities.
 */
export function hasAnyCap(userCaps, requestedCaps) {
  const caps = userCaps instanceof Set ? userCaps : new Set(userCaps);
  if (caps.has('*')) return true;
  return requestedCaps.some(c => caps.has(c));
}

/**
 * Check if a user's capability set grants ALL of the given capabilities.
 */
export function hasAllCaps(userCaps, requestedCaps) {
  const caps = userCaps instanceof Set ? userCaps : new Set(userCaps);
  if (caps.has('*')) return true;
  return requestedCaps.every(c => caps.has(c));
}

/**
 * Initialize the capability set from the me_context response.
 * Meant to be called once after login/refresh, storing the expanded set.
 *
 * @param {Array} capabilitiesFromApi - the `capabilities` array from me_context
 * @returns {{caps: Set<string>, expanded: Set<string>}}
 */
export function initCapabilities(capabilitiesFromApi) {
  const keys = (capabilitiesFromApi || []).map(c => c.key);
  const caps = new Set(keys);
  const expanded = expandCapabilities(caps);
  return { caps, expanded };
}

/**
 * Check if a user can access a route given their expanded capabilities.
 * @param {Set<string>} expandedCaps
 * @param {string} path - URL path
 * @returns {boolean}
 */
export function canAccessRoute(expandedCaps, path) {
  // Exact match first
  const required = ROUTE_CAPABILITIES[path];
  if (required) {
    return hasCap(expandedCaps, required);
  }
  // Prefix match (e.g. /carbon/admin/* matches /carbon/admin/factors)
  for (const [routePattern, cap] of Object.entries(ROUTE_CAPABILITIES)) {
    if (routePattern.endsWith('/*')) {
      const prefix = routePattern.slice(0, -2);
      if (path.startsWith(prefix) && hasCap(expandedCaps, cap)) {
        return true;
      }
    }
  }
  // No capability requirement → default to allowing access
  return true;
}

/**
 * Filter sidebar menu items based on user's capabilities.
 * Strips items the user lacks the required capability for.
 *
 * @param {Set<string>} expandedCaps
 * @param {Array} items - array of {label, path, capability, children?} objects
 * @returns {Array} filtered items (children also filtered)
 */
export function filterMenuItems(expandedCaps, items) {
  if (!items || !Array.isArray(items)) return [];
  return items
    .map(item => {
      // Check this item's capability
      const required = item.capability || MENU_ITEM_CAPABILITIES[item.label];
      if (required && !hasCap(expandedCaps, required)) return null;

      // Filter children
      if (item.children) {
        const filteredChildren = filterMenuItems(expandedCaps, item.children);
        if (filteredChildren.length === 0 && required) return null;
        return { ...item, children: filteredChildren };
      }
      return item;
    })
    .filter(Boolean);
}

/**
 * Get list of app IDs the user has access to, based on capabilities.
 * @param {Set<string>} expandedCaps
 * @returns {string[]} e.g. ['carbon', 'catalog', 'dq', 'mdm']
 */
export function getCapableApps(expandedCaps) {
  const apps = [];
  if (hasCap(expandedCaps, CARBON_VIEW_CONSOLE)) apps.push('carbon');
  if (hasCap(expandedCaps, CATALOG_VIEW)) apps.push('catalog');
  if (hasCap(expandedCaps, DQ_VIEW)) apps.push('dq');
  if (hasCap(expandedCaps, MDM_VIEW)) apps.push('mdm');
  return apps;
}
