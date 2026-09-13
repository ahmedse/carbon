# Audit — Carbon Data Trust Platform & Nibras vs. the Enterprise System Framework (CESF)

**Date:** 2026-09-13
**Role:** Master Architect
**Scope:** ClearTurn Trust Platform core + Nibras instance (People & Payroll, e-office correspondence, Chairman/Payroll consoles) — the whole "our platform" surface.
**Benchmark:** `docs/ENTERPRISE-SYSTEM-FRAMEWORK.md` (CESF v1.0), itself derived from `DrHazemAli/enterprise-system-design` + world-class systems.
**Method:** each framework requirement is scored against the *observable runtime state* of the codebase, not against documentation claims. Items marked **[verify]** are hypotheses to confirm with a focused read/test before acting.

---

## 0. Executive summary

The platform is **stronger than typical enterprise software at the two hardest problems**
— AI authority control and data trust — and **weaker than it needs to be at the
operational layer that turns those strengths into a defensible production system**.

**Maturity by pillar (L0–L5 scale, §12):**

| Pillar | Level | Verdict |
|--------|:-----:|---------|
| Engineering (boundaries, invariants) | **L2** | Strong boundary discipline in code (RULE_3 import gates, GuardChain, append-only DataRow); enforcement exists, but invariants are not yet stated as falsifiable runtime checks. |
| AI discipline (zero-trust execution) | **L2+** | Best-in-class for a mid-market stack: `CarbonIntelligence` + GuardChain + `command_boundary.py` (validate→PDP→consent→budget→idempotency→execute→verify) + MutationGuard. Gaps are in *evidence*, not authority. |
| Data trust (catalog/DQ/MDM/lineage) | **L2** | Governance models exist and are append-only, but lineage/impact/search/masking are still feature gaps (see §4). |
| Mission-critical (idempotency, safe-state) | **L1** | AI layer has idempotency. **Nibras payroll does not (no evidence of an idempotency key or `unknown`-outcome state on the pay-run path)** — the single most consequential gap in the whole platform. |
| Reliability & operations (SLOs, tracing) | **L1→L2** | OpenTelemetry is wired (P1-11); **no consequence-oriented SLOs, no error budgets, no burn-rate alerting, no circuit breakers/bulkheads, no fault injection**. |
| Security (zero trust, capability auth) | **L2** | ScopedRole + capability files (`accounts/capabilities.py`) + CBAC backfill; strong. Gaps: field-level masking/encryption on PII (civil ID), platform-wide rate limiting, secrets posture. |

**The three gaps that matter most, in order:**

1. **Nibras payroll is a C0/C1 consequential flow with no demonstrated idempotency /
   `unknown`-outcome / reconciliation path.** A lost WPS/GOSI response or a double-click
   "Run payroll" must not be able to produce a duplicate run. This is the "one
   legally-signable payroll month" promise from `NIBRAS-MASTER-STRATEGY.md` — it must be
   *provable*, not assumed. **[verify pay-run path]**
2. **No consequence-oriented operating model.** We measure uptime and logs, not
   consequence classes, error budgets, or burn rate. Incidents will be diagnosed by
   narrative, not by causal trace — exactly the failure CESF §7 warns about.
3. **AI authority is enforced, but not yet *evidenced* end-to-end.** GuardChain runs
   before every call, but there is no single immutable record linking a consequential
   action to its admitted output → final context hash → promotion decision set (CESF §6.3).

---

## 1. Strengths — what we already do right (do not regress)

| Framework principle | Where it lives today |
|---------------------|----------------------|
| **Boundary-first (§2)** | RULE_3 core↔hosted import gates, `audit-imports.sh` (I1 engine + I2 app-to-app), `ai/domain/{app}.py` domain isolation (RULE_19). |
| **No data leakage (§6.3, F6)** | `ScopeGuard` + `DataIsolationGuard` (scope.org_unit_ids on every query), CBAC-partitioned `ai/store.py`, cache keys carry app/org identity (RULE_20). |
| **No auto-mutation (§6.1, F5)** | `MutationGuard` + RULE_21 (AI suggests, Carbon executes; `requires_confirmation=True`); `command_boundary.py` idempotent execution. |
| **Fail-visible degradation (F7)** | AI ops degrade gracefully (`pulse_unavailable` not 500; deterministic fallback; RULE_13). |
| **Explicit state (§4.1)** | Append-only `DataRow` with `_MUTABLE_FIELDS`; versioned compliance rules (`ComplianceRule`); evidence trail via `evidence` app. |
| **Contracts in code (§4.1)** | `ai/protocol.py` imports nothing from Django/DRF/provider (pure contract); ADRs 0000–0030. |
| **Capability-scoped auth (§6.2)** | `ScopedRole` + `accounts/capabilities.py` + `GROUP_CAPABILITIES` + CBAC backfill. |
| **Config-not-code (Salesforce lesson, §8)** | Per-instance `.env` presets + app registry (`register-all + enable-per-instance`); no `if company == GOFSCO` in the payroll engine (rotation/leave as configurable schedule/policy types). |
| **Modular monolith (§9)** | One Django codebase, many isolated instances, per-instance DB — the right call at mid-market scale (avoids the distributed-monolith trap). |

---

## 2. Gap matrix

Legend — **Severity:** P0 blocking the compliance/trust promise · P1 required for production
maturity · P2 competitive parity · P3 future. **Confidence:** ✅ verified in code · 🟡
partial/indirect evidence · 🔶 **[verify]** hypothesis to confirm.

| # | Framework requirement (§) | Current state | Gap | Sev | Conf |
|---|---------------------------|---------------|-----|-----|------|
| G1 | Idempotency + `unknown` state on consequential writes (§5.2) | AI/feedback/management commands are idempotent; **no evidence of an idempotency key or `unknown`-outcome state on the payroll run / GOSI / WPS submission path** | Duplicate pay-run / lost-receipt risk on the single most regulated flow | **P0** | 🔶 |
| G2 | Consequence-oriented SLOs + error budgets (§7.1) | No consequence classes, no SLI catalog, no burn-rate policy | Incidents prioritized by narrative; no deliberate budget spend | **P0** | ✅ |
| G3 | Causal observability (§7.2) | OpenTelemetry wired (settings.py P1-11); **no span discipline on trust-boundary crossings, no idempotency-key event on side effects** | Trace exists but cannot answer "why *this* request failed *this* way" | **P1** | 🟡 |
| G4 | Lineage graph + impact analysis (§8, Databricks/Palantir lesson) | `lineage` JSON field exists, **no query/visualization** (matches prior audit) | Cannot prove "why is this number this number" — the Nibras moat is unrealized | **P0** | ✅ |
| G5 | Field-level security + masking (§2.2 isolation, §6) | RBAC is module/table-scoped; PII classification (`civil_id.py`, `sensitivity.py`) exists but **no automatic redaction/masking at read time** | Civil IDs / compensation exposed to any org-scoped reader | **P1** | 🟡 |
| G6 | Admission control + backpressure (§5.3) | AI `RateLimiter` exists; **platform APIs have no rate limiting, no circuit breakers, no bulkheads** | Retry storms / overload collapse on platform + TurnKey bridge | **P1** | ✅ |
| G7 | Determinism envelope (§6.4) | No declared determinism tier, no envelope hash, no golden replay | Cannot distinguish model drift from runtime drift in AI regressions | **P2** | ✅ |
| G8 | Output-admission evidence chain (§6.3) | GuardChain + MutationGuard enforce; **no immutable admitted-output → context-hash → promotion-set record** | Audit can't reconstruct *why* a consequential AI action fired | **P1** | 🟡 |
| G9 | Governed change / canary / rollback (§7.3) | Docker redeploy script; **no canary, no budget-gated freeze, no rollback-proof of data+cache+policy** | Rollback restores code only | **P1** | 🟡 |
| G10 | Versioned APIs (§4.1) | `/carbon-api/` prefix, no `/v1/` | Contract drift with no negotiation surface | P2 | ✅ |
| G11 | Full-text catalog search (§8) | Django ORM filters only | Catalog unusable at 10K+ assets | P2 | ✅ |
| G12 | Workflow / approval engine (§2.4 promotion gate) | No approval chains; `status='approved'` is manual | Payroll/leave sign-off and DQ remediation lack a promotion gate | **P1** | ✅ |
| G13 | Business glossary hierarchy + semantic layer (§8) | `GlossaryTerm.synonyms` flat JSON; no metric definitions | No BI/metric semantics over governed data | P2 | ✅ |
| G14 | Data observability (freshness/volume SLIs) (§7.1) | DQ runs exist; no freshness SLIs, no volume anomaly alerts | Silent stale data undermines the trust promise | **P1** | 🟡 |
| G15 | Kill switch + recovery rehearsal (§5.1, §7.3) | AI fail-visible exists; **no tested kill switch with measured activation latency, no fault injection** | Cannot prove containment under uncertainty | **P1** | 🔶 |
| G16 | Instance DB isolation checklist (§2.2, CLEARTURN §5.4) | Isolation by deployment; **checklist ⚠️ not yet documented/proven** | Cross-instance reach risk is assumed, not tested | P1 | 🟡 |
| G17 | Cost attribution per org/tenant (§3) | No storage/compute attribution | Cannot answer "which customer costs what" | P3 | ✅ |
| G18 | Secrets / supply-chain posture (§2.4, SLSA) | LLM keys env-only (good); **no secret scanning hook wired, no artifact provenance** | Credential leak / supply-chain risk | P2 | 🟡 |
| G19 | Discriminating tests (§4.3) | Strong unit/integration suite (741 backend / 330 frontend); **few negative/chaos tests at trust boundaries** | "Tests pass" is weaker than the failure classes it must cover | P2 | ✅ |
| G20 | Federated metadata import (Unity/Purview/Collibra) (§8) | No external catalog sync | Lock-in; manual re-entry | P3 | ✅ |

---

## 3. Deep dives on the P0/P1 gaps

### 3.1 G1 — Nibras payroll: the consequence path (P0)

The `NIBRAS-MASTER-STRATEGY.md` promise is "one legally-signable payroll month," traceable
to the versioned rule that produced every figure. That promise is a *safety property*, not a
feature: **one logical pay-run must produce at most one committed run, even across timeout,
retry, and a lost WPS/GOSI response.**

What CESF §5.2 requires, and what we must build/confirm:

1. A **pay-run idempotency key** = `(tenant, payroll_period, employee_batch, intent_version)`,
   canonicalized and hashed, **reserved before dispatch** to GOSI/WPS.
2. An **`unknown` outcome state** on the pay-run aggregate (not "failed"), with owner,
   deadline, budget, and a reconciliation job that queries the authoritative GOSI/WPS receipt.
3. A **receipt** from the effect owner, not the caller's assumption.
4. **Compensation** (a reversal pay-run / adjustment) as another idempotent intent.

> **[verify]** Trace `people/payroll_service.py` + `calculation_engine.py` end-to-end and
> confirm whether (a) a natural idempotency key already exists, (b) the run state machine
> has an `unknown`/`outcome_unknown` state, and (c) there is a reconciliation job. If any is
> missing, this is the first build item.

### 3.2 G2 — consequence-oriented SLOs (P0)

We currently have no answer to "what must remain available, and what must we prevent when
it isn't?" Concretely:

- Map the top journeys: **Run payroll**, **Submit WPS/GOSI file**, **Sign-off leave**,
  **Chairman overview load**, **AI coworker ask**.
- Assign consequence classes (C0–C3) and one SLI each (e.g., payroll-month completion
  *correctness*, not request count).
- Define a weekly + monthly error budget and a burn-rate alert policy.
- Wire the budget to change policy (freeze on burn).

### 3.3 G4 — lineage: the unrealized moat (P0)

Nibras's defensibility ("prove why this number is this number, back to the rule version")
is currently **stored but not queryable**. The `lineage` field is data without a product.
Priority: a minimal, traversable lineage from a payroll figure → its inputs (employee
master, benefit ledger, attendance, rotation) → the `ComplianceRule` version that computed
it. This is what turns "governance theater" into a signed-off artifact.

### 3.4 G3/G8 — evidence: trace + output admission (P1)

OpenTelemetry is wired but *undisciplined*. Two cheap, high-value upgrades:

1. **Span discipline**: emit a span event on every trust-boundary crossing (auth, guard
   decision, promotion, side effect) with `{idempotency_key, outcome, policy_version}`.
2. **Output-admission record**: persist, per consequential AI action, the
   `admitted_output_id → final_context_hash → promotion_decision_set` chain (CESF §6.3).
   GuardChain already computes most of the inputs; the missing piece is *recording* them
   immutably.

### 3.5 G5 — field-level PII (P1)

`civil_id.py` + `sensitivity.py` imply classification exists. What's missing is **read-time
masking** tied to capability: a `people:view` role must see masked civil IDs unless it holds
`people:view_pii`. This is an isolation-boundary fix, not a schema change.

---

## 4. Prioritized remediation backlog

| Rank | Item | Effort | Value |
|------|------|--------|-------|
| 1 | **[verify] Payroll idempotency + `unknown` state + reconciliation** (G1) | M | Protects the compliance promise |
| 2 | **Minimal lineage traversal for payroll figures → rule version** (G4) | M | Realizes the Nibras moat |
| 3 | **Consequence classes + 5 SLIs + error budget + burn policy** (G2) | S/M | Operates the platform defensibly |
| 4 | **Trust-boundary span events + output-admission record** (G3/G8) | M | Turns AI authority into evidence |
| 5 | **Read-time PII masking by capability** (G5) | S | Civil-ID/compensation safety |
| 6 | **Platform rate limiting + circuit breaker on TurnKey** (G6) | M | Overload containment |
| 7 | **Approval workflow for payroll sign-off + DQ remediation** (G12) | L | Promotion gate for consequential state |
| 8 | **Data freshness/volume SLIs** (G14) | S | Stale-data detection |
| 9 | **Kill switch + fault-injection drill** (G15) | M | Containment proof |
| 10 | **Versioned API (`/v1/`)** (G10) | S | Contract negotiation surface |

Effort: S = small (≤1 phase), M = medium (1–2 phases), L = large (3+ phases).

---

## 5. Verification plan (how we prove the audit is not itself "governance theater")

1. **G1** — add a discriminating test: replay the same pay-run intent after a timeout and
   assert at most one committed run and one GOSI/WPS submission (CESF §4.3).
2. **G2** — instrument the 5 top journeys; assert each has a consequence class, an SLI, and
   a burn-alert rule; demonstrate a budget-burn → change-freeze transition in a staging test.
3. **G4** — assert every regulated payroll figure can be traced to a `ComplianceRule`
   version in ≤3 hops via an API query.
4. **G3/G8** — assert a consequential AI action produces an immutable
   `admitted_output → context_hash → promotion_set` record, and that a failed admission
   yields a machine-readable reason code (never a 500).
5. **G5** — assert `people:view` (without `people:view_pii`) receives masked civil IDs.
6. **G6** — load-test the TurnKey bridge and assert the circuit opens rather than cascading.

---

## 6. Bottom line

The platform has the *hard architectural calls already right*: modular monolith, core↔app
boundaries, AI-as-proposer/Human-as-executor, config-not-code multi-instance, append-only
trust data. What it lacks is the **operating layer that converts those strengths into
defensible production evidence**: idempotent consequential writes, consequence-oriented
SLOs, causal trace discipline, lineage traversal, and read-time PII masking.

Close those five, and Carbon + Nibras moves from "a strong platform that will be trusted"
to "a platform that can *prove* it is trusted" — which is precisely the promise on the tin.
