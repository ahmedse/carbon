# 2. `importexport` App Design

## **Purpose**
Handles bulk data import/export for any dataschema table, separate from core CRUD. Supports CSV, Excel, and potentially other formats or integrations. Handles validation, logging, and (optionally) async/background jobs.

---

## **Entities**

- **ImportJob:**  
  - File, target DataTable, status, user, started/finished, log, errors, summary

- **ExportJob:**  
  - Target DataTable, parameters/filters, file (generated), status, user, started/finished, log

- **(Optionally)**  
  - ImportLog/ExportLog for detailed event tracking

---

## **Responsibilities**

- File upload/download for data tables
- Mapping/importing/exporting data to/from dataschema tables
- Validate data against dataschema schema before persisting
- Handle errors, generate logs/reports for each job
- Support future async jobs (e.g., Celery tasks for large files)
- Provide audit trail for all import/export operations

---

## **API**

- `/api/importexport/import/` (POST new import job with file, table ID, etc.)
- `/api/importexport/import/{job_id}/status/` (GET job status/progress)
- `/api/importexport/import/{job_id}/log/` (GET validation/errors)
- `/api/importexport/export/` (POST create export job)
- `/api/importexport/export/{job_id}/download/` (GET, file ready)
- `/api/importexport/export/{job_id}/status/` (GET status/progress)

---

## **RBAC**

- Only Admins (or designated roles) can import/export
- All jobs linked to user and context for audit

---

## **Integration with `dataschema`**

- Reads/writes data using `dataschema` models and APIs
- Never modifies schema; only data
- Imports/exports are always validated against latest active schema

---

## **Audit, Logging**

- All jobs/events logged (who, when, what, status, errors)
- Retain logs for compliance and troubleshooting

---

## **Future Extensions**

- Support more formats (JSON, XML, Google Sheets, etc.)
- Integration with external connectors (IoT, data lakes, etc.)
- Scheduling, recurring jobs, notifications
- Permissions matrix for fine-grained control

---

# **Separation Summary Table**

| App         | Responsibilities                                           | Exposes to...           |
|-------------|-----------------------------------------------------------|-------------------------|
| dataschema  | Tables, fields, rows, schema/version/audit, RBAC          | Frontend, importexport  |
| importexport| Bulk import/export, file handling, validation, logging     | Frontend, admins        |

---
