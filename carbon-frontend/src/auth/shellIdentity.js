// Shell identity helpers — person-first display for the header menu.
// displayName = employee.full_name || user.full_name || user.username

/**
 * Resolve the human-facing name for the shell chip/menu.
 * @param {{ full_name?: string, username?: string } | null | undefined} user
 * @param {{ full_name?: string } | null | undefined} employee
 */
export function resolveDisplayName(user, employee) {
  const fromEmployee = (employee?.full_name || '').trim();
  if (fromEmployee) return fromEmployee;
  const fromUser = (user?.full_name || '').trim();
  if (fromUser && fromUser !== user?.username) return fromUser;
  if (fromUser) return fromUser;
  return (user?.username || '').trim() || '—';
}

/**
 * Initials from a display name (word starts), falling back to first two chars.
 * @param {string} displayName
 */
export function resolveInitials(displayName) {
  const parts = String(displayName || '')
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }
  if (parts.length === 1 && parts[0].length >= 2) {
    return parts[0].slice(0, 2).toUpperCase();
  }
  if (parts.length === 1) {
    return parts[0].slice(0, 1).toUpperCase() || 'U';
  }
  return 'U';
}
