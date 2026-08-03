# TASK-RESULTS-E2-B5 — importexport execution

**Date:** 2026-08-03
**Role:** backend-worker
**Status:** COMPLETE

---

## Summary

Fleshed out `ImportService.run_import()` and `ExportService.run_export()` with actual synchronous file parsing and data writing. Added download endpoints for both import and export jobs. Hid unimplemented schedule field from ExportProject serializer.

---

## Changes

### 1. `importexport/services.py` — actual execution

- **`ImportService.run_import`**: After creating a pending ImportJob, now executes synchronously:
  1. Sets status → `running`, sets `started_at`
  2. Reads the uploaded file from the saved FieldFile
  3. Delegates to `BulkImportService.import_rows()` from `dataschema/services.py`
  4. On success: status → `done`, sets `row_count`, `error_count`, `log`
  5. On failure: status → `failed`, captures exception into `log`, sets `finished_at`
  - **ADR**: Synchronous execution (no Celery). For files >10k rows, migrate to async task queue.

- **`ExportService.run_export`**: After creating a pending ExportJob, now executes synchronously:
  1. Sets status → `running`, sets `started_at`
  2. Queries `DataRow` objects for the target `DataTable`, applies `ExportProject.filters` as JSON-field lookups
  3. Generates CSV using `csv.DictWriter` with headers from active table fields
  4. Saves to `media/exports/{slug}_{timestamp}.csv` via Django `FileField.save()`
  5. Status → `ready`, sets `row_count`, `file` path
  6. On failure: status → `failed`, sets `finished_at`

### 2. `importexport/views.py` — download endpoints

- **`ImportJobViewSet.download`**: New `@action(detail=True, methods=['get'])` — serves the uploaded import file via `FileResponse` with `as_attachment=True`.
- **`ExportJobViewSet.download`**: Improved — now serves the exported CSV directly via `FileResponse` (was returning a JSON with download_url only; the serializer still provides `download_url` for UI convenience).

### 3. `importexport/serializers.py` — hide schedule

- Removed `schedule` from `ExportProjectSerializer.Meta.fields`.
- **ADR**: Scheduled exports not implemented. Schedule field hidden from serializer to avoid advertising unavailable functionality.

### 4. Tests — `importexport/tests/test_import_export.py`

6 new tests:
| # | Test | What it verifies |
|---|------|-----------------|
| 1 | `test_csv_import_creates_rows_and_status_done` | CSV import → 2 DataRows, status=done, row_count=2 |
| 2 | `test_import_bad_file_status_failed` | Bad Excel file → status=failed, error_count>0 |
| 3 | `test_export_generates_csv_and_download_serves_it` | Export → ready status, download returns CSV with correct content |
| 4 | `test_export_with_filters_returns_correct_rows` | Export with `filters={'item':'Alpha'}` → only matching rows |
| 5 | `test_import_job_download_endpoint` | Import job download serves original file |
| 6 | `test_round_trip_import_export_compare` | Import 3 rows → export → download → same 3 rows |

---

## Gates

| Gate | Result |
|------|--------|
| `pytest --reuse-db -q` | **389 passed**, 15 pre-existing failures, 0 regressions |
| `verify.sh backend` | **PASS** |
| `python manage.py check` | **0 issues** |

---

## Files Changed

| File | Change |
|------|--------|
| `backend/importexport/services.py` | Fleshed out `run_import` and `run_export` with actual execution |
| `backend/importexport/views.py` | Added `ImportJobViewSet.download`; improved `ExportJobViewSet.download` with FileResponse |
| `backend/importexport/serializers.py` | Removed `schedule` from ExportProjectSerializer fields |
| `backend/importexport/tests/__init__.py` | New |
| `backend/importexport/tests/test_import_export.py` | New — 6 integration tests |

---

## ADR Notes

1. **Synchronous execution** — Import and export run synchronously in the request thread. Acceptable for typical data volumes in this platform. If >10k rows become common, migrate to Celery async task queue.

2. **Scheduled exports not implemented** — The `ExportProject.schedule` field exists on the model but is hidden from the serializer. Cron-based or Celery Beat scheduling is future work.
