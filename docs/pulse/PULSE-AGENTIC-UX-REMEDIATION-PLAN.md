# Pulse Agentic UX — Unified Remediation Plan (Master)

> **Status:** Track A–E **Done** (2026-09-20). Operator calm chrome shipped under ADR-0043 V5.  
> **Companions:** `PULSE-AGENTIC-UIUX-AUDIT-KB.md`, `PULSE-AGENTIC-WORKFLOW-AUDIT-KB.md`, Cursor canvas `pulse-agent-uiux.canvas.tsx`.  
> **Evidence:** `docs/pulse/evidence/UX-NA-RESHOOT-2026-09-20.md` · `docs/pulse/evidence/TRACK-E-OPERATOR-CALM-2026-09-20.md`.  
> **Binding IA:** ADR-0043 **V5** · `docs/SCREEN-SPEC-AGENT-FOUR-VIEW-COCKPIT.md`.  
> **Toolkit:** `.ai-toolkit/shared/ux-patterns.md` · RULE_21 / RULE_23 · no shallow stubs.

## Goal

Functionally complete · visually simple · never overwhelm. Same engine; calm chrome.  
Tracks A–D fixed honesty / consent / routing. Track E reduces decisions and Operator noise.

## Design locks

1. Agent = planner; Chat = advisor — route, don’t force-fit.  
2. Cards + recommended default > open quizzes.  
3. Helpful ≠ continue the wrong workflow.  
4. Errors: Acknowledge → Boundary → Options → Recommend → CTA.  
5. **≤3 primary CTAs** on Operator Plan (Approve · Cancel plan · Discuss).  
6. Autonomy dial = UI density only — never auto-approve writes.  
7. No new chart library (ADR-0011/0012). Reuse `PlanDagGraph` / `OpsCanvasHost`.  
8. Exclusive heroes only (ADR-0043). Never DAG + Job Map + full list on one scroll.

---

## Track A — Mid-run HITL truth — **Done**

| ID | Work | Status |
|----|------|--------|
| A1–A5 | Consent hero, Output pause honesty, chip copy, jargon demotion | **Done** |

## Track B — Bad usage / discovery routing — **Done**

| ID | Work | Status |
|----|------|--------|
| B1–B4 | `scope_route`, leave ≠ DQ, ScopeRouteCard | **Done** |

## Track C — Clarify, honesty, receipts — **Done**

| ID | Work | Status |
|----|------|--------|
| C1–C4 | Deixis, idle contract, export gap, consent chip | **Done** |

## Track D — Trust dials & receipts — **Done**

| ID | Work | Status |
|----|------|--------|
| D1–D4 | Rerun receipt, autonomy dial, topic stack, non-admin PASS | **Done** |

---

## Track E — Operator calm chrome

| ID | Work | Status |
|----|------|--------|
| E1 | **Plan:** toolbar under tabs (renameable label); graph + docked RichContent pane; no overlay drawer / Finished; Approve · Cancel · Discuss | **Done (V6)** |
| E2 | **Run:** chronicle (time · event · status) default; transport bar; params collapsed; Run health lives here | **Done** |
| E3 | **Canvas:** story-first Job Map (goal → stages → here → outcome); demote QoS / RULE_ / tool ids for Operator | **Done** |
| E4 | **Output:** Answer + files only; file Delete with confirm; no Run health accordion | **Done** |
| E5 | Lifecycle copy + i18n (en/ar) + Vitest + evidence; refresh UIUX canvas | **Done** |

### E acceptance (Given / When / Then)

- Given `pending_approval` Plan, When Operator lands, Then ≤3 primary actions and structure graph visible; no stage wall; no Finished/run status on Plan.
- Given Run with steps, When Operator opens Run, Then chronicle events render; INPUT/API JSON not visible until expand.
- Given Canvas Job Map, When Operator views, Then no raw `RULE_` strings; story layers readable.
- Given settled Output, When Operator views, Then no Run health accordion; Answer + artifact cards; Delete confirms consequence.
- Given Cancel plan, When confirmed path used, Then plan `cancelled` (same as prior Decline API).

### Non-goals (Track E)

- Do not remove Replan / Fork / Rename from the product — demote only.  
- Do not auto-approve writes when autonomy = Faster.  
- Do not merge Chat into Agent tabs (ADR-0014).  
- Do not rebuild the engine graph model or invent a fifth pane.

---

## Proof bar

| Check | Gate |
|-------|------|
| Operator Plan chrome | ≤3 primary CTAs; Cancel plan label |
| Run chronicle | Events from real step statuses; clocks when timestamps exist |
| Canvas | Human story; Analyst expand for tools/QoS |
| Output purity | Zero Run health on Output; Delete wired to `DELETE ai/artifacts/:id/` |
| Toolkit | `verify.sh frontend` / Vitest green; ADR-0043 V5 + Screen Spec aligned |
