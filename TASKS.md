
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

**Status:** PENDING
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
