# GOFSCO — Next-Generation Enterprise Platform Vision
# Built on the Carbon Data Trust Platform · Pulse as Co-worker
# ============================================================
# Status:  DRAFT — Strategic Vision & Product Definition
# Author:  Master Architect
# Date:    2026-08-30
# Source:  Raw materials ingested 2026-07-28 (GOFSCO raw/GOFSCO app/)
#          • Issues with Hard Task HRMS System.docx
#          • GOFSCO Stores Operations and ERP Workflow Report.pdf (2)
#          • GOFSCO Stores Report (3).pdf
#          • tectona-fin depts requirements.txt (Finance dept)
#          • Internal Handover Form.docx (Vehicle checklist)
#          • MIV/MRV paper forms (WhatsApp images)
#          • Sage 300 screenshots (inventory workflow)

---

## 1. VISION STATEMENT

GOFSCO is the seed customer for a **platform play**, not a bespoke ERP project.
The goal is to build next-generation, AI-native domain apps on top of the
Carbon Data Trust Platform — and turn that platform+apps combination into
a commercial product targeting mid-sized oil and gas service companies in the
GCC, then the wider region.

**What makes this "next-generation" vs traditional ERP:**

| Traditional ERP (Sage 300 / SAP B1 / Odoo) | This Platform |
|---------------------------------------------|---------------|
| Data lives in the ERP — hard to trust, audit, or govern | Every business object is a governed data product with lineage, DQ scores, and ownership |
| AI is bolted on after the fact (chatbot on top of old data) | Pulse is an ambient co-worker woven into every workflow — not a separate module |
| Compliance rules are hard-coded logic in application code | Compliance rules (Kuwait Labor Law, KOC standards) are first-class DQ rules — declarative, auditable, AI-enhanced |
| Reports are built by extracting to Excel | Live, governed reports with full lineage — Excel is an optional export, never the source of truth |
| One monolithic system — rigid, one-size-fits-all | Modular domain apps hosted on a shared platform — each app is composable, each shares the same trusted data fabric |
| Integration is a custom project | Connections module provides governed ETL from Sage 300, bank feeds, KOC systems |
| Knowledge locked in staff heads and spreadsheets | Pulse learns patterns, surfaces anomalies, drafts reports — institutional knowledge is amplified, not trapped |

---

## 2. WHO IS GOFSCO

**Company:** Gas and Oil Field Services Company (GOFSCO / GOFNDT)
**Industry:** Oilfield services — drilling, coiled tubing (CT), well testing, PCP operations
**Client:** Kuwait Oil Company (KOC) and related entities
**Locations:** Ahmadi (main base), Drilling yard, CT yard, PCP yard — all in Kuwait
**Current ERP:** Sage 300 (Plexsolution Co. dealer) — licensed to Gas & Oil Field Services Co.
**Current HRMS:** Hard Task — failing Kuwait Labor Law compliance
**Size signal:** 4 operational stores, KOC project billing, Kuwaitization requirements → mid-size (est. 200-500 employees)
**KOC context:** KOC No. 26005371 appears in forms; projects tracked as GSWT, coiled tubing, drilling services

---

## 3. PAIN MAP — WHAT IS BROKEN TODAY

### 3.1 Human Resources (Hard Task HRMS)

| Pain | Root Cause | Business Impact |
|------|-----------|-----------------|
| Annual leave advance payment not Kuwait Labor Law compliant | Hard Task computes full month advance; actual law = split by calendar | Manual Excel corrections every payroll cycle |
| No rotation status (1/1, 2/1, 3/1, 5/1 schedules) | System treats all as 30-day KLL standard | Manual adjustments to every rotation employee's salary, every month |
| No Kuwaitization status (42 days leave, 21-day salary basis, KOC standards) | System has no Kuwaitization concept | Separate manual track for every Kuwaiti employee |
| No End of Service provision automation | Job Bonus, OT, Incentive Bonuses excluded from EOSI base | Incorrect EOSI calculations; legal exposure |
| No attendance permission handling | System auto-deducts without exception logic | Deductions for business meetings → employee disputes |
| No C&B elements | Accommodation, vehicle, medical, school fees, air tickets, OT, bonuses | Entire C&B ledger lives in Excel |
| No HR reporting | No promotions log, no increment history, no budget vs actual | Entire HR reporting done in Excel post-payroll |
| Missing modules | No: Recruitment, Org Structure, Performance, KPIs, Training, Employee Relations, Penalties, Disciplinary | No system of record for people lifecycle |

**Verdict:** Hard Task is a payroll tool pretending to be an HRMS. GOFSCO has no functioning people management system.

### 3.2 Finance (Sage 300 + Excel silos)

| Pain | Root Cause | Business Impact |
|------|-----------|-----------------|
| Loans in separate Excel | No loan management module in Sage 300 | No accrual automation, no rollover alerts, no audit trail |
| Bank Guarantees in Excel | Same | BGs expire unnoticed → penalties with KOC or suppliers |
| Letters of Credit in Excel | Same | LC deadlines missed, exposure to forfeiture |
| Bank reconciliation in Excel per bank | Same | Version control risk, formula errors, delayed close |
| Daily manual journal entries for bank transactions | No bank feed | Finance team spends time on data entry instead of analysis |
| No centralized document vault | Sage 300 has no document linking | PDF bank letters, payment confirmations, LC docs scattered |
| No loan rollover reminder | No workflow system | Rollovers missed → penalty interest |

**Verdict:** Finance is running a shadow ERP in Excel alongside Sage 300. Two sources of truth = neither is fully trusted.

### 3.3 Stores & Inventory (Sage 300 I/C)

| Pain | Root Cause | Business Impact |
|------|-----------|-----------------|
| Hardcopy MIV/MRV transcribed into Sage manually | No mobile / digital capture at point of movement | Errors in item code, qty, date, location, UOM, cost center |
| Physical movement before system update | No workflow enforcement | System balances temporarily wrong → decisions on bad data |
| 4 stores with no unified item master | Each store manages its own items | Duplicates, inconsistent naming, no cross-store visibility |
| No bin/zone/status tracking | Sage 300 location = single field | Cannot distinguish available vs reserved vs quarantine vs damaged vs expired |
| No chemical/HAZMAT controls | No lot/expiry/SDS fields enforced | Expired chemicals issued; HSE/KOC compliance risk |
| Physical counts done on exported Excel sheets | No mobile counting app | Blind count discipline broken; count = guided by same data being verified |
| Reporting = export to Excel then reformat | No live dashboards | Aged inventory, MIV/MRV reports are retrospective and manual |
| 4 separate stores with no network visibility | Sage 300 not configured for multi-warehouse governed model | Blind to inter-store stock; duplicate procurement |

**Verdict:** The stores operation is functional but fragmented. The Sage 300 process works for basic transactions but fails on data quality, visibility, and decision support.

---

## 4. THE PLATFORM ARCHITECTURE — HOW GOFSCO APPS FIT

The Carbon Data Trust Platform is already built. GOFSCO apps are **hosted apps** —
they live inside the platform just like the existing `emissions` app. They get
for free: governed data catalog, MDM reference data, DQ rule engine, evidence
document vault, connections/ETL, RBAC, Pulse AI, and the entire shell UI.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Carbon Data Trust Platform                           │
│                                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Catalog  │  │   MDM    │  │    DQ    │  │Evidence  │  │Connections│ │
│  │(schemas) │  │(ref data)│  │(rules)   │  │(doc vault)│  │(ETL/sync)│  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │              Carbon AI  (Pulse as co-worker)                       │  │
│  │   DQ validation · anomaly detection · report drafting · NL query  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │   emissions/ │  │   people/    │  │   stores/    │  │ finance/   │  │
│  │  (CARBON APP)│  │  (GOFSCO-1)  │  │  (GOFSCO-3)  │  │(GOFSCO-2)  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘  │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐                                      │
│  │   assets/    │  │  projects/   │                                      │
│  │  (GOFSCO-4)  │  │  (GOFSCO-5)  │                                      │
│  └──────────────┘  └──────────────┘                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

**What each platform capability gives to GOFSCO apps:**

| Platform Capability | How GOFSCO Apps Use It |
|---------------------|----------------------|
| **Catalog** | Every entity schema (Employee, Position, Item, BankAccount, Asset) is a governed data product with owner, steward, lineage |
| **MDM** | Reference sets: job grades, departments, KOC project codes, item categories, UOM table, rotation patterns, bank list, currency |
| **DQ Rules** | Kuwait Labor Law rules as DQ checks on payroll runs; stock movement validation rules; bank recon tolerance rules |
| **Evidence** | Employment contracts, bank guarantee PDFs, LC documents, SDS sheets, MIV/MRV paper scans — all linked to their parent transaction |
| **Connections** | Sage 300 import (daily sync of existing transactions), bank statement feeds, KOC project data |
| **RBAC / OrgUnit** | The existing org tree (Ahmadi/CT/Drilling/PCP/Finance/HR) maps directly to platform OrgUnits — zero re-implementation |
| **Pulse AI** | Detects payroll anomalies, warns about expiring BGs/LCs, forecasts stock depletion, drafts monthly HR reports, answers "how many employees are on rotation in Drilling?" in natural language |

---

## 5. THE FIVE GOFSCO DOMAIN APPS

---

### App 1: PEOPLE & WORKFORCE (Start here)
**Priority:** P0 — highest pain, highest strategic value, enables all other apps
**Code name:** `people`
**Backend Django app:** `backend/people/`
**Nature:** Active operations app (data entry + approvals + workflows + AI)

#### What makes this next-gen vs Hard Task

**Traditional HRMS approach:** A form per process. Leave form → payroll deduction.
Training record → checkbox.

**Next-gen approach:**
- **Employee is a governed data product.** Their record has a data quality score.
  A payroll run is a transformation pipeline with full lineage — inputs (salary
  components, attendance, permissions, bonuses), calculation rules (Kuwait Labor
  Law + company policy as DQ rules), outputs (net pay, provisions).
- **Compliance rules are declarative, not code.** Kuwait Labor Law leave
  calculation = a DQ rule on the payroll dataset. If violated, the run fails
  DQ — and Pulse explains why and suggests the fix.
- **Pulse knows every employee.** "Ahmed has 47 days leave accrued, is on 2/1
  rotation, leaves on 15 October — split his October pay at 31st and November
  at 1st." Pulse validates every run, not just the edge cases a payroll clerk
  catches.
- **Org hierarchy IS the platform's OrgUnit tree.** No new org model to build —
  GOFSCO's Ahmadi / CT / Drilling / PCP structure plugs directly into the
  platform's existing RBAC and scoping.

#### Module Breakdown

**M1.1 — Organisation & Positions**
```
Model: Position (linked to OrgUnit)
  - Position code, title, grade band, department
  - Headcount budget (budgeted vs actual)
  - KOC Kuwaitization target per department
  - Reporting line (parent position)

Pulse role: "Department X has 3 vacancies against headcount plan — Recruitment queue has 0 open jobs for these positions"
```

**M1.2 — Employee Record (core data product)**
```
Model: Employee
  - Personal data (name, nationality, civil ID, passport, visa expiry)
  - Employment type: KLL standard | Rotation (1/1, 2/1, 3/1, 5/1) | Kuwaiti national
  - Salary structure: basic + C&B components
  - C&B: accommodation tier, vehicle entitlement, medical plan, school fees, air ticket
  - Start date, probation end, position, department, work location

DQ rules on Employee record:
  - Civil ID / Iqama expiry > 30 days away → warning
  - Visa expiry < 60 days and not renewed → warning
  - Kuwaitization employee has correct leave calendar (42 days) assigned → pass/fail
  - Salary grade within band → pass/fail

Pulse role: "3 employees in Drilling have Iqama expiring within 30 days — no renewal initiated"
```

**M1.3 — Leave & Absence**
```
Leave types:
  - Annual: 30 days (KLL standard) | 42 days (Kuwaiti national) | Rotation-adjusted
  - Emergency, unpaid, sick, maternity, paternity, Hajj

Rotation-aware leave calculation:
  Leave days = f(rotation_type, days_in_field) — not a flat calendar
  Example: 2/1 = 2 months field + 1 month leave → pro-rated leave accrual per day worked

Kuwait Labor Law advance payment rule:
  Leave pay for month M = (basic / days_in_M) × leave_days_in_M
  NOT: full leave advance on departure date
  This becomes a DQ rule on the payroll run dataset.

Pulse role: "This leave spans October and November — the pay split must be
  Oct: 16 days × (basic/31) and Nov: 15 days × (basic/30). Current calculation
  gives a full October advance. Flagging for correction."
```

**M1.4 — Payroll Engine**
```
Payroll run = a DataSchema table (like any other data product in the platform)
  - Inputs: Employee records, attendance data, leave records, permissions, one-off items
  - Calculation pipeline: additions (OT, incentives, C&B) → deductions (late, absences, loans)
  - Output: pay slip dataset with full lineage to every input

DQ rules on payroll run:
  - Kuwait Labor Law leave calculation correct → pass/fail
  - Kuwaitization employee uses 21-day salary basis → pass/fail
  - EOSI provision includes all qualifying C&B elements → pass/fail
  - No employee has net pay < minimum wage (if applicable) → pass/fail
  - Total payroll variance < X% from previous month (configurable) → warning if exceeded

Pulse role: "This payroll run has 3 DQ failures and 2 warnings. The failures
  are: (1) Ahmed Al-Rashid leave split, (2) Faisal's EOSI base excludes vehicle
  allowance, (3) Rotation employee in Drilling has wrong calendar. Do you want
  me to explain each and suggest corrections?"
```

**M1.5 — Compensation & Benefits**
```
C&B components (each a separate data product):
  - Accommodation: tier (single/married/senior), actual vs allowance tracking
  - Company vehicle: entitlement grade, assigned vehicle (→ links to assets app)
  - Medical insurance: plan, family size, insurer, policy expiry
  - School fees: children count, approved amount, reimbursement vs direct
  - Air tickets: economy/business entitlement, family size, annual budget

DQ rules:
  - Vehicle assignment matches entitlement grade → pass/fail
  - Medical insurance expiry > 30 days away → warning
  - School fees reimbursement total ≤ approved amount → pass/fail
```

**M1.6 — End of Service (Indemnity)**
```
EOSI calculation (Kuwait Labor Law Article 51+):
  Base = basic + qualifying allowances (which allowances qualify = configurable policy)
  Standard: 15 days per year for first 5 years, 1 month per year after
  Adjusted for: unpaid absences, disciplinary deductions (where applicable)

Provisions:
  Monthly EOSI provision = (annual EOSI estimate) / 12
  Posted as a journal entry to Finance app → Sage 300 sync

Pulse role: "Narsimha's EOSI provision this month is understated by KD 47 —
  the vehicle allowance was excluded from the calculation base. This has been
  the case for 6 months. Total exposure: KD 282."
```

**M1.7 — Attendance & Permissions**
```
Attendance sources:
  - Biometric integration (if available) or manual roster entry
  - Rotation schedule as the truth — field staff are "present" if on shift

Permission types:
  - Business meeting (no deduction)
  - Medical (doctor letter → no deduction or partial)
  - Personal (deduction or balance from annual leave)
  - Emergency (manager approval → no deduction)

DQ rule: payroll deduction only if permission NOT approved → blocks incorrect deductions
```

**M1.8 — Employee Relations**
```
Sub-modules:
  - Warnings & Counselling (verbal → written → final)
  - Penalties: types, rules, amounts (% of salary or fixed)
  - Disciplinary investigations: case, witnesses, evidence (links to Evidence module), outcome
  - Grievances: employee-filed, response, resolution

Pulse role: "Mohamed has received 2 written warnings in the last 6 months —
  company policy triggers a mandatory performance review before a 3rd warning
  is issued."
```

**M1.9 — Recruitment**
```
- Job requisition (linked to Positions with headcount budget)
- Approval workflow (department head → HR → GM)
- Candidate pipeline (applied → screened → interviewed → offered → accepted)
- Document collection (CV, certificates, Iqama application)
- Onboarding checklist (generates employee record on hire)

Pulse role: "You have 4 open positions in Drilling that have been vacant for
  more than 45 days. Would you like me to draft a recruitment status report?"
```

**M1.10 — Performance & KPIs**
```
Performance cycle:
  - Annual goal setting (from company KPIs → department → individual)
  - Mid-year review
  - Year-end appraisal + rating
  - Linked to: increment decision, bonus calculation, promotion recommendation

KPI monitoring:
  - Department KPIs as a data product with DQ score (completeness + timeliness of updates)
  - Integration with 2026 Target & KPIs Excel (already in raw materials)

Pulse role: "Q3 performance data is 43% complete — 12 managers have not submitted
  their team reviews. Deadline is in 8 days."
```

**M1.11 — Training & Development**
```
- Training catalogue (internal + external)
- Employee training plan (linked to performance gaps)
- Attendance records + certifications
- KOC mandatory certifications (H2S, First Aid, etc.) with expiry tracking

DQ rule: employees assigned to field work must hold valid H2S certification → pass/fail

Pulse role: "6 field employees in Ahmadi have H2S certifications expiring within
  60 days — no renewal training is scheduled."
```

---

### App 2: FINANCE INTELLIGENCE
**Priority:** P1 — high value, complements HR (EOSI provisions flow here)
**Code name:** `fintrust`
**Backend Django app:** `backend/fintrust/`
**Nature:** Active monitoring + document vault + smart alerts

#### Module Breakdown

**M2.1 — Treasury Instruments**
```
Each instrument = a governed data product in the Catalog.

Loans:
  - Lender bank, original amount, drawn amount, currency
  - Repayment schedule (monthly installments as a dataset)
  - Maturity date, rollover date, interest rate
  - Status: active | maturing | matured | defaulted
  - Evidence: facility letter PDFs linked via Evidence module

Bank Guarantees (BGs):
  - Issuing bank, beneficiary (KOC or other), purpose
  - Amount (KD / USD), expiry date, auto-renewal flag
  - Status: active | pending renewal | expired | cancelled

Letters of Credit (LCs):
  - Project, supplier, value, currency
  - Open date, expiry date, utilization
  - Document set: linked to Evidence module

DQ rules:
  - BG expiry < 45 days with no renewal initiated → error
  - LC expiry < 30 days with open shipment → error
  - Loan maturity < 30 days with no rollover instruction → warning

Pulse role: "BG-2026-014 (KOC, KD 85,000) expires in 18 days. I found no renewal
  application in the system. The contact at Gulf Bank for your BG desk is Fatima
  Al-Rashidi. Would you like me to draft the renewal request letter?"
```

**M2.2 — Bank Reconciliation Pipeline**
```
Instead of Excel per bank, each bank account is a data product.

Monthly BRS = a data pipeline:
  Input A: bank statement (CSV/PDF upload → parsed via Connections)
  Input B: Sage 300 GL entries for that bank account (synced via Connections)
  Reconciliation rule: match by reference, date, amount (tolerance: KD 0.001)
  Output: matched items, unmatched items with aging, reconciling items list

DQ rules:
  - No unmatched items older than 7 business days → warning
  - Closing balance match between bank statement and GL → pass/fail

Pulse role: "Bank reconciliation for KFIC account as of 31 July has 3 unmatched
  entries totalling KD 4,200. The largest item is a debit dated 22 July with no
  GL posting. Do you want me to investigate matching candidates?"
```

**M2.3 — Document Vault (uses platform Evidence module)**
```
Documents linked to:
  - Loans → facility letters, disbursement confirmations
  - BGs → guarantee certificates, renewal letters
  - LCs → LC documents, shipping documents, payment confirmations
  - Bank accounts → monthly bank statements, bank advices

The platform Evidence module already handles upload, storage, and linking.
Finance app simply uses it with Finance-domain metadata tags.
```

**M2.4 — Smart Alerts & Accruals**
```
Accruals automation:
  - Monthly loan interest accrual = auto-calculated from schedule → journal entry draft
  - EOSI provisions from People app → journal entry draft
  - Both posted to Sage 300 via Connections

Alerts (delivered via platform Notification Panel from NGX plan):
  - Loan rollover: 30 days, 14 days, 7 days ahead
  - BG expiry: 45 days, 30 days, 15 days ahead
  - LC expiry: 30 days, 14 days ahead
  - Unreconciled bank items > 7 days old
```

---

### App 3: SMART STORES & INVENTORY
**Priority:** P2 — operationally critical, replaces Sage 300 I/C
**Code name:** `stores`
**Backend Django app:** `backend/stores/`
**Nature:** Operational transaction system + mobile workflows + AI intelligence

#### What makes this next-gen vs Sage 300 I/C

- **Item master is an MDM data product** — governed, duplicate-detected, category-driven,
  maker-checker approval before activation. Not a form in Sage 300.
- **MIV/MRV are data quality-scored transactions** — a movement is complete only
  when all required fields pass DQ checks. Incomplete = red; complete = green.
  The score is visible to the store supervisor on a live dashboard.
- **Pulse sees patterns across all 4 stores simultaneously** — "Drilling store has
  been issuing Item X at 3× the Ahmadi rate for 6 weeks. Either consumption is
  unusually high or there's undocumented re-transfer. Investigate."
- **The physical count is a reverse DQ run** — the system hides expected quantities
  from the counter (blind count), then Pulse analyzes variances.

#### Module Breakdown

**M3.1 — Item Master (MDM-backed)**
```
Item as a governed reference data entity:
  - Item code (auto-generated by category prefix rule)
  - Description, category (A/B/C criticality, consumable/spare/chemical)
  - Unit of Measure (from MDM UOM table — no free-text)
  - Min/max stock level per location
  - Lead time, preferred supplier
  - For chemicals: chemical name, SDS document (Evidence), hazard class, storage temp
  - For serials: tracked individually

MDM workflow: New item request → duplicate detection (Pulse checks similar names)
  → mandatory field validation → supervisor approval → activated

DQ rules on item master:
  - Chemical items must have SDS document linked → pass/fail
  - Min/max levels must be set for A-class items → pass/fail
```

**M3.2 — Receiving (MRV — Material Receiving Voucher)**
```
Digital MRV workflow:
  1. Storekeeper scans PO QR / selects PO from mobile
  2. Records received qty, condition, lot/expiry (for chemicals)
  3. Attaches delivery note photo (Evidence)
  4. Routes for inspection if required (quarantine → inspection → release)
  5. System posts GRN and triggers 3-way match signal to Finance

DQ rules on MRV:
  - Received qty ≤ PO qty (unless approved amendment) → pass/fail
  - Expiry date > 90 days for chemicals → warning if < 90 days
  - Delivery note attached → pass/fail
```

**M3.3 — Issue (MIV — Material Issue Voucher)**
```
Digital MIV workflow:
  1. Requester submits electronic material request (from any device)
  2. Supervisor approves (tiered by value/category)
  3. Storekeeper picks and scans items
  4. System posts issue to job/cost center — no re-entry
  5. Receiver signs on device → digital acknowledgement

DQ rules on MIV:
  - Item not expired → hard block
  - Item not in quarantine/damaged status → hard block
  - Cost center is valid → hard block
  - Requested by authorized person → pass/fail

Pulse role: "CONS-0031 (CO2 Detection Tubes) is at zero stock with 3 pending
  MIV requests for GSWT operations. Last received: 47 days ago. Minimum stock
  level is 5. A PO was never raised after the last depletion — alerting."
```

**M3.4 — Physical Inventory Counting**
```
Blind count process:
  1. System freeze — no movements during count window (or in parallel with cutoff tracking)
  2. Count sheets generated WITHOUT expected quantities (blind)
  3. Counters submit counts on mobile
  4. System compares actual vs book → variance report
  5. Variances above threshold → second count
  6. Supervisor approves adjustment → posted with reason code

Pulse role: "Location AHM-B3-R2-S4 has a variance of -12 units on CONS-0012
  (H2S Detection Tubes). This is the 3rd consecutive month with a negative
  variance at this location. Possible causes: undocumented issues, bin labelling
  error, or systematic counting error. Recommend investigation."
```

**M3.5 — Cross-Store Network**
```
4-store unified view:
  - Ahmadi Main | Coiled Tubing | Drilling | PCP
  - Inter-store transfer workflow (same item, different locations)
  - Consolidated stock dashboard across all locations
  - "Available to allocate" view: total network stock - reservations

Pulse role: "Drilling store needs 20 units of CONS-0042 (H2S Detector 0.75-300 PPM)
  and has 0 in stock. Ahmadi has 35 in available status. Suggest initiating a
  store transfer."
```

---

### App 4: ASSET & FLEET MANAGEMENT
**Priority:** P3 — supports operations; depends on stores for spare parts
**Code name:** `assets`
**Backend Django app:** `backend/assets/`
**Nature:** Equipment lifecycle + vehicle fleet + maintenance scheduling

#### Module Breakdown

**M4.1 — Asset Registry**
```
Asset as a governed data entity (like an employee — has a lifecycle):
  - Asset code, category (vehicle / field equipment / office equipment)
  - Description, serial number, model, manufacturer
  - Assigned to: OrgUnit (Ahmadi/CT/Drilling/PCP) + responsible person
  - Cost, depreciation method, book value
  - Insurance policy expiry, safety certificate expiry

Evidence links: purchase order, insurance certificate, safety certificates
```

**M4.2 — Vehicle Fleet (from vehicle check form)**
```
Vehicle-specific:
  - Registration, chassis/engine numbers
  - Registration expiry (Daftar), insurance expiry, safety certificate expiry
  - Assigned driver, department
  - Daily trip checklist (digital version of the paper form found in raw materials):
    Fluids / Lights / External / Internal / Tyres / Safety equipment
  - Mileage log

DQ rules:
  - Vehicle safety certificate > 30 days valid → warning if < 30
  - Daily check not completed before first trip → escalation

Pulse role: "Vehicle KWB-2345 last safety certificate expires in 11 days.
  No renewal booking found. This vehicle is assigned to Drilling operations
  where it runs daily to the KOC yard."
```

**M4.3 — Work Orders & Maintenance**
```
Preventive maintenance:
  - Schedule by mileage (km-based) or calendar interval
  - Generates material requisition to Stores for spare parts
  - Technician completes checklist

Corrective maintenance:
  - Breakdown reported → work order created → parts requisitioned from Stores
  - Downtime tracked → cost allocated to job/department

Pulse role: "3 vehicles are overdue for oil service by more than 500km.
  This is a safety and warranty issue."
```

---

### App 5: PROJECTS & JOB COSTING
**Priority:** P4 — completes the financial picture; feeds from all other apps
**Code name:** `projects`
**Backend Django app:** `backend/projects/`
**Nature:** Cost aggregation + KOC billing intelligence

#### Module Breakdown

**M5.1 — Project / Job Register**
```
KOC project as the organizing entity:
  - KOC No. (e.g., 26005371), project name, type (GSWT, CT, Drilling, PCP)
  - Start / end date, contract value (KD + USD)
  - Primary operation team, site

Reference data (MDM): KOC project codes as a governed reference set
```

**M5.2 — Cost Allocation**
```
All transactions reference a project/job:
  - MIV issues → job cost centre
  - Payroll allocation (field staff → project or overhead)
  - Vehicle/asset usage → project
  - Overhead allocation rules

Pulse role: "Project GSWT-05 is 23% over material budget with 40% of the
  job remaining. The overrun is concentrated in H2S detection consumables —
  3× the budgeted rate. Do you want a variance analysis?"
```

---

## 6. PULSE AS CO-WORKER — THE DIFFERENTIATOR

This is what turns a functional enterprise app into a next-generation platform.
Pulse is not a chatbot bolted onto ERP screens. It is a co-worker who:

1. **Watches every data change** — a DQ rule fires on a payroll run, Pulse explains
   the violation in plain English and proposes the fix.

2. **Learns the patterns** — "In the last 8 months, GOFSCO consistently has 3-5
   employees with Iqama expiry issues in Q1. I'll surface this as a proactive
   checklist in November."

3. **Drafts reports you used to make in Excel** — "Draft the September HR headcount
   report by department, including vacancies, rotation split, and Kuwaitization %."
   Pulse pulls from governed data, structures the report, and you review/sign off.

4. **Bridges the silos** — "The Drilling team has 3 new headcount approvals from
   HR. None of the new hires have H2S certification, and their projected start
   date is in 4 weeks. Training typically takes 3 weeks. You need to enroll them
   now." This requires People + Training data — Pulse crosses both.

5. **Speaks the language** — Pulse knows Kuwait Labor Law, KOC Kuwaitization
   requirements, EOSI Article 51, rotation patterns. These are encoded as DQ rules
   and as knowledge in the AI domain layer.

### Pulse Domain Operations per App

```python
# backend/ai/domain/people.py
class PeopleDomainAI(DomainAIOperations):
    app_identifier = "people"
    operations = [
        "payroll.validate",         # DQ check on payroll run with KLL rules
        "payroll.explain",          # explain a violation in plain English
        "headcount.report",         # draft headcount report from live data
        "leave.calculate",          # verify leave calculation for an employee
        "certification.alert",      # surface expiring certifications
        "eosi.calculate",           # verify EOSI provision for an employee
    ]

# backend/ai/domain/stores.py
class StoresDomainAI(DomainAIOperations):
    app_identifier = "stores"
    operations = [
        "stock.anomaly",            # detect unusual consumption patterns
        "stockout.predict",         # predict stockouts from consumption trend
        "reorder.suggest",          # suggest reorder quantities
        "count.variance.explain",   # analyze physical count variances
        "transfer.suggest",         # cross-store transfer recommendations
    ]

# backend/ai/domain/fintrust.py
class FinanceDomainAI(DomainAIOperations):
    app_identifier = "fintrust"
    operations = [
        "reconciliation.analyze",   # explain unmatched BRS items
        "treasury.alert",           # BG/LC/loan expiry intelligence
        "accrual.draft",            # monthly accrual journal entry draft
        "variance.explain",         # explain payroll-to-GL variance
    ]
```

---

## 7. BUILD SEQUENCING & RATIONALE

### Why start with People & Workforce

1. **Highest pain, lowest existing coverage.** Hard Task is actively causing
   payroll errors every month. Every month of delay = more manual Excel work
   + compliance risk.

2. **All other apps depend on it.** Finance needs EOSI provisions from People.
   Stores needs employee IDs for MIV requests. Assets needs driver assignments.
   Projects needs payroll cost allocation. People is the foundation.

3. **OrgUnit is already built.** The platform's OrgUnit model is the org chart.
   Departments, cost centers, and reporting lines in GOFSCO map directly to
   the existing data model. No re-architecture needed.

4. **Fastest commercial validation.** An HRMS that is Kuwait-Law-compliant with
   AI payroll validation is immediately differentiable from Hard Task, Sage HR,
   and every generic HRMS in the Kuwait market. It can be sold to any KOC
   contractor.

### Recommended phase sequence

```
Month 1-2:  People MVP (Employee record, Leave, basic Payroll, C&B)
            → replaces Hard Task; immediate GOFSCO go-live
            → Pulse: payroll validation + KLL compliance checks

Month 2-3:  Finance Intelligence (Treasury instruments, BRS, alerts)
            → replaces Excel silos; EOSI provisions auto-flow from People
            → Pulse: BG/LC expiry alerts + bank recon anomalies

Month 3-5:  Smart Stores MVP (Item master, MIV/MRV digital, 4-store network)
            → parallel to Finance; Ahmadi first, then roll to CT/Drilling/PCP
            → Pulse: stock anomalies, stockout prediction

Month 5-6:  People Full (ER, Recruitment, Performance, KPIs, Training)
            → completes the people lifecycle

Month 6-7:  Asset & Fleet
            → depends on Stores (spare parts) and People (driver assignments)

Month 7-8:  Projects & Job Costing
            → aggregates costs from all domains

Month 8+:   Continuous intelligence deepening
            → Pulse learns GOFSCO-specific patterns
            → Cross-domain reports (headcount + cost + project profitability)
```

---

## 8. PLATFORM EXTENSION REQUIREMENTS

Building GOFSCO apps requires minimal platform changes — the platform is designed
to host apps. What needs to be added or confirmed:

### 8.1 New Django apps (backend)

Each app follows the existing pattern (like `emissions/`):
```
backend/people/
backend/fintrust/
backend/stores/
backend/assets/
backend/projects/
```

Each app:
- Imports from `core`, `catalog`, `mdm`, `dq`, `evidence`, `connections`
- Never imported by platform apps (one-way dependency)
- Registers its Pulse domain operations in `ai/domain/{app}.py`
- Registers its manifest in `appregistry/`

### 8.2 MDM reference data to add

The MDM system needs these reference sets added for GOFSCO:
```
- job_grades          (GG1–GG10 or company scale)
- rotation_patterns   (11/1, 1/1, 2/1, 3/1, 5/1)
- leave_calendars     (KLL-30, Kuwaiti-42, Rotation-adjusted)
- allowance_types     (accommodation, vehicle, medical, school, ticket, OT, bonus)
- item_categories     (consumable, spare_part, chemical, asset)
- uom_table           (Pcs, Kg, L, M, Box, Roll, Set, …)
- koc_project_codes   (reference to KOC project register)
- bank_list           (KFIC, Gulf Bank, KFH, NBK, …)
- currency_list       (KWD, USD, EUR)
- store_locations     (Ahmadi, CT, Drilling, PCP)
```

### 8.3 New Connections

```
- Sage 300 connector: read I/C balances, GL entries, PO data (initial migration + delta sync)
- Bank statement parser: CSV/MT940 format → BRS pipeline input
- KOC project data: project codes import (if API available; else manual MDM entry)
- Biometric system: attendance data feed (future)
```

### 8.4 Pulse domain modules

```
backend/ai/domain/people.py    — payroll.validate, leave.calculate, eosi.calculate, headcount.report
backend/ai/domain/fintrust.py  — reconciliation.analyze, treasury.alert, accrual.draft
backend/ai/domain/stores.py    — stock.anomaly, stockout.predict, reorder.suggest
backend/ai/domain/assets.py    — maintenance.alert, certification.check
backend/ai/domain/projects.py  — cost.variance, profitability.report
```

---

## 9. COMMERCIAL PRODUCT ANGLE

The seed customer is GOFSCO. The product is for the **GCC oilfield services market**:

**Target ICP (Ideal Customer Profile):**
- Mid-size oilfield services companies (100–1000 employees)
- Operating in Kuwait, Saudi Arabia, UAE, Qatar
- Working under NOC (National Oil Company) contracts → compliance-heavy
- Currently on Sage 300, SAP B1, Epicor, or Excel
- Kuwaitization / Saudization / Emiratization compliance challenges
- Multiple operational sites, fragmented data

**What makes it defensible:**
1. **Labor law compliance engine** — Kuwait Labor Law rules are encoded as DQ rules.
   This is reusable across every KOC contractor. Adding KSA Labor Law = adding
   another rule set. This is a moat.

2. **NOC project data model** — KOC project codes, cost centers, and reporting
   requirements are embedded. New NOC = add their reference data. Not a custom build.

3. **Pulse knows oilfield services** — the AI knowledge graph is trained on
   oilfield terminology, KOC requirements, standard consumables. Not a generic
   LLM answering HR questions.

4. **Trust layer is the product** — in an industry where KOC audits, HSE compliance,
   and KD-million contract disputes depend on data integrity, a platform that
   assigns every business object a trust score is not optional. It is the audit
   trail that wins disputes.

**Pricing model (initial thinking):**
- Per-employee per-month for People app
- Per-store per-month for Stores app
- Platform fee (catalog + MDM + DQ + Pulse) as base
- Implementation as professional services (not free)

---

## 10. IMMEDIATE NEXT STEPS

1. **Master Architect:** Define the People app data model (Employee, Position, Leave,
   PayrollRun, Allowance, EOSI) as a TASKS.md phase spec

2. **Backend Worker:** Scaffold `backend/people/` with models, migrations, basic DRF
   viewsets — following the `emissions/` pattern

3. **Backend Worker:** Create People MDM reference sets: rotation_patterns,
   leave_calendars, allowance_types, job_grades

4. **Backend Worker:** Implement Kuwait Labor Law DQ rules as DQ rule templates
   in the `dq/` engine (leave split rule, Kuwaitization calendar rule, EOSI base rule)

5. **AI Worker:** Define `backend/ai/domain/people.py` with payroll.validate and
   leave.calculate operations

6. **Frontend Worker:** Design People app shell (employee list, record detail,
   leave calendar, payroll run page) — following platform UI patterns
   (PageContainer, BaseDetailPage, FilteredDataGrid)

7. **Connections Worker:** Build Sage 300 import connector for the item master
   and opening GL balances (for Finance Intelligence bootstrap)
