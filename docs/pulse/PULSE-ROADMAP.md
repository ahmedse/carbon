# PULSE — Roadmap (the plan toward the goal)

> **Status:** CANONICAL PLAN · **Owner:** Master Architect · **Established:** 2026-09-15
> **Companion to** [`PULSE-CANONICAL.md`](./PULSE-CANONICAL.md) (what Pulse *is* + audit findings).
> **Supersedes** the archived `PULSE-0.2/0.3-ROADMAP.md` and `PULSE-UNIFIED-REMEDIATION-PLAN.md`.
> **Anchor domain:** Nibras / HRMS (decided 2026-09-15). Carbon/emissions follows the same contracts.

---

## 0. The one goal, and the gap to it

**Goal:** a **trustworthy enterprise AI coworker** for Nibras/HRMS — one that is **certain**
(governed, deterministic where it matters), **remembers**, **grows**, is **proactive**, runs
**24/7**, and is **measurably** reliable — while staying advisory (RULE_21) until proven.

**Where we are (audit-verified 2026-09-15):** the *anatomy* is built and the safety foundations are
real (grounding, consent boundary, CBAC isolation, memory) — but the *metabolism* is missing: **no
heartbeat drives the background faculties**, learning-reuse is unproven, proactive delivery is
unverified, and there is no evaluation harness. See [`PULSE-CANONICAL.md §0, §9`](./PULSE-CANONICAL.md).

**The plan below closes that gap in leverage order.** It is not a rewrite — it is *turning on and
proving* faculties that already exist, plus governance depth and an admin surface.

### Prioritization principle
`user-value × risk-reduction × strategic-differentiation`, balanced against `effort × dependency ×
operating-cost`. Every phase ships **evidence** (a test, a telemetry counter, or a ledger row) — a
phase with green lint but no runtime evidence is **not done** (anti-drift law L5/L7).

### Legend
Effort: **S** ≤2d · **M** ≤1wk · **L** >1wk. Each phase: Goal · Why · Scope · **Acceptance
(evidence)** · Effort · Risk · Depends-on.

---

## Phase map (at a glance)

| # | Phase | Outcome | Effort | Priority |
|---|-------|---------|--------|----------|
| **P0** | Foundations | Audit, canonical doc, C-F4a/b fixes, Nibras migrations + payroll governance slice | — | ✅ Done |
| **P1** | The Heartbeat | Background cognition runs on a schedule, per instance, with telemetry | M | 🔴 Highest |
| **P2** | Prove Learning-Reuse | A promoted skill fires on the hot path, with a counter | M | 🔴 High |
| **P3** | Proactive Delivery | Real insights reach the Nibras UI via SSE | M | 🟠 High |
| **P4** | Evaluation Harness | Golden HRMS + emissions scenarios in CI; a reliability baseline exists | M–L | 🔴 High |
| **P5** | HRMS Governance Depth | Leave/loan/GOSI/WPS/onboarding as governed processes; per-role QA | L | 🟠 Med |
| **P6** | Pulse Console (AI admin) | Admin room to manage processes/capabilities/skills/watches | L | 🟠 Med |
| **P7** | Convergence & Cleanup | One prompt-config mechanism; zero inert subsystems | S–M | 🟢 Med |

---

## P0 — Foundations ✅ (done 2026-09-15)
- Evidence-led audit → [`PULSE-CANONICAL.md`](./PULSE-CANONICAL.md) (SSOT, capability matrix, findings).
- Fixed **C-F4a** (PDP infra-error ≠ policy-deny) + **C-F4b** (RULE_23 error-copy leak); 83 tests green.
- Applied 11 pending `ai` migrations to `nibras_dev`; Nibras Pulse verified grounded at runtime.
- **Nibras payroll governance slice**: `domain_packs/nibras/` (api_catalog + `payroll.run.lifecycle`
  process), 8 capabilities, idempotent seed, 6 tests — closes **F1a**. Commit is `human_only` + consent.

---

## P1 — The Heartbeat (metabolism) 🔴 highest leverage
- **Goal:** the proactive, consolidation (learning), distill, and decay loops run **on a schedule,
  per instance**, so Pulse thinks between messages.
- **Why:** finding **F5** — the organs exist (`run_cognition_loop`, `run_learning_loop`,
  `proactive/loop.py`) and flags are enabled, but **nothing drives them**. This single phase converts
  every "dormant" faculty to "alive." Highest value × lowest effort.
- **Scope:**
  - A scheduler the deployment actually runs: a **systemd timer** per instance (mirrors
    `deploy/instance/*.timer`) or celery-beat. Cadence: proactive/briefing daily; consolidation
    sweep nightly (sleep-time); distill/decay weekly. Per-brand env (`DJANGO_BRAND`).
  - Wire the existing management commands; add a thin `run_pulse_maintenance` umbrella command if
    helpful. Respect the per-instance daily USD budget (already enforced by the router).
  - **Telemetry:** each run writes a heartbeat row (instance, loop, started/finished, items produced,
    tokens/cost). Health endpoint surfaces "last heartbeat per loop."
- **Acceptance (evidence):** on a scheduled tick, a real `KgProactiveInsight` and a real
  consolidation sweep row appear for `nibras`, with a heartbeat telemetry row; `showmigrations`/logs
  prove it ran unattended (not manually invoked). Restart-safe.
- **Effort:** M · **Risk:** cost runaway (mitigate: budget + max-LLM-calls caps already exist) ·
  **Depends-on:** P0.

---

## P2 — Prove Learning-Reuse (does it actually grow?) 🔴
- **Goal:** demonstrate a **promoted skill reused on the hot path**, observably.
- **Why:** the planner reads promoted skills (code-verified) but reuse has **never been observed at
  runtime** (matrix: **U**). "Grows/evolves" stays a claim until a counter proves it.
- **Scope:**
  - Verify the full arc under the heartbeat: trajectory → consolidation drafts a `Skill` candidate →
    admission gate → **admin/gate promotion** → `SkillAwarePlanner` matches + reuses it.
  - Add a **reuse counter** (per skill, per instance) incremented when a promoted skill drives a turn;
    surface it in usage/observability.
  - If the arc cannot be made to fire on a realistic HRMS scenario, **cut the reuse path** (L6) rather
    than keep inert "learning" code.
- **Acceptance (evidence):** a named skill promoted, then a later HRMS turn shows the reuse counter
  increment + a ledger row citing the skill. Or a documented decision to remove the path.
- **Effort:** M · **Risk:** learning may be genuinely marginal for HRMS — be willing to cut ·
  **Depends-on:** P1.

---

## P3 — Proactive Delivery to the human 🟠
- **Goal:** a real backend insight reaches the **Nibras React UI** via SSE (not just persisted).
- **Why:** delivery persists `KgProactiveInsight` (shared) but UI arrival is **unverified** (matrix:
  U/P). An insight the user never sees is not proactivity.
- **Scope:** trace `proactive/delivery.py` → Django SSE surface → React notification panel end-to-end;
  fix the gap; add a "dismiss/act" affordance. Must pass the [`PULSE-UX.md`](./PULSE-UX.md) rubric
  (4-beat story, provenance, honest confidence, no engine jargon — RULE_23).
- **Acceptance (evidence):** in a live session, a scheduled HRMS insight (e.g. "payroll run 12 has an
  unresolved variance") appears in the Nibras notification panel; screenshot + network trace.
- **Effort:** M · **Risk:** SSE plumbing already exists for chat — reuse it · **Depends-on:** P1.

---

## P4 — Evaluation Harness (make "intelligence" measurable) 🔴
- **Goal:** a **reliability baseline** — golden scenarios run in CI with pass-rate, grounding, deny-
  correctness, latency, and cost metrics.
- **Why:** the audit could confirm *shape* but not *rate*. Without measurement, "more intelligent" is
  unfalsifiable, and no roadmap claim can be trusted. This is the BUILD item from the verdict.
- **Scope:**
  - ≥20 golden scenarios per instance (Nibras HRMS first: net-pay grounding, cross-employee deny,
    payroll lifecycle, ambiguous→clarify, compound "how is net pay calculated + figures" = **Q-1**).
  - Reuse `ai/eval/` (fixtures, replay) + the `eval` router lane. Emit per-run metrics: grounding-pass,
    deny-correctness, fabrication-rate (must be 0), reuse-fired, tokens, latency.
  - Gate merges: the harness runs on CI; regressions block. Establish the **baseline numbers**
    (don't invent targets — measure, then set thresholds).
- **Acceptance (evidence):** `pytest`/harness prints per-scenario pass-rate + metrics for `nibras`;
  a deliberately broken grounding change is caught by the harness.
- **Effort:** M–L · **Risk:** scenario authoring is the real cost · **Depends-on:** P0 (independent of
  P1–P3; can run in parallel).

---

## P5 — Nibras HRMS Governance Depth 🟠
- **Goal:** the whole HRMS lifecycle is **explicit, admin-governed** (certainty), not just payroll.
- **Why:** you asked for a coworker that is *certain*; certainty = governed `ProcessDefinition`s +
  `Capability`s with autonomy dials, not learned guesses. P0 did payroll; this extends it.
- **Scope:**
  - Governed processes: **leave** (request→approve, calendar-split), **loans** (schedule→installment
    reconciliation), **GOSI/WPS** compliance (SIF generation), **onboarding**, **attendance
    permission** (short-hours submit→review→approve). Each with per-step
    autonomy (`human_only` on statutory/irreversible steps), `refuse_if`/`ask_if`, `kill_switch`, tests.
  - Register the host actions in `capability_registry.py`; seed idempotently (mirror
    `seed_nibras_processes.py`).
  - Fix **Q-1** (compound answers) via better planning/tool-selection for the net-pay formula.
  - Assign representative **per-role QA users** (people_lead/manager/analyst/finance) — finding
    **F2**: today only `employee_group` is populated, so role-scoped behavior is under-tested.
- **Acceptance (evidence):** each new process validates + seeds; a live turn walks a governed leave/
  loan flow with correct autonomy gating; per-role QA turns pass in the harness.
  **“Proper” (2026-09-21):** catalog parity (pack tools ⊆ instance.yaml), honest GOSI generate→validate→submit
  (`WpsFiling`), Operator Chat·Plan·Run evidence (`simulate_nibras_operator_processes`), deep sim 5/5.
  **Attendance (2026-09-21):** 6th process `attendance.permission.lifecycle` — deep+operator 6/6 PASS.
  **Security honesty (2026-09-21):** ADR-0045 / RULE_34 — YAML SoD ≠ host ACL; leave/loan = Correspondence;
  payroll/GOSI/onboard/attendance irreversibles dial-only until NPS-1 shared host gate.
  See ADR-0044 · ADR-0045.
- **Effort:** L · **Risk:** statutory correctness — keep rates rule-driven, never hardcoded ·
  **Depends-on:** P0, ideally P4 (to measure).

---

## P6 — Pulse Console (the AI-admin room) 🟠
- **Goal:** a dedicated admin surface to **manage** processes, capabilities, skill-promotion, anomaly
  watches, budget, and audit — the "managed by AI admin" you asked for.
- **Why:** the backend governance exists (`registry_api.py`, `process_interview.py`, observability/
  usage APIs) but there is **no admin UI** — today these are API/CLI only. Certainty needs a
  human-usable control room (promote skills, activate/deprecate processes, tune autonomy dials).
- **Scope:** a Console room: Processes (draft→review→active→deprecated), Capabilities registry,
  Skills pipeline (review + promote/reject), Watches, Budget, Audit viewer. CBAC-gated to admins.
  Must pass the UX rubric.
- **Acceptance (evidence):** an admin promotes a skill and activates a process **from the UI**, and it
  takes effect in a subsequent turn (ledger proof).
- **Effort:** L · **Risk:** scope creep — ship read + the 3 highest-value actions first ·
  **Depends-on:** P2 (skills), P5 (processes).
- **Progress (2026-09-15):**
  - ✅ **Processes** in the Console shell (`AIProcessesTab`) — activate/deprecate, emergency-stop,
    and step autonomy dials, now CBAC-gated **up-front** by capability (`ai:process_owner`,
    `ai:publisher`, `ai:operator`) with a 403 lock fallback. 4 tests green.
  - ✅ **Skills catalog + Watches** tabs wired into the Console shell, reusing the existing
    `SkillsPanel`/`WatchesPanel` components (single source of truth — no duplicate panels). Shell
    reachability tests green; lint + production build green.
  - ⏳ **Remaining:** the skill **promote/reject** action (needs a backend decision endpoint — skill
    admission is gate-only today, `ai/engine/skills/_authority.py`), plus Capabilities-registry view
    and Budget/Audit viewers.

---

## P7 — Convergence & Cleanup 🟢
- **Goal:** one mechanism per job; zero inert "impressive" subsystems (anti-drift L6).
- **Scope:**
  - **Prompt-config:** standardize on `instance.yaml` (decided). Delete the inert filesystem
    domain-pack *guidance-skill* live-wiring path (**F1a**) and either **seed or remove** the
    `PlaybookBlock` A/B machinery (**F3**).
  - Add a per-instance **migration-drift startup check** (so F4 can never recur silently).
  - Confirm no dead subsystems remain (drift/learned-triggers either fire or are removed).
- **Acceptance (evidence):** a grep/import check shows one prompt-config path; `PlaybookBlock` is
  either populated-and-used or gone; a drifted schema fails a startup check loudly.
- **Effort:** S–M · **Risk:** low · **Depends-on:** P1–P4 (so we know what's truly inert).

---

## Cross-cutting (every phase)
- **Invariants** I1–I8 hold ([`INVARIANTS.md`](./INVARIANTS.md)); engine imports nothing from domain
  apps (RULE_20); every mutation staged+confirmed (RULE_21); no engine jargon (RULE_23).
- **Cost:** per-instance daily USD budget enforced; heartbeat loops capped (`CONSOLIDATION_SWEEP_MAX_LLM_CALLS`).
- **Observability:** every "it learned / delivered / escalated" ships a counter or ledger row (L7).
- **Security:** default-deny PDP; PII gate (server-side) tracked as a hardening item.

---

## Decisions still needed from the human
1. **Autonomy ceiling:** keep everything advisory (propose→confirm), or allow gated auto-execution for
   low-risk `act_notify`/`act_silent` steps once P4 proves reliability? (Recommendation: advisory
   until P4 baseline exists.)
2. **Heartbeat host:** systemd timers (matches existing `deploy/instance/`) vs celery-beat? (Rec: systemd.)
3. **Learning:** if P2 shows HRMS reuse is marginal, do we **cut** the learning path or invest? 
4. **Console scope:** minimum viable admin room (read + promote-skill + activate-process) vs full suite.

---

## Definition of done for "enterprise coworker" (the finish line)
All true, each proven by a telemetry/ledger artifact:
1. Background cognition runs unattended (P1). ✅ PEC-1A (`docs/pulse/evidence/PEC-1A-heartbeat.md`)
2. A learned skill is reused on the hot path with a counter (P2). ✅ PEC-2A (`PEC-2A-reuse.md`)
3. A proactive insight reaches the user in the UI (P3). ✅ PEC-3A + PEC-3B
4. A reliability baseline exists and gates merges (P4). ✅ PEC-4A (`PEC-4A-eval-baseline.md`, CI harness)
5. The HRMS lifecycle is governed with correct autonomy dials (P5). ✅ PEC-5A/5B (GOSI/WPS + onboarding; payroll/leave/loan pre-existed)
6. An AI admin manages processes/skills from a console (P6). ✅ PEC-6A/6B (promote/retire; Capabilities list deferred)
7. One prompt-config mechanism, zero inert subsystems (P7). ✅ PEC-7A (`PEC-7A-convergence.md`)
8. The boundary contract still holds — zero upward imports, RULE_21 intact. ✅ (unchanged spine; PEC-ID-1 attribution additive)

**Track closed 2026-09-16** — see `TASKS.md` §PEC + `TASK-RESULTS.md` PEC-* sections.
Follow-ups (non-blocking): Capabilities registry list API; seed django_db tests when Postgres up; ratify ADR-0033.
