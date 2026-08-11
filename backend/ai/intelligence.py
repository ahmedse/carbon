"""
CarbonIntelligence — Single entry point for all AI calls in Carbon.

Wave C. Wraps the configured AIProvider (from AI_PROVIDER_CLASS) and
provides the bridge between Carbon ORM objects and the protocol's typed
dataclasses. All Carbon code calls CarbonIntelligence — never a specific
provider directly. Swap backends by changing AI_PROVIDER_CLASS in settings.

Two modes:
  Sync  — calls AIProvider ABC methods, returns typed responses.
  Async — submits tasks via post_task(), returns task_id dicts for the
          DQ job system (nl_check, suggest, anomaly jobs poll via refresh()).
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from django.conf import settings

from backend.ai.protocol import (
    AIProvider,
    DqRuleInput,
    DqValidateRequest,
    DqValidateResponse,
    ProviderStatus,
    Scope,
)
from backend.ai.providers._http import get_modules as _http_get_modules
from backend.ai.providers._http import post_task as _http_post_task
from backend.ai.providers._http import get_task as _http_get_task

logger = logging.getLogger("carbon.ai.intelligence")

# ── Provider factory ──────────────────────────────────────────────────────


def _get_provider() -> AIProvider:
    """Instantiate the configured AIProvider class.

    Reads AI_PROVIDER_CLASS from Django settings (default:
    ``ai.providers.pulse.PulseProvider``).  The class MUST be a concrete
    subclass of ``AIProvider``.
    """
    class_path: str = getattr(settings, "AI_PROVIDER_CLASS", "ai.providers.pulse.PulseProvider")

    module_path, _, cls_name = class_path.rpartition(".")
    if not module_path:
        raise ImportError(f"Invalid AI_PROVIDER_CLASS: {class_path}")

    module = importlib.import_module(module_path)
    cls = getattr(module, cls_name)

    if not issubclass(cls, AIProvider):
        raise TypeError(f"{class_path} is not a subclass of AIProvider")

    return cls()


# ── Scope builder ─────────────────────────────────────────────────────────


def build_scope(user) -> Scope:
    """Extract a Scope from a Django User (RBAC-aware).

    Called by every CarbonIntelligence method that takes a user.  The
    Scope is injected into every AIProvider request so the provider
    can enforce data-access boundaries.
    """
    from accounts.models import ScopedRole

    org_unit_ids: list[str] = []
    module_ids: list[str] = []
    is_read_only = True

    if user is None or not user.is_authenticated:
        return Scope()

    if user.is_superuser:
        return Scope(is_superuser=True, org_unit_ids=["*"])

    if user.is_staff:
        is_read_only = False

    roles = ScopedRole.objects.filter(user=user, is_active=True).select_related(
        "org_unit", "module"
    )

    for role in roles:
        if role.org_unit_id and str(role.org_unit_id) not in org_unit_ids:
            org_unit_ids.append(str(role.org_unit_id))
        if role.module_id and str(role.module_id) not in module_ids:
            module_ids.append(str(role.module_id))
        if not role.is_read_only:
            is_read_only = False

    return Scope(
        org_unit_ids=org_unit_ids,
        module_ids=module_ids,
        is_read_only=is_read_only,
        user_identifier=str(user.pk),
    )


# ── CarbonIntelligence ───────────────────────────────────────────────────


class CarbonIntelligence:
    """Single entry point for all AI calls in Carbon.

    Usage::

        intelligence = CarbonIntelligence()
        result = intelligence.validate_dq_rule(rule, rows, user=request.user)

    The provider is lazily instantiated from ``AI_PROVIDER_CLASS``.
    """

    def __init__(self) -> None:
        self._provider: AIProvider | None = None

    # ── Provider access ────────────────────────────────────────────────

    @property
    def provider(self) -> AIProvider:
        """Lazy-instantiate the configured AIProvider."""
        if self._provider is None:
            self._provider = _get_provider()
        return self._provider

    # ── Health ─────────────────────────────────────────────────────────

    def health_check(self) -> ProviderStatus:
        return self.provider.health_check()

    # ── Sync: DQ Validate ──────────────────────────────────────────────

    def validate_dq_rule(
        self,
        rule,
        rows: list[dict[str, Any]],
        user=None,
        context: dict[str, Any] | None = None,
    ) -> DqValidateResponse:
        """Validate a DQRule against rows.

        Args:
            rule: DQRule model instance
            rows: list of {field_name: value} dicts
            user: Django User for scope
            context: optional dict with table_name, row_count_hint, etc.
        """
        prompt = _extract_prompt(rule)
        scope = build_scope(user)

        request = DqValidateRequest(
            rules=[
                DqRuleInput(
                    id=str(rule.pk),
                    prompt=prompt,
                    fields=_rule_fields(rule),
                    severity=rule.severity or "error",
                )
            ],
            rows=rows,
            context=context or {},
            scope=scope,
        )
        return self.provider.validate_dq(request)

    # ── Async: Submit DQ Validate (for DQ job system) ──────────────────

    def submit_dq_validate(
        self,
        rules: list[dict[str, Any]],
        rows: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Submit a dq.validate task and return immediately.

        Returns the raw Pulse response dict (may be ``status: completed``
        or ``status: pending``).  Callers poll ``get_task_status()``.
        """
        mapped_rules = [
            {
                "id": str(r.get("id", "")),
                "prompt": r.get("prompt", ""),
                "fields": r.get("fields", []),
                "severity": r.get("severity", "error"),
            }
            for r in rules
        ]
        payload = {
            "rules": mapped_rules,
            "rows": rows,
            "context": context or {},
        }
        return _http_post_task(
            base_url=settings.AI_PROVIDER_URL.rstrip("/"),
            api_key=settings.AI_PROVIDER_API_KEY,
            task_type="dq.validate",
            payload=payload,
            timeout=30,
        )

    # ── Async: Submit DQ Suggest ────────────────────────────────────────

    def submit_dq_suggest(self, table_payload: dict[str, Any]) -> dict[str, Any]:
        """Submit a dq.suggest task and return immediately."""
        return _http_post_task(
            base_url=settings.AI_PROVIDER_URL.rstrip("/"),
            api_key=settings.AI_PROVIDER_API_KEY,
            task_type="dq.suggest",
            payload={"table": table_payload},
            timeout=60,
        )

    # ── Async: Submit Anomaly Detect ─────────────────────────────────────

    def submit_anomaly_detect(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Submit an anomaly.detect task and return immediately."""
        return _http_post_task(
            base_url=settings.AI_PROVIDER_URL.rstrip("/"),
            api_key=settings.AI_PROVIDER_API_KEY,
            task_type="anomaly.detect",
            payload={"profile": payload},
            timeout=120,
        )

    # ── Task status polling ──────────────────────────────────────────────

    def get_task_status(self, task_id: str) -> dict[str, Any]:
        """Poll Pulse for a task's current status.

        GET {base_url}/tasks/{task_id}

        Returns raw JSON or ``{status: pulse_unavailable, error: {...}}``.
        """
        base_url = settings.AI_PROVIDER_URL.rstrip("/")
        return _http_get_task(base_url, task_id, timeout=10)


# ── Helpers ───────────────────────────────────────────────────────────────


def _extract_prompt(rule) -> str:
    """Extract NL prompt from a DQRule (definition JSON, then legacy params)."""
    try:
        definition = rule.definition
        if isinstance(definition, dict):
            params = definition.get("params", {})
            if isinstance(params, dict) and params.get("prompt"):
                return str(params["prompt"])
    except Exception:
        pass
    try:
        if isinstance(rule.params, dict) and rule.params.get("prompt"):
            return str(rule.params["prompt"])
    except Exception:
        pass
    return ""


def _rule_fields(rule) -> list[str]:
    """Return field names assigned to a DQRule."""
    names: list[str] = []
    try:
        for assn in rule.field_assignments.select_related("data_field"):
            if assn.data_field:
                names.append(assn.data_field.name)
    except Exception:
        pass
    return names
