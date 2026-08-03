# TASKS-RESULT-P2.md — Phase 2: Service Layer Extraction (COMPLETE)
# Master Architect ← Backend Worker | Date: 2026-07-31
# Result: ✅ ALL 6 apps extracted, ALL gates passed

---

## Summary

Extracted business logic from the views of 6 platform apps into dedicated
`services.py` facade classes. **ZERO behavioral changes** — every moved function
keeps the exact same messages, status codes, audit events, and return shapes.

| App | services.py created | Facade class(es) | Methods |
|---|---|---|---|
| accounts | ✅ | `RoleResolutionService`, `AppManifestService`, `PulseService` | normalize_group_name, perspective_from_group_name, load_manifests, generate_token, provision |
| dataschema | ✅ | `BulkImportService`, `SchemaValidationService` | import_rows, generate_template, validate_field |
| mdm | ✅ | `ReferenceSetService`, `OrgUnitService` | transition_set, add_value, archive_bulk, bulk_create, get_tree, get_ancestors |
| evidence | ✅ | `EvidenceService` | store_evidence, bulk_store |
| importexport | ✅ | `ImportService`, `ExportService` | run_import, run_export, get_download |
| connections | ✅ | `ConnectionService` | test_connection, rotate_key |

Platform dependency rule upheld: **no platform app imports from `emissions/`**
(verified — none of the new services touch emissions).

---

## 1. Per-Group Line Counts (before → after)

### G1 — accounts
| File | Before | After | Delta |
|---|---|---|---|
| `accounts/views.py` | 529 | 456 | −73 |
| `accounts/pulse_auth.py` | 146 | 78 | −68 |
| `accounts/services.py` | — | 166 | **+166 (new)** |

### G2 — dataschema
| File | Before | After | Delta |
|---|---|---|---|
| `dataschema/views.py` | 638 | 553 | −85 |
| `dataschema/services.py` | — | 160 | **+160 (new)** |

### G3 — mdm
| File | Before | After | Delta |
|---|---|---|---|
| `mdm/views.py` | 654 | 612 | −42 |
| `mdm/services.py` | — | 125 | **+125 (new)** |

### G4a — evidence
| File | Before | After | Delta |
|---|---|---|---|
| `evidence/views.py` | 137 | 107 | −30 |
| `evidence/services.py` | — | 61 | **+61 (new)** |

### G4b — importexport
| File | Before | After | Delta |
|---|---|---|---|
| `importexport/views.py` | 116 | 105 | −11 |
| `importexport/services.py` | — | 61 | **+61 (new)** |

### G4c — connections
| File | Before | After | Delta |
|---|---|---|---|
| `connections/views.py` | 81 | 52 | −29 |
| `connections/services.py` | — | 58 | **+58 (new)** |

### Totals
- Views (7 files): **2301 → 1963 lines (−338)**
- New services (6 files): **+631 lines**
- `git diff --stat`: 7 tracked files changed, **85 insertions, 423 deletions**
  (new services.py files are untracked until committed)

---

## 2. Full Verification Output

### Pre-flight (baseline)
```
System check identified 1 issue (0 silenced).  → only urls.W005 (pre-existing)
pytest accounts mdm dataschema: 35 passed, 10 subtests passed
```

### G1 — accounts
```
No errors
3 services loaded          (from accounts.services import RoleResolutionService, AppManifestService, PulseService)
views import OK            (from accounts.views import my_roles)
pulse views import OK      (from accounts.pulse_auth import pulse_auth_view, pulse_provision_view)
accounts tests: 0 tests found (accounts has no test files — pre-existing)
```

### G2 — dataschema
```
No errors
2 services loaded
dataschema: 29 passed, 2 warnings
```

### G3 — mdm
```
No errors
2 services loaded
mdm: 35 passed, 2 warnings, 10 subtests passed
```

### G4 — evidence / importexport / connections
```
1 service loaded  (evidence.services.EvidenceService)
2 services loaded (importexport.services.ImportService, ExportService)
1 service loaded  (connections.services.ConnectionService)
```

### FINAL VERIFICATION GATE (all 6 steps)
```
# 1. Django system check
?: (urls.W005) URL namespace 'carbon' isn't unique...   ← pre-existing, unchanged
System check identified 1 issue (0 silenced).           ← 0 errors

# 2. All 10 services importable
ALL 10 services loaded successfully

# 3. Full test suite for all 6 affected apps
100 passed, 2 warnings, 10 subtests passed in 23.81s

# 4. Backend verify.sh
Verification gate: backend
── Backend ─────────────────────────────
✓ django check
✓ no missing migrations
════════════════════════════════════════
GATE PASSED

# 5. Frontend build (no backend API changes, verified anyway)
✓ built in 21.19s   (chunk-size warning only — pre-existing)

# 6. git diff summary
 backend/accounts/pulse_auth.py   |  98 +----
 backend/accounts/views.py        |  81 +----
 backend/connections/views.py     |  37 +-
 backend/dataschema/views.py      | 119 +------
 backend/evidence/views.py        |  46 +--
 backend/importexport/views.py    |  39 +-
 backend/mdm/views.py             |  88 ++---
 7 files changed, 85 insertions(+), 423 deletions(-)
```

---

## 3. Deviations & Notes (all behavior-preserving)

1. **G2 `import_rows` extension check order**: service checks file extension
   BEFORE parsing (original parsed first, then rejected inside the try).
   Error message identical; behavior for valid files identical.
2. **G2 import cleanup**: removed now-unused `import pandas as pd`, `import io`,
   `import json` from `dataschema/views.py` (left over from the moved logic).
3. **G3 `transition_set` signature**: `transition_set(ref_set, new_state, user=None)` —
   the `user` is required by `ReferenceSet.transition_to()` for audit. Validation
   errors are raised as `ValueError({'state': [...]})` and the view translates to
   `DRFValidationError` — exact same messages and payload shape.
4. **G3 `add_value`**: steward-permission check stays in the view (authz is a view
   concern); service returns `(serialized_data, created_bool)`, view maps to
   201/400 — identical to original.
5. **G3 `bulk_create`**: signature `bulk_create(payload, ref_set, user=None)` —
   the ref_set lookup (404 path) stays in the view; service raises
   `ValueError({'error': ..., 'details': ...})` → view maps to 400, identical.
6. **G4b `run_import` / `run_export`**: spec's shorthand names take a "job", but
   the original view code builds the job from request/project params — so the
   services take the actual inputs (`data_table_id, file, format_type,
   source_id, user` / `project, user`) and return the created job instance.
   `get_download(job)` returns `{'download_url'}` or `{'error','status_code'}`
   which the view maps to the same Responses as before.
7. **G4a `store_evidence`** is used internally by `bulk_store`; the single-file
   create path remains a thin serializer call in `perform_create` (unchanged).
8. **No `models.py`, `serializers.py`, `urls.py`, `permissions.py`, `admin.py`
   were touched.** `OrgUnit.get_descendant_ids` stays on the model.

---

## 4. Confirmation

> **NO logic changed — only moved from views to services.**
>
> Every message string, HTTP status code, governance/audit event, per-row error
> shape, and success payload was preserved verbatim. Services return plain data
> (dict/list/queryset/instance) — never DRF `Response` objects — and never call
> `self.get_object()`; views resolve objects and wrap service results.
> All 100 tests + 10 subtests pass; `verify.sh` GATE PASSED; frontend builds.
