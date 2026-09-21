# GOFSCO Onboarding Runbook (Nibras)

**Brand:** `nibras` · **Tenant data:** Gas and Oil Field Services Company (Kuwait)  
**Apps:** `people`, `my`, `team`  
**Phase:** NSR-1A · 2026-09-16

This is the **authoritative command sequence** to make a GOFSCO Nibras instance usable for staff.  
Do **not** run `people.seed_gofsco` — it is deprecated and refuses to create fabricated GF-00X demo employees.

---

## 0. Environment

| Variable | Required | Notes |
|----------|----------|-------|
| `DJANGO_BRAND` | yes | `nibras` |
| `INSTANCE_NAME` | recommended | e.g. `gofsco` / `nibras` — ADR-0028 instance-gated seeds land in NSR-8; until then keep a **dedicated DB** |
| `EMPLOYEE_DEFAULT_PASSWORD` | for link step | Default password for `emp_<employee_no>` users |
| DB | yes | Dedicated Postgres DB for this instance (do not mix AAST + GOFSCO roots) |

From repo root (dev):

```bash
cd /home/ahmed/ws/carbon/backend
export DJANGO_BRAND=nibras
# export INSTANCE_NAME=gofsco
# export EMPLOYEE_DEFAULT_PASSWORD='…'
```

Use project Python: `/home/ahmed/ws/carbon/.venv/bin/python` (or `../.venv/bin/python` from `backend/`).

---

## 1. Ordered commands

Run in order. All listed seeds are idempotent unless noted.

### 1.1 Org tree

```bash
../.venv/bin/python manage.py seed_gofsco_org
# Optional (NSR-1A):
../.venv/bin/python manage.py seed_gofsco_org --dry-run
```

**Accept:** `OrgUnit` with slug `gofsco`, `parent=None`, code `GOFSCO`.

### 1.2 Correspondence types + workflows (required for My/Team)

```bash
../.venv/bin/python manage.py seed_correspondence
```

**Accept:** ReferenceSet `correspondence_type` includes `leave_request`, `loan_request`, `profile_change`; workflow policies exist for leave.

### 1.3 GOFSCO rules (leave policies, compliance, benefits)

```bash
../.venv/bin/python manage.py seed_gofsco_rules
```

**Accept:** active `LeavePolicy` rows; compliance rules present.

### 1.4 Import real employees (ERP export)

```bash
# Report only:
../.venv/bin/python manage.py import_gofsco_employees --dry-run

# Apply (default xlsx under raw/GOFSCO app/… or --path):
../.venv/bin/python manage.py import_gofsco_employees
# ../.venv/bin/python manage.py import_gofsco_employees --path /path/to/export.xlsx
```

**Import honesty (do not ignore):**

| Field | Status |
|-------|--------|
| employee_no, name, position, cost-center org | Real from Excel |
| `basic_salary` | **Estimated** from job title — **not** production-safe |
| `join_date`, `civil_id`, DOB, gender | Often blank |
| `manager` FK | **Not set by import** |

### 1.5 Optional enrichment

```bash
../.venv/bin/python manage.py apply_gofsco_kuwaitization   # if JSON inputs present
# backfill_salary_estimates — still estimates; does not make payroll safe
```

### 1.6 Leave entitlements

```bash
../.venv/bin/python manage.py propagate_leave_policies
```

**Accept:** `LeaveEntitlement` count > 0 for active employees with `join_date` / policy applicability.  
Employees with `join_date=NULL` may get **no** entitlements until enriched — My Leave will show zeros.

### 1.7 Link users (unlock `/my` and `/team`)

```bash
../.venv/bin/python manage.py link_employee_users --dry-run
../.venv/bin/python manage.py link_employee_users --password "$EMPLOYEE_DEFAULT_PASSWORD"
# QA / Playwright: also refresh existing emp_* passwords to match the default
../.venv/bin/python manage.py link_employee_users --password "$EMPLOYEE_DEFAULT_PASSWORD" --reset-password
```

**Accept:** Users `emp_<employee_no>`; `my:access` via employee_group.
`team:access` only for users who manage others (see §2).
**Note:** without `--reset-password`, existing linked users keep their prior hash — Playwright defaults (`ChangeMe_132`) will fail login.
---

## 2. Manager hierarchy (mandatory for Team inbox)

Import does **not** set `Employee.manager` or `OrgUnit.manager_employee_id`.

Until managers are set:

- `/team` inbox stays empty for most users
- Leave/loan approvals do not route

### HR step (preferred for first cohort)

1. Open People → Employees.
2. For each requester, set **Manager** to the approving employee.
3. Optionally set `OrgUnit.manager_employee_id` for org-level approvers (admin / shell).

### Ops alternative (CSV)

Provide a CSV `employee_no,manager_employee_no` and assign via Django shell (no dedicated command yet):

```bash
../.venv/bin/python manage.py shell <<'PY'
from people.models import Employee
# mapping = {"1399": "1001", ...}
mapping = {}  # fill from CSV
for emp_no, mgr_no in mapping.items():
    emp = Employee.objects.get(employee_no=emp_no)
    emp.manager = Employee.objects.get(employee_no=mgr_no)
    emp.save(update_fields=["manager"])
print("managers set:", len(mapping))
PY
```

Then re-run `link_employee_users` so manager_group / `team:access` refresh.

---

## 3. Salary honesty — payroll freeze until NSR-2A

- Import **estimates** `basic_salary`. Ledger (ADR-0029) may also exist per employee.
- Until **NSR-2A** (payroll compute from compensation ledger, fail-closed without verified lines):

  **Do not run production payroll commits** on estimated basics.

- Safe before NSR-2A: leave request / Team approve, profile, org, policies, linking users.
- After NSR-2A: append verified ledger lines (Pay tab), then compute → validate → commit.

---

## 3b. Attendance & Rotation — not go-live (NSR-6A Path H)

Master chose **Path H** (hide, not thicken OT into payroll this wave).

| Surface | Go-live? | Notes |
|---------|----------|-------|
| People sidebar / PeopleHome | **No** | Attendance + Rotation removed from nav/manifest |
| Certifications | **Yes** | Remains in Workforce nav as simple CRUD |
| `/people/attendance`, `/people/rotation` URLs | Deep-link only | Routes may still resolve; **not promised** for GOFSCO week-1 ops |
| Timesheets → OT / gross | **No** | Do not treat attendance hours as payroll drivers |

Do **not** brief GOFSCO staff on Attendance or Rotation schedules as supported go-live modules. Prefer leave + payroll + certifications workflows documented elsewhere in this runbook / QA manuals.

---

## 4. Acceptance checklist (ORM / SQL)

Run after the sequence (adjust brand/DB):

```bash
../.venv/bin/python manage.py shell <<'PY'
from django.contrib.auth import get_user_model
from mdm.models import OrgUnit
from people.models import Employee, LeaveEntitlement, LeavePolicy
from correspondence.models import WorkflowPolicy

User = get_user_model()
print("org_roots", OrgUnit.objects.filter(parent=None).count())
print("gofsco_root", OrgUnit.objects.filter(slug="gofsco").exists())
print("employees", Employee.objects.filter(is_active=True).count())
print("leave_policies", LeavePolicy.objects.filter(status="active").count())
print("entitlements", LeaveEntitlement.objects.count())
print("workflows", WorkflowPolicy.objects.count())
print("emp_users", User.objects.filter(username__startswith="emp_").count())
print("with_manager", Employee.objects.exclude(manager=None).count())
PY
```

**Go / no-go for ESS (My/Team leave):**

| Check | Required |
|-------|----------|
| `gofsco_root` True | yes |
| `workflows` > 0 | yes |
| `leave_policies` > 0 | yes |
| `entitlements` > 0 for pilot cohort | yes |
| `emp_users` > 0 | yes |
| `with_manager` > 0 for pilot | yes |
| Production payroll | **no** until NSR-2A + real ledger |

---

## 5. Related docs

- Manual QA: `docs/QA-MANUAL-PEOPLE-MY-TEAM.md` (uses linked `emp_*` users — not GF-00X)
- Screen / payroll SoT: NSR-2A/2B in `TASKS.md`
- Single-root / instance gate: NSR-8 (ADR-0028)
