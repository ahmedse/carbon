// src/utils/navigation.js
// Safe internal-route validation for AI-driven navigate actions.
// The engine may suggest routes (e.g. /dq/rules/{id}) in message metadata;
// the UI must only follow routes that cannot escape the SPA.

/**
 * Validate that a route string is a safe in-app path.
 * Rules:
 *  - must be a string starting with "/" but not "//" (protocol-relative)
 *  - must not contain a scheme (":" + "//"), backslashes, ".." traversal
 *  - only allow a conservative character set (alnum, - _ . ~ / ? & = # + %)
 *
 * @param {unknown} route
 * @returns {boolean}
 */
export function isSafeInternalRoute(route) {
  if (typeof route !== 'string' || !route.startsWith('/')) return false;
  // Reject protocol-relative ("//host"), scheme injection ("https://"),
  // backslashes, and parent-directory traversal.
  if (route.startsWith('//') || route.includes('://') || route.includes('\\') || route.includes('..')) return false;
  // eslint-disable-next-line no-useless-escape
  return /^[\/A-Za-z0-9\-_~\.\?\=&\+#%]*$/.test(route);
}
