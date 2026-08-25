// I18N-2: Minimal error-code -> i18n key mapping.
//
// I18N-5 will complete the full backend error-code -> message mapping and wire it
// into `src/utils/errorNormalizer.js` (normalizeError) / the apiFetch normalized
// error envelope. For now this exposes a small, stable helper so callers that
// surface an error to the user can resolve a translated message without reaching
// into raw API internals.
//
// Keys are namespace-relative to the `errors` namespace (useTranslation('errors')).

export const ERROR_CODE_KEYS = {
  invalid_credentials: 'invalidCredentials',
  authentication_failed: 'sessionExpired',
  not_authenticated: 'sessionExpired',
  permission_denied: 'permissionDenied',
  not_found: 'notFound',
  timeout: 'timeout',
  network_error: 'network',
  server_error: 'server',
};

// Resolve a translated message for a known error code. Returns null when the
// code is unknown so callers can fall back to a generic message.
export function errorMessageKey(code) {
  return ERROR_CODE_KEYS[code] || null;
}
