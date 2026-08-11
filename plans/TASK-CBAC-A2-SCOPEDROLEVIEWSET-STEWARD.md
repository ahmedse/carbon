# TASK-CBAC-A2 — MA Decision: ScopedRoleViewSet steward role-assignment loss

> **Status**: ✅ CLOSED — Option A accepted (centralize role-assignment management)
> **Type**: Decision + remediation
> **Depends on**: TASK-CBAC-TRUST-CORE-SWAP (committed `cc196da`)
> **Owner**: Master Architect
> **Opened**: 2026-08-11 (QA verification, deviation #5)
> **Closed**: 2026-08-11 — **MA decision: Option A (Accept/centralize)**

## Problem Statement

During the RBAC→CBAC trust-core swap, `ScopedRoleViewSet` (role-assignment management)
was moved from `CanManageScopedRoles` to:

```python
permission_classes = [AdminOrSuperuserOnly]
required_capability = 'platform:manage_access'
```

`platform:manage_access` is **only** granted to `admin` / `admins_group` (via the `"*"`
wildcard in `GROUP_CAPABILITIES`). Per DD-1, scoped wildcard roles resolve to **view-only**
capabilities, so an **org-scoped steward** (`admins_group` attached to an org unit) **loses
all role-assignment management** (list/create/delete) — even within their own org subtree.

The class docstring still advertises the pre-swap steward contract:

```python
"""
CRUD for scoped role assignments.
- Superusers / global admins: full access.
- Org-scoped stewards (admins_group on an org unit): may list/create/delete role
  assignments ONLY within their own org subtree, and NEVER global roles.
"""
```

…which is now false: `AdminOrSuperuserOnly` gates reads too, so stewards cannot even list.

## Impact

| Stakeholder | Before (RBAC) | After (CBAC, current) |
|---|---|---|
| Global admin | Full | Full (unchanged) |
| Org-scoped steward (admins_group on org unit) | CRUD within own subtree | **None** |
| Anti-escalation guards (`_assert_within_subtree`, `get_queryset` subtree filter) | Active | Still present but **dead code** for stewards (no steward can reach them) |

The org-scoped delegation model (DATA_TRUST org access design) previously allowed
stewards to self-manage their org's role assignments. This swap silently removes that.

## Options

### Option A — Accept the deviation (no code change)
Stewards lose role-assignment management; only global admins manage scoped roles.
- ✅ Simplest, safest; capability model stays clean (no scoped `platform:*` caps).
- ❌ Breaks documented steward contract; orgs must request global-admin escalations.
- ❌ Dead code left in place (`get_queryset` subtree filter, `_assert_within_subtree`).
- **Requires**: docstring fix on `ScopedRoleViewSet` + deprecation note; frontend check
  that no steward-facing role-management UI silently 403s.

### Option B — Restore steward management (OR-check, MDM/evidence pattern)
Mirror the MDM/evidence fix: allow writes when the user has the capability **OR** the
steward-subtree check passes.

```python
# sketch — permissions.py or view-level check
if user_is_global_admin(user) or has_capability(user, PLATFORM_MANAGE_ACCESS):
    return True
# steward path: only within own subtree, never global roles
return steward_has_scope(user, request, view)   # uses get_steward_org_unit_ids
```

- ✅ Preserves the org-delegation model; anti-escalation guards stay meaningful.
- ⚠️ **Security risk**: re-opens a high-privilege surface; needs the same rigor as
  `_check_write_capability` — steward grants must remain subtree-only, global roles
  (`org_unit=None AND module=None`) must stay admin-only.
- ⚠️ Adds a scoped-role capability (e.g. `platform:manage_access_scoped`) or an explicit
  steward check — must be decided by MA.
- **Requires**: regression tests for (1) steward create/delete within subtree,
  (2) steward create of GLOBAL role → denied, (3) steward write outside subtree → denied,
  (4) global admin unaffected, (5) non-steward user → denied.

### Option C — Middle ground (read-only stewards)
Stewards may **list** assignments in their subtree (view-only), but create/delete remain
global-admin. Least useful of the three, but closes the "dead code" concern partially.

## Recommendation (worker/QA)

Open question for MA. If the org-delegation workflow must survive (it is documented in
`DESIGN_ORG_ACCESS_MODEL.md`), **Option B** with strict anti-escalation tests is the
faithful fix. If product direction is centralizing access management, **Option A** +
docstring fix is acceptable — but the dead `get_queryset`/`_assert_within_subtree` code
should be removed or flagged.

## MA Decision — 2026-08-11: **Option A (Accept/centralize)** ✅

Role-assignment management is now **global-admin only**. Org-scoped stewards do NOT
manage assignments; DD-1 resolves their scoped wildcard roles to view-only capabilities,
so `platform:manage_access` is absent for them — this is by design, not a regression to
fix. The org-delegation model lives on for **data access** (MDM/evidence subtree scoping);
access-control administration is centralized.

Implemented in this closure:
- `ScopedRoleViewSet` docstring rewritten to state the global-admin-only contract
  (no longer advertises the false pre-swap steward CRUD contract).
- Inert steward guards (`get_queryset` subtree filter, `_assert_within_subtree`) are
  **kept and flagged** as defense-in-depth (per DoD: "removed or flagged") with a
  pointer to the class docstring — if `permission_classes` is ever relaxed, stewards
  would still be confined to their own subtree and could never target global roles.
- Regression tests added (`TestScopedRoleViewSetOptionA`, 5 tests): org-scoped
  steward → 403 on GET/POST `/access-control/`; global admin → 200/201; superuser → 200.

## DoD

- [x] MA decision recorded (Option A) with rationale
- [x] Code updated to match decision (docstring + guard flags; guards kept as defense-in-depth)
- [x] Docstring on `ScopedRoleViewSet` reflects actual behavior
- [x] Regression tests (RULE_11): steward-deny cases — org-scoped steward 403 on list+create,
      global admin 200/201, superuser 200 (5 tests, `TestScopedRoleViewSetOptionA`)
- [x] Frontend verified: no steward UI path silently broken (see A3 for capabilities mirror)
- [x] `./manage.sh verify` green — backend 1120 passed + 11 subtests, 0 failures;
      frontend 321/321
