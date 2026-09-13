# Pulse — QA, Measurement & Evaluation Framework

**Status:** canonical spec (P0-11). Defines *what "measured" means* for Pulse's intelligence and its features.
**Reads with:** `PULSE-MASTER.md` (§guards/§learning), `INVARIANTS.md`, `EFFECT-PATHS.md`, `PILOT.md`.
**Feeds:** P0-07 (replay fixtures), P1-13 (fail-open lint), P1-17 (red-team), Phase 4 (process evals), D9 (escalation A/B).

---

## 0. Why this exists

The audits and this remediation plan carry two non-negotiable principles:

- **"Evaluate outcomes (final state, pass^k), not activity."**
- **"Docs follow code — a rule that isn't a CI check is a wish."**

The codebase already instruments a lot of behavior — `confidence_label`, `honest_uncertainty`, `ungrounded_claim`, veto verdicts, `intent_zone`, mutation blocking — and ships a handful of live-probe scripts. But the measurement is **ad-hoc and activity-based**: most "checks" assert that a phrase appeared in the response (`has_any(text, "retrieved")`), not that the *verified final state* changed correctly. Nothing connects the scattered scripts into one thresholded gate.

This document is that gate. It is a **through-line**, not a new subsystem: it turns P0-07, P1-17, Phase 4, and D9 from four disconnected boxes into one measurable, versioned contract.

---

## 1. Core model — measurement mirrors the four representations

The platform invariant is *"four representations, never merged."* Measurement has one lens per representation. Confuse them, and you get the exact "knowledge ≠ authority" failure the plan is built to prevent.

| Representation | Meaning | What we measure against it |
|---|---|---|
| **Observed behavior** | events, traces, real turns | Behavioral evals + continuous gauges |
| **Approved definition** | registry, policy versions, process contracts | Conformance checks (deviation → violation) |
| **Executable implementation** | capabilities + host services | Per-capability contract tests |
| **Current instance** | run state + verified outcomes | Final-state assertions + pass^k |

**Rule:** an intelligence signal (grounding, calibration, refusal) is measured on *observed behavior*. A feature claim ("this tool works") is measured on *current instance* — i.e. the final DB state — never on whether the answer *mentioned* the tool.

---

## 2. Two axes, two modalities

### 2.1 Axes

1. **Intelligence** — the six-witness spine (S1→S6): grounding, honesty/calibration, intent, refusal, faithfulness, memory.
2. **Features** — the capability surface: `chat`, `call_host_api`, plan/ReAct, worker fan-out, skills, proactive delivery, MCP, sandbox, retrieval, memory. Each measured for **reliability + safety + cost**.

### 2.2 Modalities

| Modality | Nature | Runs when | Fail → |
|---|---|---|---|
| **Test** | binary (pass/fail), deterministic | commit / merge / phase-gate | blocks |
| **Gauge** | continuous sample, thresholded | staging + prod, drift detection | alert + audit |

Tests are the *rules*. Gauges are the *drift detector*. A gauge without a CI check is a wish (Principle 5).

---

## 3. Metric taxonomy

### 3.1 Intelligence gauges (reasoning quality)

| Gauge | Definition | Signal today | Target |
|---|---|---|---|
| **Grounding rate** | % answers citing real retrieval when retrieval exists | `ungrounded_claim` flag | 0 false "grounded" |
| **Bluff rate** | high `confidence_label` ∧ wrong answer | `confidence_label` vs oracle | 0% |
| **Calibration error (ECE)** | expected calibration error of `confidence` vs correctness | `confidence` field | < 0.15 |
| **Refusal precision** | of refusals, how many were correct | veto / `pulse_unavailable` | high |
| **Refusal recall** | of unanswerable probes, how many refused | off-limits probes | → 1.0 |
| **Zone accuracy** | correct `intent_zone` routing | `intent_zone` | 100% on fixtures |
| **pass^k** | k independent runs all pass final-state | **missing — to add** | k=3, 100% |

### 3.2 Feature gauges (one row per capability in the P0-06 inventory)

| Gauge | Definition |
|---|---|
| Success rate / error rate | tool call completes without error |
| Latency p50 / p95 / p99 | execution + retrieval + LLM |
| Flakiness | rerun variance on the same fixture |
| Contract conformance | input validated, output schema matches |
| Guard coverage | P0-06 column — is a guard *on the path* (not just defined) |

### 3.3 Safety & authority gauges (fail-closed axis)

| Gauge | Definition | Target |
|---|---|---|
| **Mutation-block rate** | red-team attempts blocked / total, across **every** P0-06 path | 100% |
| **Consent correctness (RULE_21)** | zero unconfirmed mutations execute | 100% |
| **Tenancy isolation** | cross-tenant reads return 0 rows | 0 rows |
| **Fail-closed** | injected guard crash → deny (never `pass`) | deny |
| **Audit completeness** | every effect has ledger + audit row (0 orphan effects) | 0 orphans |

### 3.4 Efficiency gauges

tokens/turn · cost/turn · **cost/outcome** (never cost/call) · budget adherence (P1-08) · retrieval efficiency (chunks fetched vs used) · escalation-lane A/B delta (D9).

---

## 4. The 4-layer evidence ladder (the QA gate)

Monotonic: a claim must clear L0 before L1 before L2 before L3. A later layer failing **fails the gate even if earlier layers pass**.

| Layer | What | Runs when | Exists today | Must add |
|---|---|---|---|---|
| **L0 — static/unit** | deterministic contract tests, fail-open lint (P1-13), import-linter, forbidden-grep | every commit (fast) | `test_critic_veto`, `test_retrieval_grounding`, `test_confidence_surface` | fail-open lint, import-linter enforce |
| **L1 — replay/golden** | P0-07 replay fixtures + curated grounded Q→A golden sets | every change | `eval_pulse_behavior.py` (40 msgs, no golden baseline) | committed golden JSON + drift report |
| **L2 — red-team + process** | P1-17 red-team across all P0-06 paths + τ-bench-style business-process evals w/ final-state assertions + pass^k | release gate | `test_multi_hop`, `test_parallel` (partial) | full P0-06 coverage + pass^k + final-state |
| **L3 — live canary** | staging/prod gauges, drift detection, sampled human review | continuous | `qa_pulse_smoke.py`, `test_answer_quality_live.py` | thresholds + dashboard |

---

## 5. The key upgrade — outcome, not activity

The single highest-value change. Replace phrase-presence checks with **final-state assertions**:

```python
# BEFORE (activity): did the answer *mention* a tool?
assert has_any(content, "get_calculation_summary")

# AFTER (outcome): did the *verified final state* change correctly?
assert dq_rules.filter(status="published").count() == 1   # the mutation happened
assert audit_log.filter(action="publish").exists()          # and was recorded
```

A "feature works" claim must end in a **state assertion** against the host DB. A "business process works" claim must run the pilot's 16 steps (PILOT.md) to completion — **pass^k** — the τ-bench method the plan already endorses. Anything else is activity theater.

---

## 6. Deliverables

| # | Artifact | Purpose | Depends |
|---|---|---|---|
| 1 | `backend/ai/eval/fixtures.py` | golden + replay loader (P0-07) | P0-07 |
| 2 | `backend/ai/eval/scorer.py` | per-gauge scoring (this taxonomy) | #1 |
| 3 | `backend/ai/eval/reporter.py` | one JSON report (supersedes scattered `qa_pulse_results_*.json`) | #2 |
| 4 | `backend/ai/eval/gauges.py` | continuous gauge defs + thresholds → audit/log path | #3 |
| 5 | `backend/ai/tests/redteam/` | red-team suite v1 (P1-17) | P1-02…P1-09 |
| 6 | `docs/pulse/QA-FRAMEWORK.md` | this file (canonical spec) | — |

---

## 7. Thresholds & gate wiring

| Gate | Must hold |
|---|---|
| **Merge** | L0 green + L1 no-drift |
| **Phase 1 exit** | L2 red-team 100% blocked + fail-closed lint clean |
| **Phase 4 exit** | business-process eval ≥ threshold + Pulse cites policy version on allow/block |
| **Continuous** | L3 gauges within thresholds; drift → audit row + alert |

**Anti-thin-implementation:** every gauge defined here ships with a test that fails when the gauge is absent or silent. A gauge that never emits a number is treated as "not implemented."

---

## 8. Relationship to the remediation plan

- **P0-06** supplies the path list every safety gauge iterates.
- **P0-07** supplies the fixtures L1 replays.
- **P1-13** automates L0's fail-open lint.
- **P1-17** is L2's red-team layer.
- **Phase 4** is L2's business-process eval.
- **D9** (escalation A/B) is the one *cost/outcome* gauge, measured on L1 fixtures.

This document is the connective tissue: it makes "did we improve intelligence and features?" a **computed answer**, not an opinion.
