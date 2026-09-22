# Nibras domain pack — governed People & Payroll processes

**Brand:** Nibras (GOFSCO HRMS) · **Live Agent catalog SSOT:**  
`backend/ai/engine/instances/nibras/instance.yaml`  
**This pack:** capabilities + process YAMLs + `tools:` parity with instance.

## Process inventory (vacation = leave)

| What people call it | Process id | Primary Agent tools |
|---------------------|------------|---------------------|
| Request vacation / leave | `leave.request.lifecycle` | `submit_my_leave`, `get_my_leave_balance` |
| Request loan | `loan.request.lifecycle` | `submit_my_loan`, `list_my_loans` |
| Hire / onboard | `employee.onboarding.lifecycle` | `create_employee`, `update_employee` |
| Run payroll | `payroll.run.lifecycle` | `compute_payroll_run`, `validate_payroll_run`, `commit_payroll_run` |
| GOSI / WPS SIF file | `gosi_wps.sif.lifecycle` | `generate_gosi_wps_sif`, `validate_gosi_wps_sif`, `submit_gosi_wps_sif` |
| Short-hours attendance permission | `attendance.permission.lifecycle` | `submit_my_attendance_permission`, `list_my_attendance_permissions` |

There is **no** separate `vacation.*` process — use leave.

## Security planes (ADR-0045 / RULE_34)

| Plane | What | Today |
|-------|------|-------|
| **Host** | CBAC + org scope + Correspondence FSM + `people.governance.sod` | Leave/loan/**attendance ESS** = Correspondence; payroll/GOSI/onboard admin irreversibles = **host_gate** (NPS-1). Attendance admin PATCH remains ops fallback + SoD. |
| **Pulse dials** | YAML `human_only` / SoD / `refuse_if` + RULE_21 consent | All six processes |
| **Pulse review authority** | Inbox `required_authority` | Nibras `*.review` → HR CBAC via `ai.governance.review_authority` (NPS-2); leave/attendance → `correspondence:act` |

Irreversibles refuse same-actor on the **DRF/service path** (not Agent-only). Honesty CI:
`ai/tests/test_nibras_process_security_planes.py` · `ai/tests/test_review_authority.py`.

## Dual catalog (ADR-0044)

- **instance.yaml** — every Agent-callable `call_host_api` name + path
- **api_catalog.yaml `tools:`** — must be ⊆ instance names (CI: `test_nibras_catalog_parity.py`)
- **api_catalog.yaml `capabilities:`** — governance contracts → `capability_registry.py`

## Seed / sim

```bash
cd backend && ../.venv/bin/python manage.py seed_nibras_processes
../.venv/bin/python manage.py simulate_nibras_pulse_processes
../.venv/bin/python manage.py simulate_nibras_operator_processes
```
