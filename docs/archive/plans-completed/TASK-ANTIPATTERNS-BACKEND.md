# TASK-ANTIPATTERNS-BACKEND — Fix Pre-existing Backend Antipatterns

## Summary
Fix the **real** pre-existing backend antipatterns flagged by `verify.sh antipatterns`. Focus on the 2 categories that are actual bugs/code-smells: naive datetimes and startup debug `print()` calls.

## What is IN scope

| # | File | Issue | Fix |
|---|------|-------|-----|
| 1 | `backend/evidence/models.py:14` | `datetime.now()` — naive datetime, ignores Django timezone | `timezone.now()` |
| 2 | `backend/dq/executor.py:275` | `datetime.now().isoformat()` — naive datetime | `timezone.now().isoformat()` |
| 3 | `backend/emissions/services.py:1100` | `datetime.now().isoformat()` — naive datetime | `timezone.now().isoformat()` |
| 4 | `backend/config/settings.py:41-46` | 3 `print()` calls — startup noise (1 commented) | Replace with `logger.debug()` or remove |

## What is OUT of scope (explain why)

| File | Print count | Why excluded |
|------|------------|--------------|
| `backend/deploy_aastmt_carbon.py` | ~18 | Standalone deployment CLI script — `print()` is correct for user-facing output |
| `backend/seed_2026_data.py` | ~10 | Standalone seed script — `print()` is correct |
| `backend/seed_aastmt_data.py` | ~25 | Standalone seed script — `print()` is correct |
| `backend/seed_historical_data.py` | ~10 | Standalone seed script — `print()` is correct |
| `backend/test_governance_rbac.py` | ~9 | Standalone test script — `print()` is correct |
| `backend/test_swagger_direct.py` | ~8 | Standalone test script — `print()` is correct |
| All `carbon-frontend/` files | N/A | Frontend antipatterns belong to a **separate frontend worker task** |

## DO-NOT-TOUCH

- ❌ No model changes (no migrations)
- ❌ No URL/route changes
- ❌ No settings changes beyond the 3 print lines
- ❌ Frontend files (`carbon-frontend/`)
- ❌ Seed scripts, deploy script, test scripts
- ❌ `backend/emissions/services.py` — only fix the `datetime` import+usage in `ReportConfigService.generate_from_config()`; touch **nothing else** in this large file

---

## Detailed Fix Instructions

### Fix 1 — `backend/evidence/models.py`

**Current (lines 1-15):**
```python
# File: backend/evidence/models.py
import os
from django.db import models
from django.contrib.auth import get_user_model
from dataschema.models import DataRow


User = get_user_model()


def evidence_upload_path(instance, filename):
    """Upload evidence files to media/evidence/YYYY/MM/DD/ directory."""
    from datetime import datetime
    today = datetime.now()
    return f'evidence/{today.year}/{today.month:02d}/{today.day:02d}/{filename}'
```

**Change:**
1. Remove the local `from datetime import datetime` inside `evidence_upload_path()`
2. Add `from django.utils import timezone` at the top with other Django imports
3. Replace `datetime.now()` with `timezone.now()`

---

### Fix 2 — `backend/dq/executor.py`

**Current (line 3):**
```python
from datetime import datetime
```

**Current (line 275):**
```python
'timestamp': datetime.now().isoformat()
```

**Change:**
1. Replace `from datetime import datetime` → `from django.utils import timezone`
2. Replace `datetime.now().isoformat()` → `timezone.now().isoformat()`

Note: `timezone.now()` returns a `datetime` object with timezone-aware UTC. Calling `.isoformat()` on it works identically.

---

### Fix 3 — `backend/emissions/services.py`

**Current (line 1016, inside `ReportConfigService.generate_from_config()`):**
```python
from datetime import datetime
```

**Current (line 1100):**
```python
'generated_at': datetime.now().isoformat(),
```

**Change:**
1. Replace `from datetime import datetime` → `from django.utils import timezone`
2. Replace `datetime.now().isoformat()` → `timezone.now().isoformat()`

⚠️ This is the ONLY change in `services.py`. Do not touch any other code in this ~1100-line file.

---

### Fix 4 — `backend/config/settings.py`

**Current (lines 38-46):**
```python
).split(",")
#FORCE_SCRIPT_NAME = get_env('FORCE_SCRIPT_NAME', None)
#print("FORCE_SCRIPT_NAME =", FORCE_SCRIPT_NAME)

CSRF_TRUSTED_ORIGINS = [x.strip() for x in get_env("CSRF_TRUSTED_ORIGINS", "").split(",") if x.strip()]

print("CSRF_TRUSTED_ORIGINS =", repr(CSRF_TRUSTED_ORIGINS))

print("DEBUG =", repr(DEBUG))
```

**Change:**
1. Add `import logging` at the top of settings.py if not present; add `logger = logging.getLogger(__name__)` after imports
2. Remove the commented `#print("FORCE_SCRIPT_NAME =", FORCE_SCRIPT_NAME)` line (and the commented `#FORCE_SCRIPT_NAME =...` line too — dead code)
3. Replace `print("CSRF_TRUSTED_ORIGINS =", repr(CSRF_TRUSTED_ORIGINS))` → `logger.debug("CSRF_TRUSTED_ORIGINS = %s", repr(CSRF_TRUSTED_ORIGINS))`
4. Replace `print("DEBUG =", repr(DEBUG))` → `logger.debug("DEBUG = %s", repr(DEBUG))`

---

## Verification Checklist

After making all changes, verify:

```bash
# 1. Django system checks
cd backend && python manage.py check

# 2. No unexpected migrations
python manage.py makemigrations --check

# 3. AI Toolkit backend gate
cd .. && bash .ai-toolkit/scripts/verify.sh backend

# 4. Antipatterns gate — should show FEWER violations:
#    - 0 naive datetime violations (was 3)
#    - 3 fewer print() violations (was 145, now ~142)
#    - MUI/rawFetch/hexColor violations unchanged (frontend, out of scope)
bash .ai-toolkit/scripts/verify.sh antipatterns

# 5. All tests still pass
cd backend && python -m pytest emissions/tests/ -v
```

## Success Criteria

- [ ] `python manage.py check` — exit 0
- [ ] `makemigrations --check` — "No changes detected"
- [ ] `verify.sh backend` — GATE PASSED
- [ ] `verify.sh antipatterns` — 0 "naive datetime" violations remaining
- [ ] `verify.sh antipatterns` — 3 fewer "print()" violations
- [ ] All 50 emissions tests pass
- [ ] No files outside the 4 listed files were changed
