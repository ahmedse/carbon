# Alamein Campus Test Materials

This folder contains everything needed for a complete end-to-end manual test of the Carbon Data Trust Platform using a new Alamein Campus scenario.

## Contents

| File | Purpose |
|------|---------|
| `ALAMEIN_TEST_JOURNEY.md` | **The main document** — complete step-by-step checklist (Phases 1-7) |
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
| `alamein.admin` | `Alamein_2026` | Alamein campus admin |
| `alamein.medical` | `Alamein_2026` | College of Medicine + Hospital |
| `alamein.transport` | `Alamein_2026` | Transportation |
| `alamein.finance` | `Alamein_2026` | Financial Affairs |
| `alamein.hotels` | `Alamein_2026` | Student Hotels — Sakan Masr |

## Key URLs

| URL | What |
|-----|------|
| http://localhost:5179/carbon/my-data | My Data (L1) |
| http://localhost:8009/admin/ | Django Admin |
| http://localhost:5179/admin/org-units | Org Units management |
