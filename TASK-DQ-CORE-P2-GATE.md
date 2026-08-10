# TASK-DQ-CORE-P2-GATE

**Status:** NOT STARTED
**Phase:** 2 of 5 — DQ Core next-gen plan (`plans/CARBON_DQ_CORE_PLAN.md` §3-Phase-2)
**Depends on:** TASK-DQ-CORE-P1-RULE-CORE
**Executing agent:** read this file cold; everything needed is below.

## Goal

A standalone, stateless **gate** that enforces field-level DQ rules at write time and at import. This closes the audit's central flaw: today DQRules are never evaluated on write — only `DataField.validation` JSON is. After this phase there is **one rule world**.

## Design decisions (do NOT debate)

1. **Severity acts.** `error` → block (write rejected / import row rejected or quarantined); `warn` → store + flag; `info` → store + record. No advisory-only severities.
2. **Gate is pure.** `dq/gate.py` does zero DB writes; it reads rules and rows, returns verdicts. Persistence happens in callers.
3. **Only gate-eligible types** (`rule_schema.GATE_ELIGIBLE_TYPES`) with `enforcement.on_write=true` run in the gate. `nl_check` never runs synchronously.
4. Level-1 metadata validation (`dataschema/validators.py::validate_row`) stays as-is and runs **first**; the gate runs **after** it. Two layers, one write path.
5. No new dependencies.

## Deliverables

### 1. `backend/dq/gate.py` (new)

```python
def check_rows(table, rows: list[dict], *, mode: str = "write") -> dict:
    """Pure. Returns:
    {
      "summary": {"blocked": n, "warned": n, "passed": n},
      "row_verdicts": [{"row_index": i, "verdict": "pass|warn|block",
                        "failures": [{"rule_id", "rule_name", "field",
                                      "severity", "message"}]}]
    }"""
```

- Load active, non-archived rules bound to `table` where `type ∈ GATE_ELIGIBLE_TYPES` and `definition.enforcement.on_write == true`; evaluate each with `engine.evaluate()`.
- Row verdict = worst severity across failures (`block > warn > pass`).

### 2. Gate endpoint

- `POST /carbon-api/dq/gate/check/` — body `{data_table: <id>, rows: [...], mode: "write"|"import"}`; returns the `check_rows` dict. Stateless, no persistence. Permissions: existing scoped-access pattern used by other dq views (`accounts.permissions`). Register in `dq/urls.py`.

### 3. Write-path hook — `backend/dataschema/serializers.py`

- `DataRowSerializer.validate()`: after `validate_row()` passes, call `gate.check_rows(table, [values])`.
  - Any `block` → DRF `ValidationError` with per-field messages (HTTP 400, write rejected — same shape as Level-1 errors so the frontend maps them unchanged).
  - `warn` → allow the write; the view (`perform_create`/`perform_update`) persists the flag from item 4.

### 4. Row flag — `backend/dataschema/models.py`

- Add `DataRow.dq_flags` JSONField, default `list` — stores `[{"rule_id", "severity", "message", "at"}]` for warn-level gate failures. Migration. Exposed read-only in the row serializer.

### 5. Import integration — `dataschema/services.py::BulkImportService`

- Each row: Level-1 then gate. `enforcement.on_import` decides: `"block"` → row skipped into `errors[]` (current invalid-row behavior); `"flag"` → row stored with `dq_flags`; import summary gains `{"dq_blocked": n, "dq_flagged": n}`.

### 6. Frontend surfacing — `carbon-frontend/src/components/DataRowFormDrawer.jsx`

- Backend 400 field errors already map onto fields (verify `err.response.data` is actually populated by the api helper — if the helper throws plain `Error`, fix the helper or the drawer so server field errors render; this is a known-soft spot from the audit).
- `dq_flags` on an existing row render as a warning chip with tooltip listing rule names. Non-blocking.

## Explicit exclusions

- No jobs, no batch-run changes, no `nl_check`, no Pulse work.
- Do not make the gate call Pulse or any network service.
- Do not change `validate_row()` itself.

## Gates

1. Backend green: `cd backend && python -m pytest -q` (or `./manage.sh test` from repo root). Note: there is **no `verify.sh`** in this repo — `manage.sh test` wraps pytest.
2. `python -m pytest dq/ dataschema/ -q` — green; new tests ≥ 10: gate purity (mock out DB writes, assert none), severity→verdict mapping, write-path 400 on `error` rule, warn stored + `dq_flags` set, import `block` vs `flag` modes, endpoint auth scoping.
3. Migration count: exactly one (`DataRow.dq_flags`).
4. Manual smoke (documented in commit message): create rule `{type: range, params: {min: 0}, severity: error, enforcement: {on_write: true}}` on a table → `POST` row with negative value → 400 with field error; same rule with `severity: warn` → 201 + `dq_flags` populated.
5. `cd carbon-frontend && npm run build && npm run lint` — clean.

## Done criteria

A field-level DQ rule with `on_write: true` genuinely blocks/flags bad data at entry and import — the A/B split from the audit is closed. The `/dq/gate/check/` endpoint is usable standalone by external producers later.
