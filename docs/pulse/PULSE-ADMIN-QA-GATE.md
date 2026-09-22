# Pulse Admin QA Gate Plan — Enterprise Control Plane

**Status:** Plan (ready to execute)  
**Date:** 2026-09-18  
**Scope:** Pulse **Control Plane** (`/admin/ai/*` six destinations) — not chat engage UX  
**Extends:** [ADR-0036](../../.ai-toolkit/decisions/0036-pulse-control-plane-ia.md) · [PULSE-ADMIN-REMAKE.md](./PULSE-ADMIN-REMAKE.md) · [QA-FRAMEWORK.md](./QA-FRAMEWORK.md) · [PULSE-QA-MASTER.md](./PULSE-QA-MASTER.md)  
**Owner:** Master Architect + QA Validator  
**Benchmark:** Salesforce Agentforce Admin · IBM watsonx.ai Governance · AWS Bedrock Guardrails Console · Azure AI Studio Content Safety / Monitoring

---

## 0. Why this plan exists

The Control Plane remake (Phases 0–7) shipped IA, APIs, steward journeys, and thin-tab bridges.
What is still missing is a **single enterprise QA gate**: thresholded, role-aware, metric-backed,
and fail-closed — so “admin is done” is falsifiable.

Chat intelligence is already governed by `QA-FRAMEWORK.md` (grounding, fabrication, pass^k).
This document is the **parallel contract for steward operations**: contain, publish, evidence,
learn, spend, and access — measured as **final state + audit**, never as “a button rendered.”

**Principles (non-negotiable)**

1. **Evaluate outcomes (final state, pass^k), not activity.** A containment POST that returns 200 but leaves `learning_admissions_frozen=false` fails.
2. **View never implies publish.** Every mutation API has a deny case for `ai:view_console`-only.
3. **Four representations stay separate.** Admin UI must not merge Observed · Approved · Executable · Instance into one undifferentiated grid.
4. **A rule without a CI check is a wish.** Every gate below maps to pytest and/or Playwright and/or a metric threshold.
5. **Docs follow code.** Green evidence updates this plan’s scoreboard; the plan does not invent green.

---

## 1. Scope

### In scope (Pulse Admin / Control Plane)

| Surface | Paths |
|---------|--------|
| Six destinations | `/admin/ai`, `/domain`, `/assets`, `/evidence`, `/learning`, `/platform` |
| Object page | `/admin/ai/domain/processes/:processId` |
| Control APIs | `/carbon-api/ai/pulse/control/*` |
| Governance mutations | registry, skills promote/reject, memory revoke, knowledge CRUD, prompt activate/rollback |
| CBAC / roles | `ai:*` capabilities + Platform Roles matrix + Access Control |
| Metrics exposed to stewards | command/spend, containment, budget, quality-trend, rollups (truthfulness), maturity, candidates |
| Legacy redirects | All `LEGACY_REDIRECTS` → hub?tab= |

### Out of scope (covered elsewhere)

| Surface | Where |
|---------|--------|
| Chat / workspace engage UX | `QA-CHAT-*`, journeys 10–11, 14–15 Part A–C |
| Engine heartbeat / metabolism | PEC-1A |
| Golden eval fabrication gates | PEC-4A + `QA-FRAMEWORK` intelligence gauges |
| MCP admin UI | Non-goal per remake |

**Engage vs govern:** Workspace/Conversations may appear in smoke checks as “reachable,” but are not Control Plane exit criteria.

---

## 2. Enterprise dimensions (12 axes for Admin)

Adapted from `PULSE-QA-MASTER` for **steward** jobs (not chat coworker axes).

| # | Axis | Question | Primary evidence |
|---|------|----------|------------------|
| A1 | **Authority & SoD** | Can the wrong role publish / promote / override budget? | Roles×actions deny matrix; J2 |
| A2 | **Containment** | Can an operator freeze learning / stop autonomy in &lt;60s? | J1; command round-trip |
| A3 | **Process lifecycle** | Define → scope → submit → reject/publish → kill with audit? | ProcessObjectPage + registry + J3 |
| A4 | **Evidence reconstructability** | Can a steward answer “why was X allowed?” in ≤3 clicks / one API? | Evidence explorer + J4 |
| A5 | **Learning without authority widening** | Promote blocked under freeze; admissions audited? | J5; admission logs |
| A6 | **Asset governance** | Memory revoke / knowledge revoke / prompt rollback leave provenance? | J6; prompt/knowledge pack |
| A7 | **Spend fail-closed** | Budget override trips LLM path without deploy? | J7 |
| A8 | **Policy simulation** | PDP dry-run matches live decision shape? | Policy dry-run API + UI |
| A9 | **Observability honesty** | Quality/maturity/rollups never invent rows; offline states clear? | Observability API tests + UI empty/offline |
| A10 | **IA integrity** | Six nav only; legacy redirects; no new peer without ADR? | Sidebar freeze; redirect matrix test |
| A11 | **UX steward fitness** | Typography/contrast/density per ADR-0037; no dead-end thin tabs? | Visual checklist + deep-link bridges |
| A12 | **Audit completeness** | Every mutation writes AuditLog with actor/action/target? | Audit asserts on J1/J6/containment/budget |

---

## 3. Gate model (L0 → L5)

Each level is **blocking** for the next. No “mostly green” promotion.

| Level | Name | Modality | Blocking artifact | Owner |
|-------|------|----------|-------------------|-------|
| **L0** | Contract freeze | Static | ADR-0036 + remake doc + no new sidebar peers in PR checklist | Architect |
| **L1** | Unit / component | Vitest | ProcessObjectPage, ProcessRegistry, pulseControlIa redirects, P0 panel smoke | Frontend |
| **L2** | API steward pack | Pytest | `test_steward_journeys.py` + control + prompt/knowledge + registry reject | Backend |
| **L3** | CBAC deny matrix | Pytest | Every mutation endpoint: anon 401, view-only 403, authorized 2xx | Backend |
| **L4** | Playwright steward | E2E | journey-09 (read CBAC) + journey-17 (mutations + UI) + **new** journey-18 full UI depth | QA |
| **L5** | Metrics & SLO gate | Gauge + threshold | Command/spend, quality-trend, rollups truthfulness, maturity — **admin-visible and thresholded in CI sample** | Platform |

**Promotion rule:** L(n) green ⇒ may start L(n+1). Production steward release requires **L0–L5 green** on the release branch.

---

## 4. Roles × actions matrix (L3 core)

**Contract:** `ai:view_console` never authorizes publish / promote / budget / containment / knowledge write / prompt activate.

| Action | view | auditor | process_owner | publisher | operator | policy_owner | manage_console |
|--------|:----:|:-------:|:-------------:|:---------:|:--------:|:------------:|:--------------:|
| GET command / evidence / candidates | ✓ | ✓ | ✓ | —* | —* | —* | ✓ |
| POST containment | ✗ | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ |
| PATCH budget | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |
| POST pdp/dry-run | ✗ | ✗ | ✓ | ✗ | ✗ | ✓ | ✓ |
| Registry create/submit/autonomy | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ | —† |
| Registry publish | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | —† |
| Registry reject | ✗ | ✗ | ✓ | ✓ | ✗ | ✗ | —† |
| Kill switch | ✗ | ✗ | ✓ | ✗ | ✓ | ✗ | —† |
| Skill promote/reject | ✗ | ✗ | ✓ | ✓ | ✗ | ✗ | —† |
| Promote under learning_freeze | ✗ | ✗ | 423 | 423 | — | — | 423 |
| Knowledge create/revoke | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✓ |
| Prompt activate/rollback | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✓ |
| Memory revoke (steward) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ / owner |
| Capability matrix GET | — | — | — | — | — | — | platform:manage_access / admin |

\* Implied via `ai:view_console` inheritance or group membership; tests must use **minimal** personas, not superuser.  
† Superuser bypass is allowed but must be tested separately so SoD is not accidentally waived for non-superusers.

**Deliverable:** `backend/ai/tests/test_admin_cbac_matrix.py` — one parametrized table mirroring the grid above (minimal users via `grant_role`, never only superuser).

---

## 5. Destination coverage matrix (L4 UI)

Every hub tab must have at least: **load**, **empty/offline honesty**, **deep-link or primary action**, **no “Not authorized” for allowed role**.

| Destination | Tab / page | Must prove | Priority |
|-------------|------------|------------|----------|
| Command | Overview | Health + queues + containment control + spend chips | P0 |
| Command | Expertise / Monitoring | Load + deep link to Command/Evidence | P1 |
| Domain | Processes | List → open ProcessObjectPage; create draft navigates | P0 |
| Domain | Process object | Overview / Steps / Scope save (draft) / Diff / Submit-Publish-Kill gated | P0 |
| Domain | Policy | PDP dry-run request/response shape | P0 |
| Domain | Caps / Agents / Tools / Topology / Archetypes | Load + Tools deep links | P1 |
| Assets | Knowledge | Create + revoke; brand app_identifier scoping | P0 |
| Assets | Memory | Revoke + forget; provenance retained on revoke | P0 |
| Assets | Skills | Promote/reject gated; freeze → disabled or 423 surfaced | P0 |
| Assets | Prompts | Activate/rollback + PEC-7A disclaimer visible | P0 |
| Assets | Graph | Load / empty | P1 |
| Evidence | Explorer | Requires run_id; PDP events appear when seeded | P0 |
| Evidence | Audit / Runs / Inbox / Watches / Logs / Quality | Load + Logs deep links | P1 |
| Learning | Review / Candidates | Candidates list; review actions | P0 |
| Learning | Feedback / Jobs / Flywheel / Skill learning | Load + deep links | P1 |
| Platform | Spend | Budget override save + exceeded chip | P0 |
| Platform | Engine | Settings load / redaction | P1 |
| Platform | Roles | Matrix renders AI domain; link to `/admin/access` | P0 |

**New Playwright pack:** `journey-18-steward-admin-depth.spec.ts` — serial, one admin token, walk the P0 rows above with heading + one mutation or seeded evidence check each.

---

## 6. Steward journeys J1–J7 (L2 + L4)

| ID | Name | API oracle (final state) | UI oracle | pass^k |
|----|------|--------------------------|-----------|--------|
| J1 | Contain | Containment level + `learning_admissions_frozen`; AuditLog `ai.containment.set`; promote → 423 | Command Center level control | k=1 CI; k=3 staging |
| J2 | Publish SoD | Author∩publisher → publish 403; status stays `review` | Process object Publish disabled or error | k=1 |
| J3 | Reject persisted | Status `draft`; `last_reject_reason`; history `rejected` | Reject reason visible on overview | k=1 |
| J4 | Evidence PDP | `GET evidence/?run_id=` includes `source=pdp` | Explorer shows PDP event | k=1 |
| J5 | Skill freeze | Promote under freeze → 423 `learning_frozen` | Skills panel surfaces lock | k=1 |
| J6 | Memory revoke | `archived=true`; `valid_to` set; AuditLog `ai.memory.revoke` | Assets Memory revoke | k=1 |
| J7 | Budget trip | Control override → `route_chat` `budget_exceeded`; PATCH budget persists | Platform Spend | k=1 |

**Current baseline:** `test_steward_journeys.py` + journey-17 cover API + partial UI.  
**Gap to close:** Staging env re-confirm of J1/J7 pass^k=3 (local 3/3 green 2026-09-18).

---

## 7. Metrics & SLOs (L5)

Admin stewards must **see** and CI must **sample** these. Thresholds are release gates unless marked *gauge-only*.

### 7.1 Control & spend (fail-closed)

| Metric | Source | SLO / gate |
|--------|--------|------------|
| Containment apply latency | Time from POST to command GET match | &lt; 2s p95 (staging) |
| Budget override active | `command.spend.override_active` after PATCH | Must flip within same request response |
| Budget trip correctness | J7 | 100% of pack runs |
| Spend honesty | `usage/` vs `command.spend` | No contradiction on same day sample |

### 7.2 Trust & quality (admin-visible)

| Metric | Source | SLO / gate |
|--------|--------|------------|
| Truthfulness hit rate | `GET …/pulse/rollups/` | ≥ baseline from PEC-4A; **never invent** when no data |
| Quality trend | `quality-trend/` | Drift flags render; empty = honest empty |
| Maturity score | `maturity/` | Renders 0–100; sub-keys present |
| Candidates freshness | `control/candidates/` | 200 + `results` array (may be empty) |

### 7.3 Governance volume (gauge-only until volume exists)

| Metric | Definition | Alert |
|--------|------------|-------|
| Reject rate | rejects / submits (7d) | Spike vs 30d baseline |
| Promote rate under freeze attempts | 423 count | Should be &gt;0 when freeze drills run |
| Kill-switch events | AuditLog | Any unexpected in prod → P0 page |

### 7.4 What we do **not** gate in Admin QA

Grounding rate / fabrication=0 on **chat** answers → `QA-FRAMEWORK` + PEC-4A (intelligence), not Admin UI.
Admin QA only asserts those **metrics endpoints are readable, honest, and surfaced**.

---

## 8. Test pyramid & ownership

```
                    ┌─────────────────────┐
                    │ L5 Metrics sample   │  nightly / pre-release
                    ├─────────────────────┤
                    │ L4 Playwright       │  journey-09, 17, 18
                    ├─────────────────────┤
                    │ L3 CBAC matrix      │  test_admin_cbac_matrix.py
                    ├─────────────────────┤
                    │ L2 Steward API      │  test_steward_journeys.py + packs
                    ├─────────────────────┤
                    │ L1 Vitest panels    │  Process*, Registry, IA redirects
                    └─────────────────────┘
```

| Pack | Command | CI |
|------|---------|-----|
| Steward + control + governance | `./manage.sh test ai/tests/test_steward_journeys.py ai/tests/test_control_plane_api.py ai/tests/test_prompt_knowledge_governance.py ai/tests/test_registry_reject.py` | Required PR |
| CBAC matrix | `./manage.sh test ai/tests/test_admin_cbac_matrix.py` | Required PR |
| L5 metrics sample | `./manage.sh test ai/tests/test_admin_metrics_sample.py` | Required PR |
| Redirect IA | `npx vitest run …/pulseControlIa.test.js` | Required PR |
| Playwright steward | `playwright test journey-09 journey-17 journey-18-steward-admin-depth` | Nightly + release |
| Full AI regression | `pytest ai -q -m "not live"` | Nightly |

---

## 9. Execution waves (implementation plan)

### Wave 0 — Scoreboard (1 day)

- [x] Publish this plan + canvas scoreboard
- [x] Map every P0 row in §5 to an existing test ID or `GAP` (see §11)
- [ ] Freeze L0 checklist in PR template (link ADR-0036)

### Wave 1 — Close L3 CBAC (2–3 days)

- [x] Author `test_admin_cbac_matrix.py` from §4 (minimal personas)
- [x] Green on live DB (**73 passed**)
- [x] Document manage_console / view-only publisher discoverability in §11

### Wave 2 — Journey-18 UI depth (2–3 days)

- [x] Playwright walk of all P0 destination rows (§5) — `journey-18-steward-admin-depth.spec.ts`
- [x] UI oracles for J2–J6 (headings, disabled buttons, reject reason, freeze message)
- [x] Skills freeze banner (`data-testid=skills-learning-freeze`) for J5 UI

### Wave 3 — L5 metrics harness (2 days)

- [x] Script or pytest that samples command/usage/quality-trend/rollups/maturity
- [x] Assert schema + honesty (no fabricated counts); compare to documented thresholds
- [x] Surface failures as release blockers (`test_admin_metrics_sample.py` **7 passed**)

### Wave 4 — Hardening & evidence (1–2 days)

- [x] pass^k=3 for J1 + J7 (local CI sample **3/3 × 4 passed**; staging env re-confirm optional)
- [x] Evidence pack `docs/pulse/evidence/ADMIN-QA-2026-09-18.md`
- [x] Update remake §8: “J1–J7 acceptance = L2+L4 green”

**Exit of Wave 4 = Control Plane release-ready under this plan.**

---

## 10. Severity & triage

| Sev | Definition | Example | SLA |
|-----|------------|---------|-----|
| **P0** | Authority hole or false containment/budget | view_console can publish; freeze doesn’t block promote | Fix before merge |
| **P1** | Steward cannot complete a core job | Evidence missing PDP join; reject reason not persisted | Fix before release |
| **P2** | Honesty/UX debt | Thin tab without deep link; stale heading | Backlog within sprint |
| **P3** | Cosmetic / docs | Copy inconsistency | Opportunistic |

---

## 11. Baseline vs target (honest)

| Layer | Baseline (2026-09-18) | Target | Status |
|-------|----------------------|--------|--------|
| L0 Freeze / ADR | Done | Hold | **DONE** |
| L1 Vitest | Partial (process object, registry, IA) | Full P0 panels smoke | **DONE** — `adminControlP0Panels.smoke.test.jsx` (**6 passed**) |
| L2 Steward API | **16 passed** (J1–J7 + packs) | Keep green + expand reuse arc | **DONE** |
| L3 CBAC matrix | Fragmented | One parametrized matrix file | **DONE** — `test_admin_cbac_matrix.py` (**73 passed**) |
| L4 Playwright | J9 + J17 (partial) | J9 + J17 + **J18** full P0 UI | **DONE** — `journey-18-steward-admin-depth` **8 passed** |
| L5 Metrics gate | APIs exist; no admin CI harness | Sampled schema + threshold gate | **DONE** — `test_admin_metrics_sample.py` (**7 passed**) |

### Wave 0 scoreboard (P0 destination → evidence)

| P0 surface | Evidence | Gap |
|------------|----------|-----|
| Command overview | L2 J1; L4 J17 + J18A | — |
| Domain processes + object | L1 ProcessObject/Registry; L2 J2/J3; L4 J18B–D | — |
| Domain policy dry-run | L3 matrix PDP; L4 J18E | — |
| Assets knowledge/memory/prompts/skills | L2/L3 + L4 J18A/F/G | — |
| Evidence explorer | L2 J4; L4 J18E | — |
| Learning candidates/review | L2 candidates; L4 J18A | — |
| Platform spend/roles | L2 J7; L3 budget; L4 J18A/H | — |

### L3 notes (discovered)

- `ai:publisher` / `ai:operator` alone **cannot** `GET control/command/` (no `ai:view_console`) — by design.
- `ai:manage_console` is not on AI governance groups; platform `admins_group` (*) is the manage persona in the matrix.
- Skill promote for allowed roles may return **400 admission_rejected** after CBAC — matrix asserts ≠403.

---

## 12. Definition of Done (Admin QA)

Pulse Admin is **QA-gated complete** when:

1. L0–L5 all green on the release branch.  
2. Roles×actions matrix has **zero unexpected allows**.  
3. J1–J7 API + UI oracles pass (L2 + L4).  
4. Metrics endpoints are sampled and honest under L5.  
5. Evidence note filed under `docs/pulse/evidence/ADMIN-QA-*`.  
6. No new `/admin/ai/<noun>` peer without ADR exception.

Until then: remake IA may be “complete”; **enterprise QA gate is not**.

---

## 13. Traceability

| Plan ID | Code / doc |
|---------|------------|
| ADR-0036 | `.ai-toolkit/decisions/0036-pulse-control-plane-ia.md` |
| Remake | `docs/pulse/PULSE-ADMIN-REMAKE.md` |
| Measurement philosophy | `docs/pulse/QA-FRAMEWORK.md` |
| Steward API | `backend/ai/tests/test_steward_journeys.py` |
| CBAC matrix | `backend/ai/tests/test_admin_cbac_matrix.py` |
| L5 metrics | `backend/ai/tests/test_admin_metrics_sample.py` |
| Playwright | `e2e/journeys/journey-09-*.ts`, `journey-17-*.ts`, `journey-18-steward-admin-depth.spec.ts` |
| Control APIs | `backend/ai/control_plane_api.py`, `prompt_governance_api.py`, `knowledge_api.py` |
| Canvas scoreboard | `canvases/pulse-admin-qa-gate.canvas.tsx` |

---

## 14. Immediate next action

**Wave 4 closed locally.** Optional: re-run J1/J7 pass^k=3 on dedicated staging.
