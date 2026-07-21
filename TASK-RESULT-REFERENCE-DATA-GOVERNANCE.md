# TASK RESULT: Reference Data Governance (Track D)

## Summary
Implemented the backend completion for Reference Data Governance (Track D) in the Data Trust Core. This adds temporal validity query support, reference set lifecycle management, and bulk field binding management with safety checks for the Carbon platform backend.

### What was implemented
- Added `lifecycle_state` to `ReferenceSet` with states: `draft`, `active`, `deprecated`, `archived`.
- Added lifecycle transition validation and audited state changes through `ReferenceSet.transition_to()`.
- Implemented temporal query support for reference values via `GET /mdm/reference-sets/{id}/values/?date=YYYY-MM-DD` with null-safe valid_from/valid_to logic.
- Added `ReferenceSet.get_current_values(as_of=None)` helper for current valid values.
- Updated DQ reference integrity validation to use temporal validity when evaluating `ReferenceSet` codes.
- Extended `BindFieldView` to support bulk field bind/unbind operations and reject unsafe unbinds unless `force=true`.
- Added a Django migration to introduce `lifecycle_state` on existing `ReferenceSet` records.

## Files modified
- backend/mdm/models.py — 195 lines
- backend/mdm/views.py — 479 lines
- backend/mdm/serializers.py — 143 lines
- backend/mdm/migrations/0004_reference_set_lifecycle.py — 23 lines
- backend/mdm/tests/test_reference_governance.py — 105 lines
- backend/dq/services.py — 349 lines
- backend/dq/tests/test_executor.py — 476 lines

## API endpoints
### Temporal reference values query
- `GET /carbon-api/mdm/reference-sets/{id}/values/?date=2025-01-15&active=true`
- Returns values valid on the requested date.
- Includes values with `valid_from` null or <= date and `valid_to` null or >= date.

Example request:
```http
GET /carbon-api/mdm/reference-sets/5/values/?date=2025-01-15&active=true
```
Example response:
```json
[
  {
    "id": 12,
    "reference_set": 5,
    "code": "SCOPE1",
    "label": "Direct Emissions",
    "description": "",
    "is_active": true,
    "sort_order": 0,
    "valid_from": "2024-01-01",
    "valid_to": null,
    "metadata": {},
    "created_at": "2026-07-21T00:00:00Z",
    "updated_at": "2026-07-21T00:00:00Z"
  }
]
```

### Reference set lifecycle transition
- `POST /carbon-api/mdm/reference-sets/{id}/transition/`
- Body: `{"state": "active"}`
- Valid transitions: `draft -> active`, `active -> deprecated`, `deprecated -> active`, `deprecated -> archived`.
- `archived` also sets `is_active=false`.

Example request:
```http
POST /carbon-api/mdm/reference-sets/5/transition/
Content-Type: application/json

{"state": "active"}
```
Example response:
```json
{
  "id": 5,
  "name": "Emission Scopes",
  "lifecycle_state": "active",
  "message": "Transitioned to active"
}
```

### Bulk field bind/unbind with safety
- `POST /carbon-api/mdm/bind-field/`
- Body examples:
  - Bind a single field: `{"data_field": 1, "reference_set": 5}`
  - Bulk bind: `{"data_fields": [1,2], "reference_set": 5}`
  - Unbind with safety: `{"data_field": 1, "reference_set": null}`
  - Force unbind
    `{"data_fields": [1,2], "reference_set": null, "force": true}`
- If field rows exist and `force=true` is not supplied, the unbind is rejected.

Example response (bind):
```json
{"updated": [{"data_field": 1, "reference_set": 5}]}
```

## Test results
### Backend test output
Verified with:
```bash
cd /home/ahmed/aast/carbon/backend && python3 manage.py test mdm.tests.test_reference_governance dq.tests.test_executor --verbosity=2
```

Result:
- `48 tests run`
- `0 failures`
- `0 errors`

### Coverage notes
- New DQ and MDM tests cover temporal validity, lifecycle transitions, and binding safety.
- `reference_integrity` now validates against `ReferenceSet.get_current_values()`.

## Manual testing evidence
- Verified `GET /carbon-api/mdm/reference-sets/{id}/values/?date=2025-06-15` returns only values valid on that date.
- Verified `POST /carbon-api/mdm/reference-sets/{id}/transition/` accepts valid lifecycle transitions and rejects invalid ones.
- Verified `POST /carbon-api/mdm/bind-field/` rejects unsafe unbind without `force=true` and succeeds when `force=true`.
- Verified `get_current_values()` returns today’s valid active values.

## Known issues
- The backend API prefix is `carbon-api`, so clients must use that prefix rather than `/api/v1/`.
- The lifecycle action is backend-only; no frontend UI was added in this task.

## Master prompt back to Ahmed
Ahmed, the Reference Data Governance backend is now complete for Track D. Temporal value time-travel, lifecycle state transitions, and safe field binding are all implemented and tested. The next step is to wire these endpoints into the governance UI and any downstream data-entry validation flows if you want the platform to enforce them in production.
