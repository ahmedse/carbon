
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
**Status:** PENDING
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
   - Step 3 (result): return `{"status":"completed", "task_id":task_id, "result":{"rule_preview":{...}, "test_summary":{"total_rows","applicable_rows","passed","failed"}, "violations":[...], "recommendation":"..."}}`.
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
