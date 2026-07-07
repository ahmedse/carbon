# TASK.md — STEWARD-ADMIN-1 (RUN 12): Steward-scoped role assignment

> **Role:** worker/executor. Do **exactly** this task. This is a **security-sensitive** change —
> follow the code verbatim, do not "improve" or generalize it. When done, write `TASK-RESULT.md` and STOP.

---

## 0. Context (read first)

Carbon is a platform with an OrgUnit tree and `ScopedRole` (user + group + org_unit + module) RBAC.
Today only **global admins / superusers** can manage role assignments. We want an **org-scoped steward**
(a user who holds an `admins_group` role on an OrgUnit) to be able to **assign roles to EXISTING users
within their own org subtree only** — and never escalate beyond it.

**Locked decisions:**
- A steward may **only assign/list/delete role assignments** (`ScopedRole`). A steward may **NOT create users**
  (the Users endpoint stays global-admin-only — do NOT touch `UserViewSet`).
- **Anti-escalation (hard rule):** a steward can NEVER
  - create/edit/delete a **global** role (`org_unit=None` AND `module=None`), nor
  - target an org unit **outside** their allowed subtree (directly via `org_unit`, or indirectly via a `module`'s org unit).

Org tree (for reference): AAST(1) → Abu Qir Campus(3) → Transportation/Fleet(4), **Facilities & Utilities(5)**, Procurement & Finance(6); College of Engineering(2) under AAST(1).

**This task changes NO models → NO migration.** If `makemigrations --check` reports changes, STOP.

---

## 1. Files you MAY edit (EXACTLY 3)

1. `backend/accounts/rbac_utils.py` — append 2 helpers (STEP 1).
2. `backend/accounts/permissions.py` — extend one import line + add one permission class (STEP 2).
3. `backend/accounts/views.py` — extend imports + replace the `ScopedRoleViewSet` class body (STEP 3).

## 1b. Files you MUST NOT touch
- Any `models.py`, any migration, any serializer, any frontend, any other app.
- **`UserViewSet`, `GroupViewSet`, `HasScopedRole`** (leave exactly as-is).
- Do NOT reintroduce `project` / `project_id` / `tenant`.

---

## STEP 1 — `backend/accounts/rbac_utils.py`

**Append** to the END of the file (after `get_visible_module_ids`). `ADMIN_ROLES` already exists in this file.

```python


def get_steward_org_unit_ids(user):
    """Org units (incl. all descendants) where the user holds an admins_group role.
    Empty set => the user is not a steward anywhere."""
    if not user or not getattr(user, "is_authenticated", False):
        return set()
    return get_allowed_org_unit_ids(user, ADMIN_ROLES)


def user_is_steward(user):
    """True if the user administers at least one org subtree (but is not necessarily global)."""
    return bool(get_steward_org_unit_ids(user))
```

---

## STEP 2 — `backend/accounts/permissions.py`

### 2.1 Replace the import block

Find:

```python
from .rbac_utils import (
    user_has_global_role, user_has_module_role, get_allowed_org_unit_ids,
)
```

Replace with:

```python
from .rbac_utils import (
    user_has_global_role, user_has_module_role, get_allowed_org_unit_ids,
    ADMIN_ROLES, get_steward_org_unit_ids,
)
```

### 2.2 Append this permission class to the END of the file

```python


class CanManageScopedRoles(permissions.BasePermission):
    """Allows superusers, global admins, and org-scoped stewards (admins_group on any org unit).
    Subtree enforcement + anti-escalation is done in the viewset (get_queryset / perform_*)."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if user_has_global_role(user, ADMIN_ROLES):
            return True
        return bool(get_steward_org_unit_ids(user))
```

---

## STEP 3 — `backend/accounts/views.py`

### 3.1 Extend imports

Find:

```python
from .permissions import HasScopedRole
```

Replace with:

```python
from .permissions import HasScopedRole, CanManageScopedRoles
from .rbac_utils import user_is_global_admin, get_steward_org_unit_ids
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q
```

### 3.2 Replace the whole `ScopedRoleViewSet` class

Find (replace the ENTIRE class, from `class ScopedRoleViewSet` down to the end of its `get_serializer_class` method):

```python
class ScopedRoleViewSet(viewsets.ModelViewSet):
    """
    CRUD for scoped role assignments.
    """
    queryset = ScopedRole.objects.all()
    permission_classes = [HasScopedRole]
    required_role = "admin"  # Only users with 'admin' ScopedRole can manage scoped roles

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ScopedRoleCreateSerializer
        return ScopedRoleSerializer
```

Replace with:

```python
class ScopedRoleViewSet(viewsets.ModelViewSet):
    """
    CRUD for scoped role assignments.

    - Superusers / global admins: full access.
    - Org-scoped stewards (admins_group on an org unit): may list/create/delete role
      assignments ONLY within their own org subtree, and NEVER global roles.
    """
    queryset = ScopedRole.objects.all()
    permission_classes = [CanManageScopedRoles]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ScopedRoleCreateSerializer
        return ScopedRoleSerializer

    def get_queryset(self):
        user = self.request.user
        if user_is_global_admin(user):
            return ScopedRole.objects.all()
        allowed = get_steward_org_unit_ids(user)
        # Only assignments whose target org (directly or via module) is in the steward's subtree.
        return ScopedRole.objects.filter(
            Q(org_unit_id__in=allowed) | Q(module__org_unit_id__in=allowed)
        )

    def _assert_within_subtree(self, org_unit, module):
        """Anti-escalation guard: a steward may only target an org unit inside their subtree,
        never a global role (org_unit=None AND module=None) and never a foreign subtree."""
        user = self.request.user
        if user_is_global_admin(user):
            return
        allowed = get_steward_org_unit_ids(user)
        target_org_id = None
        if org_unit is not None:
            target_org_id = org_unit.id if hasattr(org_unit, 'id') else org_unit
        elif module is not None:
            target_org_id = getattr(module, 'org_unit_id', None)
        if not target_org_id or target_org_id not in allowed:
            raise PermissionDenied(
                "You can only manage role assignments within your own organization units."
            )

    def perform_create(self, serializer):
        self._assert_within_subtree(
            serializer.validated_data.get('org_unit'),
            serializer.validated_data.get('module'),
        )
        serializer.save()

    def perform_update(self, serializer):
        self._assert_within_subtree(
            serializer.validated_data.get('org_unit'),
            serializer.validated_data.get('module'),
        )
        serializer.save()

    def perform_destroy(self, instance):
        self._assert_within_subtree(instance.org_unit, instance.module)
        instance.delete()
```

> Do NOT change `UserViewSet` or `GroupViewSet`. They keep `HasScopedRole` + `required_role="admin"`,
> which correctly keeps user creation restricted to global admins (a steward gets 403 there).

---

## 4. Run

```bash
cd /home/ahmed/aast/carbon/backend && source venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
cd /home/ahmed/aast/carbon && ./manage.sh restart
```

---

## 5. Acceptance — setup the steward fixture

```bash
cd /home/ahmed/aast/carbon/backend && source venv/bin/activate
python manage.py shell -c "
from accounts.models import User, ScopedRole
from django.contrib.auth.models import Group
from mdm.models import OrgUnit
u,_ = User.objects.get_or_create(username='fac.steward', defaults={'is_active':True})
u.is_active=True; u.set_password('Steward_123'); u.save()
g = Group.objects.get(name='admins_group')
ou = OrgUnit.objects.get(name='Facilities & Utilities')  # id 5
ScopedRole.objects.get_or_create(user=u, group=g, org_unit=ou, module=None)
tu = User.objects.get(username='transport.officer')
print('READY steward=%s trans_user=%s fac_org=%s trans_org=%s' % (u.id, tu.id, ou.id, OrgUnit.objects.get(name='Transportation / Fleet').id))
" 2>&1 | grep READY
```
Record the printed ids: `TRANS_USER`, `FAC_ORG` (=5), `TRANS_ORG` (=4).

## 6. Acceptance — checks (paste all outputs into TASK-RESULT.md)

```bash
cd /home/ahmed/aast/carbon
tok() { curl -s -X POST http://localhost:8009/carbon-api/token/ -H "Content-Type: application/json" \
  -d "{\"username\":\"$1\",\"password\":\"$2\"}" | python3 -c "import sys,json;print(json.load(sys.stdin).get('access',''))"; }
ST=$(tok fac.steward Steward_123)
AD=$(tok ahmed AdminPa_132)
# helper: POST a scoped role, print HTTP status
mkrole() { curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8009/carbon-api/scoped-roles/ \
  -H "Authorization: Bearer $1" -H "Content-Type: application/json" -d "$2"; }
```

Use `TRANS_USER` from setup, `FAC_ORG=5`, `TRANS_ORG=4`.

**6.1 — steward list is subtree-scoped**
```bash
curl -s http://localhost:8009/carbon-api/scoped-roles/ -H "Authorization: Bearer $ST" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);r=d.get('results',d);print('orgs seen:', sorted({x['org_unit'] for x in r}))"
```
Expected: only Facilities & Utilities roles — must **NOT** contain `Transportation / Fleet` or a global (`None`) role.

**6.2 — steward CAN assign an existing user within subtree (org 5)** → expect `201`
```bash
echo "create-in-subtree: $(mkrole "$ST" "{\"user\":TRANS_USER,\"group\":2,\"org_unit\":5,\"module\":null,\"is_active\":true}")"
```
> Replace `TRANS_USER` with the id and `\"group\":2` with the id of `dataowners_group`
> (find it: `curl -s http://localhost:8009/carbon-api/roles/ -H "Authorization: Bearer $AD"`).

**6.3 — steward CANNOT create a GLOBAL role** → expect `403`
```bash
echo "create-global: $(mkrole "$ST" "{\"user\":TRANS_USER,\"group\":2,\"org_unit\":null,\"module\":null,\"is_active\":true}")"
```

**6.4 — steward CANNOT target a foreign subtree (org 4)** → expect `403`
```bash
echo "create-foreign: $(mkrole "$ST" "{\"user\":TRANS_USER,\"group\":2,\"org_unit\":4,\"module\":null,\"is_active\":true}")"
```

**6.5 — steward CANNOT delete a foreign role (role id 3 = transport.officer @ org 4)** → expect `404` or `403`
```bash
echo "delete-foreign: $(curl -s -o /dev/null -w '%{http_code}' -X DELETE http://localhost:8009/carbon-api/scoped-roles/3/ -H "Authorization: Bearer $ST")"
```

**6.6 — steward CANNOT create users** → expect `403`
```bash
echo "steward-create-user: $(curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8009/carbon-api/users/ \
  -H "Authorization: Bearer $ST" -H "Content-Type: application/json" -d '{"username":"x.hacker","password":"Zzz_12345"}')"
```

**6.7 — global admin still has full access** → expect `200`
```bash
echo "admin-list: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8009/carbon-api/scoped-roles/ -H "Authorization: Bearer $AD")"
```

---

## 7. PASS BAR (all must hold)
1. `manage.py check` clean; `makemigrations --check` = **No changes detected**.
2. 6.1: steward sees **only Facilities & Utilities** roles (no Transportation, no global).
3. 6.2: **201** (assign existing user within subtree works).
4. 6.3: **403** (no global role).
5. 6.4: **403** (no foreign subtree).
6. 6.5: **404 or 403** (cannot delete foreign role).
7. 6.6: **403** (steward cannot create users).
8. 6.7: **200** (global admin unaffected).
9. Exactly **3 files changed**; no migration, no frontend, no model, `UserViewSet` untouched.

## 8. STOP conditions (report and halt)
- Any migration would be created.
- Any acceptance status differs from expected (especially any 403 that returns 201 — that is a
  privilege-escalation failure; STOP immediately).
- You need to edit any file beyond the 3 listed.

## 9. Report
Write `TASK-RESULT.md` with: files changed, the setup ids, exact outputs for §6.1–6.7, deviations
(should be none), and `Final status: PASS` or `FAIL`.
