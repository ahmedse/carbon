# Carbon Platform - Dev Login Credentials

## Local Development Users

### Admin User
- **Username:** `admin`
- **Password:** `CarbonDev123!`
- **Permissions:** Full admin access, all projects and modules

### Data Owner
- **Username:** `dataowner1`
- **Password:** `dataowner1pass`
- **Permissions:** Data entry access to assigned modules

---

## How to Login

1. Start services: `./manage.sh start`
2. Navigate to: http://localhost:5173/carbon/login
3. Enter credentials above
4. You'll be redirected to the dashboard automatically (single project) or shown project selection (multiple projects)

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
