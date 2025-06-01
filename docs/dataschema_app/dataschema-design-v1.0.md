
# 1. `dataschema` App Design

## **Purpose**
Defines and manages dynamic, versioned, RBAC-controlled data tables (schemas), fields, and row data, fully integrated into the Carbon Platform’s multi-tenant/project/module context.

---

## **Entities**

- **DataTable:**  
  - Title, description, belongs to module → project → tenant
  - Versioned, archivable, audited

- **DataField:**  
  - Belongs to DataTable
  - Type (string, number, date, select, etc.), options, validation (JSON), required/active/archived/versioned/audited

- **FieldOption:**  
  - For select/multiselect fields: value, label, order

- **DataRow:**  
  - Belongs to DataTable
  - Stores all row values as JSON (plus system fields: created at/by, updated at/by)

- **SchemaChangeLog:**  
  - Logs all schema changes: who, what, when, before/after

---

## **Responsibilities**

- Manage CRUD for tables, fields, and data rows
- Enforce RBAC and context (tenant/project/module) at all levels
- Validate all data against schema and field rules
- Provide versioning and audit/history for schema changes
- Expose API for CRUD and for other apps (like import/export) to use

---

## **API (Internal/External)**

- `/api/dataschema/tables/` (list/create)
- `/api/dataschema/tables/{id}/` (retrieve/update/delete)
- `/api/dataschema/tables/{id}/fields/` (list/add fields)
- `/api/dataschema/fields/{id}/` (retrieve/update/delete/archive)
- `/api/dataschema/tables/{id}/rows/` (list/create)
- `/api/dataschema/rows/{id}/` (retrieve/update/delete)
- *(No direct import/export endpoints; those are in `importexport`)*

---

## **RBAC**

- Table/field CRUD: admin
- Row CRUD: dataowner for module (via platform RBAC)
- API always checks context/permissions

---

## **Audit, Versioning, Archiving**

- All schema changes logged with full before/after, who, when, what
- Soft-archive for tables/fields/rows
- Version integer on tables/fields

