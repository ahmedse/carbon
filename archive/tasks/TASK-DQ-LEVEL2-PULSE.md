# TASK-DQ-LEVEL2-PULSE

**Task ID:** DQ-LEVEL2-PULSE  
**Status:** DONE (commits: 0da0da5)  
**Assigned to:** Worker (backend)  
**Depends on:** DQ-LEVEL1-VALIDATION (✅ complete), PULSE_CONTRACT_SPEC (✅ complete)  
**Estimated effort:** 4-6 hours  
**Created:** 2026-08-09  

---

## 0. Context — What Already Exists

### 0.1 Level 1 (✅ done)
- `backend/dataschema/validators.py`: `validate_row(values, fields)` — deterministic field-metadata validation (required, type, min/max, pattern, reference_set, select, date). 40 tests, all passing.
- Called from 3 places: `DataRowSerializer.validate()`, `BulkImportService`, `SchemaValidationService`.

### 0.2 Existing DQ infrastructure
- `backend/dq/models.py`: `DQRule` model with 7 `rule_type` choices: `not_null`, `unique`, `allowed_values`, `range`, `regex`, `reference_integrity`, `threshold`.
- `backend/dq/executor.py`: `DQRuleExecutor` class — 7 hardcoded validators. Used in tests.
- `backend/dq/services.py`: `_evaluate_rule()` function — 7 hardcoded validators. Used by `run_dq()` (production path).
- Both executor and `_evaluate_rule` share the same if/elif chain pattern. Both need `nl_check`.

### 0.3 Pulse contract (✅ spec written)
- `docs/PULSE_CONTRACT_SPEC.md` — authoritative. Task envelope: `POST /instances/carbon/tasks` with `{auth, task:{id,type,payload,meta}}`.
- Task type for DQ: `dq.validate` (sync, 10s timeout).
- Pulse returns: `{task_id, status, result: {results: [{rule_id, status, failing_rows, explanation, confidence}]}}`.

---

## 1. What To Build

### 1.1 `backend/pulse_gateway.py` — NEW FILE

A thin HTTP client. **Zero AI logic.** No SDK imports. No model config. Just HTTP.

```python
class PulseGateway:
    """
    Thin HTTP client for Pulse. No AI logic.
    Reads PULSE_URL and PULSE_API_KEY from Django settings.
    """
    def __init__(self): ...
    def validate_dq_rules(self, rules: list[dict], rows: list[dict], context: dict = None) -> dict:
        """Submit dq.validate task. Returns full response dict.
        Graceful degradation: on timeout/connection-error, returns
        {'status': 'pulse_unavailable', 'error': {...}}."""
```

#### Behavior:
- **Timeout**: 10s for sync calls (configured from agent card on first call).
- **Graceful degradation**: On `requests.Timeout` or `requests.ConnectionError`, return `{"status": "pulse_unavailable", "error": {"code": "timeout"|"unreachable"}}`. Never throw.
- **Idempotency**: Generate UUID v4 `task_id` per call. If Pulse is retried with same ID, Pulse honors it.
- **Agent Card**: On first call, `GET /instances/carbon/agent-card` and cache. Validate `dq.validate` exists before sending.
- **Error logging**: Log all Pulse errors with structured logging (use `dq.performance` logger or a dedicated `pulse` logger).
- **No Django ORM imports**: This file imports nothing from `dq.models` or `dataschema.models`. It's pure HTTP.

#### Settings to add in `backend/config/settings.py`:
```python
PULSE_URL = os.environ.get('PULSE_URL', 'http://127.0.0.1:9100/instances/carbon')
PULSE_API_KEY = os.environ.get('PULSE_API_KEY', '')
```

#### Payload construction (mapping DQRule → Pulse format):
```python
def _build_dq_validate_payload(rules, rows, context=None):
    """
    rules: list of DQRule objects (or dicts with id, params.prompt, severity)
    rows: list of dicts (row.values from DataRow)
    Returns: payload dict matching PULSE_CONTRACT_SPEC.md §3.1
    """
    return {
        "rules": [
            {
                "id": str(rule.id),
                "prompt": rule.params.get("prompt", ""),
                "fields": rule.params.get("fields", []),
                "severity": rule.severity
            }
            for rule in rules
        ],
        "rows": rows,
        "context": context or {}
    }
```

### 1.2 `backend/dq/models.py` — ADD `nl_check` to RULE_TYPES

Add to `RULE_TYPES`:
```python
('nl_check', 'NL Check'),
```

This is an additive change — zero impact on existing rules. No migration needed beyond `makemigrations` (the tuple list is only used for `choices=` display; the DB stores the string value).

### 1.3 `backend/dq/executor.py` — ADD `nl_check` branch

In `DQRuleExecutor._execute_field_rule()`, add after the `threshold` elif and before the `custom` elif:

```python
elif rule_type == 'nl_check':
    passed, failed_count, sample_failures = self._validate_nl_check(data_sample)
```

Add new method:
```python
def _validate_nl_check(self, data: list) -> tuple:
    """
    Send rule + rows to Pulse for NL validation.
    Graceful degradation: if Pulse is unavailable, log warning, return passed=True.
    """
    from pulse_gateway import PulseGateway
    
    prompt = self.rule.params.get('prompt', '')
    if not prompt:
        logger.warning(f"NL check rule {self.rule.id} has no prompt — skipping")
        return True, 0, []
    
    try:
        gateway = PulseGateway()
        response = gateway.validate_dq_rules(
            rules=[{
                'id': str(self.rule.id),
                'prompt': prompt,
                'fields': self.rule.params.get('fields', []),
                'severity': self.rule.severity,
            }],
            rows=data,
            context={'table_name': self.rule.data_table.name if self.rule.data_table else ''}
        )
    except Exception as e:
        logger.error(f"Pulse gateway error for rule {self.rule.id}: {e}")
        return True, 0, []  # graceful degradation — don't block on Pulse failure
    
    if response.get('status') == 'pulse_unavailable':
        logger.warning(f"Pulse unavailable for rule {self.rule.id} — skipping NL check")
        return True, 0, []
    
    # Parse Pulse response
    results = response.get('result', {}).get('results', [])
    if not results:
        return True, 0, []
    
    rule_result = results[0]  # Single rule sent → single result returned
    status = rule_result.get('status', 'error')
    if status == 'pass':
        return True, 0, []
    elif status == 'fail':
        failing_rows = rule_result.get('failing_rows', [])
        failures = [
            {'row': idx, 'reason': rule_result.get('explanation', 'NL check failed')}
            for idx in failing_rows[:10]
        ]
        return False, len(failing_rows), failures
    else:  # error
        logger.warning(f"Pulse NL check error for rule {self.rule.id}: {rule_result.get('explanation')}")
        return True, 0, []
```

### 1.4 `backend/dq/services.py` — ADD `nl_check` branch in `_evaluate_rule()`

In `_evaluate_rule()`, add after the `threshold` elif block:

```python
elif rule.rule_type == 'nl_check':
    return _evaluate_nl_check(rule, rows)
```

Add new function:
```python
def _evaluate_nl_check(rule, rows):
    """
    Send nl_check rule + rows to Pulse. Returns (passed, checked, failed, failures, score).
    Graceful degradation: if Pulse unavailable, treat as passed.
    """
    from pulse_gateway import PulseGateway
    
    prompt = rule.params.get('prompt', '')
    if not prompt:
        logger.warning(f"NL check rule {rule.id} has no prompt")
        return True, 0, 0, [], 100
    
    row_dicts = [r.values for r in rows]  # DataRow.values is a JSONField dict
    
    try:
        gateway = PulseGateway()
        response = gateway.validate_dq_rules(
            rules=[{
                'id': str(rule.id),
                'prompt': prompt,
                'fields': rule.params.get('fields', []),
                'severity': rule.severity,
            }],
            rows=row_dicts,
            context={
                'table_name': rule.data_table.name if rule.data_table else '',
                'row_count_hint': len(rows),
            }
        )
    except Exception as e:
        logger.error(f"Pulse gateway error for rule {rule.id}: {e}")
        return True, len(rows), 0, [], 100
    
    if response.get('status') == 'pulse_unavailable':
        logger.warning(f"Pulse unavailable for rule {rule.id}")
        return True, len(rows), 0, [], 100
    
    results = response.get('result', {}).get('results', [])
    if not results:
        return True, len(rows), 0, [], 100
    
    rule_result = results[0]
    status = rule_result.get('status', 'error')
    checked = len(rows)
    
    if status == 'pass':
        return True, checked, 0, [], 100
    elif status == 'fail':
        failing_rows = rule_result.get('failing_rows', [])
        failed = len(failing_rows)
        score = round((checked - failed) / checked * 100) if checked else 100
        failures = [
            {'row': idx, 'reason': rule_result.get('explanation', 'NL check failed')}
            for idx in failing_rows[:20]
        ]
        return False, checked, failed, failures, score
    else:
        return True, checked, 0, [], 100
```

### 1.5 `backend/dq/serializers.py` — UPDATE `DQRuleSerializer`

If `DQRuleSerializer` has a `rule_type` field with explicit `choices=RULE_TYPES`, it already picks up the new choice automatically. If it uses a hardcoded list, update it.

Also ensure `params` validation accepts `prompt` and `fields` for `nl_check` rules:
```python
# If params validation exists, add:
# For nl_check: params must include 'prompt' (str), optionally 'fields' (list[str])
```

---

## 2. Tests To Write

### 2.1 `backend/dq/tests/test_nl_check.py` — NEW FILE

| # | Test | What it verifies |
|---|------|-----------------|
| 1 | `test_nl_check_rule_type_exists` | `nl_check` in RULE_TYPES |
| 2 | `test_nl_check_requires_prompt` | Rule with no prompt → returns True (skipped) |
| 3 | `test_nl_check_pulse_unavailable` | Mock Pulse timeout → returns True (graceful degradation) |
| 4 | `test_nl_check_pulse_pass` | Mock Pulse returns `status: pass` → rule passes |
| 5 | `test_nl_check_pulse_fail` | Mock Pulse returns `status: fail` with failing_rows → rule fails, failures captured |
| 6 | `test_nl_check_pulse_error` | Mock Pulse returns `status: error` → treated as pass (graceful) |
| 7 | `test_nl_check_pulse_malformed` | Mock Pulse returns invalid JSON → treated as pass |
| 8 | `test_nl_check_pulse_partial` | Mock Pulse returns `status: partial` → successes used, failures logged |
| 9 | `test_nl_check_payload_construction` | Verify the payload sent to Pulse matches contract §3.1 |
| 10 | `test_nl_check_via_run_dq` | Integration: `run_dq()` with an nl_check rule → DQResult created |

All Pulse calls MUST be mocked using `unittest.mock.patch('pulse_gateway.requests.post')` — never make real HTTP calls.

### 2.2 `backend/pulse_gateway/tests/test_pulse_gateway.py` — NEW FILE (optional, if time)

| # | Test |
|---|------|
| 1 | Gateway constructs correct URL and auth headers |
| 2 | Gateway handles timeout gracefully |
| 3 | Gateway handles connection error gracefully |
| 4 | Gateway caches agent card on first call |

---

## 3. Files Changed (Summary)

| File | Action | Lines |
|------|--------|-------|
| `backend/pulse_gateway.py` | **CREATE** | ~120 |
| `backend/dq/models.py` | Add `('nl_check', 'NL Check')` to RULE_TYPES | 1 |
| `backend/dq/executor.py` | Add `nl_check` branch + `_validate_nl_check()` method | ~50 |
| `backend/dq/services.py` | Add `nl_check` branch + `_evaluate_nl_check()` function | ~55 |
| `backend/config/settings.py` | Add `PULSE_URL` and `PULSE_API_KEY` | 3 |
| `backend/dq/tests/test_nl_check.py` | **CREATE** — 10 tests | ~200 |

Total: ~430 lines of code, ~200 lines of tests.

---

## 4. Acceptance Gates

- [ ] **G1**: `nl_check` is a valid choice in `DQRule.rule_type`. Creating an `nl_check` rule with `params={"prompt": "..."}` succeeds.
- [ ] **G2**: `run_dq()` routes `nl_check` rules to Pulse via `pulse_gateway.validate_dq_rules()`.
- [ ] **G3**: When Pulse is unreachable, `nl_check` rules are treated as passed (graceful degradation). No exception propagates. Warning is logged.
- [ ] **G4**: When Pulse returns `status: fail`, the DQResult shows `passed=False` with correct `failed_count` and `sample_failures`.
- [ ] **G5**: All 10 tests in `test_nl_check.py` pass.
- [ ] **G6**: All existing DQ tests (in `test_dq.py`, `test_executor.py`) still pass — zero regressions.
- [ ] **G7**: `pulse_gateway.py` imports nothing from `dq.models`, `dataschema.models`, or any AI SDK.

---

## 5. Out of Scope (Not Now)

- Real Pulse endpoint integration (this is the Carbon-side contract implementation — Pulse side is separate)
- Streaming or async DQ execution (sync only for now)
- `dq.suggest` task type (Pulse suggesting DQ rules — Phase 3)
- `classification.infer` task type (Phase 3)
- Preview/test-run for NL rules in the UI (frontend work)
- Batch NL rule execution with batching optimization

---

## 6. Reference

- Pulse contract: `docs/PULSE_CONTRACT_SPEC.md` §3.1 (`dq.validate`)
- Level 1 validator: `backend/dataschema/validators.py` (already delegates from 3 callers)
- Existing DQ executor: `backend/dq/executor.py` (7 validators, add 8th)
- Existing DQ services: `backend/dq/services.py` (`_evaluate_rule` has 7 branches, add 8th)
- Project config: `.ai-toolkit/project.config.md` (`RULE_13`, `RULE_14`, `ARCH_PULSE_*`)
