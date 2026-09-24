# TASK-RESULT-QA-ADR-0043 — Agent Four-View Cockpit

**Seat:** Pulse · **Roles:** QA/Validator + Master Architect review  
**Date:** 2026-09-19 · **Scope:** ADR-0043 V1–V4 vs Screen Spec  
**Spec:** `docs/_archive/design-superseded/SCREEN-SPEC-AGENT-FOUR-VIEW-COCKPIT.md`  
**ADR:** `.ai-toolkit/decisions/0043-agent-four-view-cockpit.md` (Implemented)

---

## Executive Summary

**Gate verdict: PASSED WITH FINDINGS**

ADR-0043 exclusive Plan · Run · Canvas · Output is structurally sound: Job Map is
unstacked from Run, Canvas loads by `plan_id`, Metrics is demoted, soft lifecycle
defaults are unit-covered, frontend build is clean, targeted Vitest **64/64**.

Findings are **non-blocking** (P2/P3): no Playwright consent→Run journey, Screen Spec
status string stale, registry does not list new shell components, L4 browser not re-run
in this session.

---

## Layer 1 — Structural

| Check | Result | Evidence |
|-------|--------|----------|
| `./.ai-toolkit/scripts/scan.sh` | ✅ | Registry refreshed 2026-09-19 |
| Vitest ADR-0043 suite (7 files) | ✅ | **64/64** passed |
| `npm run build` | ✅ | Clean build ~18.6s (chunk size warnings pre-existing) |
| Dual Job Map on Run | ✅ | `AgentRunSurface.test`: no `agent-run-job-map` / `agent-run-job-map-board` |
| Exclusive hero | ✅ | `AgentCockpit.test`: one `agent-cockpit-hero-*` at a time |
| i18n en+ar | ✅ | `cockpit*`, `jobMapEmpty`, `runHealth`, `statusConsentNeeded` present |

`verify.sh full` / full backend suite **not** re-run this refresh (frontend-scoped change;
no Django edits in V1–V4).

---

## Layer 2 — Security

| Check | Result | Notes |
|-------|--------|-------|
| New auth surface | N/A | Reuses existing `listArtifacts` / plan APIs |
| Canvas 403 path | ⚠ | Uses `notifyFromError` (spec OK); no dedicated 403 UI copy test |

No new endpoints. No L2 curl campaign this session.

---

## Layer 3 — Functional vs Screen Spec

| Acceptance | Result | Evidence |
|------------|--------|----------|
| One exclusive hero | ✅ | Vitest exclusive hero test-ids |
| No Job Map under Run DAG | ✅ | Run surface stripped; Canvas owns board |
| Lifecycle soft defaults | ✅ | `defaultCockpitSegment` unit tests + AITaskPanel effect |
| Canvas by `plan_id` | ✅ | `AgentCanvasSurface` + `listArtifacts({artifact_type, plan_id})` |
| Canvas empty + retry | ✅ | `agent-canvas-empty` / error + Retry tests |
| Status chip | ✅ | `agent-status-chip` + `runHeaderStatusChip` |
| Metrics demoted | ✅ | Output → Run health accordion; no Metrics segment |
| Consent not auto-Canvas | ✅ | Defaults send paused/running → **Run** |
| Playwright: consent lands on Run | ❌ | **Gap** — ADR V2 gate named Playwright; only Vitest today |

---

## Layer 4 — UX / Screen Spec states

| State | Plan | Run | Canvas | Output |
|-------|------|-----|--------|--------|
| loading | ⚠ (detailLoading via AgentStage path) | ✅ Starting alert | ✅ spinner | ✅ artifacts spinner |
| empty | ✅ | ✅ | ✅ copy + Retry | ✅ “Run the plan…” |
| error | — | step chips | ✅ Retry | notify |
| loaded | ✅ | ✅ | ✅ OpsCanvasHost | ✅ + Run health |

**Browser (W1–W10):** not re-executed this session — **P3** gap for live smoke.

---

## Findings

| ID | Sev | Symptom | Suggested owner |
|----|-----|---------|-----------------|
| F1 | P2 | No Playwright e2e for “paused/consent → Run segment” (ADR V2 gate) | Frontend Worker |
| F2 | P3 | Screen Spec header still “APPROVED for implementation” after ship | Master (doc) |
| F3 | P3 | Registry `components.md` does not list `AgentCockpit` / `AgentCanvasSurface` | Master / scan coverage |
| F4 | P3 | L4 live browser smoke not re-run this refresh | QA (next session) |
| F5 | P2 (track) | COMMS `20260918-3` Catalog Trust Index ACK still open — blocks Catalog | Pulse Master |

---

## Master Architect (Pulse) review

**I am Master: Pulse.**

- ADR-0043 closed for product IA; classic 6-tab remains debug hatch (accepted).
- Do **not** reopen stacking DAG + Job Map.
- Next Pulse dispatch priority: **Catalog REQUEST 20260918-3** (ACK + trust-ranked grounding), then optional F1 Playwright.
- EduOS/Nibras: no action from this audit.

**Master gate on ADR-0043 UI:** accept as **shipped** with F1–F4 debt tracked; F5 is separate track.
