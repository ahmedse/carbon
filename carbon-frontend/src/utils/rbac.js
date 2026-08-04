// src/utils/rbac.js
// Centralized RBAC utilities for role-based access control

import { hasCap, CARBON_VIEW_CONSOLE, CATALOG_VIEW, DQ_VIEW, MDM_VIEW,
  CONNECTIONS_VIEW, IMPORTEXPORT_VIEW, DATASCHEMA_VIEW } from '../capabilities';

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

/**
 * Check if user has admin perspective (platform admin).
 *
 * Trusts the backend's authoritative is_global_admin flag from me_context.
 * "admin" perspective is ONLY granted by the backend when is_global_admin=True.
 * Domain Leads (carbon_lead, etc.) get "{app}-admin" — NOT "admin" — so they
 * cannot access platform admin pages (Users, Groups, OrgUnits, Access Control).
 */
export function isGlobalAdmin(user, availablePerspectives = [], isGlobalAdminFlag = null) {
  // Backend-authoritative flag (from me_context.is_global_admin) — most reliable
  if (isGlobalAdminFlag === true) return true;
  if (isGlobalAdminFlag === false) return false;

  // Fallback: check perspectives (only if flag not provided)
  const perspectives = availablePerspectives || [];
  if (perspectives.includes("admin")) {
    return true;
  }

  // Fallback: check roles for bare "admin" group only
  const roles = (user?.roles || []).map((r) => r?.role).filter(Boolean).map((r) => r.toLowerCase());
  if (roles.includes("admin")) {
    return true;
  }

  return false;
}

/**
 * Check if user is a Domain Lead for a specific app.
 * Domain Leads have org-scoped administrative access to their app only.
 * They do NOT have platform admin access.
 */
export function isDomainLead(appId, availablePerspectives = []) {
  if (!appId || !availablePerspectives?.length) return false;
  const perspectives = availablePerspectives || [];
  return perspectives.includes(`${appId}-admin`);
}

/**
 * Check if user has catalog admin access
 */
export function isCatalogAdmin(user, availablePerspectives = []) {
  if (!user && !availablePerspectives?.length) return false;
  
  const perspectives = availablePerspectives || [];
  const roles = (user?.roles || []).map((r) => r?.role).filter(Boolean).map((r) => r.toLowerCase());
  
  // Catalog requires global admin or catalog-admin perspective
  if (perspectives.includes("admin") || perspectives.includes("catalog-admin")) {
    return true;
  }
  
  // Check for admin roles
  if (roles.includes("admin") || roles.includes("admins_group")) {
    return true;
  }
  
  return false;
}

/**
 * Check if user has access to a specific app/domain
 * Returns true if user has any role or module access for that app
 */
export function hasAppAccess(appId, user, context, availablePerspectives = [], userCapabilities = null) {
  if (!user || !appId) return false;

  // Global admins can access everything
  if (isGlobalAdmin(user, availablePerspectives)) {
    return true;
  }

  // CBAC: Check capabilities (most reliable — comes from backend groups)
  if (userCapabilities && userCapabilities.length > 0) {
    const caps = userCapabilities.map(c => typeof c === 'string' ? c : c.key);
    const viewCap = APP_VIEW_CAPABILITY[appId];
    if (viewCap && caps.includes(viewCap)) {
      return true;
    }
  }

  // Check if user has any modules for this app
  const modules = context?.modules || [];
  const hasModules = modules.some((m) => m.app_id === appId || m.scope === appId);
  
  if (hasModules) {
    return true;
  }
  
  // Domain Leads have {appId}-admin perspective
  if (availablePerspectives.includes(`${appId}-admin`)) {
    return true;
  }

  // Check for app-specific roles in user.roles array
  const roles = (user?.roles || []).map((r) => r?.role).filter(Boolean).map((r) => r.toLowerCase());
  const hasAppRole = roles.some((role) => {
    return role === appId || role.includes(`${appId}_`) || role.startsWith(`${appId}:`);
  });
  
  return hasAppRole;
}

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
    return isGlobalAdmin(user, availablePerspectives);
  }
  
  // Catalog routes
  if (path.startsWith('/catalog')) {
    return isCatalogAdmin(user, availablePerspectives);
  }
  
  // Carbon app routes
  if (path.startsWith('/carbon')) {
    // Global admins can access everything
    if (isGlobalAdmin(user, availablePerspectives)) return true;
    // Domain Leads can access their app's admin area
    if (path.startsWith('/carbon/admin') || path.startsWith('/carbon/calculations') || path.startsWith('/carbon/verification') || path.startsWith('/carbon/reporting') || path.startsWith('/carbon/analytics')) {
      if (isDomainLead('carbon', availablePerspectives)) return true;
    }
    // Carbon owner routes
    if (path.startsWith('/carbon/owner')) {
      return isDataOwner(user, availablePerspectives);
    }
    // General carbon routes require some carbon access
    return hasAppAccess('carbon', user, context, availablePerspectives);
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
  if (isGlobalAdmin(user, availablePerspectives)) return items;
  
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
