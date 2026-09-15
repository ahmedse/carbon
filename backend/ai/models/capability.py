"""Django model for durable capability contracts — :class:`Capability` (P3-01).

A capability is the registry row for one governed host action, loaded from the
domain pack's ``api_catalog.yaml`` ``capabilities:`` list via the DomainPack
port (:func:`ai.engine.ports.domain.load_domain_pack`). This module is
**host-side**: it may import engine *ports* (allowed by RULE_20 / ADR-0007),
but the engine never imports it.

Host-action resolution (the "loader fails if the referenced host action doesn't
exist" rule)
-----------------------------------------------------------------------------
Each capability declares a ``host_action`` string. The loader resolves it
against :mod:`ai.capability_registry` — a host-side, import-free mapping of
``host_action`` key → fully-qualified callable path (``"module:qualname"``) or
the human-task sentinel. Resolution is lazy (``importlib``) so importing this
module never imports ``dq`` / ``ai.predicates`` and cannot create a cycle; it
also performs no database access at import time.

Why a dedicated registry (not the engine tool catalog): the engine agent tools
(``ai.engine.agent.tools.get_tool_definitions``) and the domain tool catalogs
(``ai.domain.*.get_tools``) enumerate *agent-facing tools* (``search_knowledge``,
``create_dq_rule``, …), whereas a capability names a *governed host action* the
command boundary executes (``dq.rule.validate``, ``dq.rule.publish``, …). Those
two namespaces are deliberately distinct, so a host registry is the cleanest
non-circular resolution point — the single source of truth both the P3-02
contracts and the P3-03 process validator consume.

An unknown ``host_action`` (not in the registry, or an unimportable callable)
raises :class:`CapabilityValidationError` — fail-closed, never a silent skip.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import models

from ai.capability_registry import HUMAN_TASK_SENTINEL, HOST_ACTION_REGISTRY

from .base import AppScopeMixin, generate_uuid

# Capability kinds (Text, documented not enforced by a DB constraint).
KIND_READ_ONLY = "read_only"
KIND_HUMAN_TASK = "human_task"
KIND_MUTATION = "mutation"
KIND_ASSERTION = "assertion"
VALID_KINDS = frozenset(
    {KIND_READ_ONLY, KIND_HUMAN_TASK, KIND_MUTATION, KIND_ASSERTION}
)

# Fields copied verbatim from an unsaved instance during ``sync_capabilities``.
_SYNC_FIELDS = (
    "business_name",
    "purpose",
    "kind",
    "inputs",
    "preconditions",
    "permissions",
    "effects",
    "side_effects",
    "approval_requirements",
    "requires_confirmation",
    "idempotency",
    "verification",
    "failure_semantics",
    "recovery",
    "owner",
    "version",
    "host_action",
)


class CapabilityValidationError(ValueError):
    """Raised when a capability spec references an unknown host action."""


def default_pack_dir() -> Path:
    """Return the active brand's domain pack directory (host resolves brand → dir).

    Resolves the brand → instance id via :func:`ai.instance_registry.resolve_instance_id`
    (``domain_packs/<instance_id>``, e.g. ``nibras`` under ``DJANGO_BRAND=nibras``)
    and falls back to the Carbon pack when the brand has no pack directory. The
    import is local so this module holds no import-time brand/Django coupling.
    """
    from ai.instance_registry import resolve_instance_id

    root = Path(settings.BASE_DIR).parent / "domain_packs"
    instance_dir = root / resolve_instance_id()
    if instance_dir.is_dir():
        return instance_dir
    return root / "carbon"


def resolve_host_action(host_action: str) -> Any:
    """Resolve a ``host_action`` key to its host callable (or the sentinel).

    Fail-closed: an unregistered key or an unimportable ``"module:qualname"``
    path raises :class:`CapabilityValidationError`.
    """
    target = HOST_ACTION_REGISTRY.get(host_action)
    if target is None:
        raise CapabilityValidationError(
            f"Unknown host_action {host_action!r} — not in the host action "
            f"registry. Registered: {sorted(HOST_ACTION_REGISTRY)}"
        )
    if target == HUMAN_TASK_SENTINEL:
        return target

    module_name, _, qualname = target.partition(":")
    if not module_name or not qualname:
        raise CapabilityValidationError(
            f"Malformed host_action target {target!r} for {host_action!r} "
            "(expected 'module:qualname')"
        )
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:  # pragma: no cover - depends on host module set
        raise CapabilityValidationError(
            f"Host action {host_action!r} references unimportable module "
            f"{module_name!r}"
        ) from exc
    obj: Any = module
    for part in qualname.split("."):
        obj = getattr(obj, part, None)
        if obj is None:
            raise CapabilityValidationError(
                f"Host action {host_action!r} references missing attribute "
                f"{qualname!r} on {module_name!r}"
            )
    return obj


def iter_capability_specs(pack: Any = None) -> list[dict[str, Any]]:
    """Return the raw capability specs from a DomainPack (or the default pack)."""
    if pack is None:
        from ai.engine.ports.domain import load_domain_pack

        pack = load_domain_pack(default_pack_dir())
    catalog = pack.api_catalog() or {}
    specs = catalog.get("capabilities") or []
    return [spec for spec in specs if isinstance(spec, dict)]


class Capability(AppScopeMixin):
    """A durable capability contract (one governed host action).

    Inherits :class:`AppScopeMixin` for CBAC partitioning; ``id`` is a UUID
    string pk via ``generate_uuid``; ``capability_id`` is the unique contract
    key (e.g. ``dq.rule.validate``).
    """

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)

    capability_id = models.TextField(unique=True)
    business_name = models.TextField(default="")
    purpose = models.TextField(default="")
    kind = models.TextField(default=KIND_READ_ONLY, db_index=True)
    inputs = models.JSONField(default=dict)
    preconditions = models.JSONField(default=dict)
    permissions = models.JSONField(default=dict)
    effects = models.JSONField(default=dict)
    side_effects = models.JSONField(default=dict)
    approval_requirements = models.JSONField(default=dict)
    requires_confirmation = models.BooleanField(default=False)
    idempotency = models.TextField(default="")
    verification = models.JSONField(default=dict)
    failure_semantics = models.TextField(default="")
    recovery = models.TextField(default="")
    owner = models.TextField(default="")
    version = models.TextField(default="")
    host_action = models.TextField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"
        ordering = ["capability_id"]
        indexes = [
            models.Index(
                fields=["kind", "owner"],
                name="ai_capability_lookup_idx",
            ),
        ]

    def __repr__(self) -> str:
        return (
            f"<Capability id={self.id!r} capability_id={self.capability_id!r} "
            f"kind={self.kind!r} host_action={self.host_action!r}>"
        )

    @classmethod
    def from_spec(
        cls, spec: dict[str, Any], *, validate: bool = True,
    ) -> "Capability":
        """Build an (unsaved) Capability from a pack spec, validating it.

        ``validate=True`` resolves ``host_action`` fail-closed (raises
        :class:`CapabilityValidationError` on an unknown host action).
        """
        capability_id = spec.get("capability_id") or spec.get("id")
        if not capability_id:
            raise CapabilityValidationError("Capability spec missing 'capability_id'")
        host_action = spec.get("host_action")
        if not host_action:
            raise CapabilityValidationError(
                f"Capability {capability_id!r} missing 'host_action'"
            )
        kind = spec.get("kind", KIND_READ_ONLY)
        if kind not in VALID_KINDS:
            raise CapabilityValidationError(
                f"Capability {capability_id!r} has invalid kind {kind!r} "
                f"(expected one of {sorted(VALID_KINDS)})"
            )
        if validate:
            resolved = resolve_host_action(str(host_action))
            if resolved == HUMAN_TASK_SENTINEL and kind != KIND_HUMAN_TASK:
                raise CapabilityValidationError(
                    f"Capability {capability_id!r} resolves to the human-task "
                    f"sentinel but declares kind {kind!r} (must be 'human_task')"
                )
        return cls(
            capability_id=str(capability_id),
            business_name=str(spec.get("business_name") or ""),
            purpose=str(spec.get("purpose") or ""),
            kind=kind,
            inputs=spec.get("inputs") or {},
            preconditions=spec.get("preconditions") or {},
            permissions=spec.get("permissions") or {},
            effects=spec.get("effects") or {},
            side_effects=spec.get("side_effects") or {},
            approval_requirements=spec.get("approval_requirements") or {},
            requires_confirmation=bool(spec.get("requires_confirmation", False)),
            idempotency=str(spec.get("idempotency") or ""),
            verification=spec.get("verification") or {},
            failure_semantics=str(spec.get("failure_semantics") or ""),
            recovery=str(spec.get("recovery") or ""),
            owner=str(spec.get("owner") or ""),
            version=str(spec.get("version") or ""),
            host_action=str(host_action),
        )


def load_capabilities(pack: Any = None) -> list[Capability]:
    """Read capabilities from a DomainPack and build validated (unsaved) rows.

    Tolerates a :class:`~ai.engine.ports.domain.NeutralDomainPack` (empty
    catalog → empty list, no error).
    """
    return [Capability.from_spec(spec) for spec in iter_capability_specs(pack)]


def sync_capabilities(pack: Any = None) -> list[Capability]:
    """Persist capabilities idempotently (upsert by ``capability_id``)."""
    saved: list[Capability] = []
    for cap in load_capabilities(pack):
        defaults = {field: getattr(cap, field) for field in _SYNC_FIELDS}
        obj, _ = Capability.objects.update_or_create(
            capability_id=cap.capability_id, defaults=defaults,
        )
        saved.append(obj)
    return saved
