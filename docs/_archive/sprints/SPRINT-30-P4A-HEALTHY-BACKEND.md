# Sprint 30 — P4-A: Healthy Domain App (backend `healthy/`)

**Date:** 2026-08-20
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Flash
**Status:** READY
**Kind:** New Django app. Large. Backend-only.
**Depends on:** P1 (datahub ✅), P2 (integrations/turnkey ✅), P3 (appregistry ✅) — all ACCEPTED.
**Source of truth (READ FIRST, no forks):** `docs/DESIGN-PLATFORM.md` §8 — it has the exact models, 5 pipelines, and module table. Do not duplicate its models here; follow it.

## What this phase builds

Healthy Foods Factory is the first full "domain app" proving the whole data-product
loop end-to-end: **ERP snapshot → Dataset version (DQ) → TurnKey train/serve →
PredictionRecord → dashboard**. Backend = new `backend/healthy/` Django app that
reads a legacy Arabic ERP (Azure PostgreSQL, 1,047 decoded views, **read-only**) and
exposes `/carbon-api/healthy/` APIs.

## Files to Read First

- `docs/DESIGN-PLATFORM.md` §8 (the full contract: models, 5 pipelines, module table)
- `backend/datahub/models.py` + `serializers.py` + `views.py` — the seams Healthy consumes (Dataset, DatasetVersion, approve/reject)
- `backend/integrations/turnkey/models.py` — `TurnKeyConfig`, `TurnKeyModelLink`, `PredictionRecord` (already built in P2)
- `backend/appregistry/models.py` — `AppManifest` / `AppActivation` (already built in P3)
- `backend/connections/models.py` — `DataSource` (the read-only ERP connection)
- `backend/ai/protocol.py` + `backend/ai/domain/` — the `DomainAIOperations` ABC pattern (see existing `ai/domain/emissions.py`)
- `backend/config/urls.py` — how apps register (`path(f'{api_prefix}/…/', include('….urls'))`)
- `.ai-toolkit/shared/data-layer.md`, `.ai-toolkit/shared/cbac.md`, `.ai-toolkit/shared/api-contract.md`

## Files to Change

- `backend/healthy/models.py` — NEW: `ERPSnapshot`, `LoadoutSheet`, `RepHealthCard` (+ any pipeline model §8.4 specifies), read-only `DataSource` wiring
- `backend/healthy/services.py` — NEW: ERP snapshot/extract service + pipeline orchestration (thin views, business logic here)
- `backend/healthy/serializers.py` — NEW
- `backend/healthy/views.py` + `backend/healthy/urls.py` — NEW; register under `/carbon-api/healthy/`
- `backend/healthy/domain_ai.py` — NEW: `HealthyDomainAI` implementing the `DomainAIOperations` ABC
- `backend/healthy/admin.py` — NEW (register all models)
- `backend/healthy/apps.py` — NEW
- `backend/healthy/management/commands/register_healthy_app.py` — NEW (registers AppManifest + 5 modules + seed DataSource; §8.2 / §8 reference)
- `backend/healthy/tests/` — NEW (≥10 tests)
- `backend/config/settings.py` — add `'healthy'` to `INSTALLED_APPS`
- `backend/config/urls.py` — add `path(f'{api_prefix}/healthy/', include('healthy.urls'))`

## Implementation (summary — §8 is authoritative)

1. **Read-only ERP connection** — `DataSource(source_type='database')` to Azure PostgreSQL
   (`healthy_legacy_2026`), `connection_config` encrypted. **Never write to the ERP.**
2. **5 modules** (core.Module, CBAC via ScopedRole): `healthy-sales`, `healthy-returns`,
   `healthy-inventory`, `healthy-collections`, `healthy-production`.
3. **5 pipelines**, each = snapshot → DatasetVersion(DQ) → TurnKey link → PredictionRecord:
   1. Returns/Load-Out demand (LIVE model `healthy-returns` v1) — `healthy-returns-panel`
   2. Churn / rep retention — `healthy-churn-panel`
   3. Demand forecast / dead-stock — `healthy-sales-lines`
   4. AR collections prioritization — `healthy-ar-aging`
   5. Transaction-type classifier (DQ guard) — `healthy-transaction-classifier-panel`
4. `HealthyDomainAI` via `DomainAIOperations` ABC (scope is handled by the guards — do NOT
   write scope checks in the domain class).
5. API under **`/carbon-api/healthy/`** (RULE_4). The old inline note "/api/v1/healthy/" is
   stale — the correct prefix is `api_prefix` from `config/urls.py`.

### DO NOT TOUCH

- Azure PostgreSQL ERP is **read-only** — no writes/DDL to it.
- `carbon-frontend/**` (that's P4-B).
- Existing P1/P2/P3 apps (`datahub/`, `integrations/`, `appregistry/`) — READ them, do not edit.
- `backend/ai/protocol.py` (platform ABC) — `HealthyDomainAI` plugs INTO it, never modifies it.

## Verification Gate (run ALL, paste FULL output)

```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations healthy   # generates 0001
/home/ahmed/aast/carbon/.venv/bin/python manage.py migrate healthy
/home/ahmed/aast/carbon/.venv/bin/python -m pytest healthy -q               # ≥10 tests
/home/ahmed/aast/carbon/.ai-toolkit/scripts/verify.sh backend
/home/ahmed/aast/carbon/.ai-toolkit/scripts/verify.sh antipatterns
```

## Output contract

Append to `TASK-RESULTS.md` (Part B handoff format): Summary → Task results → Files Changed →
Verification Output (full paste) → Deviations → Issues Found → verdict.

## Notes for the Master

- P4-A before P4-B. ERP stays read-only; Carbon writes only to its own models.
- If the live Azure ERP is unreachable in dev, build the extract behind the
  `DataSource.connection_config` seam and use a **mocked/recorded** snapshot in tests
  (never depend on a live external DB for the test gate). Flag this clearly in Deviations.
- Commit with `feat(healthy): P4-A — Healthy domain app backend (5 pipelines, read-only ERP)`.
