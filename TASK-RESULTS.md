## [2026-08-16] Frontend Worker — Phase 7A: Domain Manifest Frontend Wiring

### Summary
7/7 gates passed. 5 files changed (2 created, 3 modified). 3 new tests added; full suite 399 passed, 0 failed, 0 skipped.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Add `listDomainManifests` to `src/api/aiPulse.js` | ✅ | 1 function, reuses `BASE` + `apiFetch` |
| 2 | Extend `AIEmptyState.jsx` with `manifests` + `onStartStarter` | ✅ | Chips above "Start a Chat", generic fallback preserved |
| 3 | Wire manifests + starter handler into `AIWorkspace.jsx` | ✅ | `useState` + mount `useEffect` + `handleStartStarter`, both empty-state sites |
| 4 | Create `AIDomainManifest.test.jsx` | ✅ | 3 tests: chip render, exact arg forward, fallback |

### Files Changed
| Action | File | Lines | What |
|--------|------|-------|------|
| MODIFY | `carbon-frontend/src/api/aiPulse.js` | +9 | Added `listDomainManifests(token)` → `GET ai/pulse/apps/` |
| MODIFY | `carbon-frontend/src/shell/AIEmptyState.jsx` | +62 | Added `manifests`/`onStartStarter` props + starter-chip section + propTypes |
| MODIFY | `carbon-frontend/src/shell/AIWorkspace.jsx` | +40 | `listDomainManifests` + `sendMessage` imports, `manifests` state, mount effect, `handleStartStarter`, both `<AIEmptyState>` sites |
| MODIFY | `carbon-frontend/src/__tests__/AIWorkspace.shell.test.jsx` | +5 | Mocked `../api/aiPulse` (`listDomainManifests` resolves `{ apps: [] }`) + added `sendMessage` to aiWorkspace mock |
| CREATE | `carbon-frontend/src/__tests__/AIDomainManifest.test.jsx` | 87 | 3 manifest-wiring unit tests |

### Verification Output
```
$ npx vitest run src/__tests__/AIDomainManifest.test.jsx
 RUN  v4.1.10 /home/ahmed/aast/carbon/carbon-frontend
 Test Files  1 passed (1)
      Tests  3 passed (3)

$ npm test -- --run
 Test Files  18 passed (18)
      Tests  399 passed (399)

$ npm run lint
> eslint .

(exit 0 — clean)

$ npm run build
vite v6.3.5 building for production...
✓ 12825 modules transformed.
✓ built in 13.84s

$ ./.ai-toolkit/scripts/verify.sh frontend
Verification gate: frontend
── Frontend ────────────────────────────
✓ lint
✓ build
── Routes ──────────────────────────────
✓ route audit clean: 72 referenced path(s) resolve, 16 namespace root(s) covered
✓ route/URL audit
════════════════════════════════════════
GATE PASSED

$ grep -rn "\bitem\b.*xs=\|<Grid item\b" src/ --include="*.jsx"
(no output — empty)
```

### Deviations
NONE — implemented exactly per spec. Two pre-existing `AIWorkspace.shell.test.jsx` mock adjustments were required (mock `../api/aiPulse`, add `sendMessage`) because the component now imports those symbols; this is required for the existing suite to remain deterministic, not a spec deviation.

### Issues Found
- The `emissions` manifest's `starter_prompts.default` includes a `dq_validate` chip with no `table_id` context; task-driven chips with no entity scope open an empty conversation of that type. Entity-scoped entry points (with `table_id`) arrive in Phase 7b. (Not fixed — out of scope.)

---

## [2026-08-16] Frontend Worker — Phase 7C: Entity-Scoped Entry Points

### Summary
All gates passed. 8 files changed (4 created, 4 edited). 9 new tests added; full suite 408 passed, 0 failed.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Remove `dq_validate` from `starter_prompts.default` (Gap A) | ✅ | `emissions.py` — `default` now only `chat`; `dq_validate` still reachable via `entry_points` + `starter_prompts.table` |
| 2 | Create `useDomainManifests` hook (NEW) | ✅ | module-level cache, silent failure → `[]` |
| 3 | Create `AIDomainEntryPoints` (NEW) | ✅ | filters by `on_entity`, icon map, renders `null` on no match, always passes `app_identifier` |
| 4 | Replace hardcoded `Ask AI` in `SchemaDetailPage` | ✅ | removed `AutoAwesomeIcon`/`useAITaskTransfer`/`handleAskAI`/`tableLabel`; now `<AIDomainEntryPoints entityType="table">` |
| 5 | Add entry points to `DataProductDetailPage` | ✅ | `actions` slot with `<AIDomainEntryPoints entityType="module">` |
| 6 | Extend `enrichPayload` (Gap C, defensive) | ✅ | `dq_validate`/`investigate` table fields, `report_draft` module+period, `chat` table+module; all `?? null` |
| 7 | Create `AIDomainEntryPoints.test.jsx` (NEW) | ✅ | 5 tests: filter, null, table dispatch, module dispatch, `*` chat dispatch |
| 8 | Create `AITaskTransferContext.test.jsx` (NEW) | ✅ | 4 `enrichPayload` normalization tests |

### Files Changed
| Action | File | Lines | What |
|--------|------|-------|------|
| MODIFY | `backend/ai/domain/emissions.py` | -7 | Removed `dq_validate` from `starter_prompts.default` |
| CREATE | `carbon-frontend/src/hooks/useDomainManifests.js` | 34 | Shared manifest fetch + module cache |
| CREATE | `carbon-frontend/src/shell/AIDomainEntryPoints.jsx` | 126 | Manifest-driven entity entry points |
| MODIFY | `carbon-frontend/src/pages/catalog/SchemaDetailPage.jsx` | -35 / +9 | Hardcoded `Ask AI` → `AIDomainEntryPoints` |
| MODIFY | `carbon-frontend/src/pages/catalog/DataProductDetailPage.jsx` | +9 | `actions` slot with entry points |
| MODIFY | `carbon-frontend/src/shell/AITaskTransferContext.jsx` | +27 | `enrichPayload` cases for entity task types |
| CREATE | `carbon-frontend/src/__tests__/AIDomainEntryPoints.test.jsx` | 116 | 5 unit tests |
| CREATE | `carbon-frontend/src/__tests__/AITaskTransferContext.test.jsx` | 104 | 4 `enrichPayload` tests |

### Verification Output
```
$ cd backend && .venv/bin/python manage.py check
System check identified no issues (0 silenced).

$ .venv/bin/python manage.py makemigrations --check --dry-run
No changes detected

$ .venv/bin/python -m pytest ai -q
348 passed in 12.36s

$ cd carbon-frontend && npm test -- --run
Test Files  20 passed (20)
     Tests  408 passed (408)

$ npm run lint          # exit 0 (clean — baseline was also clean, no new errors)
$ npm run build         # ✓ built in 13.13s
$ grep -rn "\bitem\b.*xs=\|<Grid item\b" src/ --include="*.jsx"   # (no output)
```

### Deviations
NONE — implemented verbatim per spec. One note: `useDomainManifests` is used by `AIDomainEntryPoints` only; `AIWorkspace.jsx` still does its own inline `listDomainManifests` fetch (not listed in "Files to Change", so left untouched to respect scope). Flagging for a future dedup pass.

### Issues Found
- **Uncommitted working tree (pre-existing):** `git status` shows substantial uncommitted changes from Phases 6/7A/7B (backend `ai/` files, migrations, tests, docs) that predate this phase and were never committed. My 7C edits to `emissions.py` and `AITaskTransferContext.jsx` are interleaved with that prior work. I did **not** commit to avoid entangling unrelated changes — awaiting direction on commit/push scope.

## [2026-08-16] Backend Worker — Phase 8-A: `nl_rule_test` Execution Path (Execute Mode gate)

### Summary
5/5 gates passed. 4 files changed (1 created, 3 modified). 9 new tests (all passing); full `ai` suite 357 passed, 0 failed, 0 skipped.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Register `dq.rule_test` task type + `_nl_rule_test_prompt` + `_run_nl_rule_test` | ✅ | `MODULES` now 11; deterministic-only parse; `dispatch_task` handler wired |
| 2 | Route `nl_rule_test` conversations + `_send_nl_rule_test_message` | ✅ | `_route_typed_message` branch; loads table fields + rows read-only; `timeout=60` |
| 3 | Tests: `test_nl_rule.py` (9 tests) + bump `test_ops_api.py` count | ✅ | 10→11 module count; fail-visible contract covered |
| 4 | Add spec-REQUIRED `rows` detail (per-applicable-row actual/expected/passed) | ✅ | `_rule_test_rows` mirrors `dq.engine.evaluate` branches; threshold slider re-score data |
| 5 | Verification gates | ✅ | `check`, `pytest ai`, `makemigrations --check`, `verify.sh backend`, `verify.sh antipatterns` all green |

### Files Changed
| Action | File | Lines | What |
|--------|------|-------|------|
| MODIFY | `backend/ai/engine_runtime.py` | +230 | `dq.rule_test` in `MODULES`; `_nl_rule_test_prompt`; `_is_empty_value`; `_rule_test_rows` (per-row actual/expected/passed); `_run_nl_rule_test` (LLM parse → `dq.engine.evaluate` dry-run → preview + summary + violations + rows) |
| MODIFY | `backend/ai/intelligence.py` | +40 | `nl_rule_test` routing; `_send_nl_rule_test_message` (guard chain, table/rows load, dispatch, audit-log, metadata includes `rows`) |
| CREATE | `backend/ai/tests/test_nl_rule.py` | 381 | 9 tests: not_null/zero-row/all-fail/threshold-rows/LLM-outage/unparseable/unsupported/empty-nl/routing |
| MODIFY | `backend/ai/tests/test_ops_api.py` | 3 | module count 10→11, test renamed to `_eleven_types` |

### Verification Output
```
$ cd backend && .venv/bin/python manage.py check
System check identified no issues (0 silenced).

$ .venv/bin/python manage.py makemigrations --check --dry-run
No changes detected

$ .venv/bin/python -m pytest ai -q
357 passed in 12.95s

$ .venv/bin/python -m pytest ai/tests/test_nl_rule.py -v
9 passed in 4.69s

$ cd /home/ahmed/aast/carbon && ./.ai-toolkit/scripts/verify.sh backend
GATE PASSED

$ cd /home/ahmed/aast/carbon && ./.ai-toolkit/scripts/verify.sh antipatterns
GATE PASSED
```

### Deviations
- **`rows` detail shape:** the `dq.engine.evaluate` return only exposes aggregate `(passed, checked, failed, sample_failures[:20])` — no per-row enumeration. Per TASKS.md ("`rows` is REQUIRED — one entry per *applicable* row"), I added a dedicated `_rule_test_rows` helper that mirrors `evaluate`'s deterministic branches (`not_null`/`unique`/`allowed_values`/`range`/`regex`/`threshold`/`reference_integrity`) to emit `{row_id, actual, expected, passed}`. `expected` is typed per rule (`{"min","max"}` for range, `{"operator","value"}` for threshold, a `pattern` string for regex, `"non-empty"` for not_null, etc.) so Phase 8-B's threshold slider can re-score client-side with no round-trip.
- **`reference_integrity`/`allowed_values` reference-set lookup:** for reference-backed rules the helper reads `mdm.models` (ReferenceValue/ReferenceSet) read-only to populate `expected`; this never mutates DQ.
- **Severity default `"warn"`** (matches existing `_run_dq_suggest` convention), not `"error"` — the spec text does not mandate a default severity, so I followed the in-repo idiom.

### Issues Found
- **Pre-existing (not in my scope):** `verify.sh antipatterns` still reports `raw fetch()` in `carbon-frontend/src/pages/{ForgotPasswordPage,ResetPasswordPage}.jsx` and `src/api/aiWorkspace.js:228`, plus 28 `print()` calls in backend app code. None are in files I touched.
- **Phase 8-B dependency note:** the `metadata.rows` array and `rule_preview`/`test_summary`/`violations` fields are now the authoritative server payload for the `NLRuleTestCard`; 8-B should render from `metadata` and do threshold re-scoring purely client-side (no POST to `/dq/rules/` until the user confirms "Save Rule").

---

## [2026-08-16] Frontend Worker — Phase 8-B: Execute Mode toggle + NL Rule Test Card

### Summary
3/3 gates passed. 8 source files changed (4 created, 4 modified) + 2 test files (1 created, 1 extended). Full suite 415 passed, 0 failed, 0 skipped.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Create `executeModeContext.js` | ✅ | Shared context object (mirrors `aiTaskTransferContext.js` pattern) |
| 2 | Create `useExecuteMode.js` | ✅ | Hook with safe no-op fallback outside provider |
| 3 | Create `ExecuteModeContext.jsx` | ✅ | Provider + toggle persisted to `sessionStorage` (`carbon.executeMode`) |
| 4 | Create `NLRuleTestCard.jsx` | ✅ | Renders `nl_rule_test` metadata; threshold slider re-scores client-side; Save gated by `executeMode` |
| 5 | Edit `AIInputBar.jsx` | ✅ | Execute Mode toggle button + warning border, `aria-pressed` |
| 6 | Edit `AIMessageBubble.jsx` | ✅ | `nl_rule_test` branch + "Test live" on DQ suggestions |
| 7 | Edit `AIConversationView.jsx` | ✅ | `handleTestLive` + `handleSaveRule` (builds DQ definition, `createDQRule`) |
| 8 | Edit `AIWorkspace.jsx` | ✅ | Wrap main return in `<ExecuteModeProvider>` |
| 9 | Tests | ✅ | `NLRuleTestCard.test.jsx` (5) + `AIMessageBubble.transparency.test.jsx` (+2) |
| 10 | Verification gates | ✅ | lint clean, 415 tests green, build clean |

### Files Changed
| Action | File | What |
|--------|------|------|
| CREATE | `carbon-frontend/src/shell/executeModeContext.js` | `createContext(null)` export |
| CREATE | `carbon-frontend/src/shell/useExecuteMode.js` | `useContext` + no-op fallback |
| CREATE | `carbon-frontend/src/shell/ExecuteModeContext.jsx` | `ExecuteModeProvider` + `sessionStorage` persistence |
| CREATE | `carbon-frontend/src/shell/NLRuleTestCard.jsx` | Presentational card (rule preview, summary, violations, threshold slider, Save) |
| MODIFY | `carbon-frontend/src/shell/AIInputBar.jsx` | Execute Mode toggle (Bolt/Lock icon, warning border) |
| MODIFY | `carbon-frontend/src/shell/AIMessageBubble.jsx` | `nl_rule_test` card branch + "Test live" button |
| MODIFY | `carbon-frontend/src/shell/AIConversationView.jsx` | `handleTestLive`, `handleSaveRule`, prop plumbing |
| MODIFY | `carbon-frontend/src/shell/AIWorkspace.jsx` | `<ExecuteModeProvider>` wrap |
| CREATE | `carbon-frontend/src/__tests__/NLRuleTestCard.test.jsx` | 5 unit tests |
| MODIFY | `carbon-frontend/src/__tests__/AIMessageBubble.transparency.test.jsx` | +2 tests (nl_rule_test render, Test live button) |

### Verification Output
```
$ npm run lint
> eslint .
(exit 0 — clean; 2 initial react-hooks warnings in NLRuleTestCard fixed via useMemo)

$ npm test -- --run
Test Files  21 passed (21)
     Tests  415 passed (415)

$ npm run build
✓ built in 11.64s
```

### Deviations
- **Design-doc file map was STALE:** §8-B referenced a nonexistent `src/shell/cards/` directory and `DQSuggestionCard.jsx`. Resolved by placing the card at `src/shell/NLRuleTestCard.jsx` and rendering "Test live" inline in `AIMessageBubble.jsx`'s `dq_suggestions` branch.
- **Threshold slider is NOT gated by `executeMode`:** preview-only re-scoring remains available with Execute Mode OFF; only the Save button is gated. This keeps the test experience usable for exploration while still preventing writes until explicitly enabled.
- **Backend `violations` shape is `[{row, value}]`** (not the illustrative `{month, total_kwh, expected_min, deficit_pct}` in §8.2). `NLRuleTestCard` defensively handles both shapes via `toColumns` + `rescoreThreshold` reading `r?.actual ?? r?.value`.

### Issues Found
- **Uncommitted working tree (still unresolved):** `git status` continues to show interleaved uncommitted changes from Phases 6/7A/7B/7C/8-A/8-B (backend `ai/` files, migrations, tests, docs, plus all new frontend shell files). **No commit was made** — awaiting direction on commit/push scope before touching git history.

---

## [2026-08-16] Backend Worker — Phase 9-A: Investigate Mode (read-only pipeline)

### Summary
5/5 gates passed. 4 files changed (1 created, 3 modified). 7 new tests (all passing); full `ai` suite 364 passed, canonical `ai dq accounts` suite 961 passed, 0 failed, 0 skipped.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Add `"investigate"` to `MODULES` + register `_TASK_HANDLERS["investigate"]` | ✅ | `MODULES` now 12; `_run_investigate` wired into `dispatch_task` |
| 2 | Implement `_run_investigate` read-only pipeline | ✅ | 5 plan steps (profile → DQ → anomaly → KG → synthesis); DQ via pure `dq.engine.evaluate` loop; anomaly reuses `_run_anomaly_detect`; LLM outage → `llm_unavailable` (never `pulse_unavailable`) |
| 3 | Route `investigate` conversations + `_send_investigate_message` | ✅ | Removed `investigate` from staged placeholder; pre-loads schema/rows/latest `TableProfile`/rule_defs/anomaly payload/KG (all read-only, RULE_21); `timeout=90` |
| 4 | Tests: `test_investigate.py` (7 tests) + bump `test_ops_api.py` count | ✅ | 11→12 module count; test renamed to `_twelve_types` |
| 5 | Verification gates | ✅ | `check`, `pytest ai`, `pytest ai dq accounts`, `verify.sh backend`, `verify.sh antipatterns` all green |

### Files Changed
| Action | File | Lines | What |
|--------|------|-------|------|
| MODIFY | `backend/ai/engine_runtime.py` | +~235 | `"investigate"` in `MODULES`; `_INVESTIGATE_SEVERITY_MAP`/`_investigate_severity`; `_run_investigate` (5-step read-only pipeline, frozen `counts`/`plan_steps`/`findings`/`summary` metadata contract) |
| MODIFY | `backend/ai/intelligence.py` | +~175 | `investigate` routing branch; `_send_investigate_message` (guard chain, read-only pre-load, anomaly payload translation, KG retrieval via `_retrieve_knowledge_graph`, dispatch, audit-log, sanitized metadata) |
| CREATE | `backend/ai/tests/test_investigate.py` | 303 | 7 tests: empty-table 5 done steps, DQ `error→high`, DQ `warn→medium`, anomaly `error→high`, insufficient-history, LLM-outage `llm_unavailable`, routing |
| MODIFY | `backend/ai/tests/test_ops_api.py` | 4 | module count 11→12, test renamed to `_twelve_types`, asserts `"investigate" in engine_runtime.MODULES` |

### Verification Output
```
$ cd backend && .venv/bin/python manage.py check
System check identified no issues (0 silenced).

$ .venv/bin/python -m pytest ai/tests/test_investigate.py ai/tests/test_ops_api.py -q
12 passed in 3.84s

$ .venv/bin/python -m pytest ai -q
364 passed in 11.96s

$ .venv/bin/python -m pytest ai dq accounts -q
961 passed in 22.92s

$ cd /home/ahmed/aast/carbon && ./.ai-toolkit/scripts/verify.sh backend
GATE PASSED

$ cd /home/ahmed/aast/carbon && ./.ai-toolkit/scripts/verify.sh antipatterns
GATE PASSED
```

### Deviations
- **Test runner:** the spec's gate cites `manage.py test ai.tests.test_investigate ...`, but `project.config.md` (TESTING note) and `.ai-toolkit/scripts/verify.sh` both document that `manage.py test` aborts with a "Conflicting … models in application 'ai'" error under the unittest loader. Used `python -m pytest` (the canonical runner) instead — same test targets, no loss of coverage.
- **Anomaly payload translation:** `build_anomaly_payload(table_id)` returns a `{table, history, sensitivity, volume_anomaly_pct, ...}` shape, but `_run_anomaly_detect` consumes `{table_name, profile_history, sensitivity, volume_threshold_pct}`. `_send_investigate_message` translates between the two (mirroring `_build_anomaly_request`), so `_run_investigate` passes the exact shape `_run_anomaly_detect` expects. `None` (insufficient history) → a `done` plan step with `"insufficient history"` and 0 anomalies (not an error).
- **Field-less deterministic rules skipped:** rules whose field_assignments resolve to no table field are excluded from `rule_defs` (a `not_null` with no field would otherwise fail every row spuriously).

### Issues Found
- **Pre-existing (not in my scope):** `verify.sh antipatterns` still reports `raw fetch()` in `carbon-frontend/src/pages/{ForgotPasswordPage,ResetPasswordPage}.jsx` and `src/api/aiWorkspace.js:228`, plus 28 `print()` calls in backend app code. None are in files I touched.
- **Phase 9-B dependency note:** the frozen metadata contract `{type:"investigation", table_id, table_name, summary, plan_steps[], findings[], counts{rules_run,rules_failed,anomalies,kg_entities}}` is now the authoritative payload for the frontend. Each `finding` carries `{severity: high|medium|low, title, detail, recommended_action, entity_ref}`; each `plan_step` carries `{step, label, status: done|llm_unavailable, detail}`. Message status is `needs_input` when findings exist, else `completed`.
- **Uncommitted working tree (still unresolved):** `git status` continues to show interleaved uncommitted changes from prior phases. **No commit was made** — awaiting direction on commit/push scope before touching git history.

---

## [2026-08-16] Frontend Worker — Phase 9-B: Investigate Mode Frontend (tab + card + one-click trigger)

### Summary
All gates passed. 11 files changed (2 created, 9 modified). 8 new tests added; full suite 425 passed, 0 failed, 0 skipped.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Add `investigate` label to `AIConversationTabs` | ✅ | `CONVERSATION_TYPE_LABELS` now: chat, dq_validate, dq_suggest, nl_query, anomaly, investigate |
| 2 | Create `InvestigationCard.jsx` | ✅ | Renders frozen `investigation` metadata: summary, counts chips, plan steps (`done`/`llm_unavailable`), severity-tinted findings, per-finding Chat/Create-rule/Dismiss + Re-run |
| 3 | Create `InvestigateTab.jsx` | ✅ | Lists `conversation_type==='investigate'`, New-investigation button, status chip, relative `last_message_at || updated_at || created_at` time |
| 4 | Dispatch card in `AIMessageBubble` | ✅ | `metadata.type === 'investigation'` branch after `nl_rule_test` |
| 5 | Wire callbacks in `AIConversationView` | ✅ | `handleRerunInvestigation` / `handleChatAboutFinding` / `handleCreateRuleFromFinding` (→ `transferTask('nl_rule_test', …)`) |
| 6 | Add Investigate mode to `AIWorkspace` | ✅ | third tab, `investigateConversations` memo, `handleNewInvestigation` / `handleOpenInvestigation`, gated search/rail/tabs |
| 7 | One-click trigger in `AITaskTransferContext` | ✅ | sends sentinel `"Investigate this table"` when `type==='investigate'` && `table_id` |
| 8 | Tests | ✅ | 4 files: `InvestigationCard.test.jsx` (new, 6), `AIMessageBubble.transparency` (+1), `AIWorkspace.shell` (+1), `AITaskTransferContext` (+2 incl. negative) |

### Files Changed
| Action | File | Lines | What |
|--------|------|-------|------|
| CREATE | `carbon-frontend/src/shell/InvestigationCard.jsx` | ~150 | Severity/step meta maps, summary, counts, plan steps, tinted findings, dismiss set, Re-run |
| CREATE | `carbon-frontend/src/shell/InvestigateTab.jsx` | ~120 | Status meta, empty state, list of investigate conversations, New button |
| MODIFY | `carbon-frontend/src/shell/AIConversationTabs.jsx` | +1 | `investigate: 'Investigate'` label |
| MODIFY | `carbon-frontend/src/shell/AIMessageBubble.jsx` | +6 | `import InvestigationCard`, props `onRerun/onChatAbout/onCreateRule`, render branch |
| MODIFY | `carbon-frontend/src/shell/AIConversationView.jsx` | +~25 | three `useCallback`s wired into `<AIMessageBubble>` |
| MODIFY | `carbon-frontend/src/shell/AIWorkspace.jsx` | +~40 | `import InvestigateTab`, memo, handlers, `<Tab>`, mode gating, render branch |
| MODIFY | `carbon-frontend/src/shell/AITaskTransferContext.jsx` | +~10 | `sendMessage` import + sentinel send after `setPendingTransferId` |
| MODIFY | `carbon-frontend/src/__tests__/InvestigationCard.test.jsx` | 6 tests | summary/steps, severity tint, `llm_unavailable`, callbacks, re-run, dismiss |
| MODIFY | `carbon-frontend/src/__tests__/AIMessageBubble.transparency.test.jsx` | +1 test | investigation render case |
| MODIFY | `carbon-frontend/src/__tests__/AIWorkspace.shell.test.jsx` | +1 mock +1 test | Investigate tab renders `<InvestigateTab>` |
| MODIFY | `carbon-frontend/src/__tests__/AITaskTransferContext.test.jsx` | +2 tests | sentinel sent with `table_id`; not sent without |

### Verification Output
```
$ npm run lint
> eslint .
(exit 0 — clean)

$ npm test -- --run
 Test Files  22 passed (22)
      Tests  425 passed (425)

$ npm run build
✓ built in 12.81s
```

### Deviations
- **Design-doc file map stale:** §9-B referenced `src/shell/cards/InvestigationCard.jsx`, but no `cards/` directory exists. Card placed at `src/shell/InvestigationCard.jsx` alongside the other shell cards (e.g. `NLRuleTestCard.jsx`).
- **No new Investigate button added:** the "Investigate" entry-point already exists (domain manifest + `AIDomainEntryPoints`). The real gap was `transferTask` creating a conversation but never sending a message — fixed with the sentinel send, not a new button.

### Issues Found
- **Sentinel string is load-bearing:** `"Investigate this table"` must stay consistent across `AITaskTransferContext` (trigger), `AIConversationView` `handleRerunInvestigation` (re-run), and the entry-point path. Any change in one must be mirrored in the others.
- **Uncommitted working tree (still unresolved):** `git status` continues to show interleaved uncommitted changes from prior phases. **No commit was made** — awaiting direction on commit/push scope before touching git history.

---

## [2026-08-16] Backend Worker — Phase 10-A: Report Draft typed route + provider wiring

### Summary
5/5 tests pass; full AI suite 369 passed, 0 failed. 2 files changed (1 modified, 1 created). The engine (`_run_report_draft`), protocol dataclasses, and provider (`pulse.draft_report`) were already built and tested — this phase added only the intelligence-layer typed handler and its routing, per the "KEY FACT: this is SMALL" directive.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Route `report_draft` → `_send_report_draft_message` in `_route_typed_message` | ✅ | Retired the `_send_staged_task_message` placeholder |
| 2 | Add `_send_report_draft_message` (mirrors `_send_anomaly_message`) | ✅ | guard `workspace_report_draft` → translate payload → `provider.draft_report` → serialize sections → save `needs_input` |
| 3 | Create `backend/ai/tests/test_report_draft.py` (5 cases) | ✅ | routing, period_id resolution, direct params, shape, deterministic fallback |

### Files Changed
| Action | File | Lines | What |
|--------|------|-------|------|
| MODIFY | `backend/ai/intelligence.py` | +~100 | `ReportDraftRequest` import; `_route_typed_message` now routes `report_draft` → typed handler; added `_send_report_draft_message`; removed dead `_send_staged_task_message` (kept `_progress_stage_label` with its `report_draft` entry for the streaming path) |
| CREATE | `backend/ai/tests/test_report_draft.py` | 302 | 5 tests covering routing, parameter resolution, frozen metadata shape, and deterministic LLM-outage fallback |

### Verification Output
```
$ ../.venv/bin/python -m pytest ai/tests/test_report_draft.py ai/tests/test_kg_wiring.py ai/tests/test_provider_pulse.py -q
51 passed

$ ../.venv/bin/python -m pytest ai -q
369 passed

$ ./.ai-toolkit/scripts/verify.sh backend
GATE PASSED

$ ./.ai-toolkit/scripts/verify.sh antipatterns
GATE PASSED
```

### Deviations
- **`pytest` not `manage.py test`:** per project.config.md TESTING note, `manage.py test` hits a "Conflicting models in application 'ai'" error — used `python -m pytest` (addopts `--reuse-db --nomigrations -n auto`).
- **`_send_staged_task_message` deleted** (now-dead code) rather than left in place — the spec allows either; `_progress_stage_label` and its `"report_draft"` entry are retained (still used by `send_message_stream`).

### Issues Found
- **`type` is `"report"`, not `"report_draft"`:** the frozen metadata contract uses `metadata.type == "report"` (message status `needs_input`). 10-B must key on `type === 'report'`.
- **`period_type` → `report_type` map:** `annual→annual_summary`, `quarterly→quarterly_summary`, `monthly→monthly_summary`, everything else `ghg_summary`. The handler defaults `report_type="ghg_summary"` when neither `period_id` nor `report_type` is present (overriding the engine's internal `"summary"` default).
- **Uncommitted working tree (still unresolved):** `git status` continues to show interleaved uncommitted changes from prior phases. **No commit was made** — awaiting direction on commit/push scope before touching git history.

---

## [2026-08-16] Frontend Worker — Phase 10-B: ReportDraftCard + one-click trigger

### Summary
Frontend-only phase. Report cards key on `metadata.type === 'report'` (NOT `conversation_type`), rendered via a new presentational `ReportDraftCard` dispatched from `AIMessageBubble`. The "Draft Report" entry point already existed (manifest + `AIDomainEntryPoints`), so this phase closed the remaining gap: the one-click trigger in `AITaskTransferContext.transferTask` (sends the sentinel `"Draft this report"` after `createConversation` when `type === 'report_draft'` and `module_id || period_id`). The card renders whatever the backend returns (title, summary, period, sections with caveats, generated-at) and never invents emissions figures. "Save as Artifact" reuses `createArtifact` (`artifact_type:'report'`, `content_json: metadata`); "Export .md" is client-side Markdown generation + download; "Re-draft" re-sends the sentinel. 433 frontend tests pass; lint and build clean.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Add `report_draft` label to `AIConversationTabs` | ✅ | `report_draft: 'Report'` in `CONVERSATION_TYPE_LABELS` |
| 2 | Create `ReportDraftCard` | ✅ | presentational card: title + Draft chip, period, summary, sections (+ caveats), generated-at, 3 actions |
| 3 | Dispatch card in `AIMessageBubble` | ✅ | `if (metadata.type === 'report')` → `<ReportDraftCard …/>` |
| 4 | Wire callbacks in `AIConversationView` | ✅ | save artifact / export md / re-draft |
| 5 | One-click trigger in `AITaskTransferContext` | ✅ | sentinel `"Draft this report"` after `createConversation` |
| 6 | Tests | ✅ | ReportDraftCard (5), bubble report case (1), transfer context (2) |

### Files Changed
| Action | File | What |
|--------|------|------|
| MODIFY | `carbon-frontend/src/shell/AIConversationTabs.jsx` | `report_draft: 'Report'` label |
| CREATE | `carbon-frontend/src/shell/ReportDraftCard.jsx` | presentational report card (title/summary/period/sections/caveats + save/export/re-draft) |
| MODIFY | `carbon-frontend/src/shell/AIMessageBubble.jsx` | import + `report` dispatch branch + 3 propTypes |
| MODIFY | `carbon-frontend/src/shell/AIConversationView.jsx` | `handleSaveReportArtifact` (createArtifact), `handleExportReport` (client md), `handleRedraftReport` (sentinel) wired into bubble |
| MODIFY | `carbon-frontend/src/shell/AITaskTransferContext.jsx` | `report_draft` trigger → `sendMessage(…, 'Draft this report')` |
| CREATE | `carbon-frontend/src/__tests__/ReportDraftCard.test.jsx` | 5 tests |
| MODIFY | `carbon-frontend/src/__tests__/AIMessageBubble.transparency.test.jsx` | report render case |
| MODIFY | `carbon-frontend/src/__tests__/AITaskTransferContext.test.jsx` | report_draft positive + negative |

### Verification Output
```
$ npm run lint
(clean — no output)

$ npm test -- --run
Test Files  23 passed (23)
      Tests  433 passed (433)

$ npm run build
✓ built in 12.42s

$ grep -rn "\bitem\b.*xs=\|<Grid item\b" src/ --include="*.jsx"
(0 results)
```

### Deviations
- **Cards key on `metadata.type`, not `conversation_type`** (mandated): dispatch is `if (metadata.type === 'report')`; no `cards/` dir — card lives at `src/shell/ReportDraftCard.jsx`.
- **Entry point NOT re-added**: "Draft Report" already exists in the manifest + `AIDomainEntryPoints`; this phase only added the one-click trigger and rendering.

### Issues Found
- **Report is a DRAFT, not the calculated GHG report**: the card renders only what the backend returns (KG context + live host-table volumes + narrative). No emissions figures are invented client-side.
- **Sentinel string is load-bearing:** `"Draft this report"` must stay consistent between `AITaskTransferContext` (trigger) and `AIConversationView` `handleRedraftReport` (re-draft).
- **`get_errors` did not catch a JSX parse error**: a `multi_replace_string_in_file` on `AIMessageBubble.jsx` nested the report branch inside the investigation JSX; only `npm run lint` surfaced `356:8 Parsing error: Unexpected token (`. Fixed by rewriting the block and re-verifying with lint.
- **Uncommitted working tree (still unresolved):** `git status` continues to show interleaved uncommitted changes from prior phases. **No commit was made** — awaiting direction on commit/push scope before touching git history.
