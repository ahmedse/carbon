import { listDomainManifests } from '../api/aiPulse';

// ── Domain-app registry (manifest-driven) ──────────────────────────────
// The set of valid app_identifiers is derived from the live manifest API
// (GET ai/pulse/apps/) so installing a new domain app is recognized with
// ZERO frontend edits. Previously this was a hard-coded Set(['emissions'])
// that silently dropped every other registered app (e.g. "water").

// Session cache of the app ids. A failed load is NOT cached, so a later
// transfer retries the fetch. Reset via __resetAppIdentifierCache() (tests).
let _appIdsCache = null;

/**
 * Fetch the list of registered domain-app identifiers, cached for the session.
 * Never throws — returns [] on failure (caller degrades to platform scope).
 * @param {string} token - JWT access token
 * @returns {Promise<Array<string>>}
 */
export async function fetchKnownAppIdentifiers(token) {
  if (_appIdsCache) return _appIdsCache;
  try {
    const data = await listDomainManifests(token);
    _appIdsCache = (data?.apps || [])
      .map((m) => m?.app_identifier)
      .filter((id) => typeof id === 'string' && id);
  } catch {
    return [];
  }
  return _appIdsCache;
}

/** Test-only: clear the session manifest cache. */
export function __resetAppIdentifierCache() {
  _appIdsCache = null;
}

/**
 * Resolve the conversation's app_identifier from payload + metadata against
 * the known (registered) app ids. Pure — no fetch, no cache.
 *
 * Order of precedence:
 *   1. metadata.app_identifier (explicit — e.g. from a domain entry-point)
 *   2. payload.app_identifier
 *   3. source_page slug naming a registered app (e.g. "emissions-report-generator")
 *
 * Returns null (platform-level scope) when nothing maps to a known app.
 */
export function normalizeAppIdentifier(payload = {}, metadata = {}, knownAppIds = []) {
  const ids = Array.isArray(knownAppIds) ? knownAppIds : [];

  const explicit = typeof metadata.app_identifier === 'string' ? metadata.app_identifier.trim() : '';
  if (explicit && ids.includes(explicit)) return explicit;

  const payloadApp = typeof payload.app_identifier === 'string' ? payload.app_identifier.trim() : '';
  if (payloadApp && ids.includes(payloadApp)) return payloadApp;

  const sourcePage = String(metadata.source_page || '').toLowerCase();
  if (sourcePage) {
    for (const id of ids) {
      if (
        sourcePage === id ||
        sourcePage.startsWith(`${id}-`) ||
        sourcePage.startsWith(`${id}/`) ||
        sourcePage.startsWith(`/${id}`)
      ) {
        return id;
      }
    }
  }

  return null;
}