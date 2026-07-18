# Carbon Platform - Dev Login Credentials

## Local Development Users

### Superuser (Django Admin)
- **Username:** `ahmed`
- **Password:** `AdminPa_132`
- **Type:** Django superuser (`is_superuser=True`)
- **Permissions:** Full access via Django admin interface
- **Role:** Global admin via ScopedRole (admins_group, org_unit=None)

### Global Admin (API)
- **Username:** `global_admin`
- **Password:** `GlobalAdmin_2026!`
- **Role:** admins_group with org_unit=None (global scope)
- **Permissions:** Full CRUD on governance, schema, data across ALL org units
- **Use Cases:** Platform configuration, governance management, cross-org administration

### Org-Scoped Admin (API) — Facilities
- **Username:** `fac.steward`
- **Password:** `FacSteward_2025!`
- **Role:** admins_group with org_unit=5 (Facilities & Utilities)
- **Permissions:** 
  - Read-only: governance, schema
  - Full CRUD: data within org scope
- **Use Cases:** Org-level data management, Facilities reporting

### Data Owner — Facilities
- **Username:** `facilities.officer`
- **Password:** `Facilities_123`
- **Role:** dataowners_group with org_unit=5
- **Permissions:** CRUD data rows within Facilities scope (read-only governance/schema)

### Data Owner — Transportation
- **Username:** `transport.officer`
- **Password:** `Transport_123`
- **Role:** dataowners_group with org_unit=4 (Transportation/Fleet)
- **Permissions:** CRUD data rows within Transportation scope

---

## API Authentication

All API access requires a JWT token. To obtain a token:

```bash
curl -X POST http://localhost:8009/carbon-api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"USERNAME","password":"PASSWORD"}'
```

**Response:**
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

Use the `access` token in API requests:
```bash
curl http://localhost:8009/carbon-api/[endpoint] \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Example: Get Global Admin Token**
```bash
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8009/carbon-api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"global_admin","password":"GlobalAdmin_2026!"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access'])")

echo "Token: $ADMIN_TOKEN"
```

---

## How to Login (Web UI)

1. Start services: `./manage.sh start`
2. Navigate to: http://localhost:5173/carbon/login
3. Enter credentials from the table above
4. You'll be redirected to the dashboard

---

## How to Reset User Passwords

```bash
cd backend && python manage.py shell << 'PY'
from django.contrib.auth import get_user_model
User = get_user_model()

# Reset password for global_admin
user = User.objects.get(username='global_admin')
user.set_password('GlobalAdmin_2026!')
user.save()
print('Password reset for global_admin')
PY
```

---

## How to Reset/Create Users

```bash
cd backend && ./venv/bin/python - <<'PY'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from django.contrib.auth import get_user_model
from accounts.models import Tenant
User = get_user_model()

# Create tenant
t, _ = Tenant.objects.get_or_create(name='local')

# Create admin
u, _ = User.objects.get_or_create(username='admin')
u.email = 'admin@example.com'
u.tenant = t
u.is_staff = True
u.is_superuser = True
u.set_password('CarbonDev123!')
u.save()
print('Admin user created/updated')
PY
```

---

## Troubleshooting

If login doesn't redirect to dashboard:
1. Clear browser localStorage: `localStorage.clear()` in browser console
2. Ensure backend is running: `./manage.sh status`
3. Check browser console for errors
4. Verify user has project assignments (see backend logs)

---

**Security Warning:** These are development credentials only. 
Change all passwords before deploying to staging or production.
