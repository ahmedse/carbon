# 🚀 Developer Guide: Multi-Tenant RBAC Django Platform

---

## **1. Project Structure Overview**

```
project/
│
├── accounts/   # Users, roles, permissions, RBAC context, assignment, auth
├── core/       # Tenants, Projects, Cycles, Modules (business structure)
├── dataschema/ # Dynamic tables, fields, rows, schema change logs
├── manage.py
└── ...
```

---

## **2. RBAC Data Model Summary**

- **Tenant**: Top-level organization (customer). All data is isolated per tenant.
- **User**: Linked to one tenant.
- **Project**: Belongs to one tenant.
- **Module**: Belongs to one project.
- **Roles**: `admin` (project), `auditor` (project), `dataowner` (module)
- **Permissions**: Assigned to roles (e.g., `manage_schema`, `manage_data`, etc.)
- **Context**: Defines where a role applies (`project` or `module`).
- **RoleAssignment**: A user, a role, and a context (active/inactive).

---

## **3. Authentication and Authorization**

### **Authentication**

- Use JWT (`/accounts/token/` to obtain, `/accounts/token/refresh/` to refresh).
- Always send `Authorization: Bearer <token>` header in API calls.

### **Authorization**

- All sensitive API endpoints use `HasRBACPermission` to enforce per-context permissions.
- Role assignments are managed via the Django admin interface.
- Tenants, projects, modules, and all related data are strictly tenant-isolated (except for superusers).

---

## **4. Key API Endpoints and Usage**

### **Authentication**

| Endpoint                       | Method | Description                 |
|--------------------------------|--------|-----------------------------|
| `/accounts/token/`             | POST   | Obtain JWT token            |
| `/accounts/token/refresh/`     | POST   | Refresh access token        |
| `/accounts/my-roles/`          | GET    | Get current user's roles    |

**Usage:**  
Login with username/password via `/accounts/token/`.  
Store and use the JWT access token for all requests.

---

### **User, Tenant, Project, Module Info**

| Endpoint                     | Method | Description                  |
|------------------------------|--------|------------------------------|
| `/accounts/tenants/`         | GET    | List own tenant info         |
| `/accounts/users/`           | GET    | List users in own tenant     |
| `/accounts/projects/`        | GET    | List projects (tenant)       |
| `/accounts/modules/`         | GET    | List modules (tenant)        |

---

### **RBAC Management**

- Role assignments are done **only via Django admin**.
- Frontend queries `/accounts/my-roles/` to get role/context/permissions for the logged-in user.

---

### **Dataschema (Tables, Fields, Rows)**

| Action                     | Endpoint                                    | Method | Permission Required      | Notes                                         |
|----------------------------|---------------------------------------------|--------|-------------------------|-----------------------------------------------|
| List tables in module      | `/dataschema/tables/?module={id}`           | GET    | view_schema             |                                               |
| Create table               | `/dataschema/tables/`                       | POST   | manage_schema           | Set `module` in POST body                     |
| Update table               | `/dataschema/tables/{id}/`                  | PATCH  | manage_schema           |                                               |
| Archive table              | `/dataschema/tables/{id}/archive/`          | POST   | manage_schema           | Only admin/dataowner                          |
| List fields in table       | `/dataschema/fields/?data_table={id}`       | GET    | view_schema             |                                               |
| Create field               | `/dataschema/fields/`                       | POST   | manage_schema           | Set `data_table` in POST body                 |
| Archive field              | `/dataschema/fields/{id}/archive/`          | POST   | manage_schema           | Only admin/dataowner                          |
| List rows in table         | `/dataschema/rows/?data_table={id}`         | GET    | view_data               | Can filter/search by field                    |
| Create row                 | `/dataschema/rows/`                         | POST   | manage_data             | Set `data_table` and `values` in POST body    |
| Update row                 | `/dataschema/rows/{id}/`                    | PATCH  | manage_data             |                                               |
| Upload file to row field   | `/dataschema/rows/{id}/upload/`             | POST   | manage_data             | `multipart/form-data`, `field`, `file`        |
| Schema change logs         | `/dataschema/schema-logs/`                  | GET    | manage_schema           | For audit/history                             |

---

### **Core Business Structure**

| Endpoint                | Method | Description                       |
|-------------------------|--------|-----------------------------------|
| `/core/projects/`       | GET    | List all projects (tenant)        |
| `/core/cycles/`         | GET    | List all cycles (tenant)          |
| `/core/modules/`        | GET    | List all modules (tenant/project) |

---

## **5. Permission Codes and Role Matrix**

| Role      | Context   | Permissions                                                      |
|-----------|-----------|------------------------------------------------------------------|
| admin     | project   | manage_schema, manage_data, view_schema, view_data, manage_project, manage_module |
| auditor   | project   | view_schema, view_data, manage_data                              |
| dataowner | module    | manage_schema, manage_data, view_schema, view_data, manage_module |

- "admin" and "auditor" assigned at project context.
- "dataowner" assigned at module context.

---

## **6. Frontend Integration Patterns**

### **a. Fetch and Store Role/Permission Data**

- On login or context switch, call `/accounts/my-roles/`.
- Store roles and permissions per context.
- Use this to drive available UI functionality.

**Example:**  
If user has `manage_schema` for current module/project → show "create table" button.

---

### **b. Context-aware API Calls**

- Always include required context (project/module ID) in API parameters or body as described.
- For table/field/row creation, ensure you pass the IDs as required.

---

### **c. Error Handling**

- **403 Forbidden:** User lacks permission. Show a clear message.
- **404 Not Found:** Resource doesn't exist or is inaccessible by tenant/is archived.

---

### **d. File Uploads**

- Use `/dataschema/rows/{row_id}/upload/` for file fields.
- Use `multipart/form-data` with `field` (field name) and `file` (file object).

---

### **e. Search and Filtering**

- Rows: `/dataschema/rows/?data_table={id}&search={value}` for full-text search.
- Filter by individual field: `/dataschema/rows/?data_table={id}&field__fieldname=value`.

---

### **f. Schema Change Logs**

- `/dataschema/schema-logs/` for audit/history per table/field.

---

## **7. Django Admin Usage**

- **Role assignments** (user, role, context) are managed via Django admin only.
- Only assign `admin` and `auditor` to project contexts.
- Only assign `dataowner` to module contexts.
- Maintain tenants, users, roles, and permissions as needed.

---

## **8. Developer Best Practices**

- **Never expose cross-tenant data.**  
  Always filter by tenant in views, serializers, and admin.
- **Always use RBAC permission checks in views.**
- **Document any new permission code and assign it to the right roles via admin.**
- **Test with multiple users, roles, and tenants.**
- **Log all critical actions (e.g., schema changes) for auditability.**
- **Use signals to clean up empty contexts when RoleAssignments are deleted.**

---

## **9. Example: Role/Permission Check in Frontend**

```js
// Pseudocode for checking if user can manage schema in current module
const canManageSchema = myRoles.some(role =>
    ((role.context_type === 'project' && role.project_id === currentProjectId) ||
     (role.context_type === 'module' && role.module_id === currentModuleId)) &&
    role.permissions.includes('manage_schema')
);
```

---

## **10. Frequently Used Endpoints (Cheat Sheet)**

| Action                   | Endpoint                                | Method | Notes                               |
|--------------------------|-----------------------------------------|--------|-------------------------------------|
| Login                    | /accounts/token/                        | POST   | JWT                                |
| List My Roles            | /accounts/my-roles/                     | GET    |                                    |
| List Projects            | /core/projects/                         | GET    |                                    |
| List Modules             | /core/modules/                          | GET    |                                    |
| List Tables in Module    | /dataschema/tables/?module={id}         | GET    |                                    |
| Create Table             | /dataschema/tables/                     | POST   |                                    |
| List Fields in Table     | /dataschema/fields/?data_table={id}     | GET    |                                    |
| Create Field             | /dataschema/fields/                     | POST   |                                    |
| List Rows in Table       | /dataschema/rows/?data_table={id}       | GET    |                                    |
| Create Row               | /dataschema/rows/                       | POST   |                                    |
| Upload File to Row Field | /dataschema/rows/{row_id}/upload/       | POST   | multipart/form-data                |
| Schema Change Logs       | /dataschema/schema-logs/                | GET    |                                    |

---

## **11. Adding New Features**

1. **Add new permission code** to the `Permission` table.
2. **Assign permission** to appropriate roles in Django admin.
3. **Use new permission** in API views (`required_permission = 'new_permission'`).
4. **Document new roles/permissions** for the frontend team.

---

## **12. Testing**

- Write tests for all new endpoints and business logic.
- Use Django's `TestCase` to check tenant isolation, RBAC enforcement, and data integrity.
- Example: see `core/tests.py` for model tests.

---

## **13. Gotchas & Reminders**

- **Superusers** see everything; all others are restricted to their tenant.
- **“is_archived”** is used instead of delete for most objects for audit/history.
- **Only use the official permissions codes and assign via admin**—no ad hoc codes.
- **Never show actions in UI that user doesn’t have rights for.**

---

## **14. Onboarding Checklist for New Developers**

- Clone repo, set up virtualenv, install requirements.
- Run migrations.
- Create superuser, log into Django admin.
- Add tenants, users, projects, modules, roles, permissions via admin.
- Assign roles to users in context.
- Run test suite.
- Review `/accounts/my-roles/` API to understand role/context/permissions structure.

---

## **15. Support**

For questions about:
- **Authentication/JWT:** See `accounts/urls.py` and DRF SimpleJWT docs.
- **RBAC:** See `accounts/models.py`, `accounts/permissions.py`, and Django admin.
- **Data structure:** See `core/models.py` and `dataschema/models.py`.
- **API integration:** See `urls.py`, `views.py`, and corresponding serializers.

---

# **Summary Diagram**

```
Tenant
 └─ User
      ├─ RoleAssignment (user, role, context)
      │    └─ Context (type: project/module, project, module)
      │         └─ Role (name, permissions)
      │              └─ Permission (code, description)
 └─ Project
      └─ Module
           └─ DataTable
                └─ DataField
                └─ DataRow
```

---

**If you follow this guide, your team will develop and maintain a robust, secure, and scalable multi-tenant SaaS platform with strong RBAC and data isolation.**

For additional onboarding docs or OpenAPI/Swagger generation, let me know!