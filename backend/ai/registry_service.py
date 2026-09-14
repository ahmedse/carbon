"""Process Registry service (P3-05a) — host-side lifecycle + autonomy dial.

The registry operates on :class:`~ai.models.process.ProcessDefinition` (created
in P3-03) and the durable :class:`~ai.models.autonomy.AutonomyOverride` rows
(added here). It enforces the CBAC capability gates for each lifecycle
transition (via ``accounts.capabilities.has_capability`` /
``has_any_capability``) — group/role names are never hardcoded here.

Key rule — **author ≠ publisher**: ``publish`` refuses the transition when the
actor's identity equals the document's ``owner`` (the draft author), even if the
actor also holds ``ai:publisher`` (e.g. a superuser). This is the separation-of-
duties guarantee behind the pilot.

The kill switch is the existing ``kill_switch`` boolean inside the definition
document (no new model); ``is_killed`` is a read helper.

This module is host-side; the engine never imports it (RULE_20 / ADR-0007).
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.capabilities import (
    AI_OPERATOR,
    AI_PROCESS_OWNER,
    AI_PUBLISHER,
    has_any_capability,
    has_capability,
)
from ai.models.autonomy import AutonomyOverride
from ai.models.process import (
    STATUS_ACTIVE,
    STATUS_DEPRECATED,
    STATUS_DRAFT,
    STATUS_REVIEW,
    ProcessDefinition,
    VALID_AUTONOMY,
)


class RegistryError(Exception):
    """Base class for registry service errors."""


class RegistryNotFoundError(RegistryError):
    """Raised when a process definition is not found."""


class RegistryPermissionError(RegistryError):
    """Raised when the actor lacks the capability (or violates separation of duties)."""


class RegistryStateError(RegistryError):
    """Raised when the operation is illegal for the current status."""


class RegistryValidationError(RegistryError):
    """Raised when an input (autonomy level, step id) is invalid."""


def _identity(actor: Any) -> str:
    """Derive a stable identity string for an actor (user object or string)."""
    if actor is None:
        return ""
    username = getattr(actor, "username", None)
    if username:
        return str(username)
    return str(actor)


def _diff_dict(a: Any, b: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Recursive unified diff returning (added, removed, changed)."""
    a = a if isinstance(a, dict) else {}
    b = b if isinstance(b, dict) else {}
    added: dict[str, Any] = {}
    removed: dict[str, Any] = {}
    changed: dict[str, Any] = {}
    for key in b:
        if key not in a:
            added[key] = b[key]
    for key in a:
        if key not in b:
            removed[key] = a[key]
    for key in a:
        if key not in b:
            continue
        av, bv = a[key], b[key]
        if isinstance(av, dict) and isinstance(bv, dict):
            sub_a, sub_r, sub_c = _diff_dict(av, bv)
            if sub_a or sub_r or sub_c:
                changed[key] = {"added": sub_a, "removed": sub_r, "changed": sub_c}
        elif av != bv:
            changed[key] = {"from": av, "to": bv}
    return added, removed, changed


class ProcessRegistry:
    """Lifecycle + autonomy dial for governed process definitions."""

    # ── Lookups ──────────────────────────────────────────────────────

    def _latest(self, process_id: str) -> ProcessDefinition | None:
        return (
            ProcessDefinition.objects.filter(process_id=process_id)
            .order_by("-created_at")
            .first()
        )

    def _get(self, process_id: str) -> ProcessDefinition:
        obj = self._latest(process_id)
        if obj is None:
            raise RegistryNotFoundError(
                f"No process definition found for {process_id!r}."
            )
        return obj

    def resolve(self, process_ref: str) -> ProcessDefinition:
        """Resolve a ``process_ref`` to a process definition.

        A ``process_ref`` is either a bare ``process_id`` or a pinned
        ``process_id@version``. With an explicit ``@version`` the exact version
        is required (most recent row wins); without one, the latest definition
        is returned. Raises :class:`RegistryNotFoundError` when unknown.
        """
        if not process_ref or not str(process_ref).strip():
            raise RegistryNotFoundError("Empty process_ref.")
        ref = str(process_ref).strip()
        if "@" in ref:
            process_id, _, version = ref.rpartition("@")
            process_id = process_id.strip()
            version = version.strip()
            obj = (
                ProcessDefinition.objects.filter(
                    process_id=process_id, version=version,
                )
                .order_by("-created_at")
                .first()
            )
            if obj is None:
                raise RegistryNotFoundError(
                    f"No process definition found for {process_id!r}@{version!r}."
                )
            return obj
        return self._get(ref)

    async def get_active_run(self, run_id: str) -> dict[str, Any] | None:
        """Return the current run record (``RunRecord``) for ``run_id``.

        Read-only bridge for the ``ai.engine.ports.process.ProcessRegistry``
        port's ``get_active_run``: the host exposes a run's pinned definition,
        state, timestamps, and context so the engine can observe run state
        without importing host models. Returns ``None`` when the run is unknown.

        The port declares this ``async`` and the fail-closed command boundary
        awaits it (``_check_eligibility``), so this implementation is async too
        and wraps the synchronous ORM read in ``sync_to_async``.
        """
        from asgiref.sync import sync_to_async

        from ai.models.core import Run

        def _read() -> dict[str, Any] | None:
            run = Run.objects.filter(id=run_id).first()
            if run is None:
                return None
            return {
                "id": run.id,
                "process_id": run.definition_id,
                "process_version": run.definition_version,
                "state": run.run_state,
                "created_at": run.created_at,
                "updated_at": run.updated_at,
                "context": run.plan_json or {},
            }

        return await sync_to_async(_read, thread_sensitive=True)()

    @staticmethod
    def _set_status(current: ProcessDefinition, status: str) -> ProcessDefinition:
        doc = dict(current.definition or {})
        doc["status"] = status
        current.definition = doc
        current.status = status
        current.save()
        return current

    # ── Lifecycle ────────────────────────────────────────────────────

    def create_draft(self, document: dict[str, Any], author: Any) -> ProcessDefinition:
        """Create a new draft; ``author`` becomes the owner identity."""
        identity = _identity(author)
        doc = dict(document)
        doc["status"] = STATUS_DRAFT
        doc["owner"] = identity
        instance = ProcessDefinition.from_document(doc)
        instance.save()
        return instance

    def edit_draft(
        self, process_id: str, document: dict[str, Any], editor: Any,
    ) -> ProcessDefinition:
        """Edit a draft in place. Only when status==draft; editor must be the
        author or hold ``ai:process_owner``."""
        current = self._get(process_id)
        if current.status != STATUS_DRAFT:
            raise RegistryStateError(
                f"Process {process_id!r} is {current.status!r}; only drafts can be edited."
            )
        editor_identity = _identity(editor)
        if editor_identity != current.owner and not has_capability(
            editor, AI_PROCESS_OWNER.key
        ):
            raise RegistryPermissionError(
                "Only the author or a process owner may edit a draft."
            )
        doc = dict(document)
        doc["id"] = process_id
        doc["status"] = STATUS_DRAFT
        doc["owner"] = current.owner  # editing never reassigns ownership
        instance = ProcessDefinition.from_document(doc)
        current.definition = doc
        current.version = instance.version
        current.owner = instance.owner
        current.status = STATUS_DRAFT
        current.save()
        return current

    def submit_for_review(self, process_id: str, actor: Any) -> ProcessDefinition:
        """draft → review. Actor must hold ``ai:process_owner``."""
        current = self._get(process_id)
        if current.status != STATUS_DRAFT:
            raise RegistryStateError(
                f"Process {process_id!r} is {current.status!r}; only drafts can be submitted."
            )
        if not has_capability(actor, AI_PROCESS_OWNER.key):
            raise RegistryPermissionError(
                "Submitting for review requires the ai:process_owner capability."
            )
        return self._set_status(current, STATUS_REVIEW)

    def publish(self, process_id: str, actor: Any) -> ProcessDefinition:
        """review → active. Actor must hold ``ai:publisher`` AND must NOT be the
        document's author/owner (author ≠ publisher — self-publish refused)."""
        current = self._get(process_id)
        if current.status != STATUS_REVIEW:
            raise RegistryStateError(
                f"Process {process_id!r} is {current.status!r}; only review docs can be published."
            )
        if not has_capability(actor, AI_PUBLISHER.key):
            raise RegistryPermissionError(
                "Publishing requires the ai:publisher capability."
            )
        if _identity(actor) == current.owner:
            raise RegistryPermissionError(
                "Self-publish is refused: the publisher must differ from the author."
            )
        return self._set_status(current, STATUS_ACTIVE)

    def deprecate(self, process_id: str, actor: Any) -> ProcessDefinition:
        """active → deprecated. Actor holds ``ai:process_owner`` or ``ai:publisher``."""
        current = self._get(process_id)
        if current.status != STATUS_ACTIVE:
            raise RegistryStateError(
                f"Process {process_id!r} is {current.status!r}; only active docs can be deprecated."
            )
        if not has_any_capability(
            actor, {AI_PROCESS_OWNER.key, AI_PUBLISHER.key}
        ):
            raise RegistryPermissionError(
                "Deprecating requires the ai:process_owner or ai:publisher capability."
            )
        return self._set_status(current, STATUS_DEPRECATED)

    def diff(
        self,
        process_id: str,
        version_a: str | None = None,
        version_b: str | None = None,
    ) -> dict[str, Any]:
        """Structured diff (added/removed/changed) between two versions.

        Defaults: ``a`` = latest draft/review, ``b`` = current active version.
        Explicit ``version_a`` / ``version_b`` override either side.
        """
        def _by_version(version: str | None) -> ProcessDefinition | None:
            if version is None:
                return None
            return (
                ProcessDefinition.objects.filter(
                    process_id=process_id, version=version,
                )
                .order_by("-created_at")
                .first()
            )

        current = self._get(process_id)
        if version_a is not None:
            a_obj = _by_version(version_a)
        else:
            a_obj = (
                ProcessDefinition.objects.filter(process_id=process_id)
                .exclude(status=STATUS_ACTIVE)
                .order_by("-created_at")
                .first()
            ) or current

        b_obj = _by_version(version_b) if version_b is not None else (
            ProcessDefinition.objects.filter(
                process_id=process_id, status=STATUS_ACTIVE,
            )
            .order_by("-created_at")
            .first()
        )

        doc_a = a_obj.definition if a_obj else {}
        doc_b = b_obj.definition if b_obj else {}
        added, removed, changed = _diff_dict(doc_a, doc_b)
        return {
            "process_id": process_id,
            "from": {
                "version": a_obj.version if a_obj else None,
                "status": a_obj.status if a_obj else None,
            },
            "to": {
                "version": b_obj.version if b_obj else None,
                "status": b_obj.status if b_obj else None,
            },
            "added": added,
            "removed": removed,
            "changed": changed,
        }

    # ── Autonomy dial ────────────────────────────────────────────────

    def set_autonomy(
        self,
        process_id: str,
        step_id: str,
        org_unit: str,
        autonomy: str,
        set_by: str = "",
    ) -> AutonomyOverride:
        """Persist an autonomy override for a step × org unit."""
        if autonomy not in VALID_AUTONOMY:
            raise RegistryValidationError(
                f"Invalid autonomy {autonomy!r}; expected one of {sorted(VALID_AUTONOMY)}."
            )
        if not step_id:
            raise RegistryValidationError("step_id must not be empty.")
        if not org_unit:
            raise RegistryValidationError("org_unit must not be empty.")

        current = self._get(process_id)
        step_ids = {
            s.get("id")
            for s in (current.definition or {}).get("steps", [])
            if isinstance(s, dict) and s.get("id")
        }
        if step_id not in step_ids:
            raise RegistryValidationError(
                f"Unknown step {step_id!r}; known steps: {sorted(step_ids)}."
            )

        override, _ = AutonomyOverride.objects.update_or_create(
            process_id=process_id,
            step_id=step_id,
            org_unit=org_unit,
            defaults={"autonomy": autonomy, "set_by": set_by},
        )
        return override

    def get_autonomy(self, process_id: str) -> dict[str, Any]:
        """Effective autonomy per step: definition default + per-org_unit overrides."""
        current = self._get(process_id)
        steps = (current.definition or {}).get("steps", [])
        defaults = {
            s.get("id"): s.get("autonomy")
            for s in steps
            if isinstance(s, dict) and s.get("id")
        }
        result: dict[str, Any] = {
            step_id: {"default": default, "overrides": {}}
            for step_id, default in defaults.items()
        }
        for override in AutonomyOverride.objects.filter(process_id=process_id):
            entry = result.setdefault(
                override.step_id,
                {"default": defaults.get(override.step_id), "overrides": {}},
            )
            entry["overrides"][override.org_unit] = override.autonomy
        return {"process_id": process_id, "steps": result}

    # ── Kill switch ──────────────────────────────────────────────────

    def set_kill_switch(
        self, process_id: str, enabled: bool, actor: Any,
    ) -> ProcessDefinition:
        """Flip the ``kill_switch`` boolean. Actor holds ``ai:operator`` or
        ``ai:process_owner``."""
        if not has_any_capability(
            actor, {AI_OPERATOR.key, AI_PROCESS_OWNER.key}
        ):
            raise RegistryPermissionError(
                "Setting the kill switch requires the ai:operator or ai:process_owner capability."
            )
        current = self._get(process_id)
        doc = dict(current.definition or {})
        doc["kill_switch"] = bool(enabled)
        current.definition = doc
        current.save()
        return current

    def is_killed(self, process_id: str) -> bool:
        """Read helper for the ``kill_switch`` boolean in the definition."""
        current = self._get(process_id)
        return bool((current.definition or {}).get("kill_switch", False))
