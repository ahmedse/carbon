# Nibras fixtures — Team manager hierarchy

## `employee_managers.csv`

Columns: `employee_no,manager_employee_no`

Snapshot of **nibras_dev** reporting lines after the 2026-09-22 org-lead seed
(522 rows). Prefer this over `--org-leads` when re-applying:

```bash
cd backend
python manage.py assign_employee_managers --csv ../docs/nibras/fixtures/employee_managers.csv
python manage.py link_employee_users --password mozafNibrasPa_132
python manage.py reroute_orphaned_correspondence
```

Replace this file with an HR-authoritative export when available. Do **not**
re-run `--org-leads` on a production-like cell without Master approval.
