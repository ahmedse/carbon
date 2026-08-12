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
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


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

    # ── Domain-specific operations ───────────────────────────────────
    # Each domain defines its own operations here.
    # Platform operations (DQ, NL query, anomaly, etc.) live in protocol.py.
    #
    # Example for emissions domain:
    #
    # @abstractmethod
    # def calculate_footprint(
    #     self, activity_data: list[dict[str, Any]]
    # ) -> FootprintResponse: ...
    #
    # @abstractmethod
    # def suggest_reduction(
    #     self, current_footprint: dict[str, Any]
    # ) -> ReductionResponse: ...


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
