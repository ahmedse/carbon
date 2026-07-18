# TASK-RESULT-3.md — DT-1c (RUN 3: Data Quality / dq)

## Files created / changed
- backend/dq/__init__.py
- backend/dq/apps.py
- backend/dq/models.py
- backend/dq/permissions.py
- backend/dq/services.py
- backend/dq/serializers.py
- backend/dq/views.py
- backend/dq/urls.py
- backend/dq/admin.py
- backend/dq/README.md
- backend/dq/migrations/0001_initial.py
- backend/config/settings.py
- backend/config/urls.py

## Acceptance evidence
### SETUP ids
TABLE_ID 3 / AMOUNT_FIELD 3 / CODE_FIELD 4

### A no-regression
```text
modules 200
catalog-assets 200
mdm-sets 200
```

### B profiling
```json
{
    "table": 3,
    "rows": 3,
    "fields_profiled": 2,
    "completeness_pct": 83.33
}
```
```text
field profiles: [(4, 100.0, 2), (3, 66.67, 2)]
```

### C reference set
```text
RS=3
refval 201
```

### D rule creation
```text
not_null 201
unique 201
allowed_values 201
range 201
regex 201
```

### E dq run (5 results)
```json
{
    "table": 3,
    "rules_run": 5,
    "summary": [
        {
            "rule": 1,
            "type": "not_null",
            "passed": false,
            "failed": 1,
            "score": 67
        },
        {
            "rule": 2,
            "type": "unique",
            "passed": false,
            "failed": 2,
            "score": 33
        },
        {
            "rule": 3,
            "type": "allowed_values",
            "passed": false,
            "failed": 1,
            "score": 67
        },
        {
            "rule": 4,
            "type": "range",
            "passed": false,
            "failed": 1,
            "score": 50
        },
        {
            "rule": 5,
            "type": "regex",
            "passed": false,
            "failed": 1,
            "score": 67
        }
    ]
}
```

### F catalog roll-up
```text
amount asset quality_status: failing score: 50
```

### G RBAC guard
```text
nonadmin-read 200
nonadmin-run 403
```

### H swagger
```text
200
```

## Deviations from TASK.md
- none

## Blockers
- none

## Final status
- PASS
