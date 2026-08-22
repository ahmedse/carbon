# TASK-RESULT — QA-AI-PULSE-SIMULATION

**Task ID:** `QA-AI-PULSE-SIMULATION`
**Plan:** `docs/TASK-QA-AI-PULSE-SIMULATION.md` (~340 scenarios, Categories A–O, 4-layer model)
**Role:** qa-validator — validation only; **no product-code changes were made** (evidence-only, per §6/§7 of the plan)
**Date:** 2026-08-20
**Environment:** Django 5.2.3 + DRF :8009 (`/carbon-api/`), React 19 + Vite :5179, PostgreSQL, Redis, TZ Africa/Cairo. Personas: ahmed (admin, id=1), admin (admin, id=13), alamien_viewer (16), alamien_dataowner (14), sv_dataowner (17).

---

## 1. Executive Summary

The AI Pulse platform (20 admin routes, workspace chat, engine ops, rich export, feedback, memory, KG, mentions, budget) was validated across all four layers. **Layer 1 is fully green (GATE PASSED). Layer 2 security matrix is green with two design-level findings. Layer 3 functional has 6 confirmed P1 defects — all reproducible with exact engine-ledger evidence — plus a cluster of P2s. Layer 4 UX passed 8 of 10 checks with 2 a11y/info findings.** One P1 (dev-server SyntaxError in `aiWorkspace.js`) was **fixed by the user during the run** and verified fixed; it remains uncommitted (W2-A work in working tree).

**Verdict: PASSED WITH FINDINGS** — 5 active P1s (two newly root-caused this run), 8 P2s, 5 P3s, 2 design notes.

| Layer | Result |
|-------|--------|
| Layer 1 — structural (verify.sh, build, pytest, migrations) | ✅ GATE PASSED — 549 passed, build OK |
| Layer 2 — security / RBAC matrix (SEC-01..20) | ✅ 20 executed, 2 design findings (SEC-07/08) |
| Layer 3 — functional (categories A–O) | ⚠️ 6 P1s confirmed, 8 P2s, 5 P3s |
| Layer 4 — UX audit (UX-W1..W10 + UX-11..15) | ⚠️ 13 pass, 2 findings (W6 breadcrumb, W9 focus) |
| **Final verdict** | **PASSED WITH FINDINGS** |

**Headline this run (new root causes, previously unexplained):**
- **P1 — `/admin/ai/learning-flywheel` full-page crash.** Root cause: MUI X DataGrid **8.5.0 breaking change** — `valueFormatter` is now invoked **positionally** `(value, row, colDef, apiRef)` (verified in installed `useGridParamsApi.js`), but `LearningFlywheelPanel.jsx:119–133` uses the old v7-style destructure `({ value }) => …`. Any **null** cell value throws `TypeError: Cannot destructure property 'value' of 'object null'` → ErrorBoundary → "Something went wrong". The backend endpoint is defensive (503, never 500); the crash is purely frontend.
- **P1/`USG-F1` root cause upgraded — Budget & Usage grid is functionally blind.** Same `valueFormatter` mismatch in `BudgetUsagePanel.jsx:86–98`: **all numeric cells (Cost/Tokens/Calls) render `'—'`** (live capture: 28 cells, 21 = `'—'`) even though the API returns real numbers. Not cosmetic — the detail grids show no data at all.
- **P1 — `/admin/ai/engine-settings` full-page crash** (USG-11, re-confirmed with exact error): `ChipList` (EngineSettingsPanel.jsx:77–89, called at :313) renders **agent objects** `{id,name,role,tool_set,is_active}` directly as `Chip label` → `Objects are not valid as a React child` + duplicate-key `[object Object]` warnings.
- **P2 — 429 throttle storm.** `AuthContext.refetchTables` fires 1 request **per module on every full page load** (no cache/dedupe) against DRF `UserRateThrottle` `user: 1000/hour` (shared across **all** endpoints) → after ~15–20 page loads every AI admin page 429s for ~30 minutes ("Expected available in 1778 seconds"). Observed live across the whole 20-route sweep.
- **P1 blocker (aiWorkspace.js:352) — FIXED by user** mid-run; `node --check` OK, dev server serves 200, workspace renders. **File still uncommitted** (W2-A work in tree).

---

## 2. Preconditions (executed in mandated order)

1. `./manage.sh status` — backend healthy :8009, frontend healthy :5179, Postgres + Redis up.
2. Layer 1 GATE: `verify.sh full` → **GATE PASSED**; `npm run build` → **OK** (23.86s, chunk-size warnings only); `pytest backend/ai` (excl. mandated `test_store_execute.py`) → **549 passed**; `migrate` → applied `ai.0017_conversationcheckpoint`; `makemigrations --check` → clean.
3. Personas seeded and verified via `/carbon-api/token/` (ahmed, admin, alamien_viewer, alamien_dataowner, sv_dataowner, sv_analyst, carbon_lead_user, auditor_user).

---

## 3. Layer 1 — Structural (GATE)

| Check | Result |
|-------|--------|
| `verify.sh full` — django check / backend tests / lint / build / route audit / secrets / MUI v5 Grid / naive datetime | ✅ **GATE PASSED** (route audit 72 paths/16 namespaces; no hardcoded secrets; no naive datetime; no MUI v5 Grid) |
| Warnings (non-blocking) | raw `fetch()` ×5 (binary downloads + password reset — acceptable); `print()` ×28 in backend app code |
| `npm run build` | ✅ OK 23.86s (1.5 MB index chunk — warning only) |
| `pytest backend/ai` (excl. `test_store_execute.py`) | ✅ **549 passed** (baseline 510 → all green) |
| Migrations | ✅ `ai.0017` applied; `makemigrations --check` → "No changes detected" |
| Pre-existing frontend test failures | ⏭️ 9 pre-existing failures untouched (out of scope per plan §6) |

---

## 4. Layer 2 — Security / RBAC (SEC-01..20)

All 20 scenarios executed with real HTTP codes. **18 ✅, 2 design-level findings.**

| ID | Action | Result |
|----|--------|--------|
| SEC-01..06 | Anonymous on conversations / detail / messages / inventory / learning-run / settings | ✅ 401 on all |
| SEC-07 | Viewer **creates** conversation | ⚠️ **201** (not 403 — workspace ViewSet is `IsAuthenticated`-only, `workspace_api.py:65`) |
| SEC-08 | Viewer **sends** on own conversation | ⚠️ **200** (not 403); sending on admin's conversation → **404** (visibility gate correct) |
| SEC-09..11 | Data owner list / GET / PATCH admin conv | ✅ 200 (own only) / 404 / 404 |
| SEC-12..14 | Data owner facts scoped / learning-run / settings | ✅ 200 scoped / 403 / 403 |
| SEC-15 | Admin full access (convs, inventory, settings, usage, facts, learning-run, profile) | ✅ all 200/201; admin sees only own 56 convs (user-scoped by design) |
| SEC-16 | Cross-org isolation (sv_dataowner → alamien) | ✅ 404; fact scoping ahmed=45 / alamien=4 / sv=3 |
| SEC-17 | XSS `<script>alert(1)</script>` | ✅ stored as raw text; ReactMarkdown without `rehypeRaw` escapes; `dangerouslySetInnerHTML` only for mermaid SVG |
| SEC-18..19 | IDOR (message detail route, suggestions cross-owner) | ✅ 405 / 404 |
| SEC-20 | Secret redaction (settings/inventory/usage/profile/models) | ✅ no raw secrets; `_redact_secrets` active (`observability_api.py:173`) |

**Design notes:** SEC-07/08 — workspace conversation/messaging is intentionally `IsAuthenticated`-only (no role gating); the cross-user visibility gate (404) prevents leakage. Not a leak — recommend documenting the role matrix. **No P1 security issue found.**

---

## 5. Layer 3 — Functional (Categories A–O)

> Full per-scenario evidence is in session notes; the table below is the consolidated outcome. "✅" = passed, "❌" = confirmed defect, "⚠️" = env-limited or design note.

| Category | Outcome | Key evidence |
|----------|---------|--------------|
| A — Workspace lifecycle (WS) | ✅ | create/list/rename/archive menus, More menu (Pin/Rename/Archive/Delete), empty state "No sessions yet" |
| B — Messaging/streaming/modes (MSG-01..05) | ✅ | SSE deltas, "Generating…", Stop→"Interrupted"+Continue, Edit, Retry all verified live |
| C — Formats (FMT-01..04) | ⚠️ | Markdown table ✅, Mermaid SVG ✅, KaTeX ✅; **FMT-02 ❌ bare-hash fly-to links open blank tab** (P2) |
| D — Typed result cards (TYP) | ⚠️ | cards render for report/summary paths; **QUERY-02 ❌ P1** (empty reply, see F-04) |
| E — Feedback loop (FB-01..07) | ✅ | color-thumb UX, persistence (`outcome=rejected` in DB), no text labels |
| F — Memory (MEM-01..04) | ⚠️ | APIs + episodes verified; **MEM-01/04 ❌ P2** "Remember…" accepted but no durable fact, cross-conversation recall fails (contract violation) |
| G — KB / KG | ⚠️ | KB list + detail ✅; **KB-03 ❌ P1** empty reply; KG force graph 24 nodes/31 edges, hover/click/legend/768px/dark ✅; **provenance inconsistency P2** (T3_retrieval=0 vs chunks=1) |
| H — Agents/tools (AGT-08) | ❌ | **P1**: agent mode + tool-requiring prompt → empty content, wrong tool (`search_knowledge` instead of domain tool), critic VETO (see F-04) |
| I — Budget/usage (USG-01..12) | ⚠️ | summary cards/APIs/by_model/by_day ✅; **USG-11 ❌ P1 engine-settings crash (F-01)**; **USG-F1 ❌ P2 budget grid `'—'` (F-03)**; USG-F2 ⚠️ by_day window 5/7 days |
| J — Provenance (TR-01..10) | ⚠️ | "Why this answer" tooltip ✅ (minor: missing Conversation/App lines); status chips ✅; no engine jargon ✅; budget within limits ✅; single-model env limits TR-06/07 |
| K — Rich copy/export (EXP-01..04) | ✅ | Markdown/HTML/DOCX/JSON menus + backend fmt=json/markdown/400/401 verified; Save-images unreachable on collapsed old groups (minor) |
| L — Mentions (MNT-01..14) | ⚠️ | `#`→kinds, per-kind search lists, context chips, entry-point dispatch (dq_validate/report_draft/chat) ✅; **MNT-03..06 ❌ P2 mention→entity resolution NOT implemented** (`TODO(mentions)` in AIConversationView.jsx:272-274); **MNT-07 ❌ P2 follow-up chips dead code** (`_finalize_response`/`_generate_follow_ups` 0 call sites); MNT-03 also hit the P1 empty-reply family |
| M — Platform ops (OPS-01..15) | ⚠️ | dq.validate/suggest, schema.analyze, fix.suggest, anomaly, report.draft, apps manifest, RBAC split, latency ✅; **OPS-03 ❌ P1 query.nl broken** (no physical tables; `relation 'emissions' does not exist`); **OPS-01 ⚠️ clarify-instead-of-execute**; OPS-07 hit P1 family |
| N — Security/RBAC | ✅ | see Layer 2 |

### Confirmed P1 — systemic empty replies (tool-requiring turns)

Five independent reproductions, all with the same engine-ledger fingerprint:

> `salience → retrieval → draft(text_len=0, tool_calls=1) → critic(VETO, ungrounded_claim) → execution(tools_executed=1: search_knowledge) → final(VETO → content='')`

| Repo | Conv / turn | Prompt |
|------|-------------|--------|
| AGT-08 | d31e511b | "Create a DQ rule that flags negative emission values…" |
| QUERY-02 | 3c3fea59 | "Run a query to show me the first 5 rows of the emissions table…" |
| KB-03 | 66154d8b | "According to the platform knowledge base, what are Scope 2 emissions…" |
| MNT-03 | (4th) | "@Electricity show me its rows" |
| OPS-07 | dispatch chat | "What can you do?" / "What tables are in the catalog?" |

Control group (KB-05): "What is the capital of Madagascar?" → real answer. So the defect is specific to tool-requiring turns: the model emits a bare tool call with **zero accompanying text**; the critic vetoes any `text_len=0` turn; the pipeline returns empty content while spending tokens (2.0–2.4K per turn).

---

## 6. Layer 4 — UX Audit (UX-W1..W10 + UX-11..15)

Executed headlessly with the project Playwright (Chromium) — the integrated browser extension was non-functional this session, so all evidence is from `node` scripts against :5179.

| ID | Check | Result | Evidence |
|----|-------|--------|----------|
| UX-W1 | No console errors (workspace + 20 routes) | ⚠️ | workspace: **0 errors**; sweep: tables-endpoint 429s (F-07, infra), 2 data-dependent crashes (F-01/F-02) |
| UX-W2 | Loading spinners | ✅ | CircularProgress/Skeleton present in all Pulse panels (34 hits/9 files) |
| UX-W3 | Empty states | ✅ | "No sessions yet" / "Nothing learnt yet." / offline Papers / AIEmptyState |
| UX-W4 | Friendly error, no crash | ✅ | ErrorBoundary with correlationId caught both P1 crashes ("Something went wrong"); backend 503s never 500 |
| UX-W5 | Dark mode toggle | ✅ | aria-label "Dark mode"→"Light mode"; body `rgb(255,255,255)`→`rgb(9,9,11)` |
| UX-W6 | Breadcrumb present + correct | ⚠️ | nav innerText = "Home Admin"; **current crumb = "Admin"** (`aria-current="page"`); "Pulse" only rendered as page heading, not in trail — all 20 `/admin/ai/*` routes (F-15) |
| UX-W7 | Distinct titles | ✅ | 20 distinct titles verified (Pulse Overview … AI Logs) |
| UX-W8 | Responsive 768px | ✅ | scrollW == innerW == 768, no horizontal overflow |
| UX-W9 | Keyboard focus visible | ❌ | `:focus-visible` matches on header IconButtons **but outline `none 0px`, border `none`, boxShadow `none`** — no visible indicator; no theme focus-visible overrides (F-16, WCAG 2.4.7) |
| UX-W10 | No broken links | ⚠️ | sidebar + breadcrumb links OK; **fly-to links broken** (FMT-02, F-11) |
| UX-11 | Console clean over usage session | ⚠️ | 0 page errors on workspace; 429 noise under load (F-07); 2 crash routes (F-01/F-02) |
| UX-12 | Zoom 150% | ✅ | no overflow (1440==1440) |
| UX-13 | 200-char title truncation | ✅ | `<span>` (caption) `text-overflow: ellipsis; white-space: nowrap; overflow: hidden;` scrollW 1382 > clientW 68 → truncated |
| UX-14 | Rapid tab switching (10 convs, 12 clicks) | ✅ | **0 new console errors, 0 MUI Tabs invalid-value errors** |
| UX-15 | Refresh mid-stream | ✅ | reload during generation → page fully functional, 0 page errors (actual SSE resume not verifiable in this env) |

---

## 7. Findings Register

| ID | Sev | Component | Symptom | Evidence | Owner |
|----|-----|-----------|---------|----------|-------|
| F-01 (USG-11) | **P1** | `EngineSettingsPanel.jsx:77-89,313` | `/admin/ai/engine-settings` full-page crash | `Objects are not valid as a React child (found: object with keys {id, name, role, tool_set, is_active})` at `MuiChip-label`; duplicate-key `[object Object]` ×6; correlation `mt0ktkb2-1` | Engine-settings panel author / backend settings contract |
| F-02 (NEW) | **P1** | `LearningFlywheelPanel.jsx:119-133` | `/admin/ai/learning-flywheel` full-page crash when data present | `TypeError: Cannot destructure property 'value' of 'object null'` at `valueFormatter` (129:98) → `getCellParamsForRow` → `GridCell2` → ErrorBoundary. Root cause: MUI X v8.5 calls `valueFormatter(value, row, colDef, apiRef)` positionally (`useGridParamsApi.js:58-59`); panel uses v7-style `({ value })` destructure → null cell crashes | Flywheel panel author |
| F-03 (USG-F1 upgraded) | **P1** | `BudgetUsagePanel.jsx:86-98` | Budget & Usage detail grids show `'—'` for **all** numeric cells | Live: 28 cells / 21 `'—'`; `gpt-4o` row cost/tokens/calls all `'—'` though API returns real numbers — same v8 valueFormatter mismatch (silent undefined→'—', not crash) | Budget panel author |
| F-04 (AGT-08 / QUERY-02 / KB-03 / MNT-03 / OPS-07) | **P1** | Agent pipeline tool-selection + critic | Systemic **empty replies** on every tool-requiring turn (×5) | Ledger: `draft(text_len=0) → critic VETO → execution(search_knowledge, wrong tool) → final('')`; 2.0–2.4K tokens spent per empty turn; control (non-tool question) works | Agent/reasoning author |
| F-05 (OPS-03) | **P1** | `ExecutionEngine` (`ai/engine/knowledge_graph/engine.py`) / `query.nl` | NL query execution impossible on seeded data | `relation 'emissions' does not exist` — data lives in `dataschema_datarow` JSONB, no physical tables/views, no logical→physical mapping | KG execution / data-layer author |
| F-06 | **P2** | `src/api/aiWorkspace.js:352` | **Was P1 dev-server SyntaxError** (all shell modules "Failed to reload", GET → 500) | `node --check` failed; **FIXED by user 2026-08-20**, verified OK; **still uncommitted** W2-A work | W2-A author (commit + test) |
| F-07 (NEW) | **P2** | `AuthContext.jsx:318-350` refetchTables + DRF `UserRateThrottle` (settings.py:298-305) | **429 throttle storm**: after ~15–20 page loads every AI admin page 429s ~30 min | "Request was throttled. Expected available in 1778 seconds" on tables endpoint across all 20 routes; `user: 1000/hour` shared across all endpoints; refetchTables = 1 req/module per full page load, no cache | Frontend (cache/dedupe) + backend (scoped throttle) |
| F-08 (MNT-03..06) | **P2** | Mention resolution | `#table/#rule/#field/#module` mentions never resolve to entity ids | `AIConversationView.jsx:272-274` `TODO(mentions)`; stored user message `workspace_context=None` | Mentions/W2 frontend author |
| F-09 (MNT-07) | **P2** | Follow-up chips | Follow-up suggestion chips never render | `_finalize_response` / `_generate_follow_ups` in `reasoning.py` **dead code (0 call sites)**; 0/96 msgs carry `follow_up_questions` | Agent reasoning author |
| F-10 (MEM-01/04) | **P2** | `learn_fact` tool + agent | "Remember that my favorite color is teal…" → "Noted!" but **no durable fact**, cross-conversation recall fails | facts API has no preference fact; contract "Never claim you have memorized…" violated | Agent/tools author |
| F-11 (FMT-02) | **P2** | `MarkdownMessage.jsx` `a` renderer | Fly-to links (`#rules`) open blank tab, no navigation | only `href` starting with `/` intercepted; bare-hash falls to external branch `target=_blank` | Frontend markdown author |
| F-12 | **P2** | Sessions list ordering | Session list stale — `last_message_at` never updated after creation | `last_message_at || created_at` fallback; `updated_at` only set at creation, never bumped on new messages | Backend workspace author |
| F-13 (KB-04) | **P2** | Provenance payload | `context_snapshot.T3_retrieval=0` vs ledger `retrieval chunks=1`; `guard_results:[]` vs `verdict=veto` | message provenance payload vs engine ledger | Provenance author |
| F-14 (OPS-01) | **P2** | dq.validate via UI | Clarify action asks a question instead of executing | ledger: `draft text_len=270, tool_calls=0, critic veto`; clarification options shown | Agent author |
| F-15 (UX-W6) | **P3** | `Breadcrumbs.jsx` ROUTE_CONFIG | All `/admin/ai/*` routes show "Home › Admin" (current="Admin"); page label missing from trail | `nav` innerText "Home Admin"; no `/admin/ai/*` config entries; "Pulse" rendered as page heading only | Frontend breadcrumbs |
| F-16 (UX-W9) | **P3** | Header IconButtons / theme | **No visible keyboard focus indicator** (WCAG 2.4.7) | `:focus-visible` matches but outline/border/boxShadow all none; zero theme `focusVisible` overrides | Frontend theme |
| F-17 (TR-01) | **P3** | Provenance tooltip | "Why this answer" tooltip lacks Conversation/App lines | `app_identifier: null` in payload; tooltip shows Model/Type/Turn/Context only | Backend scope snapshot |
| F-18 (USG-F2) | **P3** | Usage `by_day` | "Last 7 days" shows only activity days (5 of 7) | usage API `by_day` = 5 entries | Backend usage author |
| F-19 (SEC-07/08) | note | Workspace RBAC | Viewer can create conversations (201) and send (200); cross-user 404 | `workspace_api.py:65` `IsAuthenticated`-only | Backend RBAC |
| F-20 | note | Hygiene | 5 raw `fetch()` + 28 `print()` warnings | verify.sh | Various |

**QA residue:** the audit created ~23 test conversations in ahmed's workspace (long-title + Rapid ×20 + others; 47 sessions total at last count) and 1 feedback outcome + message edits in `Main`/test convs. No product code was modified. Clean-up is at master's discretion.

---

## 8. Do-Not-Touch Compliance (plan §6)

- ✅ No product-code changes — all evidence gathered via curl, API calls, and read-only Playwright scripts (temp `.l4-*.mjs` removed after use).
- ✅ 9 pre-existing frontend test failures + `test_store_execute.py` untouched.
- ✅ No docker, no DB migrations, no config changes, no data deletion.

---

## 9. Verdict

**PASSED WITH FINDINGS.**

The platform is structurally sound (L1 GATE PASSED, 549 tests, clean build, no security P1s) and the UX surface is strong (dark mode, responsive, truncation, rapid-tab stability, refresh-mid-stream all clean). However, the AI engine has a **systemic P1** (empty replies on tool-requiring turns, ×5 repro), two **crash-level P1s** in the admin console (`engine-settings`, `learning-flywheel`) and one **data-blind P1** (`budget-usage` grid) — all with root causes now pinned to exact lines and one shared upstream cause (MUI X DataGrid v8.5 `valueFormatter` signature migration). A **P2 throttle storm** degrades all admin pages under sustained use. Recommended priority: F-04 (engine), F-02/F-03 (valueFormatter migration — one fix heals two panels), F-01 (ChipList), then F-07 (throttle), then the P2 backlog.

---

## 10. ROUND 2 — Agentic Task Orchestration & Agent Surface (post-866e3a8 W3-A)

**Status: PARTIALLY EXECUTED — live API phases BLOCKED by P1C regressions (F-21, F-22).**

**NEW SCENARIO ADDED (2026-08-22):** `docs/TASK-QA-AGENTIC-WORKFLOW-SIMULATION.md` — comprehensive test of multi-agent workflow orchestration using "create platform documentation (Word+Excel)" as the validation scenario. Tests full lifecycle: discovery → plan → approve → execute → monitor → pause/resume → deliver artifacts. Identifies 7 implementation gaps (F-23 to F-29) blocking enterprise-grade agentic workflow execution.

### 10.1 Unit layer (executed — GREEN)

| Layer | Suite | Result |
|---|---|---|
| Backend | `ai/tests/test_plans.py` + `test_agent_action_stream.py` + `test_tool_execution_actions.py` | **55 passed** (8.5s) |
| Frontend | `AITaskPanel.test.jsx` + `AITaskTransferContext.test.jsx` (vitest) | **23 passed** (4.9s) |
| **Total** | New W3-A task/agent/tool surface | **78/78 PASSED** |

Covers: plan create/list/owner-scope/approve/decline/run SSE frames/consent/confirm/decline/stop/ledger/api-auth; agent action stream; tool execution (search_knowledge, get_entity_details, call_host_api, navigate_to, open_entity, learn_fact, forget_fact, ask_clarification, run_ops_workflow, draft_skill, invoke_skill, code_snippet); MCP registry empty/malformed-config graceful degradation. `pytest.ini --nomigrations` masks migration-graph issues (see F-21).

### 10.2 New P1 blockers — live testing BLOCKED (need master fix, then re-run)

| ID | Sev | Symptom | Root cause (evidence-pinned) | Fix target (for master) |
|---|---|---|---|---|
| **F-21** | P1 (P0 for sprint) | `NodeNotFoundError: Migration datahub.0003_remove_models dependencies reference nonexistent parent node ('integrations.turnkey','0002_alter_turnkeymodellink_dataset_version')` — **every `migrate`/`makemigrations` fails** | App label is `turnkey` (TurnkeyConfig `name='integrations.turnkey'` → default label `turnkey`). Loader `disk_migrations` keys = `('turnkey','0001_initial')`, `('turnkey','0002_…')` (verified). `backend/datahub/migrations/0003_remove_models.py:13` (untracked P1C) depends on `('integrations.turnkey', …)` → DummyNode. | Change dep to `('turnkey', '0002_alter_turnkeymodellink_dataset_version')` |
| **F-22** | P1 (P0 for sprint) | `runserver`/`check` refuse to start — **60 system-check errors (E304/E305 reverse accessor clashes)**; backend STOPPED (was PID 2145, now down) | P1C adoption left duplicate model names: `datahub.DatasetAccessPolicy/group/user`, `datahub.DatasetVersion.approved_by/created_by/data_table`, `datahub.DatasetVersionMember.data_table` clash with `catalog.Dataset*` copies (verified in `backend.log`). State-only `DeleteModel` in 0003 does NOT clear live model classes from `datahub/models.py` → checks run against both apps. | Remove adopted models from `datahub/models.py` (or resolve related_name collisions); then 0003 state-op is redundant |

**Blocker impact on Round 2:** T-01..T-15 (plans lifecycle live), AG-05..AG-10 (actions/stream SSE, MCP, consent, stop) are **BLOCKED** — require a bootable backend on :8009. AG-01..AG-04/AG-11/AG-12 (pure unit/UI) already covered by 10.1. MEM-01/04 memory re-check (AG-11) blocked until backend boots.

### 10.3 Next actions (after master fixes F-21/F-22)
1. `./manage.sh restart backend` → verify `/carbon-api/health/` 200 + token endpoint JSON.
2. Phase 1: T-01 (live decomposition, ≤2 plans for LLM budget), T-02..T-05 lifecycle.
3. Phase 2: run SSE + consent gate + ledger (T-06..T-12).
4. Phase 3: MCP config redaction + actions/stream SSE (AG-05..AG-10).
5. Phase 4: MEM-01/04 fact persistence + cross-conversation recall (AG-11).
6. Phase 5: AITaskPanel/AIAgentPanel UI headless (Playwright `.lN-*.mjs`).
