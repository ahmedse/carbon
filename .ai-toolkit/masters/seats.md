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
- `.ai-toolkit/decisions/00{04,05,07,08,09,11,13,14,16,17,21,22,23,24,26,31,32,33,34}*` (Pulse/AI ADRs — prefer Pulse to amend)
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

---

## Adding a seat

1. Add a section here.
2. Add Owner rows on Active focus.
3. Post `DECISION` in `docs/ops/MASTERS-COMMS.md`.
