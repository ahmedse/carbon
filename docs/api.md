Absolutely! Here’s a **comprehensive developer guide** for your `dataschema` API, including authentication, endpoints, request/response formats, validation, and best practices.  
This is written so frontend developers (React, Vue, etc.) can easily integrate with your backend.

---

# 🗂️ DataSchema API Developer Guide

## Table of Contents

1. [Authentication](#authentication)
2. [General Conventions](#general-conventions)
3. [Endpoints Overview](#endpoints-overview)
4. [Data Table APIs](#data-table-apis)
5. [Data Field APIs](#data-field-apis)
6. [Data Row APIs](#data-row-apis)
7. [Validation Rules](#validation-rules)
8. [Error Responses](#error-responses)
9. [RBAC/Permissions](#rbacpermissions)
10. [Changelog & Schema Management](#changelog--schema-management)
11. [Examples](#examples)

---

## Authentication

All endpoints require authentication via **JWT Bearer tokens**.

- **How to authenticate:**  
  - Obtain a token via `/api/token/` (or your login endpoint).
  - Attach header to every request:  
    ```
    Authorization: Bearer <your_token_here>
    ```

---

## General Conventions

- **All requests/response bodies:** JSON
- **All endpoints are under `/api/dataschema/`** (or as routed in your project)
- **Timestamps:** ISO8601, UTC
- **IDs:** Always refer to entities by integer `id`

---

## Endpoints Overview

| Entity      | List             | Detail           | Create           | Update           | Delete           |
|-------------|------------------|------------------|------------------|------------------|------------------|
| DataTable   | `GET /tables/`   | `GET /tables/:id/` | `POST /tables/` | `PUT/PATCH /tables/:id/` | `DELETE /tables/:id/` |
| DataField   | `GET /fields/`   | `GET /fields/:id/` | `POST /fields/` | `PUT/PATCH /fields/:id/` | `DELETE /fields/:id/` |
| DataRow     | `GET /rows/`     | `GET /rows/:id/`   | `POST /rows/`   | `PUT/PATCH /rows/:id/`   | `DELETE /rows/:id/`   |

*Changelog, versioning, and module/project filtering also available.*

---

## Data Table APIs

### 1. **List Tables**
```http
GET /api/dataschema/tables/?module_id=1
```
**Query params:**
- `module_id`: (optional) Filter by module

**Response:**
```json
[
  {
    "id": 1,
    "title": "Customers",
    "description": "Customer information",
    "module": 2,
    "version": 1,
    "is_archived": false,
    "created_at": "...",
    "fields": [
      { ... see DataField ... }
    ],
    "row_count": 10
  },
  ...
]
```

### 2. **Table Detail**
```http
GET /api/dataschema/tables/1/
```
**Response:**
Same as above, single object.

### 3. **Create Table**
```http
POST /api/dataschema/tables/
Content-Type: application/json

{
  "title": "Customers",
  "description": "Customer information",
  "module": 2
}
```
**Response:**  
201, the created DataTable object.

---

## Data Field APIs

### 1. **List Fields**
```http
GET /api/dataschema/fields/?data_table_id=1
```
**Query params:**
- `data_table_id`: (optional) Filter by data table

**Response:**
```json
[
  {
    "id": 1,
    "data_table": 1,
    "name": "first_name",
    "label": "First Name",
    "type": "string",         // string | number | boolean | select | multiselect | reference
    "order": 1,
    "description": "",
    "required": true,
    "options": [ {"value": "red"}, {"value": "blue"} ],   // for select/multiselect
    "validation": null,       // e.g. regex
    "is_active": true,
    "reference_table": null,
    "created_at": "...",
    "version": 1
  },
  ...
]
```

### 2. **Create Field**
```http
POST /api/dataschema/fields/
Content-Type: application/json

{
  "data_table": 1,
  "name": "email",
  "label": "Email",
  "type": "string",
  "required": true,
  "order": 2
}
```
#### Special notes:
- **Unique constraint:** `name` must be unique within the table.
- **Select/multiselect:** You **must** provide `options` as a list of `{ "value": ... }` objects.

---

## Data Row APIs

### 1. **List Rows**
```http
GET /api/dataschema/rows/?data_table_id=1
```
**Query params:**
- `data_table_id`: (required) For which table
- Filtering, pagination, and search may be available

**Response:**
```json
[
  {
    "id": 1,
    "data_table": 1,
    "values": {
      "first_name": "Alice",
      "age": 30,
      "favorite_color": "red"
    },
    "created_at": "...",
    "version": 1
  },
  ...
]
```

### 2. **Create Row**
```http
POST /api/dataschema/rows/
Content-Type: application/json

{
  "data_table": 1,
  "values": {
    "first_name": "Bob",
    "age": 22,
    "favorite_color": "blue"
  }
}
```
- **All `required` fields must be present in `values`.**
- **Type checking** is enforced per field.

#### Example errors:
```json
{
  "age": "This field is required."
}
```

---

## Validation Rules

- **Required fields:** Must be present and not empty/null.
- **Types:**
  - `string`: Must be string.
  - `number`: Must be integer or float.
  - `boolean`: Must be true/false.
  - `select`: Value must match one of the allowed options.
  - `multiselect`: Must be a list of allowed values.
- **Uniqueness:** Field `name` per table is unique.
- **Reference fields:** Value must point to a valid row in the referenced table.

**Example error:**
```json
{
  "favorite_color": "Value must be one of ['red', 'blue']."
}
```

---

## Error Responses

- **400 Bad Request**: Validation failed.  
  Example:
  ```json
  {
    "age": "This field is required.",
    "favorite_color": "Value must be one of ['red', 'blue']."
  }
  ```
- **401 Unauthorized**: Not authenticated.
- **403 Forbidden**: No permission for the operation (RBAC).

---

## RBAC/Permissions

- **All APIs check your JWT and RBAC permissions.**
- **You need appropriate role (admin, dataowner, audit, etc.) in the project/module scope.**
- **If you get 403:** Your token is valid but you lack permission for the table/module/project.

---

## Changelog & Schema Management

- **Schema changes** (fields, tables) are versioned.
- **Changelog endpoint** logs all schema changes for audit/history.

```http
GET /api/dataschema/changelog/?data_table_id=1
```

---

## Examples

### Create a new table, add fields, and upload row

1. **Create table**
   ```http
   POST /api/dataschema/tables/
   {
     "title": "Customers",
     "module": 2
   }
   ```

2. **Add fields**
   ```http
   POST /api/dataschema/fields/
   {
     "data_table": 1,
     "name": "email",
     "label": "Email",
     "type": "string",
     "required": true
   }
   ```

3. **Add row**
   ```http
   POST /api/dataschema/rows/
   {
     "data_table": 1,
     "values": {
       "email": "alice@example.com"
     }
   }
   ```

---

## Tips for Frontend

- **Always GET table schema (fields) before building forms.**
- **For select/multiselect fields, use the `options` array to build dropdowns.**
- **Show validation errors inline using the error response JSON.**
- **Handle 401/403 globally (redirect to login or show "no permission").**
- **Display field `label` not just the `name`.**
- **Support pagination for large row sets.**

---

## Feedback & Debugging

- If you get **unexpected 403**: double-check roles.
- If **validation fails**, use the error keys to highlight the relevant fields.
- For any API problem, check the server logs for traceback.

---

**For anything custom (file uploads, reference fields, etc.), ask your backend team for the exact API contract.**

---

**If you want this as a downloadable Markdown or want OpenAPI/Swagger docs, just let me know!**