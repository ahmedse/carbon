# accounts

This Django app implements Role-Based Access Control (RBAC) for users, supporting multi-level context (global, project, cycle, module).

## Main Components

- **models.py**: Defines User, Role, Context, and RoleAssignment models.
- **views.py**: API endpoints for managing roles, contexts, assignments, authentication, and retrieving user roles.
- **serializers.py**: DRF serializers for all models.
- **permissions.py**: Custom DRF permission for RBAC enforcement.
- **utils.py**: Helper for hierarchical permission checking.
- **admin.py**: Admin site integration for all models.
- **urls.py**: API routing for all endpoints.
- **apps.py**: App configuration.

## API Overview

- `roles/`: CRUD for roles
- `contexts/`: CRUD for contexts
- `role-assignments/`: CRUD for assignments
- `token/`, `token/refresh/`: JWT auth
- `my-roles/`: Returns roles and their contexts for the authenticated user

## How to Extend

- Add new permissions to roles via the `permissions` JSON field.
- Extend contexts to fit your project’s structure.
- Override `user_has_permission` for customized rules.

## Test

Add your tests in `accounts/tests.py`.

---

**Location:** `accounts/` (inside your Django project)