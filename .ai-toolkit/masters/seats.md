# Master Seats — Path & Track Ownership

**Binding companion to:** `shared/multi-master.md`  
**Updated:** 2026-09-16

Exclusive = other Master must not edit without HANDOFF/ACK.  
Shared = either Master may read; write only when your track owns the change.

---

## Seat: Pulse

**Tracks:** PEC (complete), ECF, Pulse residuals (Capabilities API, ADR-0033, AI suite debt, L2/L4 for AI surfaces), Pulse docs under `docs/pulse/**`.

### Exclusive write
- `backend/ai/**` (host + engine)
- `backend/ai/engine/**`
- `domain_packs/**/processes/**` when seeded for Pulse Capability/Process governance
- `docs/pulse/**`
- `.ai-toolkit/decisions/00{04,05,07,08,09,11,13,14,16,17,21,22,23,24,26,31,32,33,34,35}*` (Pulse/AI ADRs — prefer Pulse to amend)
- AI admin frontend under `carbon-frontend/src/pages/admin/ai/**`, `carbon-frontend/src/shell/AI*.jsx`, `carbon-frontend/src/api/ai*.js`

### Shared (coordinate via COMMS if touching)
- `docker-compose.yml` Pulse sidecars (`pulse-heartbeat`, learning/cognition schedulers)
- `.github/workflows/ci.yml` AI/eval steps
- Root `TASKS.md` / `TASK-RESULTS.md` — **only your sections**
- Local `./manage.sh` stack (**:8009** / **:5179**) — **stack lease** required to kill/restart (`shared/multi-master.md`)

### Must not touch
- NSR phases; `backend/people/**` staff-product thickening; `carbon-frontend/src/apps/{people,my,team}/**` product UI (except AI deep-links explicitly in a Pulse phase)

---

## Seat: Nibras

**Tracks:** NSR (all NSR-*), NIR leftovers consumed by NSR, GOFSCO staff go-live, people/my/team/correspondence product circuits.

### Exclusive write
- `backend/people/**`
- `backend/correspondence/**` (ESS / e-office as staff spine)
- `carbon-frontend/src/apps/{people,my,team}/**`
- `carbon-frontend/src/api/{people,my,team}.js`
- `docs/nibras/**`, `docs/QA-MANUAL-PEOPLE-MY-TEAM.md`
- ADRs 0025/0027/0028/0029/0030 when amending for NSR

### Shared (coordinate via COMMS if touching)
- Local `./manage.sh` stack (**:8009** / **:5179**) — **stack lease** (`shared/multi-master.md`)
- Root `TASKS.md` / `TASK-RESULTS.md` — **only your sections**
- `manage.sh` URL/banner helpers when fixing Nibras QA ops (notify Pulse via INFO)

### Must not touch
- ECF / PEC / Pulse engine phases; `backend/ai/engine/**` internals; Pulse Console/AI workspace product work
- EduOS / GradeVance product tracks (unless COMMS ACK)

---

## Seat: EduOS

**Tracks:** GradeVance design + scaffold, LCT/Rubric config engines, EduOS brand,
education assessment/coaching product. Canonical design:
`docs/eduos/GRADEVANCE-DESIGN.md` · professor journey
`docs/eduos/GRADEVANCE-PROFESSOR-JOURNEY.md` ·
`docs/eduos/GRADEVANCE-PROFESSOR-LIFECYCLE.md` · ADR-0038.

### Exclusive write
- `docs/eduos/**`
- `backend/gradevance/**` (when created)
- `carbon-frontend/src/apps/gradevance/**` (when created)
- `carbon-frontend/src/brands/eduos.js`
- `backend/ai/engine/instances/eduos/**`
- `domain_packs/eduos/**` / GradeVance engine packs (when created)
- ADR-0038 and future EduOS/GradeVance ADRs

### Shared (coordinate via COMMS if touching)
- Local `./manage.sh` stack — **stack lease** (`shared/multi-master.md`)
- Root `TASKS.md` / `TASK-RESULTS.md` — **only EduOS / GradeVance sections**
- Pulse HITL/eval hooks used by GradeVance — REQUEST to Pulse seat

### Must not touch
- Nibras People/Payroll product UI or payroll correctness tracks
- Tectona Healthy product tracks (except shared platform bugs via COMMS)

### Logistics note
Coding may occur in this monorepo while Nibras masters are active. That does
**not** place GradeVance on the Nibras instance. Product home = EduOS.

---

## Seat: Catalog

**Tracks:** Data Trust platform — `catalog` / `dq` / `mdm` / `dataschema` metadata plane,
Data Trust Index, glossary, lineage, freshness, Dataset Hub contracts. Domain-agnostic
(RULE: catalog must not import emissions/hosted apps).

### Exclusive write
- `backend/catalog/**`
- `backend/dq/**` (DQ rules, scorecards, catalog write-back)
- `backend/mdm/**` (reference data / org units as trust producers)
- `carbon-frontend/src/pages/catalog/**`
- `carbon-frontend/src/pages/admin/catalog/**`
- `carbon-frontend/src/api/{catalog,dq,mdm}*.js` (when present)
- `docs/catalog/**`, `docs/data-trust/**` (when created)
- ADRs amending catalog/DQ/MDM Data Trust (e.g. future Trust Index ADR)

### Shared (coordinate via COMMS if touching)
- `backend/dataschema/**` when FieldAccessPolicy / PII masking couples to catalog
- Pulse `api_catalog` / AI grounding that consumes catalog trust — REQUEST to Pulse
- Local `./manage.sh` stack — **stack lease**
- Root `TASKS.md` / `TASK-RESULTS.md` — **only Catalog / Data Trust sections**

### Must not touch
- Pulse engine/host AI phases (`backend/ai/engine/**`) except COMMS ACK for grounding
- Nibras people/my/team product UI
- EduOS / GradeVance product tracks

---

## Adding a seat

1. Add a section here.
2. Add Owner rows on Active focus.
3. Post `DECISION` in `docs/ops/MASTERS-COMMS.md`.
