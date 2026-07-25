// src/utils/rbac.js
// Centralized RBAC utilities for role-based access control

/**
 * Check if user has admin perspective (platform admin)
 */
export function isGlobalAdmin(user, availablePerspectives = []) {
  if (!user && !availablePerspectives?.length) return false;
  
  const roles = (user?.roles || []).map((r) => r?.role).filter(Boolean).map((r) => r.toLowerCase());
  const perspectives = availablePerspectives || [];
  
  // Check perspectives first (most reliable)
  if (perspectives.includes("admin")) {
    return true;
  }
  
  // Check roles
  if (roles.includes("admin") || roles.includes("admins_group")) {
    return true;
  }
  
  return false;
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
export function hasAppAccess(appId, user, context, availablePerspectives = []) {
  if (!user || !appId) return false;
  
  // Global admins can access everything
  if (isGlobalAdmin(user, availablePerspectives)) {
    return true;
  }
  
  // Check if user has any modules for this app
  const modules = context?.modules || [];
  const hasModules = modules.some((m) => m.app_id === appId || m.scope === appId);
  
  if (hasModules) {
    return true;
  }
  
  // Check for app-specific roles
  const roles = (user?.roles || []).map((r) => r?.role).filter(Boolean).map((r) => r.toLowerCase());
  const hasAppRole = roles.some((role) => {
    return role.includes(appId) || role.startsWith(`${appId}_`) || role.startsWith(`${appId}:`);
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
    // Carbon owner routes
    if (path.startsWith('/carbon/owner')) {
      return isDataOwner(user, availablePerspectives);
    }
    // Carbon admin routes (emission factors, etc)
    if (path.startsWith('/carbon/admin')) {
      return isGlobalAdmin(user, availablePerspectives);
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
export function filterMenuItems(items, user, availablePerspectives = [], context = {}) {
  if (!items || !Array.isArray(items)) return [];
  
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
      return userRoles.includes(normalizedSuffix) || userRoles.includes(appPrefixedRole) || isGlobalAdmin(user, availablePerspectives);
    }
    
    return userRoles.includes(item.role) || isGlobalAdmin(user, availablePerspectives);
  });
}
