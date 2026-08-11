# core

This Django app contains core domain models and APIs for Modules (data products), Feedback, and Notifications.

## Main Components

- **models.py**: Defines Module, Feedback, and Notification models.
- **views.py**: API endpoints for modules (CBAC-protected).
- **serializers.py**: DRF serializers for all models.
- **admin.py**: Admin site integration for all models.
- **urls.py**: API routing for all endpoints.
- **apps.py**: App configuration.

## API Overview

- `modules/`: CRUD for data products (CBAC-protected) + `quality_summary/` and `audit_trail/` @actions
- `notifications/`: User-scoped notifications with `mark_read`/`mark_all_read` actions
- `feedback/`: Public feedback submission

## Access Control

Module endpoints use Capability-Based Access Control (CBAC):
- GET/HEAD/OPTIONS: `IsAuthenticated` (any authenticated user)
- POST/PUT/PATCH/DELETE: `AdminOrSuperuserOnly`
- Module visibility is scoped via `get_visible_module_ids()` from `accounts.rbac_utils`

## Testing

Add your tests in `core/tests.py`.

---

**Location:** `core/` (inside your Django project)