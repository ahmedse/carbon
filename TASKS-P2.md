# TASKS-P2.md — Phase 2: Service Layer Extraction
# Master Architect → Backend Worker | Date: 2026-07-31
# Role: Backend Worker | Model: DeepSeek | Budget: ~40K tokens

---

## Architecture Context (READ FIRST)

```
DATA TRUST PLATFORM (foundation — NEVER imports from emissions/)
  accounts/      RBAC, auth, scoped roles
  catalog/       Data domains, glossary, tags, assets, governance
  dataschema/    Metadata-driven schema engine
  mdm/           Reference data, org units
  dq/            Data quality
  connections/   Data sources
  evidence/      File uploads
  importexport/  Import/export jobs
  core/          Modules, feedback

CARBON DOMAIN APP (tenant — sits ON TOP)
  emissions/     GHG calculations, factors, targets, reports
```

## What This Phase Does

Extract business logic from views into `services.py` for 6 apps that violate
Hard Rule #3 ("Views are THIN — business logic in services.py").

**Pattern:** Facade — each app gets ONE public service class that views call.

---

## PRE-FLIGHT CHECK (do this first)

```bash
cd /home/ahmed/aast/carbon
# Confirm baseline
./manage.sh manage check --deploy 2>&1 | tail -5
# Run existing tests
./manage.sh test accounts mdm dataschema --keepdb 2>&1 | tail -5
```

---

## G1 — accounts/services.py

**Current state:** `accounts/views.py` (529 lines) contains 3 helper functions
that are adapter/service logic, not view logic. Also `accounts/pulse_auth.py`
has standalone view functions that should be service-backed.

**What to CREATE:**
- `backend/accounts/services.py`

**What to MOVE (from `accounts/views.py` → `services.py`):**
1. `_normalize_group_name(group_name)` → `RoleResolutionService.normalize_group_name()`
2. `_perspective_from_group_name(group_name)` → `RoleResolutionService.perspective_from_group_name()`
3. `_load_app_manifests()` → `AppManifestService.load_manifests()`

**What to MOVE (from `accounts/pulse_auth.py` → `services.py`):**
4. `generate_pulse_token(user)` → `PulseService.generate_token(user)`
5. Re-wrap `pulse_auth_view` and `pulse_provision_view` to call `PulseService`

**What to EDIT (views.py):**
- Import from services, call the service method, return result
- Remove the original `_normalize_group_name`, `_perspective_from_group_name`, `_load_app_manifests` function definitions
- Keep all DRF view classes and `@action` decorators untouched

**What to EDIT (pulse_auth.py):**
- Import `PulseService` from services
- Keep the view functions but delegate logic to service

**Rules:**
- Services file: NO DRF imports (no `rest_framework`, no `Response`, no `status`)
- Views file: NO business logic (no loops, no transformations, no dict-building beyond parameter extraction)
- Every moved function MUST keep the exact same behavior — ZERO behavioral changes
- DO NOT TOUCH: `models.py`, `permissions.py`, `rbac_utils.py`, `serializers.py`, `admin.py`, `urls.py`

**Verification:**
```bash
./manage.sh manage check --deploy 2>&1 | grep -i error || echo "No errors"
./manage.sh shell -c "from accounts.services import RoleResolutionService, AppManifestService, PulseService; print('3 services loaded')"
./manage.sh shell -c "from accounts.views import my_roles; print('views import OK')"
./manage.sh test accounts --keepdb 2>&1 | tail -5
```

---

## G2 — dataschema/services.py

**Current state:** `dataschema/views.py` (638 lines). Bulk import at line ~415,
template download at ~526, plus validation logic in views.

**What to CREATE:**
- `backend/dataschema/services.py`

**What to EXTRACT (from `dataschema/views.py`):**
1. `BulkImportService` class:
   - Method: `import_rows(data_table, file_data)` — bulk import logic from `DataTableViewSet.bulk_import`
   - Method: `generate_template(data_table)` — template generation from `DataTableViewSet.download_template`
2. `SchemaValidationService` class:
   - Method: `validate_field(field, value)` — field validation logic
   - Any validation helper functions currently in views

**What to EDIT (views.py):**
- `DataTableViewSet.bulk_import` → call `BulkImportService.import_rows()`
- `DataTableViewSet.download_template` → call `BulkImportService.generate_template()`
- Views become thin: parse request → call service → return Response

**Rules:**
- Services do NOT return DRF Response objects — they return data (dict, list, bytes)
- Views wrap service results in Response
- DO NOT TOUCH: `models.py`, `serializers.py`, `urls.py`

**Verification:**
```bash
./manage.sh shell -c "from dataschema.services import BulkImportService, SchemaValidationService; print('2 services loaded')"
./manage.sh test dataschema --keepdb 2>&1 | tail -5
```

---

## G3 — mdm/services.py

**Current state:** `mdm/views.py` (654 lines). Reference set CRUD with
transitions, org unit tree/ancestors, bulk operations.

**What to CREATE:**
- `backend/mdm/services.py`

**What to EXTRACT (from `mdm/views.py`):**
1. `ReferenceSetService` class:
   - Method: `transition_set(ref_set, new_status)` — status transition logic from `ReferenceSetViewSet.transition`
   - Method: `add_value(ref_set, value_data)` — from `ReferenceSetViewSet.add_value`
   - Method: `archive_bulk(ids)` — from `ReferenceSetViewSet.archive_bulk`
   - Method: `bulk_create(data)` — from `ReferenceSetViewSet.bulk_create`
2. `OrgUnitService` class:
   - Method: `get_tree(org_unit=None)` — tree structure from `OrgUnitViewSet.tree`
   - Method: `get_ancestors(org_unit)` — from `OrgUnitViewSet.ancestors`

**What to EDIT (views.py):**
- Each `@action` method becomes thin: parse → call service → return Response

**Rules:**
- Services do NOT call `self.get_object()` — views pass the resolved object
- DO NOT TOUCH: `models.py` (especially `OrgUnit.get_descendant_ids` — that's model logic, stays)
- DO NOT TOUCH: `serializers.py`, `urls.py`

**Verification:**
```bash
./manage.sh shell -c "from mdm.services import ReferenceSetService, OrgUnitService; print('2 services loaded')"
./manage.sh test mdm --keepdb 2>&1 | tail -5
```

---

## G4 — evidence + importexport + connections services

**Current state:** evidence (137 views), importexport (116 views), connections (81 views).
Smaller apps — each gets a lightweight service class.

### G4a — evidence/services.py
**What to CREATE:** `backend/evidence/services.py`
**Class:** `EvidenceService`
- Method: `store_evidence(file, metadata)` — from view upload logic
- Method: `bulk_store(files, metadata)` — from bulk_upload logic
**Verification:**
```bash
./manage.sh shell -c "from evidence.services import EvidenceService; print('1 service loaded')"
```

### G4b — importexport/services.py
**What to CREATE:** `backend/importexport/services.py`
**Classes:**
- `ImportService` — `run_import(job)` from `ImportJobViewSet.run`
- `ExportService` — `run_export(job)` from `ExportJobViewSet.run` + `get_download(job)` from download
**Verification:**
```bash
./manage.sh shell -c "from importexport.services import ImportService, ExportService; print('2 services loaded')"
```

### G4c — connections/services.py
**What to CREATE:** `backend/connections/services.py`
**Class:** `ConnectionService`
- Method: `test_connection(source)` — from `DataSourceViewSet.test`
- Method: `rotate_key(source)` — from `DataSourceViewSet.rotate_key`
**Verification:**
```bash
./manage.sh shell -c "from connections.services import ConnectionService; print('1 service loaded')"
```

---

## FINAL VERIFICATION GATE

```bash
cd /home/ahmed/aast/carbon

# 1. Django system check
./manage.sh manage check --deploy 2>&1 | grep -i "error\|warning" | grep -v "urls.W005\|security.W" || echo "Only known warnings"

# 2. All services importable
./manage.sh shell -c "
from accounts.services import RoleResolutionService, AppManifestService, PulseService
from dataschema.services import BulkImportService, SchemaValidationService
from mdm.services import ReferenceSetService, OrgUnitService
from evidence.services import EvidenceService
from importexport.services import ImportService, ExportService
from connections.services import ConnectionService
print('ALL 10 services loaded successfully')
"

# 3. Existing tests still pass
./manage.sh test accounts mdm dataschema --keepdb 2>&1 | tail -5

# 4. Backend verify.sh
./.ai-toolkit/scripts/verify.sh backend 2>&1 | tail -10

# 5. Frontend still builds (no backend API changes, but verify anyway)
cd carbon-frontend && npm run build 2>&1 | tail -3

# 6. git diff summary
cd /home/ahmed/aast/carbon && git diff --stat
```

## DELIVERABLE

Create `TASKS-RESULT-P2.md` containing:
1. Each G1-G4: before/after line counts (views.py lines before → after, services.py lines created)
2. Full verification output (copy-paste terminal)
3. Any test failures or deviations
4. Confirmation: "NO logic changed — only moved from views to services"
