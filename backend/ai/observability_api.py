"""
AI Pulse Observability API — read-only, model-backed console read layer.

GET  /carbon-api/ai/pulse/inventory/          — 13 panels + model row counts
GET  /carbon-api/ai/pulse/data/<panel_key>/   — merged, redacted, capped rows
GET  /carbon-api/ai/pulse/archetypes/         — vendored engine bundles (FS)

Read-only by structure: every view is a GET-only ``APIView`` (no model
viewset, no mutation actions). Rows are serialized with a generic factory
serializer — never 49 bespoke serializers — and every JSON value stored under
a ``token|secret|password|api_key`` key is recursively redacted before it
leaves the process. ``Instance.host_api_token`` is additionally excluded at
the field level (matches the ``token`` regex).
"""

import logging
import re
from pathlib import Path

from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai.models.core import (
    Agent,
    AgentHandoff,
    AuditLog,
    ConversationContextRecord,
    Feedback,
    Insight,
    Instance,
    KgEdge,
    KgNode,
    KgProvenance,
    KnowledgeEntity,
    LLMCallLog,
    MemoryEpisodic,
    MemoryLongTerm,
    Notification,
    OpsRun,
    PlaybookBlock,
    PromptEval,
    PromptVersion,
    Run,
    RunStep,
    Skill,
    SkillAdmissionLog,
    SystemSnapshot,
    TaskExecution,
    ToolExecution,
    Trajectory,
    TurnLedgerRow,
)
from ai.models.knowledge_graph import (
    KgBootstrapRun,
    KgFeedbackRecord,
    KgGoldenPair,
    KgPlanStep,
    KgProactiveInsight,
    KgProactiveTrigger,
    KgQualityScore,
    KgQueryFeedback,
    KgQueryPlan,
    KgRecoveryLog,
    KgReviewItem,
    KnowledgeEdge,
    KnowledgeNode,
)

logger = logging.getLogger("carbon.ai.observability_api")

# ── Panel registry ───────────────────────────────────────────────────────────
# One curated mapping from panel key to backing ai models. `archetypes` is NOT
# here — it is a filesystem surface served by PulseArchetypesView.
PANEL_REGISTRY = {
    "knowledge": [KnowledgeEntity, KnowledgeNode, KnowledgeEdge, Insight],
    "memory": [MemoryLongTerm, MemoryEpisodic],
    "graph": [
        KnowledgeNode,
        KnowledgeEdge,
        KgNode,
        KgEdge,
        KgProvenance,
        KgQueryPlan,
        KgPlanStep,
        KgBootstrapRun,
    ],
    "agents": [Agent, AgentHandoff],
    "mcp": [Instance],
    "tools": [ToolExecution, TaskExecution],
    "skills": [Skill, SkillAdmissionLog],
    "prompts": [PromptVersion, PromptEval, PlaybookBlock],
    "feedback": [Feedback, KgFeedbackRecord, KgQueryFeedback, KgReviewItem, KgGoldenPair],
    "learning": [OpsRun, Run, RunStep, Trajectory, KgQualityScore, KgRecoveryLog],
    "monitoring": [SystemSnapshot, Notification, Insight, KgProactiveTrigger, KgProactiveInsight],
    "audit": [AuditLog],
    "logs": [LLMCallLog, ToolExecution, TaskExecution, TurnLedgerRow, ConversationContextRecord],
}

PANEL_LABELS = {
    "knowledge": "Knowledge Base",
    "memory": "Memory",
    "graph": "Knowledge Graph",
    "agents": "Agents",
    "mcp": "MCP Servers",
    "tools": "Tools",
    "skills": "Skills Catalog",
    "prompts": "Prompts & Playbook",
    "feedback": "Feedback Review",
    "learning": "Learning Jobs",
    "monitoring": "Monitoring",
    "audit": "AI Audit Trail",
    "logs": "AI Logs",
}

_SECRET_KEY_RE = re.compile(r"token|secret|password|api_key", re.IGNORECASE)

# Most-recent-first panel ordering per model (candidate order matters).
_TIMESTAMP_CANDIDATES = (
    "updated_at",
    "last_accessed_at",
    "last_accessed",
    "last_used",
    "occurred_at",
    "taken_at",
    "executed_at",
    "synthesized_at",
    "extracted_at",
    "promoted_at",
    "last_executed_at",
    "last_login_at",
    "completed_at",
    "last_fired_at",
    "delivered_at",
    "expires_at",
    "decay_at",
    "reviewed_at",
    "created_at",
)

_SERIALIZER_CACHE: dict = {}


def _make_serializer(model):
    """Build a ModelSerializer excluding any field whose name hints at a secret.

    ``Instance.host_api_token`` matches the ``token`` regex and is therefore
    excluded here — it can never reach the wire through this layer.
    """
    cached = _SERIALIZER_CACHE.get(model)
    if cached is not None:
        return cached
    excluded = {
        field.name
        for field in model._meta.get_fields()
        if _SECRET_KEY_RE.search(field.name)
    }
    # NOTE: this DRF version rejects `fields="__all__"` combined with a
    # non-empty `exclude` (AssertionError). When nothing is excluded use the
    # explicit `fields="__all__"`; otherwise rely on `exclude` alone, which
    # DRF resolves to "all fields minus the excluded ones" — same behavior.
    meta_attrs = {"model": model, "exclude": tuple(excluded)}
    if not excluded:
        meta_attrs["fields"] = "__all__"
    meta = type("Meta", (), meta_attrs)
    serializer = type(f"{model.__name__}Serializer", (serializers.ModelSerializer,), {"Meta": meta})
    _SERIALIZER_CACHE[model] = serializer
    return serializer


def _redact_secrets(value):
    """Recursively redact JSON values stored under secret-hinting keys.

    Applies to ``Instance.config`` and any ``*_json`` fields: any dict value
    whose key matches ``token|secret|password|api_key`` becomes
    ``"[REDACTED]"`` — the same spirit as the E1 masked-config lesson.
    """
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if _SECRET_KEY_RE.search(key) else _redact_secrets(val))
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [_redact_secrets(item) for item in value]
    return value


def _timestamp_field(model):
    """Return the most-recent timestamp field name for a model, else None."""
    fields = {field.name: field for field in model._meta.get_fields()}
    for name in _TIMESTAMP_CANDIDATES:
        field = fields.get(name)
        if field is not None and field.get_internal_type() == "DateTimeField":
            return name
    return None


class PulseInventoryView(APIView):
    """GET inventory/ — 13 panels with model-backed row counts."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        panels = []
        for key, models in PANEL_REGISTRY.items():
            panels.append(
                {
                    "key": key,
                    "label": PANEL_LABELS[key],
                    "count": sum(model.objects.count() for model in models),
                    "models": [model.__name__ for model in models],
                }
            )
        panels.sort(key=lambda panel: panel["label"])
        return Response({"panels": panels})


class PulseDataView(APIView):
    """GET data/<key>/ — merged, redacted, capped rows for one panel."""

    permission_classes = [IsAuthenticated]

    def get(self, request, key):
        models = PANEL_REGISTRY.get(key)
        if models is None:
            return Response({"error": "unknown_panel"}, status=404)

        try:
            limit = int(request.query_params.get("limit", 50))
        except (TypeError, ValueError):
            limit = 50
        limit = min(max(limit, 1), 200)

        results = []
        for model in models:
            queryset = model.objects.all()
            timestamp = _timestamp_field(model)
            if timestamp is not None:
                queryset = queryset.order_by(f"-{timestamp}")
            serializer = _make_serializer(model)
            for row in queryset[:limit]:
                data = _redact_secrets(serializer(row).data)
                data["_type"] = model.__name__
                results.append(data)
        results = results[:limit]

        return Response(
            {
                "key": key,
                "label": PANEL_LABELS[key],
                "count": len(results),
                "models": [model.__name__ for model in models],
                "results": results,
            }
        )


class PulseArchetypesView(APIView):
    """GET archetypes/ — top-level vendored engine bundle directories.

    Read-only directory listing; no file contents are ever read, so no
    filesystem secrets can leak. Fail-visible: on any error return an empty
    bundle list with the error string (never 500).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        base = Path(__file__).resolve().parent / "engine" / "archetypes"
        skipped = {"__init__.py", "README.md", "__pycache__"}
        try:
            bundles = [
                {"name": entry.name, "kind": "bundle"}
                for entry in sorted(base.iterdir())
                if entry.is_dir() and entry.name not in skipped
            ]
            return Response({"bundles": bundles})
        except Exception as exc:  # noqa: BLE001 — never 500 the console
            logger.exception("archetypes listing failed")
            return Response({"bundles": [], "error": str(exc)})
