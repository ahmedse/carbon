// ⚠️ FULLY DEPRECATED — use ../authz.js and ../capabilities.js instead.
// This file is retained ONLY for backward-compatible re-exports.
// All new code MUST import directly from authz.js or capabilities.js.
// No imports remain of filterMenuItems or canAccessRoute from this file as of Phase 4.
// src/utils/rbac.js

import { CARBON_VIEW_CONSOLE, CATALOG_VIEW, DQ_VIEW, MDM_VIEW,
  CONNECTIONS_VIEW, IMPORTEXPORT_VIEW, DATASCHEMA_VIEW } from '../capabilities';

// Re-export from authz.js for consumers that still import from here
import {
  isGlobalAdmin as _isGlobalAdmin,
  isDomainLead as _isDomainLead,
  isCatalogAdmin as _isCatalogAdmin,
  hasAppAccess as _hasAppAccess,
} from '../authz';

// Domain view capability lookup — which capability gates each app's visibility
const APP_VIEW_CAPABILITY = {
  carbon: CARBON_VIEW_CONSOLE,
  catalog: CATALOG_VIEW,
  dq: DQ_VIEW,
  mdm: MDM_VIEW,
  connections: CONNECTIONS_VIEW,
  importexport: IMPORTEXPORT_VIEW,
  dataschema: DATASCHEMA_VIEW,
};

// ═══════════════════════════════════════════════════════════════
// ⚠️ isGlobalAdmin — migrated to authz.js. Re-exported below.
// Original implementation commented out for reference:
// ═══════════════════════════════════════════════════════════════
// export function isGlobalAdmin(user, availablePerspectives = [], isGlobalAdminFlag = null) {
//   if (isGlobalAdminFlag === true) return true;
//   if (isGlobalAdminFlag === false) return false;
//   const perspectives = availablePerspectives || [];
//   if (perspectives.includes("admin")) return true;
//   const roles = (user?.roles || []).map((r) => r?.role).filter(Boolean).map((r) => r.toLowerCase());
//   if (roles.includes("admin")) return true;
//   return false;
// }

// ═══════════════════════════════════════════════════════════════
// ⚠️ isDomainLead — migrated to authz.js. Re-exported below.
// ═══════════════════════════════════════════════════════════════
// export function isDomainLead(appId, availablePerspectives = []) {
//   if (!appId || !availablePerspectives?.length) return false;
//   const perspectives = availablePerspectives || [];
//   return perspectives.includes(`${appId}-admin`);
// }

// ═══════════════════════════════════════════════════════════════
// ⚠️ isCatalogAdmin — migrated to authz.js. Re-exported below.
// ═══════════════════════════════════════════════════════════════
// export function isCatalogAdmin(user, availablePerspectives = []) {
//   if (!user && !availablePerspectives?.length) return false;
//   const perspectives = availablePerspectives || [];
//   const roles = (user?.roles || []).map((r) => r?.role).filter(Boolean).map((r) => r.toLowerCase());
//   if (perspectives.includes("admin") || perspectives.includes("catalog-admin")) return true;
//   if (roles.includes("admin") || roles.includes("admins_group")) return true;
//   return false;
// }

// ═══════════════════════════════════════════════════════════════
// ⚠️ hasAppAccess — migrated to authz.js. Re-exported below.
// ═══════════════════════════════════════════════════════════════
// export function hasAppAccess(appId, user, context, availablePerspectives = [], userCapabilities = null) {
//   if (!user || !appId) return false;
//   if (isGlobalAdmin(user, availablePerspectives)) return true;
//   if (userCapabilities && userCapabilities.length > 0) {
//     const caps = userCapabilities.map(c => typeof c === 'string' ? c : c.key);
//     const viewCap = APP_VIEW_CAPABILITY[appId];
//     if (viewCap && caps.includes(viewCap)) return true;
//   }
//   const modules = context?.modules || [];
//   if (modules.some((m) => m.app_id === appId || m.scope === appId)) return true;
//   if (availablePerspectives.includes(`${appId}-admin`)) return true;
//   const roles = (user?.roles || []).map((r) => r?.role).filter(Boolean).map((r) => r.toLowerCase());
//   return roles.some((role) => role === appId || role.includes(`${appId}_`) || role.startsWith(`${appId}:`));
// }

/**
 * Check if user has data entry perspective
 */
export function isDataEntry(user, availablePerspectives = []) {
  if (!user && !availablePerspectives?.length) return false;
  
  const perspectives = availablePerspectives || [];
  return perspectives.includes("data_entry") || perspectives.includes("data-entry");
}

/**
 * Check if user has analyst perspective
 */
export function isAnalyst(user, availablePerspectives = []) {
  if (!user && !availablePerspectives?.length) return false;
  
  const perspectives = availablePerspectives || [];
  return perspectives.includes("analyst") || perspectives.includes("carbon-analyst");
}

/**
 * Check if user has data owner perspective
 */
export function isDataOwner(user, availablePerspectives = []) {
  if (!user && !availablePerspectives?.length) return false;
  
  const perspectives = availablePerspectives || [];
  return perspectives.includes("data-owner") || perspectives.includes("data_owner");
}

/**
 * Check if user can access a specific route/page
 * @param {string} path - The route path
 * @param {object} user - User object
 * @param {array} availablePerspectives - User's available perspectives
 * @param {object} context - User context with modules
 * @returns {boolean}
 */
export function canAccessRoute(path, user, availablePerspectives = [], context = {}) {
  if (!user) return false;
  
  // Admin routes
  if (path.startsWith('/admin')) {
    return _isGlobalAdmin(user, availablePerspectives);
  }
  
  // Catalog routes
  if (path.startsWith('/catalog')) {
    return _isCatalogAdmin(user, { perspectives: availablePerspectives });
  }
  
  // Carbon app routes
  if (path.startsWith('/carbon')) {
    // Global admins can access everything
    if (_isGlobalAdmin(user, availablePerspectives)) return true;
    // Domain Leads can access their app's admin area
    if (path.startsWith('/carbon/admin') || path.startsWith('/carbon/calculations') || path.startsWith('/carbon/verification') || path.startsWith('/carbon/reporting') || path.startsWith('/carbon/analytics')) {
      if (_isDomainLead('carbon', availablePerspectives)) return true;
    }
    // Carbon owner routes
    if (path.startsWith('/carbon/owner')) {
      return isDataOwner(user, availablePerspectives);
    }
    // General carbon routes require some carbon access
    return _hasAppAccess('carbon', user, { perspectives: availablePerspectives, modules: context?.modules });
  }
  
  // Module routes
  if (path.startsWith('/modules/')) {
    const modules = context?.modules || [];
    return modules.length > 0;
  }
  
  // Default: allow if authenticated
  return true;
}

/**
 * Filter menu items based on user permissions
 */
export function filterMenuItems(items, user, availablePerspectives = []) {
  if (!items || !Array.isArray(items)) return [];
  
  // Global admins see everything
  if (_isGlobalAdmin(user, availablePerspectives)) return items;
  
  return items.filter((item) => {
    // Always show items without role restriction
    if (!item.role || item.role === '*') return true;
    
    // Show dividers and groups always
    if (item.type === 'divider' || item.type === 'group') return true;
    
    // Check role-based access
    const userRoles = availablePerspectives || [];
    
    // Match full role format (carbon:data_owner) or short format (data-owner)
    if (item.role.includes(':')) {
      const [appPrefix, roleSuffix] = item.role.split(':');
      const normalizedSuffix = roleSuffix.replace(/_/g, '-');
      const appPrefixedRole = `${appPrefix}-${normalizedSuffix}`;
      return userRoles.includes(normalizedSuffix) || userRoles.includes(appPrefixedRole);
    }
    
    return userRoles.includes(item.role);
  });
}

// ═══════════════════════════════════════════════════════════════
// Re-exports from authz.js for backward compatibility
// ═══════════════════════════════════════════════════════════════
// Backward-compatible wrappers — bridge old call signatures to authz.js
// ================================================================
// isGlobalAdmin:  old (user, availablePerspectives, isGlobalAdminFlag)
//                 new (user, perspectives, isGlobalAdminFlag) — same
// isDomainLead:   old (appId, availablePerspectives) — same as new
// isCatalogAdmin: old (user, availablePerspectives)
//                 new (user, ctx) where ctx = { perspectives, capabilities }
// hasAppAccess:   old (appId, user, context, availablePerspectives, userCapabilities)
//                 new (appId, user, ctx) where ctx = { perspectives, capabilities, modules }
// ═══════════════════════════════════════════════════════════════

export function isGlobalAdmin(user, availablePerspectives = [], isGlobalAdminFlag = null) {
  // Normalize null to [] for backward compat
  const perspectives = availablePerspectives || [];
  return _isGlobalAdmin(user, perspectives, isGlobalAdminFlag);
}

export function isDomainLead(appId, availablePerspectives = []) {
  // Normalize null to [] for backward compat
  const perspectives = availablePerspectives || [];
  return _isDomainLead(appId, perspectives);
}

export function isCatalogAdmin(user, availablePerspectives = []) {
  // Bridge old (user, perspectives[]) to new (user, ctx)
  return _isCatalogAdmin(user, { perspectives: availablePerspectives || [] });
}

export function hasAppAccess(appId, user, context, availablePerspectives = [], userCapabilities = null) {
  // Bridge old 5-arg call to new (appId, user, ctx)
  return _hasAppAccess(appId, user, {
    perspectives: availablePerspectives || [],
    capabilities: userCapabilities,
    modules: context?.modules || [],
  });
}
