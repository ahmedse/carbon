"""Phase H1-B — filterable, admin-only AI audit trail API.

GET  /carbon-api/ai/audit/   —  admin-only, read-only audit trail.

Read-only by structure: a GET-only ``APIView`` (no model viewset, no mutation
actions).  ``detail`` JSON is recursively redacted (``token|secret|password|
api_key`` keys) and long string values are truncated to 200 chars before they
leave the process — mirroring the redaction contract in
``ai.observability_api``.
"""

import logging
import re

from django.utils.dateparse import parse_date, parse_datetime
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.capabilities import AI_MANAGE_CONSOLE
from accounts.permissions import AdminOrSuperuserOnly
from ai.models.core import AuditLog

logger = logging.getLogger("carbon.ai.audit_api")

# Copied verbatim from ``ai.observability_api._SECRET_KEY_RE``.
_SECRET_KEY_RE = re.compile(r"token|secret|password|api_key", re.IGNORECASE)

_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 200
_MAX_STRING_LEN = 200


def _redact_detail(value):
    """Recursively blank secret-hinting keys and truncate long string values."""
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if _SECRET_KEY_RE.search(key) else _redact_detail(val))
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [_redact_detail(item) for item in value]
    if isinstance(value, str):
        return value[:_MAX_STRING_LEN]
    return value


def _parse_boundary(raw):
    """Parse an ISO datetime/date query boundary, or ``None`` when absent."""
    if not raw:
        return None
    dt = parse_datetime(raw)
    if dt is not None:
        return dt
    return parse_date(raw)


class AuditListView(APIView):
    """GET / — admin-only, filterable audit trail (no writes)."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = AI_MANAGE_CONSOLE.key

    def get(self, request):
        qs = AuditLog.objects.all()

        action = request.query_params.get("action")
        if action:
            qs = qs.filter(action=action)

        actor = request.query_params.get("actor")
        if actor:
            qs = qs.filter(actor=actor)

        start = _parse_boundary(request.query_params.get("start"))
        if start:
            qs = qs.filter(created_at__gte=start)

        end = _parse_boundary(request.query_params.get("end"))
        if end:
            qs = qs.filter(created_at__lte=end)

        try:
            page = int(request.query_params.get("page", 1))
        except (TypeError, ValueError):
            page = 1
        page = max(page, 1)

        try:
            page_size = int(request.query_params.get("page_size", _DEFAULT_PAGE_SIZE))
        except (TypeError, ValueError):
            page_size = _DEFAULT_PAGE_SIZE
        page_size = max(1, min(page_size, _MAX_PAGE_SIZE))

        qs = qs.order_by("-created_at")
        total = qs.count()
        start_idx = (page - 1) * page_size
        rows = qs[start_idx:start_idx + page_size]

        results = [
            {
                "id": row.id,
                "timestamp": row.created_at.isoformat(),
                "actor": row.actor,
                "action": row.action,
                "target": row.target,
                "detail": _redact_detail(row.detail),
            }
            for row in rows
        ]

        return Response(
            {
                "count": total,
                "page": page,
                "page_size": page_size,
                "results": results,
            }
        )
