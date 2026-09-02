"""Host Adapter contract (Pulse 0.3 — Wave E).

``HostAdapterContract`` is the typed seam between the AI engine/assembler and
the host platform's durable data.  The engine receives expertise through this
contract, never through direct ORM imports above ``ai/adapter/``.

``CarbonHostAdapter`` is *one* implementation; a Nibras/GOFSCO deployment may
supply its own adapter or reuse the registry-driven default.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ai.adapter.types import MemorySeed, SessionContext, ToolCatalog, WorldModel


class HostAdapterContract(ABC):
    """Abstract host adapter — the four-method expert seam.

    The four abstract methods below are the public contract.  Concrete adapters
    (e.g. ``CarbonHostAdapter``) additionally expose the context-retrieval seam
    that ``ai.context_assembler`` delegates its ORM access to:

        ``resolve_mentions``, ``retrieve_long_term_memory``,
        ``retrieve_knowledge_graph``, ``build_user_profile``, and
        ``user_memory_enabled``.
    """

    @abstractmethod
    def get_world_model(self) -> WorldModel:
        """Return the registry-driven typed world model (entities, vocabulary)."""
        ...

    @abstractmethod
    def get_tool_catalog(self, user: Any, scope: Any) -> ToolCatalog:
        """Return the per-user, per-scope tool catalog."""
        ...

    @abstractmethod
    def assemble_context(
        self, query: str, user: Any, scope: Any, page_context: Any
    ) -> SessionContext:
        """Assemble a typed session context for a turn."""
        ...

    @abstractmethod
    def get_org_memory_seeds(self, instance_id: str) -> list[MemorySeed]:
        """Return org-scoped long-term memory seeds for an instance."""
        ...
