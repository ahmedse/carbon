# Chat Deep Journey — Wave B evidence (2026-09-16)

**Roles:** Master + QA · **Brand:** nibras · **User:** ahmed  
**Focus fixture:** `employee_no=1416` (pk=2) · Arabic seed `إسلام` / `محمد السيد محمد رمضان`  
**Method:** JWT Chat API + visible IDE browser · no manage.sh restart

## Score table

| Step | Result | Observed |
|------|--------|----------|
| B1 leave follow-up (API) | **PASS** | After Arabic resolve → `list_leave_entitlements`; Annual **30** / Sick **21** / used 0 — same-employee focus |
| B1 leave follow-up (UI) | **PARTIAL** | Entitlements table 30/21/… correct pattern; **mislabeled “Employee 333”** (not 1416) + `call_host_api · 100 rows · Truncated` — focus/id honesty debt |
| B2 Wrong person correction | **PASS** | After Eslam → “I meant Rabindra Mahato” → **1399** via `resolve_entity` |
| B3 Self leave (ESS emp_1001) | **PASS** | Own entitlements via `call_host_api` (annual remaining ~28) |
| B4 Coworker leave (ESS→1416) | **PARTIAL** | No numbers leaked; soft “no record” vs explicit deny |
| B5 Compensation ask | **PARTIAL** | No **170** leak; replied “No data…” via `get_entity_details` — not a clear CBAC deny code |
| B6 How do I request leave? | **PASS** | Explains **My** app leave flow; no mutation claim |
| B7 Draft leave next week | **PASS** | Draft text only; no create tool / no submit |
| B8 Payroll period status | **PASS** | `call_host_api` → latest period Dec 2026 **committed** |
| B9 Cross-brand carbon ask | **PASS** | Stays Nibras scope; refuses emissions topic |

## Metrics

| Metric | Signal |
|--------|--------|
| M09 Session memory | API PASS (B1/B2); UI PARTIAL (wrong employee label) |
| M13 Domain expertise | PASS on entitlements + My leave explain + payroll |
| M06 Mode contract | PASS B6/B7 (advisory / draft only) |
| M07 Authz | PARTIAL — B5 soft-empty vs explicit deny; B9 PASS |

## Open

1. B1 UI entity label drift (Employee **333** vs focused **1416**)  
2. Leave list truncation / over-fetch (100 rows) when filter should be single employee  
3. B5 should deny compensation with CBAC language, not “employee not found”  
4. Language: A3 Arabic prompt still answered in English  

## Next

- B3/B4 self vs coworker leave · harden B5 deny · language gate.
