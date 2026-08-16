
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
