// src/apps/people/useCompensationAccess.js
// Progressive-disclosure guard for compensation (Tier-2 sensitivity).
// A user may view compensation only when they hold `people:view_compensation`
// (implied by `people:manage`) or are a global admin.

import { useAuth } from '../../auth/AuthContext';
import { PEOPLE_VIEW_COMPENSATION } from '../../capabilities';

export function useCompensationAccess() {
  const { isGlobalAdminFlag, userCapabilities } = useAuth();
  const caps = Array.isArray(userCapabilities) ? userCapabilities : [];
  const canViewCompensation =
    isGlobalAdminFlag === true || caps.includes(PEOPLE_VIEW_COMPENSATION);
  return { canViewCompensation, isGlobalAdmin: isGlobalAdminFlag === true };
}
