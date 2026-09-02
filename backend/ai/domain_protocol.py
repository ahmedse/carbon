"""
Carbon AI Intelligence — Domain Protocol

AI CONTRACT §8: Domain apps register their AI operations here.
Each domain app gets its own module in ai/domain/{app}.py.

Platform AI (protocol.py) = operations common to ALL apps (DQ, NL query, anomaly, etc.)
Domain AI (this module)    = operations scoped to a single domain app.

Architecture:
    ai/protocol.py          — PlatformAIOperations ABC (all-domain operations)
    ai/domain_protocol.py   — DomainAIOperations ABC (this file)
    ai/domain/emissions.py  — EmissionsDomainAI (carbon footprint domain)
    ai/domain/water.py      — WaterDomainAI (future)
    ai/domain/waste.py      — WasteDomainAI (future)

NEVER import domain-specific code into platform-level code.
NEVER cross-reference domain modules.

─────────────────────────────────────────────────────────────
MANIFEST CONTRACT (v4, 2026-08-16)
─────────────────────────────────────────────────────────────
Every DomainAIOperations subclass is ALSO the AI manifest for its domain app.
The manifest layer (class attributes + instance methods below) is what the
platform uses to:

  1. Surface the right entry-point buttons on domain app pages.
  2. Render context-aware starter chips in the AI workspace empty state.
  3. Validate task_payload before dispatch (fail-fast, clear error).
  4. Inject domain-specific T1 context (WorkspaceContext enrichment).
  5. Serve the frontend via GET /carbon-api/ai/apps/{app_identifier}/.

Adding a NEW domain app AI capability = write ai_manifest in your domain class.
Zero changes to the platform AI workspace code required.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ai.adapter.types import ToolDef


# ── Domain AI Operation Base ─────────────────────────────────────────────

@dataclass
class DomainContext:
    """Context injected into every domain AI call.

    Unlike platform Scope, DomainContext carries domain-specific enrichment:
      - domain_knowledge: domain-specific vocabulary, units, and business rules
      - domain_config: domain-specific thresholds, conversion factors, etc.
    """

    app_identifier: str                              # "emissions", "water", etc.
    domain_knowledge: dict[str, Any] = field(default_factory=dict)
    domain_config: dict[str, Any] = field(default_factory=dict)


class DomainAIOperations(ABC):
    """ABC for domain-specific AI operations.

    Each domain app module (e.g. emissions.py) implements this ABC.
    The platform CarbonIntelligence delegates domain calls to the
    appropriate DomainAIOperations implementation.

    KEY RULES (ai-contract.md §8):
      1. Domain operations NEVER access another domain's data.
      2. Domain operations inherit the platform Scope + app_identifier.
      3. Domain providers may differ from platform providers.
      4. Domain operations go through the same guard chain.
    """

    @property
    @abstractmethod
    def app_identifier(self) -> str:
        """The domain app this implementation belongs to.

        Must match a key in DataIsolationGuard.DOMAIN_TABLES.
        """
        ...

    @property
    @abstractmethod
    def app_display_name(self) -> str:
        """Human-readable name: "Carbon Footprint", "Water Management", etc."""
        ...

    @abstractmethod
    def get_domain_context(self) -> DomainContext:
        """Return domain-specific context (knowledge, config, vocabulary).

        Called once per session. Cached by CarbonIntelligence.
        """
        ...

    # ── Manifest Layer ────────────────────────────────────────────────────
    # Class-level attributes — override in every concrete domain class.
    # These drive the frontend manifest API and the AI workspace UI.

    # Task types this domain supports. Platform base types available:
    # chat | dq_validate | dq_suggest | nl_query | anomaly | investigate |
    # nl_rule_test | report_draft
    supported_task_types: list[str] = []

    # Entry points: buttons rendered on this domain's pages.
    # Schema: [{label, task_type, on_entity, icon}]
    # "on_entity" controls which entity types cause the button to appear and
    # must be a concrete type the domain owns ("table"|"module"|"entity"|
    # "user"|"policy"). The "*" wildcard is forbidden: it leaks a domain's
    # actions onto every page, including pages of unrelated domains.
    entry_points: list[dict[str, str]] = []

    # Context-aware starter prompts for the empty state.
    # Keys: entity_type ("table"|"module"|"default"). Values: list of
    # {label, prompt, task_type}. "@{entity_name}" in prompt is replaced.
    starter_prompts: dict[str, list[dict[str, str]]] = {}

    # Injected verbatim as the last paragraph of the T0 system prompt.
    # Use to give domain vocabulary, units, and business rules.
    system_prompt_extension: str = ""

    # Phase 22-A — optional per-domain default model (stable ModelCatalog
    # ``model_id`` slug, e.g. "gpt-4o-mini").  This is the "domain manifest"
    # tier of the turn-time model resolution order:
    #
    #     system default → domain manifest → user profile → per-message override
    #
    # Empty string = "no opinion" → the next tier (user profile / system
    # default) decides.  Never overrides the user's profile default or a
    # per-message model pick.
    default_model_id: str = ""

    # ── Manifest instance methods ─────────────────────────────────────────

    def build_workspace_context(
        self, user: Any, entity_type: str | None, entity_id: str | None
    ) -> dict[str, Any]:
        """Return domain-specific context injected into T1 (workspace tier).

        Override to enrich the context with live domain data (e.g. row counts,
        module scope, recent calculations). Keep results small (<200 tokens).
        Default: empty dict (no enrichment).
        """
        return {}

    def validate_task_payload(
        self, task_type: str, payload: dict[str, Any]
    ) -> tuple[bool, str]:
        """Validate task_payload before dispatch.

        Return (True, "") on success; (False, <reason>) on validation failure.
        Called by CarbonIntelligence before every send_message / send_message_stream.
        Default: always passes.
        """
        return True, ""

    def to_manifest_dict(self) -> dict[str, Any]:
        """Serialize the manifest for the GET /ai/apps/{id}/ API endpoint."""
        return {
            "app_identifier": self.app_identifier,
            "display_name": self.app_display_name,
            "supported_task_types": self.supported_task_types,
            "entry_points": self.entry_points,
            "starter_prompts": self.starter_prompts,
            "system_prompt_extension": bool(self.system_prompt_extension),  # never leak the full text
        }

    # ── Tool catalog (Pulse 0.3 — Phase E2) ──────────────────────────────

    def get_tools(self) -> list[ToolDef]:
        """Return the domain's typed tool catalog (``list[ToolDef]``).

        Each tool declares:

          * ``id``             — ``"{app_identifier}.{action}"`` where ``action``
                                is the matching ``call_host_api`` endpoint name.
          * ``description``    — non-empty, human-readable.
          * ``required_capability`` — a real key in ``ALL_CAPABILITIES``
                                (``accounts.capabilities``) or ``None`` for an
                                always-available tool.
          * ``is_mutation``    — ``True`` only for POST/PUT/DELETE tools.
          * ``input_schema``   — ``{"type": "object", "properties": {...}}``.

        Advisory/manifest-only domains (finance/hr/customer/people, and any
        domain with no ``call_host_api``-backed data tools) return ``[]``.
        """
        return []

    # ── Abstract required fields (unchanged from original contract) ────────


# ── Domain Registration ──────────────────────────────────────────────────
# AI CONTRACT §8 Step 3: Register domain implementation here.

# Registry of domain AI implementations.
# Populated by each domain module's register() call.
_DOMAIN_REGISTRY: dict[str, type[DomainAIOperations]] = {}


def register_domain(app_identifier: str, cls: type[DomainAIOperations]) -> None:
    """Register a domain AI implementation.

    Called at the bottom of each ai/domain/{app}.py module.

    Raises ValueError if app_identifier is already registered (no duplicates).
    """
    if app_identifier in _DOMAIN_REGISTRY:
        raise ValueError(
            f"Domain '{app_identifier}' is already registered. "
            f"Existing: {_DOMAIN_REGISTRY[app_identifier].__name__}. "
            f"Attempted: {cls.__name__}."
        )
    _DOMAIN_REGISTRY[app_identifier] = cls


def get_domain(app_identifier: str) -> type[DomainAIOperations]:
    """Get a registered domain AI class by app_identifier.

    Raises KeyError if domain is not registered.
    Use has_domain() to check first.
    """
    if app_identifier not in _DOMAIN_REGISTRY:
        raise KeyError(
            f"Domain '{app_identifier}' is not registered. "
            f"Registered domains: {list(_DOMAIN_REGISTRY.keys())}. "
            f"See ai-contract.md §8 for registration steps."
        )
    return _DOMAIN_REGISTRY[app_identifier]


def has_domain(app_identifier: str) -> bool:
    """Check if a domain is registered."""
    return app_identifier in _DOMAIN_REGISTRY


def list_domains() -> list[str]:
    """List all registered domain app identifiers."""
    return list(_DOMAIN_REGISTRY.keys())


def get_manifest(app_identifier: str) -> dict[str, Any]:
    """Return the serialized manifest for a registered domain.

    Raises KeyError if domain is not registered.
    Used by the manifest API endpoint.
    """
    return get_domain(app_identifier)().to_manifest_dict()


def all_manifests() -> list[dict[str, Any]]:
    """Return all registered domain manifests as a list."""
    return [cls().to_manifest_dict() for cls in _DOMAIN_REGISTRY.values()]


# Built-in conversation types that every domain AI conversation may use,
# regardless of which domain manifests are registered. Domain manifests may
# declare additional task types via ``supported_task_types``; those are added
# to the allowed set at runtime by :func:`supported_conversation_types`.
CORE_CONVERSATION_TYPES: frozenset[str] = frozenset(
    {"chat", "dq_validate", "dq_suggest", "nl_query", "anomaly"}
)


def supported_conversation_types() -> frozenset[str]:
    """Return the full set of conversation types the platform accepts.

    This is the union of the built-in core types and every task type declared
    by a registered domain manifest. Keeping this manifest-driven means a new
    domain app can introduce a new conversation type with zero core changes
    (ADR-0010).
    """
    types = set(CORE_CONVERSATION_TYPES)
    for cls in _DOMAIN_REGISTRY.values():
        types.update(cls.supported_task_types)
    return frozenset(types)
