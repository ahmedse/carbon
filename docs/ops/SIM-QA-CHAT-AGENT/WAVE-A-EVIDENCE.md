# WAVE A — Evidence (real browser)

**Env:** local `http://localhost:5179` · Backend `:8009`  
**Brand observed:** ClearTurn · **EduOS** (not Nibras)  
**Role:** `ahmed` ADMIN  
**Date:** 2026-09-19  
**Runner:** QA real-user · Lead seat: Nibras  
**Fix policy:** findings only — **no firefighting** this wave

---

## Env gate findings (before scenarios)

| ID | Sev | Finding | Owner |
|----|-----|---------|-------|
| ENV-01 | P1 (program) | Local stack boots as **EduOS** brand — Domain apps = GradeVance / Learn / Teach only. **No People / My / Team / Emissions** cards. Nibras + Emissions packs are **BLOCKED** on this tenant until Nibras/emissions-branded instance or multi-brand switch. | DevOps / brand config · Nibras+Pulse |
| ENV-02 | P2 | Notifications popover leaves an invisible MUI backdrop that **blocks Show Pulse** until Escape. | Pulse FE |
| ENV-03 | P2 | Agent chrome still shows activity **Tasks · Monitor · Results** alongside ADR-0043 **Plan · Run · Canvas · Output** — dual IA. | Pulse FE |

---

## Scenarios executed

### S-MODE-01 — Open Pulse + Chat/Agent toggle
Steps: Login → Show Pulse → Expand → Chat pressed → Agent pressed.  
Binary: **PASS**  
Scores: UX:3 INT:n/a MEM:n/a LRN:n/a C21:n/a REF:n/a DEP:2 CAN:n/a A11Y:4 REG:n/a · mean:~3.0  
Notes: Toggle works; header copy sometimes lags (“Agent” subtitle while Chat still pressed for one frame).

### S-SEG-01 — Plan · Run · Canvas · Output visible
Steps: Agent mode with open task → see four segment toggles.  
Binary: **PASS**  
Scores: UX:4 · mean:4.0  
Notes: Segments present: Plan, Run, Canvas, Output. Status chip `8/10 · consent needed` + Needs approval.

### S-SEG-02 — Soft default lands on Run when consent needed
Steps: Open paused OSCE/LCT task.  
Binary: **PASS**  
Scores: UX:4 C21:5 · mean:4.5  
Notes: Run pressed; “Run paused — a step needs your approval”; Approve / Decline on blocked step. Matches ADR-0043.

### S-SEG-03 — Plan exclusive hero (DAG)
Steps: Click Plan.  
Binary: **PASS**  
Scores: UX:4 CAN:n/a · mean:4.0  
Notes: Plan graph chrome (zoom/fit/export) + step nodes; Approve list chrome gone → exclusive Plan. No Job Map on Plan.

### S-SEG-04 — Canvas exclusive (no step list)
Steps: Click Canvas.  
Binary: **FAIL** (content) / **PASS** (exclusivity)  
Scores: UX:2 CAN:1 C21:4 · mean:~2.3  
Notes: Canvas segment selected; step list/Approve gone (good exclusivity). **Body appeared empty** — no OpsCanvasHost / empty-state copy visible in viewport. Treat as **P1 Canvas empty** for this seeded Agent Job Map case until Pulse confirms artifact `plan_id` wiring on live data.

### I-C21-01 — RULE_21 consent on Run
Steps: Observe blocked `deny_compensation_request` step with Approve/Decline.  
Binary: **PASS**  
Scores: C21:5 UX:4 DEP:4 · mean:4.3  
Notes: Cross-domain seed (GradeVance OSCE + People compensation) shows consent CTA on Run — correct placement.

### S-MODE-02 — Chat mode available from Agent
Steps: Chat mode control present and releasable.  
Binary: **PASS**  
Scores: UX:4 · mean:4.0  

### X-MIX-01 — Cross-domain task brief visible
Steps: Task “Mark OSCE… then stage compensation deny… Employee 333”.  
Binary: **PASS** (surface)  
Scores: DEP:4 INT:4 · mean:4.0  
Notes: Intelligence depth not scored this wave (no new live LLM turn). Seed proves multi-domain Agent task exists.

---

## Scoreboard rollup (Wave A so far)

| Metric | Value |
|--------|-------|
| Executed | 8 |
| PASS | 6 |
| FAIL | 1 (S-SEG-04 content) |
| PARTIAL | 1 (S-SEG-04 exclusivity OK) |
| BLOCKED (domain packs) | Nibras B1, Emissions B2 on this brand |

**Mean of PASS rows:** ~4.0  
**Open P1:** Canvas blank (S-SEG-04); EduOS-only brand blocks Nibras/Emissions real-user packs (ENV-01)

---

## Next runner actions (no code)

1. Pulse ACK SIM-20260919-N1 → triage Canvas empty + dual Tasks/Monitor chrome  
2. Lease / switch **Nibras-branded** local (or staging) for Wave B1  
3. EduOS ACK SIM-20260919-N2 → continue GradeVance depth on this brand (Learn/Teach)  
4. Continue Wave A: Output + Run health, Memory panel, Chat live turn scoring  

---

*No product code changed in this wave (anti-firefighting).*
