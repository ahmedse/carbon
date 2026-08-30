# PULSE — Master Reference (Single Source of Truth)

> **Status:** CANONICAL · **Owner:** Master Architect · **Last audited:** 2026-08-30
> **This document is the single entry point for all Pulse work.** It supersedes the *vision*
> portions of `DESIGN-GENERALIZED-INTELLIGENCE-PULSE-BRAIN.md`, `DESIGN_AI_WORKSPACE_NEXTGEN.md`,
> `DESIGN_AI_WORKSPACE_V4.md`, and `DESIGN_AI_WORKSTATION.md`. Those remain as historical detail;
> when they conflict with this file, **this file wins.**
> The execution plan lives in [`PULSE-0.2-ROADMAP.md`](./PULSE-0.2-ROADMAP.md).
> The experience spec (how Pulse must *feel*) lives in [`PULSE-UX.md`](./PULSE-UX.md).
> The build-level wireframes + component specs live in [`PULSE-UX-DESIGN.md`](./PULSE-UX-DESIGN.md).

---

## 0. What Pulse is (in one paragraph)

Pulse is Carbon's **in-hand reasoning engine** — a host-agnostic cognitive architecture vendored
under `backend/ai/engine/`. It is not a chatbot with a memory bolt-on: it is a **six-witness
reasoning pipeline** wrapped by memory, a knowledge graph, a proactive engine, a learning loop, an
agent/tool layer, and an LLM router. Carbon (`backend/ai/`) owns **all durable state and identity**;
Pulse owns **inference only**. The goal of **Pulse 0.2** is to cross the line from *impressive
assistant* to *true enterprise coworker*: it plans, reasons, remembers, learns, teaches, and is
proactive — while never violating the boundary contract in §2.

**Naming (RULE_23):** the word "Pulse" is an **internal** term. User-facing text always says
"AI" / "the assistant" and describes **outcomes**, never internals. "Pulse" appears only in code,
docs, and admin/observability surfaces.

---

## 1. The eight faculties (the mental model)

A real coworker is a loop over eight faculties, not a prompt. This is the frame every Pulse phase
maps to. (Reference systems: Anthropic Claude + MCP, Cursor, GitHub Copilot agent mode, OpenAI
o-series + memory. Research: CoALA, ReAct, Reflexion, Voyager, Generative Agents, MemGPT.)

| # | Faculty | What it means | Where it lives in code |
|---|---------|---------------|------------------------|
| 1 | **Perception / salience** | Understand meaning + urgency; route reasoning depth | `engine/cognition/turn/salience.py`, `turn/intent.py` |
| 2 | **Memory** | Working, short-term, episodic, semantic — persistent + scoped | `engine/memory/*`, `ai/context_assembler.py` |
| 3 | **Reasoning** | Multi-step plan → execute → observe → replan | `engine/cognition/turn/runner.py`, `cognition/plan/loop.py` |
| 4 | **Action** | Tools with permission, dry-run, consent | `engine/agent/plugins.py`, `agent/tools.py`, MCP |
| 5 | **Grounding / truthfulness** | Never assert what a tool didn't confirm | `engine/cognition/turn/critic.py` (S4) |
| 6 | **Learning / growth** | Turn experience into reusable skills **actually reused** | `cognition/trajectory.py`, `consolidation.py`, `skills/*` |
| 7 | **Metacognition / awareness** | Knows what it knows, its capabilities, its uncertainty | knowledge-gap critic, `list_my_capabilities` |
| 8 | **Proactivity / collaboration** | Notices, warns, mentors — before being asked | `engine/proactive/*` |

---

## 2. The Boundary Contract (NON-NEGOTIABLE — RULE_6)

This is the contract that keeps Pulse a **separate brain**. Violating it is the #1 way to make the
platform unsustainable. Every worker reads this before touching `backend/ai/`.

| Concern | Pulse (`engine/`) owns | Carbon (`ai/` host) owns |
|---------|------------------------|--------------------------|
| Reasoning | ✅ six-witness pipeline, salience, retrieval, draft, critic, execute, ledger | ❌ none |
| Truthfulness gates | ✅ S4 critic, grounding, honest-uncertainty | ❌ none |
| Tool **decision** | ✅ declares which tool + params | — |
| Tool **effect** | — | ✅ owns the actual mutation (DQ rule, memory row, query) |
| Durable state | ❌ **forbidden** | ✅ all models, migrations, PostgreSQL, Redis |
| Memory storage | ✅ *retrieves* in-context (S2) | ✅ owns `MemoryLongTerm`, learn/forget, feedback |
| Identity / auth | ❌ none | ✅ RBAC, org isolation, `GuardChain` |
| Cost / budget | ✅ *requests* budget | ✅ *enforces* token/cost budget |

**Hard rules that gate every Pulse change** (from `.ai-toolkit/project.config.md`):

- **RULE_6** — engine holds **zero durable state**; all persistence is Carbon-owned.
- **RULE_18** — every AI op goes through `CarbonIntelligence`; never call a provider/engine directly.
- **RULE_20** — `engine/` imports **nothing** from `catalog/mdm/dq/emissions/accounts/core`; domain
  apps plug in via `ai/domain/{app}.py`.
- **RULE_21** — **no auto-mutation.** AI suggests, Carbon executes. Mutations are `requires_confirmation=True`.
- **RULE_23** — **no implementation leakage** in user-facing text.

**Integration surfaces (the ONLY allowed touch points between host and engine):**
`ai/intelligence.py` · `ai/providers/pulse.py` · `ai/engine_runtime.py` · `ai/serializers.py` ·
`ai/workspace_api.py`. No other file crosses the seam.

---

## 3. Architecture map (what actually exists — audited 2026-08-30)

```
backend/ai/                      ← Carbon host (durable state, guards, API)
  intelligence.py                ← CarbonIntelligence: THE entry point
  context_assembler.py           ← tiered context (T2 history / T2b summary / T3 KG / T4 memory)
  providers/pulse.py             ← engine adapter seam
  engine/                        ← Pulse (in-process, stateless reasoning)
    cognition/
      turn/                      ← SIX-WITNESS SPINE
        salience.py   (S1)       ← regex router: fast | full | deep
        intent.py     (S1.5)     ← LLM intent classifier + confidence ladder
        retrieve.py   (S2)       ← knowledge + memory context pack
        draft.py      (S3)       ← LLM tool-use draft
        critic.py     (S4)       ← grounding + tenancy + safety + honest-uncertainty
        execute.py    (S5)       ← parallel tool dispatch + streaming
        runner.py     (S6)       ← orchestrates S1..S6 + ledger + synthesis
      plan/loop.py               ← ReAct multi-step loop (phases, consent, replan, resume)
      consolidation.py           ← trajectory → skill candidates (sleep-time)
      trajectory.py              ← append-only run log
      synthesis.py               ← insight synthesis / reflection / decay
      distill/                   ← episodic→semantic distill, promotion, decay
      dialogue/                  ← entity extractor, anaphora, pending-action
    memory/
      short_term.py              ← ⚠ in-process dict (ephemeral)
      working.py                 ← ⚠ in-process dict (entity focus, ephemeral)
      long_term.py               ← Postgres + vector: dedup, contradiction, supersede, decay
      episodic.py                ← Postgres + vector: causal chains, typed decay
    knowledge_graph/             ← nodes/edges (PG + vector + in-memory adjacency), BM25, SQL planner
    proactive/                   ← triggers, insight generator, delivery, suppression
    skills/                      ← SkillRegistry + admission gate (4 critics)
    learning/preferences.py      ← session preference classifier
    agent/                       ← tools.py, plugins.py (ToolPlugin ABC), MCP, orchestrator, budget
    llm/                         ← router (task lanes), provider, prompts, playbook
```

**Task lanes** (`engine/llm/router.py`): `chat` · `deep` · `cognition` · `introspect` · `eval` · `embed`.
Cost is logged per call; a per-instance daily USD budget is enforced.

---

## 4. Maturity scorecard (honest audit, 2026-08-30)

| Faculty | Verdict | Evidence |
|---------|---------|----------|
| 1 Perception | **Solid, shallow** | regex salience + LLM intent ladder; salience not learned |
| 2 Memory | **Strong, half-ephemeral** | long-term/episodic excellent; **short-term + working are in-process dicts (lost on restart, not shared across workers)** |
| 3 Reasoning | **Genuinely strong** | ReAct loop: topological phases, parallel steps, consent pauses, bounded replans, resume |
| 4 Action | **Strong & modern** | plugin ABC, `requires_confirmation`, **MCP dynamic tools**, truthful capability manifest |
| 5 Grounding | **Best-in-class** | S4 critic: grounding + tenancy + safety + `knowledge_gap` → escalate or honest uncertainty; phantom-success guards |
| 6 Learning | **Built but likely COLD** | full pipeline exists, but skills are `gate_status=pending`; planner reads `list_promoted`; **no automatic promotion→reuse arrow** |
| 7 Metacognition | **Partial** | knowledge-gap critic + capability manifest real; no confidence surfaced to user |
| 8 Proactivity | **Built but NOT DELIVERED** | triggers/briefings/drift real, but `proactive/delivery.py` pushes to an **in-process WS registry, not the Django/React UI** |

**Keep (don't lose these differentiators):** the S4 grounding critic, the RULE_21 consent
architecture, MCP support, episodic memory with causal chains, and the learning *gate* machinery.

---

## 5. The five critical gaps (the truth Pulse 0.2 must fix)

1. **G1 — Learning loop is cold.** Consolidation drafts `Skill` rows at `gate_status=pending`;
   `SkillAwarePlanner` only sees `list_promoted`. Experience is *recorded* but never *reused*. This
   is **learning theater** until the promotion→reuse arrow is closed **and observable**.
2. **G2 — Proactivity never reaches the human.** `proactive/delivery.py` → `notifier._subscribers`
   (engine in-process WebSocket), not the Django HTTP/SSE surface the React app consumes. The engine
   "thinks" daily; the user never hears it. **Highest-ROI fix.**
3. **G3 — Ephemeral in-process state.** `short_term.py`, `working.py`, KG `_adjacency`, and
   `notifier._subscribers` are module-level dicts → lost on restart, split-brain under multi-worker.
   The "colleague with amnesia every deploy."
4. **G4 — Dead subsystems.** `detect_performance_drift` is fed `cache_profile.drift_metrics` which is
   "always empty today"; `learned_triggers` seed conditions referencing pseudo-table
   `system_snapshots:<field>` the host-DB evaluator can't query → learned triggers never fire.
5. **G5 — No reasoning lane / adaptive compute.** Router has no o-series/extended-thinking lane
   beyond a single `LLM_ESCALATION_MODEL` on knowledge-gap. No test-time-compute scaling.

---

## 6. Pulse 0.2 — the North Star (Definition of "as it should be")

**Pulse 0.2 is DONE when all eight are true and each is proven by a terminal/telemetry artifact:**

1. **Proactive insights reach the user** in the Carbon UI (notification panel shows real backend
   insights via SSE) — G2 closed.
2. **Continuity survives restart and scales across workers** — short-term/working/subscribers/KG
   adjacency move to Redis; a restarted process resumes the same focus + short-term window — G3 closed.
3. **Learning is real and observable** — a learned skill is promoted through the gate and *reused* on
   the hot path, with a telemetry counter proving reuse — G1 closed.
4. **No dead subsystems** — drift + learned-trigger paths either produce real fired insights or are
   deleted; no inert "impressive-looking" code — G4 closed.
5. **Adaptive reasoning** — a `reason` task lane exists; hard problems escalate to a reasoning model
   with a measured quality delta — G5 closed.
6. **Calibrated awareness** — the assistant surfaces confidence and honest uncertainty to the user
   (metacognition faculty visible) — Faculty 7.
7. **The boundary contract still holds** — zero new upward imports, zero durable state in `engine/`,
   RULE_21 intact (proven by `verify.sh` + an import-boundary check).
8. **It feels alive** — the NGX real-time UX layer (SSE progress, optimistic CRUD, presence,
   skeletons, AI transparency) is delivered on top of the now-connected brain.

**Anti-goals (explicitly NOT Pulse 0.2):** bigger prompts, a second AI database, runtime provider
swapping, autonomous self-mutation of memory/rules, any user-facing "Pulse"/engine jargon.

---

## 7. Invariants every worker must never break

These are the rails. A phase that violates any of these is **rejected in review**, regardless of
tests passing.

- **I1** — `engine/` imports nothing from Carbon domain apps (RULE_20). Enforced by an import-boundary check.
- **I2** — `engine/` writes no durable state (RULE_6). Persistence only through Carbon stores.
- **I3** — every mutation is staged + confirmed (RULE_21). No tool writes host state without a consent gate.
- **I4** — every AI call carries a `Scope`; cross-org/cross-app data never leaks (RULE_20).
- **I5** — user-facing text describes outcomes, never internals (RULE_23).
- **I6** — new capability = register a tool/plugin/skill, **never** edit the six-witness spine or add a Django app.
- **I7** — every change ships terminal proof + a regression test; every bug fix adds a playbook entry.
- **I8** — stable system-prompt prefix stays at the front of every LLM call (cache discipline, RULE_25).

---

## 8. Where to look (file map for workers)

| You need… | Read |
|-----------|------|
| The binding AI contract | `.ai-toolkit/shared/ai-contract.md` |
| Project hard rules | `.ai-toolkit/project.config.md` (RULE_1..26) |
| The reasoning spine | `engine/cognition/turn/runner.py` + `turn/witnesses.py` |
| Multi-step execution | `engine/cognition/plan/loop.py` |
| Memory | `engine/memory/{short_term,working,long_term,episodic}.py` + `ai/context_assembler.py` |
| Proactive engine | `engine/proactive/{loop,trigger_evaluator,delivery,insight_generator}.py` |
| Learning loop | `engine/cognition/{trajectory,consolidation}.py` + `engine/skills/{registry,gate}.py` |
| Tools / plugins | `engine/agent/{tools,plugins}.py` |
| Model routing | `engine/llm/router.py` |
| The execution plan | [`PULSE-0.2-ROADMAP.md`](./PULSE-0.2-ROADMAP.md) |
| How Pulse must **feel** (UI/UX) | [`PULSE-UX.md`](./PULSE-UX.md) |
| Why decisions were made | `.ai-toolkit/decisions/` (ADRs, esp. 0007/0008/0009/0024) |

---

## 8b. The experience (how Pulse must feel)

Architecture is only half of a coworker; the other half is how it *feels* to work with. The full,
detailed UI/UX philosophy and spec is [`PULSE-UX.md`](./PULSE-UX.md) — **canonical for all user-facing
work.** Its non-negotiables in one breath:

- **Crystal clear · storylike · easy · intuitive · robust · highly exceptional** — the five experience
  pillars, each made testable (PULSE-UX §1).
- **Every interaction is a 4-beat story:** acknowledge (<100ms) → think out loud (narrated, human) →
  grounded answer (scoped + provenance + confidence) → carry forward (next action + continuity). No
  dead ends (PULSE-UX §3).
- **Five data states, not four:** loading · empty · error · loaded · **uncertain** (honest uncertainty
  is first-class, PULSE-UX §5).
- **Transparency, quiet:** provenance on demand (ⓘ), real confidence (never UI-invented), legible
  consent (RULE_21), zero engine leakage (RULE_23) (PULSE-UX §6).
- Every user-facing phase must pass the **UX Acceptance Rubric** (PULSE-UX §10).

---

## 9. Glossary

- **Witness** — one stage of the reasoning pipeline (S1 salience … S6 ledger).
- **Ledger** — per-turn, per-stage audit trail (`TurnLedgerRow`).
- **Trajectory** — append-only record of a completed run (feeds the learning sweep).
- **Skill** — a learned, reusable procedure; must pass the admission gate to be promoted.
- **Trigger / Insight** — proactive condition and its generated narrative (`KgProactiveTrigger/Insight`).
- **Boundary contract** — the Pulse-owns-inference / Carbon-owns-state split (§2).
- **Consent gate (RULE_21)** — propose→confirm before any mutation.
