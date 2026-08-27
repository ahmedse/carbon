"""DRF exception handler that decorates every error with a taxonomy error_code.

Extends the existing ``catalog.exceptions.data_trust_exception_handler`` —
that handler remains the single source of truth for the error envelope
(``error``/``message``/``timestamp``/``path``/``correlation_id``/``details``).
This handler only augments dict payloads with a machine-readable
``error_code`` so clients can branch on failure types.
"""
from catalog.exceptions import data_trust_exception_handler
from core.error_codes import infer_error_code


def structured_exception_handler(exc, context):
    """Augment the platform error envelope with a taxonomy ``error_code``.

    - Delegates to ``data_trust_exception_handler`` for the base envelope.
    - Returns None when the base handler does (let Django handle it).
    - Adds ``error_code`` to dict payloads via ``infer_error_code``.
    - Leaves ``AppFeedback`` envelopes untouched (they already carry a
      machine-readable ``code`` inside their feedback payload).
    """
    from core.feedback import AppFeedback

    response = data_trust_exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(response.data, dict) and not isinstance(exc, AppFeedback):
        if 'error_code' not in response.data:
            response.data['error_code'] = infer_error_code(exc, response.status_code)

    return response
