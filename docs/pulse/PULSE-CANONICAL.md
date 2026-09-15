# PULSE — Canonical Reference (Single Source of Truth)

> **Status:** CANONICAL · **Owner:** Master Architect · **Established:** 2026-09-15
> **Supersedes as the entry point:** `archive/PULSE-MASTER.md` (its 2026-08-30
> scorecard is stale — see §9). This document unifies and reconciles the whole Pulse doc set
> against the **actual code and runtime behavior** verified on 2026-09-15.
>
> **This file wins on conflict.** The other docs remain authoritative *within their scope*:
> - Experience/UX spec → [`PULSE-UX.md`](./PULSE-UX.md) + [`PULSE-UX-DESIGN.md`](./PULSE-UX-DESIGN.md)
> - Execution plan → [`PULSE-ROADMAP.md`](./PULSE-ROADMAP.md) (the forward plan; supersedes the
>   archived 0.2/0.3 roadmaps)
> - QA plan → [`PULSE-QA-MASTER.md`](./PULSE-QA-MASTER.md) + [`QA-FRAMEWORK.md`](./QA-FRAMEWORK.md)
> - Invariants → [`INVARIANTS.md`](./INVARIANTS.md) · Effect paths → [`EFFECT-PATHS.md`](./EFFECT-PATHS.md)
> - Remediation & phase history → `archive/` (superseded; provenance only)
>
> **Naming (RULE_23):** "Pulse" is an **internal** term. User-facing text always says "AI" /
> "the assistant" and describes **outcomes**, never internals.

---

## 0. Executive verdict (what Pulse is, today)

Pulse is a **host-agnostic reasoning engine** vendored under `backend/ai/engine/` (~38K LOC),
wrapped by a Carbon host layer (`backend/ai/`, ~137K LOC total, 181 test files / ~1,887 test
functions — all host-side). It is **one codebase** serving **multiple isolated instances**
(AASTMT/Carbon, Nibras/HRMS, …) that differ only by data partition and per-instance config —
**never by engine code**.

**The honest one-line answer to "coworker or interface?"** Pulse is a **genuinely grounded,
consent-gated advisory assistant with a real reasoning spine and real per-role data isolation** —
verified at runtime — that is **not yet** a self-improving autonomous coworker. It has the **anatomy**
of an enterprise coworker (memory, learning, proactive, and consolidation *organs* are all
implemented) but not yet the **metabolism**: **no scheduler/heartbeat is deployed** (no celery/beat/
timer), so the growth, proactive, and "24/7 cognition" faculties are **built but dormant** (§9 F5),
and learning-reuse is unproven. It is **more than an interface around a model**, but **less than the
eight-faculty coworker** the vision describes.

**Runtime-verified on 2026-09-15 (Nibras instance, real data):**
- ✅ **Grounding / no fabrication** — under a hard tool failure it refused to invent a payroll
  figure and failed closed; after the fix it grounded its answer in real DB rows.
- ✅ **Multi-tenant isolation** — one engine, per-instance `instance.yaml` + `instance_id` partition.
- ✅ **CBAC per-role scoping** — a non-superuser employee was cleanly **denied** cross-employee
  payroll data (`requires people:view`), with no data leak and no jargon leak.
- ✅ **Clarification** — an ambiguous request triggered a disambiguation turn, not a guess.

**The audit standard** is not "does Pulse look impressive?" but "can it perform valuable work
reliably, safely, and measurably?" On the evidence: **reliably + safely = substantially yes;
measurably = not yet** (no live evaluation harness with regression traces is in routine use).

---

## 1. What Pulse is (in one paragraph)

Pulse owns **inference only**; Carbon owns **all durable state and identity**. Reasoning runs
through a **six-witness turn pipeline** (S1 salience → S2 retrieve → S3 draft → S4 critic →
S5 execute → S6 ledger/synthesis), optionally escalating to a **ReAct multi-step plan loop** for
agentic work. Around the spine sit memory (short-term/working/long-term/episodic), a knowledge
graph, a proactive engine, a learning loop (trajectory → skills gate → planner reuse), an
agent/tool layer, and an LLM router with task lanes. Every host **effect** funnels through a single
**command boundary** (14 fail-closed stages) gated by a **default-deny PDP**. No mutation happens
without a consent gate (RULE_21).

---

## 2. The eight faculties (mental model) — with verified maturity

Reference systems: Anthropic Claude + MCP, Cursor, GitHub Copilot agent mode, OpenAI o-series +
memory. Research lineage: CoALA, ReAct, Reflexion, Voyager, Generative Agents, MemGPT.

| # | Faculty | Lives in | Maturity (2026-09-15, code-verified) |
|---|---------|----------|--------------------------------------|
| 1 | **Perception / salience** | `cognition/turn/salience.py`, `turn/intent.py` | Solid, shallow — regex router + LLM intent ladder; not learned |
| 2 | **Memory** | `engine/memory/*`, `ai/context_assembler.py` | Strong — long-term/episodic on PG+vector; **short-term/working now Redis-backed** (survives restart) |
| 3 | **Reasoning** | `cognition/turn/runner.py`, `cognition/plan/loop.py` | Genuinely strong — six-witness spine + ReAct loop (phases, parallel steps, consent, replan, resume) |
| 4 | **Action** | `engine/agent/{plugins,tools}.py`, MCP client | Strong — plugin ABC, `requires_confirmation`, capability manifest; MCP client exists |
| 5 | **Grounding / truthfulness** | `cognition/turn/critic.py`, `turn/verify.py` | **Best-in-class, runtime-verified** — fail-closed, no fabrication under failure |
| 6 | **Learning / growth** | `cognition/{trajectory,consolidation}.py`, `skills/*` | Stronger than first graded — reuse arc **implemented + unit-tested** (usage_count increments, flywheel promotes proven skills, planner prefers `usage_count≥3`); live end-to-end demo still pending |
| 7 | **Metacognition** | knowledge-gap critic, `list_my_capabilities`, `clarify.py` | Partial→improving — clarification witness verified; confidence surfacing partial |
| 8 | **Proactivity** | `engine/proactive/*` | Delivery infra **runtime-verified** — insight reaches `ai/insights/` (outcome shape) + SSE stream live + frontend consumes it; scheduled *generation* is the remaining gap (ties to the heartbeat) |

---

## 3. The boundary contract (NON-NEGOTIABLE — RULE_6)

| Concern | Pulse (`engine/`) owns | Carbon (`ai/` host) owns |
|---------|------------------------|--------------------------|
| Reasoning, truthfulness gates, tool **decision** | ✅ | ❌ |
| Tool **effect**, durable state, memory storage, identity/auth, budget enforcement | ❌ | ✅ |

**Hard rules (from `.ai-toolkit/project.config.md`):** RULE_6 (engine holds zero durable state) ·
RULE_18 (all AI ops go through `CarbonIntelligence`) · RULE_20 (engine imports nothing from domain
apps) · RULE_21 (no auto-mutation; propose→confirm) · RULE_23 (no implementation leakage in
user-facing text) · RULE_25 (stable system-prompt prefix for cache discipline).

**The one door.** Every host effect routes through `CommandBoundary` (`ai/command_boundary.py`,
14 fail-closed stages: identity → scope → contract → validate → state_eligibility → **pdp** →
consent → grant → budget → revision → execute → persist_events → verify → outcome) and `PDP`
(`ai/pdp.py`, default-deny). Host effects reach the DB only via `CarbonHostExecutor`
(`ai/host_executor.py`) through four `execute_*_via_boundary` seams. See [`EFFECT-PATHS.md`](./EFFECT-PATHS.md).

**Integration surfaces (the ONLY host↔engine touch points):** `ai/intelligence.py` ·
`ai/providers/pulse.py` · `ai/engine_runtime.py` · `ai/serializers.py` · `ai/workspace_api.py`.

**Invariants I1–I8** ([`INVARIANTS.md`](./INVARIANTS.md)) and **anti-drift laws L1–L7**
(`archive/PULSE-0.2-ROADMAP.md`) gate every change: no upward imports, no durable
state in `engine/`, every mutation staged+confirmed, every scope carries an org/app boundary,
outcomes-only copy, freeze-the-spine/grow-the-periphery, telemetry-or-it-didn't-happen.

---

## 4. Architecture map (audited)

```
backend/ai/                      ← Carbon host (durable state, guards, API)
  intelligence.py                ← CarbonIntelligence: THE entry point (RULE_18)
  instance_registry.py           ← brand→instance: aastmt→carbon, nibras→nibras, medos, tectona
  engine_runtime.py              ← dispatch_task[_stream]; _instance_config() loads instance.yaml
  providers/pulse.py             ← engine adapter seam
  command_boundary.py / pdp.py / host_executor.py   ← the one door (14 stages, default-deny)
  context_assembler.py           ← tiered context (history / summary / KG / memory)
  engine/                        ← Pulse (in-process, stateless reasoning)
    cognition/turn/              ← SIX-WITNESS SPINE
      salience.py(S1) intent.py(S1.5) retrieve.py(S2) draft.py(S3)
      critic.py(S4) execute.py(S5) runner.py(S6) verify.py clarify.py(S1.7 new) ledger.py
    cognition/plan/loop.py       ← ReAct multi-step loop
    cognition/{trajectory,consolidation,synthesis,auto_memory}.py, distill/, dialogue/
    memory/{short_term,working(Redis),long_term,episodic}.py
    knowledge_graph/, knowledge/ (skill_folder, terminology), proactive/, skills/, learning/
    agent/{tools,plugins,mcp_client,budget,workers}.py
    llm/{router,provider,prompts,playbook,prompt_synthesizer}.py
    instances/<id>/instance.yaml ← per-instance persona/api_catalog/domain_topics/topic_guard
```

**Task lanes** (`engine/llm/router.py`): `chat` · `deep` · **`reason`** (adaptive-compute lane,
shipped) · `cognition` · `introspect` · `eval` · `embed`. Cost logged per call; per-instance daily
USD budget enforced.

---

## 5. The multi-instance model (why Carbon ≠ Nibras — correctly)

**The engine is byte-for-byte identical across brands.** `./manage.sh brand <id>` flips only env
(`DJANGO_BRAND`, `PULSE_INSTANCE_ID`, Redis DB index, media/chroma dirs) — zero engine code changes.

| Layer | AASTMT (Carbon) | Nibras (HRMS) | Verdict |
|-------|-----------------|---------------|---------|
| Engine code | identical | identical | ✅ correct |
| `resolve_instance_id()` | `carbon` | `nibras` | ✅ tenant partition |
| Redis DB | `/0` | `/1` | ✅ ephemeral isolation |
| Active apps | carbon/emissions | carbon **off**; people/HRMS + catalog/mdm/dq/my/team | ✅ different domains |
| `instances/<id>/instance.yaml` | 174 lines, persona 1.2k, 11 endpoints | **357 lines, persona 3.2k, 16 endpoints**, +topic_guard/excluded_tools | ✅ Nibras richer, not degraded |
| DB schema | migrated | **was 11 `ai` migrations behind** → fixed 2026-09-15 | ⚠️ see §9 F4 |

**Design fact:** `_instance_config()` falls back to the `carbon` config **only** when an instance's
YAML is empty. Nibras's is non-empty, so **no cross-instance contamination**. The real per-instance
expertise is the `instance.yaml`, **not** the filesystem `domain_packs/` — which is inert in the
live path (§9 F1a). **Decision (§12): `instance.yaml` is the single prompt-config mechanism.**

---

## 5.1 Process & tooling governance — the certainty model

**Principle:** the coworker is certain because it executes **explicit, admin-governed processes and
capabilities** — not because it "figured things out." Learning is a *suggestion feed*, never an
autonomous behavior change. Two authoritative layers, one advisory feed:

| Layer | What it is | Who owns it | Certainty |
|-------|-----------|-------------|-----------|
| **`ProcessDefinition`** (`ai/models/process.py`, P3-03) | A governed process document: `objects`, `objective` (predicate), `steps[]`, `constraints`, `policies[refuse_if/ask_if]`, `exceptions`, **`kill_switch`**, `tests`. Lifecycle **draft → review → active → deprecated**. Each step carries an **autonomy dial** (`observe`/`propose`/`act_confirm`/`act_notify`/`act_silent`/`human_only`). Validated vs `ai/process_schema.json`. | **AI admin** authors/reviews/activates | **Deterministic** — an `active` process runs the same way every time, gated by its declared autonomy + policies |
| **`Capability`** (`ai/models/capability.py`, P3-01) | The registry contract for one **governed host action** (e.g. `payroll.run.commit`), declared in the domain pack `api_catalog.yaml` and resolved fail-closed against `ai/capability_registry.py`. Distinct from agent-facing tools. | **AI admin** (registry) | **Explicit** — an unknown/unregistered host action is refused, never improvised |
| **Learned skills** (`engine/skills/*`, `_authority.py`) | Trajectory → consolidation → skill **candidates**. `instance_promoted` is **gate-only** (`skills/_authority.py`): no automatic promotion. | Proposed by engine, **promoted by admin/gate** | **Advisory** — a candidate does nothing authoritative until an admin promotes it |

**How this reduces uncertainty (the answer to "explicit or learnt?"): both, but ranked.**
Explicit `ProcessDefinition` + `Capability` are **authoritative and deterministic**; learned skills
are **candidates** that require **gated promotion**. The **per-step autonomy dial** is the precise
knob: keep high-stakes steps at `human_only`/`act_confirm` (certain, gated), let low-risk steps run
`act_notify`/`act_silent`. `refuse_if`/`ask_if` policies + `kill_switch` bound every process.

**For Nibras/HRMS (recommended):** model the payroll lifecycle (draft → compute → validate →
**commit**) as `ProcessDefinition`s with `commit` pinned to `human_only`; register HRMS host actions
(`list_payslip_lines`, `run_payroll`, …) as `Capability` rows with `refuse_if`/`ask_if`; treat any
learned pattern as an admin-reviewed candidate — never auto-active.

**Gap (§9):** the backend governance (models, `process_interview.py`, `registry_api.py`) exists, but
the dedicated **admin console UI** to manage processes/capabilities/skill-promotion is **not built**
(0.3 roadmap "Pulse Console"). Today these are managed via API/CLI, not a room.

---

## 6. Capability matrix — intended vs implemented vs verified

Legend: **V** = runtime-verified this audit · **I** = implemented (code present) · **U** =
implemented-but-unverified · **P** = partial · **N** = not found / inert.

| Capability | Intended | Status | Evidence |
|---|---|---|---|
| Six-witness reasoning turn | ✓ | **I** | `cognition/turn/*` all present; runner 2,962 LOC |
| Grounding, no fabrication under failure | ✓ | **V** | Nibras turn failed closed; no invented figure |
| Grounded answer from live tool data | ✓ | **V** | Post-fix turn returned real committed payroll runs |
| Consent gate / no auto-mutation (RULE_21) | ✓ | **I** | 14-stage boundary + default-deny PDP |
| CBAC per-role data scoping | ✓ | **V** | Employee denied cross-employee payroll (`people:view`) |
| Multi-tenant isolation | ✓ | **V** | Nibras vs Carbon partition + own instance.yaml |
| Clarification on ambiguity | ✓ | **V** | Ambiguous ask → disambiguation turn (`clarify.py`) |
| Persistent short-term/working memory | ✓ | **I** | `short_term.py` Redis-backed (in-proc fallback) |
| Adaptive reasoning lane | ✓ | **I** | `reason` lane in router |
| ReAct multi-step plans + resume | ✓ | **I** | `cognition/plan/loop.py`, `plans_service.py` |
| Learning reuse (promoted skill on hot path) | ✓ | **I + tested** | `SkillAwarePlanner` matches promoted skills; `tools.py`→`update_stats` increments `Skill.usage_count` on reuse; flywheel promotes after proven use. 17 tests green (`test_skill_reuse`, `test_skill_flywheel`). Live e2e demo (real consolidation→reuse) still pending. |
| Proactive insight → React UI | ✓ | **I + delivery verified** | delivery→persistence→CBAC-scoped list API proven at runtime (outcome shape, no jargon); SSE stream live (`200 text/event-stream`); frontend consumes `ai/insights/`. Remaining: live SSE *frame* push + real generation-on-schedule (needs heartbeat + LLM). |
| Filesystem domain-guidance packs in prompt | ✓ | **N** | `build_chat_prompt` called without `guidance_skills=` → inert (test-only) |
| Versioned PlaybookBlocks / A-B prompts | ✓ | **N** (in this DB) | `PlaybookBlock` table empty both instances → `_fallback_prompt` path |
| Typed domain `ToolDef` objects | 0.3 gap | **N** | tools are `call_host_api` strings today |

---

## 7. Genuine strengths (keep, don't lose)

1. **Grounding critic + fail-closed boundary** — the differentiator, and the only major claim this
   audit could confirm *end-to-end at runtime*. It did not fabricate under failure.
2. **RULE_21 consent architecture** — one door, default-deny, staged mutations; a code path, not a
   convention.
3. **CBAC role isolation** — verified: an employee cannot read others' payroll.
4. **Clean multi-tenant model** — one engine, per-instance config + partition, no leakage.
5. **Episodic memory with causal chains + the learning gate machinery** — well-built substrate.

---

## 8. Real vs surface (the honest cut)

- **Real intelligence:** grounding/verification, the six-witness decomposition, CBAC-scoped
  retrieval, clarification. These change outcomes and are testable.
- **Orchestration (not intelligence, but valuable):** salience routing, tool dispatch, the plan
  loop, streaming SSE. Deterministic scaffolding — **keep it deterministic**.
- **Presentation:** rich markdown/mermaid/tables, thinking indicator, confidence chips. Good UX;
  not intelligence. Don't mistake fluent tables for competence.
- **Where additional autonomy would add more risk than value (today):** any path that lets the
  engine mutate host state without the consent gate. Keep mutations advisory until there is a live
  evaluation harness proving reliability. The verified behavior that *pays off* is **refusing to
  act/guess**, not acting autonomously.

---

## 9. Open findings (this audit — 2026-09-15)

| ID | Finding | Sev | Conf | Action |
|----|---------|-----|------|--------|
| **F4** | `nibras_dev` was **11 `ai` migrations behind** (0031–0041) → PDP `_persist` hit `UndefinedColumn "stage"` → every host tool call failed "pdp: evaluation error (fail-closed)". **RESOLVED** by applying migrations; verified grounded answers after. | High | Certain | ✅ Done (dev). Add a startup migration-drift check per instance. |
| **C-F4a** | PDP/boundary surfaced an **infra error** (DB/schema) identically to a policy **deny** ("fail-closed"), masking operational failures as authz decisions. **RESOLVED 2026-09-15** — infra/evaluation errors now classify as `failed` (still fail-closed), distinct from `refused`. | Med | High | ✅ Done (`ports/policy.py`, `command_boundary._decide`). |
| **C-F4b** | **RULE_23 leak** on the *infra-error* path: `pdp: evaluation error (fail-closed)` and `call_host_api` leaked verbatim to the user. (Policy-deny path copy was already clean.) **RESOLVED 2026-09-15** — tool-error copy is now outcome-only. | Med | High | ✅ Done (`engine/cognition/turn/execute.py` + regression test). |
| **F1a** | Filesystem `domain_packs/*/skills` guidance is **inert** — `runner.py` calls `build_chat_prompt()` without `guidance_skills=` (lines 1737/2550/2683/2796). Loaded only by tests. Only `carbon` has a pack. | Med | High | Make live (pass `guidance_skills`) **or** delete (L6). Decide one mechanism. |
| **F3** | `PlaybookBlock` table **empty** for both instances → the versioned-playbook / A-B candidate-prompt machinery is unused; prompts fall to `_fallback_prompt`. | Med | High (dev) | Verify prod; seed or mark deferred. Don't ship inert "impressive" code. |
| **F5** | **No heartbeat / no 24/7 cognition.** No celery/beat/scheduler is deployed. The proactive, consolidation (learning), distill, and decay loops exist as code + management commands (`run_cognition_loop`, `run_learning_loop`) but **nothing runs them on a timer**. Config flags are enabled (`CONSOLIDATION_SWEEP_ENABLED`, `KG_PROACTIVE_ENABLED`) but undriven. As deployed, Pulse is **reactive per-turn only**; growth/proactivity are dormant. | High | Certain | Deploy a heartbeat (systemd timer / celery-beat) driving the loops; add reuse + delivery telemetry. Cheap, high-leverage. |
| **Q-1** | Answer-quality gap: "how is net pay calculated + figures" returned run **metadata** only, not per-employee net pay or the `gross − GOSI − loan = net` formula the persona defines. | Low-Med | Med | Strengthen planning/tool-selection for compound asks; add eval scenario. |
| **F2-obs** | Nibras RBAC: 532 users but **only `employee_group`** is populated; lead/manager/analyst/finance roles are defined-but-unassigned. Role-scoped UX beyond employee+superuser is untested with real users. | Low | High | Assign representative test users per role for QA. |

**Stale-doc note:** `archive/PULSE-MASTER.md` (2026-08-30) lists gaps G1–G5 as open; the code shows 0.2
shipped (Redis short-term, `reason` lane, shared proactive persistence, skill-aware planner). Trust
code + this file over that scorecard.

---

## 10. What to KEEP / FIX / REMOVE / DEFER / BUILD

- **KEEP:** grounding critic + fail-closed boundary; RULE_21 consent; CBAC isolation; multi-tenant
  model; episodic memory + learning-gate substrate; deterministic salience/plan orchestration.
- **FIX (now):** C-F4a (infra-error ≠ deny), C-F4b (RULE_23 error copy), per-instance
  migration-drift startup check, compound-ask planning (Q-1).
- **REMOVE or make-live:** F1a inert domain-pack path; F3 unused PlaybookBlock/A-B machinery
  (choose one prompt-config mechanism and delete the other).
- **DEFER:** typed `ToolDef` catalog, cross-domain synthesis, Pulse Console, platform-as-MCP-server
  (0.3/0.4 roadmap) — until the reliability baseline (below) exists.
- **BUILD (highest leverage):** a **live evaluation harness** — golden HRMS + emissions scenarios,
  regression traces, and telemetry counters for grounding-pass, deny-correctness, learning-reuse,
  and proactive-delivery. Without it, "measurably" stays unproven.

---

## 11. 30 / 60 / 90-day focus (prioritized by user-value × risk-reduction × differentiation)

- **30 days — trust the plumbing.** Ship C-F4a/C-F4b; add migration-drift guard; stand up the eval
  harness with ≥20 golden scenarios per instance; wire telemetry counters. *Acceptance:* every merge
  runs the harness; grounding-pass and deny-correctness reported per build.
- **60 days — prove the loops.** Make learning-reuse observable (counter proving a promoted skill
  fired on the hot path) or cut it; verify proactive insight → React UI via SSE end-to-end, or cut
  it. Resolve F1a/F3 (one prompt-config mechanism). *Acceptance:* a reuse counter increments in a
  real turn; an insight appears in the UI in a real session.
- **90 days — deepen one domain.** Pick Nibras/HRMS **or** Carbon/emissions and make compound,
  multi-tool answers excellent (Q-1 class). Add per-role QA users. *Acceptance:* the 90-day
  instance passes a compound-scenario suite at a stated pass-rate baseline.

---

## 12. Decisions that need the human

1. **Autonomy appetite** — keep Pulse advisory (propose→confirm) or invest in gated
   auto-execution? (Recommendation: stay advisory until the eval harness exists.)
2. **Primary user & anchor domain** — **DECIDED 2026-09-15: Nibras/HRMS** is the anchor domain.
3. **Prompt-config mechanism** — **DECIDED 2026-09-15: standardize on `instance.yaml`** (the
   live path, per-instance, host-side, RULE_20-clean, and already the richest source). The
   filesystem `domain_packs/*/skills` guidance wiring (F1a) and the DB `PlaybookBlock` A/B machinery
   (F3) are **REMOVE/DEFER** — do not invest in them; fold any needed guidance into `instance.yaml`.
4. **Doc consolidation** — **DONE 2026-09-15:** superseded docs archived under `docs/pulse/archive/`;
   the forward set is `PULSE-CANONICAL.md` + `PULSE-ROADMAP.md` + UX/QA/invariants/effect-paths.

---

## 13. What would change these conclusions

- A live evaluation harness showing grounding-pass < ~95% on golden scenarios (would downgrade §7.1).
- Evidence that learning-reuse or proactive-delivery fires in real turns (would upgrade Faculty 6/8
  from **U** to **V**).
- Prod showing `PlaybookBlock`/domain-packs actually in use (would retire F1a/F3).
- Cross-tenant leakage in any turn (would be a critical downgrade of §7.4).

---

## 14. Where to look (file map)

| You need… | Read |
|-----------|------|
| Binding AI contract | `.ai-toolkit/shared/ai-contract.md` |
| Project hard rules | `.ai-toolkit/project.config.md` (RULE_1..26) |
| Reasoning spine | `backend/ai/engine/cognition/turn/runner.py` + `turn/witnesses.py` |
| Multi-step execution | `backend/ai/engine/cognition/plan/loop.py` |
| The one door | `backend/ai/command_boundary.py`, `ai/pdp.py`, `ai/host_executor.py` |
| Per-instance config | `backend/ai/engine/instances/<id>/instance.yaml`, `ai/instance_registry.py` |
| Memory | `backend/ai/engine/memory/*` + `ai/context_assembler.py` |
| Proactive engine | `backend/ai/engine/proactive/*` |
| Learning loop | `backend/ai/engine/cognition/{trajectory,consolidation}.py` + `engine/skills/*` |
| Tools / plugins | `backend/ai/engine/agent/{tools,plugins}.py` |
| Model routing | `backend/ai/engine/llm/router.py` |
| Experience (UX) | [`PULSE-UX.md`](./PULSE-UX.md) + [`PULSE-UX-DESIGN.md`](./PULSE-UX-DESIGN.md) |
| Execution plan | [`PULSE-ROADMAP.md`](./PULSE-ROADMAP.md) |
| QA plan | [`PULSE-QA-MASTER.md`](./PULSE-QA-MASTER.md) + [`QA-FRAMEWORK.md`](./QA-FRAMEWORK.md) |
| Invariants / effect paths | [`INVARIANTS.md`](./INVARIANTS.md) · [`EFFECT-PATHS.md`](./EFFECT-PATHS.md) |

---

## 15. Glossary

**Witness** — one stage of the reasoning pipeline (S1…S6). **Ledger** — per-turn, per-stage audit
trail (`TurnLedgerRow`). **Trajectory** — append-only record of a completed run (feeds learning).
**Skill** — a learned, reusable procedure; must pass the admission gate to be promoted.
**Trigger / Insight** — proactive condition + generated narrative (`KgProactiveTrigger/Insight`).
**Boundary contract** — Pulse-owns-inference / Carbon-owns-state. **Consent gate (RULE_21)** —
propose→confirm before any mutation. **Instance** — an isolated tenant (Carbon, Nibras, …); one
engine, many instances. **CBAC** — capability-based access control filtering tools/data per user.
