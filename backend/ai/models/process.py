"""Django model for governed process definitions — :class:`ProcessDefinition` (P3-03).

Stores a process definition document and validates it against the unified
process schema (``ai/process_schema.json``). The canonical document shape::

    id, version, owner, status(draft/review/active/deprecated),
    objects, inputs, scope(source: authenticated_host_context),
    objective (predicate), steps[ ... ], constraints[ ... ], evidence,
    policies[refuse_if/ask_if], exceptions, kill_switch, tests.

``jsonschema`` is **not** in ``backend/requirements.txt``, so :meth:`validate`
uses a minimal hand-rolled validator (:func:`validate_definition`) that enforces
the same enumerated fields and rules the JSON Schema declares: the five required
fields, the ``status`` enum, the ``step.kind`` enum, the ``autonomy`` enum,
capability resolution (via P3-01), and ``depends_on`` references.
``process_schema.json`` remains the canonical external contract; the hand-rolled
validator is the enforcement fallback and is kept in sync by hand (all enums are
declared here as module constants).

This module is host-side; the engine never imports it (RULE_20/ADR-0007).
"""

from __future__ import annotations

from typing import Any, Iterable

from django.core.exceptions import ValidationError
from django.db import models

from .base import AppScopeMixin, generate_uuid

# ── Enumerated fields (mirror ``ai/process_schema.json``) ──────────────────
STATUS_DRAFT = "draft"
STATUS_REVIEW = "review"
STATUS_ACTIVE = "active"
STATUS_DEPRECATED = "deprecated"
VALID_STATUSES = frozenset(
    {STATUS_DRAFT, STATUS_REVIEW, STATUS_ACTIVE, STATUS_DEPRECATED}
)

STEP_KIND_COMMAND = "command"
STEP_KIND_HUMAN_TASK = "human_task"
STEP_KIND_ASSERTION = "assertion"
VALID_STEP_KINDS = frozenset(
    {STEP_KIND_COMMAND, STEP_KIND_HUMAN_TASK, STEP_KIND_ASSERTION}
)

AUTONOMY_OBSERVE = "observe"
AUTONOMY_PROPOSE = "propose"
AUTONOMY_ACT_CONFIRM = "act_confirm"
AUTONOMY_ACT_NOTIFY = "act_notify"
AUTONOMY_ACT_SILENT = "act_silent"
AUTONOMY_HUMAN_ONLY = "human_only"
VALID_AUTONOMY = frozenset(
    {
        AUTONOMY_OBSERVE,
        AUTONOMY_PROPOSE,
        AUTONOMY_ACT_CONFIRM,
        AUTONOMY_ACT_NOTIFY,
        AUTONOMY_ACT_SILENT,
        AUTONOMY_HUMAN_ONLY,
    }
)

REQUIRED_FIELDS = ("id", "version", "owner", "status", "steps")


def _default_known_capabilities() -> set[str]:
    """Resolve the set of known capability ids via the P3-01 loader."""
    from ai.models.capability import load_capabilities

    return {cap.capability_id for cap in load_capabilities()}


def _validate_step(
    step: Any, idx: int, step_ids: set[str], known: set[str],
) -> list[str]:
    """Validate a single step; return a list of error messages."""
    errors: list[str] = []
    if not isinstance(step, dict):
        errors.append(f"steps[{idx}] must be a mapping")
        return errors
    if not step.get("id"):
        errors.append(f"steps[{idx}] missing 'id'")
    kind = step.get("kind")
    if kind not in VALID_STEP_KINDS:
        errors.append(
            f"steps[{idx}] has unknown kind {kind!r} "
            f"(expected one of {sorted(VALID_STEP_KINDS)})"
        )
    capability = step.get("capability")
    if capability is None:
        errors.append(f"steps[{idx}] missing 'capability'")
    elif capability not in known:
        errors.append(f"steps[{idx}] references unknown capability {capability!r}")
    autonomy = step.get("autonomy")
    if autonomy is not None and autonomy not in VALID_AUTONOMY:
        errors.append(
            f"steps[{idx}] has invalid autonomy {autonomy!r} "
            f"(expected one of {sorted(VALID_AUTONOMY)})"
        )
    depends_on = step.get("depends_on")
    if depends_on is not None:
        if not isinstance(depends_on, list):
            errors.append(f"steps[{idx}] 'depends_on' must be a list")
        else:
            for dep in depends_on:
                if dep not in step_ids:
                    errors.append(
                        f"steps[{idx}] references unknown dependency {dep!r}"
                    )
    return errors


def validate_definition(
    document: Any, *, known_capabilities: Iterable[str] | None = None,
) -> list[str]:
    """Validate a process definition document; return a list of error messages.

    Empty list == valid. Enforces required fields, the ``status`` enum, step
    shape/kind/autonomy enums, capability resolution, and ``depends_on``
    references. ``known_capabilities`` defaults to the P3-01 loader's registry.
    """
    if not isinstance(document, dict):
        return ["definition must be a mapping"]

    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        value = document.get(field)
        if value is None or value == "" or value == [] or value == {}:
            errors.append(f"missing required field: {field!r}")

    status = document.get("status")
    if status is not None and status not in VALID_STATUSES:
        errors.append(
            f"invalid status {status!r} "
            f"(expected one of {sorted(VALID_STATUSES)})"
        )

    steps = document.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("'steps' must be a non-empty list")
        return errors

    known = (
        set(known_capabilities)
        if known_capabilities is not None
        else _default_known_capabilities()
    )
    step_ids = {s.get("id") for s in steps if isinstance(s, dict) and s.get("id")}
    for idx, step in enumerate(steps):
        errors.extend(_validate_step(step, idx, step_ids, known))
    return errors


class ProcessDefinition(AppScopeMixin):
    """A governed process definition document.

    Stores the full document in ``definition`` (JSONField) with ``process_id``
    / ``version`` / ``owner`` / ``status`` denormalized for querying and admin.
    ``id`` is a UUID string pk via ``generate_uuid``.
    """

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)

    process_id = models.TextField(db_index=True)  # document `id`
    version = models.TextField(default="")
    owner = models.TextField(default="")
    status = models.TextField(default=STATUS_DRAFT, db_index=True)
    definition = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"
        ordering = ["process_id", "-created_at"]
        indexes = [
            models.Index(
                fields=["process_id", "version"],
                name="ai_process_lookup_idx",
            ),
        ]

    def __repr__(self) -> str:
        return (
            f"<ProcessDefinition id={self.id!r} process_id={self.process_id!r} "
            f"version={self.version!r} status={self.status!r}>"
        )

    def validate(
        self,
        document: Any = None,
        *,
        known_capabilities: Iterable[str] | None = None,
    ) -> None:
        """Validate this (or a supplied) definition; raise on the first errors."""
        doc = self.definition if document is None else document
        errors = validate_definition(doc, known_capabilities=known_capabilities)
        if errors:
            raise ValidationError({"definition": errors})

    @classmethod
    def from_document(
        cls,
        document: dict[str, Any],
        *,
        known_capabilities: Iterable[str] | None = None,
    ) -> "ProcessDefinition":
        """Build a validated (unsaved) instance from a definition document."""
        errors = validate_definition(document, known_capabilities=known_capabilities)
        if errors:
            raise ValidationError({"definition": errors})
        return cls(
            process_id=str(document.get("id") or ""),
            version=str(document.get("version") or ""),
            owner=str(document.get("owner") or ""),
            status=str(document.get("status") or STATUS_DRAFT),
            definition=document,
        )
