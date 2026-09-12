# ADR 0031 — Pulse Unified Remediation Plan (D1–D12)

- **Status:** Accepted
- **Date:** 2026-09-13
- **Deciders:** Master Architect
- **Area:** cross-cutting

## Context

Two independent audits of Pulse (Deep Audit II + Research-backed Architectural Audit) disagreed on
framing but converged on substance: fail-open is the dominant defect, the engine/host boundary is
leaky (14+ engine files import `ai.models.*`), learning is shallow/theatrical, and process
"discovery" today is only schema discovery. The merged execution plan lives in
`docs/pulse/PULSE-UNIFIED-REMEDIATION-PLAN.md`. This ADR pins the 12 resolved disagreements (D1–D12)
so no worker re-litigates them mid-build.

## Decision

The unified plan is authoritative. The 12 resolved decisions:

- **D1 — Invariant I2, by layer.** Cognitive state (episodic, ledger, working memory) → engine calls
  a `port`; host adapter persists. Business effects → engine emits an `ActionProposal`; host command
  boundary executes. Rewritten I2: *"Engine holds no process-lifetime state and never commits durable
  state directly; all persistence and all effects go through host-implemented ports."*
- **D2 — Process definition shape.** Unified schema: steps + constraints + autonomy per activity +
  policies + evidence + exceptions + tests. Constraints give cheap conformance; steps give
  executability; tests gate publication.
- **D3 — Policy engine.** PDP is a **stage inside the command boundary**, not a peer. Start in-house
  (default-deny, forbid-overrides-permit, *error → refuse* for mandatory policies). Cedar spike in
  Phase 7 with an explicit diagnostics wrapper.
- **D4 — Skills.** Split guidance skills / executable-procedure references / candidates; use the
  Agent Skills folder format. An "executable" skill's body *references* `process.id@version`;
  `invoke_skill` creates/resumes a host run. No arbitrary `sql_macro`/`api_call` from skill bodies.
- **D5 — Tool coverage.** Depth first. Metric = number of capabilities with full contracts + process
  + evals. Second domain only after the pilot passes the Phase 4 gate.
- **D6 — Mining order.** Conformance first (Phase 5), discovery second (Phase 6). Mining output is
  never authoritative.
- **D7 — Durable runtime.** Harden Django for the pilot (strict workflow/activity split, idempotency
  keys, 9-state run machine). Bounded Temporal spike in Phase 7; ADR decides. No custom BPMN engine;
  no two runtimes in prod.
- **D8 — Admin console.** 7 screens under `/admin/ai/*`, 6 roles (`process_owner`, `policy_owner`,
  `publisher`, `operator`, `auditor`, `platform_admin`). `AI_VIEW_CONSOLE` never implies publish.
- **D9 — Escalation lane.** Measure, then decide. A/B on replay fixtures (Phase 2); keep only if it
  moves an outcome metric.
- **D10 — Approvals.** Approval bound to revision/args/evidence digest; three concepts separated in
  code: authorization (PDP), business approval (grant), user consent (RULE_21). Standing authorization
  is a separate future ADR, never inferred from an autonomy setting.
- **D11 — Requirements.** Interviewing process owners is a first-class discovery capability; Pulse
  generates an interview kit per process.
- **D12 — MCP.** Delete the UI surface now (Phase 1); wire in Phase 7 through the catalog + boundary.

**Sequencing discipline (non-negotiable):** fail-closed → boundaries → registry → expertise →
events/conformance → discovery/learning → scale.

## Alternatives Considered

- **Keep I1/I2 literally (engine emits proposals, host persists everything).** Rejected — collapses
  the cognitive/effect distinction; D1 keeps the literal rule for *business effects* while allowing
  ports for *cognitive state*.
- **PDP as a peer service (Cedar/OPA from day one).** Rejected — a peer PDP can be bypassed; a
  boundary stage cannot. Cedar deferred to Phase 7.
- **Chase 9/9 tool coverage.** Rejected — coverage vanity; depth-first (D5).
- **Temporal from day one.** Rejected — overkill before the pilot exists; harden Django first (D7).

## Consequences

- **Positive:** One authoritative plan; every task traces to a decided answer; workers can't fork the
  architecture; fail-closed defects are sequenced before all feature work.
- **Negative / trade-off:** The plan spans ~31 weeks; it deliberately defers MCP, Cedar, Temporal,
  and the escalation lane to keep the pilot honest.
- **Do NOT re-try:** a second reasoning spine (revive KG planner / new agent framework); an
  "autonomous mode" implying standing authorization; mining output as authoritative without a
  publisher; RestrictedPython as a security boundary; raw SQL predicates in the proactive path.

## References

- `docs/pulse/PULSE-UNIFIED-REMEDIATION-PLAN.md` (execution plan, phase gates, §8 first-10-actions)
- `docs/pulse/INVARIANTS.md` (I1–I8, L1–L7 recovered with status)
- `docs/pulse/PULSE-MASTER.md` (single source of truth)
- `docs/PULSE-DETAILED-AUDIT-ARCHITECTURE.md` (evidence backing)
