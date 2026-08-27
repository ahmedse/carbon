
# TASKS — Carbon Master Task List

**This is the SINGLE SOURCE OF TRUTH for all outstanding work.** One worker task =
one `## Phase N-X` entry = one Worker Role. No phase spans both backend and frontend.

**Canonical docs (no forks):**
| Doc | Role |
|-----|------|
| `TASKS.md` (this file) | **Active + planned work.** Workers read "Phase N" here. |
| `docs/DESIGN-PLATFORM.md` | Platform Expansion spec (§5–8 = P1–P4). Pointer only — never duplicate its models/APIs here. |
| `docs/DESIGN-ADAPTIVE-LEARNING-DQ-CORE.md` | Unratified proposal (Phase 24 pointer). |
| `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` | Target architecture for the AI shell (reference). |
| `ROADMAP.md` | **HISTORICAL ARCHIVE** — Sprint 1–12 log. Do not add new work here. |

**Status legend:** `DONE` = verified + shipped · `READY` = spec complete, dispatchable · `PLANNED` = sequenced, spec pending · `PROPOSAL` = unratified, do not dispatch.

**Dispatch a task:** `./.ai-toolkit/scripts/activate.sh <role>` → paste into worker chat (model per `project.config.md` WORKER_MODEL_POLICY).

**Phase-name uniqueness:** before adding a new `Phase N-X`, grep this file for the proposed ID (e.g. `grep -n "Phase W3-B" TASKS.md`) — phase IDs are never reused even after a phase is `DONE`.

---

## MASTER DIRECTIVE — Test Partitioning (NON-NEGOTIABLE)

Full-suite `pytest` + `pytest-xdist -n auto` spawns parallel Postgres test DBs and
**hangs the dev laptop**. xdist flags are REMOVED from `backend/pytest.ini` and MUST
NOT be re-added. Every worker MUST follow:

- **Backend:** one app at a time, never full suite:
  `python -m pytest <app> -q --maxfail=5 --disable-warnings -p no:cacheprovider`
  (e.g. `pytest ai -q`, `pytest catalog -q`, `pytest integrations -q`).
  Max 2 apps in one invocation, and only the changed app + direct dependents.
- **Frontend:** one spec file at a time, never whole suite:
  `npx vitest run src/__tests__/<file>.test.jsx`; build **once per phase**
  (`npm run build`), not per file.
- **E2E:** only when a journey changed, one spec at a time (`npx playwright test e2e/journeys/<file>`).
- **NEVER:** `pytest` with no args · `-n auto`/`--dist loadscope`/xdist · `npx vitest run` with no path.
- Stale-test-DB cleanup (only if `test_carbon*` DBs linger): see `.ai-toolkit/shared/testing.md` RULE 7.

**Frontend completion is PROVEN, not claimed:** a frontend phase is `DONE` only
when `npm run lint` + a targeted `vitest` + `npm run build` all pass. No build/test
evidence → not done.

---

## AI WORKSPACE TRACK

---

## Phase 7C — Entity-Scoped Entry Points
**Date:** 2026-08-16
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek-V3, Kimi K3, Claude Haiku (simple), Sonnet (complex)
**Status:** DONE
**Full spec (source of truth):** `docs/TASK-AI-WORKSPACE-PHASE-7C-ENTITY-ENTRY-POINTS.md` — read it FIRST; it has exact code blocks and payload shapes.

### Files to Read First
- `docs/TASK-AI-WORKSPACE-PHASE-7C-ENTITY-ENTRY-POINTS.md` (full spec)
- `backend/ai/domain/emissions.py` (manifest: `entry_points`, `starter_prompts`, `validate_task_payload`)
- `carbon-frontend/src/shell/AITaskTransferContext.jsx` + `src/shell/aiTaskTransferUtils.js` + `src/shell/useAITaskTransfer.js` (transfer contract)
- `carbon-frontend/src/api/aiPulse.js` (`listDomainManifests`)
- `carbon-frontend/src/pages/catalog/SchemaDetailPage.jsx` + `DataProductDetailPage.jsx`
- `carbon-frontend/src/__tests__/AIDomainManifest.test.jsx` (self-contained; DO NOT TOUCH)

### Files to Change
- `backend/ai/domain/emissions.py` (1-line: remove `dq_validate` from `starter_prompts.default`)
- `carbon-frontend/src/hooks/useDomainManifests.js` (NEW — fetch + module-level cache)
- `carbon-frontend/src/shell/AIDomainEntryPoints.jsx` (NEW — render entry_points, dispatch transferTask)
- `carbon-frontend/src/pages/catalog/SchemaDetailPage.jsx` (replace hardcoded `Ask AI`)
- `carbon-frontend/src/pages/catalog/DataProductDetailPage.jsx` (add `actions` entry points)
- `carbon-frontend/src/shell/AITaskTransferContext.jsx` (extend `enrichPayload`)
- `carbon-frontend/src/__tests__/AIDomainEntryPoints.test.jsx` (NEW)
- `carbon-frontend/src/__tests__/AITaskTransferContext.test.jsx` (add enrichPayload cases)

### Context
The domain-AI manifest already declares `entry_points` + entity-scoped `starter_prompts`, but no entity page renders them. Only affordance is a hardcoded `Ask AI` (chat) button in `SchemaDetailPage`; `DataProductDetailPage` has none. Three gaps: (A) `default` ships a `dq_validate` chip with no `table_id` → backend `validate_task_payload` fails; (B) `entry_points` never rendered; (C) `normalizeAppIdentifier` can't infer `emissions` from catalog pages → returns `null`. Fix = render manifest `entry_points` scoped to `table`/`module`, carry `table_id`/`module_id` in `task_payload`, and always pass `app_identifier` explicitly.

### Implementation
Follow §3 (contract) and §4 (file-by-file) of the spec verbatim. Essentials:
- `AIDomainEntryPoints` props `{ entityType, entityId, entity, context }`; filter `entry_points` where `on_entity === entityType || '*'`; icon map FactCheck/AutoFixHigh/ManageSearch/Description/Chat (fallback AutoAwesome); render `size="small" variant="outlined"` buttons; return `null` when no match.
- Dispatch: `transferTask(task_type, payload, metadata)` — table payload `{ table_id, table_name, row_count, module_id, module_name }`; module payload `{ module_id, module_name }`; metadata ALWAYS includes `app_identifier: manifest.app_identifier` (Gap C) + `title`, `source_page`, `workspaceContext`.
- `enrichPayload` (defensive): `dq_validate`/`investigate` → table fields; `report_draft` → module fields + `period_id`; `chat` → table + module fields; each `?? null`.

### DO NOT TOUCH
- `carbon-frontend/src/__tests__/AIDomainManifest.test.jsx` (self-contained fixture)
- `backend/ai/domain_protocol.py`, `backend/ai/domain/__init__.py`, `backend/ai/apps.py` (Phase 7B, done)
- Any backend file other than `emissions.py` (this phase is frontend-heavy; backend change is 1 line)

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check          # → "System check identified no issues (0 silenced)"
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q          # → 348 passed (no logic change)
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run   # → "No changes detected"

cd /home/ahmed/aast/carbon/carbon-frontend
npm test -- --run        # → includes AIDomainEntryPoints + transfer-context tests, all green
npm run lint             # → 0 new errors (baseline ~6 err / ~62 warn pre-existing)
npm run build            # → clean
```

---

## Phase 8-A — Backend: `nl_rule_test` execution path (Execute Mode gate)
**Date:** 2026-08-16
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek-V3 / Sonnet
**Status:** DONE
**Full spec (source of truth):** `docs/DESIGN_AI_WORKSPACE_V4.md` § "Phase 8 — Execute Mode + NL → DQ Rule", sub-section 8-A. Read it first.

### Files to Read First
- `docs/DESIGN_AI_WORKSPACE_V4.md` — §8 (Phase 8) + §8-A (this phase); §5.3 (Execute Mode) for context.
- `backend/ai/intelligence.py` — `_route_typed_message` (~L1449), `_send_staged_task_message` (~L1474, the placeholder to replace), `_send_dq_suggest_message` (~L1604, the template), `_progress_stage_label` (~L1500), `_save_assistant_message` (~L2052), `_guard_workspace_operation` (~L1979).
- `backend/ai/engine_runtime.py` — `_run_dq_suggest` (~L1224) + `_run_dq_validate` (~L1146) as the LLM-parse/eval templates, `_TASK_HANDLERS` registry (~L1290), `dispatch_task` (~L1300).
- `backend/dq/engine.py` — `evaluate(rule_def, rows, *, field)` — the read-only v1 rule evaluator.
- `backend/dq/services.py` — `run_single_rule` (how a `DataField` is resolved). DO NOT call it — it persists DQResult.

### Files to Change
- `backend/ai/engine_runtime.py` — add `_run_nl_rule_test(instance_id, payload, task_id)`; register `"dq.rule_test"` in `_TASK_HANDLERS`.
- `backend/ai/intelligence.py` — add `_send_nl_rule_test_message(...)`; route `nl_rule_test` to it (drop it from the `{"investigate", "nl_rule_test", "report_draft"}` staged set, leaving `investigate` + `report_draft` staged).
- `backend/ai/tests/test_nl_rule.py` — NEW.

### Context
Phase 7B already added `nl_rule_test` to `CONVERSATION_TYPES` (no model change needed) and routed it — together with `investigate` + `report_draft` — to `_send_staged_task_message`, a fail-visible placeholder that says "scheduled for a later phase". This phase makes `nl_rule_test` actually execute: parse the user's NL into a DQ rule definition, dry-run it read-only against the table's rows, and return a preview + pass/fail summary so the frontend (Phase 8-B) can render an `NLRuleTestCard` with a "Save Rule" (Execute Mode) gate. `investigate` + `report_draft` remain staged (Phase 9 / later).

### Implementation
1. **`_run_nl_rule_test`** in `engine_runtime.py` — mirror `_run_dq_suggest` (LLM parse) + `_run_dq_validate` (eval loop):
   - Input payload: `{table_id, table_name, schema, nl, rows, field_name}` (the intelligence layer pre-loads these; see #2).
   - Step 1 (LLM parse): one `_llm_text` call (`task="cognition"`, `temperature=0.3`, `response_format={"type":"json_object"}`) asking for a v1 rule definition from the NL. **CRITICAL: the JSON must use `type` + `params` keys (NOT `rule_type`) to match `dq.engine.evaluate`.** Emit `{type, params, severity, confidence, field}`.
   - Step 2 (dry-run): call `dq.engine.evaluate(rule_def, rows, field=<resolved field>)`. It is already a pure read-only function — it returns `(passed, checked, failed, sample_failures, score)` and writes NOTHING. Do NOT call `dq.services.run_dq`/`run_single_rule`. No `dry_run` flag is needed.
   - Step 3 (result): return `{"status":"completed", "task_id":task_id, "result":{"rule_preview":{...}, "test_summary":{"total_rows","applicable_rows","passed","failed"}, "violations":[...], "rows":[{"row_id", "actual", "expected", "passed"}], "recommendation":"..."}}`. **`rows` is REQUIRED** — one entry per *applicable* row carrying the numeric comparison (`actual` vs `expected`) so the Phase 8-B threshold slider can re-score client-side with no server round-trip (see design ADR §1185).
   - LLM unavailable or unparseable → `_llm_unavailable(...)` (status `pulse_unavailable`) — never fabricate a pass/fail.
   - Register `"dq.rule_test": _run_nl_rule_test` in `_TASK_HANDLERS`.

2. **`_send_nl_rule_test_message`** in `intelligence.py` — mirror `_send_dq_suggest_message`:
   - `payload = conversation.task_payload_json or {}`; `guard_chain, operation = self._guard_workspace_operation(scope, "workspace_nl_rule_test", payload)`.
   - Load the table (resolve `DataTable` from `payload["table_id"]`), its `DataField`s (`schema`), and `DataRow.objects.filter(data_table_id=...)` (`rows`). Resolve the target `field` the same way `services.run_single_rule` does (by field name/id in the rule def).
   - Dispatch via `dispatch_task("dq.rule_test", {...})` consistent with the other typed handlers; audit-log start/end; on `pulse_unavailable` return `_save_provider_unavailable_message`.
   - Persist with `_save_assistant_message(conversation, text, metadata={"type":"nl_rule_test", "rule_preview":..., "test_summary":..., "violations":...}, status=...)`; use `status="needs_input"` when done (so 8-B can prompt "Save Rule").
   - Route it in `_route_typed_message`: add `if conv_type == "nl_rule_test": return self._send_nl_rule_test_message(...)` and change the staged set to `{"investigate", "report_draft"}`.

3. **Tests** `test_nl_rule.py` (mirror `test_domain_emissions.py` / `test_context_assembler.py` style):
   - LLM parse produces a valid `type`/`params` rule definition.
   - 0-row table → `passed=True` with `test_summary.total_rows == 0`.
   - all-fail table → `test_summary.passed == 0` (0 pass rate).
   - LLM unavailable → `pulse_unavailable` (fail-visible, no fabricated result).

### DO NOT TOUCH
- `backend/ai/models/workspace.py` (CONVERSATION_TYPES already has `nl_rule_test` — Phase 7B, done)
- `backend/ai/domain/*`, `backend/ai/domain_protocol.py`, `backend/ai/apps.py` (manifest registry, done)
- `backend/dq/services.py` + `backend/dq/engine.py` logic (read-only eval already correct; only CONSUME `evaluate`)
- Any frontend file (that is Phase 8-B)

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check          # → "System check identified no issues (0 silenced)"
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q          # → 348 passed + new test_nl_rule.py cases
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run   # → "No changes detected"
```

---

## Phase 8-B — Frontend: Execute Mode toggle + NL Rule Test Card
**Date:** 2026-08-16
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek-V3 / Sonnet
**Status:** DONE
**Full spec (source of truth):** `docs/DESIGN_AI_WORKSPACE_V4.md` §8-B + §5.3 (toggle) + §8.2 (workflow/card). Read first.

> ⚠️ **The design doc's file map is stale.** There is **no `shell/cards/` directory** and **no `DQSuggestionCard.jsx`** — DQ suggestions render *inline* inside `AIMessageBubble.jsx` (`renderStructuredContent()` → `metadata.type === 'dq_suggestions'`). Structured cards are keyed by `metadata.type`, NOT `conversation_type`. Follow the actual file map below, not the doc's.

### Files to Read First
- `docs/DESIGN_AI_WORKSPACE_V4.md` §5.3 (Execute Mode), §8.2 (7-step workflow + card), §8-B.
- `carbon-frontend/src/shell/AIMessageBubble.jsx` — `renderStructuredContent()` (~L200): the `dq_suggestions` / `nl_query_result` / `anomalies` branches are the template for the new `nl_rule_test` branch.
- `carbon-frontend/src/shell/AIInputBar.jsx` — input bar; the Execute Mode toggle mounts here.
- `carbon-frontend/src/shell/AIConversationView.jsx` — `lastMetadata` typing (~L454) + `handleAcceptSuggestion` (~L372); where conversation-level wiring lives.
- `carbon-frontend/src/shell/AITaskTransferContext.jsx` — the existing React-context pattern to mirror for Execute Mode.
- `carbon-frontend/src/api/aiWorkspace.js` — `createConversation(token, { conversation_type, ... })` (~L16).
- `carbon-frontend/src/api/dq.js` — `createDQRule(token, data)` (~L90) already exists.

### Files to Change
- `carbon-frontend/src/shell/ExecuteModeContext.jsx` — NEW: provider + `useExecuteMode()` hook. State in `sessionStorage` (`'carbon.executeMode'`), default OFF, reset on new session.
- `carbon-frontend/src/shell/AIInputBar.jsx` — add the Execute Mode toggle (§5.3): amber border on the bar when ON; toast "Execute Mode enabled/disabled" on toggle.
- `carbon-frontend/src/shell/NLRuleTestCard.jsx` — NEW presentational card (§8.2 Step 6): rule preview, test-summary bar, violations grid, threshold slider (client-side re-score from `metadata.rows`), `Save Rule` button.
- `carbon-frontend/src/shell/AIMessageBubble.jsx` — add `metadata.type === 'nl_rule_test'` branch in `renderStructuredContent()` → `<NLRuleTestCard>`; add a **"Test live"** affordance in the `dq_suggestions` branch that calls a new `onTestLive(suggestion)` prop.
- `carbon-frontend/src/shell/AIConversationView.jsx` — wire `onTestLive` → `createConversation({ conversation_type:'nl_rule_test', task_payload:{ table_id } })` then send the suggestion text as the message `content`; wire `onSave` → `createDQRule`; pass `executeMode` + handlers down to bubbles.
- `carbon-frontend/src/__tests__/NLRuleTestCard.test.jsx` — NEW.
- `carbon-frontend/src/__tests__/AIMessageBubble.transparency.test.jsx` — add a `nl_rule_test` render case (or new file `NLRuleTest.bubble.test.jsx`).

### Context
Phase 8-A (backend, in parallel) makes `nl_rule_test` execute and persist an assistant message with `metadata.type === "nl_rule_test"` and `metadata: {rule_preview, test_summary, violations, rows, recommendation}`. The frontend still has no way to (a) gate mutations (Execute Mode) or (b) render that result or (c) save the rule. This phase adds all three. The `rows` array in the metadata (frozen in 8-A) powers the exact client-side threshold re-score — no server round-trip on slider drag.

### Implementation
1. **`ExecuteModeContext.jsx`** — mirror `AITaskTransferContext.jsx`. Provider wraps the AI workspace (`AIWorkspace.jsx` or `AIConversationView`); `useExecuteMode()` returns `{ executeMode, setExecuteMode }`; value is `'true'/'false'` in `sessionStorage` (NOT `localStorage`), default OFF.
2. **`AIInputBar.jsx`** — consume `useExecuteMode()`; render a toggle in the bar header row: OFF = grey + `LockIcon` + tooltip "Execute Mode off — AI can suggest actions but cannot apply them."; ON = amber (`warning.main`) + amber border on the whole bar + toast "Execute Mode enabled — AI may now propose data changes." (OFF toast: "Execute Mode disabled.").
3. **`NLRuleTestCard.jsx`** — presentational, props `{ metadata, executeMode, onSave, onRetest, onDiscard }`:
   - Render `metadata.rule_preview` (type/severity/fields), `metadata.test_summary` (pass-rate bar + `passed/applicable_rows`), `metadata.violations` (compact `CarbonDataGrid` or `Table`), `metadata.recommendation` (lightbulb callout).
   - **Threshold slider** (from a numeric param in `rule_preview`, e.g. `threshold_pct`): re-score locally by re-applying the slider value against `metadata.rows[].actual`/`expected`; update the pass-rate bar + violations instantly (debounce 200ms). No network call.
   - **Save Rule** button: disabled when `!executeMode` with tooltip "Enable Execute Mode to save"; when ON → `onSave()` → on success show an immutable "Saved ✓" chip.
   - **Re-test** → `onRetest()` (re-send the same NL for a fresh server result); **Discard** → `onDiscard()`.
4. **`AIMessageBubble.jsx`** — in `renderStructuredContent()` add:
   - `if (metadata.type === 'nl_rule_test')` → `<NLRuleTestCard metadata={metadata} executeMode={executeMode} onSave={...} onRetest={...} onDiscard={...} />`.
   - In the `dq_suggestions` branch, add a `Test live` button next to Accept/Reject → `onTestLive?.(s)`.
5. **`AIConversationView.jsx`** — provide `executeMode` from context; implement `handleTestLive(s)` → `createConversation(token, { conversation_type:'nl_rule_test', task_payload:{ table_id: <resolved> }, title: 'Rule test' })` then `sendMessage(token, conversationId, s.prompt)` (the NL text is the **message content**, NOT `task_payload.nl` — the backend reads `content` first, with a `task_payload.nl` fallback) and navigate to the new thread; implement `handleSaveRule(rulePreview)` → `createDQRule(token, {...})` → toast "Rule created".
6. **Tests** — `NLRuleTestCard.test.jsx`: (a) renders rule_preview + test_summary; (b) slider drag re-scores pass rate locally; (c) Execute Mode OFF → Save Rule disabled with tooltip; (d) Execute Mode ON → Save Rule calls `onSave`; (e) after save → "Saved ✓" chip. Plus a `nl_rule_test` render case in the bubble transparency test.

### DO NOT TOUCH
- Any backend file (8-A owns `nl_rule_test` execution + the metadata shape).
- `carbon-frontend/src/__tests__/AIDomainManifest.test.jsx` (self-contained, 7A).
- `carbon-frontend/src/shell/AIDomainEntryPoints.jsx` / `useDomainManifests.js` (7C, done).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm test -- --run        # → all green incl. NLRuleTestCard + bubble nl_rule_test case
npm run lint             # → 0 new errors
npm run build            # → clean
```
> The `metadata` fixture for `nl_rule_test` must mirror the 8-A contract exactly: `{type:"nl_rule_test", rule_preview, test_summary, violations, rows, recommendation}`.

---

## Phase 9-A — Investigate Mode backend (read-only pipeline + typed route)

**Status:** DONE
**Role:** backend-worker
**Source spec:** `docs/DESIGN_AI_WORKSPACE_V4.md` §9 + "### Phase 9 — Investigate Mode".

### Files to read first (ground truth — the design doc is STALE, trust code)
- `backend/ai/engine_runtime.py` — `MODULES` list (~11 entries), `_TASK_HANDLERS` (~L1631), `_run_anomaly_detect` (~L699), `_run_report_draft` (~L886), `_run_nl_rule_test` (8-A, `dq.rule_test`), `dispatch_task`.
- `backend/ai/intelligence.py` — `_route_typed_message` (~L1449, the staged `{"investigate","report_draft"}` line), `_send_staged_task_message` (~L1476), `_send_anomaly_message` (~L1916, guard + audit pattern), `_build_anomaly_request` (~L2175), `_send_nl_rule_test_message` (~L1701, typed-handler template), `_save_assistant_message` (~L2230), `_save_provider_unavailable_message`.
- `backend/dq/engine.py` — `evaluate(rule_def, rows, *, field)` read-only pure eval (NOT `run_dq`, which MUTATES).
- `backend/dq/services.py` — `profile_table` (~L66, MUTATES), `run_dq` (~L609, MUTATES), `build_anomaly_payload` (~L426, READ-ONLY, returns `(payload, err)`).
- `backend/ai/context_assembler.py` — `_retrieve_knowledge_graph(scope, retrieval_budget)` (~L248) → `(entries, tokens_used)`.
- `backend/ai/models/workspace.py` — `CONVERSATION_TYPES` (already has `investigate`).
- `backend/ai/tests/test_ops_api.py` — `test_modules_returns_eleven_types` (count hardcoded to 11).

### Context / deviations from the stale design doc (MUST follow these, not the doc)
1. **No model change.** `investigate` is ALREADY in `CONVERSATION_TYPES`, `supported_task_types`, `entry_points`, and `starter_prompts` (done in 7B/7C). Do NOT touch `workspace.py` or `emissions.py`.
2. **Do NOT call `run_dq` or `profile_table`.** Both MUTATE (persist `DQResult`/rollup/`GovernanceEvent`; delete-and-recreate `FieldProfile`). Investigate is a READ-ONLY pipeline (RULE_21: AI suggests, Carbon executes). Evaluate DQ by mirroring `run_dq`'s rule SELECTION loop but calling the pure `dq.engine.evaluate` on the rows already loaded — no persistence.
3. **Anomaly task_type is `carbon.anomaly.detect`** (not `anomaly.detect` as the doc implies). Reuse `_run_anomaly_detect` directly (it is already registered) — do NOT create a second anomaly module.
4. **LLM outage is NOT `pulse_unavailable`.** The deterministic steps (profile → DQ → anomaly → KG) already yield findings; only the narrative `summary` depends on the LLM. On outage, return the deterministic findings with a fallback summary string. This deviates from the doc's "LLM outage → pulse_unavailable" test — rationale: discarding real deterministic findings to satisfy a fail-visible rule is dishonest; fail-visibility is preserved by marking the synthesis step `llm_unavailable`.
5. New task type key is `"investigate"` (add to `MODULES` AND `_TASK_HANDLERS`). `dispatch_task` 404s unknown types, and `/ai/ops/modules/` lists `MODULES` — so the ops test count 11 → 12.

### Frozen contract (9-B depends on this exact metadata shape)
`_send_investigate_message` persists an assistant message with:
```json
{
  "type": "investigation",
  "table_id": 12,
  "table_name": "emissions_fuel",
  "summary": "Plain-language brief…",
  "plan_steps": [
    {"step": 1, "label": "Profile table", "status": "done", "detail": "64 rows · 5 fields"},
    {"step": 2, "label": "Evaluate DQ rules", "status": "done", "detail": "8 rules run · 3 failed"},
    {"step": 3, "label": "Detect anomalies", "status": "done", "detail": "2 anomalies (HIGH)"},
    {"step": 4, "label": "Retrieve knowledge graph", "status": "done", "detail": "4 entities"},
    {"step": 5, "label": "Synthesize findings", "status": "done|llm_unavailable", "detail": "…"}
  ],
  "findings": [
    {"severity": "high|medium|low", "title": "…", "detail": "…", "recommended_action": "…|null", "entity_ref": "…|null"}
  ],
  "counts": {"rules_run": 8, "rules_failed": 3, "anomalies": 2, "kg_entities": 4}
}
```
Severity mapping: DQ rule severity (`error→high`, `warn→medium`, `info→low`); anomaly severity (`error→high`, `warning→medium`, `info→low`). `status` of the assistant message = `needs_input` if findings else `completed`.

### Implementation — `engine_runtime.py`
1. Add `"investigate"` to the `MODULES` list.
2. Add `_run_investigate(instance_id, payload, task_id)` (async) that consumes this payload (pre-loaded by the intelligence layer): `{table_id, table_name, schema, rows, profile_summary, rule_defs, anomaly_payload, kg_entries, kg_tokens}` and produces `plan_steps` + `findings` + `summary`:
   - **Step 1 Profile** — emit plan step from `profile_summary` (read-only, e.g. `{row_count, field_count}`).
   - **Step 2 DQ** — for each `rule_def`, build `field = SimpleNamespace(name=rule_def["field_name"], data_type=...)` from `schema`, call `dq.engine.evaluate(rule_def, rows, field=field)` (READ-ONLY). For each rule with `failed > 0`, append a finding. Count rules evaluated.
   - **Step 3 Anomaly** — if `anomaly_payload` is present, `await self._run_anomaly_detect(instance_id, anomaly_payload, task_id)`; map `anomalies` → findings. If `anomaly_payload` is `None` (insufficient history), emit `done` with detail `"insufficient history"` and 0 anomalies (NOT an error).
   - **Step 4 KG** — plan step from `len(kg_entries)` (KG retrieval happens in the intelligence layer because it needs `scope`).
   - **Step 5 Synthesis** — best-effort `_llm_text` (temperature 0.3, `response_format="json_object"`) → `{summary}`; on `LLMUnavailable`/parse failure, use a deterministic fallback summary (e.g. `"N rules failed, M anomalies detected."`) and set that step's `status` to `llm_unavailable`. Never raise; never `pulse_unavailable`.
   - Return `{"status": "completed", "result": {"table_id", "table_name", "plan_steps", "findings", "summary", "counts"}}`.
3. Register `_TASK_HANDLERS["investigate"] = self._run_investigate` (or the module-level equivalent, matching how `_run_anomaly_detect`/`_run_nl_rule_test` are registered).

### Implementation — `intelligence.py`
1. In `_route_typed_message`, change the staged branch to only catch `report_draft`, and add before it:
   `if conv_type == "investigate": return self._send_investigate_message(conversation, content, conv_ctx, scope)`. `report_draft` stays staged.
2. Add `_send_investigate_message(conversation, content, conv_ctx, scope)` mirroring `_send_anomaly_message`:
   - `payload = conversation.task_payload_json or {}`; `guard_chain, operation = self._guard_workspace_operation(scope, "workspace_investigate", payload)`.
   - Resolve `table_id` from `payload`; if missing → audit-fail + save a `status="failed"` message `"Investigate requires a table_id."` (metadata `{"type":"investigation","findings":[]}`).
   - **Read-only pre-load** into `task_payload`: table + `schema` (fields, archived excluded) + `rows` (CBAC-filtered, same as `_send_nl_rule_test_message`), `profile_summary` (latest `TableProfile` only — do NOT re-profile), `rule_defs` (active non-`nl_check`/non-`anomaly_detect` rules via the same selection as `run_dq`, each `{id,name,type,severity,params,field_name,reference_set_id}`), `anomaly_payload` from `build_anomaly_payload(table_id)` (None on `insufficient_history` — graceful), `kg_entries`/`kg_tokens` from `context_assembler._retrieve_knowledge_graph(scope, 800)`.
   - `result = await dispatch_task("investigate", task_payload, timeout=90)`.
   - Audit-trail log the start/end with `latency_ms` and `result["status"]`; on `pulse_unavailable` → `_save_provider_unavailable_message`; else `metadata = guard_chain.sanitize_response(scope, result["result"])` and `_save_assistant_message(..., metadata=metadata, status="needs_input" if findings else "completed")`.
   - Wrap the pre-load in `try/except` so a malformed scope/payload never crashes the turn.

### Tests
- New `backend/ai/tests/test_investigate.py`:
  1. Empty table (no rows) → 0 findings, all 5 plan steps `done`, status `completed`.
  2. Table with a failing DQ rule → at least one finding with mapped severity; `counts.rules_failed >= 1`.
  3. Anomaly payload present → anomaly-derived finding with severity `high` (monkeypatch `build_anomaly_payload`/`_run_anomaly_detect` as needed).
  4. LLM outage (monkeypatch `_llm_text` to raise/return `LLMUnavailable`) → still returns deterministic findings; synthesis step `status == "llm_unavailable"`; NOT `pulse_unavailable`.
  5. Route: an `investigate` conversation with `task_payload_json.table_id` routes to `_send_investigate_message` (not the staged placeholder).
- Update `test_ops_api.py::test_modules_returns_eleven_types` → `..._twelve_types`, assert `body["count"] == 12` and `"investigate" in engine_runtime.MODULES`.

### DO NOT TOUCH
- `backend/ai/models/workspace.py`, `backend/ai/domain/emissions.py` (investigate already declared).
- `backend/dq/services.py` (`run_dq`, `profile_table`) — do not modify; do not call from the investigate path.
- `backend/ai/engine.py` / `ai/domain/{app}.py` protocol layer.
- Any `carbon-frontend/**` (9-B owns it).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
.venv/bin/python manage.py test ai.tests.test_investigate ai.tests.test_ops_api --verbosity=2
# then the full AI suite:
.venv/bin/python manage.py test ai --verbosity=2
```
All green. `git diff --stat` shows only the files above (plus test files). Commit with `feat(ai-workspace): Phase 9-A — Investigate Mode backend (read-only pipeline)`.

---

## Phase 9-B — Investigate Mode frontend (tab + card + one-click trigger)

**Status:** DONE
**Role:** frontend-worker
**Depends on:** Phase 9-A (frozen metadata contract above).

### Files to read first (ground truth — the design doc file map is STALE)
- `carbon-frontend/src/shell/AIWorkspace.jsx` — mode tabs (`const [mode, setMode] = useState('chat')`, `<Tabs>` L415-423), `handleStartStarter` (create+send precedent), conversation filtering.
- `carbon-frontend/src/shell/AIConversationView.jsx` — `renderStructuredContent()` dispatch, `handleTestLive` (8-B precedent), `conversation_type` resolution (~L604).
- `carbon-frontend/src/shell/AIMessageBubble.jsx` — `renderStructuredContent()` keyed by `metadata.type` (NOT conversation_type); existing branches `dq_suggestions`, `nl_query_result`, `anomalies`, `nl_rule_test`.
- `carbon-frontend/src/shell/AITaskTransferContext.jsx` — `transferTask` (~L100) creates the conversation but does NOT send a message.
- `carbon-frontend/src/shell/AIDomainEntryPoints.jsx` — already renders the `Investigate` entry point (manifest-driven) and builds `{table_id, table_name, row_count, module_id}`.
- `carbon-frontend/src/pages/catalog/SchemaDetailPage.jsx` — table detail page (DataTable); 7C already mounted `AIDomainEntryPoints` here.
- `carbon-frontend/src/shell/AIConversationTabs.jsx` — `CONVERSATION_TYPE_LABELS` map (add `investigate`).

### Context / deviations (MUST follow these)
1. **Structured cards key on `metadata.type`, NOT `conversation_type`.** The design doc's `src/shell/cards/InvestigationCard.jsx` path does NOT exist — there is no `cards/` dir. Put the card at `carbon-frontend/src/shell/InvestigationCard.jsx` and dispatch it in `AIMessageBubble.renderStructuredContent()` via `if (metadata.type === 'investigation')`.
2. **The "Investigate" button already exists** — `emissions.py` `entry_points` + `AIDomainEntryPoints` already render it on the table detail page, and `transferTask` already creates the investigate conversation with the correct `task_payload`. Do NOT re-add it.
3. **The one-click trigger is the real gap.** `transferTask` creates the conversation but sends no message, so the backend `_route_typed_message` never fires. 9-B must trigger the run after creation. Backend contract: the investigate handler reads `task_payload_json.table_id` and ignores `content`, so the trigger is a fixed non-empty sentinel `"Investigate this table"` (non-empty to pass any frontend trim guard).

### Implementation
1. **`AIConversationTabs.jsx`** — add `investigate: 'Investigate'` to `CONVERSATION_TYPE_LABELS`.
2. **`AIWorkspace.jsx`** — add a third mode tab: `const [mode, setMode] = useState('chat')`; `<Tab label="Investigate" value="investigate" />`. When `mode === 'investigate'`, render `<InvestigateTab ... />` (filter conversations `conversation_type === 'investigate'`, newest first, with running vs. completed state and a "New" button that opens a new investigate conversation).
3. **New `carbon-frontend/src/shell/InvestigateTab.jsx`** — list of investigate conversations; each row: title, status (pending/needs_input/completed), last message time; click → open thread; "New" button → create a bare investigate conversation (`conversation_type:'investigate'`, `task_payload:{type:'investigate'}`) and let the user pick a table (or disable "New" until a table is chosen — keep it simple: "New" opens chat-style and the user invokes "Investigate" from a table detail page).
4. **New `carbon-frontend/src/shell/InvestigationCard.jsx`** — renders `metadata` of type `investigation`:
   - `summary` paragraph.
   - `plan_steps` as a vertical stepper/list with `status` chips (`done` = success, `llm_unavailable` = warning "synthesis unavailable").
   - `findings` as severity-tinted cards: `high→error.main`, `medium→warning.main`, `low→success.main` (theme tokens, no raw hex); each with `title`, `detail`, `recommended_action`, `entity_ref`.
   - Actions per finding: **"Chat about this ↗"** (send a follow-up chat message referencing the finding), **"Create rule ↗"** (open the `nl_rule_test` flow for the finding's table — reuse the 8-B `transferTask('nl_rule_test', {table_id, nl})` path), **"Dismiss"** (client-side collapse), and a card-level **"Re-run"** (re-send the sentinel trigger).
5. **`AIMessageBubble.jsx`** — in `renderStructuredContent()` add `if (metadata.type === 'investigation') return <InvestigationCard metadata={metadata} … />` (wire the action callbacks through from `AIConversationView`, same pattern as `NLRuleTestCard` in 8-B).
6. **`AIConversationView.jsx`** — pass `executeMode`/callbacks into `AIMessageBubble` for the new card; implement `handleRerunInvestigation` (re-send sentinel to the active conversation) and `handleChatAboutFinding(title, detail)` (send a chat follow-up).
7. **One-click trigger** — in `AITaskTransferContext.transferTask`, after `createConversation` succeeds, if `type === 'investigate'` (and the payload carries a `table_id`), send the sentinel message `"Investigate this table"` via the AI client `sendMessage` so the backend runs immediately. (If the AI client is not imported there, import it alongside `createConversation`.) This is the minimal, non-architectural fix for the "entry point creates but never runs" gap that 8-B also hit with `nl_rule_test`.

### Tests
- `carbon-frontend/src/__tests__/InvestigationCard.test.jsx`: (a) renders summary + plan steps; (b) renders findings tinted by severity; (c) `llm_unavailable` step shows the warning chip; (d) "Chat about this" and "Create rule" call their handlers; (e) "Re-run" calls `onRerun`.
- Add an `investigation` metadata render case to the existing bubble transparency test.
- Add an `AIWorkspace` tab test: Investigate tab renders `<InvestigateTab>`.

### DO NOT TOUCH
- Any `backend/**` file (9-A owns the backend + metadata shape).
- `AIDomainEntryPoints.jsx` / `useDomainManifests.js` (7C, already correct).
- `AIDomainManifest.test.jsx` (self-contained, 7A).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm test -- --run        # → all green incl. InvestigationCard + bubble investigation case + tab
npm run lint             # → 0 new errors
npm run build            # → clean
```
> The `metadata` fixture for `investigation` must mirror the 9-A contract exactly: `{type:"investigation", table_id, table_name, summary, plan_steps, findings, counts}`. Commit with `feat(ai-workspace): Phase 9-B — Investigate tab + InvestigationCard + one-click trigger`.

---

## Phase 10-A — Report Draft backend (typed route + provider wiring)

**Status:** DONE
**Role:** backend-worker
**Source spec:** `docs/DESIGN_AI_WORKSPACE_V4.md` §7.5 (Report Draft Card). NOTE: the design doc has NO dedicated report-draft phase number — its "Phase 10" is *Proactive Suggestions Rail* (a different frontend feature). I am labeling report-draft completion as **Phase 10** here so the last staged conversation type gets finished; the doc's "Proactive Polish" becomes Phase 11 when we reach it.

### Files to read first (ground truth — the engine/provider/protocol are ALREADY built)
- `backend/ai/intelligence.py` — `_route_typed_message` (~L1449, the `report_draft → _send_staged_task_message` line), `_send_staged_task_message` (~L1478, the placeholder to retire), `_send_anomaly_message` (~L1916, typed-handler template), `_build_ai_message`, `_save_assistant_message` (~L2230), `_save_provider_unavailable_message`.
- `backend/ai/protocol.py` — `ReportDraftRequest` / `ReportDraftResponse` / `ReportSection` (~L360-386) — ALREADY defined.
- `backend/ai/providers/pulse.py` — `draft_report(request)` (~L334) — ALREADY implemented, dispatches `carbon.report.draft` with `timeout=180` and maps `sections` → `ReportSection`.
- `backend/ai/engine_runtime.py` — `_run_report_draft` (~L887) — ALREADY implemented and registered under `"carbon.report.draft"` in `_TASK_HANDLERS`; consumes `{report_type, period_start, period_end}`; returns `{title, summary, report_type, period_start, period_end, generated_at, kg_context, host_metrics, sections}`; `_deterministic_report_summary` (~L315) is the no-LLM fallback (engine ALWAYS returns `completed`).
- `backend/emissions/models.py` — `ReportingPeriod` (`name`, `start_date`, `end_date`, `period_type`).
- `backend/ai/domain/emissions.py` — `report_draft` already in `supported_task_types`, `entry_points` ("Draft Report", `on_entity: module`), `starter_prompts` ("Draft GHG report"), `validate_task_payload` (requires `module_id` OR `period_id`).
- `backend/ai/models/workspace.py` — `report_draft` already in `CONVERSATION_TYPES`.

### Context / what is ALREADY DONE (do NOT re-implement)
1. Engine `_run_report_draft`, protocol dataclasses, provider `draft_report()`, domain manifest, and `CONVERSATION_TYPES` entry all exist and are tested (`test_kg_wiring.py`, `test_provider_pulse.py`, `test_protocol.py`, `test_domain_emissions.py`).
2. The ONLY gap is the intelligence-layer typed handler: `_route_typed_message` still routes `report_draft` → `_send_staged_task_message` (placeholder).
3. **Payload mismatch to bridge:** the frontend entry point sends `{module_id, module_name, period_id}` (see `AITaskTransferContext.enrichPayload`), but `draft_report`/`_run_report_draft` consume `{report_type, period_start, period_end}`. `_send_report_draft_message` must translate.
4. **No LLM-outage special case.** `_run_report_draft` always returns `completed` (deterministic `_deterministic_report_summary` when `_llm_text` is empty). The only non-completed status is `provider_unavailable` from `dispatch_task`.

### Frozen contract (10-B depends on this exact metadata shape)
`_send_report_draft_message` persists an assistant message with:
```json
{
  "type": "report",
  "title": "GHG Summary Report",
  "summary": "…",
  "report_type": "ghg_summary",
  "period_start": "2026-01-01",
  "period_end": "2026-12-31",
  "generated_at": "2026-08-16T12:00:00+00:00",
  "sections": [
    {"title": "Summary", "content": "…markdown…", "sql": null, "data": {…}|null, "caveat": "…"|null},
    {"title": "Data Volume (Live)", "content": "…", "sql": null, "data": {…}|null, "caveat": null}
  ]
}
```
- `type` is **`"report"`** (NOT `report_draft`) so the frontend card key (`metadata.type`) never collides with the `conversation_type` value.
- Each `sections[]` element is the `ReportSection` dataclass serialized to a plain dict (`title`, `content` = narrative, `sql`, `data`, `caveat`).
- Message status = `needs_input` (the card renders Save-as-Artifact / Export / Re-draft actions).

### Implementation — `intelligence.py` only (no engine/provider/protocol changes)
1. In `_route_typed_message`, replace the staged branch with:
   `if conv_type == "report_draft": return self._send_report_draft_message(conversation, content, conv_ctx, scope)`.
   `_send_staged_task_message` then has no callers — leave the method in place (dead but harmless) OR delete it; either is acceptable, but if you delete it also remove the `labels` dict and its `_progress_stage_label` entry only if you are certain nothing else references it (grep first).
2. Add `_send_report_draft_message(conversation, content, conv_ctx, scope)` mirroring `_send_anomaly_message`:
   - `payload = conversation.task_payload_json or {}`; `guard_chain, operation = self._guard_workspace_operation(scope, "workspace_report_draft", payload)`.
   - **Translate payload → report params** (wrap in `try/except` so a malformed scope never crashes the turn):
     - If `payload.get("period_id")`: `ReportingPeriod.objects.get(id=...)` → `period_start = start_date.isoformat()`, `period_end = end_date.isoformat()`; `report_type` from `period.period_type` (`annual→annual_summary`, `quarterly→quarterly_summary`, `monthly→monthly_summary`, else `ghg_summary`).
     - Else: `report_type = payload.get("report_type") or "ghg_summary"`; `period_start = payload.get("period_start") or ""`; `period_end = payload.get("period_end") or ""`.
   - Build `ReportDraftRequest(report_type, period_start, period_end, scope)`; time it with `time.perf_counter()`; call `self.provider.draft_report(request)`.
   - Audit-trail log (`latency_ms`, `response.status`, `error_message=_error_message(response.error)`).
   - `provider_unavailable` → `_save_provider_unavailable_message`; `status != "completed"` → save failed message (`metadata={"type":"report","sections":[]}`).
   - Else serialize `sections = [{"title": s.title, "content": s.content or s.narrative or "", "sql": s.sql, "data": s.data, "caveat": s.caveat} for s in response.sections]`; `metadata = guard_chain.sanitize_response(scope, {"type":"report", "title": response.title, "summary": response.summary, "report_type": response.report_type, "period_start": response.period_start, "period_end": response.period_end, "generated_at": response.generated_at, "sections": sections})`; `_save_assistant_message(..., metadata=metadata, status="needs_input")`.
   - Message text: `f"Drafted {response.title or 'report'} ({response.period_start} → {response.period_end})."`.

### Tests — new `backend/ai/tests/test_report_draft.py`
1. **Routing** — a `report_draft` conversation routes to `_send_report_draft_message` (assert the assistant message metadata has `type == "report"`, NOT `staged_task`).
2. **period_id resolution** — payload `{period_id: <ReportingPeriod>}` → metadata `period_start`/`period_end` match the period's `start_date`/`end_date` and `report_type` maps from `period_type`.
3. **Direct params** — payload `{report_type, period_start, period_end}` (no period_id) → passed through unchanged.
4. **Shape** — metadata has `title`, `summary`, non-empty `sections[]` with `title`/`content` keys; message status `needs_input`.
5. **Deterministic fallback** — monkeypatch `_llm_text` (or provider `draft_report`) so no LLM text is produced → still `completed`, `summary` is the deterministic `_deterministic_report_summary` string (not empty).

### DO NOT TOUCH
- `backend/ai/engine_runtime.py`, `backend/ai/protocol.py`, `backend/ai/providers/pulse.py`, `backend/ai/domain/emissions.py`, `backend/ai/models/workspace.py` (all already correct).
- Any `carbon-frontend/**` (10-B owns it).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
../.venv/bin/python -m pytest ai/tests/test_report_draft.py ai/tests/test_kg_wiring.py ai/tests/test_provider_pulse.py -q
../.venv/bin/python -m pytest ai -q
```
All green. Commit with `feat(ai-workspace): Phase 10-A — Report Draft typed route + provider wiring`.

---

## Phase 10-B — Report Draft frontend (ReportDraftCard + one-click trigger)

**Status:** DONE
**Role:** frontend-worker
**Depends on:** Phase 10-A (frozen metadata contract above).

### Files to read first (ground truth — the design doc file map is STALE)
- `carbon-frontend/src/shell/AIMessageBubble.jsx` — `renderStructuredContent()` keyed by `metadata.type`; existing branches (`investigation` added in 9-B) show the dispatch pattern.
- `carbon-frontend/src/shell/AIConversationView.jsx` — `handleTestLive`/`handleCreateRuleFromFinding` (8-B/9-B precedent for action wiring), `conversation_type` resolution.
- `carbon-frontend/src/shell/AITaskTransferContext.jsx` — `enrichPayload` (`report_draft` branch already normalizes `{module_id, module_name, period_id}`), `transferTask` (~L100, the 9-B investigate auto-send trigger pattern).
- `carbon-frontend/src/shell/AIConversationTabs.jsx` — `CONVERSATION_TYPE_LABELS` (add `report_draft`).
- `carbon-frontend/src/api/aiWorkspace.js` — `createArtifact(token, {conversation_id, message_id, title, artifact_type, content_json})` (ALREADY exists), `sendMessage`.
- `carbon-frontend/src/shell/AIDomainEntryPoints.jsx` — the "Draft Report" entry point (manifest-driven) ALREADY renders on the module detail page.

### Context / deviations (MUST follow these)
1. **Structured cards key on `metadata.type`, NOT `conversation_type`.** No `cards/` dir exists — create `carbon-frontend/src/shell/ReportDraftCard.jsx` and dispatch via `if (metadata.type === 'report')`.
2. **The "Draft Report" entry point already exists** (manifest + `AIDomainEntryPoints`), and `enrichPayload` already normalizes `{module_id, module_name, period_id}`. Do NOT re-add the button.
3. **One-click trigger is the gap** (same as 9-B investigate): `transferTask` creates the report_draft conversation but sends no message. After `createConversation`, if `type === 'report_draft'` and the payload has `module_id` or `period_id`, send the sentinel `"Draft this report"` via `sendMessage`.
4. **The report the backend produces is a DRAFT** (KG context + live host table volumes + an LLM/fallback narrative) — it is NOT the fully-calculated GHG report with per-building Scope 2 totals shown in §7.5. 10-B renders what `_run_report_draft` actually returns. Do not invent emissions figures client-side.
5. **"Save as Artifact" uses the existing `createArtifact` API** (`artifact_type: "report"`, `content_json` = the `metadata` dict). **"Export .md"** is client-side: build Markdown from `title` + each `section.title`/`section.content` and trigger a download.

### Implementation
1. **`AIConversationTabs.jsx`** — add `report_draft: 'Report'` to `CONVERSATION_TYPE_LABELS`.
2. **New `carbon-frontend/src/shell/ReportDraftCard.jsx`** — renders `metadata` of type `report`:
   - Header: `title` + a "Draft" chip + `period_start → period_end` (when present).
   - `summary` paragraph.
   - `sections[]`: each section → subtitle (`section.title`) + Markdown-ish `section.content` (render as pre-wrap body text; no MD parser dependency) + `section.caveat` as an italic warning line.
   - `generated_at` as a caption ("Generated …").
   - Actions: **Save as Artifact** (`onSaveArtifact?.(metadata)`), **Export .md** (`onExport?.(metadata)`), **Re-draft** (`onRedraft?.()`).
   - All theme tokens (no raw hex); severity-free (reports carry caveats, not severity).
3. **`AIMessageBubble.jsx`** — in `renderStructuredContent()` add `if (metadata.type === 'report') return <ReportDraftCard metadata={metadata} onSaveArtifact={onSaveReportArtifact} onExport={onExportReport} onRedraft={onRedraftReport} />`; thread the three callbacks through props (PropTypes too).
4. **`AIConversationView.jsx`** — implement and pass:
   - `handleSaveReportArtifact(metadata)` → `createArtifact(token, { conversation_id, message_id, title: metadata.title || 'Report', artifact_type: 'report', content_json: metadata })` → toast "Saved to Artifacts".
   - `handleExportReport(metadata)` → build Markdown string and download as `{slug(title)}.md`.
   - `handleRedraftReport()` → `handleSend('Draft this report')` (same sentinel as the trigger).
5. **`AITaskTransferContext.jsx`** — add the report_draft auto-send trigger (mirror the investigate trigger, guard on `type === 'report_draft' && (normalizedPayload.module_id || normalizedPayload.period_id)`).

### Tests
- `carbon-frontend/src/__tests__/ReportDraftCard.test.jsx`: (a) renders title + summary + sections; (b) renders caveats; (c) Save as Artifact calls `onSaveArtifact`; (d) Export .md calls `onExport`; (e) Re-draft calls `onRedraft`.
- Add a `report` metadata render case to the bubble transparency test.
- `AITaskTransferContext.test.jsx`: add a report_draft auto-send positive case + a negative case (no module_id/period_id → no send).

### DO NOT TOUCH
- Any `backend/**` file (10-A owns the backend + metadata shape).
- `AIDomainEntryPoints.jsx` / `useDomainManifests.js` (7C, already correct).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm test -- --run        # → all green incl. ReportDraftCard + bubble report case
npm run lint             # → 0 new errors
npm run build            # → clean
```
> The `metadata` fixture for `report` must mirror the 10-A contract exactly: `{type:"report", title, summary, report_type, period_start, period_end, generated_at, sections:[{title, content, sql, data, caveat}]}`. Commit with `feat(ai-workspace): Phase 10-B — ReportDraftCard + one-click trigger`.

---

## Phase 11-A — Proactive suggestion accept/dismiss endpoint

**Status:** DONE (`bcee0d5`)
**Role:** backend-worker
**Source spec:** `docs/DESIGN_AI_WORKSPACE_V4.md` §Phase 10 item 1 (Proactive Suggestions Rail). This is the LAST backend gap — the `AISuggestionRail` is display-only because there is no endpoint to mark a `KgProactiveInsight` acknowledged/dismissed.

### Ground truth (ALREADY built — do NOT re-implement)
- `backend/ai/models/knowledge_graph.py` — `KgProactiveInsight` model already has `disposition = TextField(default="pending")` and `dismissed_reason = TextField(null=True, blank=True)`. The field is `disposition`, NOT `status`. Target values: `"acknowledged"` and `"dismissed"`.
- `backend/ai/intelligence.py` — `list_proactive_suggestions(user, conversation_id=None, limit=10)` (~L1059) already scopes via `scope_ai_queryset(KgProactiveInsight.objects.all(), user)` and filters `disposition="pending"` + unexpired. `_serialize_proactive_suggestion(insight)` (~L1088) already exists. `_get_accessible_conversation(user, conversation_id)` (~L1253) already exists.
- `backend/ai/workspace_api.py` — `WorkspaceConversationViewSet` already has a `suggestions` GET detail action (~L353) and a `resume` POST action (~L380). The accept/dismiss action is the ONLY missing piece.
- `backend/ai/tests/test_proactive_resume.py` — existing tests for `list_proactive_suggestions` + `resume_conversation`; add new tests here (do NOT create a new test file).

### Implementation
1. **`backend/ai/intelligence.py`** — add ONE method `acknowledge_proactive_suggestion(self, user, conversation_id, suggestion_id, disposition="acknowledged", reason=None)`:
   - Verify conversation access first: `if self._get_accessible_conversation(user, conversation_id) is None: raise ValueError(f"Conversation {conversation_id} not found.")` (mirror `list_proactive_suggestions`).
   - Validate `disposition in {"acknowledged", "dismissed"}` else `raise ValueError`.
   - `from ai.models import KgProactiveInsight` + `from accounts.ai_scoping import scope_ai_queryset`.
   - `qs = scope_ai_queryset(KgProactiveInsight.objects.all(), user)`; `insight = qs.get(id=suggestion_id)` (catch `KgProactiveInsight.DoesNotExist` → `raise ValueError(f"Suggestion {suggestion_id} not found.")`).
   - Set `insight.disposition = disposition`; if `reason` and `disposition == "dismissed"` set `insight.dismissed_reason = reason`; `insight.save(update_fields=["disposition"] + (["dismissed_reason"] if reason else []))`.
   - Return `self._serialize_proactive_suggestion(insight)`.
2. **`backend/ai/workspace_api.py`** — add TWO `@action` methods on `WorkspaceConversationViewSet` (after the existing `suggestions` action):
   - `@action(detail=True, methods=["post"], url_path="suggestions/(?P<suggestion_id>[^/.]+)/accept", url_name="suggestion-accept")` → `accept_suggestion(self, request, pk=None, suggestion_id=None)` calls `acknowledge_proactive_suggestion(user=request.user, conversation_id=pk, suggestion_id=suggestion_id, disposition="acknowledged")`.
   - `@action(detail=True, methods=["post"], url_path="suggestions/(?P<suggestion_id>[^/.]+)/dismiss", url_name="suggestion-dismiss")` → `dismiss_suggestion(...)` calls the same with `disposition="dismissed", reason=request.data.get("reason")`.
   - Both: catch `ValueError` → `Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)`; else `Response(result)`.
3. **`backend/ai/workspace_api.py`** — add ONE list-level action for the notification badge (no `pk` needed):
   - `@action(detail=False, methods=["get"], url_path="suggestions", url_name="workspace-suggestions")` → `workspace_suggestions(self, request)` reads `limit` from query params (default 10, clamp 1–50), returns `Response({"suggestions": self.intelligence.list_proactive_suggestions(user=request.user, limit=limit)})`.
   - This coexists with the detail `suggestions` action (different URL: `/conversations/suggestions/` vs `/conversations/{pk}/suggestions/`).

### DO NOT TOUCH
- `backend/ai/models/knowledge_graph.py` (field already exists — no migration).
- `backend/ai/intelligence.py` `list_proactive_suggestions` / `_serialize_proactive_suggestion` / `resume_conversation` (already correct).
- Any `carbon-frontend/**` (11-B owns it).

### Tests (append to `backend/ai/tests/test_proactive_resume.py`)
1. `test_acknowledge_proactive_suggestion_sets_disposition` — create a pending insight, call `acknowledge_proactive_suggestion(..., disposition="acknowledged")`, assert `disposition == "acknowledged"` and the returned dict still has `id`/`title`.
2. `test_dismiss_proactive_suggestion_sets_reason` — `disposition="dismissed", reason="not relevant"` → `dismissed_reason == "not relevant"`.
3. `test_acknowledge_unknown_suggestion_raises` — bogus id → `ValueError`.
4. `test_acknowledge_bad_disposition_raises` — `disposition="banana"` → `ValueError`.
5. `test_acknowledge_inaccessible_conversation_raises` — a conversation not accessible to the user → `ValueError`.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
../.venv/bin/python -m pytest ai/tests/test_proactive_resume.py -q
../.venv/bin/python -m pytest ai -q
../.venv/bin/python manage.py check
```
All green. Commit with `feat(ai-workspace): Phase 11-A — Proactive suggestion accept/dismiss endpoint`.

---

## Phase 11-B — Suggestion rail actions + notification badge + catch-up button

**Status:** DONE (`6048e4b`)
**Role:** frontend-worker
**Depends on:** Phase 11-A (accept/dismiss endpoints).

### Ground truth (ALREADY built — do NOT re-implement)
- `carbon-frontend/src/shell/AISuggestionRail.jsx` — display-only rail (fetches via `getSuggestions`, renders severity chip + title + narrative + recommended actions + expand). Add Accept/Dismiss buttons here.
- `carbon-frontend/src/api/aiWorkspace.js` — `getSuggestions(token, conversationId, limit)` already exists. `acceptSuggestion`/`rejectSuggestion` ALREADY EXIST but they hit the **DQ** endpoints (`dq/suggestions/{id}/accept/`) — do NOT reuse them for proactive insights; add NEW helpers.
- `carbon-frontend/src/shell/AIConversationView.jsx` — resume catch-up banner (~L805) already renders an `Alert` with `HistoryIcon`, `hours_since_last_view`, and a `summary_lines` bullet list. The ONLY missing piece is a **"Catch me up"** action button.
- `carbon-frontend/src/shell/StatusBar.jsx` — the AI Workspace toggle button lives HERE (~L203), NOT in `ActivityBar` (the design doc file map is stale). Props `copilotVisible` + `onToggleCopilot` are already threaded. Add the unread `Badge` around the toggle `IconButton`.
- `carbon-frontend/src/shell/useShellState.js` — `copilotVisible` state + `toggleCopilot`/`openCopilot` already exist.
- `carbon-frontend/src/auth/AuthContext.jsx` — exposes `token` + user info.

### Implementation
1. **`carbon-frontend/src/api/aiWorkspace.js`** — add three helpers:
   - `acceptProactiveSuggestion(token, conversationId, suggestionId)` → `POST ${BASE}conversations/${conversationId}/suggestions/${suggestionId}/accept/`.
   - `dismissProactiveSuggestion(token, conversationId, suggestionId, reason)` → `POST .../dismiss/` with optional `{reason}` body.
   - `listWorkspaceSuggestions(token, limit = 50)` → `GET ${BASE}conversations/suggestions/?limit=...` (list-level, added by 11-A, for the badge — the detail `suggestions` endpoint requires a `pk`; the badge has none).
2. **`carbon-frontend/src/shell/AISuggestionRail.jsx`** — add an **Accept** (check icon, `color="success"`) and **Dismiss** (close icon) action per item; on click call the new helpers then remove the item from local state optimistically (filter out by `id`). On error, `notifyFromError` (the component already imports from `../components/NotificationProvider`? — if not, accept an `onError` prop or import `useNotification`). Keep display-only fallback if the endpoint 404s.
3. **`carbon-frontend/src/shell/StatusBar.jsx`** — wrap the AI Workspace toggle `IconButton` with MUI `<Badge>` showing `badgeContent` = count of pending workspace suggestions; hide the badge when `copilotVisible` is true (the rail inside already shows them — "clears on open"). Fetch count via `listWorkspaceSuggestions` on mount + on a lightweight interval (e.g. 60s) + refresh when `copilotVisible` flips.
4. **`carbon-frontend/src/shell/AIConversationView.jsx`** — add a **"Catch me up"** `Button` (size small, `startIcon={<AutoAwesomeIcon/>}`) to the resume catch-up banner; on click, send a chat follow-up `handleSend("Summarize what changed since my last visit.")` (reuse the existing `handleSend` callback already in scope) and clear the banner (`setCatchUp(null)`).

### Tests (extend existing + new)
- `carbon-frontend/src/__tests__/aiWorkspacePhase5.test.jsx` — (a) rail renders Accept/Dismiss buttons; (b) Accept calls `acceptProactiveSuggestion` and removes the item; (c) Dismiss calls `dismissProactiveSuggestion` with reason. Mock the new API helpers.
- `carbon-frontend/src/__tests__/StatusBar.test.jsx` (or nearest existing StatusBar test) — badge shows count, hides when `copilotVisible`.
- `carbon-frontend/src/__tests__/aiWorkspacePhase5.test.jsx` — resume banner renders "Catch me up" and clicking it calls `handleSend`.

### DO NOT TOUCH
- Any `backend/**` file (11-A owns it).
- `AISuggestionRail`'s existing severity/render logic (only ADD actions).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm test -- --run        # → all green
npm run lint             # → 0 new errors
npm run build            # → clean
```
Commit with `feat(ai-workspace): Phase 11-B — Suggestion rail actions + badge + catch-up`.

---

## Phase 12 — Shared Threads frontend (read-only collaboration)

**Status:** DONE (`f1bae71`) — frontend-only; backend was already complete.
**Role:** frontend-worker
**Source spec:** `docs/DESIGN_AI_WORKSPACE_V4.md` §Phase 11 (Shared Threads). The BACKEND is already complete — this is a frontend-only phase.

### Ground truth (backend ALREADY done — do NOT touch backend)
- `backend/ai/models/workspace.py` — `AIConversation.visibility` (`private`/`shared`) already exists; `AIConversation.user` is a `ForeignKey(AUTH_USER_MODEL)`.
- `backend/ai/intelligence.py` — `update_conversation` already accepts `visibility`; `list_conversations` already returns shared conversations via `_shared_conversation_ids`; `delete_conversation` already requires `ai:manage_console` for shared; `send_message` already denies non-owners (`objects.get(id=..., user=user)`); `_serialize_conversation` already includes `visibility` + `user_id` (numeric owner PK).
- `carbon-frontend/src/api/aiWorkspace.js` — `updateConversation(token, id, fields)` already exists (supports `visibility`).
- **CRITICAL ENCOUNTERED FACT:** `useAuth().user` currently is `{ username, token, refresh, roles }` — it has **NO `id`**. `accounts/me/context/` returns `data.user.id` (numeric) but AuthContext currently drops it. You MUST add the enabler below or ownership detection cannot work.

### Implementation (frontend-only)
0. **ENABLER — `carbon-frontend/src/auth/AuthContext.jsx`** — expose the current user's numeric id on `useAuth().user.id`:
   - In `fetchPerspectiveContext` (after `const data = await apiFetch(...)`), persist `data.user?.id`: `localStorage.setItem("user_id", String(data.user.id))` and merge into state `setUser((prev) => (prev ? { ...prev, id: data.user.id } : prev))`.
   - In `login`, capture the perspective result: `const perspective = await fetchPerspectiveContext(access);` then build `const userObj = { id: perspective?.user?.id, username, token: access, refresh, roles };`.
   - In the mount `useEffect`, when restoring `storedUser`, merge the persisted id: `setUser({ ...storedUser, id: localStorage.getItem("user_id") || storedUser.id || undefined })` (only when `storedUser?.token` is truthy).
   - Do NOT otherwise change auth flow. The id may be numeric; compare with `String(a) === String(b)` everywhere.
1. **`carbon-frontend/src/shell/AIConversationTabs.jsx`** — group the tab bar into **"My threads"** (owned) and **"Shared with me"** (non-owned shared). `const { user } = useAuth()`; `const isOwned = (c) => c.visibility !== 'shared' || String(c.user_id) === String(user?.id);`
   - Order tabs owned-first then shared; insert a thin vertical `<Divider orientation="vertical" flexItem />` between the two groups.
   - Non-owned shared tabs render a small **"Shared"** `<Chip size="small" label="Shared" />` in the tab label.
   - Hide the per-tab close "X" `IconButton` for non-owned shared tabs (closing maps to `onClose`→`handleArchive` which the backend rejects for non-owners).
   - In the context `Menu`, disable/hide Pin/Rename/Archive/Delete for non-owned shared tabs (non-owners cannot mutate; backend enforces this — UI must match).
   - Keep existing behavior on owned tabs unchanged.
2. **`carbon-frontend/src/shell/AIConversationView.jsx`** — derive `const { user } = useAuth(); const isOwner = !conversation || conversation.visibility !== 'shared' || String(conversation.user_id) === String(user?.id);`
   - When `!isOwner`: hide the `<AIInputBar />` (render a read-only `<Alert severity="info">You have read-only access to this shared thread.</Alert>` in its place), and disable/suppress all mutation actions (suggestion Accept/Reject, anomaly View Details/Dismiss follow-ups, catch-up "Catch me up" send, artifact save, re-draft, rule-create, export is read-only so keep it).
   - Add a **"Share"/"Unshare"** toggle in the header action row (next to Export) shown ONLY when `isOwner`: button calls `updateConversation(token, conversation.id, { visibility: current === 'shared' ? 'private' : 'shared' })` then updates local `conversation` state. Import `updateConversation` from `../api/aiWorkspace` and a suitable icon (e.g. `GroupIcon`/`LockIcon`).
3. **No backend changes.**

### Tests (new `carbon-frontend/src/__tests__/AISharedThreads.test.jsx`)
- (a) owned vs shared tab grouping shows a "Shared" chip on non-owned shared tabs and hides the close button.
- (b) read-only view hides the input bar and shows the read-only banner for a non-owned shared thread.
- (c) Share toggle calls `updateConversation` with `{visibility:'shared'}` and the toggle is absent for non-owners.
- (d) AuthContext exposes `user.id` after `accounts/me/context/` returns `data.user.id` (mock `apiFetch`).

### DO NOT TOUCH
- Any `backend/**` file (already complete).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm test -- --run        # → all green
npm run lint             # → 0 new errors
npm run build            # → clean
```
Commit with `feat(ai-workspace): Phase 12 — Shared threads read-only collaboration`.

---

## Phase 13 — E2E Simulation: Carbon AI as generalist chat + DQ coworker/expert

**Status:** IN PROGRESS — journey authored (`journey-11-ai-coworker-dq.spec.ts`); Journey-10 29/29 PASS; 3 defects found & fixed (F1 protocol `current_view`, A1 spec `newChat` race, B5 `nl_rule_test` auto-send gap); re-validation handed to Phase 14.
**Role:** qa-validator (DeepSeek-V3)
**Kind:** Pure validation + E2E authoring. No product code is built or fixed here — only a new Playwright journey spec + live-browser evidence. If a defect is found, record it with severity + repro; the Debugger/Fixer applies the fix (with a regression test, RULE_11).

### Objective (user directive, verbatim intent)
Drive Carbon AI **in-browser as a real user** (Playwright clicks/typing, not raw API), in **two distinct personas**:
1. **Regular chat** — a generalist assistant (platform overview, GHG methodology, follow-up questions, feedback, edit/regenerate, export, rename).
2. **DQ processes coworker/expert** — the AI acting as a data-quality teammate on real seeded tables: **Validate DQ**, **Suggest Rules** (then accept one), **NL rule test** (then save with Execute Mode), **Investigate anomalies**, and **NL query**.

### Ground truth (verified — trust, do not re-derive)
- E2E lives in `carbon-frontend/e2e/`. Config `e2e/playwright.config.ts` (chromium, 1440×900, baseURL `http://127.0.0.1:5179`, apiURL `:8009`, serial). Fixtures `e2e/fixtures/users.ts` export `PERSONAS`, `login(page, persona)`, `getAuthHeaders`, `navigateTo`.
- Existing `journey-10-ai-workspace.spec.ts` is **API-heavy**. Phase 13 must be **UI-first** — reuse only `login`/`navigateTo`/`PERSONAS`; do NOT copy its API matrix.
- **Personas** (`PERSONAS`): `admin` (admin/admin123, global admin), `alamien_dataowner` (data123, can enter data + see DQ), `alamien_viewer` (viewer123, read-only, NO `dq:manage_rules`).
- **Table detail page** = `/catalog/tables/{tableId}` (`SchemaDetailPage`). **Module detail** = `/catalog/products/{moduleId}` (`DataProductDetailPage`). Both render `AIDomainEntryPoints` with these buttons:
  - table: **"Validate DQ"** (`dq_validate`), **"Suggest Rules"** (`dq_suggest`), **"Investigate"** (`investigate`), **"Ask about this"** (`chat`).
  - module: **"Draft Report"** (`report_draft`), **"Ask about this"** (`chat`).
- **AI Workspace** full page = `/admin/ai/workspace` (capability `ai:view_console`). Also opens as a copilot overlay via the StatusBar AI toggle.
- **Key selectors** (from source): message input `getByLabel('Message input')`; send `getByLabel('Send message')`; send-mode `getByLabel('Send mode')`; "New chat" `getByLabel('New chat')` (AIConversationTabs). Verify each selector against the live DOM before relying on it (see Step 0).
- **DQ accept flow** (`AIConversationView`): when a `dq_suggest` turn completes, a "needs-input" area renders per-suggestion **Accept**/**Reject** buttons. Accept calls `acceptSuggestion(token, suggestionId)` (`src/api/aiWorkspace.js`) → creates a DQ rule. Gated by `canManageRules` = global-admin OR `dq:manage_rules` capability; otherwise the UI shows "Requires DQ manage permission…" instead of buttons.
- **NL rule test** (`nl_rule_test`) renders `NLRuleTestCard` (pass-rate + violations + "Save" gated by Execute Mode).
- **Investigate** (`investigate`) renders the Investigate tab + `InvestigationCard` (read-only pipeline).
- **Seed data** (already loaded): modules "Medicine Carbon", "Finance Carbon", "Transport Carbon", "Hotels Carbon", "Hospital Carbon"; tables "Electricity", "Fuel", "Fleet", "Travel", "Chilled Water", "HVAC", etc. Real DQ rules exist (e.g. "Electricity consumption_kwh > 0"). **Discover the actual `tableId`/`moduleId` at runtime** — do not hardcode UUIDs; resolve them from `/catalog/products` + a table's detail link, or via the DQ/Catalog list API.
- API base `http://127.0.0.1:8009/carbon-api`; AI workspace endpoints under `/ai/workspace/`.

### Preconditions (verify before authoring)
1. `./manage.sh start` → backend (8009) + frontend (5179) up; `./manage.sh status` shows both healthy.
2. Seed data present (the 5 modules + 15 tables). If empty, re-run `alamein-campus/seed_tables.py` + `seed_trust_core.py` (see `alamein-campus/README.md`).
3. Confirm `admin` and `alamien_dataowner` can log in and reach `/catalog/products` and `/admin/ai/workspace`.

### Step 0 — Selector recon (do FIRST, before writing any test)
Open `/admin/ai/workspace` and one table detail page as `admin` and record (in the TASK-RESULTS recon section) the **exact accessible name/label/role** for: the workspace open/toggle control, "New chat", the message input, the send button, the conversation tab, the entry-point buttons ("Validate DQ"/"Suggest Rules"/"Investigate"/"Ask about this"), the DQ Accept/Reject buttons, and the NLRuleTestCard "Save" button. Use Playwright's UI-mode `--debug` or `codegen` if helpful. Quote each selector you end up using.

### Deliverable — new `carbon-frontend/e2e/journeys/journey-11-ai-coworker-dq.spec.ts`
Use `test.describe.serial` + one-time `login` (rate-limit: 5 logins/min). Structure in three parts. Every assertion must be **in-browser** (Playwright locators), not raw `fetch`.

**Part A — Regular chat (generalist assistant)** as `alamien_dataowner`:
- A1. Open AI Workspace, click "New chat".
- A2. Type `Summarize the purpose of this carbon data platform in one sentence.` → send → assert an assistant message bubble appears (streaming resolves to a terminal; wait up to 120s). Assert NO "ScopeGuard"/"empty user_identifier" error text is visible (regression from §1 P0).
- A3. If follow-up question chips render, click the first → assert a second assistant turn is produced.
- A4. Feedback: on the latest assistant message, exercise accept or reject via the feedback control (assert the control exists and is clickable; a success/ack state follows).
- A5. Edit: locate a user message, edit its content, assert the edited text persists in the UI; then regenerate (if a regenerate affordance exists) and assert a new assistant turn.
- A6. Export: open the "Export" menu → "Markdown (.md)" → assert a download is triggered or an export completion signal (read-only; must work for any role).
- A7. Rename: rename the conversation to a known title and assert the tab updates.

**Part B — DQ coworker/expert** as `admin` (has `dq:manage_rules`):
- B1. From `/catalog/products`, navigate into a real module (e.g. "Transport Carbon") → its detail page. Assert the module entry points ("Draft Report", "Ask about this") render.
- B2. Open a real table (e.g. "Fleet" or "Electricity") at `/catalog/tables/{id}`. Assert the table entry points ("Validate DQ", "Suggest Rules", "Investigate", "Ask about this") render.
- B3. Click **"Validate DQ"** → assert the AI Workspace opens with a typed conversation (`dq_validate`) whose title is `Validate DQ: <table>` → assert a response streams to a terminal frame and DQ findings are surfaced (look for pass/fail/violation text or a structured result card). Record evidence.
- B4. Click **"Suggest Rules"** → `dq_suggest` → assert suggested rules render (Accept/Reject present). **Accept the first rule** → assert the Accept action succeeds (button disables / success notification / rule name appears), proving the "coworker writes the rule only on my approval" contract.
- B5. **NL rule test**: start an `nl_rule_test` turn with a natural-language rule (e.g. "reject rows where fuel liters is negative") → assert `NLRuleTestCard` renders pass-rate + violations. Toggle Execute Mode ON → click **Save** → assert a rule is created (success signal). This proves the "expert drafts, I confirm" Execute-Mode gate.
- B6. **Investigate**: click **"Investigate"** → assert the Investigate tab renders an `InvestigationCard` (read-only findings) with no mutation buttons.
- B7. **NL query**: from the module detail, use "Ask about this" (or a chat turn) asking `How many rows are in <table>?` (or "Why did emissions change?" starter) → assert a data-grounded answer returns (mentions table/field/row counts).

**Part C — RBAC negative (DQ expert respects permissions)** as `alamien_viewer` (NO `dq:manage_rules`):
- C1. Open the same DQ-suggestion surface; assert Accept/Reject are **absent** and "Requires DQ manage permission" (or equivalent) is shown instead.

**Part D — UX audit on the DQ flow** (W1 render, W3 empty vs tabs, W4 no offline banner, W10 no 404) — condensed, on the table-detail + workspace surfaces.

### Assertion & robustness rules
- Prefer `getByRole`/`getByLabel`/`getByText` over brittle CSS/XPath. No `.Mui*` class selectors.
- Never `expect` a specific LLM token — assert structural signals (a bubble rendered, terminal state reached, a card title present, a button disabled).
- Set generous timeouts on AI turns (`test.setTimeout(180_000)`; `expect(..., { timeout: 120_000 })` on streaming completion).
- Resolve table/module ids dynamically; tolerate seeded-title variations (use substring/`hasText`).

### Verification Gate (run ALL, paste FULL output in TASK-RESULTS)
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npx playwright test e2e/journeys/journey-11-ai-coworker-dq.spec.ts --config e2e/playwright.config.ts --reporter=list
```
Plus a **regression sweep** confirming no breakage:
```bash
npm test -- --run          # unit suite still green
npm run lint               # 0 new errors
npm run build              # clean
```

### Output contract
- File: `carbon-frontend/e2e/journeys/journey-11-ai-coworker-dq.spec.ts` (the authored journey).
- Evidence: `TASK-RESULTS-13.md` at repo root — Executive Summary → Step-0 selector recon → Part A/B/C/D results (✅/❌/⚠ per scenario) → Findings table (ID, severity P0–P3, symptom, repro, suggested fix owner) → Gate verdict (PASSED / PASSED WITH FINDINGS / FAILED).

### DO NOT TOUCH
- Any `backend/**` file. Any existing `e2e/journeys/*.spec.ts` (add a NEW file only). No product source files. Do NOT commit to git (Master Architect commits).

### Notes for the Master
- This phase produces evidence, not product code. A "FAILED" verdict is a valid outcome — findings go to Debugger/Fixer as separate phases.
- Dispatch with the qa-validator activation prompt; worker confirms "Ready as QA/Validator for Carbon."

---

## Phase 14 — QA Re-validation: Journey-11 after defect fixes (F1 / A1 / B5)

**Date:** 2026-08-18 (re-validated 2026-08-27)
**Worker Role:** qa-validator
**Recommended Model:** DeepSeek-V3
**Status:** DONE — 2026-08-27 (commit `9d7c0a3`). **Verdict: FAILED** — B5 chain broken by two confirmed runtime defects: R14-5 ("Test live" sends empty NL) + R14-14 ("Save Rule" 400 `params.max must be numeric`). F1/A1 remain validated; `dq_suggest` + NL-rule-test engine healthy. Full evidence in `TASK-RESULTS-14.md` appended re-validation section.
**Kind:** Pure validation. NO code changes. Evidence only. If a test still fails, record it (severity + repro + suggested owner) and STOP — do NOT fix (RULE_11 → Debugger/Fixer applies fixes).

### Context (already done — trust, do NOT redo)
Three defects were found during Phase 13 execution and are **ALREADY FIXED**. This phase only re-runs the suite to confirm the fixes and produce evidence.
- **F1** — `WorkspaceContext.__init__()` missing `current_view` → 500 on "edit message + regenerate". FIXED in `backend/ai/protocol.py` (default/guard). Already validated: Journey-10 = 29/29 PASS.
- **A1** — `journey-11` `newChat` helper race: `count()` returned 0 while the sessions list was still loading → test waited on an empty-state-only "Start a Chat" button that never appears for a user with existing threads. FIXED in `carbon-frontend/e2e/journeys/journey-11-ai-coworker-dq.spec.ts` (now waits for `getByRole('button', { name: 'New chat' }).first()` to be visible).
- **B5** — `nl_rule_test` transfer created a conversation but did NOT auto-send the NL text, so `NLRuleTestCard` ("Pass rate") never rendered. FIXED in `carbon-frontend/src/shell/AITaskTransferContext.jsx` (auto-send when `type === 'nl_rule_test' && normalizedPayload.nl`). 2 new unit tests added in `carbon-frontend/src/__tests__/AITaskTransferContext.test.jsx` (10 total, all passing).

### Files to Read First
- `carbon-frontend/e2e/journeys/journey-11-ai-coworker-dq.spec.ts` — the suite under test; note the rewritten `newChat` helper and Part B "Pass rate"/Execute-Mode assertions.
- `carbon-frontend/src/shell/AITaskTransferContext.jsx` — note the `nl_rule_test` auto-send block.
- `carbon-frontend/src/__tests__/AITaskTransferContext.test.jsx` — 10 tests.
- `.ai-toolkit/shared/qa-framework.md` — 4-layer validation model + evidence standards.
- `.ai-toolkit/shared/security.md` — RBAC expectations (Part C negative test).

### Preconditions (verify BEFORE running)
1. `./manage.sh status` → backend (:8009) + frontend (:5179) both healthy. If not: `./manage.sh start`.
2. `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8009/carbon-api/health/` → `200`.
3. `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5179/` → `200`.

### Tasks

1. **UNIT GATE (fast — confirms B5 fix + no regressions)**
   - `cd carbon-frontend && npx vitest run src/__tests__/AITaskTransferContext.test.jsx` → `10 passed`.
   - `cd carbon-frontend && npm test -- --run` → all green (expected ~400+).

2. **E2E GATE — re-run Journey-11**
   - `cd carbon-frontend && npx playwright test --config e2e/playwright.config.ts journey-11-ai-coworker-dq` → expect ALL tests PASS.
   - Confirm specifically: Part A `newChat` no longer times out (A1), and Part B "Pass rate" card + "Save Rule" + Execute-Mode steps pass (B5).

3. **REGRESSION SWEEP — Journey-10 still green**
   - `cd carbon-frontend && npx playwright test --config e2e/playwright.config.ts journey-10-ai-workspace` → 29/29 PASS (F1 regression guard).

4. **ON FAILURE — record, do NOT fix**
   - For each ❌, read `carbon-frontend/test-results/**/error-context.md`, capture the exact failing locator/assertion + screenshot path, classify severity P0–P3, and note the likely owner (frontend-worker / backend-worker / debugger-fixer). STOP after recording — no code edits.

### DO NOT TOUCH
- `backend/**` — no backend changes (F1 already fixed).
- `carbon-frontend/src/**` — no product code changes (B5 already fixed).
- `carbon-frontend/e2e/journeys/journey-11-ai-coworker-dq.spec.ts` — no spec edits (A1 already fixed). Re-run as-is.
- Do NOT commit. Master Architect commits.

### Verification Gate (paste FULL output into TASK-RESULTS)
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npx vitest run src/__tests__/AITaskTransferContext.test.jsx   # → 10 passed
npm test -- --run                                             # → all green
npx playwright test --config e2e/playwright.config.ts journey-11-ai-coworker-dq   # → all PASS
npx playwright test --config e2e/playwright.config.ts journey-10-ai-workspace     # → 29/29 PASS
```

### Output contract
- Append to `TASK-RESULTS.md` (or new `TASK-RESULTS-14.md` at repo root) using the Part B handoff format: Executive Summary → Task results (1..4 with ✅/❌) → Files Changed (should be NONE) → Verification Output (full paste) → Deviations → Issues Found (findings table: ID, severity, symptom, repro, owner).
- End with verdict: PASSED / PASSED WITH FINDINGS / FAILED.

### Notes for the Master
- Expected outcome: PASSED (all three fixes validated). If B5 still fails, the most likely cause is a suggestion whose `nl` resolves empty (falls back to `definition?.name`) → produces no card; the worker records that exact repro for the Debugger/Fixer.

---

## Phase 15 — AI User Profile Injection: the AI reasons *about* the user, not just gates by them

**Date:** 2026-08-18
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek-V3
**Status:** DONE — `_user_profile_message` + `[User Profile]` system message + `profile_content` in context signature (commit `177d662`).
**Kind:** Small, low-risk backend addition to prompt assembly. The `Scope` is already computed server-side on every AI call; this phase only *enriches the assembled prompt* with a compact user profile so the LLM can reason about the user. It does NOT change any security decision.

### Context (verified — trust, do not re-derive)
- `backend/ai/intelligence.py::build_scope(user)` already derives a full `Scope` (`user_identifier`, `org_unit_ids`, `module_ids`, `is_read_only`, `is_superuser`) from `ScopedRole`. This is authoritative and is NEVER sent to the LLM as free-form context — it stays on the security side only.
- `backend/ai/context_assembler.py` is the prompt-assembly seam: it builds the `[Workspace Context]` system message from `WorkspaceContext` and retrieves scoped long-term memory. This is the correct place to add a `[User Profile]` system message.
- `backend/ai/guards.py` guard chain is NOT touched. Guards keep using `Scope` for security decisions.
- Frontend `AuthContext` already exposes `user.id`, `roles`, `org_units`, `userCapabilities` — but the AI must NOT trust client-sent identity; the profile is re-derived server-side from `request.user` + `build_scope(user)`.

### Implementation (backend-only)
1. **`backend/ai/context_assembler.py`** — add a `_user_profile_message(scope, user)` helper returning a compact `[User Profile]` system message dict:
   - name (first_name/last_name, fall back to username)
   - active role names (from ScopedRole group names, deduped)
   - org-unit names (resolve `org_unit_ids` → `OrgUnit` display/name)
   - module names (resolve `module_ids` → `Module.name`)
   - `is_read_only` flag (phrase as "read-only" vs "can write")
   - `is_superuser` flag
   - NEVER include the numeric `user_identifier` as semantic context (it stays for audit/scoping only).
   - Keep the message ≤ ~300 chars; budget it with the existing token-estimation helper like the other tiers.
2. **Wire it in** — inject the message into the assembled system prefix next to `[Workspace Context]`, ordered: `[User Profile]` → `[Workspace Context]` → resolved mentions → retrieved memory. Skip entirely when `scope` has no `user_identifier` (anonymous/None).
3. **No changes** to `build_scope`, `guards.py`, or the Scope security path.

### Tests (new `backend/ai/tests/test_user_profile.py`)
- (a) profile message includes username + role names + org-unit name + "read-only" flag.
- (b) superuser profile includes the superuser marker.
- (c) anonymous/empty scope → no `[User Profile]` message emitted.
- (d) profile respects the token budget (truncates within budget).

### DO NOT TOUCH
- `backend/ai/guards.py`, `backend/ai/intelligence.py::build_scope` (security path).
- Any `carbon-frontend/**` file.
- `backend/ai/protocol.py` (no new dataclass needed).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_user_profile.py ai/tests/test_context_assembler.py -q
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q   # no regressions
```

### Output contract
- Append to `TASK-RESULTS.md` (Part B handoff format): Summary → Task results → Files Changed → Verification Output (full paste) → Deviations → Issues Found.

### Notes for the Master
- Expected: PASSED. Low risk — additive prompt enrichment only; the guard chain is untouched.

---

## Phase 16 — Conversation resume: stop new-session noise on every AI click

**Date:** 2026-08-18
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek-V3
**Status:** DONE — `resume` action + `resume_conversation` in `workspace_api.py` (commit `177d662`).
**Kind:** Frontend-only, small. No backend changes. No new API. Reuses existing `listConversations`.

### Problem (verified)
Every AI-button transfer calls `createConversation` unconditionally, and `handleNewChat` always spawns a fresh "New Chat". Clicking the same button repeatedly piles up near-identical threads.

### The simple rule (do NOT over-engineer)
**One open conversation per `(user, conversation_type, app_identifier)`.** That's the whole design:
- `chat` → one "General" thread.
- `investigate` → one investigation thread (per app).
- `dq_validate` → one DQ-validate thread (per app). Etc.
- No rule_id/table_id/module_id matching. No "fork to new session" (defer that to backlog). Just *resume the most recent open thread of the same kind*.

### Implementation
1. **`src/api/aiWorkspace.js`** — add `findOpenConversation(token, { conversation_type, app_identifier })`:
   - call existing `listConversations(token, { conversation_type, limit: 200 })`
   - filter client-side to `!is_archived` and (when `app_identifier` given) `c.app_identifier === app_identifier`
   - return the first by `-updated_at`, or `null`.
2. **`src/shell/AITaskTransferContext.jsx`** — in `transferTask`, before `createConversation`:
   - `const existing = await findOpenConversation(...)`.
   - if found: for auto-send types (`nl_rule_test`, `investigate`, `report_draft`) still `sendMessage(existing.id, <sentinel>)`; set `pendingTransferId(existing.id)`; return `existing.id`.
   - else: current create path unchanged.
3. **`src/shell/AIWorkspace.jsx`** — `handleNewChat`: first look up the most recent open `chat` conversation; if found `setActiveId(existing.id)` (no create), else create one.

### Explicitly out of scope
- No backend resume endpoint. No `get_or_create`. No task_payload diffing. No "move message to new session" UI.
- Guard chain, audit trail, memory partitioning — all untouched (they stay per-conversation, which is exactly why we resume-by-kind instead of a single monolith).

### Tests (frontend unit)
- `src/__tests__/AITaskTransferContext.test.jsx`: (a) transfer of a type with an existing open thread does NOT call `createConversation` and instead sends into it; (b) transfer with no open thread creates one; (c) archived threads are skipped.
- `src/__tests__/AIWorkspace.test.jsx` (or closest existing): "New chat" with an existing open `chat` thread reuses it; none → creates.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npx vitest run src/__tests__/AITaskTransferContext.test.jsx   # green
npm test -- --run                                             # no regressions
```

### Output contract
- Append to `TASK-RESULTS.md` (Part B handoff format): Summary → Task results → Files Changed → Verification Output → Deviations → Issues Found.

### Notes for the Master
- Expected: PASSED. Frontend-only; the single behavior change is "reuse the latest open thread of the same kind instead of always creating".

---

## Phase 17-A — Backend: Provider connection reliability + error taxonomy

**Date:** 2026-08-18
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek-V3
**Status:** DONE — `route_chat` retry + `provider_unavailable` taxonomy (`test_llm_retry.py`; commit `177d662`).
**Kind:** Backend-only. Small, high-value. No schema change. No new dependency.
**Hard rule context:** `RULE_23` (no implementation leakage) — error copy is de-leaked in Phase 17-B, not here.

### Problem (verified)
`router.route_chat()` — the path every user chat message hits — calls the raw OpenAI client directly with **no retry**:
- `get_llm_client()` (`provider.py`) sets `max_retries=0, timeout=60`.
- `route_chat()` calls `client.chat.completions.create(**kwargs)` directly (line ~203).
- `@_retry_decorator` (3 attempts, exp backoff 1s/2s/4s) is only wired to `chat_completion()` / `chat_completion_with_tools()`, used by eval/optimizer/synthesizer — **NOT** the user's chat path.

So one transient POE blip (timeout / rate-limit / connection reset / 5xx) → `engine_runtime._call_llm` swallows it (`except Exception → return None`) → `_save_provider_unavailable_message` → *"AI provider is currently unavailable."* A 60s hang also spins "thinking…" for a full minute before degrading.

### Implementation
1. **`backend/ai/engine/llm/provider.py`**
   - Add a retried raw-completion helper reusing the existing decorator:
     ```python
     @_retry_decorator
     async def create_completion(client, **kwargs):
         return await client.chat.completions.create(**kwargs)
     ```
   - Lower `timeout=60.0` → `timeout=30.0` in `get_llm_client()` so a hang fails fast and retries instead of spinning.
2. **`backend/ai/engine/llm/router.py`**
   - Replace `response = await client.chat.completions.create(**kwargs)` with `response = await create_completion(client, **kwargs)`.
   - Add `model: str | None = None` keyword to `route_chat`; when set, use it instead of `get_model_for_task(task)` (this is the seam Phase 18-A uses). Log the override.
3. **Error taxonomy** — new `backend/ai/engine/llm/errors.py` (or inline in `provider.py`):
   - `classify_llm_error(exc) -> "transient" | "permanent"`.
   - transient: `APITimeoutError`, `APIConnectionError`, `RateLimitError`, `InternalServerError`, `ServiceUnavailableError`.
   - permanent: `AuthenticationError`, `PermissionDeniedError`, `BadRequestError`, `NotFoundError`.
4. **Surface the taxonomy on the chat SSE frame**:
   - `intelligence.send_message_stream` currently yields `{"type": "error", "error": value}`. Add `"error_kind"` so the frontend can distinguish "tap to retry" vs "offline".
   - Have the provider carry the kind (extend the `(kind, value)` error tuple to `(kind, value, meta)`), and pass it through. Do **not** re-classify by string in the frontend.

### DO NOT TOUCH
- Budget logic, `_TASK_MODEL_MAP`, `EVAL_*` policy.
- `chat_completion()` / `chat_completion_with_tools()` signatures — other callers (eval/optimizer/synthesizer) depend on them.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
.venv/bin/python manage.py check                       # → "System check identified no issues"
.venv/bin/python -m pytest ai/tests/test_chat_stream.py ai/tests/test_chat_wiring.py \
  ai/tests/test_workspace_stream.py ai/tests/test_live_llm_activation.py -q
.venv/bin/python -m pytest ai -q                        # → full AI suite, no regressions
```
Add one new test: monkeypatch the client to raise `APITimeoutError` once then succeed → assert the call is retried and returns.

### Output contract
Append to `TASK-RESULTS.md` (Summary → Task results → Files Changed → Verification Output → Deviations → Issues Found).

### Notes for the Master
- This is the root cause of the recurring "AI provider is currently unavailable" reports. Retry at `route_chat` FIRST; keep `engine_runtime._call_llm`'s deterministic fallback as a last resort, not the first line of defense.

---

## Phase 17-B — Frontend: Status bar under input + de-leak status copy

**Date:** 2026-08-18
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek-V3
**Status:** DONE — `AIStatusBar.jsx` + de-leaked status copy (commit `177d662`).
**Kind:** Frontend-only (+ 2 one-line backend copy edits). Small.
**Hard rule context:** `RULE_23` / `base-rules §16` — all copy below must be outcome-flavored, never internals.

### Problem
Status/progress copy lives inside the message thread (`AIWorkingIndicator` prints verbose stage labels like *"Translating question to SQL…"* / *"Analyzing table profile…"*), which leaks implementation (violates RULE_23). There is no persistent status signal under the input — the user only sees the offline banner after it has already failed.

### Implementation
1. **De-leak copy (RULE_23):**
   - `carbon-frontend/src/shell/AIWorkingIndicator.jsx`: collapse `TYPE_MESSAGES` to a single generic `"AI is thinking…"` (the `nl_query` entry is already dead — `stage` always overrides).
   - `backend/ai/intelligence.py` `_progress_stage_label` (one edit): `"Translating question to SQL…"` → `"Working on your query…"`, `"Analyzing table profile…"` → `"Reading your table…"`.
   - `backend/ai/intelligence.py` `_save_provider_unavailable_message` (one edit): `"AI provider is currently unavailable. Please try again later."` → `"I couldn't reach the AI service — try again in a moment."`
2. **New `carbon-frontend/src/shell/AIStatusBar.jsx`:**
   - Slim footer row rendered inside `AIInputBar.jsx` below the input row.
   - States: `idle` (subtle "Carbon AI is ready") → `working` ("Working…") → `streaming` ("Generating…") → `error-transient` ("Couldn't reach the AI service — tap to retry", clickable → `handleRetry`) → `error-permanent` ("AI service is offline" + link to admin console).
   - Drive it from the existing `providerOffline` + `workingStage` state in `AIConversationView`; pass down to `AIInputBar` (reuse whatever context exists — do **not** add a new global store).
   - Use `error_kind` from Phase 17-A to pick transient vs permanent.
   - Every string passes RULE_23: no "provider", no "SQL", no internal stage names.

### DO NOT TOUCH
- `aria-label`s / roles E2E depends on: `Message input`, `Send message`, `New chat`.
- The SSE parser; `AIOfflineBanner.jsx` (keep, but reconcile wording so it doesn't contradict the status bar).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npm run build
npx vitest run src/__tests__/AIStatusBar.test.jsx   # NEW: each state renders expected copy
npm test -- --run

# De-leak grep (should return nothing user-facing):
grep -rn "Translating question to SQL\|AI provider is currently unavailable\|provider_unavailable" src/ backend/ai/intelligence.py
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- This is where RULE_23 becomes user-visible. Keep each status string ≤ ~40 chars.

---

## Phase 18-A — Backend: Model catalog endpoint + model override threading

**Date:** 2026-08-18
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek-V3
**Status:** DONE — `_CHAT_MODEL_CATALOG` + `model_override` column + `route_chat` override (commit `177d662`).
**Kind:** Backend + API. Small-medium. Decision needed on persistence (see Notes).

### Problem
No user-facing way to pick a model. `_settings_llm()` returns raw config (admin-only), `LLM_COST_MODELS` holds the cost table, and `route_chat` hard-selects by task. The user wants a model dropdown with a short description + cost.

### Implementation
1. **New read-only endpoint `GET /carbon-api/ai/models/`** (in `activation_api.py` — it is already the read-only settings surface):
   - Build the catalog from `LLM_COST_MODELS` (cost) + `_TASK_MODEL_MAP`/`get_settings()` (which models are wired) + a small static description map.
   - Return:
     ```json
     { "models": [
        {"id":"GPT-4o","name":"GPT-4o","description":"Best overall reasoning — smarter, higher cost","input_cost":2.5,"output_cost":10.0,"kind":"chat","recommended":true},
        {"id":"GPT-4o-mini","name":"GPT-4o mini","description":"Fast and cheap — everyday questions","input_cost":0.15,"output_cost":0.6,"kind":"chat","recommended":false},
        {"id":"Claude-Sonnet-4.5","name":"Claude Sonnet 4.5","description":"Balanced reasoning","input_cost":3.0,"output_cost":5.0,"kind":"chat","recommended":false}
     ] }
     ```
   - List only models present in `LLM_COST_MODELS` (actually selectable); mark the configured `LLM_MODEL`/`LLM_NORMAL_MODEL` as `recommended`.
   - Never return `LLM_API_KEY` or `base_url` (RULE_23 + security).
2. **Thread the override** — `route_chat(..., model=None)` already added in 17-A:
   - `workspace_api.send_message` / `send_message_stream` → `ChatRequest` → `provider.chat_stream` → `engine_runtime` → `route_chat`.
   - Add `model` to `ChatRequest` (protocol) with `None` default.
   - Persist the user's chosen model per conversation: **either** a new nullable column `AIConversation.model_override` (needs a migration) **or** `task_payload_json["model"]` (zero migration). See Notes — Master decides.
3. **Audit:** `route_chat` already logs the model to `llm_call_logs`; no extra work.

### DO NOT TOUCH
- Cost-guardrail `_EXPENSIVE_MODEL_MARKERS`, budget enforcement, `EVAL_*` policy.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run   # only if you add the column
.venv/bin/python -m pytest ai -q
# + curl the new endpoint and paste the JSON catalog
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- Decision: **column** (`model_override`) = cleaner audit but adds a migration; **task_payload_json** = zero migration but less queryable. I lean column. Flag your choice in TASK-RESULTS.

---

## Phase 18-B — Frontend: Model selector dropdown

**Date:** 2026-08-18
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek-V3
**Status:** DONE — `AIModelSelect.jsx` + `listModels` (commit `177d662`).
**Kind:** Frontend-only. Small-medium.

### Problem
No way to choose a model. The 18-A catalog has id/name/description/cost; surface it as a compact dropdown with a short description + cost hint — product metadata, not provider internals.

### Implementation
1. **`carbon-frontend/src/api/aiWorkspace.js`** (or `aiPulse.js`): add `listModels(token)` → `GET /carbon-api/ai/models/`.
2. **New `carbon-frontend/src/shell/AIModelSelect.jsx`**: MUI `Select` (size small) rendered in the `AIStatusBar` footer row (left of the status text, or a small icon-button popover).
   - Each option: name + one-line description + cost hint (`"🧠 Smarter · $$$ ~$2.50/$10 per 1M"` or `"⚡ Fast · $ ~$0.15/$0.60 per 1M"`). Theme tokens only, no raw hex.
   - Button label = currently-selected model (truncated).
3. **Persistence:** store selection in `localStorage` keyed per user (`carbon.ai.model.<userId>`); restore on mount.
4. **Send:** pass `model` on the message payload so 18-A's override is exercised — add it to the transfer/message payload (or create/send request if 18-A chose the column).

### DO NOT TOUCH
- `AITaskTransferContext` contract beyond adding the `model` field.
- E2E `aria-label`s.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npm run build
npx vitest run src/__tests__/AIModelSelect.test.jsx   # NEW: renders options + persists selection
npm test -- --run
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- This is the one sanctioned place where model names are user-visible (RULE_23 exception — a model selector is a product decision, not a leak). Cost is product metadata, not provider internals.

---

## Phase 19 — Message operations & retry/resume resilience

**Date:** 2026-08-18
**Worker Role:** backend-worker (19-A), frontend-worker (19-B)
**Recommended Model:** DeepSeek-V3
**Status:** DONE — 19-A (backend: `is_deleted`/`context_signature`/`parent` on
AIMessage + migration 0012, `retry_message[_stream]`/`delete_message`/
`edit_message(regenerate)` in intelligence.py, `POST …/retry` + `PATCH|DELETE
…/messages/{id}` in workspace_api.py, retry/regenerate serializers, 7 tests) ✅;
19-B (frontend: `retryMessageStream`/`editMessage(regenerate)`/`deleteMessage`
in aiWorkspace.js, AIMessageBubble hover menu Copy/Retry/Edit/Delete + inline
edit + confirm, AIConversationView optimistic delete + thread-cut + filter
`is_deleted` on load, 16 new tests) ✅. Verified: check 0 issues, migrations
clean, 393 passed (backend), 7/7 retry tests, lint+build clean.
**Kind:** Backend + frontend. Medium-large.

### Problem
A conversation is currently append-only and immutable: a user cannot retry a
failed reply, regenerate a different answer, delete a bad turn, or copy a
message. The NEXTGEN FSM (`AIMessage` status + `AIGeneration` lease) exists on
paper but message-level operations aren't implemented. Users hit dead ends on a
single 500/timeout and must start a new conversation.

### Design decisions (deep)
- **Retry == regenerate.** "Retry the assistant reply to this user message" is
  the same machinery as "edit this user message and regenerate". Model both as
  one endpoint: re-run the pipeline for a *user turn*, producing a fresh
  assistant `AIMessage`, reusing the same context snapshot (the conversation
  state at the time of that turn — NOT the current tail, or a mid-thread retry
  would leak later messages into the window).
- **Context snapshot, not live history.** `context_assembler.py` already builds
  per-turn context; persist a lightweight `context_signature` (message-id vector
  + model + profile hash) on each assistant message so a retry can rebuild the
  exact window even if later messages were added/deleted.
- **Delete = soft + thread-cut.** Add `is_deleted` to `AIMessage`. Deleting a
  user turn soft-deletes it and all descendant replies (a dangling reply with no
  prompt is confusing). Deleting an assistant reply soft-deletes just that reply
  (orphan tolerated, rendered dimmed with "This reply was removed").
- **Copy = frontend-only.** `navigator.clipboard` on the bubble; no backend call.
- **Restore context.** `context_assembler` must filter `is_deleted` messages
  BEFORE window truncation (otherwise deleted messages consume budget).

### 19-A Backend
1. `backend/ai/models.py` (or wherever `AIMessage` lives): add `is_deleted`
   (default False), `parent_id` (self FK, nullable) if not present, and
   `context_signature` (JSONField/CharField).
2. `backend/ai/workspace_api.py`:
   - `POST /ai/conversations/{cid}/messages/{user_msg_id}/retry` → abort any
     in-flight `AIGeneration` for that turn, create a new assistant message,
     stream via the existing SSE path (reuse Phase 18 model override).
   - `PATCH /ai/conversations/{cid}/messages/{mid}` (edit user text + flag
     `regenerate=true`) → updates text then invokes the same retry machinery.
   - `DELETE /ai/conversations/{cid}/messages/{mid}` → soft-delete + descendants.
3. `backend/ai/context_assembler.py`: filter `is_deleted` in history assembly;
   include `context_signature` in the assembled payload.
4. Abort semantics: reuse NEXTGEN §5.2 `AIGeneration` lease + cancellation; a
   retry while a generation is streaming must cancel the old one first (no
   orphaned streams).

### 19-B Frontend
1. `AIMessageBubble.jsx`: add a hover/overflow menu — Copy, Retry (assistant
   reply), Edit (user message), Delete. Delete → confirm dialog.
2. Retry/edit reuse the existing stream hook; render the new assistant reply as a
   fresh bubble appended after the user turn (don't re-render the whole thread).
3. Optimistic delete: dim + "removed" placeholder; reconcile on server confirm.
4. `findOpenConversation`/resume (Phase 16) must skip deleted messages when
   restoring the visible thread.

### DO NOT TOUCH
- The six-witness pipeline (`draft.py`/`runner.py`) internals — retry re-enters
  at the public pipeline entry, not inside witnesses.
- E2E `aria-label`s (add new ones, don't rename existing).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint && npm run build && npm test -- --run
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- Retry is the single highest-leverage resilience feature: it converts "start
  over" into "try again", which is the #1 user-visible trust signal.
- Keep `context_signature` as an opaque hash/vector — never serialize actual
  message text into it (privacy + drift detection, not replay).

---

## Phase 20-A — Model catalog v2: backend (versions + tiers + cost fidelity)

**Date:** 2026-08-18
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek-V3
**Status:** DONE — `ModelCatalog` model (`catalog.py`) + migrations `0013`/`0014` (8 seeds) + `AIModelsView` now catalog-backed. Gate: 5/5 new tests, 398 ai total, check + makemigrations clean.
**Kind:** Backend-only. Small-medium.
**Depends on:** Phase 18-A (model catalog endpoint).

### Files to Read First
- `backend/ai/models/workspace.py` — existing AI models + how `AIMessage` carries model id
- `backend/ai/workspace_api.py` — the Phase 18-A `GET /ai/models/` action (extend, don't fork)
- `backend/ai/engine/llm/router.py` — where a model id is resolved today (read-only reference)
- `.ai-toolkit/shared/data-layer.md` + `config.md` — model/field + env conventions

### Files to Change
- `backend/ai/models/workspace.py` (or a new `backend/ai/models/catalog.py`) — new `ModelCatalog` model + migration
- `backend/ai/workspace_api.py` — extend the models endpoint response shape
- `backend/ai/tests/test_model_catalog.py` (NEW) — catalog + endpoint tests

### Context
Phase 18 shipped a selector but the catalog is a thin list with no tiering,
versioning, or cost fidelity. Users can't tell "cheap/fast vs smart/expensive",
and there's no path to retire a model without breaking historical usage
attribution. Phase 21 (usage/cost) depends on this single-source cost table.

### Implementation
1. New `ModelCatalog` model — fields: `model_id` (unique, stable slug),
   `display_name`, `tier` (choices `fast|balanced|brain`), `version`,
   `context_window`, `input_cost_per_1m` (Decimal), `output_cost_per_1m` (Decimal),
   `deprecated` (bool), `superseded_by` (self FK nullable), `capabilities` (JSON).
   Use `django.utils.timezone.now()` for any timestamps (project.config RULE).
2. Data migration / seed: 6–9 rows covering all three tiers (≥2 `fast`, ≥2
   `balanced`, ≥2 `brain`) with correct per-1M cost + context window. Map tiers
   to concrete provider ids server-side; never expose raw routing (RULE_23).
3. Extend the Phase 18-A models endpoint to return `tier`, `context_window`,
   `deprecated`, `superseded_by`, `capabilities`, and both cost fields — as a
   compatible superset (keep the existing id/name/description/cost shape so the
   current selector does not break). Deprecated rows still returned (attribution).

### DO NOT TOUCH
- Provider routing internals in `engine/llm/router.py` — routing stays provider-side; only read cost from the catalog.
- Frontend files — `AIModelSelect.jsx` tier grouping is Phase 20-B.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check                 # → "no issues"
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run  # → "No changes detected"
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q                 # → all green (393+ baseline)
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_model_catalog.py -q  # → new tests pass
# curl GET /carbon-api/ai/models/ and assert: 3 tiers present; deprecated rows still returned
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- Cost must come from ONE place and be applied consistently to usage rows (Phase
  21). Never compute cost ad hoc in the router.

---

## Phase 20-B — Model catalog v2: frontend (tier grouping in selector)

**Date:** 2026-08-18
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek-V3
**Status:** DONE — `AIModelSelect.jsx` tier grouping (⚡/⚖/🧠 via `TIER_ORDER.flatMap`), deprecated hidden, cost hint (`formatContextWindow`). Gate: 8/8 vitest, lint clean, build ✓.
**Kind:** Frontend-only. Small.
**Depends on:** Phase 20-A (endpoint returns `tier`/`deprecated`).

### Files to Read First
- `carbon-frontend/src/shell/AIModelSelect.jsx` — current selector
- `carbon-frontend/src/api/aiWorkspace.js` — `listModels`
- `.ai-toolkit/shared/design-system.md` — tokens only, no raw hex

### Files to Change
- `carbon-frontend/src/shell/AIModelSelect.jsx` — group by tier
- `carbon-frontend/src/__tests__/AIModelSelect.test.jsx` — extend for grouping + deprecated filtering

### Implementation
1. Group options by `tier` with headers: `⚡ Fast`, `⚖ Balanced`, `🧠 Brain`.
2. Hide `deprecated=true` models from the picker (endpoint still returns them).
3. Show cost hint from the catalog cost fields (product metadata, not internals).
4. Theme tokens only — no raw hex/px (RULE_8).

### DO NOT TOUCH
- Backend files.
- E2E `aria-label`s.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/AIModelSelect.test.jsx   # → passes
npm run build
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- Prerequisite for Phase 21 (usage/cost). 20-A must land before this.

---

## Phase 21-A — Usage & cost: backend (aggregation + quota)

**Date:** 2026-08-18
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek-V3
**Status:** DONE — usage aggregation + quota (commits `bb91658` / `d580edc`)
**Kind:** Backend-only. Medium.
**Depends on:** Phase 20-A (single-source cost table).

### Files to Read First
- `backend/ai/models/workspace.py` — where `AIMessage`/generation live; add usage fields
- `backend/ai/engine/llm/router.py` — where generation completes (write usage here)
- `backend/ai/models/workspace.py` `AIUserProfile` (Phase 15) — add quota fields
- `backend/ai/workspace_api.py` — add usage viewsets here
- `.ai-toolkit/shared/api-contract.md` + `data-layer.md`

### Files to Change
- `backend/ai/models/workspace.py` — usage + quota fields + migration
- `backend/ai/engine/llm/router.py` (or the completion hook) — persist usage/cost at completion
- `backend/ai/usage_service.py` (NEW) — aggregation service
- `backend/ai/workspace_api.py` — two usage endpoints
- `backend/ai/tests/test_usage.py` (NEW)

### Context
Users and admins cannot see usage, cost, or quota. Token accounting exists in the
pipeline but is never persisted or aggregated, and there is no per-user limit
model. Cost must read the Phase 20-A catalog (never recomputed ad hoc).

### Design decisions (deep)
- **Usage is a first-class generation attribute.** Persist `prompt_tokens`,
  `completion_tokens`, `total_tokens`, `model_id`, `cost` on each generation.
  Write once at completion; never recompute from prompt text later.
- **Quota is a budget, not a kill switch (v1).** Per-user monthly token budget,
  soft warning at 80%, hard limit with a clear "quota reached" + reset date.
- **Two endpoints, one source:** `GET /ai/usage/summary?period=30d` →
  `{total_tokens, total_cost, by_tier, by_model, remaining, limit, reset_at}`;
  `GET /ai/usage/by-conversation?period=30d` → per-conversation tokens/cost.

### Implementation
1. Add usage fields to the generation/message model + migration.
2. Persist usage + cost at generation completion (read cost from Phase 20-A catalog).
3. Add `AIUsage` aggregation service + the two endpoints (DRF viewsets, CBAC-scoped).
4. Add `AIUserProfile` quota fields (`monthly_token_limit`, reset rule) + a
   request-time check that attaches a `quota` error code when exceeded.

### DO NOT TOUCH
- The streaming path — usage write happens at completion, not mid-stream.
- Frontend files (Phase 21-B).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check                 # → "no issues"
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run  # → "No changes detected"
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q                 # → all green
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_usage.py -q        # → new tests pass
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- Do NOT ship usage without quota surfacing in the same phase — a cost meter with
  no limit is a "surprise bill" generator. Always show remaining + reset.
- RULE_23: endpoints return aggregate numbers only, never provider base_url/keys.

---

## Phase 21-B — Usage & cost: frontend (dedicated activity-bar tab)

**Date:** 2026-08-18
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE — Usage & Cost tab (commit `189815a`)
**Kind:** Frontend-only. Medium.
**Depends on:** Phase 21-A (endpoints) — ✅ DONE (bb91658).

### Recommendation (resolved)
**Dedicated activity-bar tab at the right of the AI shell — NOT an icon popup.**
A popover cannot hold per-conversation breakdown + time series + quota progress +
alerts. Matches NEXTGEN §8.3 "fixed mode tabs, never dynamic" and stays
keyboard-accessible. A StatusBar sparkline may deep-link into the tab.

### Files to Read First
- `carbon-frontend/src/shell/AIWorkspace.jsx` — where the right activity bar lives
- `carbon-frontend/src/shell/StatusBar.jsx` — optional sparkline deep-link
- `carbon-frontend/src/api/aiWorkspace.js` — add usage fetch helpers
- `.ai-toolkit/shared/design-system.md`

### API contract (Phase 21-A — verified, do not guess field names)
- `GET /carbon-api/ai/usage/summary/?period=30d` →
  `{ period_days, total_tokens, prompt_tokens, completion_tokens, total_cost, total_generations, by_tier, by_model, quota }`.
  `by_tier`/`by_model` entries: `{ tokens, cost, generations }`. `total_cost` and
  bucket `cost` are **strings** (`"0.000000"`) — `Number()` before display.
- `GET /carbon-api/ai/usage/by-conversation/?period=30d` →
  `{ period_days, conversations: [{ conversation_id, title, total_tokens, total_cost, generation_count, message_count }] }`
  (already sorted desc by tokens).
- `quota` = `{ limit, used, remaining, reset_at, window_start, pct, soft_warning, hard_exceeded }`.
  `reset_at`/`window_start` are ISO-8601 strings; render the reset date via dayjs
  timezone (project default Africa/Cairo).
- `apiFetch` takes `(endpoint, { token })` and joins `API_BASE_URL` (ends in
  `/carbon-api/`), so the helpers are `apiFetch('ai/usage/summary/', { token })`
  and `apiFetch('ai/usage/by-conversation/', { token })` — NOT under `ai/workspace/`.
- Period param: `?period=30d` (also `7d`/`90d` accepted by backend).

### Files to Change
- `carbon-frontend/src/api/aiWorkspace.js` — `getUsageSummary`, `getUsageByConversation`
- `carbon-frontend/src/shell/AIUsageTab.jsx` (NEW) — the tab
- `carbon-frontend/src/shell/AIWorkspace.jsx` — register the fixed "Usage" tab
- `carbon-frontend/src/__tests__/AIUsageTab.test.jsx` (NEW)

### Implementation
1. New right activity-bar entry **"Usage"** (id `usage`, fixed mode, id-based,
   keyboard navigable): add `{ id: 'usage', icon: <DataUsageIcon/>, label: 'Usage' }`
   to the activity-bar array in `AIWorkspace.jsx` (currently sessions/context/investigate/artifacts,
   ~line 568-575), and render it as a **main-content panel** by adding an
   `activePanel === 'usage' ? <AIUsageTab /> :` branch in the leftmost `flex:1`
   box (next to `investigate`/`artifacts`, ~line 475-479). `togglePanel`/`activePanel`
   already exist — do NOT add new nav state.
2. `AIUsageTab.jsx` (self-fetching, `useEffect` on mount + a `period` selector
   30d/7d/90d + a manual Refresh): quota progress bar (remaining vs limit +
   reset date), current-period tokens/cost, tier/model breakdown,
   per-conversation table.
3. Optional `StatusBar.jsx` sparkline/icon deep-links into the tab (skip if it
   complicates the diff — it's optional).
4. Theme tokens only (RULE_8); copy describes outcomes, not internals (RULE_23).
   Cost shown as `$x.xx` (parse the string), token counts humanized (e.g. `1.2M`).

### DO NOT TOUCH
- Backend files.
- The streaming UI path.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/AIUsageTab.test.jsx   # → passes
npm run build
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- 21-A must land first. Always render remaining + reset date, never a bare cost number.

---

## Phase 22-A — User preferences: backend (profile config fields + wiring)

**Date:** 2026-08-18
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE — profile config fields + wiring (commit `715a2a0`)
**Kind:** Backend-only. Small-medium.
**Depends on:** Phase 15 (AIUserProfile), Phase 20-A (catalog FK target).

### Files to Read First
- `backend/ai/models/workspace.py` — existing `AIUserProfile` (Phase 15)
- `backend/ai/context_assembler.py` — where defaults/overrides resolve
- `backend/ai/engine/llm/router.py` — model resolution (default_model_id)
- `backend/ai/workspace_api.py` — profile endpoint location
- `.ai-toolkit/shared/data-layer.md` + `api-contract.md`

### Files to Change
- `backend/ai/models/workspace.py` — add preference fields + migration
- `backend/ai/workspace_api.py` — `GET/PATCH /ai/profile/`
- `backend/ai/context_assembler.py` (or the creation path) — resolution wiring
- `backend/ai/tests/test_profile_prefs.py` (NEW)

### Context
Every user gets the same defaults: default model, temperature, auto-titling,
memory on/off, usage-alert threshold. There is no per-user config surface, so
preferences can't persist across sessions.

### Design decisions (deep)
- **Extend `AIUserProfile` (Phase 15) with preferences, not a new table.**
  Fields: `default_model_id` (FK/nullable → Phase 20 catalog), `temperature`
  (bounded 0.0–2.0), `auto_title` (bool), `memory_enabled` (bool),
  `usage_alert_threshold` (int percent, default 80).
- **Resolution order** (low→high): system default → domain manifest →
  user profile → per-message override. Insert the profile read at the right
  layer so per-message still wins.

### Implementation
1. Migration: add preference fields to `AIUserProfile`.
2. `PATCH /ai/profile/` (upsert) + `GET /ai/profile/` returning resolved
   effective defaults (so the UI can render current values including inherited
   system defaults).
3. Wire `default_model_id` + `temperature` into message creation / router
   resolution; `auto_title` into conversation titling; `memory_enabled` into
   memory write gating.

### DO NOT TOUCH
- Phase 15 profile *injection* logic (`_user_profile_message`) — this adds
  fields, not a new injection path.
- Frontend files (Phase 22-B).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check                 # → "no issues"
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run  # → "No changes detected"
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q                 # → all green
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_profile_prefs.py -q  # → new tests pass
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- Keep the resolution-order rule explicit in code comments — future workers will
  otherwise guess and override per-message with profile (a correctness bug).

---

## Phase 22-B — User preferences: frontend (Settings tab)

**Date:** 2026-08-18
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE — AI Settings tab (commit `f73f7c5`)
**Kind:** Frontend-only. Small.
**Depends on:** Phase 22-A (GET/PATCH /ai/profile/).

### Files to Read First
- `carbon-frontend/src/shell/AIWorkspace.jsx` — right activity bar tab registration
- `carbon-frontend/src/shell/AIUsageTab.jsx` — sibling fixed-tab pattern (Phase 21-B)
- `carbon-frontend/src/api/aiWorkspace.js` — add profile helpers
- `.ai-toolkit/shared/design-system.md`

### Files to Change
- `carbon-frontend/src/api/aiWorkspace.js` — `getProfile`, `patchProfile`
- `carbon-frontend/src/shell/AISettingsTab.jsx` (NEW)
- `carbon-frontend/src/shell/AIWorkspace.jsx` — register "Settings" fixed tab
- `carbon-frontend/src/__tests__/AISettingsTab.test.jsx` (NEW)

### Implementation
1. `AISettingsTab.jsx` (right activity bar): model default, temperature slider,
   auto-title toggle, memory toggle, usage-alert threshold.
2. Load via `GET /ai/profile/`, save via `PATCH`, optimistic UI.
3. Fixed-mode, id-based, keyboard-navigable tab (NEXTGEN §8.3). Theme tokens only (RULE_8).

### DO NOT TOUCH
- Backend files.
- The Usage tab (Phase 21-B) — sibling, not replacement.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/AISettingsTab.test.jsx   # → passes
npm run build
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- 22-A first. Settings lives beside Usage in the right bar — one "me + my AI" place.

---

## Phase 23-A — Memory & learnt facts: backend (read + forget + relationship)

**Date:** 2026-08-18
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE
**Kind:** Backend-only. Medium-large. **Do last.**
**Depends on:** Phase 19 (delete/forget), Phase 20-A (cost/model attribution), Phase 21-A (usage → relationship signals), Phase 22-A (memory_enabled gate).

### Files to Read First
- `backend/ai/engine/memory/` + `backend/ai/engine/knowledge_graph/` — where facts/episodes live
- `backend/ai/workspace_api.py` — where memory endpoints live
- `backend/ai/intelligence.py` — memory write gating (`memory_enabled`)
- `.ai-toolkit/shared/api-contract.md` + `data-layer.md`

### Files to Change
- `backend/ai/memory_api.py` (NEW) — facts/episodes/relationship endpoints
- `backend/ai/workspace_api.py` (or urls) — register routes
- `backend/ai/tests/test_memory_api.py` (NEW)

### Context
The AI writes to a KG/memory tier (learnt facts, preferences, trust signals) but
the user has no visibility into what the AI "knows" about them, and no way to
correct or forget it. Both a trust feature and a GDPR right-to-erasure requirement.

### Design decisions (deep)
- **Three views, one relationship model:** Memory (episodic entries) · Learnt
  (distilled facts/KG nodes + confidence) · You & AI (relationship summary).
- **Every fact is inspectable + forgettable.** Each learnt fact exposes its
  provenance (which conversation/turn produced it) and a **Forget** action that
  removes it from the KG (and, where derivable, its episodic source).
- **Relationship is computed, not stored.** Derive the summary on read from
  memory + usage + profile; don't persist a second copy.
- **Privacy-first.** Forget = hard delete of the fact node + cascade to derived
  facts, audited. Respect `memory_enabled=false` (Phase 22) by gating writes.

### Implementation
1. `GET /ai/memory/facts` (learnt facts + confidence + provenance),
   `GET /ai/memory/episodes` (raw memory), `GET /ai/memory/relationship`.
2. `DELETE /ai/memory/facts/{id}` (forget, with audit trail).
3. Audit log on every forget (who/when/what) — legal requirement.

### DO NOT TOUCH
- The KG/memory write path internals — this phase is read + forget only.
- Frontend files (Phase 23-B).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check                 # → "no issues"
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run  # → "No changes detected"
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q                 # → all green
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_memory_api.py -q   # → new tests pass
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- Forget must hard-delete + cascade + audit — soft-delete leaves a GDPR hole.
- 23-A must land before 23-B (endpoints first).

---

## Phase 23-B — Memory & learnt facts: frontend (three fixed tabs)

**Date:** 2026-08-18
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE
**Kind:** Frontend-only. Medium-large. **Do last.**
**Depends on:** Phase 23-A (endpoints).

### Files to Read First
- `carbon-frontend/src/shell/AIWorkspace.jsx` — right bar tab registration
- `carbon-frontend/src/shell/AIUsageTab.jsx` + `AISettingsTab.jsx` — sibling tab patterns
- `carbon-frontend/src/api/aiWorkspace.js` — add memory helpers
- `.ai-toolkit/shared/design-system.md`

### Files to Change
- `carbon-frontend/src/api/aiWorkspace.js` — `listFacts`, `listEpisodes`, `getRelationship`, `forgetFact`
- `carbon-frontend/src/shell/AIMemoryTab.jsx` (NEW)
- `carbon-frontend/src/shell/AILearntTab.jsx` (NEW)
- `carbon-frontend/src/shell/AIRelationshipTab.jsx` (NEW)
- `carbon-frontend/src/shell/AIWorkspace.jsx` — register three fixed tabs
- `carbon-frontend/src/__tests__/AIMemoryTabs.test.jsx` (NEW)

### Implementation
1. `AIMemoryTab.jsx`, `AILearntTab.jsx`, `AIRelationshipTab.jsx` (right bar,
   fixed mode, id-based, keyboard navigable).
2. Forget action per fact with confirm; relationship tab renders signals →
   summary (topics, preferences, trust) with an empty state when no data yet.
3. Theme tokens only (RULE_8).

### DO NOT TOUCH
- Backend files.
- Pair every relationship claim with a "why" and a "forget" affordance (trust/UX).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/AIMemoryTabs.test.jsx   # → passes
npm run build
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- Ship last. The relationship tab is the "empathy surface" — done wrong it reads
  as creepy. Always pair every claim with a "why" and a "forget" affordance.

---

## Phase 23-C — Copilot-style composer + collapsed sessions drawer + grouped Memory surface

**Date:** 2026-08-18
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE
**Kind:** Frontend-only. Small-medium UX polish.
**Depends on:** Phase 23-B (three memory tabs exist).

### Files to Read First
- `carbon-frontend/src/shell/AIInputBar.jsx` — composer (multiline behavior)
- `carbon-frontend/src/shell/AIWorkspace.jsx` — activity bar + drawer state
- `.ai-toolkit/shared/ux-patterns.md` — Copilot density + nav model rules

### Files to Change
- `carbon-frontend/src/shell/AIInputBar.jsx` — MODIFY (grow-to-fit + internal scroll)
- `carbon-frontend/src/shell/AIWorkspace.jsx` — MODIFY (drawer default, grouped Memory panel, 7-icon bar)
- `carbon-frontend/src/__tests__/AIWorkspace.shell.test.jsx` — MODIFY (drawer-open sync + grouped Memory tests)
- `carbon-frontend/src/__tests__/AIInputBar.growth.test.jsx` — ADD (growth behavior, 4 tests)

### Implementation
1. Composer grows with content up to ~55% of pane height (clamped 6–18 rows),
   then scrolls internally; Enter=send / Shift+Enter=newline preserved.
2. Sessions drawer starts collapsed; opens on demand from the activity bar.
3. Activity bar 9 → 7 icons: Memory/Learnt/Relationship consolidate under one
   Memory icon (Psychology) opening internal MUI `<Tabs>` Episodes/Facts/
   Relationship persisted via `carbon-ai-memory-tab` (RULE_17).

### DO NOT TOUCH
- Backend files.
- The three memory tab components themselves (AIMemoryTab/AILearntTab/AIRelationshipTab).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/AIMemoryTabs.test.jsx src/__tests__/AIWorkspace.shell.test.jsx \
  src/__tests__/AIInputBar.growth.test.jsx src/__tests__/AIInputBar.mode.test.jsx \
  src/__tests__/AIInputBar.mentions.test.jsx src/__tests__/AIInputBar.entityResolve.test.jsx
npm run build
```

### Output contract
Append to `TASK-RESULTS.md`.

---

## Phase 24 — Adaptive Learning DQ Core (PROPOSAL — pending owner ratification)

**Status:** ⚠️ PROPOSAL, NOT RATIFIED. This is a pointer, not active work. Do
not dispatch a worker until the owner ratifies (or reorders/rejects) it. The
proposal's own phase sequence lives in `docs/DESIGN-ADAPTIVE-LEARNING-DQ-CORE.md`
and is owned by the other Master session — keep the two from forking by *not*
copying its G–K phase details here.

**Proposal sequence (for reference only):** Phase A (deterministic substrate +
eval harness) → Phase B (KG + memory substrate) → emissions (first Category B
domain op) → **admin/ops cluster G–K** (G domain registration, H access/CBAC
assistance, I lineage & impact, J governance & policy, K MDM & data product) →
remaining domains (mdm, data product) via the same `DomainAIOperations` ABC.

**Hard constraints (non-negotiable, already in the proposal §6):**
- Admin surfaces are **suggest/draft only** — never auto-mutate grants, users,
  groups, policies, or master records (`requires_confirmation`, RULE_21).
- **CBAC stays a correctness rail** — making it a coworker *surface* never
  weakens the request/context/write enforcement boundaries (ADR-0007).
- No new Django apps (ADR-0008); no learning inside the engine (RULE_6).

**On ratification:** the owner's verdict ("ratify / reorder / reject") triggers
the real phase split — then I fold the ratified subset into this file as proper
Phase 24+ entries with full `Files to Read/Change`, `Implementation`, and
verification gates, and hand out backend-worker activation prompts. Until then,
this pointer is the single source of truth so the two plans cannot silently
diverge.

---

## AI WORKSTATION TRACK

Turns the Pulse AI Workspace into a *workstation*: run agent actions / MCP
commands / tools with verbosity + clean abort, manage conversation context
(clear / restore / checkpoint / fork), accordion past chats, and scroll large
content. Design + research rationale: `docs/DESIGN_AI_WORKSTATION.md`.

Dispatch order: **W1-A → W2-A** (execution surface) and **W1-B → W2-C**
(context lifecycle) are two independent chains; **W2-B** is standalone polish.
Backend and frontend never share a phase.

---

### Phase W1-A — Agent/Tool/MCP execution seam + streamed events + verbosity + abort

**Date:** 2026-08-19
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE — execution seam + streamed events (commit `866e3a8`)
**Kind:** Backend-only. Medium.
**Depends on:** chat SSE (`dispatch_task_stream` + `workspace_api` messages/stream) and `generation_registry`.

### Files to Read First
- `backend/ai/engine/agent/executor.py` — `HostAPIExecutor` (confirm/decline/direct call; RULE_21 gating)
- `backend/ai/engine/agent/registry.py` + `tools.py` + `mcp_client.py` — agent/tool/MCP catalogs
- `backend/ai/generation_registry.py` — per-conversation `threading.Event` (abort primitive)
- `backend/ai/engine_runtime.py` — `dispatch_task_stream` bridge (chunk/done/error frames)
- `backend/ai/workspace_api.py` — SSE `messages/stream` action (frame shape)
- `backend/ai/models/core.py:188 ToolExecution` — durable tool-execution log

### Files to Change
- `backend/ai/engine_runtime.py` — MODIFY: add an agent/tool run path that yields **clustered** frames keyed by `turn_id`/`step_id` — `turn_start` → (`tool_start`/`tool_arg`/`tool_result`/`tool_end`)* → `turn_end` — honours `verbosity`, and checks `generation_registry.is_cancelled()` between steps
- `backend/ai/providers/pulse.py` — MODIFY: expose a `run_tool_stream` (or extend `chat_stream`) passthrough
- `backend/ai/intelligence.py` — MODIFY: `run_agent_action_stream(...)` generator + guard chain (scope/mutation/rate)
- `backend/ai/workspace_api.py` — MODIFY: new action under the existing conversation router, e.g. `POST .../conversations/{id}/actions/stream/` (SSE)
- `backend/ai/tests/test_agent_action_stream.py` — ADD

### Implementation
1. **Clustered frame protocol** (see `docs/DESIGN_AI_WORKSTATION.md` §2.5):
   every action run opens with `turn_start {turn_id,label,verbosity}`, then for
   each step emits `tool_start {turn_id,step_id,tool,category}` → optional
   `tool_arg {step_id,args}` → `tool_result {step_id,result}` → `tool_end
   {step_id,status}`, and closes with `turn_end {turn_id,status,summary}`.
   `category` ∈ `agent|mcp|tool`. Frontend nests frames under the ids.
2. Reuse `generation_registry.start/cancel/is_cancelled` for the action run.
   A cancel between tool steps must emit `tool_end {status:"stopped"}` then a
   `turn_end {status:"stopped"}` (never `error`, never leaves the conversation
   in `working`).
3. `verbosity` ∈ {`concise`, `full`}: `concise` emits `tool_start`+`tool_end`
   (name + status) only; `full` additionally emits `tool_arg` + `tool_result`
   payloads (redacted via `_redact_secrets`).
4. Every step writes a `ToolExecution` row (already exists) — status
   `running` → `completed|failed|stopped`. No auto-mutation: host-mutating
   actions stay `requires_confirmation=True` (RULE_21).
5. Agent/tool/MCP catalog reads must be read-only GET endpoints under
   `/carbon-api/ai/…`, CBAC `ai:view_console`.

### DO NOT TOUCH
- Frontend files.
- `engine/agent/executor.py` confirmation semantics (call them, don't fork).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- Abort correctness is the acceptance bar: `cancel()` mid-run must yield a
  `stopped` final frame, a completed `ToolExecution(status="stopped")`, and no
  stuck `working` message. Test this explicitly.

---

### Phase W1-B — Conversation checkpoint / restore / fork / clear-context (backend)

**Date:** 2026-08-19
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE — checkpoint/restore/fork/clear + `ConversationCheckpoint` (commit `866e3a8`)
**Kind:** Backend-only. Medium.
**Depends on:** W1-A (fork reuses the abort/stop seam).

### Files to Read First
- `backend/ai/workspace_api.py` — conversation router (where actions mount)
- `backend/ai/context_assembler.py` — `assemble_context` (the snapshot bundle)
- `backend/ai/models/workspace.py` — `AIConversation` / `AIMessage` (`context_snapshot_json`)
- `backend/ai/intelligence.py` — `send_message_stream` (how context is built/injected)

### Files to Change
- `backend/ai/models/workspace.py` — ADD `ConversationCheckpoint` (or core.py) + migration
- `backend/ai/intelligence.py` — MODIFY: `checkpoint_conversation`, `restore_conversation`, `fork_conversation`, `clear_context`
- `backend/ai/workspace_api.py` — MODIFY: `checkpoint/`, `restore/`, `fork/`, `clear-context/` actions
- `backend/ai/serializers.py` — MODIFY: checkpoint serializer
- `backend/ai/tests/test_context_lifecycle.py` — ADD

### Implementation
1. `checkpoint` snapshots the current context bundle (messages + budget +
   `kg_entities` + memory) under a user name + optional note; idempotent
   (same name → overwrite, or reject if `--strict`).
2. `restore` re-seeds a conversation's working context from a checkpoint;
   it does NOT overwrite the durable message log.
3. `fork` clones a conversation (title `"{old} — fork"`) seeded from a
   checkpoint at a chosen message boundary — new conversation id.
4. `clear-context` resets the *working* context (history/summary/KG/memory
   injection) without deleting the conversation row or learned facts.
5. All mutating actions require `ai:manage_console`; reads `ai:view_console`.

### DO NOT TOUCH
- Frontend files.
- `learning.py` / durable memory writes (clearing context must not trigger forgetting).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- Fork must produce a NEW conversation id (no aliasing the old row). Clear
  must leave `context_snapshot_json` on existing messages untouched.

---

### Phase W2-A — Agent/MCP/Tools/Logs surface + execution panel + verbosity + abort

**Date:** 2026-08-19
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE — `AIAgentPanel` + `AIActionRunner` (commit `866e3a8`)
**Kind:** Frontend-only. Medium-large.
**Depends on:** W1-A (execution SSE + catalog endpoints).

### Files to Read First
- `carbon-frontend/src/shell/AIWorkspace.jsx` — activity bar + `activePanel` branches
- `carbon-frontend/src/api/aiWorkspace.js` — `streamJsonPost` (reuse for action frames)
- `carbon-frontend/src/shell/AIMemoryTab.jsx` — grouped-surface internal-Tabs precedent (RULE_17)
- `.ai-toolkit/shared/ux-patterns.md` + `docs/DESIGN_AI_WORKSTATION.md` §2

### Files to Change
- `carbon-frontend/src/shell/AIAgentPanel.jsx` — ADD (Agents/MCP/Tools/Logs internal `<Tabs>`, persisted `carbon-ai-agent-tab`)
- `carbon-frontend/src/shell/AIActionRunner.jsx` — ADD (clustered streaming timeline: turn cluster → collapsible step cards, verbosity Select, Stop button)
- `carbon-frontend/src/api/aiWorkspace.js` — MODIFY: `runActionStream(...)` wrapper
- `carbon-frontend/src/shell/AIWorkspace.jsx` — MODIFY: one "Agent" activity-bar icon (hub icon) opening `AIAgentPanel`; do NOT add 4 flat icons
- `carbon-frontend/src/__tests__/AIAgentPanel.test.jsx` — ADD

### Implementation
1. **One icon, four tabs** (RULE_17): Agents (list + select + run) / MCP
   (servers + tools, read-only from catalog) / Tools (built-in tools) / Logs
   (`ToolExecution` + `LLMCallLog` timeline, expandable JSON).
2. **Clustered timeline** (RULE: no flat wall — see design §2.5): frames are
   nested by `turn_id`/`step_id`. A *turn cluster* renders as one collapsible
   group header — "Working…" → "Finished · N tools" (or "Stopped by you") —
   that collapses the whole group to one line. Inside, each step is its own
   collapsible card (status icon + tool name + status chip; expandable args /
   result body). Append frames incrementally without re-rendering the whole
   transcript. `verbosity` (Concise/Full) controls default expansion only —
   every card stays individually toggleable.
3. **Stop** button → `stopGeneration`; run flips to `stopped`, shows
   "Stopped by you" *inside the turn/step card* (not an error banner), and
   re-enables the composer.
4. Host-mutating actions render a confirm gate (RULE_21), never a silent run.
5. Failed/stopped step details live inside the card body; wide output
   (JSON/terminal/tables) scrolls on X inside its card; theme tokens only
   (RULE_8). Collapse state is per-run in-memory (not persisted).

### DO NOT TOUCH
- Backend files.
- `AIConversationView.jsx` / `AIMessageBubble.jsx` chat rendering (separate surface).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/AIAgentPanel.test.jsx src/__tests__/AIWorkspace.shell.test.jsx
npm run build
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- Copy must be outcomes, not internals (RULE_23): "Running…", "Finished",
  "Stopped" — never engine class names. Verify the stop-path test exists.
- Acceptance for clustering: a 3-tool run collapses to a single
  "Finished · 3 tools" summary line, each tool toggles independently, and a
  stopped run shows "Stopped by you" inside the card — never a stuck working
  spinner, never a red banner.

---

### Phase W2-B — Past-chat accordion + scroll containment

**Date:** 2026-08-19
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE — accordion groups + scroll containment (commit `866e3a8`)
**Kind:** Frontend-only. Small-medium.
**Depends on:** (independent).

### Files to Read First
- `carbon-frontend/src/shell/AIConversationTabs.jsx` — grouped session list (Today/7d/Older)
- `carbon-frontend/src/shell/AIWorkspace.jsx` — drawer + pane layout
- `carbon-frontend/src/shell/LongContent.jsx` — existing long-output container

### Files to Change
- `carbon-frontend/src/shell/AIConversationTabs.jsx` — MODIFY: collapsible accordion groups (header toggle, per-item inline expand)
- `carbon-frontend/src/shell/AIConversationView.jsx` — MODIFY: message list gets its own vertical scroll container (independent of header/input)
- `carbon-frontend/src/shell/LongContent.jsx` — MODIFY: `overflow:auto` X for wide JSON/terminal/table content
- `carbon-frontend/src/__tests__/AIConversationTabs.accordion.test.jsx` — ADD

### Implementation
1. Group header toggles collapse/expand; state persisted via localStorage
   (`carbon-ai-accordion-{group}`); long lists virtualized.
2. Message list = one vertical scroll region; input bar + header stay fixed.
3. Wide content scrolls horizontally inside its card — never widen the page.

### DO NOT TOUCH
- Backend files.
- `AIInputBar.jsx` growth behaviour (Phase 23-C).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/AIConversationTabs.accordion.test.jsx
npm run build
```

### Output contract
Append to `TASK-RESULTS.md`.

---

### Phase W2-C — Context clear/restore + checkpoint/fork UI

**Date:** 2026-08-19
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE — `AIContextMenu` + checkpoint/fork UI (commit `d511797`)
**Kind:** Frontend-only. Medium.
**Depends on:** W1-B (checkpoint/restore/fork/clear endpoints).

### Files to Read First
- `carbon-frontend/src/shell/AIWorkspaceHeader.jsx` — header actions (where Clear/Restore/Fork buttons mount)
- `carbon-frontend/src/api/aiWorkspace.js` — conversation API wrappers
- `carbon-frontend/src/shell/AIContextPanel.jsx` — context telemetry surface
- `docs/DESIGN_AI_WORKSTATION.md` §2.3

### Files to Change
- `carbon-frontend/src/api/aiWorkspace.js` — MODIFY: `checkpointConversation`/`restoreConversation`/`forkConversation`/`clearContext`
- `carbon-frontend/src/shell/AIContextMenu.jsx` — ADD (checkpoint picker + clear/fork confirm)
- `carbon-frontend/src/shell/AIWorkspaceHeader.jsx` — MODIFY: mount `AIContextMenu` (kebab)
- `carbon-frontend/src/__tests__/AIContextMenu.test.jsx` — ADD

### Implementation
1. Header kebab → Context: **Clear context** (confirm), **Save checkpoint**
   (name + note), **Restore** (picker), **Fork from here**.
2. Clear/fork show a confirm dialog (destructive-ish); fork navigates to the
   new conversation; restore refreshes the context panel telemetry.
3. Empty/error/loading 4-state on the checkpoint picker; theme tokens only.

### DO NOT TOUCH
- Backend files.
- `AIConversationView.jsx` message stream.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/AIContextMenu.test.jsx
npm run build
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- Fork/clear never delete the durable conversation; make that visible in copy.

---

### Phase W3-A — Agentic Task Orchestration: backend (plan → approve → execute → audit)

**Date:** 2026-08-20
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE — verified by backend-worker (gates re-run by Master Architect); last mile `7f4123c` plan_task chat bridge (49 tests)
**Kind:** Backend-only. Large.
**Depends on:** W1-A (execution seam + streamed events), W2-A (confirm/decline/stop wired).

### Files to Read First
- `backend/ai/engine/cognition/plan/planner.py` — `Plan`/`PlanStep` decomposition (already built)
- `backend/ai/engine/cognition/plan/loop.py` — `ReActLoop` (draft → critic → execute → observe, consent gates, ≤2 replans)
- `backend/ai/engine/core/models.py` — `Run`/`RunStep`/`ops_runs` provenance ledger + `AuditLog` (already built)
- `backend/ai/engine/cognition/turn/runner.py` — `AGENT_ORCHESTRATOR_ENABLED` (P3.2 fan-out gate) + `KG_MULTI_STEP_ENABLED` (PR-20 ReAct trigger)
- `backend/ai/plugins/` — `ToolPlugin`/`WorkflowPlugin` registry (Sprint 12) — the tool surface steps execute through
- `backend/ai/workspace_api.py` — `run_action_stream`, `confirm_tool_execution`, `decline_tool_execution`, `stop_generation` (seam to reuse)
- `.ai-toolkit/shared/api-contract.md` + `cbac.md` + `data-layer.md`

### Files to Change
- `backend/ai/plans_api.py` (NEW) — task orchestration viewset (see Implementation)
- `backend/ai/plans_service.py` (NEW) — plan lifecycle: create from brief → run via `ReActLoop` → persist `Run`/`RunStep` rows → ledger snapshot
- `backend/ai/urls.py` (MODIFY) — route `plans/…` endpoints
- `backend/ai/tests/test_plans.py` (NEW) — ≥8 tests

### Context
The engine can already decompose a task, execute it step-by-step with critic
gating + replans, persist a provenance ledger, and gate every mutation behind
user confirmation — but it only fires **reactively inside chat turns**
(`AGENT_ORCHESTRATOR_ENABLED`, `KG_MULTI_STEP_ENABLED`) and there is **no
user-initiated task surface**: no `POST /plans/` that takes a task brief, no
reviewable plan payload, no per-task audit read. W3-A exposes the built
machinery as a first-class, auditable task product without touching the engine.

### Design decisions (deep)
- **Plan is reviewable before execution.** `POST /ai/plans/` `{brief, tool_ids?}` →
  planner decomposes → returns `plan` (steps: intent, tool, dry-run preview) with
  status `pending_approval`. Nothing executes until approved — RULE_21.
- **Two-phase consent.** Step-level `confirm_tool_execution` reuses the W1-A/W2-A
  seam for host-mutating tools; the plan-level approve gate is a separate
  explicit call so a multi-step task can be reviewed as a whole, then executed.
- **Execution streams, audit is durable.** `POST /ai/plans/{id}/run/` streams
  per-step events (same `onFrame` protocol as `run_action_stream`); every step
  writes a `RunStep` row and the final `Run` row carries replans_used,
  confirmations_required, latency, tokens, and provenance — read via
  `GET /ai/plans/{id}/ledger/`. Parallel steps use the existing P3.2 fan-out gate.
- **No new engine state.** Plans reuse `Run`/`RunStep`; the ledger stays the
  single audit source. Fail-visible contract holds: step failure → `failed`
  status + reason, never a fake success.

### Implementation
1. `PlansViewSet` (CBAC-scoped, DRF):
   - `POST /ai/plans/` → create plan `pending_approval` (planner; no execution)
   - `GET /ai/plans/` + `GET /ai/plans/{id}/` → list/detail (plan + steps + status)
   - `POST /ai/plans/{id}/approve/` → `approved` (returns run id)
   - `POST /ai/plans/{id}/run/` → SSE stream of per-step events (reuses
     `run_action_stream` frame protocol: `step_start/step_result/step_confirm/step_end/done`)
   - `POST /ai/plans/{id}/steps/{step_id}/confirm|decline/` → step consent
   - `POST /ai/plans/{id}/stop/` → abort remaining steps (status `stopped`)
   - `GET /ai/plans/{id}/ledger/` → audit: steps, replans, confirmations,
     latency, tokens, provenance, actor
2. `PlansService.run_plan`: feed the approved plan into `ReActLoop`
   (draft → critic → execute → observe per step; ≤2 replans; consent gates);
   persist `Run`/`RunStep` rows; finalize ledger.
3. Wire `plans_api.py` into `backend/ai/urls.py`; GuardChain applies on every call.

### DO NOT TOUCH
- `backend/ai/engine/` — the engine (planner/ReActLoop/models) is already built; W3-A only calls it.
- Frontend files (Phase W3-B owns the UI).
- `AGENT_ORCHESTRATOR_ENABLED` / `KG_MULTI_STEP_ENABLED` default behavior in chat.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check                 # → "no issues"
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run  # → "No changes detected" (reuses Run/RunStep)
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_plans.py -q        # → new tests pass
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q                           # → all green
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- W3-A is the product wrapper, not an engine rewrite — evidence: `ReActLoop`,
  `Plan`/`PlanStep`, `Run`/`RunStep`/`ops_runs` already exist and persist.
- Approve-then-run keeps RULE_21 (no silent mutation); parallel fan-out stays
  behind the P3.2 gate so budgets are enforced.

---

### Phase W3-B — Agentic Task Orchestration: frontend (task panel + plan review + audit)

**Date:** 2026-08-20
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE — verified by frontend-worker (gates re-run by Master Architect)
**Kind:** Frontend-only. Medium-large.
**Depends on:** W3-A (plans endpoints), W2-A (`AIActionRunner` cluster/confirm/stop patterns).

### Files to Read First
- `carbon-frontend/src/shell/AIAgentPanel.jsx` + `AIActionRunner.jsx` — reuse the run-card/step-card cluster, verbosity, confirm/decline/stop
- `carbon-frontend/src/api/aiWorkspace.js` — add plans wrappers beside `runActionStream`
- `docs/DESIGN_AI_WORKSTATION.md` §2.4 (accordion/scroll) + §2.5 (execution seam)
- `carbon-frontend/src/shell/AIWorkspace.jsx` — where the activity-bar task entry mounts
- `.ai-toolkit/shared/design-system.md` (RULE_8 tokens, compact density)

### Files to Change
- `carbon-frontend/src/api/aiWorkspace.js` — MODIFY: `createPlan`, `getPlan`, `listPlans`, `approvePlan`, `runPlanStream`, `confirmPlanStep`, `declinePlanStep`, `stopPlan`, `getPlanLedger`
- `carbon-frontend/src/shell/AITaskPanel.jsx` — ADD (activity-bar "Tasks" entry; tabbed: Task list / Run detail)
- `carbon-frontend/src/shell/AITaskPlanCard.jsx` — ADD (reviewable plan: step stepper with dry-run previews + Approve / Decline)
- `carbon-frontend/src/shell/AITaskAuditCard.jsx` — ADD (ledger per task: steps, replans, confirmations, latency, tokens, provenance)
- `carbon-frontend/src/shell/AIWorkspace.jsx` — MODIFY (activity-bar entry + render branch)
- `carbon-frontend/src/__tests__/AITaskPanel.test.jsx` — ADD

### Implementation
1. **Plan review:** create from a brief (task input in the panel); render plan
   steps as a stepper with status chips + dry-run previews; **Approve / Decline**
   gate before any execution (RULE_21).
2. **Run detail:** stream per-step events into the `AIActionRunner`-style
   clustered timeline; step confirm/decline + Stop reuse the W2-A handlers.
3. **Audit:** `AITaskAuditCard` reads `getPlanLedger` — replans used,
   confirmations required, per-step latency/tokens, provenance, actor; status
   filter chips on the task list (pending / running / completed / failed / stopped).
4. Theme tokens only; compact density; empty/loading/error 4-states everywhere.

### DO NOT TOUCH
- Backend files.
- `AIInputBar.jsx` growth behaviour.
- Existing `AIActionRunner.jsx` — extend patterns, don't refactor the W2-A component.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/AITaskPanel.test.jsx   # → passes
npm run build
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- This is the missing product layer: the engine already plans/executes/audits —
  W3-B makes it user-initiated, reviewable, and observable end-to-end.
- W3-A before W3-B; the task list + audit views are the acceptance proof.

---

### Phase W3-C — Plan lifecycle: edit / pause / resume / fork (backend)

**Date:** 2026-08-20
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE — ACCEPTED (`5e8847c`, 33 tests)
**Spec:** `docs/DESIGN-AGENT-CATALOG.md` §4 (W3-C)
**Kind:** Backend-only. Medium.
**Depends on:** W3-A (plan lifecycle) — ✅ DONE.

### Files to Read First
- `backend/ai/plans_service.py` — existing statuses + `_RUNNABLE_STATUSES` + `run_plan_stream`
- `backend/ai/plans_api.py` — existing ViewSet route map
- `backend/ai/tests/test_plans.py` — existing coverage to extend
- `docs/DESIGN-AGENT-CATALOG.md` §2 invariants + §4 W3-C
- `.ai-toolkit/shared/base-rules.md` + `project.config.md` (HARD RULES)

### Files to Change
- `backend/ai/plans_service.py` — MODIFY: `edit_plan` (replan with diff), `pause_plan`, `resume_plan`, `fork_plan`, `edit_step`
- `backend/ai/plans_api.py` — MODIFY: `PATCH /plans/{id}/`, `PATCH /plans/{id}/steps/{step_id}/`, `POST /plans/{id}/pause/`, `POST /plans/{id}/resume/`, `POST /plans/{id}/fork/`
- `backend/ai/tests/test_plans.py` — EXTEND: edit-diff, pause/resume, fork tests

### Implementation
1. **Edit brief → replan with diff.** `PATCH /plans/{id}/` accepts a new `brief`
   (+ optional `step_deltas`). Re-run `SkillAwarePlanner.decompose()`, return a
   **diff** (`added`/`removed`/`changed` steps). If plan is `approved`/`running`/
   `paused`, the diff returns as a review payload and the plan drops to
   `pending_approval` — user must re-approve (RULE_21, no auto-mutation).
2. **Per-step edit.** `PATCH /plans/{id}/steps/{step_id}/` edits `title` /
   `instructions` / `depends_on` with the same diff-review rule.
3. **Pause.** `POST /plans/{id}/pause/` only from `running` → `STATUS_PAUSED`.
   Must not corrupt steps already `awaiting_approval` (consent pause is separate).
4. **Resume.** `POST /plans/{id}/resume/` from `paused`/`approved` re-enters
   `run_plan_stream` with `resume_run_id=plan_id` (reuses `_RUNNABLE_STATUSES`).
5. **Fork.** `POST /plans/{id}/fork/` clones plan JSON + brief into a new `Run`
   row (`forked_from`), status `pending_approval`. Copy, not a link.

### DO NOT TOUCH
- `backend/ai/engine/**` — call seams only, never reimplement.
- No new migrations (`makemigrations --check --dry-run` stays clean).
- Frontend files.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_plans.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- W3-C is the foundation W3-E (resume/replay) builds on — dispatch before/with W3-D.

---

### Phase W3-D — Unified Agent Catalog: backend CRUD + federated discovery

**Date:** 2026-08-20
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE — ACCEPTED (`eb2e97a`, 15 tests)
**Spec:** `docs/DESIGN-AGENT-CATALOG.md` §4 (W3-D)
**Kind:** Backend-only. Medium.
**Depends on:** W3-A (agent engine + `AgentRegistry` already exist).

### Files to Read First
- `backend/ai/engine/agent/registry.py` — `AgentRegistry.register_agent/get_agent/list_agents/remove_agent`
- `backend/ai/engine/core/models.py` — `Agent`, `AgentHandoff`, `Skill`, `SkillAdmissionLog`, `AGENT_ROLES`
- `backend/ai/engine/agent/plugins.py` — `ToolPlugin`/`WorkflowPlugin` discovery seam
- `backend/ai/plans_api.py` — CBAC/owner-scoping pattern to mirror
- `docs/DESIGN-AGENT-CATALOG.md` §2 + §4 W3-D

### Files to Change
- `backend/ai/catalog_service.py` — ADD: read-mostly catalog queries + topology + federated index
- `backend/ai/catalog_api.py` — ADD: `GET /catalog/agents/`, `GET /catalog/agents/{id}/`, `GET /catalog/topology/`, `POST/PATCH/DELETE /catalog/agents/{id}/`, `GET /catalog/skills/`
- `backend/ai/urls.py` — MODIFY: route `catalog/` → `catalog_api`
- `backend/ai/tests/test_catalog.py` — ADD

### Implementation
1. **List/detail.** `GET /catalog/agents/` returns roles with declared handoff
   edges + skills; `GET /catalog/agents/{id}/` returns one agent (incoming/
   outgoing handoffs, admitted skills, last admission log).
2. **Topology.** `GET /catalog/topology/` returns the declared graph as
   `{nodes:[], edges:[]}` (ADR-001 declared edges only) — feeds W3-G (Admin).
3. **CRUD (admin-gated).** `POST/PATCH/DELETE /catalog/agents/{id}/` map to
   `register_agent`/`remove_agent`; explicit, RULE_21.
4. **Federated index.** Build a request-time index merging `AgentRegistry.
   list_agents` (DB) with `ToolPlugin`/`WorkflowPlugin` discovery from
   `plugins.py`. Read-only merge; DB stays source of truth.
5. CBAC: catalog writes owner/role-scoped; reads follow the plan CBAC pattern.

### DO NOT TOUCH
- `backend/ai/engine/**` — read seams only.
- No new migrations.
- Frontend files.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_catalog.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- W3-D is independent of W3-C — dispatch in parallel.
- W3-D is **Admin**-surface (manage & observe). Its UI lands in W3-G by upgrading
  the existing `AgentsPanel.jsx` + `SkillsPanel.jsx` — NOT the Workspace.

---

### Phase W3-E — Durable execution: crash-resume / replay / timeline (backend)

**Date:** 2026-08-20
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE — ACCEPTED (`42bce5c`, 22 tests)
**Spec:** `docs/DESIGN-AGENT-CATALOG.md` §4 (W3-E)
**Kind:** Backend-only. Medium.
**Depends on:** W3-C (pause/resume already exist there).

### Files to Read First
- `backend/ai/plans_service.py` — `run_plan_stream`, status reconciliation
- `backend/ai/engine/core/models.py` — `Run`, `RunStep`, `Trajectory`
- `backend/ai/observability_api.py` — existing observability surface
- `docs/DESIGN-AGENT-CATALOG.md` §2 + §4 W3-E

### Files to Change
- `backend/ai/plans_service.py` — MODIFY: crash-safe `resume`, `replay`, `timeline`
- `backend/ai/plans_api.py` — MODIFY: `POST /plans/{id}/replay/`, `GET /plans/{id}/timeline/`
- `backend/ai/observability_api.py` — EXTEND: `GET /runs/` (run list)
- `backend/ai/tests/test_plans.py` — EXTEND: resume-reconcile, replay, timeline

### Implementation
1. **Crash-safe resume.** On `resume`, reconcile `RunStep` rows: mark stale
   `running`/`awaiting_approval` steps correctly; skip already-completed steps;
   re-enter via `resume_run_id=plan_id`.
2. **Replay (read-only).** `POST /plans/{id}/replay/` reconstructs a deterministic
   timeline from `RunStep` + `Trajectory` — never re-executes. Returns
   `{step, status, started_at, finished_at, artifacts}`.
3. **Timeline.** `GET /plans/{id}/timeline/` returns Gantt-ready ranges per step.
4. **Run list.** `GET /runs/` lists runs across plans (resume/replay entry points).

### DO NOT TOUCH
- `backend/ai/engine/**`.
- No new migrations.
- Frontend files.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_plans.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- W3-E is **Admin**-surface observability (cross-user run ledger/timeline).
  Feeds W3-G (Admin timeline view), not the Workspace.

---

### Phase W3-F — AI Workspace: plan controls + live plan DAG (frontend, `shell/`)

**Date:** 2026-08-20
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE — ACCEPTED (`b630228`, 44 tests + build green; last mile `91e172f` Chat→Tasks open_panel jump)
**Spec:** `docs/DESIGN-AGENT-CATALOG.md` §4 (W3-F)
**Kind:** Frontend-only (Workspace surface). Medium.
**Depends on:** W3-C (edit/pause/resume/fork endpoints).

### Files to Read First
- `carbon-frontend/src/pages/admin/ai/KnowledgeGraphPanel.jsx` — d3-force + drag/zoom/pan + hover + legend source to extract
- `carbon-frontend/src/shell/AITaskPlanCard.jsx` + `AITaskPanel.jsx` — where plan controls + preview mount
- `carbon-frontend/src/shell/MarkdownMessage.jsx` — lazy Mermaid block rendering
- `carbon-frontend/src/api/aiWorkspace.js` — plans wrappers
- `docs/DESIGN-AGENT-CATALOG.md` §2 + §4 W3-F + `.ai-toolkit/shared/design-system.md` (RULE_8)

### Files to Change
- `carbon-frontend/src/components/graph/ForceGraph.jsx` — ADD (extract shared d3 core from `KnowledgeGraphPanel`)
- `carbon-frontend/src/components/graph/PlanDagGraph.jsx` — ADD (nodes=steps, edges=`depends_on`, status-colored)
- `carbon-frontend/src/components/graph/PlanMermaidPreview.jsx` — ADD (Mermaid `graph` preview)
- `carbon-frontend/src/shell/AITaskPlanCard.jsx` — MODIFY (embed `PlanMermaidPreview` + `PlanDagGraph`; add edit/pause/resume/fork controls with diff-review)
- `carbon-frontend/src/shell/AITaskPanel.jsx` — MODIFY (wire W3-C controls)
- `carbon-frontend/src/__tests__/` workspace graph specs — ADD

### Implementation
1. **Extract `ForceGraph.jsx`** from `KnowledgeGraphPanel.jsx` — reusable d3-force
   SVG with drag/zoom/pan, hover tooltip, click-to-inspect, legend. No new deps.
   (Shared primitive — the Admin surface reuses it in W3-G.)
2. **Plan edit/pause/resume/fork controls** wired to W3-C endpoints; show the
   `PATCH /plans/{id}/` diff-review gate before re-approve (RULE_21).
3. **Plan DAG live** — nodes=steps, edges=`depends_on`, node color=status; polls
   the *current user's* plan during a run.
4. **Mermaid preview** — `graph` DAG for the review card (reuses lazy mermaid).
5. Theme tokens only (RULE_8); Workspace surface only (`shell/`).

### DO NOT TOUCH
- Backend files.
- `KnowledgeGraphPanel.jsx` public behaviour — extract, don't regress.
- Admin surface (`src/pages/admin/ai/**`) — that is W3-G.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/   # workspace graph specs pass
npm run build
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- W3-F is the **Workspace (engage)** acceptance proof: a user edits/pauses/fork
  their own plan and watches its live DAG. No admin concerns here.

---

### Phase W3-G — AI Admin: catalog + topology + run timeline (frontend, `admin/ai/`)

**Date:** 2026-08-20
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE — ACCEPTED (`7d05993`, 34 tests + build green)
**Spec:** `docs/DESIGN-AGENT-CATALOG.md` §4 (W3-G)
**Kind:** Frontend-only (Admin surface). Medium-large.
**Depends on:** W3-D (catalog/topology), W3-E (timeline).

### Files to Read First
- `carbon-frontend/src/pages/admin/ai/AgentsPanel.jsx` + `SkillsPanel.jsx` — thin `PulseDataPanel` wrappers to upgrade
- `carbon-frontend/src/pages/admin/ai/KnowledgeGraphPanel.jsx` — d3 source (already extracted to `ForceGraph.jsx` in W3-F)
- `carbon-frontend/src/pages/admin/ai/PulseDataPanel.jsx` — existing data-panel pattern
- `carbon-frontend/src/api/aiPulse.js` — existing pulse read API wrappers
- `docs/DESIGN-AGENT-CATALOG.md` §2 + §4 W3-G + `.ai-toolkit/shared/design-system.md` (RULE_8)

### Files to Change
- `carbon-frontend/src/pages/admin/ai/AgentsPanel.jsx` — UPGRADE (real read/write catalog: table + detail drawer with handoff topology; admin-gated create/edit/remove, RULE_21)
- `carbon-frontend/src/pages/admin/ai/SkillsPanel.jsx` — UPGRADE (skill catalog + admission status)
- `carbon-frontend/src/components/graph/AgentTopologyGraph.jsx` — ADD (agents + declared handoffs from `GET /catalog/topology/`)
- `carbon-frontend/src/components/graph/RunTimeline.jsx` — ADD (Gantt from `GET /plans/{id}/timeline/` + `GET /runs/`)
- `carbon-frontend/src/__tests__/` admin graph specs — ADD

### Implementation
1. **Catalog CRUD UI** — upgrade `AgentsPanel.jsx` + `SkillsPanel.jsx` from thin
   wrappers to a real table + detail drawer: agent role, edges, skills, status;
   admin-gated create/edit/remove (RULE_21).
2. **Agent topology** — renders `GET /catalog/topology/` — the system's declared
   graph (ADR-001).
3. **Run timeline** — Gantt from `GET /plans/{id}/timeline/` + `GET /runs/` —
   cross-user run observation for admins.
4. Theme tokens only (RULE_8); Admin surface only (`pages/admin/ai/`).

### DO NOT TOUCH
- Backend files.
- Workspace surface (`src/shell/**`) — that is W3-F.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/   # admin graph specs pass
npm run build
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- W3-G is the **Admin (manage & observe)** acceptance proof: admins CRUD agents,
  inspect the declared topology, and review cross-user run timelines.
- Do NOT mingled with W3-F (Workspace).

---

## AGENTIC WORKFLOW COMPLETION TRACK (W4)

The W1–W3 work built the *surface* (plans, panels, audit). W4 completes the
*live agentic loop* end-to-end. Root-cause research identified **5 surgical
disconnects** between the Carbon-owned product wrapper and the in-process
engine seams:

1. **LLM decompose unreachable** — `plans_service.py:_decompose` builds
   `SkillAwarePlanner(model=…)` with no `llm_client`; `planner.decompose()`
   guards the LLM fallback on `client is not None`, so every plan collapses to
   `single_step`.
2. **Draft never gets tools** — `loop.py:_execute_step` calls `dw.draft(…)`
   without `tools=`, so the planner can never emit `tool_calls`.
3. **Execute never gets tool_calls** — `_execute_step` calls
   `ex.execute(draft.text, stream_callback, progress_callback)` — *positional
   mis-argument* (callbacks land in `tool_calls`/`stream_callback` slots) and
   `tool_calls` is never passed.
4. **Consent gate unreachable** — consequence of 2+3 (`result.tool_output` is
   always `None` because no tool ever ran).
5. **No evaluation harness** — only the ad-hoc `simulate_agent_workflows` cmd.

**Dispatch order:** **W4-A → W4-B** (W4-B is the harness that proves W4-A; W4-C
through W4-E build on the now-live loop). W4-A is the single critical path —
~30 lines of glue that unblocks every later phase.

---

### Phase W4-A — Make the real loop real (wire tools + tool_calls + executor + LLM)
**Date:** 2026-08-20
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash (RULE_24)
**Status:** DONE ✅
**Depends on:** W3-A (plans endpoints), W3-C (lifecycle) — ✅ DONE.

### Files to Read First
- `backend/ai/plans_service.py` — `_decompose` (~L209), `_run_plan_frames` (~L742).
- `backend/ai/engine/cognition/plan/loop.py` — `run()` (~L120, where `ex = self.executor or ExecuteWitness()`), `_execute_step` (~L409).
- `backend/ai/engine/cognition/turn/runner.py` — `__init__` (~L62, the curated `_draft_tools` allow-set) + `run` (~L414, the GROUNDING RULES block). This is the **reference pattern** the loop must mirror.
- `backend/ai/engine/cognition/turn/draft.py` — `DraftWitness.draft(…, tools=None, …)`.
- `backend/ai/engine/cognition/turn/execute.py` — `ExecuteWitness.__init__(executor, hook_pipeline, hook_ctx_defaults, run_id, instance_id)` + `execute(text, tool_calls, stream_callback, progress_callback)`.
- `backend/ai/engine/llm/provider.py` — `get_llm_client()`.
- `backend/ai/engine/agent/tools.py` — `get_tool_definitions()` (READ ONLY).

### Files to Change
- `backend/ai/plans_service.py` — pass `llm_client` into the planner; build an
  `ExecuteWitness` with `executor` + `hook_ctx_defaults` and pass it as
  `executor=` to `ReActLoop`.
- `backend/ai/engine/cognition/plan/loop.py` — in `_execute_step`, build the
  step's tool set and pass `tools=` to `dw.draft(...)`; fix the `ex.execute(...)`
  call to keyword args with `tool_calls=draft.tool_calls`.

### Implementation (exact seams — edit these and nothing else)

**1. `_decompose` (plans_service.py) — make LLM decompose reachable:**
```python
from ai.engine.llm.provider import get_llm_client
# ...
planner = SkillAwarePlanner(llm_client=get_llm_client(), model=settings.LLM_MODEL)
```
(`decompose()` already resolves `client = llm_client or self.llm_client` — no
other change needed here.)

**2. `_run_plan_frames` (plans_service.py) — arm the ExecuteWitness:**
After `executor = CarbonHostExecutor(...)` is built (inside the `async with
get_session_factory(...)() as db:` block), construct an `ExecuteWitness` with the
host context and hand it to `ReActLoop`:
```python
from ai.engine.cognition.turn.execute import ExecuteWitness
# ...
execute_witness = ExecuteWitness(
    executor=executor,
    run_id=str(run.id),
    instance_id=PLAN_INSTANCE_ID,
    hook_ctx_defaults={
        "instance_id": PLAN_INSTANCE_ID,
        "conversation_id": conversation_id,
        "host_user_id": user_pk,
        "run_id": str(run.id),
        "instance_config": instance_config,
    },
)
loop = ReActLoop(
    draft_witness=DraftWitness(executor=executor),
    critic_witness=CriticWitness(),
    executor=execute_witness,
    db=db,
)
```
`host_user_id=user_pk` is **already** passed to `loop.run(...)` — leave it.

**3. `_execute_step` (loop.py) — give the draft tools + fix the execute call:**

(a) Near the top of `_execute_step`, compute the step's tool set:
```python
from ai.engine.agent.tools import get_tool_definitions

step_tools: list[dict] | None = None
if step.tool_name:
    step_tools = [
        d for d in get_tool_definitions()
        if d.get("function", {}).get("name") == step.tool_name
    ] or None
else:
    # Single-step passthrough: mirror runner.py's curated allow-set so a
    # plain imperative request ("create a dq rule…") still dispatches a tool.
    _allow = {"create_dq_rule", "search_knowledge", "get_entity_details",
              "list_my_capabilities", "plan_task"}
    step_tools = [
        d for d in get_tool_definitions()
        if d.get("function", {}).get("name") in _allow
    ] or None
```

(b) Pass `tools=step_tools` to the draft (and, when `step_tools` is non-empty,
append the same GROUNDING RULES to `system_prompt` that `runner.py:run` uses —
copy that f-string verbatim so the planner actually *calls* the tool instead of
answering in prose):
```python
draft = await dw.draft(
    instance_id=instance_id,
    conversation_id=conversation_id,
    user_message=enriched_prompt,
    system_prompt=system_prompt,
    conversation_history=conversation_history,
    instance_config=instance_config,
    user_info=user_info,
    tools=step_tools,
)
```

(c) Fix the execute call (the current positional call is a latent bug):
```python
execution = await ex.execute(
    text=draft.text,
    tool_calls=draft.tool_calls,
    stream_callback=stream_callback,
    progress_callback=progress_callback,
)
```

### DO NOT TOUCH
- `backend/ai/engine/agent/tools.py`, `backend/ai/engine/agent/plugins.py`,
  `backend/ai/engine/agent/executor.py` (vendored engine — READ ONLY).
- `backend/ai/plugins/**` (create_dq_rule, plan_task, list_capabilities) — already correct.
- `backend/ai/engine/cognition/turn/draft.py`, `execute.py`, `runner.py` — no signature changes; the loop only *calls* them.
- Frontend files (this phase is backend-only).

### Verification Gate (copy-paste; capture terminal output)
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check                     # → "System check identified no issues (0 silenced)"
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run   # → "No changes detected" (engine stays stateless)
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q --maxfail=5 --disable-warnings -p no:cacheprovider   # → all green (esp. test_plan_task, test_create_dq_rule, test_plugins)
/home/ahmed/aast/carbon/.venv/bin/python manage.py simulate_agent_workflows  # → A02 ✅ AND A03 ✅ (18/18)
```
**Acceptance:** the simulation report now shows A02 (multi-step decompose) and
A03 (create_dq_rule mutation → consent gate) both pass. If A03 still reports
"text-only claim", the single-step `tools=` allow-set is not reaching the draft —
re-check seam 3(a)/(b).

### Verification Result (2026-08-20) — DONE ✅

Two **additional** production bugs surfaced during the verification gate and
were fixed (both are the "real loop" consequence of the 5 disconnects):

- **`confirm_step` / `decline_step` str-vs-dict crash** (`plans_service.py`).
  The live engine persists `RunStep.tool_output_json` as a **JSON string** (the
  engine's SQLAlchemy `RunStep` maps it to a `Text` column), while the Django
  `RunStep.tool_output_json` is a `JSONField` and the deterministic seam writes
  a native dict. The consent endpoints called `.get(...)` on the raw value and
  500'd with `AttributeError: 'str' object has no attribute 'get'`. Fixed with
  a `_parse_tool_output_json` normalizer that accepts dict-or-string.
- **Resume re-executes the confirmed step** (`loop.py`). The resume path built
  `completed_ids` but never actually filtered already-completed/skipped steps
  out of `remaining` (the `_partition_ready` dependency check doesn't drop a
  completed step). The confirmed step was re-run and re-triggered the consent
  gate, leaving the run `paused` forever. Fixed by filtering
  `remaining = [s for s in plan.steps if s.step_id not in completed_ids]`.

**Evidence:**
- `manage.py check` → clean.
- `makemigrations --check --dry-run` → "No changes detected".
- `pytest ai` → 639 passed (4 pre-existing `test_catalog.py` username-unique
  ordering errors; `test_catalog.py` passes 15/15 in isolation — unrelated to
  this phase).
- `simulate_agent_workflows` → **18/18** (A02 multi-step decompose ✅, A03
  mutation→consent→confirm→resume→rule-created ✅).

---

### Phase W4-B — Evaluation harness (prove the loop, not just simulate)
**Date:** 2026-08-20
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash (RULE_24)
**Status:** DONE ✅
**Depends on:** W4-A (live loop) — ✅ DONE (18/18 sim green).

Make `backend/ai/management/commands/simulate_agent_workflows.py` a
**deterministic, CI-runnable harness**. The scenario assertions are already
per-scenario `(name, bool)` tuples (decompose → source, step `tool_name`,
tool executed, consent gate for mutations). What's missing is the **CI
contract**: a machine-readable `--json` reporter, a **pinned golden-expectation
file written by the harness itself**, and **non-zero exit codes** so CI can fail
the build on a regression. Backend-only — no schema, no engine changes.

### Files to Read First
- `backend/ai/management/commands/simulate_agent_workflows.py` — the whole
  harness: `SCENARIOS_A/B` registries (~L55), `Live` HTTP helper (~L68), the
  `@scenario_a`/`@scenario_b` functions, `_verdict` (~L1018),
  `_render_checks` (~L1025), `_render_detail` (~L1032), `build_report`
  (~L1036), `Command.handle` (~L1115) which loops both parts, aggregates
  `rows`, writes `REPORT_PATH` (`docs/TASK-RESULTS-SIMULATION-<date>.md`) and
  prints the human summary. `_collect_findings` (~L1215) derives the "Deep
  findings" section.
- `docs/TASK-RESULTS-SIMULATION-*.md` — the report the harness already writes
  (human-readable; keep it, don't hand-edit expectations there).

### Files to Change
- `backend/ai/management/commands/simulate_agent_workflows.py` — **the only
  file.** Add the CI contract below; do not rewrite scenario logic.

### Implementation (exact seams)

**1. Always write a machine-readable JSON report alongside the Markdown.**
Next to `REPORT_PATH` define `REPORT_JSON_PATH = REPORT_PATH.with_suffix(".json")`.
After `build_report(...)` is written, serialize the same `rows` plus a summary
header to JSON and write it:

```python
payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "scenarios": [
        {
            "id": r["id"], "part": r["part"], "title": r["title"],
            "verdict": r["verdict"], "highlight": r["highlight"],
            "plan_id": r["plan_id"],
            "checks": [{"name": n, "pass": bool(ok)} for n, ok in r["checks"]],
            "detail": r["detail"],
        }
        for r in rows
    ],
    "totals": {"passed": ok_n, "failed": len(rows) - ok_n, "total": len(rows)},
}
REPORT_JSON_PATH.write_text(json.dumps(payload, indent=2, default=str))
```

**2. `--json` flag → print the one-line compact JSON to stdout.** In
`add_arguments` add `parser.add_argument("--json", action="store_true", ...)`.
When set, after the summary, `self.stdout.write(json.dumps(payload))` (a single
line) so CI can pipe it. (`json.dumps` the same `payload` above; `default=str`
for the `detail` field.)

**3. Golden expectations — recorded by the harness, not hand-written.**
- New module constant `GOLDEN_PATH = Path(__file__).resolve().parents[4] /
  "docs" / "SIMULATION-GOLDEN.json"`.
- `--record-golden` flag: after the run, write a **pinned** golden file from the
  *currently passing* checks (so green is the contract):

```python
golden = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "scenarios": [
        {"id": r["id"], "part": r["part"], "title": r["title"],
         "checks": [{"name": n, "expect_pass": bool(ok)} for n, ok in r["checks"]]}
        for r in rows
    ],
}
GOLDEN_PATH.write_text(json.dumps(golden, indent=2))
```
  Note: record `expect_pass` for **every** check (including currently-failing
  ones with `expect_pass: false`), so the file is a faithful snapshot; only
  `expect_pass: true` checks are enforced on `--check-golden`.

- `--check-golden` flag: load `GOLDEN_PATH`; for each scenario in the golden
  file, for each check with `expect_pass: true`, assert the current run's
  same `(scenario id, check name)` check is present **and passing**. Collect
  any mismatch into `golden_regressions: list[str]` (e.g. `"A03/resume
  completed"`). If the golden file is absent, print a warning and skip (no
  failure).

**4. Exit codes (CI contract).**
At the end of `handle()`:
```python
exit_code = 0
if any(r["verdict"] == FAIL for r in rows):
    exit_code = 1
if getattr(..., "check_golden") and golden_regressions:
    exit_code = 2
# print a final line naming the exit code, then:
if exit_code:
    raise SystemExit(exit_code)
```
  `1` = a scenario failed; `2` = a pinned golden check regressed (even if all
  scenarios happened to pass). Both are fail-the-build.

**5. Surface golden regressions in the Markdown report.** Append a
"## Golden regression" section to `build_report` output (or emit it after) when
`golden_regressions` is non-empty, listing each. Keep the existing "Deep
findings" section untouched.

### DO NOT TOUCH
- Scenario functions and their assertion tuples (`a01_*` … `b06_*`) — the
  checks ARE the spec; do not weaken or reword them.
- `_install_fake_seams`, `_FakeHostExecutor`, `Live` — deterministic seams.
- Any engine file (`backend/ai/engine/**`), `plans_service.py`, frontend.
- `pytest` suite — this phase extends the *simulation command*, not the tests.

### Verification Gate (copy-paste; capture terminal output)
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py simulate_agent_workflows --part B   # → 6/6 B scenarios, exit 0
/home/ahmed/aast/carbon/.venv/bin/python manage.py simulate_agent_workflows --part B --record-golden   # → writes docs/SIMULATION-GOLDEN.json
/home/ahmed/aast/carbon/.venv/bin/python manage.py simulate_agent_workflows --part B --check-golden     # → exit 0, "0 golden regressions"
/home/ahmed/aast/carbon/.venv/bin/python manage.py simulate_agent_workflows --part B --json             # → prints one-line JSON to stdout
ls -la /home/ahmed/aast/carbon/docs/SIMULATION-GOLDEN.json /home/ahmed/aast/carbon/docs/TASK-RESULTS-SIMULATION-*.json
```
**Acceptance:** `--part B` exits 0 with all 6 B scenarios green; `--record-golden`
writes the pinned file; `--check-golden` reports 0 regressions and exits 0; a
deliberately-broken check (worker temporarily flips one to `False`) makes
`--check-golden` exit 2 — then revert.

### Verification Result (2026-08-20) — DONE ✅

- `manage.py simulate_agent_workflows --part B` → 6/6 B scenarios, `exit=0`.
- `--record-golden` → writes `docs/SIMULATION-GOLDEN.json` (6 scenarios, all
  `expect_pass: true`).
- `--check-golden` → "Golden check passed — 0 regressions.", `exit=0`.
- `--json` → one-line JSON payload printed to stdout, `exit=0`.
- Negative probe: injected a bogus `expect_pass: true` check → `exit=2` with
  "1 golden regression(s)" (golden file then restored).

---

### Phase W4-C — Multi-agent orchestration (worker dispatch + task DAG)
**Date:** 2026-08-20
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash (RULE_24)
**Status:** DONE — VERIFIED (4 tests `test_plan_loop_parallel.py`; ai suite 653 passed; `simulate_agent_workflows --part B` 6/6; `--check-golden` 0 regressions; verified 2026-08-21)
**Depends on:** W4-A (loop live ✅), W4-B (harness ✅).

**Goal (scoped to the two concrete seams that are actually live):** the plan
loop already decomposes into a `depends_on` DAG and already runs the *same*
orchestrator witness for every step. Two things are missing: (1) **independent
steps run serially** (`for step in ready:`), and (2) the per-step **`agent_role`
is never threaded into the `HookContext`**, so `readonly_worker_hook` can never
fire for worker-role steps. This phase closes both. **It does NOT build the
`WorkerPool` fan-out path** — `workers.py` already implements that; the loop is
the orchestrator's in-process parallel executor. Capability-gating is already
enforced by `readonly_worker_hook` (CBAC via `ctx.db`) once `is_worker=True`
reaches it.

### Files to Read First
- `backend/ai/engine/cognition/plan/planner.py` — `PlanStep` dataclass (~L22).
- `backend/ai/engine/cognition/plan/loop.py` — `run()` (~L225-405, the
  `while remaining:` / `for step in ready:` serial loop + fold-back),
  `_execute_step` (~L409-580).
- `backend/ai/engine/cognition/turn/execute.py` — `execute()` (~L33-160, builds
  `HookContext` from `self.hook_ctx_defaults`) and `_execute_single_tool`
  (~L176-265).
- `backend/ai/engine/agent/guardrails.py` — `HookContext` (~L36) + 
  `readonly_worker_hook` (~L213, fires only when `ctx.is_worker`).
- `backend/ai/plans_service.py` — `_rebuild_plan` (~L377), the
  `ExecuteWitness(... hook_ctx_defaults={...})` construction (~L851).

### Files to Change
- `backend/ai/engine/cognition/plan/planner.py` — add one field.
- `backend/ai/engine/cognition/turn/execute.py` — additive override params.
- `backend/ai/engine/cognition/plan/loop.py` — parallelize `ready` batch + pass role.
- `backend/ai/plans_service.py` — read `agent_role` in `_rebuild_plan`.
- `backend/ai/tests/test_plans.py` (or new `test_plan_loop_parallel.py`) — tests.

### Implementation (exact seams)

**1. `PlanStep.agent_role` (planner.py).** Add
`agent_role: str = "orchestrator"` to the `PlanStep` dataclass (default keeps
every existing plan behaving as today). Update the `_DECOMPOSE_AGENT_PROMPT`
JSON schema to mention `"agent_role": "orchestrator"` (optional, no LLM
behaviour change required — leave it out of the emitted steps by default).

**2. Read it back (`plans_service.py:_rebuild_plan`).** In the `PlanStep(...)`
constructor add `agent_role=s.get("agent_role", "orchestrator")`. Do not change
the `Plan(...)` construction or the `hook_ctx_defaults` dict.

**3. `ExecuteWitness.execute` additive overrides (`execute.py`).** Extend the
signature with `agent_role: str | None = None` and `is_worker: bool | None =
None`. At the top of `execute()`, build a per-call defaults dict:

```python
ctx_defaults = dict(self.hook_ctx_defaults or {})
if agent_role is not None:
    ctx_defaults["agent_role"] = agent_role
if is_worker is not None:
    ctx_defaults["is_worker"] = is_worker
```

Then pass `ctx_defaults` (instead of `self.hook_ctx_defaults`) to **both**
`_execute_single_tool(...)` call sites (the independent `asyncio.gather` batch
and the dependent sequential loop). `_execute_single_tool` already reads
`agent_role`/`is_worker` from `hook_ctx_defaults` via
`ctx_defaults.get("agent_role", "orchestrator")` and
`ctx_defaults.get("is_worker", False)` — no change needed there. This is
strictly additive: callers that pass nothing get today's behaviour.

**4. Parallelize the `ready` batch + thread role (`loop.py`).**

(a) `_execute_step`: accept the role on the call and forward it. Add
`agent_role: str | None = None` to the signature, and in the `ex.execute(...)`
call add `agent_role=agent_role or step.agent_role,
is_worker=(step.agent_role not in ("orchestrator", "", None))`.

(b) `run()`: replace the serial `for step in ready:` **execution** with a
parallel gather, but **keep the fold-back loop**. Structure it in three phases:

```python
# Phase 1 — broadcast started for every ready step (preserves event order)
for step in ready:
    await _get_broadcast()(instance_id, "run.step.started", {...})

# Phase 2 — execute in parallel (sequential fast-path when len==1)
async def _run_one(step):
    t0 = time.monotonic()
    result = await self._execute_step(step=step, ..., step_contexts=step_contexts)
    return step, result, (time.monotonic() - t0) * 1000

if len(ready) == 1:
    executed = [await _run_one(ready[0])]
else:
    executed = await asyncio.gather(*[_run_one(s) for s in ready])

# Phase 3 — fold back IN ORDER, reusing the existing post-step logic verbatim
for step, result, step_latency in executed:
    step_results.append(result)
    total_llm_calls += 1
    ...  # broadcast completed/failed, consent-gate pause+break, persist,
         # veto/replan+break, mutation counter, completed_ids.add,
         # step_contexts[step_id] = draft_text  (unchanged from today)
```

Preserve the exact `break` semantics: if a paused or vetoed step `break`s the
fold-back, later (already-executed, independent) results in that batch are
simply discarded — same "stop the whole loop" contract as today. The
`asyncio` import is already present in `loop.py`.

Concurrency-safety note (worker does not need to "fix" anything, just verify):
`dw.draft` / `cw.review` / `ex.execute` are stateless per call (LLM + executor
+ contextvars), and `step_contexts` is read-only during the gather (deps are
already in `completed_ids`). The shared `stream_callback`/`progress_callback`
may interleave — acceptable.

**5. Tests (`backend/ai/tests/test_plans.py` or a new file).** Two focused,
deterministic unit tests (fake executor, no HTTP):
- *Parallel overlap*: build a `Plan` with two `depends_on=[]` steps; use a fake
  executor whose tool call records `started_at`/`ended_at` timestamps with a
  small `asyncio.sleep`; assert the two execution intervals **overlap** (i.e.
  the run is not serial). (If the fake seam makes overlap hard to assert,
  instead assert both steps complete and each ran exactly once — but prefer the
  overlap assertion.)
- *Worker readonly guardrail*: a step with `agent_role="worker"` executing a
  mutation tool is cancelled by `readonly_worker_hook` (result carries a
  guardrail/cancel error), while the same step with `agent_role="orchestrator"`
  (default) proceeds. Patch the engine seams at their lazy import points as
  `test_plans.py` already does.

### DO NOT TOUCH
- `backend/ai/engine/agent/workers.py`, `guardrails.py`, `tools.py`,
  `plugins.py`, `executor.py`, `runner.py` — the fan-out + guardrail machinery
  already exists and is correct; this phase only routes the loop's context into it.
- `_partition_ready`, `_synthesise`, `_replan_step`, `_persist_run_step`,
  `_pause_run`, `_finalize_run` — untouched.
- `simulate_agent_workflows.py` scenario functions — do not reword existing
  checks. (Adding a `b07` end-to-end scenario is **optional** and only after
  the unit tests pass; if added, re-record golden with `--record-golden`.)
- `pytest` suite partitioning rules (RULE: one app at a time, `python -m pytest
  ai -q --maxfail=5 --disable-warnings -p no:cacheprovider`).

### Verification Gate (copy-paste; capture terminal output)
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q --maxfail=5 --disable-warnings -p no:cacheprovider
/home/ahmed/aast/carbon/.venv/bin/python manage.py simulate_agent_workflows --part B
/home/ahmed/aast/carbon/.venv/bin/python manage.py simulate_agent_workflows --part B --check-golden
```
**Acceptance:** `manage.py check` clean; `pytest ai` green (all prior + the two
new tests); `--part B` still 6/6 and `--check-golden` still 0 regressions
(no behaviour change to existing scenarios). Then mark W4-C DONE below.

---

### Phase W4-D — Learning flywheel (Reflexion-style step feedback)
**Date:** 2026-08-20
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash (RULE_24)
**Status:** DONE ✅ (landed 2026-08-22 — flywheel + planner boost + 10 tests; all gates green)
**Depends on:** W4-A (durable Run/RunStep rows + live loop ✅), W4-C (multi-agent
loop + replan ✅).

**Goal (scoped to what is actually live):** the ReAct loop already persists a
per-step `critic_verdict` (`pass`/`pass_with_flag`/`rewrite`/`veto`), tool
output, error, and latency on `RunStep` rows, and a `Run` row with
`total_llm_calls`/`total_latency_ms`/`status`. The `Skill` model already has
`usage_count`, `success_rate`, `avg_latency_ms`, `last_executed_at`,
`gate_status`, and `status`. What is **missing** is the flywheel that *feeds
run outcomes back into the SkillRegistry* so decomposition quality improves
with use: successful plans promote their source skill's score, vetoed/failed
steps depress it. This phase builds that loop **outside the engine core**
(mirroring Phase D's `ai/feedback/` pattern — capture → pipeline; never
learning inside `engine/**`, RULE_6) and wires the planner's skill ranking to
consume the learnt signal.

Design (verbatim from the W4-D stub): *"Feed critic verdicts + tool outcomes
back into the SkillRegistry as learnt signals (successful plans promote
skills; vetoed steps adjust scoring) so decomposition quality improves with
use."*

### Files to Read First
- `backend/ai/plans_service.py` — `_execute_plan_once` (~L911), the retry loop
  + final `Run`/`RunStep` re-read in `_run_plan_frames` (~L1120-1210, where the
  flywheel hook fires), `_serialize_run` (~L157, `skill_name` from `plan_json`).
- `backend/ai/models/core.py` — `Run` (~L312: `plan_json`, `status`,
  `total_llm_calls`, `total_latency_ms`), `RunStep` (~L337: `critic_verdict`,
  `critic_flags_json`, `tool_output_json`, `error`, `latency_ms`, `status`).
- `backend/ai/engine/skills/registry.py` — `SkillRegistry` (thin async CRUD:
  `add`, `get`, `list_by_user`, `list_promoted`, `search`, `update_status`).
- `backend/ai/engine/skills/crud.py` — `SkillsStore`: `resolve_skill` (~L102,
  name-or-ID → promoted-first), `update_stats` (~L136, updates
  `usage_count`/`success_rate`/`avg_latency_ms`/`last_executed_at` — **already
  exists, currently called from nowhere in the plan path**),
  `promote_to_instance` (~L172).
- `backend/ai/engine/cognition/plan/planner.py` — `_score_skill` (~L65, pure
  keyword overlap today — the learnable ranking), `_parse_skill_plan` (~L322,
  sets `Plan.source="skill"`, `Plan.skill_name`), `SkillAwarePlanner.decompose`
  (~L219).
- `backend/ai/engine/core/models.py` — `Skill` (~L820: `usage_count`,
  `success_rate`, `avg_latency_ms`, `last_executed_at`, `gate_status`, `status`).
- `backend/ai/feedback/` (Phase D pattern) — `__init__.py`, `pipeline.py`
  (idempotency: `applied_at` + `idempotency_key` guard; revert via
  `revert_payload`), `signals.py` (`quality_score_for` taxonomy).
- `backend/ai/engine/cognition/plan/loop.py` — the `succeeded` computation
  (~L486: `all(r.critic_verdict in ("pass","pass_with_flag") and not r.error
  for r in step_results)`) — the exact success predicate to mirror at the
  flywheel seam.

### Files to Change
- NEW `backend/ai/feedback/skill_flywheel.py` — the learning loop (outside the
  engine; no `engine/**` writes).
- `backend/ai/plans_service.py` — fire the flywheel after a run finalizes.
- `backend/ai/engine/cognition/plan/planner.py` — `_score_skill` consumes
  `success_rate`/`usage_count` (a small, deterministic learnt-signal boost).
- NEW `backend/ai/tests/test_skill_flywheel.py` — unit + integration tests.

### Implementation (exact seams)

**1. NEW `backend/ai/feedback/skill_flywheel.py`.** Public surface:

- `feed_run_feedback(run_id: str) -> dict | None` — sync entry (called from
  `plans_service` via `sync_to_async` or thread). Reads the Django `Run` +
  `RunStep` rows for `run_id`; **no-ops** (returns `None`) unless:
  `run.plan_json.get("source") == "skill"` **and** `plan_json.get("skill_name")`
  is a non-empty string. Computes the outcome:
  - `success = run.status == "completed"` and every non-skipped step has
    `critic_verdict in ("pass", "pass_with_flag")` and no `error` (mirror the
    loop's `succeeded` predicate, L486).
  - `vetoed = count of steps with critic_verdict == "veto"`
  - `total_latency_ms = run.total_latency_ms or None`
  - `flags = [f for s in steps for f in (s.critic_flags_json or [])]`
  Then opens an engine session (`get_session_factory(PLAN_INSTANCE_ID)`),
  resolves the skill via `SkillsStore(db).resolve_skill(PLAN_INSTANCE_ID,
  skill_name)`, and calls `SkillsStore(db).update_stats(skill.id, success,
  latency_ms)` — **RULE_21 is satisfied because `update_stats` only mutates the
  skill's own learning ledger columns, never host data, and never auto-promotes
  status**; the phase explicitly documents that promotion (status →
  `instance_promoted`) stays human-gated via `promote_to_instance`/admission
  gate (out of scope here). Returns
  `{"skill_id", "skill_name", "success", "vetoed", "latency_ms", "updated"}`.
  Idempotency: **at-least-once is safe** (update_stats is a running average);
  still, guard with `run.working_notes`-independent check — only fire when the
  run is in a terminal state (`completed`/`failed`), so the retry loop never
  double-fires mid-flight.
- `promote_on_success(skill_id, threshold_successes: int = 3,
  min_success_rate: float = 0.75) -> bool` — **helper only** (optional): after
  `update_stats`, if `usage_count >= threshold_successes and success_rate >=
  min_success_rate and skill.status != "instance_promoted"`, return True so a
  caller can surface "promote?" to the user (RULE_21 — the flywheel **never
  writes** status; it only reports readiness). Include a unit test that it
  returns True/False correctly without mutating status.
- Keep it importable without touching `engine/**` (imports only
  `ai.engine.skills.crud.SkillsStore`, `ai.engine.core.database`, models).

**2. `plans_service.py` — fire the hook.** In `_run_plan_frames`, after the
retry loop and the final `run.refresh_from_db()` + `steps` re-read (i.e. after
the `done`-frame logic's input data is settled), add:
```python
from ai.feedback.skill_flywheel import feed_run_feedback
try:
    feed_result = await sync_to_async(feed_run_feedback)(str(run.id))
    if feed_result:
        logger.info("skill flywheel: %s", feed_result)
except Exception:  # BLE001 — learning must never fail a plan run
    logger.exception("skill flywheel failed for run %s", run.id)
```
Place it *before* the final `yield` of `done` (so the learnt signal is applied
before the client sees completion) — or immediately after; either is fine, but
it must be inside the try/except and after the retry loop so only terminal
states reach it. Do **not** call it from `_execute_plan_once` (per-attempt —
would fire during retries).

**3. `planner.py:_score_skill` — consume learnt signals.** Keep the keyword
scoring exactly as-is, then add a deterministic quality boost at the end:
```python
# Learnt-signal boost (W4-D): skills with a proven success record rank
# above cold matches at equal keyword overlap. Pure read — never writes.
if getattr(skill, "success_rate", 0) and getattr(skill, "usage_count", 0):
    boost = min(0.1, 0.05 + 0.05 * float(skill.success_rate))
    if skill.usage_count >= 3 and skill.success_rate >= 0.75:
        boost = min(0.15, boost + 0.05)
    return min(score + boost, 0.99)
return score
```
- `_MATCH_THRESHOLD` (0.5) unchanged. Unit tests: equal keyword overlap → the
  skill with `success_rate=1.0, usage_count=5` outscores `success_rate=0.0`;
  boost never crosses 0.99; zero-usage skills score identically to today
  (golden-safe: `simulate_agent_workflows --part B --check-golden` must show 0
  regressions because the boost is additive and only triggers on nonzero stats).

**4. NEW `backend/ai/tests/test_skill_flywheel.py`** (mirror `test_dq_feedback.py`
style; reuse `_make_plan`/`_make_step` from `ai.tests.test_plans` + engine
session fixtures from `test_plans.py`). Tests:

- `test_flywheel_noop_without_skill_source` — plan with `source="single_step"`,
  or `source="skill"` but no `skill_name` → `feed_run_feedback` returns `None`
  and no `Skill` row is touched.
- `test_flywheel_promotes_successful_run` — seed a `Skill` (`multi_step_plan`,
  `instance_promoted` or draft), `_make_plan(status="completed")` with
  `plan_json.source="skill"` + `skill_name`, steps all `pass` →
  `update_stats` applied: `usage_count == 1`, `success_rate == 1.0`,
  `last_executed_at` set; result dict matches.
- `test_flywheel_depresses_vetoed_run` — one step `critic_verdict="veto"` (or
  `error` set, run `status="failed"`) → `success=False`, `success_rate < 1.0`,
  `vetoed == 1`.
- `test_flywheel_does_not_fire_mid_flight` — run `status="running"` →
  returns `None` (retry-loop safety).
- `test_promote_on_success_never_mutates` — after enough successes,
  `promote_on_success(...)` returns True but `skill.status` still `draft`.
- `test_score_skill_consumes_learnt_signal` — ranking + 0.99 cap + zero-usage
  unchanged (3 assertions).

### DO NOT TOUCH
- `backend/ai/engine/cognition/plan/loop.py` — the loop already records
  verdicts/outcomes; **no learning inside the engine** (RULE_6).
- `backend/ai/engine/skills/gate.py` + `registry.py` — admission gate +
  status transitions stay as-is; the flywheel only feeds stats and reports
  readiness.
- `ai/feedback/pipeline.py` / `signals.py` / `capture.py` — Phase D surface
  unchanged (the flywheel is additive, keyed on run outcomes, not DQ events).
- `Skill` model / migrations — **no schema change** (all needed columns exist).
- `simulate_agent_workflows.py` scenario functions + golden — the planner boost
  is additive and zero-usage-neutral; `--check-golden` must stay 0 regressions.
  (Adding a `b07` scenario is optional and only after tests pass; if added,
  re-record golden with `--record-golden`.)
- Frontend, other apps, `manage.py`, Docker gates.

### Verification Gate (copy-paste; capture terminal output)
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_skill_flywheel.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q --maxfail=5 --disable-warnings -p no:cacheprovider
/home/ahmed/aast/carbon/.venv/bin/python manage.py simulate_agent_workflows --part B
/home/ahmed/aast/carbon/.venv/bin/python manage.py simulate_agent_workflows --part B --check-golden
```
**Acceptance:** `manage.py check` clean; new flywheel tests green; full `pytest
ai` green (all prior + new); `--part B` still 6/6 and `--check-golden` still 0
regressions (planner boost is additive, zero-usage-neutral). Then mark W4-D
DONE.

---

### Phase W4-E — Observability & governance (run ledger → audit surface)
**Date:** 2026-08-20
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash (RULE_24)
**Status:** DONE (verified 2026-08-23: 36 tests pass, migrations clean)
**Depends on:** W4-A (durable Run/RunStep rows now carry real tool_output) — DONE.

Surface `tool_output` + consent events in the W3-G admin timeline; add
cross-run cost/quality rollups (`total_llm_calls`, `confirmations_required`).

### Files to Read First
- `backend/ai/durable_service.py` — `timeline()` (~L113, the event builder), `_step_status_event` (~L280), `_run_status_event`, `_audit_events`. Events are derived from `Run` + `RunStep` rows + `working_notes`; `step_completed` today carries only `{verdict}`, and no consent transition event exists.
- `backend/ai/durable_api.py` — `RunViewSet` (timeline / compare / resume / replay), `_unavailable` fail-visible envelope.
- `backend/ai/durable_urls.py` — routes (`compare/`, `{pk}/timeline/`, `{pk}/resume/`, `{pk}/replay/`).
- `backend/ai/observability_api.py` — `OutputQualityTrendView` (~L340), `_redact_secrets`, `_scoped_quality_rows`; the admin read-layer pattern to mirror.
- `backend/ai/ops_urls.py` — route registry (`quality-trend/`, `data/<key>/`).
- `backend/ai/models/core.py` — `Run` (~L312: `total_llm_calls`, `total_latency_ms`, `status`), `RunStep` (~L337: `tool_output_json` L349, `confirmation_token`, `critic_verdict`, `status`).
- `backend/ai/tests/test_durable.py` + `backend/ai/tests/test_observability_api.py` — existing test patterns + fixtures (`user`, `other_user`, `auth_client`, `_make_plan`, `_make_step`).

### Files to Change
- `backend/ai/durable_service.py` — enrich `step_completed` events with redacted `tool_output`; add `step_confirmed` / `step_declined` consent-transition events.
- `backend/ai/observability_api.py` — add a cross-run rollup view.
- `backend/ai/ops_urls.py` — mount the rollup route.
- `backend/ai/tests/test_durable.py` + `backend/ai/tests/test_observability_api.py` — new tests.

### Implementation (exact seams — edit these and nothing else)

**1. Tool output in the timeline (`durable_service.py`).** In `_step_status_event`, the `step_completed` branch returns `("step_completed", {"verdict": ...})`. Extend it to also carry the step's `tool_output` (redacted): reuse `observability_api._redact_secrets` on `step.tool_output_json` and include it as `detail["tool_output"]` **only when non-empty** (never emit an empty/null key). Keep `verdict` intact.

**2. Consent-transition events.** The current timeline never surfaces a step *leaving* `awaiting_approval`. Add, per step, a consent event when its `confirmation_token` was consumed: derive `step_confirmed` (or `step_declined`) from the durable step state the worker inspects in `plans_api.confirm_step` / `decline_step` (they update `RunStep.status` and/or `working_notes.audit`). Emit it as a product-term event with `detail: {step_id, choice}` — never engine class names (RULE_23). If the confirm/decline path does **not** persist a durable marker, add one to `working_notes.audit` via the existing `_append_audit` helper (no schema change, no new migration).

**3. Cross-run cost/quality rollups (`observability_api.py`).** Add `RunRollupView` (GET-only `APIView`, `AdminOrSuperuserOnly`, `ai:view_console`) returning:
```python
{
  "totals": {
     "runs": N,
     "total_llm_calls": N,
     "confirmations_required": N,   # count of RunStep rows still awaiting approval
     "total_latency_ms": N | None,
     "completed": N, "failed": N, "paused": N, "running": N,
  },
  "per_run": [ { "run_id", "status", "total_llm_calls", "latency_ms",
                 "confirmations_required", "step_count", "completed_at" } ]
}
```
`confirmations_required` per run = `RunStep.objects.filter(run_id=..., status="awaiting_approval").count()` (the exact status literal lives in `plans_service.STEP_AWAITING_APPROVAL` — import it, do not re-string). Scope every queryset with `scope_ai_queryset(..., request.user)` and cap `per_run` at 200 most-recent (reuse `_timestamp_field` ordering). Mount at `ai/pulse/rollups/` in `ops_urls.py`.

### DO NOT TOUCH
- `backend/ai/engine/**` — read-only callers only; no engine internals.
- No new migrations — everything rides existing `Run`/`RunStep` columns + `working_notes`.
- `carbon-frontend/**` — this phase is backend-only (the timeline payload the frontend already renders via `eventDetailText` picks up the new detail fields automatically; richer rendering is out of scope here).

### Verification Gate
```bash
cd backend && ../.venv/bin/python -m pytest ai/tests/test_durable.py ai/tests/test_observability_api.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
cd backend && ../.venv/bin/python manage.py makemigrations --check --dry-run   # clean (no new migrations)
./.ai-toolkit/scripts/verify.sh
```
Plus `get_errors` on the changed files.

### Output contract
- `timeline/` payload now carries `tool_output` (redacted) on completed steps and `step_confirmed`/`step_declined` consent events.
- New `GET /carbon-api/ai/pulse/rollups/` returns the aggregate + per-run cost/quality rollup above.
- Tests green; a concise results note with test counts, migration status, and any deviations.

---

### Phase W7-A — Agent Execution Control: backend contract (F-26 / F-28 / F-29)
**Date:** 2026-08-23
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash (RULE_24)
**Status:** DONE (verified 2026-08-23: 57 tests pass, migrations clean, `owner` added to schedule payload)
**Depends on:** W6-D (F-26 parallel), W6-E (F-28 pause→steer→resume, F-29 RunSchedule + `run_due_schedules`) — DONE. Design doc: `docs/DESIGN-AGENT-EXECUTION-CONTROL.md`.

Freeze the backend contract the frontend (W7-B) composes against: serialized
`strategy`/`parallel_group` + `runnable_state` on steps, and the schedules
REST CRUD + server-side `preview` string.

### Files to Read First
- `backend/ai/plans_service.py` — step serialization (`_serialize` ~L376 and ~L442-460; phase `strategy` already serialized at L457/645), step-edit (`edit_step` ~L545-635), schedule service (`create_schedule` ~L1389, `_serialize_schedule` ~L1448, `list_schedules` ~L1476, `delete_schedule` ~L1490, `materialize_due_schedules` ~L1506), `_cron_trigger`.
- `backend/ai/plans_api.py` + `backend/ai/plans_urls.py` — `PlanViewSet` actions + explicit `as_view` route list (note: `templates/` routes MUST precede `<str:pk>/`).
- `backend/ai/models/core.py` — `RunSchedule` (~L405: `enabled`, `cron_expr`, `run_at`, `template`, `plan_json`, `next_run_at`, `last_run_at`), `RunStep` (~L337), `Run.status` literals.
- `backend/ai/engine/cognition/plan/planner.py` — `PlanPhase.strategy` ("sequential"|"parallel", ~L49) and step `phase`/`strategy` relationship (read-only; the engine already emits `strategy` on phases).
- `backend/ai/tests/test_schedule_steering.py`, `test_plans.py` — existing schedule + step serialization test patterns.

### Files to Change
- `backend/ai/plans_service.py` — add `parallel_group` + `runnable_state` to serialized steps; add `edit_schedule`, `pause_schedule`, `_schedule_preview`.
- `backend/ai/plans_api.py` + `backend/ai/plans_urls.py` — schedule REST routes + view methods.
- `backend/ai/tests/test_plans.py` + `backend/ai/tests/test_schedule_steering.py` — new tests.

### Implementation (exact seams — edit these and nothing else)

**1. F-26 / F-28 — serialized step fields (`plans_service.py`).** In the step serializer(s) (~L376 and ~L442-460), add two fields to every serialized step:
- `"strategy"`: the enclosing phase's strategy (already computed at phase level — propagate it, default `"sequential"`).
- `"parallel_group"`: `None` when the phase `strategy != "parallel"`; otherwise a stable group key (use the phase id/ordinal so sibling steps in the same parallel phase share it). Optional — do not emit when absent.
- `"runnable_state"`: derived from `RunStep.status` → `"completed"` (`completed`/`skipped`), `"in_flight"` (`running`), `"pending"` (`pending`/`awaiting_approval`). Never derive from status *strings* the UI would need to guess — emit this explicit enum.

**2. F-28 — pause→steer contract.** Confirm `edit_step` (~L545) already accepts a PATCH on a `pending` step while the run is `paused` (the W6-E1 path). If it blocks pending-step edits during `paused`, relax the guard so **only** `pending` steps are editable while `paused` (completed/`in_flight` steps stay locked). Do **not** change `resume` semantics.

**3. F-29 — schedules REST API.** Add to `PlanViewSet` (or a thin sibling) and route in `plans_urls.py` (place `schedules/` routes BEFORE `<str:pk>/`, same as `templates/`):
- `GET    /ai/plans/schedules/` → `list_schedules` (owner-scoped, soonest first)
- `POST   /ai/plans/schedules/` → create (reuse `PlansService.create_schedule`)
- `PATCH  /ai/plans/schedules/<id>/` → `edit_schedule` (name/description/cron_expr/run_at; recompute `next_run_at`)
- `DELETE /ai/plans/schedules/<id>/` → `delete_schedule`
- `POST   /ai/plans/schedules/<id>/pause/` → `pause_schedule` (toggle `enabled`; does **not** delete)

**4. F-29 — server-side `preview`.** Add `PlansService._schedule_preview(schedule) -> str` and include `"preview"` in `_serialize_schedule`. Produce plain-language outcome copy (RULE_23): one-off → `"Once on 2026-08-25 at 2:00 PM"`; recurring → `"Every day at 9:00 AM"` / `"Every Monday at 9:00 AM"` / `"Every 1st of the month at 9:00 AM"`. Never emit a bare `cron` string as the default human text (the raw `cron_expr` stays in the payload for power users). Times in Africa/Cairo (`timezone.now()` / `localtime`).

### DO NOT TOUCH
- `backend/ai/engine/**` — the engine already emits phase `strategy`; consume it, do not modify it.
- `RunSchedule` model fields — the model is complete; no migration for W7-A.
- `materialize_due_schedules` / `run_due_schedules` command — already correct (RULE_21 pending_approval, atomic claim).
- `carbon-frontend/**` — this phase is backend-only.

### Verification Gate
```bash
cd backend && ../.venv/bin/python -m pytest ai/tests/test_plans.py ai/tests/test_schedule_steering.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
cd backend && ../.venv/bin/python manage.py makemigrations --check --dry-run   # clean
./.ai-toolkit/scripts/verify.sh
```
Plus `get_errors` on the changed files.

### Output contract
- Serialized steps carry `strategy`, `parallel_group`, `runnable_state` (frozen for W7-B).
- `schedules/` list/create/edit/delete/pause REST surface with a server-side `preview` string per schedule.
- Tests green; concise results note with test counts, migration status, and the exact serialized-step + schedule JSON shape the frontend must consume.

---

### Phase W7-B — Agent Execution Control: frontend UX (F-26 / F-28 / F-29)
**Date:** 2026-08-23
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash (RULE_24)
**Status:** DONE (verified 2026-08-23: 842 tests pass, lint 0 errors, build clean)
**Depends on:** W7-A (frozen step + schedule contract) — DONE. Design doc: `docs/DESIGN-AGENT-EXECUTION-CONTROL.md` (acceptance criteria are the source of truth).

Compose the three Enterprise features against the W7-A contract, all in the
Agent-mode surface. No new routes/sidebar entries; RULE_21 consent never
auto-bypassed; RULE_23 outcome copy only; RULE_8 theme tokens only.

### Files to Read First
- `docs/DESIGN-AGENT-EXECUTION-CONTROL.md` — §F-26 / §F-28 / §F-29 acceptance (happy/empty/error/permission/boundary scenarios) + §3 cross-feature rules.
- `carbon-frontend/src/shell/AITaskPanel.jsx` — tabs (`tasks | run | monitor | results | templates`, localStorage `carbon-ai-task-tab`), plan controls.
- `carbon-frontend/src/components/graph/PlanDagGraph.jsx` — step DAG (nodes = steps, edges = `depends_on`, status-colored); add the parallel-lane concept here.
- `carbon-frontend/src/components/` — `StepEditDialog.jsx`, `PlanDiffReviewDialog.jsx` (consent gate).
- `carbon-frontend/src/api/aiWorkspace.js` — `pausePlan`, `resumePlanStream`, `stopPlan`, `forkPlan`, `editPlan`, `editPlanStep`, `listPlanTemplates`, `instantiatePlanTemplate`, `promotePlanTemplate` (add schedule wrappers here).
- `carbon-frontend/src/__tests__/` — existing AITaskPanel / PlanDagGraph test patterns.

### Files to Change
- `carbon-frontend/src/components/graph/PlanDagGraph.jsx` — parallel-lane grouping (F-26).
- `carbon-frontend/src/shell/AITaskPanel.jsx` — paused banner + per-pending-step edit + `scheduled` tab (F-28 / F-29).
- `carbon-frontend/src/components/` — schedule dialog + schedule list + any small presentational additions (F-29).
- `carbon-frontend/src/api/aiWorkspace.js` — schedule API wrappers (F-29).
- `carbon-frontend/src/__tests__/` — new unit tests per feature.

### Implementation (exact seams — edit these and nothing else)

**1. F-26 — parallel lane.** In `PlanDagGraph.jsx`, group steps sharing a non-null `parallel_group` (and `strategy === "parallel"`) into a collapsible **parallel lane** band (MUI `Collapse`/`Stack`, theme `status` colors). Each step inside still renders its own status `Chip` (RULE 5: chip + label, never color alone). A mutation step at `awaiting_approval` shows Approve/Decline **inside the lane** without blocking its siblings; a failed step keeps a persistent `failed` chip + Retry while siblings stay `done`; the plan header shows "1 of 3 steps needs attention" (not a blanket "failed") when only some siblings failed. Lane copy = outcome words ("Gathering the data", "Drafting the report") — never "thread"/"fan-out"/"concurrency" (RULE_23).

**2. F-28 — steer a paused run.** In `AITaskPanel.jsx`: on `paused`, show a persistent banner ("Paused — N steps completed, M to go"). Lock completed/`in_flight` steps (read-only, using `runnable_state`); render an edit affordance (`IconButton` + tooltip) on `pending` steps only. Edit → `StepEditDialog` → `PlanDiffReviewDialog` consent gate (RULE_21) → save re-approves only that step. Disable the edit affordance with tooltip "No upcoming steps to adjust." when there are 0 pending steps. Resume continues from the first pending step (completed steps are never re-run).

**3. F-29 — scheduling.** Add a 6th tab `scheduled` (persist to the same `carbon-ai-task-tab` key, RULE_17). Templates tab gains a per-row **Schedule** action opening a `Dialog` with: cadence preset picker (once/daily/weekly/monthly via `Autocomplete`) + a plain-language `preview` (use the server-side `preview` string from W7-A — single source of truth) + raw cron progressive-disclosed for power users. The Scheduled list shows each schedule with its `preview`, owner, `enabled` status, and edit/pause/delete (delete = confirm dialog naming the consequence). Past-time one-off → inline validation error + disabled Save. Handle all 4 data states (loading/error/empty/loaded).

### DO NOT TOUCH
- `backend/**` — consume the W7-A contract only.
- No new routes/sidebar entries (IA lives entirely in `AITaskPanel.jsx` tabs).
- No raw hex / inline spacing magic numbers (RULE_8) — theme tokens only.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm test -- --run          # all green (new + existing)
npm run lint               # 0 new errors
npm run build              # clean
```
Plus `get_errors` on the changed files.

### Output contract
- Parallel lanes render in the plan DAG; paused-run steering (edit pending → diff-review → resume) works; a `scheduled` tab with schedule dialog + list + server `preview`.
- New unit tests per feature (F-26 lane grouping, F-28 lock/edit/resume, F-29 schedule list/dialog).
- Results note: test counts, lint/build status, and any contract mismatches with W7-A (report, do not silently fix backend).

---

### Phase W8-A — Pulse composer slash-command menu (`/` popup)
**Date:** 2026-08-23
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash (RULE_24)
**Status:** DONE (verified 2026-08-23: browser-verified all 7 commands, 30 AIInputBar tests pass, ESLint clean)
**Depends on:** W5-A (ADR-0014 mode header), W2-C (context lifecycle actions), Sprint 17 (`#`-mention picker in `AIInputBar`).

Add a `/` command menu to the Pulse composer, mirroring the existing `#`-mention
picker. Commands are client-side: **directives** insert a prompt fragment the user
completes and sends; **actions** trigger an existing workspace action via a new
`onCommand` callback. Every command maps to functionality that already exists —
nothing backend is invented.

### Files to Read First
- `carbon-frontend/src/shell/AIInputBar.jsx` — the shared composer. Has a two-stage `#` picker (`stage: null | 'kind' | 'entity'`, `KIND_TRIGGER_RE`/`ENTITY_TRIGGER_RE`, `closePicker`, `handleChange`, `handleKeyDown` (Escape closes the picker, Enter submits when no stage), `popperOpen`, the absolute-positioned `Paper` listboxes). This is where the `/` trigger slots in.
- `carbon-frontend/src/shell/AIConversationView.jsx` — the main chat parent (already owns `exportConversation` ~L900; passes `mode`/`onModeChange`/`onMentionsChange` to `AIInputBar` ~L1381).
- `carbon-frontend/src/shell/DiscoveryComposer.jsx` — the agent-mode parent (reuses `AIInputBar`).
- `carbon-frontend/src/api/aiWorkspace.js` — `clearContext`, `checkpointConversation`, `forkConversation`, `exportConversation`, `summarizeConversation` (all already exist).
- `carbon-frontend/src/shell/KeyboardShortcutsHelp.jsx` — help surface for `/help`.
- `carbon-frontend/src/__tests__/AIInputBar.mentions.test.jsx` — the `#`-picker test pattern to mirror.

### Files to Change
- `carbon-frontend/src/shell/AIInputBar.jsx` — add the `/` trigger + command registry + listbox.
- `carbon-frontend/src/shell/AIConversationView.jsx` — wire `onCommand` to the existing context actions.
- `carbon-frontend/src/__tests__/AIInputBar.slash.test.jsx` (NEW) — command-menu tests.

### Command registry (source of truth in `AIInputBar.jsx`)
```js
const SLASH_COMMANDS = [
  { name: 'summarize',  kind: 'directive', label: 'Summarize this conversation so far', description: 'Ask for a summary of the thread' },
  { name: 'plan',       kind: 'directive', label: 'Plan a task to ',                  description: 'Draft a plan before anything runs' },
  { name: 'clear',      kind: 'action',    label: 'Clear working context',            description: 'Drop the in-progress context, keep history' },
  { name: 'checkpoint', kind: 'action',    label: 'Save a checkpoint',                description: 'Snapshot the current context' },
  { name: 'fork',       kind: 'action',    label: 'Fork this conversation',           description: 'Branch from a saved checkpoint' },
  { name: 'export',     kind: 'action',    label: 'Export conversation',              description: 'Download this thread as JSON' },
  { name: 'help',       kind: 'action',    label: 'Keyboard shortcuts',               description: 'Show Pulse shortcuts' },
];
```

### Implementation (exact seams — edit these and nothing else)

**1. `/` trigger + menu (`AIInputBar.jsx`).** Add a `slash` stage alongside the
existing mention stages. Trigger regex: `/(^|[\s\n])\/([a-zA-Z]*)$/` (a `/` at the
start of the input or after whitespace, followed by optional letters). On match:
set `stage='slash'`, record the partial query, clear mention state. Filter
`SLASH_COMMANDS` by `name.startsWith(query)` (case-insensitive). Render a `Paper`
`role="listbox"` (`aria-label="Commands"`) above the composer (same absolute
positioning as the `#` picker), listing each match as a `ListItemButton role="option"`
with the command label + `description` as secondary text. Keyboard parity with the
`#` picker: `Escape` closes, `Enter` selects when a command is highlighted — and
`Enter` still submits normally when no `/` menu is open. Selection:
- **directive** → replace the trailing `/partial` with the command `label` + a
  trailing space, keep focus in the textarea (user then types arguments + Enter).
- **action** → call `onCommand?.(name)`, clear the input, close the menu, refocus.
New optional prop `onCommand(name)`. When `onCommand` is absent, action commands
still render but selection is a no-op (graceful degradation) — do NOT crash.

**2. Wire actions (`AIConversationView.jsx`).** Pass `onCommand` to `AIInputBar`
that dispatches on `name` to the already-available API (all need `token` +
`conversationId`, both in scope): `clear` → `clearContext`, `checkpoint` →
`checkpointConversation(token, conversationId, {})`, `fork` →
`forkConversation(token, conversationId, null)`, `export` →
`exportConversation(token, conversationId, 'json')`, `help` → toggle a local
shortcuts dialog (render `KeyboardShortcutsHelp`). Wrap each in try/catch via
`notifyFromError` (already imported). `DiscoveryComposer` stays as-is (no `onCommand`;
its slash menu shows directives and no-ops actions).

**3. No backend, no new routes.** Everything is client-side; the `#` picker is
untouched and still works (the two triggers are mutually exclusive — a `/` match
must not also match a `#` match, and vice versa).

### DO NOT TOUCH
- `backend/**` — no changes.
- `#`-mention picker behavior — preserve it exactly (existing tests must stay green).
- No raw hex / inline spacing magic numbers (RULE_8) — theme tokens only.
- RULE_23 — command labels/descriptions are outcome copy, never engine terms.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npx vitest run src/__tests__/AIInputBar.slash.test.jsx src/__tests__/AIInputBar.mentions.test.jsx   # new + # regression
npm test -- --run          # all green
npm run lint               # 0 new errors
npm run build              # clean
```
Plus `get_errors` on the changed files.

### Output contract
- Typing `/` in the Pulse composer opens the command menu; directives insert text,
  actions trigger the existing context actions; `/` and `#` do not conflict.
- New unit tests: menu opens on `/`, filters by partial, directive inserts label,
  action calls `onCommand` and clears input, Escape closes, `/`+`#` are independent.
- Results note: test counts, lint/build status, any deviations.

---

### Phase W4-F — Skills-vs-reasoning decompose + deterministic mutation + plan-graph UX (DONE 2026-08-21)
**Date:** 2026-08-21
**Worker Role:** backend-worker + frontend-worker
**Recommended Model:** DeepSeek V4-Flash (RULE_24)
**Status:** DONE — VERIFIED (652 ai/tests; live decompose; E2E consent cycle 11/11; 31/31 graph tests + 9/9 card tests; browser-verified pan/zoom + expand modal)

**Part 1 — Planner: skills are capabilities, reasoning is the LLM's job (user design principle)**
- `planner.py` `_DECOMPOSE_AGENT_PROMPT`: now injects `{tools_list}/{skills_list}/{task}`; rules — `invoke_skill` only exact registered names, NEVER invent; reasoning steps get `tool_name: null` + `agent_role: "domain_specialist"`. Post-parse: unknown tool → `tool_name=None`; unregistered `invoke_skill` → downgraded to reasoning.
- `loop.py` `_execute_step`: `plan_source` param; named-tool step → that tool only; `single_step` → curated allow set; multi-step reasoning → `step_tools=None` (pure LLM).
- LIVE decompose proof: 4-step plan — [0][1] web_research parallel, [2] tool=None domain_specialist compare (depends_on 0,1), [3] export_document. No invented skill.

**Part 2 — Deterministic mutation classification (closes Fix-A regression)**
- LLM marked export `is_mutation=False` → would bypass the consent gate entirely. Fix: `planner._MUTATION_TOOL_NAMES = {"export_document"}` (capability fact) forced in BOTH `_llm_decompose` and `_parse_skill_plan`. Self-staging tools excluded (avoid double-gating): non-GET `call_host_api`, `create_dq_rule`, `learn_fact`, `forget_fact`, `run_ops_workflow`.
- Chain (deterministic): planner forces `is_mutation=True` → critic vetoes `mutation_not_confirmed` when `is_mutation and not confirmation_token and not dry_run` → loop converts veto → consent pause (token uuid4, paused=True, executed=False).
- Tests: `test_planner_reasoning_skills.py` 11 total (8 + 3 mutation). ai suite 652 passed. Live: `NEEDS_CONFIRMATION: True`, export `mutation=True`.
- E2E consent cycle (fresh plan `1845c38a-…`): 11/11 PASS — create → approve → run paused at export (no file) → confirm → resume → docx `comparison-of-top-carbon-footprint-accounting-systems-20260821-111356.docx` written to `backend/mediafiles/ai_exports/` only AFTER consent.

**Part 3 — Plan graph → directed EXECUTION graph (user feedback)**
- User: *"visual graph is not execution graph, like tensor flow thing. no directions, no detailed pane, etc."*
- `planGraph.js`: `layoutExecutionGraph(plan)` — longest-path ranks FROM sources (sources rank 0, edges always left→right), per-rank vertical centering, `EXEC_LAYOUT` consts, returns `{nodes(x/y/rank/phase_id), edges(sourceX/sourceY/targetX/targetY), width, height, phaseBands}`.
- `PlanDagGraph.jsx`: full rewrite — pure SVG, `<marker id="plan-arrow">` arrowheads (`marker-end` on every edge), bezier edges right-edge→left-edge, phase band lanes, node rects + status dot + tool label, click → detailed inspection pane (`data-testid="plan-step-detail"`: step #, status chip, intent, phase, tool or "None — pure reasoning step (LLM)", agent_role, depends-on, feeds-into, error), wheel zoom + Reset view. `ForceGraph.jsx` UNTOUCHED.
- Tests: `PlanDagGraph.test.jsx` (6) + `planGraph.test.js` (+4 `layoutExecutionGraph`) = 21/21 pass; `AITaskPlanCard.controls` 9/9; eslint 0 errors; browser DOM-verified (4 nodes ranks x=28/28/252/476, 3 edges all arrowheaded, 3 phase bands, detail pane works).

**Part 3b — Graph UX round 2: movable + resizable canvas, docked info card, full-screen expand (user feedback)**
- User: *"graph, not movable, resizable, no free style, info card not float. add expand to take the graph to max modal to see details"* → clarified: **"i want them, not no!"** — they DO want pan/zoom, just NOT free-form node dragging.
- `PlanDagGraph.jsx`: new shared `GraphCanvas` (inline + modal) — **drag-to-pan** (`pan` state, 3px threshold, `moved` ref suppresses node-click after drag) + **wheel-to-zoom** (native non-passive listener, clamp 0.35–2.2), cursor grab/grabbing, transform `translate(pan + centering) scale(zoom)`. Strict auto-layout kept (no node dragging — "no free style").
- **Info card DOCKED** (not floating): `renderDetailPane` shared inline (w 236) + modal (w 300) — flexShrink 0, borderLeft, own scroll.
- **Expand → full-screen modal**: `Dialog fullScreen` (`plan-graph-modal`) with own header (title/counts/Reset view/Close `plan-graph-modal-close`), canvas column (legend + `GraphCanvas fill markerId="plan-arrow-modal"`) + docked pane (`plan-step-detail-modal`). Unique marker id per SVG (no DOM collision). Reset view restores `zoom=1, pan=0` in both views.
- Tests: `PlanDagGraph.test.jsx` now 8 (+Reset view control, +expand modal flow with unique markers) → 23/23 graph tests, 9/9 card tests, eslint 0 errors; browser-verified live (node click → docked pane x=795 w=236; expand → full-screen 628×595; wheel scale 1→1.12; drag pan deltas; reset → translate(0,0) scale(1); modal close; 0 console errors).

**Part 3c — Graph UX round 3: one reusable ENTERPRISE graph surface (movable/resizable nodes, maximize/export, refined look)**
- User: *"the nodes them selves and the graph: i want it rich, not bulky, enterprise and professional, beautiful, no huge margins and fonts, check top systems and make it like"* → extract ONE shared surface; nodes THEMSELVES movable + resizable; status visible during execution; enterprise/Linear/Temporal density (not "rich but bulky").
- `EnterpriseGraph.jsx` (ADD, Layer-2 primitive): owns ALL interaction — canvas pan, **movable + resizable nodes** (per-node `{x,y,w,h}` overrides, bottom-right 9×9 handle, `DRAG_THRESHOLD` 3, `NODE_MIN/MAX` clamps), wheel + toolbar zoom in/out/fit (`clamp 0.25–3`), **redraw** (drops overrides + re-layout), **reset** (zoom=1/pan=0), **PNG export** (SVG→canvas 2×, jsdom no-op), **full-screen maximize modal**, **live status pulse** (`<animate>` on `running` nodes). Theme tokens only (RULE_8).
- `PlanDagGraph.jsx` (REWRITE as thin domain adapter): supplies `renderNode`/`sidebar`/`nodeColor`/`nodeAriaLabel`/legend/title/summary/marker ids. Node interior = **3px status accent bar** + intent (truncated) + **UPPERCASE status label** (right-aligned) + tool/kind meta. Detail pane now also shows `latency_ms`, `draft_text`, `critic_verdict`. `planStepStatusColor`/`planStepStatusLabel` exports unchanged.
- `planGraph.js`: `layoutExecutionGraph` now emits `w`/`h` per node (rides `EXEC_LAYOUT`); layout tightened — `nodeW 176, nodeH 44, colGap 48, rowGap 28, padX 24, padTop 36, padBottom 20`.
- **Enterprise look (top-systems density):** hairline `divider` border `rx=6` (primary 2px when selected), neutral `action.selected` fill on select, edges `divider` 1.25px, phase bands 9px label at opacity 0.05 — replaces the thick status border + 52×13 status pill.
- Toolkit: **ADR-0012** (`decisions/0012-enterprise-graph-canvas.md`) + `shared/design-patterns.md` Composite note (compose `EnterpriseGraph`, never hand-roll SVG pan/zoom/export). No new deps (extends ADR-0011).
- Tests: `planGraph.test.js` (+1 w/h) + `PlanDagGraph.test.jsx` (+7 `EnterpriseGraph interactions` describe: full toolbar, zoom changes transform, node drag moves, resize via `plan-dag-graph-resize-0` handle, redraw restores, running `<animate>`/completed none, RUNNING/FINISHED status labels) → **31/31 graph tests**, eslint 0 errors (2 pre-existing react-refresh warnings on the exported helpers).

**Files changed:** `backend/ai/engine/cognition/plan/planner.py`, `backend/ai/engine/cognition/plan/loop.py`, `backend/ai/tests/test_planner_reasoning_skills.py`, `backend/ai/tests/test_plan_loop_parallel.py`, `carbon-frontend/src/utils/planGraph.js`, `carbon-frontend/src/components/graph/PlanDagGraph.jsx`, `carbon-frontend/src/components/graph/EnterpriseGraph.jsx` (new), `carbon-frontend/src/__tests__/PlanDagGraph.test.jsx`, `carbon-frontend/src/__tests__/planGraph.test.js`, `.ai-toolkit/decisions/0012-enterprise-graph-canvas.md` (new), `.ai-toolkit/decisions/README.md`, `.ai-toolkit/shared/design-patterns.md`.

**DO NOT TOUCH:** `backend/ai/engine/agent/tools.py`, `agent/plugins.py`.

**Carry-forward (next):** resume-token investigation — fresh E2E showed resume re-executed ALL steps incl. completed ones (hypothesis: single shared `pending_steps[0].confirmation_token`; completed steps should feed `completed_ids` and be skipped on resume). Then W4-D (learning flywheel) + W4-E (observability).

---

## PLATFORM EXPANSION TRACK

Strict build order: **P1 → P2 → P4** (P3 may run in parallel with P2). Full
model, API, and pipeline detail lives in `docs/DESIGN-PLATFORM.md` §5–§8 — do not
duplicate it here; these entries are dispatch contracts that point at the spec.

---

### Phase P1 — Dataset Hub (`datahub/`)

**Status:** DONE — ACCEPTED (43 datahub tests; 373 combined `datahub accounts` passing; gates re-run independently by Master Architect)
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Spec:** `docs/DESIGN-PLATFORM.md` §5
**Kind:** New Django app. Large.

### Files to Read First
- `docs/DESIGN-PLATFORM.md` §5 (full models/API/pipeline spec)
- `backend/dq/jobs.py` — DQ integration seam (reuse, do not duplicate)
- `backend/catalog/` + `backend/mdm/` — existing table/data-row conventions
- `.ai-toolkit/shared/data-layer.md`, `api-contract.md`, `cbac.md`

### Files to Change
- `backend/datahub/models.py`, `backend/datahub/views.py`, `backend/datahub/serializers.py`, `backend/datahub/ingest.py`, `backend/datahub/urls.py`
- `backend/config/settings.py` + `urls.py` — register the app
- `backend/datahub/tests/` (≥20 tests)

### Implementation (summary — read §5 for the contract)
1. Models `Dataset`, `DatasetVersion`, `DataContract`, `DataContractViolation`, `DatasetAccessPolicy`.
2. API `/carbon-api/datahub/` (datasets CRUD, versions, approve/reject, contract, violations, ingest erp/upload) gated by `ReadAnyWriteAdmin`/`AdminOrSuperuserOnly`.
3. Ingest service (`ingest.py`): ERP/CSV → DataTable+DataRows, schema_snapshot, health_score, contract checks.
4. Health score = 0.4·completeness + 0.4·validity + 0.2·freshness.
5. DQ via existing `dq/jobs.py` (no duplicate DQ logic).

### DO NOT TOUCH
- `backend/dq/` job internals — call them, don't fork.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python -m pytest datahub -q   # ≥20 tests: create, version lifecycle, 3 contract-violation types, CBAC module isolation, access-policy override, ERP + CSV ingest
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- A Dataset is the unit of trust: no data flows to a model/app without an approved `DatasetVersion` + passing DQ run.

---

### Phase P2 — TurnKey Bridge (`integrations/turnkey/`)

**Status:** DONE — ACCEPTED (14 integrations tests; 373 combined `datahub accounts` passing; `manage.py check` + `makemigrations --check --dry-run` clean; gates re-run independently by Master Architect on 2026-08-18)
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Spec:** `docs/DESIGN-PLATFORM.md` §6
**Kind:** New integration app. Medium. (DevOps touches settings/keys at the end.)

### Files to Read First
- `docs/DESIGN-PLATFORM.md` §6
- Gigacast's `aihub/turnkey_client.py` (reference implementation — in sibling project)
- `.ai-toolkit/shared/api-contract.md`, `security.md` (Fernet + HMAC)

### Files to Change
- `backend/integrations/turnkey/models.py`, `client.py`, `views.py`, `urls.py`
- `backend/config/settings.py` — `FERNET_KEY` + `TURNKEY_CALLBACK_SECRET`
- `backend/integrations/turnkey/tests/` (≥6 tests)

### Implementation (summary — read §6 for the contract)
1. Models `TurnKeyConfig` (Fernet-encrypted API key), `TurnKeyModelLink`, `PredictionRecord`, `DriftAlert`.
2. `CarbonTurnKeyClient` (based on Gigacast `turnkey_client.py`).
3. Signed (HMAC-SHA256) callback endpoints: predictions + drift-alerts.
4. Settings `FERNET_KEY` + `TURNKEY_CALLBACK_SECRET` (env, never hardcoded).

### DO NOT TOUCH
- TurnKey's own serving code — this is a client/bridge only.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python -m pytest integrations -q   # ≥6: signature 401, prediction record, drift→DQ+violation, key encrypted at rest, feedback loop, CBAC view
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- HMAC secret + Fernet key MUST be env-provided (project.config RULE); never commit real values.
- **Carry-forward gap (verified 2026-08-18):** `accounts/constants.py` gained `DATAHUB_LEAD_GROUP` (P1) and `capabilities.py` gained `turnkey_lead` (P2), but `bootstrap_platform.py` `GROUP_DEFS` was NOT updated — on a fresh bootstrap the `datahub_lead` / `turnkey_lead` Django Groups are never created, so those roles can't be assigned. Tracked as **Phase P2-F** below.

---

### Phase P2-F — Bootstrap group parity (`datahub_lead` + `turnkey_lead`)

**Status:** DONE — ACCEPTED (bootstrap parity verified; `manage.py check` clean; `pytest accounts -q` + `pytest datahub accounts -q` green; `manage.py bootstrap_platform` reports groups up-to-date)
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Kind:** Small bugfix (~15 min). Closes the gap left by P1 + P2.

### Files to Read First
- `backend/accounts/constants.py` (note `DATAHUB_LEAD_GROUP` exists, `TURNKEY_LEAD_GROUP` does NOT)
- `backend/accounts/capabilities.py` (`GROUP_CAPABILITIES` already declares `datahub_lead` + `turnkey_lead`)
- `backend/accounts/management/commands/bootstrap_platform.py` (`GROUP_DEFS`, `_app_id_for_group`)

### Files to Change
- `backend/accounts/constants.py` — add `TURNKEY_LEAD_GROUP = "turnkey_lead"`; add it to `DOMAIN_LEAD_GROUPS`
- `backend/accounts/management/commands/bootstrap_platform.py` — add `datahub_lead` + `turnkey_lead` to `GROUP_DEFS` (category `"app"`, `is_protected=True`, `is_scoped=True`, same shape as `dq_lead`); update the import line to include `DATAHUB_LEAD_GROUP, TURNKEY_LEAD_GROUP`

### Implementation
- `_app_id_for_group` already derives `datahub_lead → datahub` and `turnkey_lead → turnkey` via its `split("_")[0]` fallback — no change needed there. Only `GROUP_DEFS` + constants need updating.
- Idempotent: bootstrap is INSERT-OR-UPDATE, safe to re-run.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python -m pytest accounts -q
# Manual: PGPASSWORD=AdminPa_132 PGUSER=ahmed /home/ahmed/aast/carbon/.venv/bin/python manage.py bootstrap_platform
#   → output lists datahub_lead + turnkey_lead among groups (created or up-to-date)
```

### Output contract
Append to `TASK-RESULTS.md`.

---

### Phase P3 — App Registry (`appregistry/`)

**Status:** DONE — ACCEPTED (appregistry + accounts + datahub + ai regression suites verified; `manage.py check` clean)
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Spec:** `docs/DESIGN-PLATFORM.md` §7
**Kind:** New Django app. Small-medium. **May run in parallel with P2.**

### Files to Read First
- `docs/DESIGN-PLATFORM.md` §7
- `backend/accounts/ai_scoping.py` — GuardChain `Scope` injection point
- `.ai-toolkit/shared/cbac.md`

### Files to Change
- `backend/appregistry/models.py`, `views.py`, `urls.py`, management command
- `backend/accounts/ai_scoping.py` — inject `active_apps` into Scope
- `backend/appregistry/tests/` (≥5 tests)

### Implementation (summary — read §7 for the contract)
1. Models `AppManifest` + `AppActivation`.
2. API `/api/v1/apps/` (list/detail/activate/deactivate; non-system apps only).
3. Self-registration management command (e.g. `register_healthy_app`).
4. GuardChain integration: inject `active_apps` into Scope (`accounts/ai_scoping.py`).

### DO NOT TOUCH
- CBAC enforcement boundaries in `accounts/` — add a source, don't weaken the rail (ADR-0007).

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python -m pytest appregistry -q   # ≥5 tests
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- The control plane for domain apps: declares apps, required modules/capabilities, activation state.

---

### Phase P4-A — Healthy Domain App: backend (`healthy/`)

**Status:** DONE — ACCEPTED (35 healthy tests; `manage.py check` + `makemigrations --check --dry-run` + `migrate healthy` clean; commit `38f8def`)
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Spec:** `docs/DESIGN-PLATFORM.md` §8
**Kind:** New Django app. Large.
**Depends on:** P1 (dataset hub), P3 (app registry).

### Files to Read First
- `docs/DESIGN-PLATFORM.md` §8
- `backend/datahub/` (P1) + `backend/appregistry/` (P3) — the seams Healthy uses
- `backend/ai/protocol.py` + `ai/domain/` — `DomainAIOperations` ABC pattern
- `.ai-toolkit/shared/data-layer.md`, `cbac.md`

### Files to Change
- `backend/healthy/models.py` (`ERPSnapshot`, `LoadoutSheet`, `RepHealthCard`), read-only `DataSource` to Azure PostgreSQL, 5 modules (healthy-sales/returns/inventory/collections/production, CBAC via ScopedRole), 5 pipelines, `domain_ai.py` (`HealthyDomainAI`), `views.py`, `urls.py`
- `backend/healthy/tests/` (≥10 tests)

### Implementation (summary — read §8 for the contract)
1. Read-only `DataSource` to Azure PostgreSQL (legacy Arabic ERP, 1,047 decoded views).
2. Modules + 5 pipelines: returns/load-out forecast, churn/rep retention, demand forecast (dead-stock), AR collections prioritization, transaction-type classifier.
3. `HealthyDomainAI` via the `DomainAIOperations` ABC; API `/api/v1/healthy/`.

### DO NOT TOUCH
- Azure PostgreSQL source is **read-only** — no writes to the ERP.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python -m pytest healthy -q   # ≥10 tests
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- P4-A before P4-B. ERP stays read-only; writes only to Carbon models.

---

### Phase P4-B — Healthy Domain App: frontend

**Status:** DONE — ACCEPTED (`d333d8c`) — 27 healthy-screen tests pass; `npm run lint` 0 errors; `npm run build` green. 5 screens + `api/healthy.js` (11 `apiFetch` helpers) + routes/studio/sidebar wiring. DataGrid rows keyed via `getRowId` (`prediction_id` fallback) to satisfy MUI X unique-id.
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Spec:** `docs/DESIGN-PLATFORM.md` §11
**Kind:** Frontend-only. Medium-large.
**Depends on:** P4-A (endpoints) — ✅ DONE (`38f8def`, `/carbon-api/healthy/` live).

### Files to Read First
- `docs/DESIGN-PLATFORM.md` §8 + §11
- `carbon-frontend/src/` — existing DataGrid/table + dashboard patterns
- `.ai-toolkit/shared/design-system.md`

### Files to Change
- `carbon-frontend/src/` healthy screens: loadout, rep health, AR queue, slow movers, dashboard
- API helpers + tests

### Implementation
1. Screens: loadout sheet, rep health cards, AR collections queue, slow movers, dashboard.
2. Theme tokens only (RULE_8); route + sidebar entries.

### DO NOT TOUCH
- Backend files.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run   # healthy-screen tests pass
npm run build
```

### Output contract
Append to `TASK-RESULTS.md`.

### Notes for the Master
- P4-A first. Healthy is the end-to-end proof: dataset → DQ review → approve → TurnKeyModelLink → prediction → drift → violation.

---

## BACKLOG (unsequenced)

| Item | Worker | Notes |
|---|---|---|
| DQ rule contradiction detection | backend-worker | Detect two *different* rules on the same field that can't both pass (disjoint `range`/`allowed_values` intervals); warn on redundant overlap (duplicate `not_null`, `unique`+`not_null`); emit a composite "conflict" verdict at runtime for semantically-undecidable overlaps (e.g. `nl_check` vs `regex`). Semantic layer on top of the existing rule-type ↔ field-type applicability check. |
| Production v1.3 tag + deploy | devops-worker | After final QA gate. Tag + deploy per `docs/DEPLOYMENT_PLAN_AASTMT_CARBON.md`. |

---

## Sprint W5 — Pulse Chat/Agent Mode Split + Agentic Lifecycle Completion

> **Architect note:** ADR-0014 (`decisions/0014-pulse-chat-agent-mode-split.md`) governs
> all W5 phases. Read it before dispatching any worker. Phases are ordered — W5-A first,
> then B, C, D in any order, E last. F-21 and F-22 (migration blockers) must be fixed
> before B and C can be integration-tested against the live backend.

---

### Phase W5-A — Chat / Agent mode split at workspace level

**Status:** DONE
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Kind:** Frontend-only. Medium. No backend changes.
**Depends on:** none (pure UI refactor)

#### Goal
Make Chat and Agent the two top-level modes in Pulse. Remove the `Ask/Agent` pill
from `AIInputBar`. Add mode buttons to `AIWorkspaceHeader`. Persist mode. Reshape the
workspace so each mode shows only its relevant surface. Add the always-visible safety
contract text to the header.

#### Files to Read First
- `.ai-toolkit/decisions/0014-pulse-chat-agent-mode-split.md` — the binding decision
- `carbon-frontend/src/shell/AIWorkspace.jsx` — routing + panel switching
- `carbon-frontend/src/shell/AIWorkspaceHeader.jsx` — header component
- `carbon-frontend/src/shell/AIInputBar.jsx` — remove Ask/Agent pill from here
- `carbon-frontend/src/shell/AITaskPanel.jsx` — agent mode host
- `.ai-toolkit/shared/compact-ui.md` — density rules
- `.ai-toolkit/shared/design-system.md`

#### Tasks

**T1 — `AIWorkspaceHeader.jsx`: add Chat / Agent mode buttons**
- Add `mode` prop (`'chat'|'agent'`) and `onModeChange` callback
- Render two compact ToggleButtons (`💬 Chat` | `🤖 Agent`) in the header toolbar (left of the close button)
- Render the safety contract text as a `Typography caption` beside the mode buttons — text varies per `mode` + `agentLifecycleState` prop (idle / plan_pending / running / consent_needed / done)
- Theme tokens only (RULE_8); compact density (RULE_3)

**T2 — `AIWorkspace.jsx`: workspace-level mode state**
- Add `mode` state, persisted to `localStorage` under key `carbon-ai-mode` (default `'chat'`)
- Pass `mode` and `onModeChange` to `AIWorkspaceHeader`
- Chat mode: render existing conversation surface (no change to current chat path)
- Agent mode: render `AITaskPanel` as the primary area (no conversation view)
- Remove the `activePanel === 'tasks'` branch from the activity-bar panel switch — Tasks is now Agent mode, not a panel
- Activity bar in Chat mode: Sessions / Context / Investigate / Artifacts / Memory / Usage / Settings (unchanged)
- Activity bar in Agent mode: only agent-relevant icons — Tasks (plan list) · Run · Monitor (placeholder for W5-D) · Results (placeholder for W5-D) · Audit
- Pass `agentLifecycleState` down from `AITaskPanel` via a callback so the header shows the correct contract text

**T3 — `AIInputBar.jsx`: remove mode pill**
- Delete the `Ask / Agent` ToggleButton group (the `<Box role="group" aria-label="Composer mode">` block) and its associated `mode` + `onModeChange` props
- The mode hint text below the composer (`Ask = advisory …`) is also removed
- Keep all other composer logic unchanged

**T4 — `AITaskPanel.jsx`: emit lifecycle state to workspace**
- Add `onLifecycleStateChange` prop
- Call it whenever `phase` changes: map `{idle,working,paused,finished,stopped,error}` + `plan.status` → `{idle,plan_pending,running,consent_needed,done,error}`
- No other changes to AITaskPanel logic

#### DO NOT TOUCH
- Backend files
- `AIConversationView.jsx`, `AIConversationTabs.jsx`, `AIEmptyState.jsx`
- Any existing test file content (update test assertions only if a changed prop breaks them)
- Route paths, API endpoints, `aria-label` values used in E2E selectors

#### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint                  # 0 errors
npx vitest run                # existing passing tests still pass; new mode tests pass
npm run build                 # clean build
```

Also manually verify in the browser:
- Opening Pulse shows Chat mode by default
- Clicking Agent switches to AITaskPanel; clicking Chat switches back
- Mode persists across close/reopen
- Header contract text changes correctly as agent lifecycle progresses
- No Ask/Agent pill in the composer

#### Output contract
Append results to `TASK-RESULTS.md`.

---

### Phase W5-B — Agent mode: guided discovery conversation before plan creation

**Status:** DONE
**Worker Role:** backend-worker THEN frontend-worker (two sub-phases, same spec)
**Recommended Model:** DeepSeek V4-Flash
**Kind:** Backend (Django service + API) + Frontend. Medium-large.
**Depends on:** W5-A (mode split — brief view needs the new agent workspace layout)
**Blocked by:** F-21 + F-22 (migration/boot blockers) — fix those first

#### Goal
Replace the current "brief → immediate LLM decompose → plan" flow with a multi-turn
guided discovery conversation. Pulse first asks clarifying questions, collects requirements,
then proposes a structured plan for review. Eliminates F-23.

#### Backend sub-phase

**Files to Read First**
- `backend/ai/plans_service.py` — `create_plan`, `PlansService`
- `backend/ai/plans_api.py` — `PlanViewSet.create`
- `backend/ai/models/core.py` — `Run`, `RunStep`
- `backend/ai/workspace_api.py` — existing conversation flow for reference
- `.ai-toolkit/shared/ai-contract.md` — RULE_21 (no auto-mutation)

**Tasks**

B1 — `backend/ai/plans_service.py`: add `start_discovery` and `advance_discovery`
- `start_discovery(user, brief, conversation_id='')` → creates a `Run` with `status='discovering'` and `plan_json={'discovery_turns': [], 'brief': brief}`; returns the first Pulse question as a `discovery_turn` frame
- `advance_discovery(user, plan_id, user_reply)` → appends the reply to `discovery_turns`, calls the LLM to either ask the next question OR declare discovery complete and generate a full plan; returns `{'status': 'needs_input'|'plan_ready', 'question': str|None, 'plan': dict|None}`
- When `status='plan_ready'`: calls `SkillAwarePlanner.decompose` with the enriched brief (original brief + discovery answers) and transitions the Run to `status='pending_approval'`
- Add `STATUS_DISCOVERING = 'discovering'` to the service constants

B2 — `backend/ai/plans_api.py`: new discovery endpoints
- `POST /plans/{id}/discover/` — `PlanViewSet.advance_discovery`: accepts `{'reply': str}`, delegates to `PlansService.advance_discovery`, returns `{'status', 'question', 'plan'}`
- `POST /plans/` already creates the Run via `create_plan`; add a `discovery_mode=True` optional flag so the frontend can start in discovery mode
- Guard: discovery endpoints only callable when `run.status == 'discovering'`

B3 — `backend/ai/plans_urls.py`: register the new route
- Add `POST /{id}/discover/` before the existing action routes

**Backend Verification Gate**
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_plans.py -q
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
```
Add at least 3 tests to `ai/tests/test_plans.py`:
- `test_discovery_start_returns_question`
- `test_discovery_advance_continues_or_completes`
- `test_discovery_complete_transitions_to_pending_approval`

#### Frontend sub-phase

**Files to Read First**
- `carbon-frontend/src/shell/AITaskPanel.jsx` — current Tasks tab composer
- `carbon-frontend/src/api/aiWorkspace.js` — plans API helpers
- `.ai-toolkit/shared/design-system.md`
- `.ai-toolkit/shared/compact-ui.md`

**Tasks**

F1 — `carbon-frontend/src/api/aiWorkspace.js`: add discovery API helpers
- `startDiscoveryPlan(token, { brief, conversation_id })` → `POST /ai/plans/` with `discovery_mode: true`
- `advanceDiscovery(token, planId, reply)` → `POST /ai/plans/{id}/discover/` with `{ reply }`

F2 — `carbon-frontend/src/shell/AITaskPanel.jsx`: Brief view with discovery conversation
- Replace the static `<TextField>` + "Create plan" button in the Tasks tab with a `DiscoveryComposer`:
  - User types their outcome
  - On submit: calls `startDiscoveryPlan` → renders the first question from Pulse as a message bubble
  - User replies in the same input → calls `advanceDiscovery` → renders next question or transitions to the Plan view
  - While `status === 'needs_input'`: show conversation bubbles (Pulse question + user reply history)
  - When `status === 'plan_ready'`: show "Plan ready — review below" banner and render `AITaskPlanCard`
- Style: compact message bubbles, same visual density as `AIConversationView` but simpler (no full message toolbar)
- No raw JSON; questions and replies render as plain text bubbles

#### DO NOT TOUCH
- `backend/ai/engine/` — call public seams only
- `backend/ai/models/core.py` — `Run.status` choices list must be extended but do NOT change existing statuses
- Any existing test files beyond the new tests specified above

#### Output contract
Append results to `TASK-RESULTS.md`.

---

### Phase W5-C — Artifact delivery: storage, API, and semantic output rendering

**Status:** DONE ✅ (2026-08-22)
**Worker Role:** backend-worker THEN frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Kind:** Backend (model + service + API) + Frontend (renderer). Large.
**Depends on:** W5-A
**Blocked by:** F-21 + F-22 (fix first)

#### Goal
Give the agent workflow a first-class artifact delivery mechanism: steps that produce
files (Word, Excel, CSV, JSON reports) store them durably and expose download links.
Step outputs are rendered semantically (not as raw JSON `<pre>` blocks). Eliminates F-24 and F-25.

#### Backend sub-phase

**Files to Read First**
- `backend/ai/models/core.py` — `Run`, `RunStep`
- `backend/ai/plans_service.py` — `_serialize_run`, step serialization
- `backend/ai/plans_api.py` — step output shape
- `backend/config/settings.py` — `MEDIA_ROOT`, `MEDIA_URL`
- `backend/ai/plugins/export_document.py` — existing export plugin (reuse its logic)

**Tasks**

B1 — `backend/ai/models/core.py`: add `RunArtifact` model (NEW — justified migration)
```python
class RunArtifact(models.Model):
    run       = models.ForeignKey(Run, on_delete=models.CASCADE, related_name='artifacts')
    step_index = models.IntegerField(null=True)
    name      = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    file      = models.FileField(upload_to='ai_artifacts/%Y/%m/')
    size_bytes = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['created_at']
```
- Migration: `backend/ai/migrations/0020_runartifact.py`
- Do NOT use `AppScopeMixin` here (artifact is scoped via `run.host_user_id`)

B2 — `backend/ai/plans_service.py`: artifact storage helper
- `store_artifact(run_id, step_index, name, content_bytes, mime_type)` → saves to `MEDIA_ROOT/ai_artifacts/`, creates `RunArtifact`, returns `{'artifact_id', 'name', 'size_bytes', 'download_url'}`
- Expose `download_url` as `/carbon-api/ai/plans/{run_id}/artifacts/{artifact_id}/download/`
- Wire the `export_document` plugin to call `store_artifact` after generating a docx/xlsx

B3 — `backend/ai/plans_api.py`: artifact endpoints
- `GET /plans/{id}/artifacts/` → list `RunArtifact` rows for the plan
- `GET /plans/{id}/artifacts/{artifact_id}/download/` → `FileResponse` (streaming, Content-Disposition: attachment)
- Both endpoints are owner-scoped (same CBAC as the rest of plans_api)

B4 — `_serialize_run` + `_serialize_step`: add artifact links to step payload
- Each step's serialized form gains: `'artifacts': [{'id', 'name', 'mime_type', 'size_bytes', 'download_url'}]`
- `tool_output` gains an `'_output_type'` field: `'text'|'table'|'chart'|'artifact'|'json'` — the service infers this from the output shape; frontend uses it to pick the renderer

**Backend Verification Gate**
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python manage.py migrate
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_plans.py ai/tests/test_artifacts.py -q
```
Add `ai/tests/test_artifacts.py` with at least 4 tests:
- `test_store_artifact_creates_file_and_record`
- `test_artifact_list_endpoint_owner_scoped`
- `test_artifact_download_streams_file`
- `test_cross_user_artifact_access_denied`

#### Frontend sub-phase

**Files to Read First**
- `carbon-frontend/src/shell/AITaskPanel.jsx` — `StepCard`, `renderJson`
- `carbon-frontend/src/api/aiWorkspace.js` — plan API helpers
- `carbon-frontend/src/shell/AITaskAuditCard.jsx`
- `.ai-toolkit/shared/design-system.md`

**Tasks**

F1 — new `carbon-frontend/src/components/ai/StepOutputRenderer.jsx`
A pure component that takes `{ outputType, value }` and renders:
- `'text'` → `Typography` with `white-space: pre-wrap`; no `<pre>` block
- `'table'` → `Table` (MUI) with first-row header detection; max 10 rows, "show more" accordion
- `'artifact'` → artifact card: file icon + name + size + `[Download]` button (calls download URL via `apiFetch` with `responseType: blob`)
- `'chart'` → Sparkline or simple bar (reuse existing `StatCard` pattern); fallback to table if chart data is malformed
- `'json'` → collapsible `<pre>` block labelled "Raw output" — hidden by default, toggle to show
- `null` / unknown → nothing (no output yet)

F2 — `carbon-frontend/src/shell/AITaskPanel.jsx`: replace `renderJson` with `StepOutputRenderer`
- In `StepCard`: replace `{renderJson('Output', step.tool_output)}` with `<StepOutputRenderer outputType={step.output_type} value={step.tool_output} />`
- In `StepCard`: replace `{renderJson('Input', step.tool_args)}` with a collapsible "Input parameters" section that shows key→value rows, not raw JSON
- Add artifact card below each step if `step.artifacts?.length > 0`

F3 — `carbon-frontend/src/api/aiWorkspace.js`: artifact helpers
- `listPlanArtifacts(token, planId)` → `GET /ai/plans/{id}/artifacts/`
- `downloadArtifact(token, planId, artifactId)` → `GET /ai/plans/{id}/artifacts/{id}/download/` → returns a blob URL

#### DO NOT TOUCH
- `backend/ai/engine/`
- Existing `export_document` plugin logic beyond the `store_artifact` call addition

#### Output contract
Append results to `TASK-RESULTS.md`.

---

### Phase W5-D — Agent mode Monitor + Results views

**Status:** DONE ✅ (2026-08-22)
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Kind:** Frontend-only. Medium. No new backend endpoints needed (uses existing ledger + artifacts).
**Depends on:** W5-A, W5-C (artifacts needed for Results view)

#### Goal
Add two missing views to agent mode: a live Monitor tab (metrics during/after run) and a
Results tab (artifacts grid + output summary + rerun/fork). Partially addresses F-27.

#### Files to Read First
- `carbon-frontend/src/shell/AITaskPanel.jsx` — current tab structure, phase state
- `carbon-frontend/src/shell/AITaskAuditCard.jsx` — usage stats shape (reuse)
- `carbon-frontend/src/api/aiWorkspace.js` — `getPlanLedger`, `listPlanArtifacts`
- `.ai-toolkit/shared/design-system.md`
- `.ai-toolkit/shared/compact-ui.md`

#### Tasks

**T1 — `AITaskPanel.jsx`: add Monitor and Results internal tabs**
Current tabs: `tasks | run | templates`
New tabs: `tasks | run | monitor | results | templates`

RULE_17: persist selected tab to `localStorage` key `carbon-ai-task-tab` (already exists — extend the valid values).

**T2 — Monitor tab** (`renderMonitor()` function in AITaskPanel)
Renders when `tab === 'monitor'`. Shows:
- Header: "Monitor" + current plan status chip
- Live metrics grid (reuse `AITaskAuditCard` Stat layout):
  - Duration (elapsed from plan `created_at` to now or `completed_at`)
  - Steps completed / total
  - Steps failed / skipped
  - Token usage (from ledger `usage.total_tokens`)
  - LLM calls (from ledger `usage.total_llm_calls`)
  - Estimated cost (tokens × DeepSeek V4-Flash rate from config or hardcoded constant)
  - Latency per step (min / max / avg from ledger steps)
- Step health table: step_id | intent (truncated) | status chip | latency_ms
- Auto-loads ledger when `phase === 'finished'|'paused'|'stopped'|'error'`; polls every 5s when `phase === 'working'`
- Empty state when no plan selected

**T3 — Results tab** (`renderResults()` function in AITaskPanel)
Renders when `tab === 'results'`. Shows:
- Only rendered after `phase === 'finished'` (otherwise shows "Run the plan to see results")
- Final response card: ledger `final_response` as formatted text (not JSON)
- Artifacts grid: calls `listPlanArtifacts` and renders one card per artifact
  - File icon (by mime_type: 📄 docx/pdf, 📊 xlsx/csv, 🗄 json, 📁 other)
  - Name + size
  - `[Download]` button
  - `[Preview]` for text/csv (shows first 20 lines in a collapsible)
- Rerun button: calls `approvePlan` (if `approved`) or shows disabled with tooltip
- Fork button: calls `forkPlan` → opens the forked plan in the Tasks tab
- Share / Export button: exports the ledger as JSON or the final_response as a `.md` file

**T4 — Activity bar in Agent mode**: wire Monitor and Results icons
- `📊` icon → sets `tab = 'monitor'`
- `📦` icon → sets `tab = 'results'`
- These replace the `usage` and `artifacts` activity-bar icons when in Agent mode

#### DO NOT TOUCH
- Backend files
- Chat mode components

#### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run    # existing tests pass; add tests for Monitor + Results render
npm run build
```
Add to `src/__tests__/AITaskPanel.w3c.test.jsx` or a new file:
- `test_monitor_tab_renders_metrics_from_ledger`
- `test_results_tab_renders_artifacts_and_final_response`
- `test_results_tab_shows_placeholder_before_run_completes`

#### Output contract
Append results to `TASK-RESULTS.md`.

---

### Phase W5-E — EnterpriseGraph drag visual bug fix + agent mode run graph prominence

**Status:** DONE ✅ (2026-08-22)
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Kind:** Frontend-only. Small-medium.
**Depends on:** W5-A (agent mode layout established)

#### Goal
Fix the node drag visual break (QA finding from Round 2) and make the execution graph
a prominent, always-visible feature of Agent mode Run view rather than hidden below fold.

#### Root cause (already diagnosed — do NOT re-investigate)
`EnterpriseGraph.jsx` `onMouseMove` drag handler stores only `{x, y}` when moving
(drops `w`, `h`) and only `{w, h}` when resizing (drops `x`, `y`).
`effectiveNodes` uses `{ ...n, ...o }` spread which IS correct, but `drag.current.origW`
and `drag.current.origH` are taken from `node.w` / `node.h` at drag-start — if those are
already `undefined` from a previous drag, the second drag stores `{origW: undefined}` and
`clamp(undefined + dx, …)` → `NaN`.

The fix: at drag-start, snapshot `w`/`h` from `effectiveNodes` (the merged value),
not from the raw `node` prop. Same for `x`/`y` at resize-start.

#### Files to Read First
- `carbon-frontend/src/components/graph/EnterpriseGraph.jsx` — `startNodeDrag`, `startResize`, `drag.current` snapshot
- `carbon-frontend/src/__tests__/PlanDagGraph.test.jsx` — existing drag/resize tests
- `.ai-toolkit/decisions/0012-enterprise-graph-canvas.md` — ADR-0012 Decision 3

#### Tasks

**T1 — `EnterpriseGraph.jsx`: fix drag origin snapshot**
In `startNodeDrag`:
```js
// BEFORE (reads raw layout node — w/h may be stale after a prior resize):
drag.current = { mode: 'node', id: node.id, startX: e.clientX, startY: e.clientY, origX: node.x, origY: node.y };

// AFTER (read from effectiveNodes so post-resize w/h are included):
const en = nodeById.get(node.id) || node;
drag.current = { mode: 'node', id: node.id, startX: e.clientX, startY: e.clientY, origX: en.x, origY: en.y };
```

In `startResize`:
```js
// BEFORE:
drag.current = { mode: 'resize', id: node.id, startX: e.clientX, startY: e.clientY, origW: node.w, origH: node.h };

// AFTER:
const en = nodeById.get(node.id) || node;
drag.current = { mode: 'resize', id: node.id, startX: e.clientX, startY: e.clientY, origW: en.w ?? node.w, origH: en.h ?? node.h };
```

Note: `nodeById` is already computed from `effectiveNodes` in the same component — use it directly.

**T2 — `PlanDagGraph.jsx`: make the graph prominent in Run view**
Current: plan graph lives inside `AITaskPlanCard`, below the step list, as a `height=300` embedded card.
Change: when `live === true` (run is active), render the graph at `height=420` and position it ABOVE the step stream, so users see execution progress at a glance without scrolling.
Pass `fill={false}` (existing prop, keeps the fixed height); no layout changes to EnterpriseGraph itself.

**T3 — Regression tests**
Add to `src/__tests__/PlanDagGraph.test.jsx`:
- `test_drag_after_resize_keeps_correct_position` — drag a node, resize it, drag again; position should not be NaN
- `test_resize_after_drag_keeps_correct_dimensions` — resize, drag, resize again; dimensions should not be NaN

#### DO NOT TOUCH
- `backend/` files
- `planGraph.js` layout logic
- `ForceGraph.jsx`

#### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run    # PlanDagGraph.test.jsx — all tests including new regression tests pass
npm run build
```

Manual browser check in Agent mode:
- Move a node, then resize it, then move it again → no visual break
- Resize after move → no visual break

#### Output contract
Append results to `TASK-RESULTS.md`.

---

## Sprint W5 — Worker Activation Prompts

### W5-A: Frontend Worker
```
Your role is frontend-worker for Carbon.
1. Read .ai-toolkit/project.config.md
2. Read .ai-toolkit/shared/base-rules.md
3. Read .ai-toolkit/roles/frontend-worker.md
4. Read .ai-toolkit/decisions/0014-pulse-chat-agent-mode-split.md
5. Read TASKS.md — Phase W5-A (Chat / Agent mode split)
Confirm your role and begin. Model: DeepSeek V4-Flash.
```

### W5-B: Backend Worker (run first)
```
Your role is backend-worker for Carbon.
1. Read .ai-toolkit/project.config.md
2. Read .ai-toolkit/shared/base-rules.md
3. Read .ai-toolkit/roles/backend-worker.md
4. Read .ai-toolkit/decisions/0014-pulse-chat-agent-mode-split.md
5. Read TASKS.md — Phase W5-B backend sub-phase (discovery conversation)
Confirm your role and begin. Model: DeepSeek V4-Flash.
NOTE: F-21 and F-22 (migration blockers) must be resolved before running migrate.
```

### W5-B: Frontend Worker (after backend W5-B is done)
```
Your role is frontend-worker for Carbon.
1. Read .ai-toolkit/project.config.md
2. Read .ai-toolkit/shared/base-rules.md
3. Read .ai-toolkit/roles/frontend-worker.md
4. Read .ai-toolkit/decisions/0014-pulse-chat-agent-mode-split.md
5. Read TASKS.md — Phase W5-B frontend sub-phase (discovery composer)
Confirm your role and begin. Model: DeepSeek V4-Flash.
```

### W5-C: Backend Worker (run first)
```
Your role is backend-worker for Carbon.
1. Read .ai-toolkit/project.config.md
2. Read .ai-toolkit/shared/base-rules.md
3. Read .ai-toolkit/roles/backend-worker.md
4. Read TASKS.md — Phase W5-C backend sub-phase (artifact storage + API)
Confirm your role and begin. Model: DeepSeek V4-Flash.
```

### W5-C: Frontend Worker (after backend W5-C is done)
```
Your role is frontend-worker for Carbon.
1. Read .ai-toolkit/project.config.md
2. Read .ai-toolkit/shared/base-rules.md
3. Read .ai-toolkit/roles/frontend-worker.md
4. Read TASKS.md — Phase W5-C frontend sub-phase (StepOutputRenderer + artifact cards)
Confirm your role and begin. Model: DeepSeek V4-Flash.
```

### W5-D: Frontend Worker
```
Your role is frontend-worker for Carbon.
1. Read .ai-toolkit/project.config.md
2. Read .ai-toolkit/shared/base-rules.md
3. Read .ai-toolkit/roles/frontend-worker.md
4. Read TASKS.md — Phase W5-D (Monitor + Results views)
Confirm your role and begin. Model: DeepSeek V4-Flash.
Depends on: W5-A and W5-C frontend done.
```

### W5-E: Frontend Worker
```
Your role is frontend-worker for Carbon.
1. Read .ai-toolkit/project.config.md
2. Read .ai-toolkit/shared/base-rules.md
3. Read .ai-toolkit/roles/frontend-worker.md
4. Read .ai-toolkit/decisions/0012-enterprise-graph-canvas.md
5. Read TASKS.md — Phase W5-E (graph drag fix + run graph prominence)
Confirm your role and begin. Model: DeepSeek V4-Flash.
Can be run in parallel with W5-D.
```

---

## FLIGHT DIRECTOR TRACK

Supervisor layer for the plan-execution pipeline (Pulse): validates QoS against
the brief, reconciles cross-step state, repairs gracefully, collects verified
results, closes with evidence. Full design (authoritative):
`docs/DESIGN-FLIGHT-DIRECTOR.md` — read it FIRST before any phase below.

Dispatch order: **25-A → 25-B → 25-C → 25-D → 25-E** (each phase's green gate
must pass and be reviewed before the next dispatches). **26** (frontend) is
optional — dispatch only after 25-E passes and budget allows.

Every phase keeps the existing suite green: `pytest dq -q --maxfail=5` (38
tests in `dq/tests/test_api.py`) + `pytest ai -q --maxfail=5` + `manage.py
check` + `makemigrations --check --dry-run`. NEVER docker, NEVER `source
venv`; run from `backend` with `/home/ahmed/aast/carbon/.venv/bin/python`.

---

### Phase 25-A — FlightDirector schema (AcceptanceReport + LearningOutcome)

**Date:** 2026-08-24
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE (commit `b177d88`)
**Kind:** Backend-only. Small.
**Depends on:** — (schema first)
**Spec:** `docs/DESIGN-FLIGHT-DIRECTOR.md` §2

#### Files to Read First
- `backend/ai/models/core.py` — existing `Run`, `RunStep`, `PlanTemplate` models (field conventions, `AppScopeMixin`, `generate_uuid`)
- `backend/ai/models/__init__.py` — re-export pattern
- `backend/ai/admin.py` — registration pattern
- `backend/ai/migrations/` — latest migration number (expect 0021 → create 0022)
- `docs/DESIGN-FLIGHT-DIRECTOR.md` §2 (model table)
- `.ai-toolkit/shared/data-layer.md` + `base-rules.md`

#### Files to Change
- `backend/ai/models/core.py` — ADD `AcceptanceReport(AppScopeMixin)` and `LearningOutcome(AppScopeMixin)` exactly per spec §2 (fields, FKs, `UniqueConstraint(run, pattern)` on LearningOutcome, `app_label = "ai"`)
- `backend/ai/models/__init__.py` — re-export both models
- `backend/ai/admin.py` — register both (read-only list views)
- `backend/ai/migrations/0022_flight_director.py` — GENERATED (never hand-write)
- `backend/ai/tests/test_flight_models.py` — ADD

#### Implementation
1. Define the two models per spec §2. Use `timezone-aware` datetimes via `auto_now_add` (project rule: never `datetime.now()`).
2. Generate + apply the migration:
   ```bash
   cd /home/ahmed/aast/carbon/backend
   /home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations ai
   /home/ahmed/aast/carbon/.venv/bin/python manage.py migrate ai
   ```
3. Tests (`test_flight_models.py`): create a `Run` + `AcceptanceReport` (defaults, FK cascade); create `LearningOutcome`; assert the `(run, pattern)` unique constraint rejects a duplicate; assert `app_label="ai"`.

#### DO NOT TOUCH
- `backend/ai/engine/**` — nothing.
- Existing models/fields; `backend/dq/**`; `backend/dataschema/**`; frontend; docker files.
- Do NOT edit the generated migration by hand.

#### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check                        # → 0 issues
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run   # → "No changes detected"
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_flight_models.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
/home/ahmed/aast/carbon/.venv/bin/python -m pytest dq -q --maxfail=5 --disable-warnings -p no:cacheprovider   # → 38 passed
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q --maxfail=5 --disable-warnings -p no:cacheprovider   # → all green
```

#### Output contract
Append to `TASK-RESULTS.md`: files changed, migration output, test output (terminal proof), issues.

---

### Phase 25-B — FlightDirector core + additive engine hooks

**Date:** 2026-08-24
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE (commit `61248c1`)
**Kind:** Backend-only. Large.
**Depends on:** 25-A (models)
**Spec:** `docs/DESIGN-FLIGHT-DIRECTOR.md` §1, §3.1–§3.3

#### Files to Read First
- `docs/DESIGN-FLIGHT-DIRECTOR.md` (whole doc)
- `backend/ai/engine/cognition/plan/loop.py` — `_execute_step` (lines ~540–780), `run()` (~150–450), `_build_step_prompt`, `_persist_run_step`
- `backend/ai/engine/cognition/turn/witnesses.py` — `DraftResult.tool_calls`, `ExecutionResult.completed_tools`
- `backend/ai/engine/cognition/turn/draft.py` — `draft(..., model=...)` param
- `backend/ai/plans_service.py` — `_execute_plan_once` (~1870–1990), `_run_plan_frames` (~1990–2180)
- `backend/ai/host_executor.py` — read-only GET handlers (`_list_dq_rules_in_process`, `_list_tables_in_process`)
- `backend/ai/models/core.py` — `Run.working_notes` (flight state JSON home)
- `.ai-toolkit/shared/base-rules.md` (RULE_21, RULE_23)

#### Files to Change
- `backend/ai/flight_director.py` — ADD (core; see Implementation)
- `backend/ai/engine/cognition/plan/loop.py` — MODIFY additive-only: optional `flight_director=None` on `__init__` + `run()` + `_execute_step`; guarded call sites; NO behavior change when `None`
- `backend/ai/plans_service.py` — MODIFY: `_execute_plan_once` constructs + passes a `FlightDirector`; `_run_plan_frames` runs the contract gate before the first attempt and stores `working_notes.flight`
- `backend/ai/tests/test_flight_director.py` — ADD (unit)
- `backend/ai/tests/test_flight_director_integration.py` — ADD (integration)

#### Implementation
1. **`FlightDirector`** with:
   - `WorkingMemoryLedger` — `parse_output(tool_output)` extracts created entities (`{"id": N}`, `{"data": {"id": N}}`, `{"status_code": 201, "data": ...}`, `{"bindings": [...]}`); kind inferred from endpoint/tool; `validate_references(step, ledger)` uses read-only GET existence checks via a passed executor; returns corrected args when a stale id maps unambiguously to an earlier created entity (name overlap with step intent), else an instruction to re-list and use real ids.
   - `contract_gate(plan, brief)` — deterministic artifact-noun coverage check + auto-suggest `acceptance_criteria` per step (templates in spec §3.4). Never blocks; records findings + suggestions.
   - `prepare_step(step, ledger, attempts) -> StepPrep` — returns `corrected_tool_args`, `extra_instructions`, `model_override`, `repair_kind`, `repair_detail`.
   - `on_step_completed(step, draft, execution, result, ledger) -> StepFlightVerdict` — ledger update + fidelity guard (spec §3.3): `declared=len(draft.tool_calls)` vs `executed=len(execution.completed_tools)`; request re-run (read-only steps) or escalate (mutation steps → report partial + human-review flag, never auto re-run, RULE_21); per-step `model_override` from `getattr(settings, "AI_FLIGHT_DIRECTOR_ESCALATION_MODEL", "gpt-4o")`.
2. **Loop hooks (additive-only):** `__init__(..., flight_director=None)`; in `_execute_step`: (a) call `prepare_step` after building the step prompt, apply corrected args + extra instructions to the prompt and pass `model=prep.model_override` to `dw.draft(...)`; (b) after execution + result built, call `on_step_completed`; honor a bounded fidelity re-run INSIDE `_execute_step` (≤1 re-run for read-only steps; never for mutations). All hooks wrapped in `if self.flight_director is not None:`.
3. **plans_service:** `_execute_plan_once` builds `FlightDirector(executor=..., run=...)` and passes it to `ReActLoop`; `_run_plan_frames` calls `contract_gate` before `_execute_plan_once` and persists `working_notes["flight"]` after.
4. **Tests:**
   - `test_flight_director.py` (unit, no DB where possible): ledger parse of all output shapes; stale-id rewrite (125→129) with no false positive on pre-existing ids; contract gate finds missing artifacts + suggests criteria; fidelity verdict on 1-of-2; `prepare_step` model_override on escalation.
   - `test_flight_director_integration.py`: (a) **the water-consumption scenario** — create table step → create rule step (returns id 129) → binding step whose tool_args reference 125 → assert the binding step's args are corrected to 129 pre-staging and the run completes WITHOUT a 500/FK error; (b) a run with `flight_director=None` behaves identically to today (assert no new events/rows).

#### DO NOT TOUCH
- `backend/ai/engine/**` except `loop.py` — and there only additive optional-param hooks.
- `backend/dq/**`, `backend/dataschema/**` — read-only via existing host-executor GETs.
- `backend/ai/feedback/skill_flywheel.py`; frontend; docker files.
- No behavior change to any existing plan lifecycle path when the director is absent.

#### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_flight_director.py ai/tests/test_flight_director_integration.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_plans.py ai/tests/test_durable.py ai/tests/test_plan_task.py -q --maxfail=5 --disable-warnings -p no:cacheprovider   # → UNCHANGED + green (loop default proof)
/home/ahmed/aast/carbon/.venv/bin/python -m pytest dq -q --maxfail=5 --disable-warnings -p no:cacheprovider   # → 38 passed
```

#### Output contract
Append to `TASK-RESULTS.md`: files changed, loop diff summary (additive-only proof), test output, issues.

---

### Phase 25-C — Acceptance checks + repair + QoS endpoints

**Date:** 2026-08-24
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE (commit `5d9772a`)
**Kind:** Backend-only. Large.
**Depends on:** 25-B
**Spec:** `docs/DESIGN-FLIGHT-DIRECTOR.md` §3.4–§3.6, §4

#### Files to Read First
- `docs/DESIGN-FLIGHT-DIRECTOR.md` §3.4–§3.6, §4
- `backend/ai/flight_director.py` (from 25-B)
- `backend/ai/plans_service.py` — `_run_plan_frames` tail (frames after the retry loop), `get_ledger`, `_serialize_run`
- `backend/ai/plans_api.py` + `backend/ai/plans_urls.py` — route pattern for `<str:pk>/ledger/`
- `backend/ai/models/core.py` — `AcceptanceReport` (25-A)
- `.ai-toolkit/shared/api-contract.md` + `qa-framework.md`

#### Files to Change
- `backend/ai/flight_director.py` — MODIFY: acceptance criteria templates (§3.4), `run_acceptance_checks` (§3.5) with the repair loop (`AI_FLIGHT_DIRECTOR_MAX_REPAIRS`, default 2 → escalate), `build_acceptance_report` (§3.6)
- `backend/ai/plans_service.py` — MODIFY: after the retry loop in `_run_plan_frames`, run acceptance checks + write `AcceptanceReport`; add `get_qos_report(user, plan_id)` (row or computed-on-the-fly for legacy runs) and `get_flight_state(user, plan_id)`
- `backend/ai/plans_api.py` — MODIFY: `qos` and `flight` actions on `PlanViewSet`
- `backend/ai/plans_urls.py` — MODIFY: `qos/` + `flight/` routes (before the `steps/` pattern, after `ledger/`)
- `backend/ai/tests/test_flight_acceptance.py` — ADD
- `backend/ai/tests/test_flight_api.py` — ADD

#### Implementation
1. Acceptance criteria templates + checks per spec §3.4–§3.5 (re-query read-only via host executor GETs; evidence = query + matches; `table_fields` asserts the EXACT field set).
2. Repair loop: `missed` → repair instructions with actual diff → re-draft/re-execute (read-only/non-mutation only) → ≤2 → escalate. Report per-step `met|partial|missed` + evidence + repairs + escalated flag.
3. `build_acceptance_report` writes the `AcceptanceReport` row (report_json, metrics_json, narrative = `run.final_response`, status).
4. `get_qos_report` returns the spec §4 shape (owner-scoped; 404 on missing plan; computed on the fly when no row). `get_flight_state` returns `working_notes.flight`.
5. **Tests:**
   - `test_flight_acceptance.py`: criterion met; `table_fields` exact-set mismatch → partial + diff; repair succeeds within 2 attempts; repair exhausts → escalate + `escalations` metric; mutation step fidelity failure never re-runs (RULE_21).
   - `test_flight_api.py`: `GET qos/` returns report shape (met/partial/missed); `GET flight/` returns supervision; outsider (different org/user) → 403; unauthenticated → 401; missing plan → 404.

#### DO NOT TOUCH
- `backend/ai/engine/**` — nothing in this phase.
- `backend/dq/**`, `backend/dataschema/**` — read-only.
- Frontend files; docker files.

#### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_flight_acceptance.py ai/tests/test_flight_api.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q --maxfail=5 --disable-warnings -p no:cacheprovider
/home/ahmed/aast/carbon/.venv/bin/python -m pytest dq -q --maxfail=5 --disable-warnings -p no:cacheprovider   # → 38 passed
```

#### Output contract
Append to `TASK-RESULTS.md`: endpoints + payload shapes, test output, curl-style API evidence with a real JWT (403/401/200 paths).

---

### Phase 25-D — Grow loop: outcome → learning + playbook

**Date:** 2026-08-24
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE (commit `b3528f9`)
**Kind:** Backend-only. Small-Medium.
**Depends on:** 25-C (report)
**Spec:** `docs/DESIGN-FLIGHT-DIRECTOR.md` §3.6, §6

#### Files to Read First
- `docs/DESIGN-FLIGHT-DIRECTOR.md` §3.6
- `backend/ai/flight_director.py` (25-B/25-C)
- `backend/ai/models/core.py` — `LearningOutcome` (25-A), `PlaybookBlock`
- `backend/ai/feedback/skill_flywheel.py` — terminal-status guard pattern to mirror

#### Files to Change
- `backend/ai/flight_director.py` — MODIFY: `enqueue_learning_from_report(report)` (deterministic matchers, dedup, `PlaybookBlock` upsert with `version=N+1`, `provenance=run.id`, mark `LearningOutcome` applied) — wire it after `build_acceptance_report` in `plans_service`
- `backend/ai/plans_service.py` — MODIFY: call `enqueue_learning_from_report` after the report is written; never fail a run on learning errors (try/except, log)
- `backend/ai/tests/test_flight_learning.py` — ADD

#### Implementation
1. Matchers per spec §3.6 (missing criteria → planner pattern; fidelity_failures>0 → worker pattern; repaired_refs non-empty → planner ids pattern).
2. Dedup via the `(run, pattern)` unique constraint; idempotent re-call = no-op.
3. `PlaybookBlock(block_type="flight_director")` upsert: existing block → bump `version`, update `content`/`provenance`; new → create. Mark outcome `applied` + `applied_at`; terminal-status guard mirrors `feed_run_feedback` (`completed`/`failed` only).
4. **Tests** (`test_flight_learning.py`): each matcher fires on the right report; dedup (second call no-op); playbook version bump; non-terminal run → no outcomes.

#### DO NOT TOUCH
- `backend/ai/engine/**`; `backend/ai/feedback/skill_flywheel.py`; `backend/dq/**`; frontend; docker files.

#### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_flight_learning.py -q --maxfail=5 --disable-warnings -p no:cacheprovider
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q --maxfail=5 --disable-warnings -p no:cacheprovider
/home/ahmed/aast/carbon/.venv/bin/python -m pytest dq -q --maxfail=5 --disable-warnings -p no:cacheprovider   # → 38 passed
```

#### Output contract
Append to `TASK-RESULTS.md`: matcher/dedup/playbook evidence, test output.

---

### Phase 25-E — QA validation (4-layer evidence)

**Date:** 2026-08-24
**Worker Role:** qa-validator
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE (commits `ba5acfd`, `cde0c43`)
**Kind:** QA. Evidence-gathering.
**Depends on:** 25-A..25-D
**Spec:** `.ai-toolkit/shared/qa-framework.md` (4-layer) + `docs/DESIGN-FLIGHT-DIRECTOR.md` §7

#### Files to Read First
- `.ai-toolkit/shared/qa-framework.md` (4-layer evidence model)
- `docs/DESIGN-FLIGHT-DIRECTOR.md`
- `backend/ai/tests/test_flight_*.py` (all 5 test files)
- `backend/ai/plans_api.py` (qos/flight endpoints)

#### What to Validate (evidence, not claims)
- **L1 Structural:** `manage.py check` clean; `makemigrations --check --dry-run` clean; migration `0020` applied.
- **L2 Security (API):** real JWT — `GET /carbon-api/ai/plans/{id}/qos/` and `.../flight/` → 200 for owner; 403 for a user in a different org who doesn't own the plan; 401 unauthenticated; 404 missing plan.
- **L3 Functional (integration journey):** drive the water-consumption scenario — create table step → create rule step (id returned) → binding step with a STALE rule id in args → assert the FlightDirector corrects the reference and the run finishes with `completed` (no FK/500), and `GET qos/` returns `met` (or `partial` with repairs listed). Also validate an acceptance-miss path: a `table_fields` criterion with a wrong field set → repair → escalate → `partial` + `escalations` metric.
- **L4 UI:** not in scope unless Phase 26 shipped — state that explicitly.
- **Regression:** `pytest dq -q` (38) + `pytest ai -q` all green.

#### Output Contract
Append `TASK-RESULTS-16-FLIGHT-DIRECTOR.md` at repo root: per-layer evidence table (ID | severity | symptom | evidence | owner), exact commands + terminal output, PASS/FAIL verdict per layer, and overall verdict.

---

### Phase 26 — Frontend: QoS report panel (OPTIONAL)

**Date:** 2026-08-24
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** PLANNED (optional — dispatch only after 25-E passes and budget allows)
**Kind:** Frontend-only. Medium.
**Depends on:** 25-C endpoints (`qos/`, `flight/`)
**Spec:** `docs/DESIGN-FLIGHT-DIRECTOR.md` §4, §8

#### Files to Change
- `carbon-frontend/src/api/aiWorkspace.js` — ADD `getPlanQos(planId)`, `getPlanFlight(planId)`
- `carbon-frontend/src/shell/AITaskPanel.jsx` — MODIFY: add an "Acceptance report" view (or extend the Results tab) rendering the QoS report: status chip (`met/partial/missed`), per-requirement rows (verdict + evidence ids + repairs), metrics, and the supervision ledger; RULE_23 outcome copy only ("3 of 4 requirements met" — never engine terms); RULE_16/17 (PageContainer + Tabs pattern), theme tokens only (RULE_8)
- `carbon-frontend/src/__tests__/AITaskPanel.qos.test.jsx` — ADD (render met/partial/missed states, empty state, loading, error)

#### DO NOT TOUCH
- Backend files; `EnterpriseGraph.jsx`; `AIInputBar.jsx`; docker files.

#### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/AITaskPanel.qos.test.jsx
npm run build
```

#### Output contract
Append to `TASK-RESULTS.md`: lint/test/build output.

---

## Flight Director — Worker Activation Prompts

### 25-A: Backend Worker
```
Your role is backend-worker for Carbon.
1. Read .ai-toolkit/project.config.md
2. Read .ai-toolkit/shared/base-rules.md
3. Read .ai-toolkit/roles/backend-worker.md
4. Read docs/DESIGN-FLIGHT-DIRECTOR.md
5. Read TASKS.md — Phase 25-A (FlightDirector schema)
Confirm your role and begin. Model: DeepSeek V4-Flash.
Never docker, never `source venv`; run pytest from backend with /home/ahmed/aast/carbon/.venv/bin/python.
```

### 25-B: Backend Worker
```
Your role is backend-worker for Carbon.
1. Read .ai-toolkit/project.config.md
2. Read .ai-toolkit/shared/base-rules.md
3. Read .ai-toolkit/roles/backend-worker.md
4. Read docs/DESIGN-FLIGHT-DIRECTOR.md
5. Read TASKS.md — Phase 25-B (FlightDirector core + additive loop hooks)
Confirm your role and begin. Model: DeepSeek V4-Flash.
Engine edits are ADDITIVE-ONLY: optional flight_director=None, no behavior change when absent.
Never docker, never `source venv`; pytest from backend with /home/ahmed/aast/carbon/.venv/bin/python.
```

### 25-C: Backend Worker
```
Your role is backend-worker for Carbon.
1. Read .ai-toolkit/project.config.md
2. Read .ai-toolkit/shared/base-rules.md
3. Read .ai-toolkit/roles/backend-worker.md
4. Read docs/DESIGN-FLIGHT-DIRECTOR.md
5. Read TASKS.md — Phase 25-C (acceptance checks + repair + QoS endpoints)
Confirm your role and begin. Model: DeepSeek V4-Flash.
Never docker, never `source venv`; pytest from backend with /home/ahmed/aast/carbon/.venv/bin/python.
```

### 25-D: Backend Worker
```
Your role is backend-worker for Carbon.
1. Read .ai-toolkit/project.config.md
2. Read .ai-toolkit/shared/base-rules.md
3. Read .ai-toolkit/roles/backend-worker.md
4. Read docs/DESIGN-FLIGHT-DIRECTOR.md
5. Read TASKS.md — Phase 25-D (grow loop: outcome → learning + playbook)
Confirm your role and begin. Model: DeepSeek V4-Flash.
Never docker, never `source venv`; pytest from backend with /home/ahmed/aast/carbon/.venv/bin/python.
```

### 25-E: QA Validator
```
Your role is qa-validator for Carbon.
1. Read .ai-toolkit/project.config.md
2. Read .ai-toolkit/shared/base-rules.md
3. Read .ai-toolkit/shared/qa-framework.md
4. Read .ai-toolkit/roles/qa-validator.md
5. Read docs/DESIGN-FLIGHT-DIRECTOR.md
6. Read TASKS.md — Phase 25-E (QA validation, 4-layer evidence)
Validate with real JWTs and terminal output; write TASK-RESULTS-16-FLIGHT-DIRECTOR.md.
Model: DeepSeek V4-Flash.
```

### 26: Frontend Worker (only after 25-E passes)
```
Your role is frontend-worker for Carbon.
1. Read .ai-toolkit/project.config.md
2. Read .ai-toolkit/shared/base-rules.md
3. Read .ai-toolkit/roles/frontend-worker.md
4. Read docs/DESIGN-FLIGHT-DIRECTOR.md
5. Read TASKS.md — Phase 26 (QoS report panel)
Confirm your role and begin. Model: DeepSeek V4-Flash.
RULE_23: outcome copy only. lint + vitest + build must all pass.
```

---

# Notes + Contextual Inspector Drawer (ADR-0019)

## Phase 27 — Notes/Comments/Reactions + Contextual Inspector Drawer
**Date:** 2026-08-27
**Worker Role:** backend-worker + frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE (verified 2026-08-27: backend catalog 156 passed; frontend 901 passed; lint + build clean)
**ADR:** `.ai-toolkit/decisions/0019-contextual-inspector-drawer.md`
**Design docs:** `docs/DESIGN-NOTES-DRAWER.md` (backend + drawer), `docs/DESIGN-CONTEXTUAL-INSPECTOR-DRAWER.md` (migration plan), `docs/DESIGN-LOCK-REASON-AND-NOTES.md` (Layer A/B research).

Unify two right-edge panels into ONE global **Contextual Inspector Drawer**:
Notes (fixed first tab) + context-driven tabs (Health/Governance/Activity/Lineage/
Overview/Data Quality/…) auto-discovered from the active entity. Replaces the
per-page `EntityDetailShell` metrics panel across all 14 detail pages.

### Backend (catalog app — Notes data layer)
- `backend/catalog/models.py` — `Note`, `NoteComment` (flat 1-level), `NoteReaction`
  (one-per-user-per-target), `NoteAnchor`; polymorphic `entity_type`/`entity_id`.
- `backend/catalog/migrations/0011_notes_comments_reactions.py` + `0012_noteanchor.py`.
- `backend/catalog/serializers.py`, `views.py`, `urls.py` — list/create/update/soft-delete
  notes, lazy comments endpoint, reaction toggle, governance audit events.
- `backend/catalog/tests/test_notes.py` — 29 tests.

### Frontend (Notes drawer + Inspector migration)
- `carbon-frontend/src/notes/` — `NotesContext`, `NotesDrawer`/`NotesPanel`/`NotesRail`,
  `NotesTab`, `NoteCard`, `NoteComposer`, `CommentThread`, `ReactionBar`, `notesApi`.
- `carbon-frontend/src/inspector/` — `InspectorTabRegistry` (contribution-point
  singleton) + `tabs/` (`moduleTabs`, `catalogTabs`, `calculationTabs`, `collectionTabs`,
  `dataEntryTabs`, `myDataTabs`, `orgUnitTabs`, `rowDetailTabs`, `ruleTabs`, `helpers`).
- 14 migrated pages set inspector context via `useNotes().setContexts` and drop the
  inline metrics panel: `ModuleWorkspacePage`, `MyDataPage`, `DataEntryPage`,
  `RowDetailPage`, `CalculationsPage`, `OrgUnitDetailPage`, `AssetDetailPage`,
  `DataProductDetailPage`, `DataSourcesDetailPage`, `DomainDetailPage`,
  `ExportsDetailPage`, `ImportsDetailPage`, `ReferenceSetDetailPage`, `TagDetailPage`,
  `RuleDetailPage`, `EmissionsDashboard`.
- Deleted dead `src/components/entity/EntityDetailShell.jsx` + `useDetailPanel.jsx` (Phase D).
- New tests: `notes.drawer.test.jsx`, `inspectorTabRegistry.test.jsx`,
  `calculationTabs.test.jsx`, `EmissionsDashboard.notes.test.jsx`.

### Phase E remaining (polish, not blocking)
- Per-entity-type remembered active tab; per-user tab visibility (gear).
- Playwright smoke on migrated pages (en + ar).

### Results
- `TASK-RESULTS-19-CONTEXTUAL-INSPECTOR-CALCULATIONS.md` (final page migration).

---

# Phase Set I18N — Dual-Language UI: English (default) + Arabic RTL

**Authoritative context — read FIRST, before any worker prompt:**
- `.ai-toolkit/decisions/0018-i18n-dual-language.md` (locked decisions: i18next, semantic namespaced keys, Latin digits, no flags, AI replies NOT translated, en default)
- `.ai-toolkit/shared/compact-ui.md` (shell/theme conventions)
- RULE_23: every translated string must still describe OUTCOMES, never internals. A translation that exposes engine internals is a RULE_23 violation.

**Scope boundary (user-confirmed):** i18n = UI chrome + static platform copy ONLY.
AI/Pulse assistant replies and user-generated content stay in the language the user
writes (assistant mirrors the request language). Do NOT translate content strings.

**Non-negotiables (from ADR-0018):**
1. Switcher is text-based: "English" / "العربية" (+ translate icon). NO flags, NO country icons.
2. Default language is `en`. Persistence = localStorage + server-side user profile. NEVER navigator-language auto-detect.
3. Data numerals in Arabic stay Latin digits (`ar-EG-u-nu-latn`). Never Eastern Arabic numerals in tables/metrics.
4. Keys are semantic + namespaced (`shell.sidebar.catalog`), never English-as-key.
5. Backend errors → frontend error-code mapping. No backend gettext overhaul.
6. `useSuspense: false` + `ready` flag. `fallbackLng: 'en'`.
7. `src/api/api.js` apiFetch must remain the only fetch path (RULE_10).

**DO-NOT-TOUCH list (all I18N phases):** `vite.config.js` base, `App.jsx` route
namespace prefixes (RULE_5), `src/api/api.js` internals, backend engine files,
`src/theme/carbonTheme.js` palette tokens (extend, don't restyle).

---

## I18N-1: Foundation (frontend-worker)

**Status:** DONE (commit `80eb540`)

Files to create:
- `src/i18n/index.js` — i18next init: `lng` from localStorage (`carbon.lang`, default `'en'`), `fallbackLng: 'en'`, `useSuspense: false`, `interpolation.escapeValue: false`, namespaces `common`, `shell`, `auth`, `errors`; registers `en`/`ar` resources (v1 inline; JSON files in later phases).
- `src/i18n/locales/en/common.json`, `src/i18n/locales/ar/common.json` — starter catalogs (keep keys minimal in this phase).
- `src/i18n/LanguageProvider.jsx` — React context: `{ lang, isRtl, setLanguage, ready }`. `setLanguage` writes localStorage, `i18n.changeLanguage`, sets `document.documentElement.dir` (`rtl`/`ltr`) and `lang`, flips theme direction + Emotion cache. On mount, fetch server preference via apiFetch and reconcile (server wins on login; localStorage wins pre-login).
- `src/i18n/useLanguage.js` — hook re-export.
- `src/i18n/RtlProvider.jsx` — dual Emotion caches (`createCache({key:'muil'})` / `createCache({key:'muirtl', stylisPlugins:[rtlPlugin]})`), swaps `CacheProvider` on `isRtl`.
- `src/components/LanguageSwitcher.jsx` — text-only menu (Menu of `MenuItem`s: "English", "العربية"), `LanguageIcon` from MUI icons, placed in `HeaderEnhanced` near the avatar (top-right). NO flags. Accessible labels.
- `src/__mocks__/react-i18next.js` — vitest mock (`useTranslation: () => ({ t: (k) => k, i18n: {...} })`).

Files to modify (extend, never restyle):
- `package.json` — add deps: `i18next`, `react-i18next`, `stylis-plugin-rtl`, `@fontsource/cairo`.
- `src/theme/carbonTheme.js` — `createCarbonTheme(mode, direction='ltr')` accepts direction; sets `direction` and swaps `fontFamily` to Cairo (Arabic) when `direction==='rtl'`; Arabic `lineHeight` bump.
- `src/theme/getTheme.js` — pass direction through.
- `src/theme/ThemedApp.jsx` — wrap: `LanguageProvider` (outer) → `RtlProvider` → `ThemeProvider` (direction-aware) → existing providers. Preserve `NotificationProvider`/`AuthProvider` order.
- `src/components/HeaderEnhanced.jsx` — mount `<LanguageSwitcher />` (top-right, before avatar menu).
- `src/main.jsx` — import `src/i18n/index.js` + Cairo font css (wght 400/500/600/700) before root render.

Verification gate (run all): `npm run lint` clean; `npm test` green (existing suite must not regress — default `en` renders identical strings); `npm run build` passes; `./.ai-toolkit/scripts/verify.sh frontend` passes. Manual: switcher toggles en↔العربية, `<html>` flips `dir`/`lang`, layout mirrors, no layout breakage in sidebar.

## I18N-2: Shell + Auth strings (frontend-worker)

**Status:** DONE (commit `80eb540`)

Migrate to `t()` (namespaces `shell`, `auth`, `common`): `src/shell/*` (Shell, ShellSidebar nav labels, Breadcrumbs single crumb, AI workspace chrome bars), `src/auth/*` (login/logout pages, JWT expiry copy), `src/components/HeaderEnhanced.jsx` static labels, common buttons/empty-states/status chips used platform-wide (Save/Cancel/Delete/Edit/Search/No results…), date/time labels.

Rules:
- Keys under `shell.*`, `auth.*`, `common.*`; full-sentence keys; `<Trans>` for any sentence embedding JSX.
- Add Arabic catalogs: `src/i18n/locales/{ar,en}/shell.json`, `auth.json` (+ register in `index.js`).
- Any string containing an API error message goes through the error-code mapping (see I18N-5; stub `src/i18n/errorMessages.js` with a small starter map in this phase, code-prefixed).
- DO NOT touch AI workspace content bubbles, rule descriptions, or assistant copy (content scope).

Gate: lint + vitest + build + `verify.sh frontend`; key-parity script `node scripts/check-i18n-keys.js` (compares en/ar key sets; add this script in this phase) → zero missing keys.

## I18N-3: Core apps — catalog + mdm + dq + dataschema (frontend-worker, per-app sub-phases)

**Status:** READY — remaining (pages live in `src/pages/{catalog,dq,dataschema}`, not `src/apps/*`)

`src/apps/catalog/*`, `src/apps/mdm/*`, `src/apps/dq/*`, `src/apps/dataschema/*` pages, dialogs, tables, forms → `t()` with namespaces `catalog`, `mdm`, `dq`, `dataschema`. RTL-correct markup only (logical props; MUI handles most via theme). Arabic catalogs for each namespace. Charts/data tables: numerals stay Latin; tooltips localized.

Gate: per-app lint + vitest + build; key-parity zero-missing; RTL manual smoke per app (no clipped text — Arabic is ~25-40% longer in some strings, allow flexible widths; no directionally-broken icons).

## I18N-4: Hosted + tools — emissions, evidence, connections, importexport (frontend-worker)

**Status:** READY — remaining (evidence/import live in `src/components/{evidence,import}`)

Same pattern as I18N-3 for `src/apps/emissions/*`, `src/apps/evidence/*`, `src/apps/connections/*`, `src/apps/importexport/*` (namespaces `emissions`, `evidence`, `connections`, `importexport`). Also `src/components/` shared dialogs and `src/pages/*` root pages (dashboard/health/404) → `common`/`shell`.

Gate: same as I18N-3 + full-suite vitest + build + `verify.sh frontend`.

## I18N-5: AI workspace chrome + backend error-code mapping (frontend-worker + backend-worker)

**Status:** DONE — backend prefs (`cdc0ceb`) + frontend error mapping + core AI chrome (`AIWorkspace`/`AIWorkspaceHeader`/`AIStatusBar`, commit `ad6d7c1`). Remaining: deep per-panel chrome (22 AI shell files + 25 admin panels).

Frontend: migrate AI workspace **chrome** (tabs, panels, buttons, status labels in `src/shell/AI*.jsx` / `src/apps/ai/*` if present) to namespace `ai`. Assistant message bubbles, plan/artifact content, and rule/provenance text are CONTENT — untouched. Complete `src/i18n/errorMessages.js`: map backend `error_code`/DRF detail codes → localized strings for both languages; wire into `src/api/api.js` error normalization layer (apiFetch stays the only fetch path).

Backend (backend-worker): `accounts.User.language` field (CharField, max_length=10, default `'en'`, choices `en`/`ar`), migration, `GET/PATCH /carbon-api/accounts/me/preferences/` (read/write `language`), surface `language` in `me/context/`. Tests: serializer round-trip, auth required, invalid value 400. Run: pytest for `accounts/` + `manage.py check` + `makemigrations --check --dry-run`.

Gate: frontend lint+vitest+build; backend pytest `accounts` green; end-to-end: switch language in UI → reload logged-in → server preference persists.

## I18N-6: QA / RTL audit + Arabic quality + E2E (qa-validator + master gates)

**Status:** DONE ✅ (2026-08-27) — see `TASK-RESULTS-17-I18N-DUAL-LANG.md`. All
gates green: key parity 1036 (en===ar), E2E journey-13 6/6 (EN+AR incl. mid-
session switch, reload persistence, logout/login), RTL fixes in
`MarkdownMessage.jsx` + `RuleJsonEditor.jsx`, Arabic quality pass clean.
Deferred to W7-B: directional-icon flip (~92 matches/40 files, 90% W7-B dirty)
+ Arabic plural keys. EPH-4C / I18N-3/4 remain HELD until W7-B commits.

- RTL sweep: DataGrid (columns/density/pinning), Monaco editor (keep LTR internally), Chart.js tooltips/legends, mermaid/katex blocks, tooltips/menus/popovers, scrollbars, `dir="ltr"` on code blocks/IDs/emails.
- Directional-icon audit: chevrons, arrows, undo/redo, sort indicators → flipped in RTL (MUI icons don't auto-flip).
- Numerals audit: all tables/metrics show Latin digits in Arabic mode (`ar-EG-u-nu-latn`).
- Arabic translation quality pass: native-fluent review of `ar/*.json`; gendered "you" forms neutralized; word-order/plural correctness (6 CLDR forms); dates Gregorian with Arabic month names via dayjs `ar`.
- Key parity gate: `node scripts/check-i18n-keys.js` → zero missing; `fallbackLng` never silently serving en keys in ar.
- E2E (Playwright): full key journeys in EN and AR (login → dashboard → one app workflow → language switch mid-session → persistence across reload → logout/login).
- Deliverable: `TASK-RESULTS-17-I18N-DUAL-LANG.md` with evidence (gates, key parity, E2E runs, RTL audit checklist).

# ─────────────────────────────────────────────────────────────────────
# Phase 28 — Inventory Coverage (GHG declared-universe completeness)
# Spec: ADR-0020 (.ai-toolkit/decisions/0020-inventory-coverage.md)
# ─────────────────────────────────────────────────────────────────────

## Phase 28-A — Inventory Coverage backend (backend-worker)

**Date:** 2026-08-27
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** READY
**Depends on:** nothing (greenfield — grep confirms no InventorySource/CoverageGoal exists yet)

**Files to Read First:**
- `.ai-toolkit/decisions/0020-inventory-coverage.md` (authoritative design)
- `backend/emissions/models.py` (end of file — GHG Phase 2 model patterns)
- `backend/emissions/services.py` (TargetService at ~1398 — static-method service precedent)
- `backend/emissions/serializers.py` (SBTiTargetSerializer ~340 — read-only display field pattern)
- `backend/emissions/views.py` (OrganizationalBoundaryViewSet ~1369 — ReadAnyWriteAdmin + required_write_capability pattern)
- `backend/emissions/urls.py` (router registration pattern)
- `backend/accounts/capabilities.py` (Capability dataclass, ALL_CAPABILITIES ~555, IMPLIES ~640, GROUP_CAPABILITIES ~721)
- `backend/emissions/admin.py` (GHG Phase 2 admin registrations at end)
- `backend/emissions/tests/test_targets.py` (test patterns)

**Files to Change:**
1. `backend/emissions/models.py` — append 4 models
2. `backend/emissions/services.py` — append `InventoryCoverageService`
3. `backend/emissions/serializers.py` — append 4 serializers
4. `backend/emissions/views.py` — append 4 viewsets + 1 coverage APIView
5. `backend/emissions/urls.py` — register 4 routers + coverage path
6. `backend/accounts/capabilities.py` — add `CARBON_MANAGE_INVENTORY_COVERAGE`
7. `backend/emissions/admin.py` — register 4 models
8. `backend/emissions/tests/test_inventory_coverage.py` — NEW tests

**Context:** The platform measures emissions but never records *what it is accountable for measuring* vs *what it measured*. This adds the GHG Protocol "declared universe" layer: `InventorySource` (period-invariant binding keyed by org_unit×scope×scope3_category×source_name), `InventorySourceStatus` (per-period through-model carrying status declared/covered/excluded + PCAF data_quality_tier 1–5 + period-scoped M2M `linked_tables`), `CoverageGoal` (target % + min_quality_tier + completeness_definition absolute|materiality_bounded), `CoverageAction` (remediation work items), and `InventoryCoverageService.compute_coverage()` returning 5 outputs.

**Implementation:**

### 1. Models — append to `backend/emissions/models.py`

```python
# ── Inventory Coverage (ADR-0020) ───────────────────────────────────

class InventorySource(models.Model):
    """Declared-universe binding: an emission source the org is accountable for measuring.

    Period-invariant fact keyed by (org_unit, scope, scope3_category, source_name).
    NOT a DataTable extension — one physical table can be both scope 1 and scope 3
    cat 3, so scope semantics live here, not on the table.
    """
    SCOPE_CHOICES = [(1, 'Scope 1'), (2, 'Scope 2'), (3, 'Scope 3')]

    org_unit = models.ForeignKey(
        'mdm.OrgUnit', on_delete=models.CASCADE, related_name='inventory_sources'
    )
    scope = models.PositiveSmallIntegerField(choices=SCOPE_CHOICES)
    scope3_category = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Scope 3 category 1-15; null for scope 1/2"
    )
    source_name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='inventory_sources_created'
    )

    class Meta:
        ordering = ['scope', 'scope3_category', 'source_name']
        verbose_name = "Inventory Source"
        verbose_name_plural = "Inventory Sources"
        constraints = [
            models.UniqueConstraint(
                fields=['org_unit', 'scope', 'scope3_category', 'source_name'],
                name='uniq_inventory_source_binding',
            ),
        ]
        indexes = [models.Index(fields=['org_unit', 'scope', 'is_active'])]

    def __str__(self):
        label = f"Scope {self.scope}"
        if self.scope == 3 and self.scope3_category:
            label += f" — Cat {self.scope3_category}"
        return f"{self.source_name} ({label})"


class InventorySourceStatus(models.Model):
    """Per-period status of a source — slowly-changing dimension (ADR-0020).

    Carries PCAF data quality tier + exclusion reason + period-scoped linked_tables.
    The M2M lives HERE (not on InventorySource) so a table linked in 2024 no longer
    reads as 'covered' in 2026.
    """
    STATUS_CHOICES = [
        ('declared', 'Declared'),
        ('covered', 'Covered'),
        ('excluded', 'Excluded'),
    ]
    TIER_CHOICES = [
        (1, 'Tier 1 — Audited'),
        (2, 'Tier 2 — Verified'),
        (3, 'Tier 3 — Calculated'),
        (4, 'Tier 4 — Estimated'),
        (5, 'Tier 5 — Proxy'),
    ]
    EXCLUSION_REASON_CHOICES = [
        ('not_material', 'Not Material'),
        ('insufficient_data', 'Insufficient Data'),
        ('out_of_boundary', 'Outside Operational Boundary'),
        ('other', 'Other'),
    ]

    source = models.ForeignKey(
        InventorySource, on_delete=models.CASCADE, related_name='statuses'
    )
    reporting_period = models.ForeignKey(
        ReportingPeriod, on_delete=models.CASCADE, related_name='inventory_source_statuses'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='declared')
    data_quality_tier = models.PositiveSmallIntegerField(
        choices=TIER_CHOICES, null=True, blank=True,
        help_text="PCAF data quality score 1-5 (1=best)"
    )
    exclusion_reason = models.CharField(
        max_length=30, choices=EXCLUSION_REASON_CHOICES, null=True, blank=True
    )
    linked_tables = models.ManyToManyField(
        'dataschema.DataTable', blank=True, related_name='inventory_source_statuses'
    )
    notes = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['reporting_period', 'source__scope', 'source__scope3_category']
        verbose_name = "Inventory Source Status"
        verbose_name_plural = "Inventory Source Statuses"
        constraints = [
            models.UniqueConstraint(
                fields=['source', 'reporting_period'],
                name='uniq_source_period_status',
            ),
        ]
        indexes = [models.Index(fields=['reporting_period', 'status'])]

    def __str__(self):
        return f"{self.source} — {self.get_status_display()} ({self.reporting_period})"


class CoverageGoal(models.Model):
    """Coverage target: org_unit × scope × target % × quality tier × completeness def."""
    SCOPE_CHOICES = [
        ('1', 'Scope 1'), ('2', 'Scope 2'), ('3', 'Scope 3'),
        ('1+2', 'Scope 1+2'), ('1+2+3', 'Scope 1+2+3'),
    ]
    COMPLETENESS_CHOICES = [
        ('absolute', 'Absolute'),
        ('materiality_bounded', 'Materiality-Bounded'),
    ]
    STATUS_CHOICES = [('draft', 'Draft'), ('active', 'Active'), ('archived', 'Archived')]

    org_unit = models.ForeignKey(
        'mdm.OrgUnit', on_delete=models.CASCADE, related_name='coverage_goals'
    )
    name = models.CharField(max_length=200)
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES)
    target_coverage_pct = models.DecimalField(max_digits=5, decimal_places=2)
    min_quality_tier = models.PositiveSmallIntegerField(
        choices=InventorySourceStatus.TIER_CHOICES, null=True, blank=True,
        help_text="Minimum PCAF tier for a source to count as 'covered'"
    )
    completeness_definition = models.CharField(
        max_length=30, choices=COMPLETENESS_CHOICES, default='materiality_bounded'
    )
    target_year = models.PositiveIntegerField()
    sbti_target = models.ForeignKey(
        SBTiTarget, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='coverage_goals'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='coverage_goals_created'
    )

    class Meta:
        ordering = ['-target_year', 'scope']
        verbose_name = "Coverage Goal"
        verbose_name_plural = "Coverage Goals"
        indexes = [models.Index(fields=['org_unit', 'scope', 'status'])]

    def __str__(self):
        return f"{self.name} — {self.scope} @ {self.target_coverage_pct}%"


class CoverageAction(models.Model):
    """Remediation work item for closing a coverage gap or improving quality."""
    ACTION_TYPE_CHOICES = [
        ('collect_data', 'Collect Data'),
        ('improve_quality', 'Improve Data Quality'),
        ('obtain_verification', 'Obtain Verification'),
        ('formalize_exclusion', 'Formalize Exclusion'),
    ]
    STATUS_CHOICES = [('open', 'Open'), ('in_progress', 'In Progress'), ('done', 'Done'), ('blocked', 'Blocked')]

    source = models.ForeignKey(
        InventorySource, on_delete=models.CASCADE, related_name='actions'
    )
    action_type = models.CharField(max_length=30, choices=ACTION_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    due_date = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='coverage_actions'
    )
    notes = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='coverage_actions_created'
    )

    class Meta:
        ordering = ['due_date', '-created_at']
        verbose_name = "Coverage Action"
        verbose_name_plural = "Coverage Actions"
        indexes = [models.Index(fields=['source', 'status'])]

    def __str__(self):
        return f"{self.get_action_type_display()} — {self.source}"
```

### 2. Service — append `InventoryCoverageService` to `backend/emissions/services.py`

```python
class InventoryCoverageService:
    """Computes declared-universe coverage for a reporting period (ADR-0020).

    Returns FIVE outputs: total, covered, gaps, pct, avg_quality_tier,
    material_exclusions, completeness_definition.
    """

    @staticmethod
    def compute_coverage(reporting_period_id, org_unit_id=None):
        from .models import InventorySource, InventorySourceStatus, CoverageGoal

        sources = InventorySource.objects.filter(is_active=True).select_related('org_unit')
        if org_unit_id:
            sources = sources.filter(org_unit_id=org_unit_id)

        total = sources.count()
        statuses = {
            s.source_id: s
            for s in InventorySourceStatus.objects.filter(
                reporting_period_id=reporting_period_id, source__in=sources
            ).select_related('source')
        }

        covered = 0
        tier_sum = 0
        tier_count = 0
        gaps = []
        exclusions = []

        for source in sources:
            st = statuses.get(source.id)
            if st is None:
                gaps.append({
                    'source_id': source.id, 'source_name': source.source_name,
                    'scope': source.scope, 'scope3_category': source.scope3_category,
                    'reason': 'not_assessed',
                })
            elif st.status == 'covered':
                covered += 1
                if st.data_quality_tier:
                    tier_sum += st.data_quality_tier
                    tier_count += 1
            elif st.status == 'excluded':
                exclusions.append({
                    'source_id': source.id, 'source_name': source.source_name,
                    'scope': source.scope, 'scope3_category': source.scope3_category,
                    'reason': st.get_exclusion_reason_display() if st.exclusion_reason else None,
                })
            else:  # declared
                gaps.append({
                    'source_id': source.id, 'source_name': source.source_name,
                    'scope': source.scope, 'scope3_category': source.scope3_category,
                    'reason': 'declared',
                })

        goal = CoverageGoal.objects.filter(status='active')
        if org_unit_id:
            goal = goal.filter(org_unit_id=org_unit_id)
        goal = goal.first()
        completeness_definition = goal.completeness_definition if goal else 'absolute'

        denominator = (total - len(exclusions)) if completeness_definition == 'materiality_bounded' else total
        pct = round((covered / denominator) * 100, 2) if denominator else 0.0
        avg_quality_tier = round(tier_sum / tier_count, 2) if tier_count else None

        return {
            'total': total,
            'covered': covered,
            'gaps': gaps,
            'gaps_count': len(gaps),
            'pct': pct,
            'avg_quality_tier': avg_quality_tier,
            'material_exclusions': exclusions,
            'material_exclusions_count': len(exclusions),
            'completeness_definition': completeness_definition,
            'min_quality_tier': goal.min_quality_tier if goal else None,
            'target_coverage_pct': float(goal.target_coverage_pct) if goal else None,
        }
```

### 3. Serializers — append to `backend/emissions/serializers.py`

Four ModelSerializers mirroring the existing pattern (read-only `*_name`/`*_label` display fields + `read_only_fields` for created_at/updated_at/created_by):

- `InventorySourceSerializer` — add `org_unit_name = CharField(source='org_unit.name', read_only=True)`, `scope_display`, `scope3_category`.
- `InventorySourceStatusSerializer` — add `source_name`, `reporting_period_name = CharField(source='reporting_period.name', read_only=True)`, `status_display`, `data_quality_tier_display`, `exclusion_reason_display`.
- `CoverageGoalSerializer` — add `org_unit_name`, `scope_display`, `completeness_definition_display`, `status_display`.
- `CoverageActionSerializer` — add `source_name`, `action_type_display`, `status_display`, `owner_username = CharField(source='owner.username', read_only=True)`.

### 4. Views — append to `backend/emissions/views.py`

- Import the 4 models + 4 serializers + `InventoryCoverageService`.
- 4 ModelViewSets using **`ReadAnyWriteAdmin` + `required_write_capability = 'carbon:manage_inventory_coverage'`** (mirror OrganizationalBoundaryViewSet exactly). `get_queryset` scoped via `get_visible_org_units(user)` for the org-scoped ones (InventorySource, CoverageGoal). All 4: `http_method_names` default; add `@extend_schema(tags=['emissions'])` if present elsewhere.
- `InventoryCoverageAPIView(APIView)` — `permission_classes = [IsAuthenticated]`, GET only. Accepts `reporting_period` (required int) + `org_unit` (optional int) query params, calls `InventoryCoverageService.compute_coverage()`, returns Response. 400 if `reporting_period` missing.

### 5. URLs — `backend/emissions/urls.py`

- Import the 4 viewsets + `InventoryCoverageAPIView`.
- 4 new `DefaultRouter()` instances: `inventory-sources`, `inventory-source-statuses`, `coverage-goals`, `coverage-actions` (basenames `inventory-source`, `inventory-source-status`, `coverage-goal`, `coverage-action`).
- `path('', include(...))` for each + `path('coverage/', InventoryCoverageAPIView.as_view(), name='inventory-coverage')`.

### 6. Capability — `backend/accounts/capabilities.py`

Add after `CARBON_MANAGE_REPORTING_PERIODS`:

```python
CARBON_MANAGE_INVENTORY_COVERAGE = Capability(
    key="carbon:manage_inventory_coverage",
    domain="carbon",
    action="manage_inventory_coverage",
    label="Manage Inventory Coverage",
    description="Declare emission sources, track coverage, set coverage goals",
    category="admin",
)
```

Then:
- `ALL_CAPABILITIES`: add `CARBON_MANAGE_INVENTORY_COVERAGE.key: CARBON_MANAGE_INVENTORY_COVERAGE,`
- `IMPLIES`: add `CARBON_MANAGE_INVENTORY_COVERAGE.key: {CARBON_VIEW_CONSOLE.key},`
- `GROUP_CAPABILITIES["carbon_lead"]`: add `CARBON_MANAGE_INVENTORY_COVERAGE.key,`

### 7. Admin — `backend/emissions/admin.py`

Register all 4 with `list_display`/`list_filter`/`search_fields`/`ordering` matching the GHG Phase 2 style.

### 8. Migration + tests

- Run `makemigrations emissions` (create migration), do NOT run migrate in dev (document as `./manage.sh migrate` step).
- `backend/emissions/tests/test_inventory_coverage.py`: test model creation + unique constraint, `compute_coverage` for all status branches (not_assessed/covered/excluded/declared), materiality-bounded denominator, API GET `coverage/` 200 + 400 on missing period, viewset write-permission (non-admin 403 on POST).

**DO NOT TOUCH:** `backend/core/*`, `backend/catalog/*`, `backend/mdm/*`, `backend/dataschema/*`, `backend/accounts/permissions.py`, `backend/accounts/rbac_utils.py` (import only), frontend files, `config/urls.py`, any existing model/serializer/view (append only).

**Verification Gate (backend-worker MUST run):**
1. `.ai-toolkit/scripts/verify.sh` (full backend pass)
2. `pytest backend/emissions/tests/test_inventory_coverage.py -v` (one app at a time — DO NOT run full suite)
3. `python backend/manage.py makemigrations --check --dry-run` (no missing migrations)
4. `python backend/manage.py check`
5. Report: files changed, migration name, test pass count, any gaps.

---

## Phase 28-B — Inventory Coverage frontend (frontend-worker)

**Date:** 2026-08-27
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** READY (after 28-A backend green)
**Depends on:** Phase 28-A (API contract above)

**Files to Read First:**
- `.ai-toolkit/decisions/0020-inventory-coverage.md`
- `carbon-frontend/src/pages/carbon/SBTiTargetsPage.jsx` (full CRUD reference pattern — Table + Drawer + Dialog + Snackbar + chips, FONT theme token, PageContainer + PageHeader + useDocumentTitle + useAuth)
- `carbon-frontend/src/capabilities.js` (add capability + ROUTE_CAPABILITIES + MANIFEST_ROLE_TO_CAPABILITY + MENU_ITEM_CAPABILITIES + CAPABILITY_INHERITANCE)
- `carbon-frontend/src/config.js` (API_ROUTES)
- `carbon-frontend/src/api/emissions-extended.js` (CRUD fn pattern)
- `carbon-frontend/src/apps/carbon/manifest.js` (nav items under Configuration)
- `carbon-frontend/src/App.jsx` (lazy import + route)
- `carbon-frontend/src/shell/Shell.jsx` (`studioFromPath` — RULE_15)

**Files to Change:**
1. `carbon-frontend/src/capabilities.js`
2. `carbon-frontend/src/config.js`
3. `carbon-frontend/src/api/emissions-extended.js`
4. `carbon-frontend/src/pages/carbon/InventoryCoveragePage.jsx` — NEW
5. `carbon-frontend/src/apps/carbon/manifest.js`
6. `carbon-frontend/src/App.jsx`

**Context:** Backend now exposes `carbon/inventory-sources/`, `carbon/inventory-source-statuses/`, `carbon/coverage-goals/`, `carbon/coverage-actions/`, and read-only `carbon/coverage/?reporting_period=<id>&org_unit=<id>`. Frontend adds an admin "Inventory Coverage" page (SBTiTargetsPage pattern) with a coverage summary header (pct / covered / gaps / avg_quality_tier / completeness_definition / material_exclusions) + tabs or sections for Sources, Statuses, Goals, Actions.

**Implementation:**
1. `capabilities.js`: add `export const CARBON_MANAGE_INVENTORY_COVERAGE = 'carbon:manage_inventory_coverage';` + wire into `MANIFEST_ROLE_TO_CAPABILITY['carbon:admin']`, `ROUTE_CAPABILITIES['/carbon/admin/inventory-coverage']`, `MENU_ITEM_CAPABILITIES['Inventory Coverage']`, `CAPABILITY_INHERITANCE` (→ CARBON_VIEW_CONSOLE).
2. `config.js` API_ROUTES: `emissionsInventorySources: "carbon/inventory-sources/"`, `emissionsInventorySourceStatuses: "carbon/inventory-source-statuses/"`, `emissionsCoverageGoals: "carbon/coverage-goals/"`, `emissionsCoverageActions: "carbon/coverage-actions/"`, `emissionsCoverage: "carbon/coverage/"`.
3. `emissions-extended.js`: CRUD fns — `fetchInventorySources/createInventorySource/updateInventorySource/deleteInventorySource`, same for Statuses/Goals/Actions, + `fetchCoverage({ reporting_period, org_unit }, token)` (apiFetch only — RULE_10).
4. `InventoryCoveragePage.jsx` (NEW): SBTiTargetsPage structure. Header cards for coverage summary; a reporting-period selector (from `fetchReportingPeriods`); sections for Sources (table + drawer CRUD), Goals (table + drawer CRUD), Actions (table + drawer CRUD), Statuses (table). ScopeChip/TierChip/StatusChip helpers via theme tokens. All colors via theme.palette (zero hardcoded hex), `FONT` token for typography, `PageContainer`/`PageHeader`/`useDocumentTitle`/`useAuth`.
5. `manifest.js`: add `{ label: 'Inventory Coverage', path: '/carbon/admin/inventory-coverage', role: 'carbon:admin' }` under the Configuration group (after Base Years).
6. `App.jsx`: lazy import `InventoryCoveragePage` + `<Route path="/carbon/admin/inventory-coverage" element={<AdminRoute appId="carbon" requiredCapability={CARBON_MANAGE_INVENTORY_COVERAGE}><InventoryCoveragePage /></AdminRoute>} />` (import the new capability from capabilities.js).

**DO NOT TOUCH:** `src/api/api.js`, `src/auth/*`, `src/theme/*` (use tokens only), other pages, backend files.

**Verification Gate (frontend-worker MUST run):**
1. `npm run lint` (eslint clean)
2. `npx vitest run` (existing tests green)
3. `npm run build` (no errors)
4. Report: files changed, route registered, capability wired, any i18n/lint gaps.
- Update `.ai-toolkit/roles/frontend-worker.md` (or add a shared rule): every new user-facing string must use `t()` + both locale catalogs.

Gate: ALL green — lint, vitest, build, verify.sh frontend, pytest smoke, E2E both languages, key parity.

## I18N dispatch order
1. I18N-1 (foundation) — frontend-worker
2. I18N-2 (shell+auth) — frontend-worker
3. I18N-3 (core apps) — frontend-worker (per-app)
4. I18N-4 (hosted+tools) — frontend-worker
5. I18N-5 (ai chrome + backend prefs) — frontend-worker + backend-worker (parallel-safe: separate repos of files)
6. I18N-6 (QA/audit/E2E) — qa-validator
Each phase requires the previous gate green before dispatch. Master Architect runs all terminal gates.


---

# ENTERPRISE PLATFORM HARDENING TRACK (EPH)

**Audit reference:** `docs/AUDIT-DATA-TRUST-PLATFORM-ENTERPRISE.md` — 47 gaps across 25 categories (6/10 overall).
**Goal:** Close all 8 P0 blockers. Address 8 of 12 P1 gaps. 18 phases across 6 sprints.
**Audit date:** 2026-08-26.

## Pre-Dispatch Reality Check (audit corrections vs. actual codebase)

| Audit Claim | Actual State | Implication |
|-------------|--------------|-------------|
| "No Notification model, no in-app center" | `UserAlert` + `NotificationChannel` + `NotificationRule` + `notify_event()` fully implemented in `accounts/models.py` (Phase 1.6). API in `notification_views.py`. | EPH-1B is **frontend only** (no backend work). |
| "DQ Profiling — no TableProfile model" | `TableProfile` + `FieldProfile` exist in `dq/models.py` with null_counts, distinct_counts, min/max/mean, completeness_pct. | EPH-3A = scheduling service + scorecard, NOT model creation. |
| "No freshness monitoring" | `NotificationRule.EventType.FRESHNESS_VIOLATION` defined; `notify_event('freshness_violation', ...)` callable. | EPH-3B = add `DataTable.last_data_updated_at` signal + `FreshnessPolicy` model + task. Alerting plumbing done. |

## Locked Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| Search: PostgreSQL FTS (`SearchVector`/`SearchQuery`/GIN index) | Zero new infra. Good to 50K assets. Migrate to Meilisearch later if needed. |
| Lineage: manual registration first | No SQL parser (P2). `LineageEdge` table + API + graph UI only. |
| Masking: serializer-based redaction | PII fields masked in API response per user capabilities. Dynamic consent gate is P2. |
| Column RBAC: capability-based `FieldAccessPolicy` | Extends existing `ScopedRole` + capabilities pattern. No ABAC engine (P2). |
| Rate limiting: Redis counter via DRF throttle | Redis already present. No new broker. |
| Versioning: `API-Version: 1` response header | No URL churn. `/v2/` reserved for breaking changes. |
| Profiling: Celery periodic task | Celery + Redis in stack. Profile via existing `DataRow` queryset. |
| Notifications: extend `accounts/` app | `UserAlert` is canonical. No new app. |

## P0 Closure Map

| P0 Gap | Phase | Notes |
|--------|-------|-------|
| API request audit middleware | EPH-1A | New `RequestAuditLog` + `AuditMiddleware` |
| Data access logging | EPH-1A | Same middleware, structured JSON logging |
| Unified notification system | EPH-1B (frontend only) | Backend exists since Phase 1.6 |
| Lineage graph model | EPH-2A | New `LineageEdge` table + API |
| Impact analysis | EPH-2A | BFS downstream query |
| Full-text search | EPH-2B + EPH-2D | PG FTS + search UI |
| Column-level access control | EPH-4A + EPH-4C | `FieldAccessPolicy` + serializer filtering |
| Data masking engine | EPH-4B | `DataField.masking_strategy` + `MaskingService` |

## P1 Partial Closure Map

| P1 Gap | Phase |
|--------|-------|
| Automated DQ profiling engine | EPH-3A |
| DQ scorecard API | EPH-3A |
| Freshness monitoring + alerts | EPH-3B |
| Structured error codes | EPH-5A |
| API versioning header | EPH-5A |
| Platform-wide rate limiting | EPH-5B |
| OpenAPI spec publication | EPH-5B |
| Structured JSON logging + correlation IDs | EPH-6A |
| OpenTelemetry + Prometheus | EPH-6A |

## Deferred (P2/P3 — dispatch after EPH-6 complete)

Workflow/approval engine (P1) | Retention policies/right-to-erasure (P1) | Glossary hierarchy (P2) | MDM hierarchical values (P2) | Webhook infrastructure (P2) | Column-level lineage (P2, after EPH-2A) | ABAC engine (P2, after EPH-4A) | Slack/Teams integration (P2) | Schema templates (P2) | Storybook (P2) | Async import/export (P2) | LDAP/AD sync (P2) | DQ incident management (P2) | Access review workflows (P2) | GraphQL (P3) | Event sourcing/CQRS (P3) | Federated learning (P3) | Synthetic data (P3).

---

## EPH-0 — AI Expertise Dashboard: Close In-Flight Work
**Date:** 2026-08-26
**Worker Role:** backend-worker
**Recommended Model:** Claude Haiku 3.5
**Status:** DONE (11 tests, commit e34e6d0)
**Kind:** Backend tests only. Small.

### Context
Four files exist uncommitted and ready:
- `backend/ai/maturity_api.py` (232 lines) — `AIMaturityView` at `GET ai/pulse/maturity/`
- `backend/ai/ops_urls.py` — adds `maturity/` route (already wired via `config/urls.py`)
- `carbon-frontend/src/pages/admin/ai/AIExpertisePanel.jsx` (416 lines, 0 lint errors)
- `carbon-frontend/src/App.jsx` + `src/shell/ShellSidebar.jsx` — route + nav link wired
- `carbon-frontend/src/pages/admin/ai/LearningFlywheelPanel.jsx` — minor update

### Files to Read First
- `backend/ai/maturity_api.py` (read fully — understand response structure before writing tests)
- `backend/ai/ops_urls.py` (confirm route name `ai-pulse-maturity`)
- `backend/ai/tests/test_observability_api.py` (test fixture pattern to replicate)

### Files to Change
- `backend/ai/tests/test_maturity_api.py` (NEW)

### Implementation
Write `test_maturity_api.py` covering:
1. `GET /carbon-api/ai/pulse/maturity/` returns 200 for admin user
2. Returns expected top-level keys (inspect `AIMaturityView.get()` return dict)
3. Returns 401 for unauthenticated
4. Returns 403 for regular (non-admin) user
5. Response is CBAC-scoped (query is filtered by `scope_ai_queryset` or equivalent)

No new migration needed.

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_maturity_api.py -v --maxfail=5
# >=4 tests pass

cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint      # 0 new errors
npm run build     # clean
```

### Output
Commit all 7 files: `feat(ai): AI Expertise & Maturity Dashboard (EPH-0)`

---

## EPH-1A — Request Audit Middleware + Structured JSON Logging
**Date:** 2026-08-26
**Worker Role:** backend-worker
**Recommended Model:** Claude Haiku 4.5
**Status:** DONE — commit `29f891f` (15/15 tests, migration `core.0015` applied)
**Kind:** Backend. Medium.
**Closes:** P0-5 (API request audit), P0-6 (data access logging), P1-10 (structured logging)
**Depends on:** EPH-0 done.

### Files to Read First
- `backend/config/settings.py` — `MIDDLEWARE` list, current `LOGGING` config
- `backend/core/models.py` — understand what lives in `core/` (add model here or new file)
- `backend/accounts/models.py` — ScopedRole pattern for IP/org extraction reference
- `backend/requirements.txt` — confirm `python-json-logger` not already present

### Files to Change
- `backend/core/middleware.py` (NEW or EXTEND) — `AuditMiddleware` + `CorrelationIdMiddleware`
- `backend/core/models.py` or `backend/core/audit_models.py` — `RequestAuditLog` model
- `backend/core/migrations/` — migration for `RequestAuditLog`
- `backend/core/log_filters.py` (NEW) — `CorrelationIdFilter` injects correlation_id into log records
- `backend/config/settings.py` — wire middleware, update LOGGING to JSON formatter
- `backend/requirements.txt` — add `python-json-logger>=2.0.7`
- `backend/core/tests/test_audit_middleware.py` (NEW)

### Implementation

**`RequestAuditLog` model:**
```python
class RequestAuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, db_index=True)
    ip_address = models.GenericIPAddressField()
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=500, db_index=True)
    query_string = models.CharField(max_length=500, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True)
    duration_ms = models.PositiveIntegerField(null=True)
    correlation_id = models.CharField(max_length=36, blank=True, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    class Meta:
        ordering = ['-timestamp']
        indexes = [models.Index(fields=['user', 'timestamp']), models.Index(fields=['path', 'timestamp'])]
```

**`AuditMiddleware`** — logs POST/PUT/PATCH/DELETE only:
- Skip paths: `/health/`, `/carbon-api/schema/`, `/static/`, `/mediafiles/`
- Extract real IP: `X-Forwarded-For` first entry (stripped)
- Write `RequestAuditLog` inside `try/except` — NEVER let audit failure break the request
- Read `correlation_id` from `request.correlation_id` (set by `CorrelationIdMiddleware` which runs first)

**`CorrelationIdMiddleware`** — runs before `AuditMiddleware`:
- Read `HTTP_X_REQUEST_ID` from headers or generate `uuid4()`
- Attach to `request.correlation_id` + `response['X-Request-ID']`
- Store in thread-local for log filter injection

**JSON logging** in `settings.LOGGING`:
```python
'formatters': {
    'json': {
        '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
        'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
    },
},
'filters': {'correlation_id': {'()': 'core.log_filters.CorrelationIdFilter'}},
```
Apply JSON formatter + correlation filter to all non-debug handlers.

### Tests (`test_audit_middleware.py`)
- POST creates `RequestAuditLog` with correct method/path/status_code
- GET does NOT create `RequestAuditLog`
- `/health/` endpoint is skipped
- Unauthenticated request logs `user=None`
- IP extracted correctly from `X-Forwarded-For`
- `X-Request-ID` present in response headers
- Middleware exception does NOT propagate (fail-silent guard)

### Verification Gate
```bash
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python manage.py migrate
/home/ahmed/aast/carbon/.venv/bin/python -m pytest core/tests/test_audit_middleware.py -v
# >=7 tests pass
```

---

## EPH-1B — Notification Center (In-App Bell + Panel)
**Date:** 2026-08-26
**Worker Role:** frontend-worker
**Recommended Model:** Raptor mini
**Status:** DONE — commit `5f0709d` (6/6 tests, build clean)
**Kind:** Frontend only. Medium.
**Closes:** P0-8 (unified notification system — backend exists since Phase 1.6)
**Depends on:** EPH-0 done (can run in parallel with EPH-1A — different files).

### Backend API (already exists — DO NOT TOUCH)
- `GET /carbon-api/accounts/notifications/` — paginated `UserAlert` list (newest first)
- `PATCH /carbon-api/accounts/notifications/{id}/mark-read/`
- `POST /carbon-api/accounts/notifications/mark-all-read/`
- `GET /carbon-api/accounts/notifications/unread-count/` — `{count: N}`

### Files to Read First
- `backend/accounts/notification_views.py` — exact endpoint URLs + response shape
- `carbon-frontend/src/components/HeaderEnhanced.jsx` — bell icon location
- `carbon-frontend/src/api/api.js` — `apiFetch` pattern
- `.ai-toolkit/shared/compact-ui.md` — RULE_8 (theme tokens), RULE_16 (layout)

### Files to Change
- `carbon-frontend/src/api/notifications.js` (NEW) — `getNotifications(token,page)`, `getUnreadCount(token)`, `markRead(token,id)`, `markAllRead(token)`
- `carbon-frontend/src/hooks/useNotifications.js` (NEW) — polls unread-count every 30s, returns `{alerts, unreadCount, loading, markRead, markAllRead, refresh}`
- `carbon-frontend/src/components/notifications/NotificationCenter.jsx` (NEW) — Popover anchored to bell
- `carbon-frontend/src/components/HeaderEnhanced.jsx` (MODIFY) — wire bell to `NotificationCenter`, add `Badge badgeContent={unreadCount}`
- `carbon-frontend/src/__tests__/NotificationCenter.test.jsx` (NEW)

### Implementation

**`NotificationCenter.jsx`** — MUI `Popover` (not `Modal`), 380px wide, max 480px tall:
- Header: "Notifications" + "Mark all read" `Button` (disabled when count=0)
- List: each row has level icon (Info/Warning/Error/Success with MUI severity colors) + title (bold) + body (2-line truncated) + relative time + optional link chip
- Clicking row: markRead optimistically + navigate to `alert.link` if set
- Category chips: `Chip size="small" variant="outlined"` per `UserAlert.Category`
- "Load more" button at bottom for pagination
- Empty state: "No notifications" centered with `text.secondary`
- RULE_8: theme tokens only — `warning.main`, `error.main`, `success.main`, `text.secondary`

**`useNotifications`** hook:
- On mount: fetch page 1 + unread count
- `setInterval(30000)` polling for unread count (clear on unmount)
- `markRead(id)`: optimistic `is_read=true` + PATCH
- `markAllRead()`: optimistic clear all + POST

### Tests
- Renders badge with correct unread count
- Renders empty state when no notifications
- Renders notification rows with correct level colors
- Click notification: `markRead` called + navigation to link
- "Mark all read" triggers bulk action
- Loading skeleton during fetch

### DO NOT TOUCH
- `backend/accounts/notification_views.py`, `backend/accounts/models.py`

### Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/NotificationCenter.test.jsx
npm run build
```

---

## EPH-2A — Lineage Graph Model + Impact Analysis API
**Date:** 2026-08-26
**Worker Role:** backend-worker
**Recommended Model:** Claude Haiku 4.5
**Status:** DONE — commit `2688de3` (16/16 tests, migration `catalog.0008` applied)
**Kind:** Backend. Medium-Large.
**Closes:** P0-3 (lineage graph model), P0-4 (impact analysis)
**Depends on:** EPH-1A done.

### Files to Read First
- `backend/catalog/models.py` — existing models; `lineage = JSONField` stub at ~line 305 (this is on `DatasetVersion`, not a graph — we ADD `LineageEdge` as a separate model)
- `backend/dataschema/models.py` — `DataTable`, `DataField` (FKs for LineageEdge)
- `backend/catalog/views.py` — existing viewset/RBAC patterns
- `backend/catalog/urls.py` — URL registration
- `.ai-toolkit/shared/api-contract.md` — REST conventions

### Files to Change
- `backend/catalog/models.py` — add `LineageEdge` model
- `backend/catalog/serializers.py` — `LineageEdgeSerializer`
- `backend/catalog/views.py` — `LineageEdgeViewSet`, `TableLineageView`, `TableImpactView`
- `backend/catalog/urls.py` — new route registrations
- `backend/catalog/services.py` — `get_lineage(table_id, direction, depth)`, `get_impact(table_id, depth=5)`
- `backend/catalog/migrations/` — migration
- `backend/catalog/tests/test_lineage.py` (NEW)

### Model

```python
class LineageEdge(models.Model):
    class EdgeType(models.TextChoices):
        TRANSFORM = 'transform', 'Transform'
        COPY = 'copy', 'Copy'
        AGGREGATE = 'aggregate', 'Aggregate'
        DEPENDENCY = 'dependency', 'Dependency'

    source_table = models.ForeignKey('dataschema.DataTable', on_delete=models.CASCADE, related_name='lineage_outgoing')
    target_table = models.ForeignKey('dataschema.DataTable', on_delete=models.CASCADE, related_name='lineage_incoming')
    # Column lineage (P2 — optional fields now)
    source_field = models.ForeignKey('dataschema.DataField', null=True, blank=True, on_delete=models.SET_NULL, related_name='lineage_outgoing')
    target_field = models.ForeignKey('dataschema.DataField', null=True, blank=True, on_delete=models.SET_NULL, related_name='lineage_incoming')
    edge_type = models.CharField(max_length=20, choices=EdgeType.choices, default=EdgeType.DEPENDENCY)
    transform_description = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('source_table', 'target_table', 'edge_type')]
        indexes = [models.Index(fields=['source_table']), models.Index(fields=['target_table'])]
```

### API Endpoints
```
GET  /carbon-api/catalog/lineage/             — list all edges (paginated; filter ?source=id&target=id)
POST /carbon-api/catalog/lineage/             — register edge (RequireWriteAdmin)
DEL  /carbon-api/catalog/lineage/{id}/        — remove edge (RequireWriteAdmin)
GET  /carbon-api/catalog/tables/{id}/lineage/ — upstream+downstream ?direction=upstream|downstream|both
GET  /carbon-api/catalog/tables/{id}/impact/  — BFS downstream ?depth=5 (max 10)
```

**`get_impact(table_id, depth=5)`** — BFS over `lineage_outgoing`. Cycle-guard: track visited set. Returns `{levels: [{depth:1, tables:[{id,name,module_name,edge_type}]},...], total_affected: N}`.

### Tests (`test_lineage.py`)
- Create edge: stored correctly, `unique_together` enforced
- `GET tables/{id}/lineage/?direction=upstream` returns only incoming
- `GET tables/{id}/lineage/?direction=downstream` returns only outgoing
- `GET tables/{id}/impact/` BFS: A→B→C returns 2 levels, total_affected=2
- Cycle guard: A→B→A does not loop
- 401 for unauthenticated; 403 for non-admin POST
- Cascade: deleting DataTable deletes its LineageEdges

### Verification Gate
```bash
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python manage.py migrate
/home/ahmed/aast/carbon/.venv/bin/python -m pytest catalog/tests/test_lineage.py -v
# >=8 tests pass
```

---

## EPH-2B — PostgreSQL Full-Text Catalog Search
**Date:** 2026-08-26
**Worker Role:** backend-worker
**Recommended Model:** Claude Haiku 4.5
**Status:** DONE — commit `90b6e2e` (20/20 tests, migrations `catalog.0009` + `dataschema.0009` applied)
**Kind:** Backend. Medium.
**Closes:** P0-7 (full-text search — PG FTS, zero new infra)
**Depends on:** EPH-2A done.

### Files to Read First
- `backend/catalog/models.py` — `DataDomain`, `GlossaryTerm`, `AssetProfile`
- `backend/dataschema/models.py` — `DataTable`, `DataField`
- `backend/catalog/views.py` — existing filter/search patterns
- `backend/catalog/urls.py`

### Files to Change
- `backend/catalog/models.py` — add `search_vector = SearchVectorField(null=True)` to `DataTable` + `DataDomain`
- `backend/catalog/migrations/` — migration with GIN index
- `backend/catalog/search_views.py` (NEW) — `CatalogSearchView`
- `backend/catalog/search_index.py` (NEW) — `post_save` signal handlers to update `search_vector`
- `backend/catalog/urls.py` — `path('search/', CatalogSearchView.as_view(), name='catalog-search')`
- `backend/catalog/tests/test_search.py` (NEW)

### Implementation

**SearchVectorField migration** for `DataTable` and `DataDomain` (weight A=name, B=description):
```python
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex
# Add field + GinIndex in migration
```

**Signal handler** updates `search_vector` on `post_save` for `DataTable` and `DataDomain` using `SearchVector('name', weight='A') + SearchVector('description', weight='B')`.

**`CatalogSearchView`**:
```
GET /carbon-api/catalog/search/?q=text&types=table,field,domain,glossary&page=1
```
- `table` + `domain`: use `SearchQuery` against `search_vector` (PostgreSQL ranked)
- `field` + `glossary`: use `Q(name__icontains=q) | Q(description__icontains=q)` (simpler, no GIN needed)
- Apply existing RBAC org-unit scoping
- Returns: `{query, total, results: [{type, id, name, description, url_hint}]}` (page size 20)
- Reject `?q=` shorter than 2 chars with 400

### Tests (`test_search.py`)
- Name match returns table (weight A)
- Description match returns table (weight B)
- `?types=domain` returns only domains
- Mixed type search returns interleaved results
- Empty `?q=` returns 400
- RBAC: org-scoped tables only visible to authorized user

### Verification Gate
```bash
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python manage.py migrate
/home/ahmed/aast/carbon/.venv/bin/python -m pytest catalog/tests/test_search.py -v
# >=6 tests pass
```

---

## EPH-2C — Lineage Graph Visualization (Frontend)
**Date:** 2026-08-26
**Worker Role:** frontend-worker
**Recommended Model:** Raptor mini
**Status:** DONE
**Kind:** Frontend. Medium.
**Depends on:** EPH-2A done (API live).

### Files to Read First
- `carbon-frontend/src/components/graph/EnterpriseGraph.jsx` — REUSE this for rendering
- `carbon-frontend/src/pages/catalog/SchemaDetailPage.jsx` — add tab here (between Relations and Governance)
- `carbon-frontend/src/api/aiWorkspace.js` — apiFetch pattern
- EPH-2A API response shape: `GET tables/{id}/lineage/` + `GET tables/{id}/impact/`

### Files to Change
- `carbon-frontend/src/api/lineage.js` (NEW) — `getTableLineage(tableId,direction)`, `getTableImpact(tableId)`, `createLineageEdge(data)`, `deleteLineageEdge(id)`
- `carbon-frontend/src/pages/catalog/tabs/LineageTab.jsx` (NEW)
- `carbon-frontend/src/pages/catalog/SchemaDetailPage.jsx` (MODIFY) — add "Lineage" tab
- `carbon-frontend/src/__tests__/LineageTab.test.jsx` (NEW)

### Implementation

**`LineageTab.jsx`**:
- Toggle `ToggleButtonGroup`: "Graph" / "Impact" (default Graph)
- **Graph view**: `<EnterpriseGraph nodes={tableNodes} edges={lineageEdges} />` — upstream nodes one color, current table highlighted, downstream another
- **Impact view**: structured list of impact levels — each level = indented group with `Chip` count badge
- Direction filter: `ButtonGroup` upstream / both / downstream
- Empty state: "No lineage registered. Click Add Edge to connect tables."
- "Add Edge" button (admin only): `SystemDialog` with source/target autocomplete + edge type + description

### Tests
- Renders graph view by default
- Toggle switches to impact view
- Empty state renders correctly
- Graph shows upstream + downstream nodes
- Impact view shows correct level structure
- "Add Edge" dialog opens for admin

### Verification Gate
```bash
npm run lint
npx vitest run src/__tests__/LineageTab.test.jsx
npm run build
```

---

## EPH-2D — Catalog Search UI
**Date:** 2026-08-26
**Worker Role:** frontend-worker
**Recommended Model:** Raptor mini
**Status:** DONE
**Kind:** Frontend. Medium.
**Depends on:** EPH-2B done (API live). Parallel with EPH-2C.

### Files to Read First
- `carbon-frontend/src/shell/ShellSidebar.jsx` — where to add search shortcut
- `carbon-frontend/src/App.jsx` — add `/catalog/search` route
- Backend response shape: `{query, total, results: [{type, id, name, description, url_hint}]}`

### Files to Change
- `carbon-frontend/src/api/catalogSearch.js` (NEW) — `searchCatalog(token, q, types, page)`
- `carbon-frontend/src/pages/catalog/SearchPage.jsx` (NEW)
- `carbon-frontend/src/App.jsx` (MODIFY) — add `Route path="/catalog/search"`
- `carbon-frontend/src/shell/ShellSidebar.jsx` (MODIFY) — add search shortcut at top of catalog sidebar
- `carbon-frontend/src/__tests__/SearchPage.test.jsx` (NEW)

### Implementation
- `SearchPage.jsx` at `/catalog/search`: debounced `TextField` + type filter chips (All/Tables/Fields/Domains/Glossary) + results list (type icon chip + name + 2-line description + detail link) + "N results for '...'" + loading skeleton + empty state
- URL params sync (`?q=...&types=...`) for back/forward navigation
- Sidebar: search icon button at top of Catalog sidebar; `onClick` navigate to `/catalog/search`

### Tests
- Renders search input + type chips
- Debounced fetch called on input change
- Results render with type chips + links
- Type filter toggles update results
- Empty state shown when no results
- URL params sync

### Verification Gate
```bash
npm run lint
npx vitest run src/__tests__/SearchPage.test.jsx
npm run build
```

---

## EPH-3A — DQ Profiling Service + Scorecard API
**Date:** 2026-08-26
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE
**Kind:** Backend. Medium-Large.
**Closes:** P1-1 (automated profiling — models exist, service doesn't), P1-2 (DQ scorecard API)
**Depends on:** EPH-2B done.

### Files to Read First
- `backend/dq/models.py` — `TableProfile` + `FieldProfile` (ALREADY EXIST — read fully before writing any code)
- `backend/dq/services.py` — existing run/job patterns
- `backend/dataschema/models.py` — `DataTable`, `DataField`, `DataRow`
- `backend/dq/jobs.py` — Celery/task pattern to replicate

### Files to Change
- `backend/dq/profiling_service.py` (NEW) — `profile_table(table_id)` — populates existing `TableProfile`/`FieldProfile`
- `backend/dq/tasks.py` (NEW or EXTEND) — `profile_table_task` Celery task
- `backend/dq/scorecard_service.py` (NEW) — `compute_scorecard(table_id)` aggregates `DQResult` by DAMA dimension
- `backend/dq/views.py` (EXTEND) — `TableProfileView`, `RunProfileView`, `TableScorecardView`
- `backend/dq/serializers.py` (EXTEND) — profile + scorecard serializers
- `backend/dq/urls.py` (EXTEND) — new routes
- `backend/dq/tests/test_profiling.py` (NEW)

### Implementation

**`profile_table(table_id)`** — populates existing models:
1. Load `DataRow` queryset for table (limit 10_000 rows)
2. For each `DataField`: compute null_count, distinct_count, min/max (all types), mean (numeric only), top 10 values by frequency
3. Create or update `TableProfile` + one `FieldProfile` per field (use `update_or_create` on `data_field`)
4. These models ALREADY exist — do NOT recreate them, populate them

**`compute_scorecard(table_id)`** — returns:
```python
{
    "quality_score": 0.0..1.0,         # weighted average of dimension scores
    "dimensions": {                     # per DAMA dimension
        "completeness": {"passed": N, "failed": M, "score": 0.0..1.0},
        ...                             # validity, accuracy, uniqueness, consistency, timeliness
    },
    "total_rules": N,
    "last_run_at": timestamp,
    "profile_summary": {"row_count": N, "completeness_pct": P, "profiled_at": ts}
}
```
Pull from `DQResult.objects.filter(rule__table_assignments__data_table=table)`.

**API Endpoints**:
```
GET  /carbon-api/dq/tables/{id}/profile/      — latest TableProfile + FieldProfiles
POST /carbon-api/dq/tables/{id}/profile/run/  — trigger async profiling (202 + {task_id})
GET  /carbon-api/dq/tables/{id}/scorecard/    — quality scorecard
```

### Tests (`test_profiling.py`)
- `profile_table()` creates `TableProfile` with correct `row_count`
- `profile_table()` creates `FieldProfile` with correct `null_count`
- `profile_table()` computes correct `distinct_count` for string field
- `profile_table()` computes correct `min`/`max`/`mean` for numeric field
- `compute_scorecard()` returns correct dimension breakdown from `DQResult` fixtures
- `compute_scorecard()` handles table with no DQ results (returns zeros)
- `GET tables/{id}/profile/` returns 404 when no profile yet
- `POST tables/{id}/profile/run/` returns 202

### Verification Gate
```bash
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python -m pytest dq/tests/test_profiling.py -v
# >=8 tests pass
```

---

## EPH-3B — Freshness Monitoring + Staleness Alerts
**Date:** 2026-08-26
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE
**Kind:** Backend. Medium.
**Closes:** P1-3 (freshness monitoring — alerting plumbing already exists via `notify_event`)
**Depends on:** EPH-3A done.

### Files to Read First
- `backend/dataschema/models.py` — `DataTable`, `DataRow` (add `last_data_updated_at` to DataTable)
- `backend/accounts/models.py` — `notify_event()` (line ~540), `NotificationRule.EventType.FRESHNESS_VIOLATION` (already defined!)
- `backend/catalog/models.py` — no freshness policy yet; add `FreshnessPolicy` here
- `backend/dq/jobs.py` — periodic task pattern to replicate

### Files to Change
- `backend/dataschema/models.py` — add `last_data_updated_at = models.DateTimeField(null=True, blank=True)` to `DataTable`
- `backend/dataschema/migrations/` — migration
- `backend/dataschema/signals.py` (NEW or EXTEND) — `post_save` on `DataRow` updates `DataTable.last_data_updated_at`
- `backend/catalog/models.py` — add `FreshnessPolicy` model
- `backend/catalog/migrations/` — migration
- `backend/catalog/freshness_service.py` (NEW) — `check_freshness()` service
- `backend/catalog/tasks.py` (NEW or EXTEND) — `check_freshness_task` periodic Celery task
- `backend/catalog/views.py` (EXTEND) — `FreshnessPolicyView` CRUD
- `backend/catalog/tests/test_freshness.py` (NEW)

### Models

```python
class FreshnessPolicy(models.Model):
    table = models.OneToOneField('dataschema.DataTable', on_delete=models.CASCADE, related_name='freshness_policy')
    max_age_hours = models.PositiveIntegerField(default=24)
    alert_level = models.CharField(max_length=10, default='warning',
        choices=[('info','Info'),('warning','Warning'),('error','Error')])
    enabled = models.BooleanField(default=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_alerted_at = models.DateTimeField(null=True, blank=True)
```

**`check_freshness()`** service — iterate `FreshnessPolicy.objects.filter(enabled=True)`:
1. Compute `age_hours` from `table.last_data_updated_at or table.created_at`
2. If `age_hours > max_age_hours` AND rate-limit (no alert in last 6h): call `notify_event('freshness_violation', ...)` + update `last_alerted_at`
3. Always update `last_checked_at`

**API**:
```
GET  /carbon-api/catalog/tables/{id}/freshness/   — get FreshnessPolicy + last_data_updated_at
POST /carbon-api/catalog/tables/{id}/freshness/   — create/update policy
DEL  /carbon-api/catalog/tables/{id}/freshness/   — remove policy
```

### Tests (`test_freshness.py`)
- `DataRow` save updates `DataTable.last_data_updated_at`
- `check_freshness()` creates UserAlert when data is stale
- `check_freshness()` does NOT alert when data is fresh
- Rate-limit: second alert within 6h is skipped
- `GET tables/{id}/freshness/` returns 404 when no policy

### Verification Gate
```bash
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python manage.py migrate
/home/ahmed/aast/carbon/.venv/bin/python -m pytest catalog/tests/test_freshness.py -v
# >=5 tests pass
```

---

## EPH-3C — DQ Profile + Scorecard + Freshness UI
**Date:** 2026-08-26
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE
**Kind:** Frontend. Medium.
**Depends on:** EPH-3A + EPH-3B both done.

### Files to Read First
- `carbon-frontend/src/pages/catalog/SchemaDetailPage.jsx` — tab structure
- `carbon-frontend/src/pages/catalog/tabs/DQRulesTab.jsx` — sister component patterns
- `carbon-frontend/src/pages/catalog/tabs/SchemaQualityMetrics.jsx` — existing quality surface
- API shapes from EPH-3A (profile: field stats) + EPH-3B (freshness: last_data_updated_at)

### Files to Change
- `carbon-frontend/src/api/profiling.js` (NEW) — `getTableProfile`, `runTableProfile`, `getTableScorecard`, `getTableFreshness`, `saveFreshnessPolicy`
- `carbon-frontend/src/pages/catalog/tabs/TableProfileTab.jsx` (NEW)
- `carbon-frontend/src/pages/catalog/tabs/DQScorecardTab.jsx` (NEW)
- `carbon-frontend/src/pages/catalog/SchemaDetailPage.jsx` (MODIFY) — add "Profile" + "Scorecard" tabs
- `carbon-frontend/src/__tests__/TableProfileTab.test.jsx` (NEW)
- `carbon-frontend/src/__tests__/DQScorecardTab.test.jsx` (NEW)

### Implementation

**`TableProfileTab.jsx`**:
- "Profiled N minutes ago" header + "Run Profile" button (POST `/profile/run/`, show "Profiling..." chip, poll until done)
- `DataGrid` columns: Field Name / Type / Null% / Cardinality / Min / Max / Mean / Top Values (popover on hover showing `top_values` list)
- No-profile state: info alert "No profile yet — click Run Profile"

**`DQScorecardTab.jsx`**:
- Overall quality score: large `CircularProgress` with numeric score in center (0-100%)
- Per-dimension `LinearProgress` bars: Completeness / Validity / Accuracy / Uniqueness / Consistency / Timeliness
- Each bar: name + "N passed / M failed" + score%
- Empty state if no DQ rules assigned

**Freshness indicator** — add to `SchemaQualityMetrics.jsx` (or detail page header):
- Fresh (green chip, "<2h ago") / Stale (orange chip, "26h ago") based on `last_data_updated_at`

### Verification Gate
```bash
npm run lint
npx vitest run src/__tests__/TableProfileTab.test.jsx src/__tests__/DQScorecardTab.test.jsx
npm run build
```

---

## EPH-4A — Column-Level RBAC (FieldAccessPolicy)
**Date:** 2026-08-26
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE
**Kind:** Backend. Large.
**Closes:** P0-1 (column-level access control)
**Depends on:** EPH-3C done.

### Files to Read First
- `backend/dataschema/models.py` — `DataField` (FK target for policy)
- `backend/accounts/models.py` — `ScopedRole`, `get_user_capabilities()` pattern
- `backend/accounts/permissions.py` or `capabilities.py` — existing capability constants
- `backend/dataschema/serializers.py` — `DataFieldSerializer` (extend `to_representation`)
- `.ai-toolkit/shared/cbac.md` — capability-based access control conventions

### Files to Change
- `backend/dataschema/models.py` — add `FieldAccessPolicy` model
- `backend/dataschema/migrations/` — migration
- `backend/accounts/capabilities.py` or equivalent — add `catalog:view_pii` capability constant
- `backend/dataschema/serializers.py` — extend `DataFieldSerializer.to_representation()` to apply policies
- `backend/dataschema/views.py` — ensure `request` in serializer context
- `backend/dataschema/policy_views.py` (NEW) — admin CRUD for `FieldAccessPolicy`
- `backend/dataschema/urls.py` (EXTEND) — field policy admin routes
- `backend/dataschema/tests/test_field_access_policy.py` (NEW)

### Model

```python
class FieldAccessPolicy(models.Model):
    class Action(models.TextChoices):
        DENY = 'deny', 'Deny (hide field entirely)'
        MASK = 'mask', 'Mask (redact value, show field name)'

    field = models.ForeignKey(DataField, on_delete=models.CASCADE, related_name='access_policies')
    required_capability = models.CharField(max_length=100,
        help_text='Users WITHOUT this cap are denied/masked. E.g. catalog:view_pii')
    action = models.CharField(max_length=10, choices=Action.choices, default=Action.DENY)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('field', 'required_capability')]
```

**Serializer filtering** in `DataFieldSerializer.to_representation()`:
- Get `user_caps = get_user_capabilities(request.user)`
- For each `FieldAccessPolicy` on the field:
  - If `required_capability not in user_caps` AND `action == 'deny'`: return `{id, name, access_denied: True}` (minimal safe response)
  - If `required_capability not in user_caps` AND `action == 'mask'`: return full data with `is_masked: True`
- Superuser bypasses all policies

**New capability**: add `catalog:view_pii` to capability constants. Assign to Data Owner + HR groups by default (document this in output — DO NOT silently change group permissions without a management command).

### Tests (`test_field_access_policy.py`)
- User WITH `catalog:view_pii` sees full field data
- User WITHOUT `catalog:view_pii` gets `{id, name, access_denied: True}` when action=deny
- User WITHOUT gets `is_masked: True` when action=mask
- Superuser always sees full field (bypass)
- Create policy: 403 for non-admin, 201 for admin
- Delete policy: 403 for non-admin
- Cascade: delete DataField deletes its policies

### Verification Gate
```bash
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python manage.py migrate
/home/ahmed/aast/carbon/.venv/bin/python -m pytest dataschema/tests/test_field_access_policy.py -v
# >=7 tests pass
```

### Result (2026-08-26) — DONE
- `FieldAccessPolicy` model + migration `dataschema.0011_fieldaccesspolicy` added.
- New capability `catalog:view_pii` registered; granted to `dataowners_group` ONLY.
  NOT implied by `catalog:view` (sensitive, distinct). There is no "HR" group in
  this codebase — a future HR/other group must be granted via admin/management
  command, not by silently editing `GROUP_CAPABILITIES`.
- `DataFieldSerializer.to_representation()` applies deny/mask with request-context
  guard and superuser bypass via `has_capability` (handles `"*"` wildcard).
- Admin CRUD `GET/POST /dataschema/fields/{id}/policies/` + `DELETE .../{pk}/`,
  gated by `AdminOrSuperuserOnly` + `dataschema:manage`.
- 9 tests pass; full dataschema+accounts suite 422 passed; check/migrations clean.

---

## EPH-4B — Data Masking Engine
**Date:** 2026-08-26
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE ✅
**Kind:** Backend. Medium.
**Closes:** P0-2 (data masking)
**Depends on:** EPH-4A done (`FieldAccessPolicy` + `catalog:view_pii` established).

> **Result (commit `039489d`):** `DataField.masking_strategy` added; `MaskingService.mask_value()`
> implemented; `DataRowSerializer.to_representation()` masks PII-classified and
> `FieldAccessPolicy(mask)` fields when caller lacks `catalog:view_pii`; `DataRowViewSet`
> prefetches fields/access-policies/catalog-profile. 8 tests pass; 552 across
> dataschema/accounts/catalog pass. Fix: DataRow detail tests require `?data_table=` query param.

### Files to Read First
- `backend/dataschema/models.py` — `DataField` (add `masking_strategy`), `DataRow` (where masking is applied)
- `backend/dataschema/serializers.py` — `DataRowSerializer` (extend to mask field values)
- `backend/catalog/models.py` — `AssetProfile.classification == 'pii'` (auto-masking trigger)

### Files to Change
- `backend/dataschema/models.py` — add `masking_strategy` CharField to `DataField`
- `backend/dataschema/migrations/` — migration
- `backend/dataschema/masking.py` (NEW) — `MaskingService.mask_value(value, strategy)`
- `backend/dataschema/serializers.py` — extend `DataRowSerializer` to apply masking
- `backend/dataschema/tests/test_masking.py` (NEW)

### Implementation

**`DataField.masking_strategy`**:
```python
MASKING_STRATEGY_CHOICES = [
    ('none', 'None'), ('redact', '[REDACTED]'),
    ('hash', 'Hash (SHA-256 12-char)'), ('truncate', 'Truncate (3 chars + ***)'),
    ('null', 'Null (empty)'),
]
masking_strategy = models.CharField(max_length=20, choices=MASKING_STRATEGY_CHOICES, default='none')
```

**`MaskingService.mask_value(value, strategy)`**:
- `redact` → `'[REDACTED]'`
- `hash` → `'h:' + sha256(str(value))[:12]`
- `truncate` → `str(value)[:3] + '***'` (or `'***'` if len < 3)
- `null` → `None`
- `none` / unknown → `'[REDACTED]'` (fail-safe default)

**`DataRowSerializer`** masking — for each field value in a row:
- Check: field has `FieldAccessPolicy(action='mask')` for current user (EPH-4A handles this)
- OR: field's `AssetProfile.classification == 'pii'` AND `masking_strategy != 'none'` AND user lacks `catalog:view_pii`
- Apply `MaskingService.mask_value(raw_value, field.masking_strategy)` if either condition holds

### Tests (`test_masking.py`)
- `mask_value('John Smith', 'redact')` → `'[REDACTED]'`
- `mask_value('John Smith', 'truncate')` → `'Joh***'`
- `mask_value('abc', 'hash')` → 14-char `'h:...'` string
- `mask_value('x', 'null')` → `None`
- DataRow API: PII field masked for non-PII user
- DataRow API: PII field NOT masked for user with `catalog:view_pii`
- `masking_strategy='none'` — no masking even when classification=pii

### Verification Gate
```bash
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python manage.py migrate
/home/ahmed/aast/carbon/.venv/bin/python -m pytest dataschema/tests/test_masking.py -v
# >=7 tests pass
```

---

## EPH-4C — Field Visibility + Masking UI
**Date:** 2026-08-26
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** PLANNED
**Kind:** Frontend. Medium.
**Depends on:** EPH-4A + EPH-4B done.

### Files to Read First
- `carbon-frontend/src/pages/catalog/tabs/SchemaStructureTab.jsx` — field rows to annotate
- EPH-4A response shape: `DataField` may have `access_denied: true` or `is_masked: true`
- EPH-4B response shape: `DataRow` field values may be `'[REDACTED]'` or `null`

### Files to Change
- `carbon-frontend/src/pages/catalog/tabs/SchemaStructureTab.jsx` (MODIFY) — lock icon for `access_denied`, mask icon for `is_masked`
- `carbon-frontend/src/api/fieldPolicies.js` (NEW) — `getFieldPolicies(fieldId)`, `createFieldPolicy(data)`, `deleteFieldPolicy(id)`, `updateFieldMaskingStrategy(fieldId, strategy)`
- `carbon-frontend/src/pages/admin/catalog/FieldPoliciesPanel.jsx` (NEW) — admin panel at `/admin/catalog/field-policies`
- `carbon-frontend/src/__tests__/SchemaStructureTab.access.test.jsx` (NEW)

### Implementation

**`SchemaStructureTab.jsx`** field row changes:
- `field.access_denied === true` → render `LockIcon` (gray) + "(Access Restricted)" text, mute all other cells
- `field.is_masked === true` → render `VisibilityOffIcon` (orange) + "Masked" `Chip size="small"`, tooltip: "Values masked per data policy"
- Admin view: show `masking_strategy` select inline per field (updates via PATCH)

**`FieldPoliciesPanel.jsx`** (admin at `/admin/catalog/field-policies`):
- Table: Field Name / Required Capability / Action / Created By / Actions
- Add form: field search (autocomplete against `/dataschema/fields/`) + capability input + action select
- Masking strategy per field: `None / [REDACTED] / Hash / Truncate / Null` (select updates `masking_strategy`)

### Tests
- Renders `LockIcon` for `access_denied` field
- Renders `VisibilityOffIcon` + Masked chip for `is_masked` field
- Normal field renders without access icons
- Admin sees FieldPoliciesPanel add form
- Non-admin does not see admin panel

### Verification Gate
```bash
npm run lint
npx vitest run src/__tests__/SchemaStructureTab.access.test.jsx
npm run build
```

---

## EPH-5A — Structured Error Codes + API Version Header
**Date:** 2026-08-26
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE ✅
**Kind:** Backend. Small-Medium.
**Closes:** P1-9 (structured error codes), P1-7 (API versioning)
**Depends on:** EPH-4B done.

> **Result (commit `5e2335d`):** `core/error_codes.py` taxonomy (17 codes) + `CarbonAPIError`;
> `core/exception_handler.py` wraps the existing `catalog.data_trust_exception_handler`
> (single source of truth preserved — no competing handler) and adds `error_code` to every
> error envelope; `ApiVersionMiddleware` adds `API-Version: 1`. 5 tests pass; 532 across
> core/catalog/accounts pass; live curl confirms header + `ERR_AUTH_001` on 401. Note:
> `core/feedback.unified_exception_handler` is dead code — NOT wired.

### Files to Read First
- `backend/core/feedback.py` — existing exception classes (extend, not replace)
- `backend/config/settings.py` — `REST_FRAMEWORK` exception handler setting
- Existing error format in `backend/accounts/views.py` (check current 404/403 shape)

### Files to Change
- `backend/core/error_codes.py` (NEW) — error code taxonomy + `CarbonAPIError` base exception
- `backend/core/exception_handler.py` (NEW) — custom DRF exception handler
- `backend/core/middleware.py` (EXTEND) — `ApiVersionMiddleware` adds `API-Version: 1` header
- `backend/config/settings.py` (MODIFY) — wire `EXCEPTION_HANDLER` + `ApiVersionMiddleware`
- `backend/core/tests/test_error_codes.py` (NEW)

### Implementation

**`core/error_codes.py`** — minimal taxonomy to start (extend later):
```python
ERROR_CODES = {
    'ERR_AUTH_001': 'Authentication required',
    'ERR_AUTH_002': 'Token expired',
    'ERR_AUTH_003': 'Insufficient permissions',
    'ERR_CAT_001': 'Table not found',
    'ERR_CAT_002': 'Field not found',
    'ERR_CAT_003': 'Schema is locked',
    'ERR_DQ_001': 'DQ rule not found',
    'ERR_DQ_002': 'Rule execution failed',
    'ERR_DQ_003': 'Rule already assigned',
    'ERR_MDM_001': 'Reference set not found',
    'ERR_MDM_002': 'Invalid lifecycle transition',
    'ERR_SCH_001': 'DataTable not found',
    'ERR_VAL_001': 'Required field missing',
    'ERR_VAL_002': 'Invalid value',
    'ERR_VAL_003': 'Duplicate entry',
    'ERR_AI_001': 'AI service unavailable',
    'ERR_AI_002': 'Rate limit exceeded',
}

class CarbonAPIError(Exception):
    def __init__(self, error_code, detail=None, status_code=400):
        self.error_code = error_code
        self.detail = detail or ERROR_CODES.get(error_code, 'Error')
        self.status_code = status_code
        super().__init__(self.detail)
```

**Custom DRF exception handler** — wraps default handler, adds `error_code` + `error_message` to response body. Infers code from exception type (404→ERR_CAT_001 context-free, but better than nothing).

**`ApiVersionMiddleware`** — adds `API-Version: 1` to every response (2 lines).

### Tests
- `CarbonAPIError('ERR_AUTH_003').detail` == 'Insufficient permissions'
- 404 response body contains `error_code` key
- 403 response body contains `error_code` key
- All responses have `API-Version: 1` header
- `CarbonAPIError` with unknown code gets default 'Error' message

### Verification Gate
```bash
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python -m pytest core/tests/test_error_codes.py -v
# >=5 tests pass; manual curl confirms API-Version header + error_code in 404
```

---

## EPH-5B — Rate Limiting
**Date:** 2026-08-26
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE ✅
**Kind:** Backend. Medium.
**Closes:** P1-8 (rate limiting)
**Depends on:** EPH-5A done.

> **RESULT (2026-08-27):** Delivered + verified. `core/throttling.py` (4 scoped classes:
> `UserMinuteRateThrottle` 1000/min, `AnonMinuteRateThrottle` 60/min, `AIRateThrottle` 60/min,
> `HeavyRateThrottle` 10/min) added to `DEFAULT_THROTTLE_CLASSES`/`DEFAULT_THROTTLE_RATES`;
> `AIRateThrottle` on `WorkspaceConversationViewSet`, `HeavyRateThrottle` on
> `ExportProjectViewSet` + `ImportJobViewSet`. 5/5 throttle tests; regression
> core/catalog/accounts/mdm/importexport = 622 passed + 11 subtests. Live: 62 anon POSTs →
> 60× 401 then 429,429; 429 body = structured envelope with `Retry-After` + `error_code:
> ERR_AI_002`. One test-side fix by master: DRF's `SimpleRateThrottle.THROTTLE_RATES` is a
> class-attribute import-time snapshot, so `override_settings` cannot change effective rates —
> tests use `mock.patch.object`. Commit `(see git log)`. OpenAPI half → EPH-5C.

> ⚠️ **SCOPE NOTE (master-architect 2026-08-27):** Original spec combined rate limiting + OpenAPI.
> The OpenAPI half was SPLIT OUT to EPH-5C because the platform ALREADY ships drf-yasg
> (dev-gated swagger UI at `/carbon-api/swagger/`, ~85 `@swagger_auto_schema` decorator sites,
> `mdm/tests/test_swagger_docs.py`) and ADR 0003 (Proposed) plans the drf-spectacular migration
> as its own effort. This phase delivers rate limiting ONLY.

### Files to Read First
- `backend/config/settings.py` — existing `REST_FRAMEWORK` throttle config (ALREADY has `DEFAULT_THROTTLE_CLASSES` = AnonRateThrottle + UserRateThrottle, `DEFAULT_THROTTLE_RATES` = anon 100/hour + user 1000/hour + login scope) — extend, do not replace
- `backend/accounts/views.py` line ~105 — `LoginRateThrottle(ScopedRateThrottle)` pattern (the house style for throttle classes)
- `backend/ai/workspace_api.py` — `WorkspaceConversationViewSet` (line ~58) — AI throttle target
- `backend/importexport/views.py` — `ExportProjectViewSet` (line ~19), `ImportJobViewSet` (line ~68) — heavy throttle targets

### Files to Change
- `backend/core/throttling.py` (NEW) — 4 custom throttle classes
- `backend/config/settings.py` (MODIFY) — add rates to `DEFAULT_THROTTLE_RATES` + add per-minute classes to `DEFAULT_THROTTLE_CLASSES`
- `backend/ai/workspace_api.py` (MODIFY) — apply `AIRateThrottle` to `WorkspaceConversationViewSet`
- `backend/importexport/views.py` (MODIFY) — apply `HeavyRateThrottle` to `ExportProjectViewSet` + `ImportJobViewSet`
- `backend/core/tests/test_throttle.py` (NEW)

### Implementation

**`core/throttling.py`** — follow the `LoginRateThrottle(ScopedRateThrottle)` house pattern
(scoped classes; rates live in `DEFAULT_THROTTLE_RATES`, never hardcoded in the class):
```python
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

class UserMinuteRateThrottle(UserRateThrottle):
    """Per-user per-minute cap (complement to the hourly cap)."""
    scope = 'user_minute'

class AnonMinuteRateThrottle(AnonRateThrottle):
    """Per-IP per-minute cap for anonymous traffic."""
    scope = 'anon_minute'

class AIRateThrottle(UserRateThrottle):
    """Per-user cap on AI generation endpoints (complement to the in-app RateLimiter)."""
    scope = 'ai'

class HeavyRateThrottle(UserRateThrottle):
    """Per-user cap on heavy export/import endpoints."""
    scope = 'heavy'
```

**`settings.py`** — in `REST_FRAMEWORK`:
- `DEFAULT_THROTTLE_CLASSES`: append `'core.throttling.UserMinuteRateThrottle', 'core.throttling.AnonMinuteRateThrottle'`
  (keep the existing anon/user hourly classes — both apply, stricter wins)
- `DEFAULT_THROTTLE_RATES`: add `'user_minute': '1000/min'`, `'anon_minute': '60/min'`, `'ai': '60/min'`, `'heavy': '10/min'`

**AI views** — on `WorkspaceConversationViewSet` in `ai/workspace_api.py` add
`throttle_classes = [AIRateThrottle]` (class attribute, DRF house style — NOT the decorator).
Do NOT touch the existing in-app `RateLimiter`; this is a view-layer complement.

**Import/export views** — on `ExportProjectViewSet` and `ImportJobViewSet` in
`backend/importexport/views.py` add `throttle_classes = [HeavyRateThrottle]`.

**Tests (`core/tests/test_throttle.py`)** — clear `django.core.cache.cache` in `setUp` (throttle
buckets live in cache; LocMemCache persists per process). Use `override_settings` with a
rebuilt `REST_FRAMEWORK` dict when overriding rates:
```python
from django.test import override_settings
from django.conf import settings

def _rates(**overrides):
    rf = {**settings.REST_FRAMEWORK}
    rf['DEFAULT_THROTTLE_RATES'] = {**rf['DEFAULT_THROTTLE_RATES'], **overrides}
    return {'REST_FRAMEWORK': rf}
```
- `test_user_throttle_429_with_retry_after`: `@override_settings(**_rates(user_minute='1/minute'))`,
  authenticated user (fixtures `create_user` + `get_token_for_user` from conftest) hits a GET
  endpoint twice → 2nd response 429, `Retry-After` header present
- `test_anon_throttle_lower_rate`: `@override_settings(**_rates(anon_minute='1/minute'))`,
  anonymous client hits an anon-accessible DRF endpoint (use `POST /carbon-api/token/` with
  bad creds — it's `ThrottledTokenObtainPairView`, anonymous-accessible) twice → 2nd 429
- `test_ai_throttle_applied`: assert `WorkspaceConversationViewSet.throttle_classes == [AIRateThrottle]`
  (import both) — proves wiring without network calls
- `test_heavy_throttle_applied`: assert `ImportJobViewSet.throttle_classes == [HeavyRateThrottle]`
- `test_default_rates_present`: assert `'user_minute'`/`'anon_minute'`/`'ai'`/`'heavy'` in
  `settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']`

### Do NOT touch
- `backend/requirements.txt` (no new deps in this phase — drf-spectacular is EPH-5C)
- `backend/config/urls.py` (no schema endpoints here — EPH-5C)
- The existing `RateLimiter` inside `backend/ai/` (in-app guard stays untouched)
- Any frontend files, any migrations

### Tests
- 429 with `Retry-After` after 1/minute override
- Anonymous throttle triggers at lower rate
- AI + Heavy throttle wiring assertions
- Default rates present in settings

### Verification Gate
```bash
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run   # No changes detected
/home/ahmed/aast/carbon/.venv/bin/python -m pytest core/tests/test_throttle.py -v --create-db   # >=5 pass
/home/ahmed/aast/carbon/.venv/bin/python -m pytest core/ catalog/ accounts/ -q --create-db   # regression, no throttle flakiness
```

---

## EPH-5C — OpenAPI Spec (drf-yasg → drf-spectacular migration, ADR 0003)
**Date:** 2026-08-27
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE ✅ (`537c2c5`, 2026-08-27 — verified by master-architect)
**Kind:** Backend. Medium-Large.
**Closes:** P1 OpenAPI (prod-accessible, versioned API docs)
**Depends on:** EPH-5B done.

> Executes the migration ADR 0003 (Proposed) proposes: replace unmaintained drf-yasg with
> drf-spectacular. `drf-yasg` is currently in `INSTALLED_APPS`, dev-gated swagger UI at
> `/carbon-api/swagger/` (config/urls.py ~line 95-128), ~85 `@swagger_auto_schema` decorator
> sites across `accounts/views.py`, `catalog/views.py`, `catalog/dataset_views.py`, `dq/views.py`,
> `emissions/views.py`, `mdm/views.py`, and `mdm/tests/test_swagger_docs.py` asserts schema content.

### Implementation (ADR 0003 steps)
1. `requirements.txt` — remove `drf-yasg`, add `drf-spectacular>=0.27`
2. `config/settings.py` — `INSTALLED_APPS`: replace `'drf_yasg'` → `'drf_spectacular'`; add
   `SPECTACULAR_SETTINGS = {'TITLE': 'Carbon Data Trust Platform API', 'VERSION': '1.0.0'}`;
   remove `SWAGGER_USE_COMPAT_RENDERERS` (and any `SWAGGER_SETTINGS`)
3. `config/urls.py` — replace the `IS_DEVELOPMENT` get_schema_view block with
   `SpectacularAPIView` at `/carbon-api/schema/`, `SpectacularSwaggerView` at
   `/carbon-api/schema/swagger-ui/`, `SpectacularRedocView` at `/carbon-api/schema/redoc/` —
   gated `AdminOrSuperuserOnly` (from `accounts.permissions`), available in all envs
4. Replace every `@swagger_auto_schema(...)` with the drf-spectacular equivalent
   (`@extend_schema(...)`); `manual_parameters` → `parameters`, `request_body` → `request`,
   `responses` keep `{status: serializer}` shape; keep `swagger_fake_view` guards (they are
   harmless; spectacular sets `swagger_fake_view` the same way)
5. Rewrite `mdm/tests/test_swagger_docs.py` to hit `/carbon-api/schema/?format=json` with an
   admin user and assert endpoint coverage

### Verification Gate
```bash
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python -m pytest mdm/tests/test_swagger_docs.py -v --create-db
/home/ahmed/aast/carbon/.venv/bin/python -m pytest core/ catalog/ accounts/ mdm/ dq/ -q --create-db  # full regression
# Manual (backend running): curl -u admin http://localhost:8009/carbon-api/schema/?format=json → valid OpenAPI
```

---

## EPH-6A — Structured JSON Logging + OpenTelemetry + Prometheus
**Date:** 2026-08-26
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE ✅ (2026-08-27, commit `8e2e480`)
**Kind:** Backend. Medium-Large.
**Closes:** P1-10 (structured logging), P1-11 (OpenTelemetry/Prometheus)
**Depends on:** EPH-5B done.

### Files to Read First
- `backend/config/settings.py` — current `LOGGING` config
- `backend/healthy/views.py` — existing `/health/metrics/` (extend, not replace)
- `backend/requirements.txt` — check existing observability deps

### Files to Change
- `backend/requirements.txt` — add `python-json-logger>=2.0.7`, `django-prometheus`, `opentelemetry-sdk`, `opentelemetry-instrumentation-django`
- `backend/config/settings.py` — update `LOGGING` JSON formatter + `django_prometheus` in `INSTALLED_APPS` + `MIDDLEWARE`
- `backend/healthy/views.py` (EXTEND) — `GET /health/prometheus/` returns `generate_latest()`
- `backend/core/telemetry.py` (NEW) — `Counter`, `Histogram`, `Gauge` metric definitions
- `backend/core/log_filters.py` (NEW) — `CorrelationIdFilter` for thread-local injection
- `backend/config/urls.py` (EXTEND) — add Prometheus metrics endpoint
- `backend/core/tests/test_metrics.py` (NEW)

### Implementation

**Prometheus metrics** (`core/telemetry.py`):
```python
from prometheus_client import Counter, Histogram, Gauge
api_requests_total = Counter('carbon_api_requests_total', 'Total API requests', ['method', 'status', 'app'])
api_duration_seconds = Histogram('carbon_api_duration_seconds', 'API duration', ['app'])
dq_runs_total = Counter('carbon_dq_runs_total', 'DQ rule executions', ['status'])
ai_conversations_active = Gauge('carbon_ai_conversations_active', 'Active AI conversations')
```

**`GET /health/prometheus/`** — expose `generate_latest()` on a path NOT subject to `SECURE_SSL_REDIRECT` (add to `SECURE_REDIRECT_EXEMPT` or use `http_method_not_allowed` guard — see CB-09 in team memory).

**OpenTelemetry** — `opentelemetry-instrumentation-django` auto-instruments Django. Export via `OTEL_EXPORTER_OTLP_ENDPOINT` env var (default empty = disabled).

**JSON logging** — update `LOGGING` `formatters.json` using `pythonjsonlogger.jsonlogger.JsonFormatter`. Add `CorrelationIdFilter` to all handlers (injects `correlation_id` from thread-local set by `CorrelationIdMiddleware` in EPH-1A).

### Tests (`test_metrics.py`)
- `GET /health/prometheus/` returns 200 with `text/plain` content-type
- Response body contains `carbon_api_requests_total` metric name
- JSON log entry is valid JSON with `levelname`, `name`, `message`
- Correlation ID appears in log when `X-Request-ID` header is sent

### Verification Gate
```bash
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python -m pytest core/tests/test_metrics.py -v
# >=4 tests pass
# Manual: curl http://127.0.0.1:8009/health/prometheus/ → Prometheus text format (no HTTPS redirect)
```

---

## EPH-6B — Grafana Dashboards + Prometheus Scrape Config
**Date:** 2026-08-26
**Worker Role:** devops-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE ✅ (2026-08-27, commit `37f3977`)
**Kind:** DevOps. Small.
**Depends on:** EPH-6A done (Prometheus metrics endpoint live).

### Files to Read First
- `deploy/carbon/` — existing deployment config
- `docs/DEPLOYMENT_PLAN_AASTMT_CARBON.md` — VPS setup + existing Grafana/Prometheus

### Files to Change
- `deploy/carbon/grafana/dashboards/carbon-api.json` (NEW) — API dashboard
- `deploy/carbon/grafana/dashboards/carbon-dq.json` (NEW) — DQ dashboard
- Existing `prometheus.yml` on VPS — add Carbon scrape target

### Implementation

> ⚠️ **Shipped reality (2026-08-27) supersedes the draft below** — see
> `TASK-RESULTS-EPH-6B.md`. Key corrections: prod target is `127.0.0.1:8006`
> (dev `8009`), `metrics_path` must be `/carbon-api/health/prometheus/`
> (full `API_PREFIX`), and the metrics view lives in `config/health_views.py`
> (`prometheus_metrics_view`), not `backend/healthy/views.py`.

**Prometheus scrape** (add to VPS `prometheus.yml` — HTTP NOT HTTPS to avoid CB-09 SSL redirect bug):
```yaml
- job_name: 'carbon-backend'
  static_configs:
    - targets: ['127.0.0.1:8006']   # prod; dev = 127.0.0.1:8009
  metrics_path: '/carbon-api/health/prometheus/'
  scheme: 'http'
```

**Carbon API Grafana dashboard** (JSON panels):
- API request rate by app (5m rate of `carbon_api_requests_total`)
- P50/P95/P99 latency (`carbon_api_duration_seconds`)
- Error rate (4xx + 5xx)
- Active AI conversations (`carbon_ai_conversations_active`)
- Alert rule: error_rate > 5% for 5min

**Carbon DQ dashboard**:
- DQ runs/day (`carbon_dq_runs_total`)
- Pass/fail/skip ratio (stacked bar)
- Freshness violations over time
- Tables with quality_score < 0.7 (from scorecard API — Grafana JSON panel with query)

### Verification Gate
```bash
# On VPS:
curl -s http://127.0.0.1:8009/health/prometheus/ | head -5   # Prometheus text format
# In Grafana: import JSON dashboards — all panels load without errors
```

---

## EPH-6C — Freshness Violations Gauge + Prometheus Alert Rules
**Date:** 2026-08-27
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** DONE ✅ (2026-08-27, commit `3a29eb3`)
**Kind:** Backend + DevOps. Small.
**Closes:** P1-3 follow-up flagged in `TASK-RESULTS-EPH-6B.md` (freshness
observability gap — no Prometheus gauge for staleness).
**Depends on:** EPH-3B (freshness service) + EPH-6A/6B (Prometheus stack).

### Files to Read First
- `backend/catalog/freshness_service.py` — `check_freshness()` (EPH-3B)
- `backend/catalog/tasks.py` — `check_freshness_task` (invoked by the cognition
  supervisor loop every `COGNITION_FRESHNESS_INTERVAL` = 21600s / 6h)
- `backend/core/telemetry.py` — existing Prometheus collectors (EPH-6A)
- `deploy/carbon/prometheus/prometheus.yml.example` — scrape config (EPH-6B)

### Files to Change
- `backend/core/telemetry.py` (EXTEND) — freshness collectors
- `backend/catalog/freshness_service.py` (EXTEND) — record metrics in `check_freshness()`
- `backend/catalog/tests/test_freshness_metrics.py` (NEW) — metric tests
- `deploy/carbon/prometheus/carbon-alerts.yml` (NEW) — Prometheus alert rules
- `deploy/carbon/prometheus/prometheus.yml.example` (EXTEND) — `rule_files`

### New Metrics (in `core/telemetry.py`)

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `carbon_freshness_stale_tables` | Gauge | — | Tables with an enabled policy over `max_age_hours` (last pass snapshot) |
| `carbon_freshness_tables_total` | Gauge | — | Enabled policies checked in the last pass |
| `carbon_freshness_alerts_total` | Counter | `severity` | Freshness violation alerts raised |
| `carbon_freshness_table_age_hours` | Gauge | `table_id`, `table` | Hours since last data update, per enabled policy (bounded cardinality = #enabled policies) |

### Wiring

`check_freshness()` (already returns `{checked, alerted, skipped}`):
- Per policy: `freshness_table_age_hours.labels(table_id, table).set(age_hours)`;
  track `stale_count` for `is_stale` (regardless of alert rate-limit).
- On alert: `freshness_alerts_total.labels(severity=policy.alert_level).inc()`.
- End of pass: `freshness_tables_total.set(checked)` +
  `freshness_stale_tables.set(stale_count)` (set = snapshot per pass).

**Alert rules** (`deploy/carbon/prometheus/carbon-alerts.yml`):
- `CarbonStaleDataTable` — `carbon_freshness_stale_tables > 0` for 15m, severity warning.
- `CarbonAPIErrorRateHigh` — 5xx share > 5% for 10m, severity critical
  (`sum(rate(...{status=~"5.."}[5m])) / clamp_min(sum(rate(...)), 1) * 100 > 5`).

### Tests (`test_freshness_metrics.py`)
- Stale gauge counts stale policy tables; fresh tables → `0.0`
- Alert counter increments per severity (relative to registry baseline — the
  `prometheus_client` default registry is shared across tests)
- Rate-limited alert is NOT re-counted (counter delta 0) while stale gauge stays 1
- Per-table age gauge carries `table_id` + `table` labels

### Verification Gate
```bash
cd backend && ../.venv/bin/python -m pytest catalog/tests/test_freshness_metrics.py -q
../.venv/bin/python manage.py check
curl -s http://localhost:8009/carbon-api/health/prometheus/ | grep carbon_freshness
# All 4 metric families present; non-zero values after an in-process freshness pass
```

---

## EPH Dispatch Order & Parallelism

```
IMMEDIATE:
  EPH-0   — backend-worker     (AI Expertise Panel tests + commit)

SPRINT 1 (parallel):
  EPH-1A  — backend-worker     (Audit Middleware + JSON Logging)
  EPH-1B  — frontend-worker    (Notification Center) — parallel with EPH-1A, different files

SPRINT 2 (parallel):
  EPH-2A  — backend-worker     (Lineage Graph + Impact API)
  EPH-2B  — backend-worker     (Full-Text Search) — PARALLEL with EPH-2A (different models)
  EPH-2C  — frontend-worker    — after EPH-2A done
  EPH-2D  — frontend-worker    — after EPH-2B done; parallel with EPH-2C

SPRINT 3 (parallel):
  EPH-3A  — backend-worker     (DQ Profiling Service + Scorecard)
  EPH-3B  — backend-worker     (Freshness Monitoring) — PARALLEL with EPH-3A (different files)
  EPH-3C  — frontend-worker    — after EPH-3A + EPH-3B done

SPRINT 4 (sequential — each depends on previous):
  EPH-4A  — backend-worker     (Column-Level RBAC)
  EPH-4B  — backend-worker     — after EPH-4A
  EPH-4C  — frontend-worker    — after EPH-4A + EPH-4B

SPRINT 5 (sequential):
  EPH-5A  — backend-worker     (Error Codes + API Version)   ✅ DONE (5e2335d + 1d34da5)
  EPH-5B  — backend-worker     — after EPH-5A (Rate Limiting) — scoped to rate limiting ONLY (OpenAPI split to 5C)
  EPH-5C  — backend-worker     — after EPH-5B (OpenAPI: drf-spectacular migration, ADR 0003) ✅ DONE (537c2c5)

SPRINT 6:
  EPH-6A  — backend-worker     ✅ (OTel + Prometheus + JSON Logging full wiring)
  EPH-6B  — devops-worker      ✅ (Grafana dashboards + scrape config)
  EPH-6C  — backend-worker     ✅ (Freshness gauges + Prometheus alert rules)
```

**I18N-4 can run in parallel with any EPH sprint** — frontend-only, touches different files.

**Master Architect runs all terminal verification gates before marking any phase DONE.**
All P0 blockers closed at end of Sprint 4. All target P1 gaps closed at end of Sprint 6
(freshness observability gap closed by EPH-6C).
