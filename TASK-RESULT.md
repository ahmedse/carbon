# TASK-RESULT.md — STEWARD-ADMIN-1 (RUN 12: steward-scoped role assignment)

## Files changed
- backend/accounts/rbac_utils.py
- backend/accounts/permissions.py
- backend/accounts/views.py

## 4. Run
```bash
cd /home/ahmed/aast/carbon/backend && source venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
cd /home/ahmed/aast/carbon && ./manage.sh restart
```
Output:
```text
System check identified no issues (0 silenced).
No changes detected
```

## 5. Setup ids
```bash
cd /home/ahmed/aast/carbon/backend && source venv/bin/activate
python manage.py shell -c "from accounts.models import User, ScopedRole; from django.contrib.auth.models import Group; from mdm.models import OrgUnit; u,_ = User.objects.get_or_create(username='fac.steward', defaults={'is_active':True}); u.is_active=True; u.set_password('Steward_123'); u.save(); g = Group.objects.get(name='admins_group'); ou = OrgUnit.objects.get(name='Facilities & Utilities'); ScopedRole.objects.get_or_create(user=u, group=g, org_unit=ou, module=None); tu = User.objects.get(username='transport.officer'); print('READY steward=%s trans_user=%s fac_org=%s trans_org=%s' % (u.id, tu.id, ou.id, OrgUnit.objects.get(name='Transportation / Fleet').id))" 2>&1 | grep READY
```
Output:
```text
READY steward=14 trans_user=9 fac_org=5 trans_org=4
```

## 6. Acceptance checks
### 6.1 steward list is subtree-scoped
```bash
curl -s http://localhost:8009/carbon-api/accounts/scoped-roles/ -H "Authorization: Bearer $ST" | python3 -c "import sys,json;d=json.load(sys.stdin);r=d if isinstance(d,list) else d.get('results',d);print('orgs seen:', sorted({x.get('org_unit') for x in r}))"
```
Output:
```text
orgs seen: ['Facilities & Utilities']
```

### 6.2 steward can assign within subtree
```bash
curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8009/carbon-api/accounts/scoped-roles/ -H "Authorization: Bearer $ST" -H "Content-Type: application/json" -d "{\"user\":9,\"group\":3,\"org_unit\":5,\"module\":null,\"is_active\":true}"
```
Output:
```text
201
```

### 6.3 steward cannot create global role
```bash
curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8009/carbon-api/accounts/scoped-roles/ -H "Authorization: Bearer $ST" -H "Content-Type: application/json" -d "{\"user\":9,\"group\":3,\"org_unit\":null,\"module\":null,\"is_active\":true}"
```
Output:
```text
403
```

### 6.4 steward cannot target foreign subtree
```bash
curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8009/carbon-api/accounts/scoped-roles/ -H "Authorization: Bearer $ST" -H "Content-Type: application/json" -d "{\"user\":9,\"group\":3,\"org_unit\":4,\"module\":null,\"is_active\":true}"
```
Output:
```text
403
```

### 6.5 steward cannot delete foreign role
```bash
curl -s -o /dev/null -w '%{http_code}' -X DELETE http://localhost:8009/carbon-api/accounts/scoped-roles/3/ -H "Authorization: Bearer $ST"
```
Output:
```text
404
```

### 6.6 steward cannot create users
```bash
curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8009/carbon-api/accounts/users/ -H "Authorization: Bearer $ST" -H "Content-Type: application/json" -d '{"username":"x.hacker","password":"Zzz_12345"}'
```
Output:
```text
403
```

### 6.7 global admin still has full access
```bash
curl -s -o /dev/null -w '%{http_code}' http://localhost:8009/carbon-api/accounts/scoped-roles/ -H "Authorization: Bearer $AD"
```
Output:
```text
200
```

## Deviations / Blockers
- None.

## Final status: PASS
