# TASK-RESULT: Data Product Detail Remake — Backend

**Role**: `backend-worker`  
**Date**: 2026-08-11  
**Related Task**: `TASK-DATA-PRODUCT-DETAIL-REMAKE.md` Section 4 (Backend Changes Required)

---

## Summary

All 4 backend changes specified in Section 4 of the task are complete. Two new `@action` endpoints are available for the frontend to consume.

---

## 1. Changes Made

### 1.1 Module Model — Timestamp Fields
**File**: `backend/core/models.py`

Added `created_at` and `updated_at` fields to the `Module` model:
```python
created_at = models.DateTimeField(auto_now_add=True, null=True)
updated_at = models.DateTimeField(auto_now=True, null=True)
```

### 1.2 ModuleSerializer — Computed Fields
**File**: `backend/core/serializers.py`

Enhanced `ModuleSerializer` with:
- `table_count` — `SerializerMethodField` that returns `obj.data_tables.count()`
- `created_at`, `updated_at` — now included in `fields` and marked `read_only_fields`
- `table_count` added to `fields`

### 1.3 ModuleViewSet — quality_summary @action
**File**: `backend/core/views.py`

New endpoint: `GET /carbon-api/core/modules/{id}/quality_summary/`

Aggregates DQ stats for all tables in the module via `AssetProfile`:
```json
{
  "total": 12,
  "passing": 8,
  "warning": 2,
  "failing": 1,
  "unknown": 1,
  "avg_score": 78.5
}
```

Uses `AssetProfile.objects.filter(data_table__in=tables, data_field__isnull=True)` to get table-level profiles only.

### 1.4 ModuleViewSet — audit_trail @action
**File**: `backend/core/views.py`

New endpoint: `GET /carbon-api/core/modules/{id}/audit_trail/`

Returns `GovernanceEvent` records for both the module itself (`entity_type='module'`) and its child tables (`entity_type='datatable'`), ordered by timestamp descending, limited to 100 records.

Uses `GovernanceEventSerializer` for output — includes `username`, `action`, `entity_type`, `entity_id`, `before`, `after`, `timestamp`.

### 1.5 Migration
**File**: `backend/core/migrations/0012_add_module_timestamps.py`

Auto-generated migration for the two new timestamp fields. Applied successfully.

---

## 2. Imports Added

In `backend/core/views.py`:
```python
from catalog.models import AssetProfile, GovernanceEvent
from catalog.serializers import GovernanceEventSerializer
from django.db.models import Avg, Count, Q
```

---

## 3. Verification

| Gate | Result |
|------|--------|
| `verify.sh backend` | ✅ PASSED |
| `verify.sh antipatterns` | ✅ PASSED (preexisting warnings only) |
| Django system check | ✅ No issues |
| Migration applied | ✅ `core.0012_add_module_timestamps` — OK |
| RBAC preserved | ✅ ModuleViewSet.get_queryset() unchanged; `IsAuthenticated` for GET, `AdminOrSuperuserOnly` for mutations |

---

## 4. API Contract

### quality_summary
```
GET /carbon-api/core/modules/{id}/quality_summary/
Auth: IsAuthenticated
Response: 200
{
  "total": int,
  "passing": int,
  "warning": int,
  "failing": int,
  "unknown": int,
  "avg_score": float|null
}
```

### audit_trail
```
GET /carbon-api/core/modules/{id}/audit_trail/
Auth: IsAuthenticated
Response: 200
[
  {
    "id": int,
    "entity_type": "module"|"datatable",
    "entity_id": int,
    "action": "create"|"update"|"delete",
    "before": object|null,
    "after": object|null,
    "user": int|null,
    "username": string|null,
    "timestamp": datetime
  },
  ...
]
```

---

## 5. Frontend Integration Notes

- Module list (`GET /carbon-api/core/modules/`) now includes `created_at`, `updated_at`, and `table_count` in each object
- The `table_count` field can be used immediately in the metrics panel and table listing
- `created_at`/`updated_at` replace the need to compute from child tables
- The two new `@action` endpoints should be called from dedicated API functions (e.g., `fetchModuleQualitySummary(id)`, `fetchModuleAuditTrail(id)`)
