# WAVE B1 — Nibras-only evidence (real browser)

**Seat:** Nibras · **Env:** local brand `nibras` / DB `nibras_dev`  
**Stack:** STACK-HOLD SIM-20260919-N3 · `./manage.sh brand nibras` + restart  
**Personas:** `ahmed` ADMIN · `emp_1001` employee · `emp_1399` manager — see `logs/CAST-NIBRAS.md`  
**Date:** 2026-09-19  
**Fix policy:** evidence only unless systemic Nibras-owned fix with regression test

---

## Environment unlock

| Check | Result |
|-------|--------|
| Brand | **Nibras · Enterprise Business Platform** |
| Nav | **People / My / Team** present (EduOS apps gone) |
| Data | 537 employees, 547 users in `nibras_dev` |
| Pulse | Chat + Agent Plan·Run·Canvas·Output available |

---

## Scenarios

### N-SHELL-01 — Brand + domain apps
Binary: **PASS** · UX:5 DEP:5 · Notes: People/My/Team visible; footer © Nibras.

### N-HR-UI-01 — Employees directory load
Steps: Navigate `/people/employees`.  
Binary: **PASS** (re-verify after systemic fix)  
Scores: UX:4 DEP:5 REG:5 · mean:~4.7  
**Before:** UI timed out → “0 of 0 employees”; API returned all 537 in ~9s ignoring `page_size`.  
**After (NB-P0-EMP-PAGE):** UI shows **537 of 537 employees** / **1–25 of 537**; API `?page_size=5` → 5 rows in **~0.3s**, default page 100 in **~0.6s**.  
**Systemic fix landed:**
- `EmployeeListCreateView`: `select_related` + `defer('photo')` + **always-on** `page`/`page_size` (default 100, max 200)
- FE `fetchEmployees`: walks pages under cap (never one unbounded call)
- Tests: `test_employee_list_query_budget_is_bounded`, `test_employee_list_honors_page_size`

### N-PY-AG-01 — Agent payroll theatre task on Nibras
Steps: Agent mode shows approved task “Theatre T1: payroll run_id 18… stage Finance human review… board pack”. Segments Plan·Run·Canvas·Output; Run active; 0/6 steps.  
Binary: **PASS** (surface) · UX:4 DEP:4 C21:4 (approved, run controls)  
Notes: Nibras payroll Agent cockpit usable; Canvas not re-scored this wave.

### N-CHAT-01 — Arabic Chat grounding (pre-existing thread)
Observed Chat history: user `اعطني اخر موظف تم تسجيله` → Pulse returned **Mohammed Nannu Miah Aminul / emp 1049** with table (employment type, created_at).  
Binary: **PASS** · INT:4 DEP:5 MEM:n/a · Notes: Live People grounding works in Chat when not blocked by list timeout.

### N-CHAT-02 — Leave balance follow-up
Steps: Chat “What is my leave balance?” as `ahmed` ADMIN.  
Binary: **PASS** (honest self-scope) · INT:4 DEP:5 MEM:4  
**Evidence:** Pulse: “No leave balance… no active employee profile linked to your account” + caveat; sources `call_host_api · 0 rows`.  
Notes: Correct for admin without Employee link — not a fabricated balance. Full employee-self path needs linked persona (queue as N-CHAT-02b).

### N-MY-01 — My Leave surface
Steps: `/my/leave`.  
Binary: **PASS** (surface) · UX:3 DEP:3  
Notes: Page loads (Request Leave / balances / history). API returns permission denied for `ahmed` (no employee self-scope) — consistent with N-CHAT-02.

### N-TM-01 — Team Approvals Inbox
Steps: `/team`.  
Binary: **PASS** · UX:4 DEP:5  
Notes: Approvals Inbox lists CRS-2026-0022 (memo), loan requests from emp_1001, Submitted status + dates.

### N-BRAND-01 — Cross-brand banner leak
Binary: **PASS** (re-verify after fix) · UX:4 REG:5  
**Before:** On Nibras, preview banner said **“EduOS and GradeVance are under active development”**.  
**After:** Banner reads **“Nibras is under active development…”** (brand-aware `{{platform}}` + `DEV_BANNER_PLATFORM`). EduOS keeps `devBannerPlatform: 'EduOS and GradeVance'`.

### N-MY-01b — My Leave as employee (`emp_1001`)
Steps: Login `emp_1001` → `/my/leave`.  
Binary: **PASS** · UX:5 DEP:5  
**Evidence:** Annual Leave remaining **16.00** (entitled 30 / used 6 / pending 8); sick rem 17; request history CRS-2026-0038… Nav shows **My** only (no People/Team) — correct scope.

### N-LV-01 — Chat leave balance as employee (`emp_1001`)
Steps: Pulse Chat “What is my leave balance?”  
Binary: **PASS** · INT:5 DEP:5 MEM:4  
**Evidence:** Table Annual rem **16**, Sick **17**, Emergency **3**, … Sources `call_host_api · 6 rows` · gpt-4o ~8.5s. Matches My Leave UI.

### N-CBAC-01 — Compensation deny as employee (`emp_1001`)
Observed prior thread: “What is my salary?” / “What is Abrar's salary?” → **Not authorized** (`people:view_compensation`).  
Binary: **PASS** · REF:5 DEP:5 · Notes: Authorization deny, not empty payroll.

### N-TM-01b — Team Approvals as manager (`emp_1399`)
Steps: Login `emp_1399` → `/team`.  
Binary: **PASS** · UX:5 DEP:5  
**Evidence:** Approvals Inbox lists leave requests from **emp_1001** (CRS-2026-0038 annual, 0037, 0036, sick 0035…). Nav **Team** (no People admin).

### N-CHAT-03 — Admin leave lookup for named employee (ahmed)
Prompt: annual leave rem for emp 1001 Wellie…  
Binary: **PARTIAL / FINDING** · INT:3 DEP:2  
**Evidence:** `resolve_entity` found Wellie; reply did **not** fetch leave balance tool (“please ensure the relevant data is retrieved”). Log as Pulse INT finding — not Nibras data miss.

### N-LV-02 — Employee submits annual leave (`emp_1001`)
Steps: `POST /people/me/leave/` annual 2026-11-16→2026-11-17, 2 days, note SIM-QA.  
Binary: **PASS** · UX:n/a C21:4 DEP:5 REG:5  
**Evidence:** HTTP **201** · `CRS-2026-0041` status **submitted** · approver ids include manager (61 / emp_1399). Balance after submit: pending **6→8**, remaining **18→16**.

### N-LV-03 — Manager approves leave (`emp_1399`)
Steps: `POST /correspondence/44/approve/` as emp_1399 (+ UI inbox check).  
Binary: **PASS** · UX:4 C21:5 DEP:5 REG:5  
**Evidence:** HTTP **200** · CRS-2026-0041 **approved**. Balance after: used **6→8**, pending **8→6**, remaining **16**. LeaveRecord id=27 status **approved**. Team inbox no longer lists 0041 (cleared). Also approved prior CRS-2026-0038 in same session (pending drop).

### N-LV-04 — Employee sees approved + balances (`emp_1001` UI)
Steps: Login emp_1001 → `/my/leave`.  
Binary: **PASS** · UX:5 DEP:5  
**Evidence:** History row **CRS-2026-0041** Annual Nov 16–17 **Approved**; Annual used **8.00** / pending **6.00** / remaining **16.00**. Also **CRS-2026-0038** Approved.

### N-AG-LV-01 — Agent Plan·Run·consent leave (`emp_1001`)
Steps: Pulse **Agent** → “Request 2 days annual leave … 2026-12-21→2026-12-22” → Plan now → Approve plan → Run → consent Approve on `POST /people/leave-records/`.  
Binary: **PARTIAL** · UX:4 C21:3 DEP:2 INT:2  
**Evidence (theatre OK):** Plan graph 3 steps; Run paused for confirmation; consent payload showed `method: POST`, `endpoint: /carbon-api/people/leave-records/`; UI reached **Run completed**.  
**Evidence (outcome miss):** Step 0 `resolve_entity` → `Entity 'get_my_leave_balance' not found` (entity **is** in `nibras/instance.yaml` → `/people/me/leave-balance/`). API `GET /people/me/leave/` after run has **no** 2026-12-21 row; annual pending stayed **6**. Write did not land.  
**Ownership:** REQUEST Pulse (entity resolve in Agent run + consent→write durability). No Nibras silent fix.

### N-PAY-01 — Chat payslips as employee (`emp_1001`)
Steps: Pulse Chat “Show my payslips / قسيمة الراتب”.  
Binary: **PASS** · REF:5 DEP:5 INT:4  
**Evidence:** Reply **Not authorized to view compensation** (`people:view_compensation`) with takeaway “authorization deny, not an empty payroll result”. API `GET /people/me/payslips/` → `[]`. B5-style honesty (no invented payslip lines). Salary CBAC earlier same persona also PASS.

### N-CAST-01 — Expanded emp_* cast passwords
Steps: Bulk `set_password` all `emp_*` users on `nibras_dev`; token smoke.  
Binary: **PASS** · DEP:5 REG:5  
**Evidence:** `bulk_reset 536 of 536`; HTTP **200** token for `emp_1001`, `emp_1399`, `emp_1009`, `emp_1416`, `emp_2076`, `emp_901`, `emp_1049`. `link_employee_users` alone does **not** reset existing passwords — bulk set required.

---

## Findings bank (Nibras-owned)

| ID | Sev | Symptom | Status |
|----|-----|---------|--------|
| NB-P0-EMP-PAGE | P0 | Employees list times out / shows 0 rows | **FIXED** — pagination + select_related + FE page walk + regression tests |
| NB-P2-BANNER | P2 | EduOS preview banner on Nibras | **FIXED** — brand-aware `devBanner.message` + `DEV_BANNER_PLATFORM` |
| NB-P2-BACKDROP | P2 | Modal backdrop blocks Pulse/nav (repeat) | **FIXED** — Shell desktop peek `persistent` (REQUEST N5 / Pulse P1) |
| NB-P3-ADMIN-SELF | P3 | Admin `ahmed` has no Employee link | OPEN — expected; use emp_* cast |
| NB-P2-LEAVE-TOOL | P2 | Admin Chat resolves employee but skips leave-balance tool | **FIXED** — named leave intent + Pulse INTENT inject (N7 / Pulse P1) |
| NB-P1-AG-LEAVE-ENTITY | P1 | Agent run: `get_my_leave_balance` entity not found; leave POST consent did not persist Dec 21–22 | **FIXED** — catalog coerce + alias + confirm HTTP fail-closed (N10 / Pulse P1); browser re-smoke recommended |

---

## Scoreboard delta

| Wave | Executed | PASS | FAIL | BLOCKED | PARTIAL |
|------|----------|------|------|---------|---------|
| B1 prior multi-persona | 13 | 11 | 0 | 0 | 1 |
| B1 + leave E2E | 16 | 14 | 0 | 0 | 1 |
| B1 + Agent leave / payslip / cast | **19** | **16** | **0** | **0** | **2** |

**Delta:** +N-PAY-01 +N-CAST-01 PASS; +N-AG-LV-01 PARTIAL (theatre OK, write miss).

**Cast file:** `logs/CAST-NIBRAS.md`

**Next (still Nibras-only):** Pulse ACK queue (Canvas blank, backdrop, leave-tool, Agent entity); optional deeper cast UI logins; B2 only after Nibras hold release.

---

*No firefighting timeout patches applied.*
