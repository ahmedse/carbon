// Error-code -> i18n key mapping, wired into `src/utils/errorNormalizer.js`.
//
// `normalizeError` attaches a canonical `errorCode` plus the corresponding
// `messageKey` (namespace-relative to the `errors` namespace). Callers resolve
// the translated message with `useTranslation('errors')` and `t(messageKey)`,
// falling back to `t('generic')` when `messageKey` is null.
//
// Keys are namespace-relative to the `errors` namespace (useTranslation('errors')).

export const ERROR_CODE_KEYS = {
  invalid_credentials: 'invalidCredentials',
  authentication_failed: 'sessionExpired',
  not_authenticated: 'sessionExpired',
  permission_denied: 'permissionDenied',
  not_found: 'notFound',
  validation_error: 'validation',
  timeout: 'timeout',
  network_error: 'network',
  server_error: 'server',
  unknown_error: 'generic',
};

// Resolve a translated message for a known error code. Returns null when the
// code is unknown so callers can fall back to a generic message.
export function errorMessageKey(code) {
  return ERROR_CODE_KEYS[code] || null;
}
