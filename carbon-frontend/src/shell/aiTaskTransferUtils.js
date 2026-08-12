const VALID_DOMAIN_APP_IDS = new Set(['emissions']);

export function normalizeAppIdentifier(payload = {}, metadata = {}) {
  const explicit = typeof metadata.app_identifier === 'string' ? metadata.app_identifier.trim() : '';
  if (VALID_DOMAIN_APP_IDS.has(explicit)) {
    return explicit;
  }

  const payloadApp = typeof payload.app_identifier === 'string' ? payload.app_identifier.trim() : '';
  if (VALID_DOMAIN_APP_IDS.has(payloadApp)) {
    return payloadApp;
  }

  const sourcePage = String(metadata.source_page || '').toLowerCase();
  if (sourcePage.startsWith('/emissions') || sourcePage.startsWith('emissions')) {
    return 'emissions';
  }

  return null;
}