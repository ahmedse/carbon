
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

**Date:** 2026-08-18
**Worker Role:** qa-validator
**Recommended Model:** DeepSeek-V3
**Status:** READY (handoff)
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
**Status:** PLANNED
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
**Status:** ACTIVE
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
**Status:** IN PROGRESS
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
**Status:** IN PROGRESS
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

**Status:** Not started
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

**Status:** Not started
**Worker Role:** frontend-worker
**Recommended Model:** DeepSeek V4-Flash
**Spec:** `docs/DESIGN-PLATFORM.md` §11
**Kind:** Frontend-only. Medium-large.
**Depends on:** P4-A (endpoints).

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
