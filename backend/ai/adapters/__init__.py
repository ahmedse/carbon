"""Host adapters implementing the engine ports over Django + ``scope_q()``.

P2-02a-c deliverable.  The ``ai.engine.ports`` package defines structural
Protocols only; these adapters are the concrete host-side implementations that
persist cognitive state and business effects behind the tenant-scoped
``ai.store`` session, applying ``scope_q()`` to every read so cross-tenant /
cross-user data never leaks (RULE_20 / L2 — the engine stays free of Django
models).
"""

from ai.adapters.cognition import DjangoSweepRunAdapter
from ai.adapters.evidence import DjangoEvidenceAdapter
from ai.adapters.kg import DjangoKGAdapter
from ai.adapters.knowledge import DjangoKnowledgeEntityAdapter
from ai.adapters.memory import (
    DjangoEpisodicAdapter,
    DjangoLongTermAdapter,
    DjangoOrgMemoryAdapter,
)
from ai.adapters.ledger import DjangoLedgerAdapter
from ai.adapters.preferences import DjangoUserPreferenceAdapter
from ai.adapters.skills import DjangoSkillAdapter
from ai.adapters.watches import DjangoWatchAdapter

__all__ = [
    "DjangoEpisodicAdapter",
    "DjangoLongTermAdapter",
    "DjangoOrgMemoryAdapter",
    "DjangoLedgerAdapter",
    "DjangoSkillAdapter",
    "DjangoKGAdapter",
    "DjangoWatchAdapter",
    "DjangoKnowledgeEntityAdapter",
    "DjangoSweepRunAdapter",
    "DjangoEvidenceAdapter",
    "DjangoUserPreferenceAdapter",
]
