# Alamein Campus Test Materials

This folder contains everything needed for a complete end-to-end manual test of the Carbon Data Trust Platform using a new Alamein Campus scenario.

## Contents

| File | Purpose |
|------|---------|
| `ALAMEIN_CHECKLIST.xlsx` | **Open in Excel** — 5-tab spreadsheet: Checklist (with Status dropdown), Module List, Table List, Calc Rules, Users & URLs |
| `ALAMEIN_TEST_JOURNEY.md` | Full narrative document with all data rows spelled out (Phases 1-7) |
| `evidence/` | Sample evidence files to upload during Phase 3 |
| `evidence/README.md` | Descriptions of each evidence file and which row to attach it to |

## Quick Start

1. Read `ALAMEIN_TEST_JOURNEY.md` — it's the full roadmap
2. Start with **Phase 1** (Foundation) — logged in as `ahmed` / `AdminPa_132`
3. Follow each phase in order
4. Check boxes as you go

## User Accounts

| Username | Password | Role |
|----------|----------|------|
| `ahmed` | `AdminPa_132` | Super admin (use for Phase 1 setup) |
| `alamein.admin` | `Alamein_2026` | Carbon Domain Lead (Alamein Campus) |
| `alamein.medical` | `Alamein_2026` | College of Medicine + Hospital |
| `alamein.transport` | `Alamein_2026` | Transportation |
| `alamein.finance` | `Alamein_2026` | Financial Affairs |
| `alamein.hotels` | `Alamein_2026` | Student Hotels — Sakan Masr |

## Key URLs

| URL | What |
|-----|------|
| http://localhost:5179/carbon/my-data | My Data (L1) |
| http://localhost:5179/admin/org-units | Org Units management |
| http://localhost:5179/admin/users | User management |
| http://localhost:5179/catalog/products | Module (Data Product) management |
| http://localhost:5179/schema-admin/table-manager | Table + Field management |
| http://localhost:5179/catalog/dq-rules | DQ Rules management |
| http://localhost:5179/carbon/admin/rules | Calculation Rules |
| http://localhost:5179/carbon/admin/factors | Emission Factors |
| http://localhost:5179/catalog/policies | Governance Policies |
| http://localhost:5179/carbon/reporting/periods | Reporting Periods |
| http://localhost:5179/carbon/calculations | Run Calculations |
| http://localhost:5179/carbon/verification | Verification |

> **No Django Admin needed.** Everything is in the frontend.
