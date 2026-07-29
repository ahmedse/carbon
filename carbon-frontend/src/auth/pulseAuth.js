// src/auth/pulseAuth.js
// Single source of truth for binding the authenticated Carbon user to Pulse.
// Copied from Gigacast implementation.

const PULSE_HOST = import.meta.env.VITE_PULSE_HOST || 'http://127.0.0.1:9100';

// Auto-connect Pulse by default (zero-intervention).
export const PULSE_AUTO_CONNECT =
  String(import.meta.env.VITE_PULSE_AUTO_CONNECT ?? 'true').toLowerCase() !== 'false';

// De-dupe concurrent provisioning attempts.
let inFlightProvision = null;

/**
 * Push a fresh Carbon JWT into Pulse so it keeps making scoped API calls as the
 * real user. Silent — never throws, never blocks the auth flow.
 */
export async function syncPulseToken(newAccessToken) {
  if (!PULSE_AUTO_CONNECT) return;
  const pulseKey = localStorage.getItem('pulse_key');
  if (!pulseKey || !newAccessToken) return;
  try {
    await fetch(`${PULSE_HOST}/instances/carbon/user-keys/refresh-token`, { // pulse sync
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Pulse-Key': pulseKey },
      body: JSON.stringify({ host_token: newAccessToken }),
    });
  } catch {
    // Pulse may be offline — it will use the last valid token.
  }
}

/**
 * Ensure the authenticated Carbon user is linked to Pulse so the copilot opens
 * as the real user (never "Anonymous").
 */
export async function ensurePulseKey(accessToken) {
  if (!accessToken) return null;

  const existing = localStorage.getItem('pulse_key');
  if (existing) {
    if (!PULSE_AUTO_CONNECT) return existing;
    // Already linked — keep Pulse's token copy current, then return the key.
    await syncPulseToken(accessToken);
    return existing;
  }

  if (!PULSE_AUTO_CONNECT) return null;

  // Coalesce parallel callers onto one provisioning request.
  if (inFlightProvision) return inFlightProvision;

  inFlightProvision = (async () => {
    try {
      const res = await fetch(`${PULSE_HOST}/instances/carbon/user-keys`, { // pulse provision
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ host_token: accessToken }),
      });
      if (!res.ok) return null;
      const data = await res.json().catch(() => null);
      if (data?.key) {
        localStorage.setItem('pulse_key', data.key);
        return data.key;
      }
      return null;
    } catch {
      // Pulse offline or unreachable — manual connect still works.
      return null;
    } finally {
      inFlightProvision = null;
    }
  })();

  return inFlightProvision;
}
