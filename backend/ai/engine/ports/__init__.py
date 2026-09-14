"""Pulse engine ports — the typed seam the engine calls, the host implements.

P2-01 deliverable.  This package defines **Protocols only** (method shapes +
docstrings, zero implementation).  The engine depends on these structural
types; the host supplies concrete adapters over Django + ``scope_q()`` in
P2-02, and the 14+ engine files that today import ``ai.models.*`` are migrated
onto these ports in P2-03.

Why these exist (the boundary contract — see INVARIANTS.md I1/I2/L1/L2 and
PULSE-MASTER.md §2):

* **RULE_6 / D1** — the engine holds no durable state and never commits it
  directly.  Cognitive state (episodic, long-term, ledger, working memory) and
  business effects (mutations) are *requested* through these ports; the host
  persists and executes.
* **RULE_20 / L2** — ``engine/`` imports nothing from ``catalog/mdm/dq/…`` or
  ``ai.models``.  Ports are the only downward-facing surface; they import only
  stdlib and sibling ``engine.*`` types.
* **RULE_21 / L3** — no auto-mutation.  Effects flow through
  :class:`~ai.engine.ports.actions.HostActions` as an ``ActionProposal``; the
  host command boundary applies consent, budget, PDP, and idempotency before
  any write.

The ten Protocols:

===============  ============================================================
Protocol         Role
===============  ============================================================
``Clock``        time source (deterministic under replay)
``DomainPack``   domain vocabulary/catalog/processes/skills/triggers/prompts (P2-08)
``EpisodicStore``  event memory + causal chains + decay
``LongTermStore``  durable fact memory (dedup / contradiction / supersede)
``OrgMemory``    org-scoped long-term memory seeds
``SkillStore``   skill CRUD + promotion-state transitions
``LedgerSink``   per-stage turn audit trail (S6)
``EventBus``     transient pub/sub event transport
``ProcessRegistry``  process / run / journal registry (P3 process machine)
``PolicyDecisionPoint``  authorization decision (default-deny, fail-closed)
``HostActions``  host-effect execution (mutations, read-only actions)
===============  ============================================================
"""

from ai.engine.ports.actions import ActionOutcome, ActionProposal, HostActions
from ai.engine.ports.clock import Clock
from ai.engine.ports.cognition import SweepRunStore
from ai.engine.ports.domain import DomainPack
from ai.engine.ports.events import EventBus
from ai.engine.ports.evidence import EvidenceStore
from ai.engine.ports.kg import EdgeRecord, KnowledgeGraphStore, NodeRecord
from ai.engine.ports.knowledge import KnowledgeEntityStore
from ai.engine.ports.ledger import LedgerSink
from ai.engine.ports.memory import (
    EpisodeRecord,
    EpisodicStore,
    FactRecord,
    LongTermStore,
    MemorySeed,
    OrgMemory,
)
from ai.engine.ports.policy import Decision, PolicyDecision, PolicyDecisionPoint
from ai.engine.ports.preferences import UserPreferenceStore
from ai.engine.ports.process import ProcessRecord, ProcessRegistry, RunRecord
from ai.engine.ports.skills import SkillRecord, SkillStore
from ai.engine.ports.watches import UserWatchStore, WatchRecord

__all__ = [
    "Clock",
    "DomainPack",
    "EpisodicStore",
    "LongTermStore",
    "OrgMemory",
    "SkillStore",
    "LedgerSink",
    "EventBus",
    "ProcessRegistry",
    "PolicyDecisionPoint",
    "HostActions",
    "KnowledgeGraphStore",
    "UserWatchStore",
    "KnowledgeEntityStore",
    "SweepRunStore",
    "EvidenceStore",
    "UserPreferenceStore",
    # supporting data types
    "ActionProposal",
    "ActionOutcome",
    "EpisodeRecord",
    "FactRecord",
    "MemorySeed",
    "Decision",
    "PolicyDecision",
    "ProcessRecord",
    "RunRecord",
    "SkillRecord",
    "NodeRecord",
    "EdgeRecord",
    "WatchRecord",
]
