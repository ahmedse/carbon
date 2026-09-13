# Chairman Demo Script — ClearTurn Trust Platform + Pulse AI (AASTMT Carbon · GOFSCO Nibras)

> **Audience:** Chairman / C-level. **Duration:** ~20–25 min. **Environment:** this dev machine (`http://127.0.0.1:5179`).
> **Narrative thread:** *"One ClearTurn platform, many isolated instances — AASTMT's governed carbon ledger, GOFSCO's Nibras ERP, and one shared Pulse AI that can *explain* any governed number."*

---

## 0. Before you start (5 min prep)

1. Ensure the stack is up:
   ```bash
   cd /home/ahmed/ws/carbon && ./manage.sh start
   ```
   Backend on `:8000`, frontend on `:5179`.

2. **Log in as the super admin** (not the current `emp_90210` employee):
   | Username | Password | Role |
   |----------|----------|------|
   | `ahmed` | `AdminPa_132` | Super admin — sees **everything** |

   → `http://127.0.0.1:5179/login`, sign in as `ahmed`.

3. **Open in tabs beforehand** so there's no dead time:
   - `http://127.0.0.1:5179/carbon/chairman`
   - `http://127.0.0.1:5179/admin/ai`
   - `http://127.0.0.1:5179/people/payroll`

4. **If any page shows empty tables**, seed first (see §6 "Seeding empty states").

---

## 1. The one-liner (30 seconds)

> "This is the ClearTurn Trust Platform + Pulse AI — one codebase, deployed as isolated instances. **AASTMT Data Trust** runs the university and hosts **Carbon**, the auditable emissions ledger. **Nibras** is GOFSCO's AI-native ERP (people, payroll, leave — Kuwait-compliant). **Pulse AI** is the shared executive layer that answers *any* question against governed data — and proves it with an audit trail."

Then jump straight into the Chairman Dashboard.

---

## 2. Carbon — Chairman Dashboard (4 min) 🎯 *the money shot*

**URL:** `http://127.0.0.1:5179/carbon/chairman`

Walk the single screen, top to bottom:
1. **Six KPI cards** — headline metrics (total footprint, scope breakdown, coverage %, SBTi status). *Talk to the "as of" timestamp* top-right → "this is live, recency is auditable."
2. **One chart** — the trend/breakdown. *"Everything else is a click away for the analyst, but this is what the board needs."*
3. **SBTi alignment block** — *"our trajectory against science-based targets."*
4. **Coverage + actions block** — *"what's measured, what's missing, what's next."*

**Talk track:** the 3-tier hierarchy — Chairman sees one screen → analyst drills in → auditor sees lineage. This *is* the governance story: every number traces back to a source row.

---

## 3. Carbon — drill into the ledger (3 min)

**URLs:**
- `http://127.0.0.1:5179/carbon/console` — Carbon Console
- `http://127.0.0.1:5179/carbon/dashboard` — analyst dashboard
- `http://127.0.0.1:5179/carbon/analytics` — analytics

Show the drill path:
1. **Dashboard → analytics** — *"the analyst's view; where the KPI came from."*
2. **My Data** `http://127.0.0.1:5179/carbon/my-data` — *"the raw activity rows behind the numbers."* Click into a row → shows the contextual inspector (lineage, source evidence, calculations).
3. **Run Calculations** `http://127.0.0.1:5179/carbon/calculations` and **Verification** `http://127.0.0.1:5179/carbon/verification` — *"data in → verified emissions out, with a paper trail."*

---

## 4. Pulse AI — the executive layer (6 min) 🎯 *differentiator*

**URL:** `http://127.0.0.1:5179/admin/ai` (Pulse overview)

### 4a. Overview / capabilities health (1 min)
Show the **Capabilities grid** — store, reasoning lane, verification, MCP, sandbox each with a health chip. *"Every subsystem reports its own health; nothing fails silently."*

### 4b. Live Q&A in the workspace (3 min) 🎯
**URL:** `http://127.0.0.1:5179/admin/ai/workspace`

Ask the agent **real questions that hit governed data** (keep a cheat-sheet open):
- *"What is our total carbon footprint this period?"*
- *"Which campus has the highest emissions?"*
- *"What's our SBTi alignment status?"*

**What to point out while it answers:**
- The **structured answer** (headline + table + chart + caveats) — *"not a chatbot paragraph, a publication-grade brief."*
- The **sources block** — *"it tells you which tool/table each fact came from."*

### 4c. The governance behind the answer (2 min)
- **Audit Trail** `http://127.0.0.1:5179/admin/ai/audit` — *"every AI decision is a persisted row: who, what action, allow/deny, why."*
- **Knowledge Graph** `http://127.0.0.1:5179/admin/ai/graph` — *"the connected entity map it reasons over."*
- **Memory** `http://127.0.0.1:5179/admin/ai/memory` — *"what it remembers across conversations, tenant-isolated."*
- **Watches** `http://127.0.0.1:5179/admin/ai/watches` — *"proactive alerts — e.g. it flags an anomaly before you ask."*

**Talk track:** *"This is the difference between a chatbot and a governed AI. Every answer is scoped to your data, sourced, and auditable — with fail-closed guards so a bad instruction is refused, not obeyed."*

---

## 5. Nibras — GOFSCO's AI-native ERP (4 min)

**URLs:**
- `http://127.0.0.1:5179/people` — People home
- `http://127.0.0.1:5179/people/employees` — Employees
- `http://127.0.0.1:5179/people/payroll` — **Payroll Runs** (already open)
- `http://127.0.0.1:5179/people/payslips` — Payslips
- `http://127.0.0.1:5179/people/leave` — Leave
- `http://127.0.0.1:5179/people/positions` — Positions
- `http://127.0.0.1:5179/people/loans` — Loans
- `http://127.0.0.1:5179/people/attendance` — Attendance

Show the breadth quickly:
1. **Employees** — directory with drill-down detail.
2. **Payroll Runs** — *"payroll is a governed workflow, not a spreadsheet."* Open a run → payslip.
3. **Leave / Requests** — the self-service side (`/my/leave`, `/team` inbox for approval flow).

**Talk track:** *"Nibras is GOFSCO's operational ERP — a separate instance with its own isolated database. Same platform, same Pulse AI, different tenant."*

---

## 6. Data-trust / CBAC / audit (3 min) 🎯 *closes the loop*

**URLs:**
- `http://127.0.0.1:5179/admin/access` — **Access Control**
- `http://127.0.0.1:5179/admin/catalog/field-policies` — **Field Policies**
- `http://127.0.0.1:5179/admin/audit` — **Audit Log**
- `http://127.0.0.1:5179/catalog/policies` — Governance Policies
- `http://127.0.0.1:5179/catalog/governance` — Governance Audit

Show:
1. **Access Control** — *"every table is tenancy-scoped: global / shared / private. A user only sees their slice."*
2. **Field Policies** — *"column-level rules — who can read salary vs. name."*
3. **Audit Log** — *"immutable record of every read/write. This is what a regulator or auditor asks for."*

**Closing talk track:** *"Data trust isn't a slide — it's built in: scoped access, field-level policy, an immutable audit trail, and an AI that inherits the same guards."*

---

## 7. Seeding empty states (if a page looks blank)

The platform ships with seed scripts. If a demo page is empty, seed then re-check:

```bash
cd /home/ahmed/ws/carbon/backend
/home/ahmed/ws/carbon/.venv/bin/python manage.py shell -c "
from alamein_campus import seed_trust_core, seed_tables, seed_fields
seed_trust_core.run()
seed_tables.run()
seed_fields.run()
"
```

> Note: the seed modules live under `alamein-campus/` — run from the backend with the paths on `sys.path` (see `alamein-campus/ALAMEIN_TEST_JOURNEY.md` for the full Phase 1–7 narrative + exact data rows to walk through).

For a **carbon-rich demo** (non-empty Chairman KPIs), follow `alamein-campus/ALAMEIN_TEST_JOURNEY.md` Phases 2–5 to load activity + evidence + run calculations first.

---

## 8. Q&A cheat-sheet (likely chairman questions)

| Question | Answer / where to show |
|----------|------------------------|
| "Is this auditable?" | Audit Log (`/admin/audit`) + AI Audit Trail (`/admin/ai/audit`) + lineage in the row inspector |
| "Who can see what?" | Access Control + Field Policies |
| "Is the AI safe?" | Pulse Overview capabilities health + fail-closed guards + audit trail |
| "Is this live or a mockup?" | "As of" timestamps + run a fresh calculation live |
| "Can it scale to other campuses?" | Org Units (`/admin/org-units`) + multi-tenant app registry |
| "What's next?" | `ROADMAP.md` + `docs/pulse/PULSE-UNIFIED-REMEDIATION-PLAN.md` |

---

## 9. The 60-second version (if time runs out)

1. **Chairman Dashboard** (`/carbon/chairman`) — the 6 KPIs + SBTi.
2. **Pulse workspace** (`/admin/ai/workspace`) — ask one governed question, show the sourced structured answer.
3. **Audit Trail** (`/admin/ai/audit`) — "and here's the proof."
4. Close: "one platform, many instances — AASTMT carbon, GOFSCO Nibras, one governed Pulse AI."
