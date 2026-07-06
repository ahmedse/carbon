# Design — Organizational Model & Access Control (AASTMT)

> **Type:** Detailed design specification for the org structure, access control, and portal strategy.
> **Pairs with:** [DESIGN_DATA_TRUST_CORE.md](DESIGN_DATA_TRUST_CORE.md), [STRATEGY_DATA_TRUST_PLATFORM.md](STRATEGY_DATA_TRUST_PLATFORM.md).
> **Status:** Approved direction. Implemented incrementally via the phased plan.

---

## 1. Decision summary (locked)

1. **Org structure = MDM master data**, not code. The `OrgUnit` self-referencing tree (in `mdm/`) is the single organizational anchor. Re-orgs are data edits, never migrations.
2. **One role-adaptive portal — NOT a separate admin console.** Admin/steward capabilities are **role-gated sections** of the same app. Lighter than Ataccama; single auth, single deploy.
3. **Stewardship model:** whoever owns an OrgUnit subtree manages roles/data **within that subtree**. A college steward manages their departments; a department data-owner enters their own data.
4. **Access is org-scoped:** `OrgUnit` links to `Module` (and therefore to `DataTable`/`DataRow`). RBAC and querysets enforce org isolation.

---

## 2. AASTMT organizational model

AASTMT is a multi-campus maritime/technical university. Modeled as an editable `OrgUnit` tree:

```
AAST (university)
├── Abu Qir Campus (campus)          ← Alexandria, main
│   ├── College of Engineering & Technology (college)
│   ├── College of Computing & IT (college)
│   └── Operations & Facilities (division)
│       └── Transportation / Fleet (department)   ← the "gas bills" scenario unit
├── Heliopolis / Cairo Campus (campus)
├── Smart Village (campus)
└── … (Alamein, Aswan, South Valley, Port Said …)
```

- **Depth & shape are arbitrary** — the tree supports university → campus → college → department → team, or any subset.
- `OrgUnit.org_type` gains a **`campus`** value (added this phase). Full set: university, campus, college, department, division, team, facility, other.
- **We seed a minimal realistic slice** (Abu Qir + a couple of colleges + Operations/Transportation) and expand as data. We do **not** hardcode the full AASTMT chart.

---

## 3. Data model — how org links to data

```
OrgUnit (tree)
   │  1─* (Module.org_unit, nullable FK)
   ▼
Module (scope 1/2/3, owned by an OrgUnit)
   │  1─*
   ▼
DataTable  →  DataField / DataRow      (the "Gas Bills" table + its rows)
```

- **`Module.org_unit`** (new, nullable FK → `mdm.OrgUnit`): a module (a data-collection area within a GHG scope) belongs to an org unit. e.g. *"Transportation – Fleet Fuel" (Scope 1)* is owned by *Transportation / Fleet*.
- `DataTable` inherits its org via `module.org_unit`. No separate FK on DataTable this phase (kept simple).
- `DataRow` inherits org via `data_table.module.org_unit`.
- `ScopedRole` (already has `org_unit` + `module`): a user's access is granted at **org-unit** scope (preferred) or **module** scope.

**Why `Module.org_unit` and not `DataTable.org_unit`:** the module is the natural ownership + navigation unit (the sidebar already groups by module/scope), and it keeps the FK count minimal. Finer-grained table ownership can be added later if needed.

---

## 4. Access-control model (org-scoped RBAC)

### Roles (Django groups)
- `admins_group` — global admin (sees everything).
- `dataowners_group` — can CRUD data rows within their scope.
- `auditors_group` — read across their scope.
- Superusers bypass all checks.

### Scope resolution
A `ScopedRole` grants a role at one of:
- **Global** (`org_unit=None, module=None`) — applies everywhere.
- **Org unit** (`org_unit=X`) — applies to X **and all its descendants** (subtree). A college steward covers its departments.
- **Module** (`module=Y`) — applies to that single module.

### Enforcement (two layers, both required)
1. **`HasScopedRole` permission** — grants a request if: superuser, OR global role, OR module-level role, OR the target module's `org_unit` is within the user's allowed org subtree (for the required role).
2. **Queryset filtering** — `Module`, `DataTable`, `DataRow` querysets return only rows whose module is in the user's **allowed module set** = (module-scoped roles) ∪ (modules whose `org_unit` ∈ user's allowed org subtree). Global/admin users get everything.

### Org subtree expansion
`get_allowed_org_unit_ids(user, roles)` = the org units the user has the role on, **plus all descendants** (breadth-first walk of `OrgUnit.parent`). This is what makes stewardship cascade down the tree.

**Result:** the Transportation data-owner sees ONLY the Transportation module + its Gas Bills table + its rows. Engineering's electricity data is invisible to them. AAST-level admins see all.

---

## 5. Portal strategy (one app, role-adaptive)

**No separate admin console.** The existing React app renders different sections by role:

| Role | Sees |
|---|---|
| Department **data-owner** | Their unit's modules → tables → data-entry grid + relevant dashboards. Nothing else. |
| Campus/College **steward** | The above for their subtree **+** org/user management scoped to their subtree, schema for their tables. |
| **Super-admin** | Everything: full OrgUnit tree editor, all schemas, catalog, DQ, user/role assignment. |

- Server-side filtering does most of the work: because `ModuleViewSet` returns only allowed modules, the **sidebar auto-scopes** with minimal frontend change.
- Admin sections reuse the existing `AdminRoute` + role-gated sidebar pattern — extended, not forked.

---

## 6. Phasing

- **Phase A (backend — this next RUN):** `Module.org_unit` FK, org-scoped RBAC (permission + querysets + subtree expansion), `campus` org type, and a seed command building the AASTMT slice + the Transportation Gas Bills scenario + a department data-owner user. Prove isolation over HTTP.
- **Phase B (frontend):** org context in `AuthContext`; sidebar/nav naturally scoped by the server-filtered module list; org-unit + user-role admin screens (steward-scoped).
- **Phase C:** stewardship workflows, org-based governance/lineage in the catalog, dashboards scoped by org unit.

---

## 7. Non-goals (this phase)
- No separate admin-console application.
- No `DataTable.org_unit` (org flows through `Module`).
- No frontend changes in Phase A (server filtering carries the sidebar).
- No AI/Pulse, no Celery.
