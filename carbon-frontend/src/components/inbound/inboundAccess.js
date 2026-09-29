import { expandCapabilities, hasCap, INBOUND_COMMIT, INBOUND_PREPARE } from '../../capabilities';

export function capKeys(userCapabilities) {
  return (userCapabilities || [])
    .map((c) => (typeof c === 'string' ? c : (c?.key || c?.capability)))
    .filter(Boolean);
}

export function inboundCaps(userCapabilities, isGlobalAdminFlag) {
  const caps = expandCapabilities(capKeys(userCapabilities));
  const admin = isGlobalAdminFlag === true;
  const canPrepare = admin || hasCap(caps, INBOUND_PREPARE);
  const canCommit = admin || hasCap(caps, INBOUND_COMMIT);
  return { canPrepare, canCommit, canSee: canPrepare || canCommit };
}

export const INBOUND_STATUS_COLOR = {
  draft: 'default',
  mapped: 'info',
  smoked: 'warning',
  committed: 'success',
  failed: 'error',
};

export function setInboundCrumb(id, filename) {
  if (!id || !filename) return;
  try {
    sessionStorage.setItem(`inbound-crumb:${id}`, filename);
  } catch {
    /* ignore quota */
  }
}

export function getInboundCrumb(id) {
  try {
    return sessionStorage.getItem(`inbound-crumb:${id}`) || '';
  } catch {
    return '';
  }
}
