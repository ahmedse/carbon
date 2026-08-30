# TASK-RESULTS-SPRINT-18-QA — QA Validation Report

Date: 2026-08-17 · Role: QA/Validator · Model: DeepSeek V4 Pro · Phase: Sprint-18 (AI Workspace UX polish + Pulse rebrand) · Source: `tasks/SPRINT-18-AI-WORKSPACE-UX.md`, `e2e/journeys/journey-10-ai-workspace.spec.ts`, `e2e/journeys/journey-11-ai-coworker-dq.spec.ts`

---

## Executive Summary

**Verdict: PASSED WITH FINDINGS** — 1× P1, 3× P2 (test-owner), 16× P2 (stale unit specs), 2× P3.

The Sprint-18 UX polish and **Pulse** rebrand are implemented and render correctly. Static gates (lint, build) are clean; the Pulse logo, header, empty-state, and session chrome are all rebranded with no user-facing "AI Workspace" leftovers. The automated regression gate surfaced **one real backend defect** (edit + regenerate → HTTP 500, event-loop error) that cascaded 10 downstream tests into "did not run" — including the cross-org RBAC isolation suite (SEC2–SEC6) and the W1–W10 UX audit — so L2/L4 automated coverage is **incomplete as a direct consequence of that defect**. All remaining Playwright failures (Part A A1, Part B B5, Part C C2) are **test-fragility defects, not product defects**, and the 16 failing unit tests are **stale pre-Sprint-18 specs** that were never updated alongside the component rewrites.

### Issue counts by severity

| Severity | Count | Notes |
|----------|-------|-------|
| P0 | 0 | — |
| P1 | 1 | S17 edit/regenerate → 500 (backend event-loop bug) |
| P2 | 20 | 16 stale unit specs + 3 E2E test-fragility defects + 1 S16 pagination finding (cosmetic) |
| P3 | 2 | Hardcoded hex in `MarkdownMessage.jsx` and `StatusBar.jsx` (RULE_8) |

---

## Layer 1: Structural Gate Results

| Check | Tool | Result |
|-------|------|--------|
| Frontend lint | `npm run lint` | ✅ Clean (exit 0) |
| Frontend build | `npm run build` | ✅ Clean (12.29s) |
| Frontend unit tests | `npm test -- --run` | ⚠️ 16 failed / 430 passed / 446 total — all 16 are stale pre-Sprint-18 specs (see F2) |
| Selector edits (J1) | `get_errors` on journey-10/11 | ✅ No compile/lint errors on the 7 selector fixes |
| Rebrand sweep (J4) | grep for user-facing "AI Workspace" | ✅ Clean — no user-facing leftovers |

**Notes:** `verify.sh full` (django check / backend pytest / antipatterns) was **not** re-run in this pass; the Sprint-18 scope is frontend UX + rebrand, and the backend is explicitly out of scope (§5 non-goals). L1 for the changed surface (frontend) is clean except the stale unit specs, which are test defects not product defects.

---

## Layer 2: Security (API-Level RBAC)

| Check | Evidence | Result |
|-------|----------|--------|
| SEC1 — Anonymous → 401 (list/create/retrieve/send) | journey-10 `SEC1` | ✅ 401 on all four |
| SEC7 — Admin full CRUD on own conversation | journey-10 `SEC7` | ✅ 201/200/200/200 |
| Part C1 — Viewer `/admin/ai/workspace` gate | journey-11 `C1` | ✅ Redirected off admin console |
| SEC4 — Data-owner list excludes admin-owned | journey-10 `SEC4` | ⏭️ SKIPPED (serial cascade after S17) |
| SEC5 — Data-owner retrieving admin-owned → 404 | journey-10 `SEC5` | ⏭️ SKIPPED (serial cascade after S17) |
| SEC6 — Data-owner PATCH/DELETE admin-owned → 404 | journey-10 `SEC6` | ⏭️ SKIPPED (serial cascade after S17) |
| SEC2 — Viewer can create own conversation | journey-10 `SEC2` | ⏭️ SKIPPED (serial cascade after S17) |
| SEC3 — Viewer can send to own conversation | journey-10 `SEC3` | ⏭️ SKIPPED (serial cascade after S17) |
| Part C3 — Viewer has no DQ manage controls | journey-11 `C3` | ⏭️ SKIPPED (C2 failure ended the test) |

**⚠️ Coverage gap:** `journey-10` uses `test.describe.serial`. The S17 failure (F1) halted the serial chain, skipping 5 cross-org RBAC isolation tests (SEC2–SEC6). Cross-org isolation at the HTTP layer is therefore **not re-verified this cycle** and must be re-run once F1 is fixed.

---

## Layer 3: Functional

Playwright gate: `npx playwright test --config e2e/playwright.config.ts journey-10-ai-workspace journey-11-ai-coworker-dq` → **18 passed / 4 failed / 10 did not run**.

| # | Check | Result |
|---|-------|--------|
| S1 | `/admin/ai/workspace` renders for admin | ✅ Pulse heading visible |
| S2 | Create conversation → 201 id/title/status | ✅ |
| S3 | Chat stream completes, no ScopeGuard/empty-user error | ✅ |
| S4 | Stop generation idempotent (200) | ✅ |
| S5 | Assistant message persisted (status/follow-ups) | ✅ |
| S6 | Feedback accept/reject/corrected → 200 | ✅ |
| S7 | `#`-mentions menu (#table/#rule/#field/#module) | ✅ |
| S8 | Send modes (queue/steer/stop) | ✅ Stop-generation icon while working |
| S10 | Summarize → 200 + summary | ✅ |
| S11 | Rename via PATCH → 200 (empty → 400) | ✅ |
| S12 | Search filter (q) | ✅ |
| S12b | Pin via PATCH + `?is_pinned=true` | ✅ |
| S13 | Archive active tab, no MUI invalid-value warning | ✅ |
| S14 | Restore + delete lifecycle | ✅ |
| S15 | List filters (status/type/is_archived/is_pinned) | ✅ |
| S16 | Pagination >50 messages | ⚠️ first-page `has_more=true` (correct with 55 seeded → 50/page) |
| S17 | Edit user message + regenerate → 200 | ❌ **500** (F1) |
| S18–S20, S9 | stream types / transparency tooltip / list scroll / export | ⏭️ SKIPPED (serial cascade) |
| Part A A1 | dataowner open workspace + new chat | ❌ test-fragility (F3) |
| Part B B1–B4 | module/table entry points, Validate DQ, Suggest+Accept | ✅ |
| Part B B5 | NL rule test → Execute Mode → Save Rule | ❌ test-fragility (F4) |
| Part B B6–B7 | Investigate / Ask-about-this | ⏭️ SKIPPED (B5 ended the test) |
| Part C C2 | copilot available to viewer | ❌ test-fragility (F5) |

---

## Layer 4: UX / Browser Audit

Live walkthrough (VS Code integrated browser, admin persona) confirmed the rebrand renders correctly:

- **Pulse rebrand ✅** — `PulseLogo` (`img "Pulse logo"`), header `Pulse`, `Close Pulse`, footer toggle `Show Pulse` / `Hide Pulse (Ctrl+\)`; no "AI Workspace" text anywhere.
- **Empty state ✅** — `Pulse Ready` + `Start a Chat` + starter chips (`Start with a domain app`).
- **Session chrome ✅** — `Sessions` panel, type badges (`Chat`, `Rule`, `DQ`, `NL`, `Alert`), `Session options for <title>`, `New chat` action.
- **Status bar ✅** — `Ready` + `Execute Mode` toggle + share/export.

| # | Check | Result |
|---|-------|--------|
| W1 | RENDER — no console errors | ✅ |
| W3 | EMPTY — sensible empty state | ✅ "Pulse Ready" + "Start a Chat" |
| W4 | ERROR — no offline banner leak | ✅ |
| W5 | DARK_MODE | Not exercised this cycle (read-only audit) |
| W10 | NO_404_LINKS | ✅ (footer Privacy/Terms/Support resolve) |
| RULE_8 | Theme tokens only | ⚠️ 2× hardcoded hex (F6, F7) |

---

## Findings

| ID | Severity | Symptom | Evidence / Reproduction | Suggested Owner |
|----|----------|---------|-------------------------|-----------------|
| F1 | **P1** | **Edit user message + regenerate assistant reply → HTTP 500.** Broken write path; also halts the serial E2E chain, skipping 10 downstream tests (SEC2–SEC6, W1–W10, S9, S18–S20). | Playwright S17: `PATCH …/messages/{userMsg.id}/` with `{content:"…(edited)"}` → expect 200 → **received 500**; then POST regenerate → 500. Backend log: `RuntimeError: no running event loop` at `backend/ai/engine_runtime.py:62`; `pulse.cognition.turn.runner` "Fan-out attempt failed; falling back to multi-step/single-pass" at `backend/ai/engine/cognition/turn/runner.py:185`. | Backend (AI engine) |
| F2 | P2 | **16 unit-test specs fail** — stale pre-Sprint-18 DOM assertions never updated with the component rewrite. | `npm test -- --run`: `AIMessageBubble.feedback` (5), `AIMessageBubble.transparency` (1), `AIArtifacts` (2), `AISharedThreads` (4), `AIWorkspace.shell` (4). Assertions reference removed `Accept`/`Reject`/`Correct`/`Promote` buttons, `gpt-4o · 1234 tok` usage chip, `Shared` chip, `role="tab"`/`role="separator"`, `Close conversation <title>` labels. | Test owner (frontend) |
| F3 | P2 | **E2E Part A A1 timeouts** — `newChat` helper races the conversation-list load: it does an immediate `.count()` on `New chat`, falls through to `Start a chat` (empty state) which never renders because the user has existing sessions. | journey-11 `newChat` (line 60–68); 600s timeout, snapshot shows workspace already open with `New chat` present. Fix: `await expect(newChatBtn.first()).toBeVisible()` then click. | Test owner (E2E) |
| F4 | P2 | **E2E Part B B5 fails** — "Test live" creates a scoped `nl_rule_test` conversation but does **not** auto-send, so the NL-rule-test card never renders. | `AIConversationView.handleTestLive` → `transferTask('nl_rule_test', …)`; `AITaskTransferContext.transferTask` auto-sends only for `investigate`/`report_draft`. Snapshot shows session `NL test: rule` with empty thread ("Send a message to start the conversation."). Fix: send a message after `Test live`, or auto-send for `nl_rule_test` if the spec requires it. | Test owner (E2E) — or Product if §6 DoD requires auto-run |
| F5 | P2 | **E2E Part C C2 fails** — a new viewer with no sessions renders the empty state, not a `Message input`. Assertion targets the wrong element. | Snapshot: `Pulse Ready` + `Start a Chat` + `No sessions yet`. Product behavior is correct; assertion should target `Start a Chat`/`New chat`/`Pulse`, not `Message input`. | Test owner (E2E) |
| F6 | P3 | **Hardcoded hex** violates RULE_8 (theme tokens only). | `carbon-frontend/src/shell/MarkdownMessage.jsx`: `#21252b`, `#9da5b4`, `#282c34`, `#abb2bf`. | Frontend (shell) |
| F7 | P3 | **Hardcoded hex** violates RULE_8. | `carbon-frontend/src/shell/StatusBar.jsx`: `#f87171`, `#fbbf24`, `#fff`. Likely pre-existing / out of Sprint-18 scope. | Frontend (shell) |

**Deliberately excluded (§5 non-goals — deferred backend bugs, do NOT file):** `PULSE_SECRET_KEY`/`STUDIO_PASSWORD` weak secrets, `_DjangoSession.execute`, `Pipeline user=None`, naive `LLMCallLog.created_at`.

**S16 note (not a defect):** pagination first-page `has_more=true` is correct behavior given 55 seeded messages → 50 returned per page.

---

## Gate Verdict

**PASSED WITH FINDINGS**

No P0 defects. Sprint-18 UX polish + Pulse rebrand are functionally delivered (lint/build clean, rebrand complete, 18/32 E2E tests green including SEC1/SEC7/C1 RBAC and S1–S16 core flows).

**Defect handoff list (exact):**

1. **[P1] F1** — Backend: fix `no running event loop` in `backend/ai/engine_runtime.py` / `backend/ai/engine/cognition/turn/runner.py` so message edit + regenerate returns 200. Write a regression test first (red → green, `shared/testing.md` RULE 1). After fix, re-run the full journey-10/11 gate to recover the 10 skipped RBAC/UX tests.
2. **[P2] F2** — Frontend test owner: update the 16 stale unit specs to the Sprint-18 DOM (hover-toolbar `Accept response`/`Reject response`/`Copy message`/`More message actions`, outcome chip, session listbox, `Sessions`/`Context`/`Investigate`/`Artifacts` activity bar).
3. **[P2] F3/F4/F5** — E2E test owner: fix `newChat` race, add post-"Test live" send (or auto-send), and correct the viewer empty-state assertion.
4. **[P3] F6/F7** — Frontend shell: replace hardcoded hex with theme tokens in `MarkdownMessage.jsx` and `StatusBar.jsx`.

*Validated only — no product code was changed in this pass.*
