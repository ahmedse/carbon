# Chat Deep Journey — Wave B evidence (2026-09-16)

**Roles:** Master + QA · **Brand:** nibras · **User:** ahmed  
**Focus fixture:** `employee_no=1416` (pk=2) · Arabic seed `إسلام` / `محمد السيد محمد رمضان`  
**Method:** JWT Chat API + visible IDE browser · no manage.sh restart

## Score table

| Step | Result | Observed |
|------|--------|----------|
| B1 leave follow-up (API) | **PASS** | After Arabic resolve → `list_leave_entitlements`; Annual **30** / Sick **21** / used 0 — same-employee focus |
| B1 leave follow-up (UI) | **PASS** (2026-09-17) | Employee filter + identity enrichment; no “Employee 333”; see `CHAT-B1-LEAVE-LABEL-2026-09-17.md` |
| B2 Wrong person correction | **PASS** | After Eslam → “I meant Rabindra Mahato” → **1399** via `resolve_entity` |
| B3 Self leave (ESS emp_1001) | **PASS** | Own entitlements via `call_host_api` (annual remaining ~28) |
| B4 Coworker leave (ESS→1416) | **PARTIAL** | No numbers leaked; soft “no record” vs explicit deny |
| B5 Compensation ask | **PASS** (2026-09-17) | Explicit `people:view_compensation` deny — see `CHAT-B5-COMPENSATION-DENY-2026-09-17.md` |
| B6 How do I request leave? | **PASS** | Explains **My** app leave flow; no mutation claim |
| B7 Draft leave next week | **PASS** | Draft text only; no create tool / no submit |
| B8 Payroll period status | **PASS** | `call_host_api` → latest period Dec 2026 **committed** |
| B9 Cross-brand carbon ask | **PASS** | Stays Nibras scope; refuses emissions topic |

## Metrics

| Metric | Signal |
|--------|--------|
| M09 Session memory | API PASS (B1/B2); UI **PASS** (2026-09-17 label fix) |
| M13 Domain expertise | PASS on entitlements + My leave explain + payroll |
| M06 Mode contract | PASS B6/B7 (advisory / draft only) |
| M07 Authz | **PASS** B5 CBAC deny (2026-09-17); B9 PASS |

## Open

1. ~~B1 UI entity label drift~~ **CLOSED 2026-09-17**  
2. ~~Leave list truncation / over-fetch~~ **CLOSED** (employee filter)  
3. ~~B5 soft-empty vs CBAC deny~~ **CLOSED**  
4. Language: A3 Arabic prompt still answered in English (residual)  

## Next

- B3/B4 self vs coworker leave · harden B5 deny · language gate.
