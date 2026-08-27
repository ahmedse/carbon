"""Carbon structured error taxonomy (EPH-5A).

Central registry of machine-readable error codes used across the platform's
API responses. Every error response carries a stable ``error_code`` from this
taxonomy so clients can branch on failure types without string-matching
human-readable messages.

Usage in views/services:

    from core.error_codes import CarbonAPIError

    raise CarbonAPIError('ERR_VAL_001', status_code=400)
"""
from rest_framework.exceptions import APIException

# ── Taxonomy ─────────────────────────────────────────────────────────────
# Format: <DOMAIN>_<NNN>. Extend here, never in views.
ERROR_CODES = {
    'ERR_AUTH_001': 'Authentication required',
    'ERR_AUTH_002': 'Token expired',
    'ERR_AUTH_003': 'Insufficient permissions',
    'ERR_CAT_001': 'Table not found',
    'ERR_CAT_002': 'Field not found',
    'ERR_CAT_003': 'Schema is locked',
    'ERR_DQ_001': 'DQ rule not found',
    'ERR_DQ_002': 'Rule execution failed',
    'ERR_DQ_003': 'Rule already assigned',
    'ERR_MDM_001': 'Reference set not found',
    'ERR_MDM_002': 'Invalid lifecycle transition',
    'ERR_SCH_001': 'DataTable not found',
    'ERR_VAL_001': 'Required field missing',
    'ERR_VAL_002': 'Invalid value',
    'ERR_VAL_003': 'Duplicate entry',
    'ERR_AI_001': 'AI service unavailable',
    'ERR_AI_002': 'Rate limit exceeded',
}

# Fallback message when an unknown code is raised.
_UNKNOWN_CODE_MESSAGE = 'Error'


class CarbonAPIError(APIException):
    """Base structured API error carrying a taxonomy error code.

    Raise anywhere with a code from ``ERROR_CODES``. ``default_code`` is set
    to the taxonomy code (BEFORE ``super().__init__``) so DRF propagates it
    through its own machinery; the platform exception handler additionally
    surfaces ``error_code`` on the response body.
    """

    status_code = 400
    default_code = 'carbon_api_error'

    def __init__(self, error_code, detail=None, status_code=400):
        self.error_code = error_code
        self.status_code = status_code
        detail = detail or ERROR_CODES.get(error_code, _UNKNOWN_CODE_MESSAGE)
        # APIException.__init__ reads self.default_code when no explicit code
        # is passed and stores it on the ErrorDetail — set it first.
        self.default_code = error_code
        super().__init__(detail)


def infer_error_code(exc, status_code):
    """Map an arbitrary exception/HTTP status to a taxonomy error code.

    ``CarbonAPIError`` instances keep their explicit code; everything else
    falls back to the closest taxonomy entry for the status code (context-free
    but stable and machine-readable).
    """
    if isinstance(exc, CarbonAPIError):
        return exc.error_code
    if status_code == 401:
        return 'ERR_AUTH_001'
    if status_code == 403:
        return 'ERR_AUTH_003'
    if status_code == 404:
        return 'ERR_SCH_001'
    if status_code == 400:
        return 'ERR_VAL_001'
    if status_code == 429:
        return 'ERR_AI_002'
    if status_code >= 500:
        return 'ERR_AI_001'
    return 'ERR_VAL_002'
