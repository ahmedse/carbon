# Pulse — Invariants & Anti-Drift Laws (Recovered)

> **Status:** CANONICAL · **Owner:** Master Architect · **Source of truth for:** P0-01
> Recovered verbatim from `PULSE-MASTER.md` §7 (I1–I8) and `PULSE-0.2-ROADMAP.md` ("seven anti-drift
> laws", L1–L7). This file exists so no worker has to hunt for the rails; each invariant carries a
> **status** and the **files that currently violate it** (per the two audits, held constant in
> `PULSE-UNIFIED-REMEDIATION-PLAN.md`).

**Status legend:** `HELD` = enforced today · `PARTIAL` = partly enforced / bypasses exist ·
`VIOLATED` = broken in code today. A task that widens a violation is rejected in review.

---

## Invariants I1–I8 (PULSE-MASTER §7)

| # | Invariant | Status | Currently violated by |
|---|-----------|--------|-----------------------|
| **I1** | `engine/` imports nothing from Carbon domain apps (RULE_20) | **VIOLATED** | 14+ engine files import `ai.models.*` (e.g. `knowledge_graph/store.py`, `knowledge/store.py`, `cache_store.py`, `feedback.py`, `proactive/user_watches.py`, `cognition/turn/execute.py`, `cognition/turn/ledger.py`, `cognition/loop.py`, `cognition/monitors.py`, `runner.py`). Fix = P2-03 (ports). |
| **I2** | `engine/` writes no durable state (RULE_6); persistence only through Carbon stores | **PARTIAL** | Engine still owns durable writes (own store seam, `engine/core/database.py`, engine memory modules). Reworded by **D1**: engine may *author* writes via ports; host adapters persist. Full fix = P2-01/P2-02 ports + adapters. |
| **I3** | Every mutation is staged + confirmed (RULE_21); no tool writes host state without a consent gate | **PARTIAL** | Worker fan-out bypass (`agent/workers.py`), skill-promotion bypass (`skills/registry.py`, `skills/crud.py`), dead `MutationGuard` (`ai/guards.py`). Fix = P1-06/P1-07/P2-06. |
| **I4** | Every AI call carries a `Scope`; cross-org/cross-app data never leaks (RULE_20) | **VIOLATED** | `DjangoStore._apply_tenancy_filter` is a no-op. Fix = P1-11. |
| **I5** | User-facing text describes outcomes, never internals (RULE_23) | **PARTIAL** | Cognition leaks hardcoded Carbon/DQ/GHG vocabulary (`turn/intent.py`, `plan/loop.py`, `planner.py`, `turn/execute.py`, `proactive/delivery.py`, `insight_generator.py`, `core/config.py`). Fix = P2-08 domain pack. |
| **I6** | New capability = register a tool/plugin/skill, never edit the six-witness spine or add a Django app | **HELD** | — |
| **I7** | Every change ships terminal proof + a regression test; every bug fix adds a playbook entry | **PARTIAL** | Process discipline; enforced by `definition-of-done.md` + CI gates. |
| **I8** | Stable system-prompt prefix stays at the front of every LLM call (RULE_25) | **HELD** | — |

---

## Anti-drift laws L1–L7 (PULSE-0.2-ROADMAP)

| # | Law | Status | Currently violated by |
|---|-----|--------|-----------------------|
| **L1** | No new durable state in `engine/`; persist through a Carbon store, never a module global/file | **PARTIAL** | Same as I2. Engine store seam + module-level state (short-term/working/notifier are in-process dicts). |
| **L2** | No upward imports; `engine/` never imports `catalog/mdm/dq/emissions/accounts/core` | **VIOLATED** | Same as I1. |
| **L3** | No auto-mutation; every write staged + confirmed | **PARTIAL** | Same as I3. |
| **L4** | Grow the periphery, freeze the spine | **HELD** | — |
| **L5** | Prove it end-to-end (a real request produces the real effect), not just a unit test | **PARTIAL** | Discipline; enforced per-phase by acceptance artifacts. |
| **L6** | No stubs left "for later"; dead path → make live or delete | **PARTIAL** | Dead-code register in `PULSE-UNIFIED-REMEDIATION-PLAN.md` §5.2 (19 files already removed; remaining items mapped to P1-15/P6-07/P7-10). |
| **L7** | Telemetry or it didn't happen (counter/ledger row proves learn/deliver/escalate) | **PARTIAL** | Ledger exists but usage accounting is incomplete (LLM accounting = P1-08). |

---

## How these are enforced

| Mechanism | Invariants covered | Status |
|-----------|--------------------|--------|
| `import-linter` (engine boundary) | I1, L2 | report-only P0-08 → enforcing P2-04 |
| Fail-open regex lint | I3, L3 | P1-13 |
| Startup store config check | I2, L1 | P1-01 |
| Forbidden-domain-term grep over `engine/**` | I5 | P2-08 |
| Red-team suite | I3, I4 | P1-17 |
| `vulture` dead-code gate | L6 | P0-08 → strict P7-10 |
| Business-process evals | I7, L5, L7 | P4-09 |
| `verify.sh` (import boundary + anti-patterns) | I1, I6, L2, L4 | existing |

---

## Notes

1. **D1 reword** (from `PULSE-UNIFIED-REMEDIATION-PLAN.md` §1.2): I2 is rewritten as —
   *"Engine holds no process-lifetime state and never commits durable state directly; all
   persistence and all effects go through host-implemented ports."* Cognitive state (episodic,
   ledger, working memory) → engine calls a *port*, host adapter persists. Business effects →
   engine emits an `ActionProposal`, host command boundary executes.
2. Docs that repeat the old wording ("holds NO memory / stores NO graphs", "five mandatory guards",
   "strong reasoning lane", "Pulse Console `/ai/console`") are reconciled at every phase gate (§5.3).
