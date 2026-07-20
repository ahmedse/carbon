# core/feedback.py
"""
Unified feedback mechanism for the entire platform.

Provides a single, structured response envelope for all user-facing feedback:
blocked actions, validation errors, warnings, and confirmations. Every message
carries a machine-readable code, human title/detail, the reasons behind it, and
concrete remediation steps so the UI can always tell the user WHAT happened and
WHAT TO DO next.

Usage in any view:

    from core.feedback import AppFeedback

    raise AppFeedback(
        code="table_has_rows",
        title="Cannot delete table",
        detail="This table still contains data.",
        reasons=[f"The table has {n} row(s)."],
        remediation=[
            "Delete or archive the rows first.",
            "Or ask an administrator to force-delete.",
        ],
        context={"row_count": n},
        status_code=400,
    )
"""
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework import status as http_status


SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"
SEVERITY_SUCCESS = "success"


def build_feedback(
    *,
    code,
    title,
    detail="",
    severity=SEVERITY_ERROR,
    reasons=None,
    remediation=None,
    context=None,
):
    """Build the canonical feedback envelope dict."""
    return {
        "code": code,
        "severity": severity,
        "title": title,
        "detail": detail or title,
        "reasons": list(reasons or []),
        "remediation": list(remediation or []),
        "context": dict(context or {}),
    }


class AppFeedback(APIException):
    """
    Raise this anywhere to return a structured, user-friendly feedback response.

    The response body always contains a top-level `feedback` object plus a
    `detail` string for backward compatibility with older clients.
    """
    status_code = http_status.HTTP_400_BAD_REQUEST
    default_code = "app_feedback"

    def __init__(
        self,
        *,
        code,
        title,
        detail="",
        severity=SEVERITY_ERROR,
        reasons=None,
        remediation=None,
        context=None,
        status_code=None,
    ):
        if status_code is not None:
            self.status_code = status_code
        self.feedback = build_feedback(
            code=code,
            title=title,
            detail=detail,
            severity=severity,
            reasons=reasons,
            remediation=remediation,
            context=context,
        )
        # APIException expects `.detail`; keep it human-readable.
        super().__init__(detail=self.feedback["detail"], code=code)


def _normalize_drf_error(data):
    """
    Turn a standard DRF error payload (validation errors, permission denied,
    not found, etc.) into a list of human-readable reason strings.
    """
    reasons = []
    if isinstance(data, dict):
        for field, errs in data.items():
            if field == "detail":
                continue
            if isinstance(errs, (list, tuple)):
                for e in errs:
                    label = "" if field in ("non_field_errors",) else f"{field}: "
                    reasons.append(f"{label}{e}")
            else:
                label = "" if field in ("non_field_errors",) else f"{field}: "
                reasons.append(f"{label}{errs}")
    elif isinstance(data, (list, tuple)):
        reasons.extend(str(e) for e in data)
    return reasons


def unified_exception_handler(exc, context):
    """
    DRF EXCEPTION_HANDLER that wraps every error response in the unified
    feedback envelope. AppFeedback instances pass through with their rich data;
    all other DRF exceptions are normalized into the same shape.
    """
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    # AppFeedback already carries a structured envelope.
    if isinstance(exc, AppFeedback):
        payload = dict(exc.feedback)
        response.data = {"feedback": payload, "detail": payload["detail"]}
        return response

    data = response.data
    status_code = response.status_code

    # Derive a sensible title/code from the HTTP status.
    if status_code == http_status.HTTP_401_UNAUTHORIZED:
        code, title = "unauthenticated", "Authentication required"
        remediation = ["Sign in again to continue."]
    elif status_code == http_status.HTTP_403_FORBIDDEN:
        code, title = "forbidden", "You don't have permission"
        remediation = ["Contact an administrator if you need access."]
    elif status_code == http_status.HTTP_404_NOT_FOUND:
        code, title = "not_found", "Not found"
        remediation = ["The item may have been moved or deleted. Refresh and try again."]
    elif status_code == http_status.HTTP_429_TOO_MANY_REQUESTS:
        code, title = "throttled", "Too many requests"
        remediation = ["Please wait a moment and try again."]
    elif status_code >= 500:
        code, title = "server_error", "Something went wrong"
        remediation = ["Try again shortly. If it persists, contact support."]
    else:
        code, title = "validation_error", "Please review the highlighted fields"
        remediation = ["Correct the issues listed below and try again."]

    detail = ""
    if isinstance(data, dict) and "detail" in data:
        detail = str(data["detail"])

    reasons = _normalize_drf_error(data)
    if not detail:
        detail = title

    feedback = build_feedback(
        code=code,
        title=title,
        detail=detail,
        severity=SEVERITY_ERROR,
        reasons=reasons,
        remediation=remediation,
        context={"status": status_code},
    )
    response.data = {"feedback": feedback, "detail": detail}
    return response
