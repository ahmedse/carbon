# SCOREBOARD — SIM-QA-CHAT-AGENT

Updated: 2026-09-21 · Runner: real browser + API · Lead: Nibras · Multi-persona

| Wave | Executed | PASS | FAIL | BLOCKED | Mean (PASS) | Status |
|------|----------|------|------|---------|-------------|--------|
| A Shell | 8 | 6 | 1 | 0* | ~4.0 | DONE (findings open) |
| B1 Nibras | **19** | **16** | **0** | **0** | ~4.5 | **HOLD COMPLETE** (Agent leave **cleared** by proper wave) |
| B2 Emissions | 0 | 0 | 0 | pack | — | QUEUED |
| B3 GradeVance | 0 | 0 | 0 | 0 | — | QUEUED (EduOS ACK) |
| C Intelligence | 0 | 0 | 0 | 0 | — | QUEUED |
| C Nibras-Processes | **5** | **5** | **0** | **0** | — | **PASS** 2026-09-21 — host 5/5 · agent 5/5 · chat 5/5 · [SESSION-20260921-101554](./logs/SESSION-20260921-101554-NIBRAS-PROCESSES.md) |
| C Nibras-Processes deep | **5** | **5** | **0** | **0** | — | **PASS** 2026-09-21 — edge · consent · [SESSION-20260921-111830](./logs/SESSION-20260921-111830-NIBRAS-PROCESSES.md) |
| C Nibras-Processes proper | **5** | **5** | **0** | **0** | — | **PASS** 2026-09-21 — catalog parity · honest GOSI filing · deep [SESSION-20260921-114137](./logs/SESSION-20260921-114137-NIBRAS-PROCESSES.md) · operator Chat·Plan·Run [SESSION-20260921-114311](./logs/SESSION-20260921-114311-NIBRAS-OPERATOR.md) · canvas `nibras-processes-e2e-sim` · ADR-0044 |
| C Nibras-Attendance | **6** | **6** | **0** | **0** | — | **PASS** 2026-09-21 — 6th process `attendance.permission.lifecycle` · host POST/PATCH · deep [SESSION-20260921-120517](./logs/SESSION-20260921-120517-NIBRAS-PROCESSES.md) · operator [SESSION-20260921-120709](./logs/SESSION-20260921-120709-NIBRAS-OPERATOR.md) |
| C Nibras-NPS-1 SoD | **4** | **4** | **0** | **0** | — | **PASS** 2026-09-21 — `people.governance.sod` host_gate · payroll/GOSI/onboard/attendance same-actor 403 · [SESSION-20260921-124408](./logs/SESSION-20260921-124408-NIBRAS-PROCESSES.md) · ADR-0045 |
| C Nibras-NPS-2 Review→HR | **27** | **27** | **0** | **0** | — | **PASS** 2026-09-21 — `ai.governance.review_authority` · leave→`correspondence:act` · loan→finance · admin reviews→`people:manage` · operator refused · `test_review_authority.py` + inbox |
| C Nibras-NPS-3 Att ESS | — | — | — | — | — | **SHIPPED** 2026-09-21 — `/me/attendance-permissions` + corr manager · honesty `correspondence` · `test_attendance_ess.py` · admin PATCH SoD fallback |
| C Nibras-6/6 Regression | **6** | **6** | **0** | **0** | — | **PASS** 2026-09-21 — deep [SESSION-20260921-132047](./logs/SESSION-20260921-132047-NIBRAS-PROCESSES.md) · operator [SESSION-20260921-132248](./logs/SESSION-20260921-132248-NIBRAS-OPERATOR.md) · NPS-1/2/3 + My Attendance UI + me POST leave/loan |
| C Nibras-MyAttendance UI | — | — | — | — | — | **SHIPPED** 2026-09-21 — `/my/attendance` · SystemDialog ESS · vitest smoke · mirrors My Leave |
| D Staging | 0 | 0 | 0 | 0 | — | QUEUED |

## B1 highlight — leave E2E + Agent theatre + cast

| Step | Persona | Result |
|------|---------|--------|
| Submit | `emp_1001` | **CRS-2026-0041** annual Nov 16–17 · submitted |
| Approve | `emp_1399` | **approved** · inbox cleared of 0041 |
| Verify UI | `emp_1001` | My Leave shows **Approved** · used 8 / pending 6 / rem 16 |
| Agent leave | `emp_1001` / `emp_1067` | **PASS** (proper wave) — coerce `submit_my_leave` · operator consent · [SESSION-20260921-114311](./logs/SESSION-20260921-114311-NIBRAS-OPERATOR.md) (supersedes prior PARTIAL entity miss) |
| Payslip Chat | `emp_1001` | CBAC / honest deny · API payslips `[]` · **PASS** |
| Cast expand | `emp_*` ×536 | Shared QA password reset · 7/7 token smoke **200** |

Cast: [logs/CAST-NIBRAS.md](./logs/CAST-NIBRAS.md) · Evidence: [WAVE-B1-NIBRAS-EVIDENCE.md](./WAVE-B1-NIBRAS-EVIDENCE.md)
