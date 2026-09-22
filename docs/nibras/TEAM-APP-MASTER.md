# TEAM App Master (Nibras) — Approvals + Directory + Who's Out

**Status:** COMPLETE (T1–T7 + Directory/Leave) · **Brand:** nibras · **Refreshed:** 2026-09-22  
**Scope:** Manager Team app — inbox/detail, Team Directory, Who's Out (team leave).  
**Rules:** ADR-0014 CBAC · RULE_21 consent · AI toolkit (`FilteredDataGrid`, `SearchSelect`, `SystemDialog`, `ConfirmDialog`) · **no firefight / ad-hoc Card action bars / bandit Archive CTAs**.  
**Credentials (dev):** `emp_*` / `mozafNibrasPa_132` · platform su `ahmed` / `AdminPa_132`.

---

## 1. Product truth (post 2026-09-22)

| Fact | Meaning |
|---|---|
| Inbox = `GET correspondence/inbox/` where `user.id ∈ current_approver_ids` | Correct; empty when you are not the current approver |
| History = `GET correspondence/history/` where you acted (approve/reject/send-back/ack/review) | Any type / any outcome; detail still readable for past actors |
| Manager routing | `Employee.manager.user_id`, else `OrgUnit.manager_employee_id` (parent walk) |
| Directory / Who's Out | `GET people/me/direct-reports/` · `GET people/me/team-leave/?year=&month=` — manager-scoped, needs `team:access` + active employee profile |
| ESS without routable manager | HTTP 400 `no_manager` / `manager_no_user` (leave/loan/attendance) — no silent orphans |
| Ops commands | `assign_employee_managers` (`--csv` preferred; `--org-leads` DEV only) · `reroute_orphaned_correspondence` · `link_employee_users` |
| nibras_dev (applied) | ~522 with managers · orphans rerouted · prove: `emp_1067` → `emp_1712` → approved |

`--org-leads` is an explicit DEV heuristic, not production hierarchy. Prefer HR CSV.

Superuser without `employee_profile` cannot call `me/*` manager reads — expected; prove with a linked manager (`emp_1712`).

---

## 2. Surfaces

| Route | Component | Toolkit shell |
|---|---|---|
| `/team` | `TeamInbox.jsx` | **FilteredDataGrid** — search/filters; **row click = highlight only**; **eye** → `/team/:id` |
| `/team/history` | `TeamHistory.jsx` | **FilteredDataGrid** of your decisions (any type/outcome); eye → detail |
| `/team/:id` | `TeamRequestDetail.jsx` | Summary/stepper/graph/timeline + **SystemDialog / ConfirmDialog** for act |
| `/team/directory` | `TeamDirectory.jsx` | **FilteredDataGrid** of direct reports |
| `/team/leave` | `TeamLeave.jsx` | **FilteredDataGrid** + month pager (overlap leave) |
| API | `api/team.js` | inbox/act + `fetchDirectReports` / `fetchTeamLeave` |

Capability: `team:access` (+ `correspondence:act` via `manager_group`). Static routes `/team/directory` and `/team/leave` are registered **before** `/team/:id`.

---

## 3. Architecture

```
ESS submit (leave / loan / attendance)
        ↓  manager_routing_block_response
Correspondence FSM submit
        ↓  resolve_step_approvers(role=manager)
        → line manager.user  OR  OrgUnit.manager_employee → user
        ↓
current_approver_ids = […]
        ↓
GET /correspondence/inbox/  →  /team (FilteredDataGrid)
        ↓ row
/team/:id  →  SystemDialog act (intent-aware) → FSM

Employee.manager = me
        ↓
GET /people/me/direct-reports/  →  /team/directory
GET /people/me/team-leave/      →  /team/leave  (submitted|approved overlap month)
```

---

## 4. Phase board

### Done

| # | Work |
|---|---|
| A1–A4 | Commands + link + reroute + tests |
| B1–B4 | Inbox FilteredDataGrid + i18n + empty/orphan + vitest smoke |
| C1–C3 | People manager filter/bulk + OrgUnit manager editor |
| C3b | Org-unit manager routing fallback + ESS guard parity |
| D1 | API prove leave → manager approve (Playwright spec ready; browser install local) |
| D2 | ESS 400 without manager (unit-tested) |
| T1–T7 | Detail act toolkit, inbox polish, CSV, apiFetch 429, shared OU helper |
| T8 | Team Directory — `DirectReportsView` + `/team/directory` FilteredDataGrid |
| T9 | Who's Out — `TeamLeaveView` + `/team/leave` month FilteredDataGrid |
| T10 | Team History — `GET correspondence/history/` + `/team/history`; past-actor detail view |

### Remaining

None in this scope. Do not bulk beyond History without a new master slice.

---

## 5. Non-goals / anti-patterns

- Filling inbox via `any_admin` policy bypass.
- Inventing GOFSCO reporting trees without CSV.
- Inline Card action bars, raw MUI Dialog/Table on Team primary surfaces.
- Showing Archive to managers (FSM: requester or `correspondence:admin` only).
- HR `people:view` for Directory — use manager-scoped `me/direct-reports` only.
- Pulse self-heal / loan agent hosts (other masters).

---

## 6. Acceptance

```text
# Inbox
Login emp_1712 / mozafNibrasPa_132 → /team lists pending for that user
# Act
Open item → primary intent button → SystemDialog → success → back to inbox
Reject/Send back require comment (ConfirmDialog / SystemDialog validation)
# Directory
emp_1712 → /team/directory lists employees with manager=that profile
# Who's Out
emp_1712 → /team/leave shows submitted|approved leave overlapping selected month
# Guard
Employee without manager+OU manager → leave POST 400 error_kind=no_manager
```

---

## 7. Execution order

1. T1 + T2 (detail act toolkit) — done  
2. T3 + T4 (inbox polish + tests) — done  
3. T5–T7 durability — done  
4. T8 + T9 Directory + Who's Out — done  
