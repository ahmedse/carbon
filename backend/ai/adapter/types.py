"""Pure dataclasses for the Host Adapter seam (Pulse 0.3 — Wave E).

ZERO Django imports: this module must import and instantiate with no Django
settings configured, e.g. ``python -c "import ai.adapter.types"``.  It depends
only on the standard library, so the engine/assembler can be type-checked and
unit-tested without a live Django DB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EntityDef:
    """A typed entity the host world model knows about (table, rule, org…)."""

    entity_type: str
    name: str
    description: str = ""
    attributes: list[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class VocabularyTerm:
    """A domain term plus its plain-language definition."""

    term: str
    definition: str = ""
    synonyms: list[str] = field(default_factory=list)


@dataclass
class BusinessRule:
    """A host business rule the model must respect when answering."""

    rule: str
    category: str = ""
    source: str = ""


@dataclass
class WorldModel:
    """The typed, registry-driven snapshot of what the host knows."""

    entities: list[EntityDef] = field(default_factory=list)
    vocabulary: list[VocabularyTerm] = field(default_factory=list)
    business_rules: list[BusinessRule] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)


@dataclass
class ToolDef:
    """A typed tool entry (E2 enriches this with CBAC metadata)."""

    id: str
    description: str = ""
    required_capability: str | None = None
    is_mutation: bool = False
    domain: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_description: str = ""


@dataclass
class ToolCatalog:
    """A per-user, per-scope collection of tools."""

    tools: list[ToolDef] = field(default_factory=list)


@dataclass
class SessionContext:
    """Typed output of context assembly (mirrors ``assemble_context`` dict)."""

    messages: list[dict[str, Any]] = field(default_factory=list)
    budget: dict[str, int] = field(default_factory=dict)
    kg_entities: list[dict[str, Any]] = field(default_factory=list)
    context_signature: str = ""


@dataclass
class MemorySeed:
    """A durable long-term fact exposed as an org memory seed."""

    category: str
    content: str
    source: str = ""
    confidence: float = 1.0
