# core

This Django app contains the core domain models and APIs for Projects, Cycles, and Modules.

## Main Components

- **models.py**: Defines Project, Cycle, and Module models.
- **views.py**: API endpoints for managing projects (RBAC protected).
- **serializers.py**: DRF serializers for all models.
- **admin.py**: Admin site integration for all models.
- **urls.py**: API routing for all endpoints.
- **apps.py**: App configuration.

## API Overview

- `projects/`: CRUD for projects (RBAC-protected)
- (Extend with cycles and modules if needed in future)

## RBAC

Project endpoints are protected by the `HasRBACPermission` class.  
Users must have the `view_project` permission in the appropriate context.

## Testing

Add your tests in `core/tests.py`.

---

**Location:** `core/` (inside your Django project)