# Nibras — نبراس
## AI-Native Enterprise Platform for Mid-Market Oilfield Services & Manufacturing
### Master Strategy & Product Definition Document

> **Status:** Living document (v0.1 — 2026-08-30). Supersedes the ad-hoc GOFSCO
> vision draft. Expect this to change as the market and the seed engagement evolve.
> **Author:** Master Architect
> **Owned by:** ClearTurn (parent company). Nibras is ClearTurn's product; all platform IP is ClearTurn's.
> **Anchor customer:** GOFSCO (Gas & Oil Field Services Company, Kuwait — ~500 employees)
> **Built on:** ClearTurn Trust Platform (Django + React) + Pulse (in-hand AI engine)
> **Instance context:** Nibras is **one instance** in ClearTurn's product line. For the
> umbrella architecture (all instances, apps, isolation model) see
> `docs/CLEARTURN-PLATFORM-ARCHITECTURE.md`.
> **Name meaning:** نبراس / *Nibras* — "beacon / lantern." The light that shows the way.

---

## 0. HOW TO READ THIS DOCUMENT

This is the single source of truth for the Nibras product and business. It has three
audiences and three layers:

| Layer | Sections | Audience |
|-------|----------|----------|
| **Strategy** | 1–5 | Founders, investors, GOFSCO management |
| **Product & Architecture** | 6–11 | Architects, engineers, product |
| **Execution & Commercial** | 12–18 | Delivery leads, sales, operations |

The three **binding decisions** made in this document (do not silently reverse):

1. **IP model:** **ClearTurn** (the parent company) owns all platform IP; Nibras is
   ClearTurn's product. GOFSCO is **anchor customer + design partner**, NOT owner.
   (Reverses the "build-transfer-operate / you own the code" clause in the 2026-07-29
   proposal.)
2. **Compliance is a first-class product capability, not a feature.** Every regulated
   figure is traceable to the versioned rule that produced it.
3. **Prove = one legally-signable payroll month.** Narrow but 100% correct beats broad
   but approximate. Depth of compliance is never deferred; breadth of modules is.

---

## 1. EXECUTIVE SUMMARY

Nibras is an **AI-native enterprise platform** for mid-market (50–500 employee)
oilfield-services and manufacturing companies in the GCC. It replaces the typical
patchwork — a basic accounting system (Sage 300), an unreliable HR/payroll tool
(Hard Task), Excel for everything finance touches, and shared-drive chaos for
documents — with **one governed platform** where:

- All business data lives once, correctly, with lineage and ownership (**Data Trust**).
- Every regulated number (payroll, indemnity, GOSI, WPS) is **provably compliant** and
  traceable to the exact rule version that produced it.
- Every employee has an **AI coworker** (Pulse) that understands the business, works on
  live data, alerts before problems happen, and drafts the manual work — but never acts
  without human approval.

**The wedge:** a narrow, fully-compliant HR + Payroll core that replaces Hard Task and
survives a Kuwait labor lawyer's signature. Land there. Expand to Stores, Documents,
Finance intelligence, and cross-domain AI — module by module, each with its own go-live
and its own value.

**The business:** Nibras is a **product company**, not a bespoke services shop. GOFSCO is
customer #1 and design partner. The same compliant core resells to every KOC/NOC
contractor and mid-market industrial in the GCC. The compliance engine (Kuwait Labor
Law, GOSI/PIFSS, WPS today; KSA/UAE tomorrow) is the moat.

---

## 2. THE COMMERCIAL MODEL — IP, OWNERSHIP & THE ANCHOR DEAL

> **This section overrides the 2026-07-29 proposal's build-transfer-operate model.**

### 2.1 The decision

Nibras is a **product owned by ClearTurn** (the parent company). The platform IP (Carbon
Data Trust core, Pulse engine integration, the compliance rule library, all domain apps)
is **owned by ClearTurn**. GOFSCO does **not** own the code.

Why: if the first customer owns the code, there is no product to sell to the second
customer. A services model bills per bespoke build; a product model builds once and
licenses many. The entire "make a business of it" ambition depends on retaining IP.

### 2.2 What GOFSCO gets instead of ownership (the anchor package)

GOFSCO is giving something rare — real data, real users, a real compliance gauntlet, and
a reference logo. They must be rewarded richly, just not with the IP:

| Instead of ownership | GOFSCO receives |
|----------------------|-----------------|
| Source code ownership | **Source code escrow** — released only if Nibras ceases to operate/support |
| Perpetual free use | **Perpetual license** at anchor pricing (deep discount, price-locked) |
| Full control | **Roadmap influence** — a permanent seat in quarterly roadmap planning for 3 years |
| One-time build | **Preferential pricing** on every future module (anchor rate, never list price) |
| — | **Co-marketing rights** — named as founding customer; case study revenue-share optional |
| — | **Data sovereignty guarantee** — their data is theirs, exportable, never shared cross-tenant |
| — | **On-prem or private-cloud deployment** option (their servers, their control) |

### 2.3 Deal structure

- **Phase 1 (HR + Payroll):** fixed-price build at anchor rate, funded by GOFSCO. This
  funds the reusable compliant core — but Nibras owns the output.
- **Phases 2+:** modular, each a separate SOW at anchor pricing. Go/no-go gate per phase.
- **Ongoing:** annual license + support (SaaS-style), anchor-locked.
- **Decision gate preserved:** if Phase 1 fails to deliver a compliant, signed-off
  payroll month, GOFSCO keeps a working HR system and walks away with no further
  obligation. This de-risks their commitment and forces Nibras to prove the hardest thing
  first.

### 2.4 The two-hat discipline

Every hour of GOFSCO work must be classified:

- **Product-core hours** (reusable IP): standard compliant payroll, leave engine, GOSI/WPS,
  document vault, inventory core → **Nibras-owned, cross-sellable.**
- **Customer-specific hours** (GOFSCO config): their rotation patterns, Kuwaitization
  rules, their chart of accounts, their KOC project codes → **delivered to GOFSCO,
  parameterized so the same engine serves other rotation/nationalization regimes.**

The art: build GOFSCO's specifics as **configuration of a general engine**, never as
hard-coded GOFSCO logic. Rotation = a configurable schedule type, not `if company ==
GOFSCO`. That discipline is what makes customer #2 a config exercise, not a rebuild.

---

## 3. MARKET & POSITIONING

### 3.1 Ideal Customer Profile (ICP)

| Attribute | Target |
|-----------|--------|
| Size | 50–500 employees (GOFSCO ≈ 500 — top of band) |
| Sector | Oilfield services, industrial services, manufacturing, contracting |
| Geography | Kuwait first → GCC (KSA, UAE, Qatar, Oman, Bahrain) |
| Client base | Works under NOCs (KOC, Saudi Aramco, ADNOC) — compliance-heavy |
| Current stack | Sage 300 / SAP B1 / Odoo / Excel + a weak HR tool |
| Pain | Labor-law compliance, fragmented data, manual reconciliation, no visibility |
| Buyer | Owner/GM/CFO — decides in weeks, not quarters |

### 3.2 Positioning statement

> For mid-market GCC industrial companies drowning in Excel and non-compliant legacy
> tools, Nibras is the AI-native enterprise platform that keeps you **legally compliant
> by construction** and gives every employee an **AI coworker** — without SAP-level cost
> or complexity. Unlike traditional ERP (a data graveyard you operate) or generic HR SaaS
> (compliance bolted on), Nibras is built on a Data Trust core where every regulated
> number is provably correct and every decision is informed by live, governed data.

### 3.3 Competitive landscape

| Competitor class | Examples | Where Nibras wins |
|------------------|----------|-------------------|
| Tier-1 ERP | SAP, Oracle | Cost, speed, no army of consultants, AI-native |
| Mid ERP | SAP B1, Odoo, Dynamics BC | Compliance-by-construction, AI coworker, oilfield fit |
| Local HR/payroll | Hard Task, Menaitech, local Sage HR | Real KLL/GOSI/WPS correctness + lineage + AI |
| Generic AI SaaS | Copilots on top of old data | Governed data underneath; not a chatbot on chaos |
| Excel | — | Everything (but respect that Excel is the incumbent to beat) |

### 3.4 The moat

1. **Compliance rule library** — Kuwait Labor Law, GOSI/PIFSS, WPS encoded as versioned,
   auditable rules. Each new jurisdiction (KSA: GOSI+WPS+Mudad+Nitaqat; UAE: WPS+MOHRE) is
   an additive rule set, not a rebuild. This compounds with every customer.
2. **NOC domain model** — KOC/Aramco/ADNOC project structures, cost centers, HSE
   certifications pre-modeled.
3. **Data Trust lineage** — in an audit-driven industry, "prove why this number is this
   number, back to the rule version" wins contract disputes and passes ministry audits.
4. **Pulse trained on the domain** — not a generic LLM; knows oilfield consumables,
   rotation payroll, indemnity law.

---

## 4. THE PAIN NIBRAS SOLVES (evidence-based, from GOFSCO source documents)

### 4.1 HR & Payroll (from "Issues with Hard Task HRMS")
- Non-compliant Kuwait Labor Law leave advance (calendar-split not honored) → manual Excel every cycle
- No rotation status (1/1, 2/1, 3/1, 5/1) → manual monthly salary adjustment
- No Kuwaitization (42-day leave, 21-day salary basis, KOC standards) → separate manual track
- EOSI/indemnity base excludes Job Bonus, OT, incentives → understated provisions, legal exposure
- No attendance-permission logic → wrong auto-deductions for business meetings
- No C&B ledger (accommodation, vehicle, medical, school, tickets, OT, bonuses) → all in Excel
- No HR reporting (promotions, increments, budget-vs-actual, dept salary) → manual Excel
- Missing modules: Recruitment, Org structure, Performance, KPIs, Training, Employee Relations, Penalties, Disciplinary

### 4.2 Finance (from "tectona-fin depts requirements")
- Loans, Bank Guarantees, LCs, Bank Reconciliation all in separate Excel files
- Daily manual journal entries in Sage 300
- No centralized document vault for bank facility letters/confirmations
- No loan rollover / BG / LC expiry reminders → penalty risk

### 4.3 Stores & Inventory (from "Stores Operations & ERP Workflow Report")
- Hardcopy MIV/MRV manually transcribed into Sage → data errors
- Physical movement before system update → wrong balances
- 4 stores (Ahmadi, CT, Drilling, PCP), no unified item master → duplicates
- No bin/zone/status dimension (available/reserved/quarantine/damaged/expired)
- No chemical lot/expiry/SDS enforcement → HSE/KOC risk
- Physical counts on exported Excel → broken blind-count discipline
- Reporting = export-to-Excel → retrospective, manual

### 4.4 The one-line diagnosis
> Every handoff between systems is a manual step. Every manual step is time, risk, and
> frustration. It is not a people problem — it is a systems problem.

---

## 5. GUIDING PRINCIPLES (the constitution)

1. **Compliance by construction.** Regulated outputs cannot be "approximately right."
   Narrow scope until it is 100% correct; never ship 80%-correct payroll.
2. **Traceability is the product.** Every regulated number links to its inputs and the
   versioned rule that computed it. One click from figure to law.
3. **AI prepares, human decides, system executes.** Pulse never acts on financial
   transactions without explicit human approval.
4. **Configuration over code.** Customer specifics are parameters of a general engine,
   never hard-coded branches. Customer #2 is a config, not a rebuild.
5. **Land narrow, expand by evidence.** One compliant module live and loved before the
   next. Each phase earns the right to the next.
6. **Be a layer before a replacement.** Augment the system of record (Sage GL) with
   intelligence long before attempting to replace it. Rip out the GL last, if ever.
7. **Bilingual by default.** Arabic + English, RTL-native, from day one — not a
   translation afterthought.
8. **ClearTurn owns the IP; reward the anchor.** All platform IP is ClearTurn's; give
   GOFSCO everything of value except ownership.

---

## 6. PRODUCT ARCHITECTURE — THE FOUR LAYERS

```
┌───────────────────────────────────────────────────────────────────────┐
│  LAYER 4 — AI COWORKER (Pulse)                                        │
│  NL Q&A (AR/EN) · proactive alerts · document AI · report drafting    │
│  Domain ops per app · guards (scope/access/mutation) · human-in-loop  │
├───────────────────────────────────────────────────────────────────────┤
│  LAYER 3 — BUSINESS APPLICATIONS (domain apps)                       │
│  People · Stores · Finance · Documents · Procurement · Assets · Proj  │
│  Each: transactional models + workflows + domain compliance rules     │
├───────────────────────────────────────────────────────────────────────┤
│  LAYER 2 — DATA TRUST & GOVERNANCE                                    │
│  Catalog (schemas) · MDM (reference data) · DQ engine (validation)    │
│  Compliance Rule Library (versioned) · Calculation Engine (compute)   │
│  Evidence (document vault) · Connections (ETL) · RBAC/OrgUnit         │
├───────────────────────────────────────────────────────────────────────┤
│  LAYER 1 — TRANSACTIONAL FOUNDATION                                   │
│  PostgreSQL (single source of truth) · Redis (queue/cache)            │
│  Audit log · security · workflow engine · API-first (every fn = API)  │
└───────────────────────────────────────────────────────────────────────┘
```

### 6.1 Key architectural decisions

| Decision | Rationale |
|----------|-----------|
| Single database | No integration seams; Finance/HR/Stores share one truth |
| API-first | Every function callable programmatically; future integrations trivial |
| Web-based, responsive | Any device — desktop, tablet, phone; no install |
| On-prem OR cloud | Customer chooses; data sovereignty preserved |
| Modular apps | Start with People; add modules without re-platforming |
| Metadata-driven schema | New entities without schema migrations where possible |
| In-hand AI engine | Pulse runs in-process; no hard dependency on external AI uptime; graceful degradation |

### 6.2 THE CRITICAL DISTINCTION — Validation vs Calculation

> This is the architectural gap the original vision hand-waved. It is now explicit.

The Data Trust platform's **DQ engine VALIDATES** data — it returns pass/fail/warn.
It does **not** compute payroll. Regulated outputs need a separate **Calculation Engine**
that *produces* correct numbers.

```
┌─────────────────────┐      ┌──────────────────────┐      ┌────────────────────┐
│  Calculation Engine │  →   │  Result (payroll run,│  →   │   DQ Engine        │
│  (COMPUTES the      │      │  EOSI provision,     │      │  (VALIDATES the    │
│   correct figure    │      │  GOSI contribution)  │      │   result against   │
│   from law + policy)│      │  + lineage metadata  │      │   compliance rules)│
└─────────────────────┘      └──────────────────────┘      └────────────────────┘
        ▲                                                            │
        │                                                           ▼
   Compliance Rule Library (versioned)                    Pulse explains any
   - KLL leave-split formula v2026.1                       failure in plain
   - EOSI base composition v2026.1                         Arabic/English +
   - GOSI/PIFSS contribution table v2026.1                 suggests the fix
   - WPS file format spec v2026.1
```

- **Compliance Rule Library:** versioned, dated, source-cited (article/regulation). Each
  rule has: identifier, version, effective date, jurisdiction, formula/table, source
  reference, test cases.
- **Calculation Engine:** deterministic, testable, produces a result **plus** lineage
  (which rule version, which inputs).
- **DQ Engine:** validates the computed result against independent compliance checks
  (defense in depth — the calculator and the validator are separate so a bug in one is
  caught by the other).
- **Pulse:** explains, never computes the authoritative number. It can *draft* and
  *suggest*, but the Calculation Engine is the source of the legally-relied-upon figure.

### 6.2.1 Compliance engine readiness — architecture now, rules later (a deliberate decision)

We build the **structure** now and defer the **authoritative rule values** until the
engagement moves forward. This is a decision, not a gap:

- The **Calculation Engine is rule-agnostic** — it executes rules supplied as *data*, so it
  can be built, tested, and reviewed before any real Kuwait figures exist.
- The **Compliance Rule Library defines the seam** — the schema every rule must fill
  (id, version, effective date, jurisdiction, formula/table reference, source citation,
  test cases). Populated later.
- **No authoritative Kuwait figures are encoded until sourced.** Any example rules used to
  exercise the engine are marked **`NON-AUTHORITATIVE — TEST ONLY`** and are excluded from
  production paths by construction.
- When the real **KLL / PIFSS / WPS** sources arrive, they **drop into the seam without
  engine changes** — only new rule records, versioned and dated.

Effect: everything except the rule *values* proceeds in parallel with the deal. The day the
sources land, Nibras is one data-load away from a compliant run — not one rebuild away.

### 6.3 Compliance lineage (the demo that wins deals)

For any regulated figure, one click shows:
```
Net EOSI provision (Employee: Narsimha R.) = KD 1,847.500
  ← Calculation Engine run #4821 (2026-08-31)
  ← Rule: KLL Article 51 — EOSI accrual v2026.1 (effective 2026-01-01)
      base = basic + [vehicle allowance, incentive bonus]  (policy config GOFSCO-CB-02)
      formula = 15 days/yr (yrs 1-5) + 30 days/yr (yr 6+), pro-rated
  ← Inputs: basic KD 950, vehicle KD 120, incentive KD 80, service 6.4 yrs
  ← Validated: DQ rule "EOSI base completeness" PASS, "EOSI within band" PASS
```

That is the moat made visible. An auditor, a ministry inspector, or a departing
employee's lawyer gets a complete, defensible answer in one screen.

---

## 7. THE BUSINESS APPLICATIONS (module map)

| App | Django app | Phase | Nature | Reusable core vs GOFSCO-specific |
|-----|-----------|-------|--------|----------------------------------|
| **People** | `people/` | 1 | Transactional + compliance | Core: standard KLL payroll, leave, EOSI, GOSI, WPS. GOFSCO: rotation, Kuwaitization, C&B breadth |
| **Documents** | uses `evidence/` | 2 | Vault + search | Fully reusable |
| **Stores** | `stores/` | 2 | Transactional + mobile | Core: item master, MIV/MRV, ABC, reorder. GOFSCO: 4-store network, chemical/SDS |
| **Finance** | `fintrust/` | 3 | Intelligence → GL (later) | Core: treasury, BRS, alerts, doc vault. GOFSCO: bank list, Sage sync |
| **Procurement** | `procurement/` | 3 | Transactional workflow | Core: PR/PO/GRN/3-way match. GOFSCO: approval matrix |
| **Assets & Fleet** | `assets/` | 3-4 | Lifecycle + maintenance | Core: asset registry, PM schedules. GOFSCO: vehicle checklist, KOC certs |
| **Projects/Job Costing** | `projects/` | 4 | Cost aggregation | Core: job register, cost allocation. GOFSCO: KOC project codes |
| **AI Coworker** | `ai/` (Pulse) | 1-4 | Cross-cutting | Fully reusable; domain packs per app |

Each domain app **imports** platform capabilities (catalog, mdm, dq, evidence,
connections, rbac) and **never** is imported by them — one-way dependency, so apps are
composable and removable.

---

## 8. APP DEEP-DIVE: PEOPLE & PAYROLL (Phase 1 — the wedge)

> The hardest thing, built first, to the highest standard. The proposal calls HR "easy";
> GOFSCO's own documents prove payroll is the hardest. We treat it accordingly.

### 8.1 Scope split — reusable core vs GOFSCO depth

**Reusable compliant core (product IP):**
- Employee master (governed data product with DQ score)
- Standard KLL leave accrual + calendar-correct leave-pay split
- EOSI/indemnity provision (configurable base composition)
- GOSI/PIFSS contribution calculation
- WPS file generation (Kuwait format)
- Loans & installment deductions
- Payslip generation + employee self-service
- Payroll run as a governed, lineage-tracked dataset

**GOFSCO-specific depth (configuration of the general engine):**
- Rotation patterns (1/1, 2/1, 3/1, 5/1) as configurable schedule types
- Kuwaitization rules (42-day leave, 21-day salary basis) as a nationalization-policy config
- Full C&B ledger (accommodation tier, vehicle, medical, school, tickets)
- Attendance-permission logic (no-deduction categories)
- KOC-linked certifications (H2S etc.) with expiry tracking

### 8.2 The payroll run as a governed pipeline

```
Inputs (governed data products):
  Employee master · Attendance · Leave records · Permissions · One-off items · C&B
        │
        ▼
  Calculation Engine (applies Compliance Rule Library + company policy config)
        │
        ▼
  Payroll Run dataset (each payslip line has lineage to its rule + inputs)
        │
        ├──▶ DQ validation (KLL split correct? EOSI base complete? GOSI right? min wage?)
        │        │ fail → Pulse explains + suggests fix → human corrects → re-run
        │        │ pass ▼
        ├──▶ WPS file generated (bank-ready)
        ├──▶ GL journal entries drafted → (Phase 3: Sage/Nibras Finance)
        └──▶ EOSI provisions → Finance
```

### 8.3 Phase 1 compliance rules (the must-pass set)

| Rule | Source | Type |
|------|--------|------|
| Leave-pay calendar split | KLL (leave straddling months paid per calendar month) | Calculation + DQ |
| Annual leave accrual | KLL 30-day / configurable | Calculation |
| EOSI accrual & base | KLL Art. 51+ | Calculation + DQ |
| GOSI/PIFSS contribution | PIFSS tables | Calculation + DQ |
| WPS file format | Central Bank / MoSA spec | Format generation + DQ |
| No negative net pay | Company policy | DQ hard block |
| Permission-aware deductions | Company policy | Calculation |

### 8.4 Full People modules (Phase 1 core + Phase 4 completion)
M1 Org & Positions · M2 Employee Master · M3 Leave & Absence · M4 Payroll Engine ·
M5 Compensation & Benefits · M6 End of Service · M7 Attendance & Permissions ·
M8 Employee Relations (P4) · M9 Recruitment (P4) · M10 Performance & KPIs (P4) ·
M11 Training & Certifications (P4)

### 8.5 Pulse in People
- `payroll.validate` — run compliance checks, return failures with plain-language reasons
- `payroll.explain` — "why is this figure this?" back to rule + inputs
- `leave.calculate` — verify an employee's leave entitlement/accrual
- `eosi.calculate` — verify indemnity provision
- `certification.alert` — surface expiring Iqama/visa/H2S/medical
- `headcount.report` — draft dept headcount report from live data (AR/EN)

---

## 9. APP DEEP-DIVES: OPERATIONS, FINANCE, INTELLIGENCE (summaries)

> Full specs authored per-phase in TASKS.md when dispatched. Summaries here for the map.

### 9.1 Stores & Inventory (Phase 2 — greenfield, no legacy to fight)
Item master (MDM, duplicate-detected, chemical SDS enforced) · MRV digital receiving ·
MIV digital issue (approval → pick/scan → acknowledge) · ABC classification ·
min/max + auto-reorder PR · blind physical count · 4-store network + transfers ·
live KPIs (turnover, holding cost, stockout, service level).
Pulse: `stock.anomaly`, `stockout.predict`, `reorder.suggest`, `count.variance.explain`,
`transfer.suggest`.

### 9.2 Documents (Phase 2 — uses Evidence module)
Central repository · full-text search · document linking to any transaction ·
bank facility letters, contracts, certificates, SDS, signed MIV/MRV.
Pulse: document AI (upload invoice PDF → extract → draft entry).

### 9.3 Finance Intelligence (Phase 3 — layer first, GL last)
**Stage A (layer on Sage):** Treasury instruments (loans/BG/LC as governed data products
with expiry alerts) · Bank Reconciliation pipeline (statement vs GL match) · document
vault · accruals automation (loan interest, EOSI provisions) → journal drafts to Sage.
**Stage B (only after trust earned):** GL, AP, AR, budgeting, fixed assets, procurement
3-way match — considered for replacing Sage, not assumed.
Pulse: `reconciliation.analyze`, `treasury.alert`, `accrual.draft`, `variance.explain`.

### 9.4 Assets & Projects (Phase 3-4)
Asset registry · vehicle fleet (digital daily checklist from GOFSCO's paper form) ·
maintenance work orders (→ Stores spares) · KOC project register · job costing (costs
aggregate from People, Stores, Assets).

### 9.5 Intelligence activation (Phase 4)
Cross-module NL Q&A (AR/EN) · system-wide proactive alerts · document AI everywhere ·
role-based dashboards with AI commentary · multi-step workflow automation
(purchase-to-pay, hire-to-retire).

---

## 10. THE AI COWORKER (Pulse) — DETAILED

### 10.1 What it is
An in-process, governed AI coworker woven into every module — not a bolt-on chatbot. It
understands the business ontology (PO, GL account, vendor, rotation, EOSI), works on live
governed data, respects RBAC to the field level, and operates human-in-the-loop.

### 10.2 The collaboration model
> **AI prepares and presents. Human reviews and decides. System executes.**

### 10.3 Capabilities
- **NL Q&A (AR/EN):** "كم عدد الفواتير غير المدفوعة؟" / "Show overdue POs" — answers from live data
- **Proactive alerts:** stock reorder, payment due, budget variance, stale approval,
  statistical anomaly, missing compliance step, expiring cert/BG/LC/Iqama
- **Document AI:** invoice PDF → extracted data → drafted journal entry (human approves)
- **Report drafting:** "draft September headcount report by department" → structured draft
- **Compliance explanation:** any regulated figure → traced to rule + inputs, in plain language

### 10.4 Guardrails (what it will NOT do)
- No financial action without human approval
- No data to unauthorized users (RBAC enforced pre-call)
- No payments/transfers execution
- No config changes
- No cross-tenant data sharing
- No computing the authoritative regulated number (Calculation Engine does that; Pulse drafts/explains)

### 10.5 Alert taxonomy (illustrative)
| Type | Example | Trigger |
|------|---------|---------|
| Stock | Drilling fluid X-452 at 45 (min 60) | Below reorder point |
| Financial | Dept Y budget +18% vs plan | Variance > threshold |
| Payment | Invoice #4521 due in 3 days, KD 12,500 | Due-date approaching |
| Approval | PO #231 pending 2 days | Stale approval |
| Anomaly | 3 POs to Vendor Z this week (avg 0.5) | Statistical outlier |
| Compliance | Month-end: bank rec not done | Missing workflow step |
| HR-compliance | 6 field staff H2S expiring < 60 days, no training booked | Cert expiry + no remediation |

---

## 11. NON-FUNCTIONAL REQUIREMENTS

| Area | Requirement |
|------|-------------|
| **Security** | Role-based access to field level; maker-checker on sensitive actions; JWT auth; encrypted at rest/in transit |
| **Audit** | Immutable audit log — who created/approved/changed/posted, when; no deletion of posted transactions (reversal only) |
| **Compliance** | Versioned rule library; every regulated figure traceable; jurisdiction-parameterized |
| **Availability** | Graceful AI degradation (deterministic fallback if Pulse unavailable); tested backup/DR |
| **Performance** | Mid-market volumes (≤500 employees, ~dozens of stock moves/day) — comfortably within platform capacity |
| **i18n** | Arabic + English, RTL-native, dual-language throughout |
| **Data sovereignty** | Customer data exportable, never shared cross-tenant; on-prem/private-cloud option |
| **Mobile** | Responsive web; barcode/QR scanning for stores; self-service for employees |

---

## 12. IMPLEMENTATION ROADMAP

> Reworked from the proposal's 24-month plan to reflect: compliance-first Phase 1,
> Finance-as-layer-before-replacement, and explicit go/no-go gates.

### Phase 1 — People (Months 1–6) · GATE
**Goal:** Replace Hard Task with a fully KLL/GOSI/WPS-compliant payroll core.
- Platform core hardening (governance, security, workflow, audit — reused by all)
- Employee master, leave, **compliant payroll**, loans, indemnity, self-service
- Compliance Rule Library v1 (Kuwait) + Calculation Engine + DQ validation
- GOFSCO config: rotation, Kuwaitization, C&B
- Data migration from Hard Task
- **GATE:** one real month-end payroll, fully compliant, lawyer-signable, rule-traceable.
  Pass → continue. Fail → GOFSCO keeps working HR, no obligation.

### Phase 2 — Operations (Months 7–12)
Digital stores (greenfield) + documents. ABC, reorder, KPIs, blind count, 4-store network.
Central document repository + search. **Go-live:** stores digitized, stockouts visible.

### Phase 3 — Finance (Months 13–20)
**Stage A first:** Finance intelligence layer on Sage (treasury, BRS, alerts, accruals,
doc vault). **Stage B (gated):** consider GL/AP/AR/procurement replacement only after the
layer proves trust. **Go-live:** month-end close 3–5 days → 1–2 days.

### Phase 4 — Intelligence (Months 21–24)
Activate Pulse across all modules: cross-module NL Q&A, system-wide alerts, document AI,
role dashboards, workflow automation. **Go-live:** full Nibras, AI coworker everywhere.

### Value delivered at every step
Each phase has its own go-live and ROI — value is not deferred to the end.

---

## 13. INVESTMENT & RETURNS (framework)

### 13.1 What is being funded
Platform core · business modules · data migration · training/adoption (AR+EN) ·
infrastructure. Note: Phase 1 funds the reusable compliant core — **ClearTurn retains the
IP** (see §2); GOFSCO gets anchor pricing + perpetual license + escrow, not ownership.

### 13.2 Expected returns (from proposal, retained as targets)
| Category | Annual benefit |
|----------|----------------|
| Finance efficiency | 60–70% faster month-end (3–5d → 1–2d) |
| Procurement control | 5–10% cost reduction (3-way match) |
| Inventory optimization | 15–25% holding-cost reduction (ABC + auto-reorder) |
| HR accuracy | Payroll errors eliminated; 40–50% less HR admin |
| Documents | 2–3 hrs/week saved per knowledge worker |
| Decision speed | Live dashboards + AI Q&A |
| Audit readiness | 50%+ less audit-prep time |

### 13.3 Commercial model (Nibras as product)
- Anchor deal (GOFSCO): fixed-price Phase 1 at anchor rate + annual license/support.
- Future customers: subscription (per-employee for People, per-store for Stores) + platform base fee + implementation services.
- No perpetual per-user list-price lock-in for anchor; standard SaaS pricing for the market.

---

## 14. RISK REGISTER

| # | Risk | Severity | Mitigation |
|---|------|----------|-----------|
| R1 | Payroll ships non-compliant → Phase 1 gate fails, program dies | **Critical** | Treat payroll as hardest thing; Calculation+DQ defense-in-depth; lawyer sign-off before go-live; narrow scope to 100% correct |
| R2 | IP ownership clause signed as-is → no product to resell | **Critical** — *Resolved by decision (ClearTurn owns IP)* | §2 anchor model; escrow/license/pricing instead of ownership; ensure the GOFSCO contract encodes ClearTurn ownership + anchor package before signature |
| R3 | GOFSCO complexity hard-coded → customer #2 = rebuild | High | Configuration-over-code discipline; two-hat hour classification |
| R4 | Scope creep to full ERP in one go | High | Phase gates; land-narrow-expand; Finance as layer before GL replacement |
| R5 | Sage GL replacement (Phase 3B) destabilizes finance | High | Layer-first; GL replacement gated + optional; never rip out system of record early |
| R6 | Solo/small team velocity vs 4-app ERP ambition | High | Sequence hard; reuse platform; don't build all apps at once; AI-assisted delivery |
| R7 | Compliance rules change (law updates) | Medium | Versioned rule library with effective dates; rules are data, not code |
| R8 | Data migration quality (Hard Task/Sage/Excel) | Medium | Data audit up front; DQ profiling on migration; reconciliation gates |
| R9 | AI over-promises / hallucination in regulated output | Medium | Pulse never computes authoritative numbers; human-in-loop; guardrails §10.4 |
| R10 | Adoption resistance (Excel habit) | Medium | Bilingual training; self-service wins; value at every phase; change management |

---

## 15. THE PROVE-IT MILESTONE (definition of Phase-1 success)

> Run one real monthly payroll for GOFSCO — starting with the standard-employee core,
> then extended to rotation + Kuwaitization — that is **fully compliant** with Kuwait Labor
> Law (leave accrual + calendar split + EOSI), produces a **valid WPS file** and correct
> **GOSI/PIFSS** contributions, with **every figure traceable to the rule version** that
> produced it, and that a **Kuwaiti labor lawyer signs off** as correct.
>
> Narrow. Fully correct. Legally real. If it passes, it is sellable to every KOC/NOC
> contractor in Kuwait and validates the entire platform thesis in one shot.

---

## 16. PLATFORM EXTENSION REQUIREMENTS (engineering)

- **New Django apps:** `people/`, `stores/`, `fintrust/`, `procurement/`, `assets/`,
  `projects/` — each imports core/catalog/mdm/dq/evidence/connections; never imported back.
- **New platform capability — Calculation Engine:** `core/calc/` (or dedicated app) —
  deterministic, versioned, lineage-emitting. Separate from the DQ engine.
- **Compliance Rule Library:** `core/compliance/` — rules as versioned data (id, version,
  effective date, jurisdiction, formula/table, source citation, test cases).
- **MDM reference sets:** job grades, rotation patterns, leave calendars, allowance types,
  item categories, UOM, KOC project codes, bank list, currency, store locations,
  nationalization policies, GOSI tables, WPS format specs.
- **Connections:** Sage 300 connector (read balances/GL/PO), bank statement parser
  (CSV/MT940), biometric attendance (future).
- **Pulse domain packs:** `ai/domain/people.py`, `stores.py`, `fintrust.py`, `assets.py`,
  `projects.py`.
- **i18n:** extend dual-language framework to all new apps.

---

## 17. OPEN QUESTIONS (to resolve before/at management briefing)

1. **Contract IP clause** — will GOFSCO accept anchor-customer model (escrow + license)
   over ownership? (If not, renegotiate or reconsider the engagement economics.)
2. **Phase-1 scope line** — is standard-compliant-core the funded deliverable, with
   rotation/Kuwaitization as a defined config work package?
3. **Prove-it definition** — does GOFSCO agree the gate is "one lawyer-signable payroll
   month with rule-traceable lineage"?
4. **Hosting** — on-prem (their servers) or private cloud? Data-sovereignty stance?
5. **WPS/GOSI specifics** — *deferred by decision* (see §6.2.1). Architecture/seam is built
   now; obtain exact current PIFSS tables + WPS file spec + bank requirements once the
   engagement moves forward. No authoritative figures encoded until then.
6. **Team & funding** — who builds Phase 1; what is the anchor fixed price; runway to
   product customer #2?
7. **Brand** — is "Nibras / نبراس" final? Trademark availability in Kuwait/GCC?

---

## 18. NEXT STEPS

**This week**
- Management briefing (present this doc's strategy; confirm anchor model vs ownership)
- Scope confirmation workshop (Phase-1 line; prove-it definition)
- Site survey (IT infra, Sage 300 access, Hard Task export)

**This month**
- Detailed requirements walkthrough (HR/payroll dept — rotation, Kuwaitization, C&B, GOSI/WPS)
- Data audit (Hard Task, Sage, Excel quality → DQ profiling)
- Technical proposal (architecture, security, compliance, Calculation Engine design)
- Commercial proposal (fixed-price Phase 1 anchor + estimates Phases 2–4; anchor package terms)

**Engineering kickoff (post go)**
- Master Architect: author `people/` Phase-1 spec (Employee, Leave, PayrollRun, EOSI,
  GOSI, WPS) + Calculation Engine + Compliance Rule Library design as TASKS.md phases
- Backend: scaffold `people/`, Calculation Engine, Kuwait rule set v1
- Frontend: People shell (employee list, record detail, leave calendar, payroll run page)
- AI: `ai/domain/people.py` (payroll.validate, payroll.explain, leave.calculate)
- Connections: Sage 300 + Hard Task migration audit

---

*نبراس — let's light the beacon.*
