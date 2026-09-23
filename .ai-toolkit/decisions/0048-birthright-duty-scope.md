# ADR-0048 — Birthright access: duty × org scope × dates

- **Status:** Accepted
- **Date:** 2026-09-23
- **Area:** security · accounts CBAC · every domain app
- **Extends:** ADR-0015 (brand-scoped groups), ADR-0040 (module ≠ dataset),
  ADR-0045 (host CBAC is Plane A; Pulse YAML is not an ACL)

## Decision

Every domain app, now and later, grants access through one ledger row:

**assignment = `{domain}:{duty}` × one anchor org unit × valid_from/valid_to × provenance**

| Field | Rule |
|---|---|
| Duty | Domain-prefixed bundle of `{domain}:{action}` capabilities. The manifest role key, the Django group, and the Role Registry row are the same id. |
| Scope | One anchor `OrgUnit`, or empty for a global duty. Descendants are computed at read time. |
| Dates | Open when empty. An acting grant ends on `valid_to`. |
| Provenance | `birthright` is rewritten by the engine. `exception` is an explicit admin grant and is left alone. |

Position title text and org-unit name are not inputs.

### What produces birthright

| Input | Duty | Scope |
|---|---|---|
| Active employee | `platform:employee` (`employee_group` → `my:access`) | Global, plus the home org unit |
| Direct reports, or `OrgUnit.manager_employee_id` | `platform:manager` (`manager_group` → `team:access`) | Each unit they run |
| `DutyProfile` row for the position code | The profile's duty id | `home_org`, `managed_org`, or `global` |

A transfer, a lost report, a manager change, deactivation, or a position-code change runs `recalculate_birthright`. It inserts and deactivates `birthright` rows only. Each change writes `RoleAssignmentAuditLog` with `extra.provenance=birthright`.

`has_capability` answers the verb, using live rows (`ScopedRole.objects.live()`). `visible_org_ids(user, duty)` is the only tree walk for “where”. A domain endpoint that checks the verb and skips the subtree is wrong.

`Module` stays the data-product axis. Birthright never fills `module`.

### Naming

| Object | Pattern | Current group until aliases are removed |
|---|---|---|
| Capability | `{domain}:{action}` | unchanged |
| Duty | `{domain}:{duty}` | `people:lead` → `people_lead`, `platform:employee` → `employee_group`, `platform:manager` → `manager_group` |
| Platform baselines | `platform:{duty}` | employee, manager, admin |
| Pulse / correspondence | own domain | `ai:operator`, `correspondence:finance` |

A new app adds a manifest duty, a `DUTY_GROUP` alias, and `GROUP_CAPABILITIES`. The engine does not import the app. Pulse reviews resolve to a host duty (ADR-0045). Chat does not gain a host write. Field policies stay column masks.

### Admin module (target)

**Access:** Accounts, Duties, Assignments (this ledger), Position profiles, Org units (saving a manager or parent runs the engine).

**Trust:** Field policies, audit, assurance.

**Apps:** Registered apps. Role Registry must equal the duty catalog.

**Platform:** Config, system logs.

Today Access Control is a manual user/group/org dialog with module forced empty. That dialog creates `exception` rows. The registry still shows manifest keys (`people:admin`) that are not the granting group (`people_lead`). Unifying those names is the next slice. This ADR does not rename production groups.

### Sequence

1. Ledger fields, engine, `visible_org_ids`, employee/manager/position sync. **This change.** Existing rows stay `exception`, so the first recalc does not strip production grants.
2. Call `visible_org_ids` from People, Carbon, catalog, and GradeVance querysets. Move remaining `is_active=True` checks onto `.live()`.
3. Alias-rename groups to `{domain}:{duty}` and make Role Registry read that catalog.
4. Admin screens: Assignments, position profiles, org-unit save → engine.
5. SoD refusal on the grant itself, recorded on the audit row.

## Consequences

- `provision_employee_user` no longer inserts ScopedRoles itself. It calls `sync_employee_access`.
- Employee patch and soft-delete recalculate the person and both managers (previous and current).
- An expired `valid_to` drops the verb from `get_user_capabilities` and drops the org from `get_allowed_org_unit_ids`.
- A `DutyProfile` for position code `HR-DIR` / duty `people:lead` / scope `home_org` grants People for that org and removes it when the position code changes.
