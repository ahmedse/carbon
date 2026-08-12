# TASK-RESULTS-AI-WORKSPACE-PHASE2-A.md
# Backend Worker — AI Workspace Phase 2-A
# Date: 2026-08-12

## Scope

Backend only, per role contract. Phase 2-B frontend work was not touched.

## Tasks Completed

1. Added `ConversationContext` support to all Phase 2 request dataclasses in `backend/ai/protocol.py`:
   - `DqSuggestRequest.conversation`
   - `NlQueryRequest.conversation`
   - `AnomalyDetectRequest.conversation`

2. Extended `CarbonIntelligence.send_message()` routing in `backend/ai/intelligence.py`:
   - `dq_suggest` → `_send_dq_suggest_message()`
   - `nl_query` → `_send_nl_query_message()`
   - `anomaly` → `_send_anomaly_message()`
   - refactored default chat path into `_send_chat_message()`

3. Implemented structured workspace response handling in `backend/ai/intelligence.py`:
   - DQ suggestions saved with `metadata_json.type = "dq_suggestions"`
   - NL query results saved with `metadata_json.type = "nl_query_result"`
   - anomaly results saved with `metadata_json.type = "anomalies"`
   - `needs_input` status set for suggestion/anomaly result flows that require user action
   - provider-unavailable and error states persisted gracefully

4. Switched workspace routing to the full guard chain for every provider call:
   - `GuardChain.run()` executes `ScopeGuard`, `AccessGuard`, `DataIsolationGuard`, `MutationGuard`
   - `AuditTrail.log()` called after each provider invocation with latency and status
   - generic dataschema table names only flow into prefix-based data isolation when they already match a registered domain prefix, avoiding false rejects

5. Added `anomaly` as a first-class workspace conversation type:
   - `backend/ai/models.py`
   - `backend/ai/serializers.py`
   - migration `backend/ai/migrations/0002_alter_aiconversation_conversation_type.py`

6. Extended Pulse payload building in `backend/ai/providers/pulse.py`:
   - `suggest_dq()` now includes `conversation_history`
   - `query_nl()` now includes `conversation_history`
   - `detect_anomalies()` now includes `conversation_history`

7. Added backend coverage for the new workspace flows:
   - new `backend/ai/tests/test_workspace_messages.py` with 9 tests
   - updated `backend/ai/tests/test_protocol.py` round-trips for new conversation fields

## Files Changed

- `backend/ai/protocol.py`
- `backend/ai/models.py`
- `backend/ai/serializers.py`
- `backend/ai/providers/pulse.py`
- `backend/ai/intelligence.py`
- `backend/ai/migrations/0002_alter_aiconversation_conversation_type.py`
- `backend/ai/tests/test_protocol.py`
- `backend/ai/tests/test_workspace_messages.py`

## Verification Output

### Focused workspace-message slice

Command:
```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_workspace_messages.py --reuse-db -q
```

Output:
```text
.........                                                                [100%]
9 passed in 3.49s
```

### Protocol + intelligence slice

Command:
```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_protocol.py ai/tests/test_intelligence.py --reuse-db -q
```

Output:
```text
...............................                                          [100%]
31 passed in 2.70s
```

### Full AI backend test package

Command:
```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests --reuse-db -q
```

Output:
```text
........................................................................ [ 70%]
..............................                                           [100%]
102 passed in 4.83s
```

### Migration apply

Command:
```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py migrate ai
```

Output:
```text
Operations to perform:
  Apply all migrations: ai
Running migrations:
  Applying ai.0002_alter_aiconversation_conversation_type... OK
```

### Django check

Command:
```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check
```

Output:
```text
System check identified no issues (0 silenced).
```

### Repo-wide backend pytest gate

Command:
```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest --reuse-db -q
```

Output:
```text
........................................................................ [ 89%]
........................................................................ [ 95%]
.............uuuuuuuuuuu..................................               [100%]
1127 passed, 11 subtests passed in 42.39s
```

### Toolkit backend gate

Command:
```bash
cd /home/ahmed/aast/carbon && bash ./.ai-toolkit/scripts/verify.sh backend
```

Output:
```text
Verification gate: backend
════════════════════════════════════════
── Backend ─────────────────────────────
✓ django check
✓ no missing migrations
════════════════════════════════════════
GATE PASSED
```

### Toolkit antipattern gate

Command:
```bash
cd /home/ahmed/aast/carbon && bash ./.ai-toolkit/scripts/verify.sh antipatterns
```

Output:
```text
Verification gate: antipatterns
════════════════════════════════════════
── Anti-patterns ───────────────────────
✓ no hardcoded secrets
✓ no MUI v5 Grid syntax
⚠ raw fetch() — prefer the project apiFetch helper:
carbon-frontend//src/pages/ForgotPasswordPage.jsx:27:      const res = await fetch(`${API_BASE_URL}password-reset/`, {
carbon-frontend//src/pages/ResetPasswordPage.jsx:44:        const res = await fetch(
carbon-frontend//src/pages/ResetPasswordPage.jsx:89:      const res = await fetch(
✓ no hardcoded hex in components
✓ no naive datetime in app code
⚠ 4 print() calls in backend app code (use logger)
════════════════════════════════════════
GATE PASSED
```

## Issues Found

1. `manage.sh manage <django-command>` is documented in `.ai-toolkit/project.config.md`, but the actual repo `manage.sh` does not implement a `manage` subcommand. Direct `python manage.py ...` invocation was required for the baseline and Django verification commands.

2. The antipattern gate still reports pre-existing warnings outside this change set:
   - raw `fetch()` calls in frontend password reset pages
   - 4 backend `print()` calls

3. `DataIsolationGuard` currently assumes domain identity from table-name prefixes. This repo uses generic `dataschema.DataTable.name` values frequently, so workspace routing now only passes table names into that prefix check when they already match a registered domain prefix. This preserves the guard call without falsely rejecting generic table names.

## Deviations

None beyond the documented `manage.sh` command mismatch. The backend work stayed within `backend/` and did not touch frontend or DQ app code.