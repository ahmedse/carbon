# ADR 0009 — Pulse Engine Is a Stateful Monolith: Vendor Whole + Swap Persistence Seam

- **Status:** Accepted
- **Date:** 2026-08-12
- **Deciders:** Master Architect (resolving backend-worker blocker)
- **Area:** backend (AI layer)

## Context
Phase 1 originally specced vendoring a "stateless engine subset." The backend worker
traced the real import surface and found that `core/models.py` is a 1057-line SQLAlchemy
`DeclarativeBase` with ~30 tables — the entire Pulse DB. Worse, the files assumed to be
"stateless" (`agent/reasoning.py`, `agent/guardrails.py`, `agent/tools.py`, `llm/router.py`,
`llm/prompts.py`, `cognition/turn/runner.py`) all write to the DB via
`get_session_factory()` / `.add()` / `.commit()` / `select()`. The engine is a stateful
monolith: the orchestration core is exactly the part that persists.

## Decision
1. **There is no "clean stateless subset" that is also a usable engine.** Cherry-picking
   stateless leaves (workers, provider, witnesses, etc.) yields files with no orchestrator.
   Stop trying to split on "stateless vs stateful" by file.
2. **Phase 1 vendors the FULL engine IN-HAND and INERT.** Copy the whole source tree
   (`agent/`, `llm/`, `cognition/`, `core/`, `memory/`, `knowledge/`, `knowledge_graph/`,
   `ingestion/`, `proactive/`, `archetypes/`, `skills/`) verbatim, rewriting only
   intra-package import roots. Do NOT wire to Django, create migrations, import from
   Django, or execute anything. No second DB is created because nothing runs.
3. **Phase 2 swaps the persistence seam.** Replace `core/database.py` (SQLAlchemy session
   factory) with a `Store` interface; re-model `core/models.py` tables as Django models in
   `backend/ai/models/`; provide in-memory (per-task working memory) + Django ORM (durable,
   CBAC-partitioned) implementations. This is what actually makes the engine stateless and
   Carbon-owned. `sqlalchemy` is a temporary dependency until this swap.

## Alternatives Considered
- **Vendor the worker's "clean subset"** — rejected: the subset is not a working engine
  (its orchestrators still hit the DB), and it omits the reasoning core.
- **Vendor whole + keep SQLAlchemy DB co-located** — rejected: two persistence stacks in
  one repo, CBAC can't reach raw SQLAlchemy, violates RULE_6/ADR-0007.
- **Port everything to Django in one phase** — rejected: too big for one session; the
  inert-vendor-then-seam-swap split is lower risk.

## Consequences
- **Positive:** Pulse is genuinely in-hand in one cheap, reversible step; the risky
  re-modeling is isolated to Phase 2.
- **Negative / trade-off:** Phase 1 lands code that is not yet executable (inert); the
  seam swap in Phase 2 is the real engineering effort.
- **Do NOT re-try:** splitting the vendor by "stateless vs stateful file"; a second
  co-located SQLAlchemy DB.

## References
- `.ai-toolkit/decisions/0007-pulse-inhand-stateless-engine.md`
- `.ai-toolkit/decisions/0008-pulse-packaging-portability.md`
- `plans/TASKS-PULSE-VENDOR-PHASE-1-ENGINE.md`
- `plans/TASKS-PULSE-VENDOR-PHASE-2-KNOWLEDGE.md`
