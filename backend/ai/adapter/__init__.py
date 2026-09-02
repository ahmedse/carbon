"""Host Adapter seam (Pulse 0.3 — Wave E).

The Host Adapter is the typed boundary between the AI engine/assembler and the
host platform's durable data (Django ORM, domain registry).  The engine and
``ai.context_assembler`` receive expertise through ``HostAdapterContract``,
never through direct ORM imports above ``ai/adapter/``.

Layout
------
``types.py``    — pure dataclasses, ZERO Django imports.
``contract.py`` — ``HostAdapterContract`` ABC (four abstract methods).
``carbon.py``   — ``CarbonHostAdapter``, the concrete Carbon implementation.

``CarbonHostAdapter`` is *one* implementation; a Nibras/GOFSCO deployment may
supply its own adapter or reuse the registry-driven default.  This package's
``__init__`` deliberately imports only the pure layers (contract + types) so
``python -c "import ai.adapter.types"`` succeeds with no Django settings.
"""

from ai.adapter.contract import HostAdapterContract
from ai.adapter.types import (
    BusinessRule,
    EntityDef,
    MemorySeed,
    SessionContext,
    ToolCatalog,
    ToolDef,
    VocabularyTerm,
    WorldModel,
)

__all__ = [
    "HostAdapterContract",
    "BusinessRule",
    "EntityDef",
    "MemorySeed",
    "SessionContext",
    "ToolCatalog",
    "ToolDef",
    "VocabularyTerm",
    "WorldModel",
]
