# Sprint 32 — P1C: Fold Dataset Hub into Catalog (delete `datahub` app)

**Date:** 2026-08-20
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek V4-Pro  *(multi-step, data-preserving cross-app migration — hard reasoning; RULE_24)*
**Status:** READY
**Kind:** Backend-only refactor. Large. No frontend.
**Depends on:** P1 (`datahub` ✅) + P1B composition (`96f0417` ✅) + P2 turnkey (`866e3a8` ✅).

## Why this phase exists (owner directive, verbatim)

The owner ratified: **"a data product = a complete dataset"**. That unit — `Dataset`
(multi-table, versioned, DQ-gated, contracted, stewarded) — is the *Data Trust* artifact.
There is **no separate "Data Hub" product**; the dataset layer belongs in the **catalog**
(the trust home). This phase removes the redundant `datahub` Django app and folds its 6
models + services + views into `catalog/`, keeping every table and every row intact.

**Hard constraint: NO data loss.** The actual rows live in `dataschema` (untouched).
The governance metadata (`Dataset`, `DatasetVersion`, `DatasetVersionMember`,
`DataContract`, `DataContractViolation`, `DatasetAccessPolicy`) must be **moved, not
dropped** — via the textbook Django "move a model to another app" migration.

## Files to Read First

- `backend/datahub/models.py` — the 6 models to move (full contents)
- `backend/datahub/services.py`, `ingest.py`, `serializers.py`, `views.py`, `admin.py`, `urls.py`, `apps.py`
- `backend/catalog/models.py` — where the models land (note `AssetProfile`, `DataDomain`, `Tag` already here)
- `backend/catalog/urls.py`, `admin.py`, `apps.py` — where routes/admin/AppConfig merge
- `backend/integrations/turnkey/models.py` (the `TurnKeyModelLink.dataset_version` FK), `serializers.py`, `services.py`, `tests/conftest.py`, `tests/test_callbacks.py`
- `backend/config/settings.py` (INSTALLED_APPS) + `backend/config/urls.py`
- `backend/accounts/capabilities.py` (note: `datahub:*` capabilities — see "DO NOT TOUCH")
- `.ai-toolkit/shared/data-layer.md` (move-models migration pattern)

## The 6 models to move (class names UNCHANGED)

`Dataset`, `DatasetVersion`, `DatasetVersionMember`, `DataContract`,
`DataContractViolation`, `DatasetAccessPolicy`.

From `backend/datahub/models.py` → append into `backend/catalog/models.py`.
Move the supporting constants too: `LIFECYCLE_STATES`, `VERSION_STATUSES`.

### Import fixes inside the moved models

- `from dataschema.models import DataTable` → **stays** (catalog already imports it).
- `from catalog.models import DataDomain, CLASSIFICATION_CHOICES` → becomes
  `from .models import DataDomain, CLASSIFICATION_CHOICES` (now same module).
- `from connections.models import DataSource`, `from core.models import Module` → **stay**.
- `Dataset.tags = ManyToManyField('catalog.Tag', ...)` → change string to `'Tag'`.
- `DatasetVersionMember.data_table` already uses `'dataschema.DataTable'` string → **stays**.
- Keep `db_table` **unset** (default `catalog_*`); the rename happens in the migration below.

## The migration (data-preserving — the ONLY hard part, follow exactly)

Django's canonical pattern for moving models between apps: `SeparateDatabaseAndState`
on the *leaving* side (drop from state, keep table), then on the *arriving* side (add to
state, rename table in DB). Because `integrations.turnkey` has an FK to
`DatasetVersion`, the dependency order is strict. Produce **three** migrations:

### 1. `catalog/migrations/XXXX_adopt_datasets.py` (deps: `datahub 0002`)

Rename the 6 tables `datahub_*` → `catalog_*` in the DB and add the 6 models to
catalog's **state** in one operation:

```python
from django.db import migrations, models
import uuid

# Repeat for all 6 models; table renames map datahub_* -> catalog_*.
operations = [
    migrations.SeparateDatabaseAndState(
        database_operations=[
            migrations.AlterModelTable('dataset', 'datahub_dataset', 'catalog_dataset'),
            migrations.AlterModelTable('datasetversion', 'datahub_datasetversion', 'catalog_datasetversion'),
            migrations.AlterModelTable('datasetversionmember', 'datahub_datasetversionmember', 'catalog_datasetversionmember'),
            migrations.AlterModelTable('datacontract', 'datahub_datacontract', 'catalog_datacontract'),
            migrations.AlterModelTable('datacontractviolation', 'datahub_datacontractviolation', 'catalog_datacontractviolation'),
            migrations.AlterModelTable('datasetaccesspolicy', 'datahub_datasetaccesspolicy', 'catalog_datasetaccesspolicy'),
        ],
        state_operations=[
            migrations.CreateModel(
                name='Dataset',
                fields=[  # copy EXACTLY from datahub/models.py (uuid pk, all fields, all FKs as 'catalog.X'/'dataschema.X' strings)
                ],
                options={  # copy Meta (ordering, etc.)
                },
            ),
            # ... DatasetVersion, DatasetVersionMember, DataContract,
            #     DataContractViolation, DatasetAccessPolicy — same treatment
        ],
    ),
]
```

> The `CreateModel` field definitions must mirror `datahub/models.py` **verbatim**
> (same `related_name`s, same `on_delete`, same `unique_together`). Easiest correct
> approach: first append the models to `catalog/models.py`, then run
> `python manage.py makemigrations catalog` to generate a **draft** migration with the
> correct `CreateModel` state ops, then wrap those ops into `SeparateDatabaseAndState`
> with the `AlterModelTable` DB ops. (The draft `makemigrations` would otherwise create
> fresh `catalog_*` tables — you must intercept and wrap it, NOT apply it raw.)

### 2. `integrations/turnkey/migrations/0002_alter_turnkeymodellink_dataset_version.py` (deps: `catalog XXXX`)

Repoint the FK:

```python
migrations.AlterField(
    model_name='turnkeymodellink',
    name='dataset_version',
    field=models.ForeignKey(
        on_delete=models.PROTECT,
        to='catalog.datasetversion',
        related_name='turnkey_links',
    ),
),
```

### 3. `datahub/migrations/0003_remove_models.py` (deps: `turnkey 0002`)

Drop the 6 models from datahub's **state** only (tables now owned by catalog):

```python
operations = [
    migrations.SeparateDatabaseAndState(
        state_operations=[
            migrations.DeleteModel(name='Dataset'),
            migrations.DeleteModel(name='DatasetVersion'),
            migrations.DeleteModel(name='DatasetVersionMember'),
            migrations.DeleteModel(name='DataContract'),
            migrations.DeleteModel(name='DataContractViolation'),
            migrations.DeleteModel(name='DatasetAccessPolicy'),
        ],
        database_operations=[],
    ),
]
```

**After all three are applied, `datahub` has zero models.** Then delete the app:

- Remove `'datahub'` from `INSTALLED_APPS` (`backend/config/settings.py`).
- Remove `path(f'{api_prefix}/datahub/', include('datahub.urls'))` from `backend/config/urls.py`.
- Delete the `backend/datahub/` directory entirely.

## Code move (mechanical, after models land in catalog)

| From `datahub/` | To `catalog/` | Notes |
|---|---|---|
| `models.py` (6 models) | `models.py` (append) | fix imports as above |
| `services.py` | `dataset_services.py` | `from .models import ...`; `from catalog.models import AssetProfile` → `from .models import AssetProfile` |
| `ingest.py` | `dataset_ingest.py` | `from .models import ...`, `from .services import ...` → `from .dataset_services import ...` |
| `serializers.py` | `dataset_serializers.py` | `from .models import ...` |
| `views.py` | `dataset_views.py` | imports → `.dataset_services` / `.dataset_ingest` / `.dataset_serializers` / `.models` |
| `admin.py` | `admin.py` (append) | `from .models import Dataset, ...` |
| `urls.py` | `urls.py` (append) | see URL change below |
| `tests/` | `tests/` (rename to `test_datasets_*.py`) | see tests section |
| `apps.py` | — (delete) | datahub app is gone |

### URL change (the app's namespace disappears)

`datahub/urls.py` registers `datasets` + nested `datasets/<uuid>/versions/...` under
`/carbon-api/datahub/`. Move those paths into `catalog/urls.py` so they resolve as:

```
/carbon-api/catalog/datasets/
/carbon-api/catalog/datasets/<uuid>/versions/
/carbon-api/catalog/datasets/<uuid>/versions/<uuid>/approve/
/carbon-api/catalog/datasets/<uuid>/versions/<uuid>/reject/
/carbon-api/catalog/datasets/<uuid>/contract/
/carbon-api/catalog/datasets/<uuid>/contract/violations/
/carbon-api/catalog/datasets/<uuid>/ingest/erp/
/carbon-api/catalog/datasets/<uuid>/ingest/upload/
```

In `catalog/urls.py`, `router.register('datasets', DatasetViewSet, basename='dataset')`
and declare the nested `datasets/<uuid:...>` paths **before** `router.urls` (same
collision-avoidance comment as today). Keep the existing catalog routes
(`domains`, `glossary`, `tags`, `assets`, `governance-*`) untouched.

## Import repointing in `integrations/turnkey/`

- `serializers.py`: `from datahub.models import DatasetVersion` → `from catalog.models import DatasetVersion`
- `services.py`: `from datahub.models import DataContract, DataContractViolation, DatasetVersion` → `from catalog.models import ...`
- `tests/conftest.py`: `from datahub.models import DataContract, Dataset, DatasetVersion` → `from catalog.models import ...`
- `tests/test_callbacks.py`: `from datahub.models import ...` → `from catalog.models import ...`
- `migrations/0001_initial.py`: change dependency `('datahub', '0001_initial')` → the new `catalog` adopt migration (and the FK `to='datahub.datasetversion'` → `to='catalog.datasetversion'`). Note: editing a historical migration is acceptable here because the graph is being re-rooted — but verify `showmigrations` is consistent afterward.

## Tests — move + repoint, keep green

- Move `backend/datahub/tests/*` → `backend/catalog/tests/`, renaming to avoid collision with
  existing catalog tests (`test_datasets_api.py`, `test_datasets_cbac.py`,
  `test_datasets_composition.py`, `test_datasets_models.py`, `test_datasets_services.py`,
  plus `conftest.py`).
- Global replace in those files:
  - `from datahub.models` → `from catalog.models`
  - `from datahub.services` → `from catalog.dataset_services`
  - `from datahub.ingest` → `from catalog.dataset_ingest`
  - URL constants `/carbon-api/datahub/datasets/` → `/carbon-api/catalog/datasets/`
    (and every nested `/versions/`, `/approve/`, `/reject/`, `/ingest/`, `/contract/` path).
- `conftest.py` fixtures (`module_a`, `module_b`, `domain`, `make_dataset`, `auth_client`,
  `CSV_SAMPLE`) move as-is; `make_dataset` imports `Dataset` from `catalog.models`.

## DO NOT TOUCH

- **Capabilities** — leave `datahub:view/ingest/approve/manage` keys and the
  `datahub_lead` group **exactly as they are** (`accounts/capabilities.py`,
  `accounts/constants.py`, `bootstrap_platform.py`, `ai/access_manifest.py`). Renaming
  RBAC keys is a separate, riskier data migration — a **follow-up phase**, not this one.
- `backend/dataschema/**`, `backend/dq/**` — read-only seams.
- `carbon-frontend/**` — no API calls to `/datahub/` exist (the `/dataschema` page is a
  placeholder); nothing to change.
- `backend/integrations/turnkey/models.py` field *definitions* other than the FK target.
- Do **not** drop any DB table — `SeparateDatabaseAndState` + `AlterModelTable` only.

## Verification Gate (run ALL, paste FULL output)

```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run   # → "No changes detected"
/home/ahmed/aast/carbon/.venv/bin/python manage.py migrate                            # applies the 3 new migrations cleanly
/home/ahmed/aast/carbon/.venv/bin/python manage.py showmigrations catalog datahub integrations.turnkey   # catalog=[X] adopted, datahub shows no models
# Data-preservation proof (must be > 0 if pre-existing rows existed):
/home/ahmed/aast/carbon/.venv/bin/python manage.py shell -c "from catalog.models import Dataset, DatasetVersion; print(Dataset.objects.count(), DatasetVersion.objects.count())"
/home/ahmed/aast/carbon/.venv/bin/python -m pytest catalog integrations.turnkey -q   # ALL green (43 datahub tests re-homed + turnkey 14)
./.ai-toolkit/scripts/verify.sh backend
./.ai-toolkit/scripts/verify.sh antipatterns
# No dangling references to the dead app:
grep -rn "from datahub\|import datahub\|'datahub'\|\"datahub\"" backend/ --include='*.py' | grep -v migrations/ || echo "CLEAN"
```

> The `grep` must return only `accounts/capabilities.py` + `accounts/constants.py` +
> `ai/access_manifest.py` capability/group *string keys* (intentionally left per "DO NOT
> TOUCH") and nothing else. Report the exact output.

## Output contract

Append to `TASK-RESULTS.md` (Part B handoff format): Summary → Task results → Files
Changed → Verification Output (full paste) → Deviations → Issues Found → verdict.

## Notes for the Master

- This is the mechanical completion of the "data product = dataset, in the catalog"
  directive. After it lands, the platform is: `catalog` (domains + glossary + assets +
  **datasets/versions/contracts**), `dataschema` (rows), `dq` (gates), `integrations`
  (turnkey), `appregistry` (consumers). One concept, one home.
- The capability-key rename (`datahub:*` → `dataset:*`, `datahub_lead` → `dataset_lead`)
  is intentionally deferred. If you want it, it's the next small phase.
- Commit with `refactor(catalog): fold datahub dataset layer into catalog (delete datahub app)`.
