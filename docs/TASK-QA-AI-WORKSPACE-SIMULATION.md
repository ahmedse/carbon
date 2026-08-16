# TASK-QA-AI-WORKSPACE-SIMULATION
# Playwright Extensive-Use Simulation of ALL Implemented AI Workspace Features

- **Role:** QA/Validator (evidence only — NO product-code fixes)
- **Recommended model:** DeepSeek-V3
- **Domain:** Backend (Django/DRF) + Frontend (React/MUI) — validation only
- **Task ID:** QA-AI-WORKSPACE-SIMULATION
- **Parent:** Sprints 13–17 ("AI Workspace") — reported done, tag `v1.3`
- **Goal:** Prove — with Playwright + curl evidence — that EVERY implemented AI Workspace
  feature actually works end-to-end, not just that it exists in code.

---

## 0. Preconditions (do these BEFORE writing any test)

1. **Servers up** (verified with `./manage.sh status`):
   - Backend: `http://127.0.0.1:8009` (Django, API prefix `/carbon-api/`)
   - Frontend: `http://127.0.0.1:5179` (Vite dev, base `/`)
2. **Migrations applied** — this task exists because a 500 from an unapplied migration was
   shipped. Re-run and CONFIRM before anything else:
   ```bash
   cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py migrate --plan
   /home/ahmed/aast/carbon/.venv/bin/python manage.py migrate
   ```
   Expected: `No migrations to apply` (or a clean list with nothing about `ai.0007`).
3. **Restart backend** so the uncommitted working-tree fixes are live (see §1):
   ```bash
   cd /home/ahmed/aast/carbon && ./manage.sh restart backend
   ```
4. **Credentials (from `e2e/fixtures/users.ts` PERSONAS):**
   - admin: `admin` / `admin123` (superuser, pk=13, full AI access)
   - scoped: `alamien_dataowner` / `data123` (branch=alamien, non-admin)
   - viewer: `alamien_viewer` / `viewer123` (read-only, negative case)

---

## 1. Known Working-Tree Changes (verify as REGRESSION — do NOT re-fix)

`git status` shows three uncommitted edits on `main`. They are already applied; your job is
to **confirm they work** with evidence. If any FAILS, record it as a finding and hand to
Debugger/Fixer — do NOT edit them.

| File | Change | How to verify |
|------|--------|---------------|
| `backend/ai/intelligence.py` | `build_scope()` superuser branch now sets `user_identifier=str(user.pk)` (was missing → every admin AI call rejected by `ScopeGuard` with `"Scope with empty user_identifier"`) | Run unit test + live admin chat probe (§3 S3). **This is a P0 if it regresses.** |
| `backend/ai/tests/test_intelligence.py` | `test_superuser_returns_wildcard_scope` now asserts `scope.user_identifier == "13"` | `pytest ai/tests/test_intelligence.py -q` → pass |
| `carbon-frontend/src/shell/AIWorkspace.jsx` | `effectiveActiveId` fix — MUI `Tabs` no longer receives a null/stale `value` after archiving/closing the active tab | Exercise close/archive of the ACTIVE tab (§4 S13, S11) → no MUI "invalid value" error |

---

## 2. Feature Inventory (everything the simulation MUST touch)

Source of truth: `carbon-frontend/src/api/aiWorkspace.js` (API surface), `src/shell/*` (UI).

### Backend (validate via Playwright `request` context / curl + JWT)
- **Conversation CRUD:** `POST /carbon-api/ai/workspace/conversations/` (create, all 5 types:
  `chat`, `dq_validate`, `dq_suggest`, `nl_query`, `anomaly`), `GET` list (filters:
  `status`, `limit`, `q`, `is_archived`, `is_pinned`, `conversation_type`), `GET` retrieve,
  `PATCH` (title / is_pinned / is_archived / visibility), `DELETE`.
- **Message lifecycle:** `listMessages` (cursor pagination `before`/`after`, `has_more`),
  `sendMessage`, `sendMessageStream` (SSE), `editMessage`, `regenerateMessage`, `stopGeneration`.
- **Streaming:** chat streams token deltas; non-chat streams progress frames; `onDone`/`onStopped`/`onError`.
- **Enterprise:** `summarizeConversation` (deterministic fallback), `exportConversation`
  (`json`/`markdown`), `recordFeedback` (`accepted`/`rejected`/`corrected`),
  `acceptSuggestion`/`rejectSuggestion`, token usage attribution (`token_usage_json`).

### Frontend (validate via Playwright browser)
- `src/shell/AIWorkspace.jsx` — id-keyed store, archive/restore/pin/rename/delete, search,
  `Ctrl+W` (archive) / `Ctrl+Shift+T` (restore), offline banner.
- `src/shell/AIConversationTabs.jsx` — id-keyed Tabs, MoreVert menu (pin/rename/archive/delete),
  status dot, type label, close.
- `src/shell/AIConversationView.jsx` — stream-all send, queue/steer/stop modes, infinite scroll
  (`loadOlder`), Export menu (md/json), follow-up chips, feedback, working notice.
- `src/shell/AIMessageBubble.jsx` — follow-up chips, usage chip + tooltip, status chips
  (`Interrupted`/`Error`), provenance "Why this answer" tooltip, typed cards
  (`dq_suggestions`, `nl_query_result`, `anomalies`), feedback Accept/Reject/Correct.
- `src/shell/AIInputBar.jsx` — `#`-mention autocomplete (`#table`/`#rule`/`#field`/`#module`),
  send-mode Select (queue/steer/stop), aria-labels: `Message input`, `Send message`, `Send mode`, `Mention kinds`.

### Route
- `/admin/ai/workspace` (admin, requires `AI_VIEW_CONSOLE` capability) — reuses full `AIWorkspace`.

---

## 3. Layer 1 — Structural Gate (run first, stop if hard fail)

```bash
cd /home/ahmed/aast/carbon
./.ai-toolkit/scripts/verify.sh full        # django check + backend tests + frontend lint/build + antipatterns
cd backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_intelligence.py -q
```
Expected: verify.sh green (or warnings explained); `test_intelligence.py` green including
`test_superuser_returns_wildcard_scope`. Record exact tail output.

---

## 4. Layer 3 — Functional Simulation (Playwright spec `journey-10-ai-workspace.spec.ts`)

Create ONE new file: `carbon-frontend/e2e/journeys/journey-10-ai-workspace.spec.ts`.
Reuse the existing fixtures (`e2e/fixtures/users.ts`: `login`, `apiLoginWithRetry`,
`getAuthHeaders`, `navigateTo`, `assertVisible`). Use the `e2e/playwright.config.ts` config
(baseURL 5179, apiURL 8009, workers=1, sequential). Mark the spec `serial`.

Run command (full output, no tail-pipe):
```bash
cd /home/ahmed/aast/carbon/carbon-frontend && npx playwright test e2e/journeys/journey-10-ai-workspace.spec.ts --config e2e/playwright.config.ts
```

### Scenario map (each = one `test()` with explicit assertions)

| # | Feature | Steps / Assertions |
|---|---------|--------------------|
| S1 | Login + route | `login(page,'admin')` → `navigateTo('/admin/ai/workspace')` → `assertVisible` "AI Workspace" heading + `assertURL` ends `/admin/ai/workspace`. (Layer-4 W1/W7) |
| S2 | Create chat | POST conversation `{conversation_type:'chat'}` → 201, `status:'pending'`. UI: click "New chat" → new tab appears. |
| S3 | **Send + stream (P0 probe)** | UI: type in `Message input`, click `Send message`. Assert a working indicator appears, then an assistant bubble renders. **API invariant:** a successful chat MUST NOT return the ScopeGuard error. If `{"error":"AI call rejected by ScopeGuard…empty user_identifier"}` appears → **P0 finding** (regression of §1). Also assert via `listMessages` that the assistant message has `status:'complete'`. |
| S4 | Stop/interrupt | Send another message; while working, click stop (send-mode `stop` or stop button). Assert the assistant bubble shows status chip `Interrupted`. Verify `message.status === 'stopped'`. |
| S5 | Follow-up chips | On the latest assistant message (chat type), if `metadata.follow_up_questions` is non-empty, click one chip → assert a new user message is created with that text. If the model returns none, create a chat that asks "What questions should I ask next?" and assert chips render. |
| S6 | Feedback | On an assistant bubble, click `Accept` → assert outcome label `Accepted`; send another, click `Reject` → `Rejected`; then `Correct` → dialog opens → type correction → save → `Corrected`. Verify via API: `listMessages` shows `outcome` field. |
| S7 | Mentions | Focus `Message input`, type `#` → assert `Mention kinds` menu lists `#table`, `#rule`, `#field`, `#module`. Select `#table` → assert the token is inserted into the input. |
| S8 | Send modes | Change `Send mode` to `queue` while idle → send → assert queued behavior (message waits / flush on completion). Change to `steer` → send → assert steering path. Record what each mode does vs. the mode label. |
| S9 | Export | Click `Export conversation` → menu → `Markdown (.md)` → assert toast `Exported as Markdown` + a download is triggered. Repeat for `JSON (.json)` → `Exported as JSON`. |
| S10 | Summary | API: `POST …/conversations/{id}/summarize/` → 200 with a non-empty summary (deterministic fallback acceptable). |
| S11 | Pin/rename | MoreVert menu → `Rename` → set "Sim Renamed" → assert tab label updates. `Pin` → assert tab reorders to pinned section. |
| S12 | Search | Type into search box → assert tab list filters to matching titles only. Clear → all return. |
| S13 | Archive active tab (REGRESSION) | Open MoreVert → `Archive` on the ACTIVE tab → assert NO MUI `value provided to the Tabs component is invalid` error (this validates the `effectiveActiveId` fix). Active tab falls back to next visible conversation. |
| S14 | Restore + delete | Toggle "Archived" → assert archived tab present → `Restore` → assert back in active list. `Ctrl+W` archives active; `Ctrl+Shift+T` restores last archived. |
| S15 | List filters (API) | `GET conversations?is_archived=true` → only archived; `?is_pinned=true` → only pinned; `?conversation_type=dq_suggest` → only that type; `?q=Sim` → title match. |
| S16 | Pagination (API) | Seed 60+ messages for one conversation via API (loop `sendMessage` or insert), then `listMessages?limit=50` → `has_more:true`, `before`/`after` cursor round-trips return disjoint non-overlapping pages. |
| S17 | Edit + regenerate (API) | `PATCH message {id}` content → 200, content updated. `POST …/messages/{id}/regenerate/` → 200, new assistant reply generated. |
| S18 | Non-chat types | Create + send one of each: `dq_suggest` (assert typed `AI suggests N DQ rules` card + Accept/Reject buttons), `nl_query` (assert SQL block + result grid card), `anomaly` (assert anomalies card), `dq_validate` (assert validation result). Each via SSE; assert `onProgress` frames then `onDone`. |
| S19 | Transparency | Hover `Why this answer` tooltip → assert provenance lines (Conversation/App/Org units). Hover usage chip → assert model/tokens/cost/latency breakdown. |
| S20 | Infinite scroll | In a 60+ message conversation, scroll to top → assert older messages load (`listMessages` `before` paging fires; message count grows, no duplicates). |

> **Seeding note:** S16/S20 need >50 messages. Seed via the API with a tight loop and a
> short assistant echo; use the `request` fixture (not the browser) to avoid UI flakiness.
> Do NOT depend on a real LLM for every seed message — reuse `editMessage`/direct create.

---

## 5. Layer 2 — Security Simulation (RBAC matrix)

Use `getAuthHeaders(persona)` + Playwright `request` against `http://127.0.0.1:8009/carbon-api/ai/workspace/`.

| # | Check | Expected |
|---|-------|----------|
| SEC1 | No token → `GET conversations/`, `POST conversations/`, `GET conversations/1/`, `POST conversations/1/messages/send/` | `401` on every one |
| SEC2 | `alamien_viewer` → `POST conversations/` (create) | `403` (read-only role cannot create AI workspace content) |
| SEC3 | `alamien_viewer` → `POST conversations/1/messages/send/` | `403` |
| SEC4 | `alamien_dataowner` → `GET conversations/` | `200`; results scoped to own org (no admin-only or other-branch conversations). Assert no conversation owned by another user appears. |
| SEC5 | `alamien_dataowner` → `GET conversations/{admin-owned-id}/` | `404` (not visible) or `403` — must NOT return the admin's conversation. |
| SEC6 | `alamien_dataowner` → `PATCH/DELETE conversations/{admin-owned-id}/` | `404`/`403` — never `200`. |
| SEC7 | admin → all the above | `200`/`201` (full access). |

Record the exact HTTP code + response for each. Any `200` leak in SEC4–SEC6 = **P1** (RBAC leak).

---

## 6. Layer 4 — UX Browser Audit (10-point, on `/admin/ai/workspace`, admin role)

W1 RENDER (page + tabs), W2 LOADING (spinner while listing), W3 EMPTY (no conversations →
empty-state CTA), W4 ERROR (simulate offline → `AIOfflineBanner` renders), W5 DARK_MODE (toggle
theme → no hardcoded colors break), W6 BREADCRUMB, W7 TITLE (not default "React App"),
W8 RESPONSIVE (viewport 768px → no horizontal overflow), W9 KEYBOARD (`Ctrl+W`/`Ctrl+Shift+T`,
tab-focus on input), W10 NO_404_LINKS (no broken asset/route links in console).

Capture one screenshot per W-item on failure only (config `screenshot: only-on-failure`).

---

## 7. Output Contract — `docs/TASK-RESULT-QA-AI-WORKSPACE-SIMULATION.md`

Structure:
1. **Executive Summary** (2–4 sentences + verdict).
2. **Layer 1** — verify.sh tail output + `test_intelligence.py` output.
3. **Layer 2** — SEC matrix table with HTTP codes.
4. **Layer 3** — S1–S20 table: ✅/❌/⚠ per scenario + Playwright `e2e-results.json` summary
   (N passed / N failed / N skipped) + full `npx playwright test` terminal output pasted.
5. **Layer 4** — W1–W10 checklist.
6. **Findings table** — ID, severity (P0–P3), symptom, reproduction steps, evidence, suggested fix owner.
7. **Gate verdict** — exactly one of: `PASSED` / `PASSED WITH FINDINGS` / `FAILED`.

### Verdict rules (from `shared/qa-framework.md`)
- Any **P0** → `FAILED`.
- Any **P1** → `PASSED WITH FINDINGS` (P1 blocks v-next release, not rollback).
- Only **P2/P3** → `PASSED WITH FINDINGS`.
- Clean → `PASSED`.

---

## 8. DO NOT TOUCH

- Any product code under `backend/` or `carbon-frontend/src/` (you may only ADD the
  `e2e/journeys/journey-10-ai-workspace.spec.ts` test artifact).
- The three files in §1 — do not edit; only verify and report.
- `e2e/playwright.config.ts`, `e2e/fixtures/users.ts` — reuse as-is; do not modify.
- Do not run `manage.py flush` / drop the DB / change migrations.

## 9. Hard Rules (from `project.config.md`)

- **PostgreSQL only.** Never touch/fall back to SQLite. Dev DB is `localhost:5432`.
- **Never** hand-edit secrets into test files — reuse `PERSONAS`/`getAuthHeaders`.
- Report real-time output; never silent-tail-pipe a run.
- Evidence over description: every ✅ needs terminal/HTTP proof.
