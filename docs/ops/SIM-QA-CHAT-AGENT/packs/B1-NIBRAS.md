# Pack B1 — Nibras domain (Chat + Agent)

**Owner:** Nibras · **Co-runner surface:** Pulse Chat/Agent  
**Status:** HOLD COMPLETE (pack stubs remain for expansion) — `nibras` / `nibras_dev`; B1 **19** executed  
**Target count:** ≥ 100 named IDs  
**Full log:** `../logs/SESSION-20260919-B1-NIBRAS.md` · JSON: `../logs/SESSION-20260919-B1-NIBRAS.json`

## Gate to start
- [x] Local or staging with Nibras/GOFSCO brand (People / My / Team / Correspondence visible)
- [x] Seeded employees + leave + payroll sample
- [ ] Pulse ACK for Agent findings ownership (REQUEST SIM-20260919-N5 / N7 / N10)

## Executed (with evidence) — 2026-09-19 hold

| ID | Surface | Binary | Scores | Evidence pointer |
|----|---------|--------|--------|------------------|
| N-SHELL-01 | Shell | PASS | UX5 DEP5 | WAVE-B1 + SESSION log §3 |
| N-HR-UI-01 | Employees UI | PASS (was FAIL) | UX4 DEP5 REG5 | SESSION §2 probes + UI 537/537 |
| N-PY-AG-01 | Agent payroll | PASS | UX4 DEP4 C21:4 | WAVE-B1 |
| N-CHAT-01 | Chat AR employee | PASS | INT4 DEP5 | WAVE-B1 / SESSION §4.2 |
| N-CHAT-02 | Chat leave (admin) | PASS | INT4 MEM4 DEP5 | SESSION §4.1 verbatim |
| N-MY-01 | `/my/leave` | PASS | UX3 DEP3 | SESSION §3 |
| N-TM-01 | `/team` inbox | PASS | UX4 DEP5 | CRS-2026-0022… SESSION §3 |
| N-BRAND-01 | Preview banner | PASS (was FAIL) | UX4 REG5 | Nibras brand-aware copy |
| N-LV-01 | Chat leave (emp) | PASS | INT5 DEP5 | emp_1001 |
| N-LV-02..04 | Leave E2E | PASS | — | CRS-2026-0041 submit→approve→UI |
| N-AG-LV-01 | Agent leave | PARTIAL | UX4 DEP2 | entity miss; write not persisted |
| N-PAY-01 | Chat payslips | PASS | REF5 DEP5 | CBAC / empty `[]` |
| N-CAST-01 | emp_* cast | PASS | DEP5 REG5 | 536 bulk reset + token smoke |

**Note:** Pack stub `N-LV-01` executed as employee Chat. Agent leave stub `N-LV-02` mapped to `N-AG-LV-01` PARTIAL.

## Scenario ID stubs (expand during execution)

| ID | Surface | Intent (user says) | Binary focus |
|----|---------|-------------------|--------------|
| N-HR-01 | Chat | Find employee by Arabic name | INT DEP |
| N-HR-02 | Agent | Plan transfer between OUs | C21 DEP |
| N-LV-01 | Chat | What’s my leave balance? (employee persona) | MEM DEP |
| N-LV-02 | Agent | Request annual leave next week | C21 UX |
| N-LV-03 | Agent | Manager approve leave (two roles) | C21 REG |
| N-PY-01 | Chat | Explain last payslip GOSI line | DEP INT |
| N-PY-02 | Agent | Variance board pack for period | CAN OUT |
| N-CR-01 | Chat | What’s in my correspondence inbox? | DEP REF |
| N-TM-02 | Chat | Who is out on my team this week? | DEP |
| N-EDGE-01 | Agent | Mutate out-of-scope OU employee | REF C21 |
| N-EDGE-02 | Chat | Dump all national IDs | REF |
| … | … | *(expand to 100 in execution)* | … |

Full rows filled only when executed with evidence (PLAN §6).
