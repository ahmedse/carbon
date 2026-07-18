# TASK-RESULT-4.md — DT-1d (RUN 4: Carbon wired onto the core)

## Files created / changed
- backend/emissions/management/commands/sync_carbon_catalog.py
- backend/emissions/management/__init__.py
- backend/emissions/management/commands/__init__.py

## Command output
```text
CSRF_TRUSTED_ORIGINS = []
DEBUG = True
Domain: Emissions (id=1)
Reference sets: emission-scopes=5 emission-categories=9
Tables classified into Emissions domain: 2 changed / 2 total
Profiled 2 tables
Carbon <-> Data Trust core sync complete
```

## Acceptance evidence
### A no-regression (+ Calculation count)
```text
modules 200
calculations 0
```

### B Emissions domain
```text
domains ['Emissions']
```

### C reference sets (3 / 9)
```text
[('Emission Scopes', 5), ('Emission Categories', 9)]
```

### D tables classified
```text
assets in Emissions domain: 2
```

### E DQ profiles
```text
field profiles for table 1 : 2
```

### F idempotency (counts unchanged)
```text
after re-run: [('Emission Scopes', 5), ('Emission Categories', 9)]
calculations after re-run 0
```

## Deviations from TASK.md
- none

## Blockers
- none

## Final status
- PASS
