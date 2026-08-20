# Sprint 29 — P1B: Dataset Composition (1 Dataset = N Tables)

**Date:** 2026-08-20
**Worker Role:** backend-worker
**Recommended Model:** DeepSeek-V3 / Sonnet
**Status:** READY
**Kind:** Backend-only. Small-medium. No frontend.
**Depends on:** Phase P1 (Dataset Hub `datahub/`) — already shipped.

## Why this phase exists (owner directive, verbatim intent)

Industry standard (Zhamak Dehghani's data-as-a-product, dbt exposures,
OpenMetadata "containers"): a **data product** is a *domain-scoped semantic
unit* that almost always spans **multiple tables**. The owner wants *exactly*
this:

- **Promote `Dataset` to a true data product** — domain, ownership, **steward**,
  classification, tags, table membership (1..N), lineage, versioning,
  data contracts, access policy, audit. All of it.
- **Host many data products (datasets), each with one or more tables.**
- **Apps consume them** (`AppManifest.consumed_datasets` ↔ `DataContract.consumer_apps`,
  enforced by `ScopedRole` on the dataset's `module`) — already wired; this phase
  makes the underlying unit multi-table.
- **Hard constraint: NO unnecessary complexity.** One new model + one new FK.
  Everything else is reuse. Do not build an explicit table→table relation graph,
  do not add per-table contracts, do not add a workflow engine.

## The current bug (verified against code)

`DatasetVersion` pins ONE table:

```python
# backend/datahub/models.py
data_table = models.ForeignKey(DataTable, on_delete=models.PROTECT, ...)
```

So today `Dataset == one table's approved snapshot`. The `Dataset` docstring
("backed by **DataTable(s)**") already promises multi-table; the model does not
deliver it. This phase closes that gap by **moving the table reference out of
`DatasetVersion` into a member table**, keeping the single-table path as a
back-compat alias.

## Target model (the ONLY new pieces)

```
Dataset  (the DATA PRODUCT — already exists, +1 FK)
 ├─ owner, domain, module, classification, tags, source, status, current_version  ✅
 ├─ steward → User                                  ⚠️ ADD (mirror catalog.AssetProfile.steward)
 │
 └─ DatasetVersion  (one frozen, approved snapshot of the WHOLE product)
      └─ DatasetVersionMember                       ⚠️ ADD (the only new model)
           ├─ data_table → DataTable                (one row per table)
           ├─ order                                 (deterministic ordering)
           ├─ label                                 (semantic name within product, optional)
           ├─ row_count, schema_snapshot            (per-table)
           ├─ dq_job_id                             (per-table DQ gate)
           └─ health_score, health_detail           (per-table health)
```

`DatasetVersion.data_table` **stays** as the "primary table" back-compat
shortcut (existing rows + existing tests keep working).

## Files to Read First

- `backend/datahub/models.py` — `Dataset`, `DatasetVersion`, `DataContract`, `DatasetAccessPolicy` (see how `DatasetVersion` uses `data_table`, `schema_snapshot`, `health_detail`, `dq_job_id`, `lineage`).
- `backend/datahub/ingest.py` — `create_data_table`, `compute_health`, `create_version`, `ingest_rows` (the pipeline this phase extends).
- `backend/datahub/services.py` — `check_contract`, `mirror_health_to_catalog`, `approve_version`.
- `backend/datahub/serializers.py` — `DatasetVersionSerializer`, `DatasetSerializer`.
- `backend/datahub/views.py` — `VersionListCreateView.post` (single `data_table` today), `VersionDetailView`.
- `backend/datahub/admin.py` — register the new model.
- `backend/catalog/models.py` — `AssetProfile.steward` (copy the FK definition + `related_name` convention).
- `backend/datahub/tests/` — `conftest.py`, `test_models.py`, `test_services.py` (the fixtures + patterns to reuse).

## Files to Change

- `backend/datahub/models.py` — `Dataset.steward` + `DatasetVersionMember` + a `DatasetVersion.tables` convenience property + migration.
- `backend/datahub/services.py` — `check_contract` (schema check across all members), `mirror_health_to_catalog` (per-member tables).
- `backend/datahub/ingest.py` — `create_version` accepts a **list** of tables (backward compatible single `table` kwarg); multi-table helper.
- `backend/datahub/serializers.py` — nested `DatasetVersionMemberSerializer` on `DatasetVersionSerializer`; `steward` on `DatasetSerializer`/`DatasetListSerializer`.
- `backend/datahub/views.py` — `VersionListCreateView.post` accepts `data_tables` (list) as an alternative to `data_table`.
- `backend/datahub/admin.py` — `DatasetVersionMember` inline on `DatasetVersionAdmin`; `steward` in `DatasetAdmin`.
- `backend/datahub/tests/test_composition.py` — NEW.

## Design decisions (deep)

1. **One new model only.** `DatasetVersionMember` is the entire composition
   layer. There is NO separate `VersionTable`/`DatasetTableMember` on the
   `Dataset` side — *membership lives on the version*, because a version is the
   governed, approved, DQ-gated artifact. The product's "current tables" are
   simply `dataset.current_version.members`.
2. **Per-table DQ + health, not per-table contracts.** Each member carries its
   own `dq_job_id`, `health_score`, `health_detail`, `schema_snapshot`,
   `row_count`. The **contract stays product-level** (`DataContract` on
   `Dataset`) — no per-table SLA. `check_contract` must, however, check
   `required_fields` against the **union of all member schemas** (a field is
   "present" if it exists in ANY member's snapshot).
3. **`DatasetVersion.data_table` is a compat alias, not the source of truth.**
   Keep the FK (existing migration + 43 tests depend on it). For new versions,
   set it to the **first** member's table. Add a `DatasetVersion.tables`
   property that returns `[m.data_table for m in members]`, falling back to
   `[self.data_table]` for legacy rows. Do NOT make it nullable — that would
   churn the existing migration for zero benefit.
4. **No explicit table→table relation graph.** Membership in the same product
   *is* the semantic relation. Join/dependency detail (how `orders` relates to
   `customers`) belongs in `DatasetVersion.lineage` JSON
   (`upstream_version_ids` / `transforms`), which already exists. Do not invent
   a new relation model.
5. **`steward` is a mirror of `AssetProfile.steward`.** Single nullable
   `ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='stewarded_datasets')`.
   Stewardship stays advisory metadata (the governance *workflow* is already the
   version approve/reject path); do not build steward task queues.
6. **Atomic approval is preserved.** `approve_version` flips the whole version
   (all members) — a product is approved all-or-none. No per-member approval.

## Implementation

### 1. `models.py`

Add to `Dataset`:

```python
steward = models.ForeignKey(
    settings.AUTH_USER_MODEL, null=True, blank=True,
    on_delete=models.SET_NULL, related_name='stewarded_datasets',
    help_text='Data steward accountable for this data product (advisory).',
)
```

New model:

```python
class DatasetVersionMember(models.Model):
    """One table inside a multi-table DatasetVersion (the data-product composition)."""
    version = models.ForeignKey(
        'DatasetVersion', on_delete=models.CASCADE, related_name='members')
    data_table = models.ForeignKey(
        'dataschema.DataTable', on_delete=models.PROTECT, related_name='dataset_version_members')
    order = models.PositiveIntegerField(default=0)
    label = models.CharField(max_length=120, blank=True,
                             help_text='Semantic name within the product, e.g. "orders", "customers".')
    row_count = models.IntegerField(default=0)
    schema_snapshot = models.JSONField(default=dict, blank=True)
    health_score = models.FloatField(null=True, blank=True)
    health_detail = models.JSONField(default=dict, blank=True)
    dq_job_id = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ['order', 'id']
        unique_together = [('version', 'data_table')]
        verbose_name = 'dataset version member'
        verbose_name_plural = 'dataset version members'

    def __str__(self):
        return f"{self.version} :: {self.data_table_id or self.label or self.order}"
```

Add a `DatasetVersion` property:

```python
@property
def tables(self):
    """All DataTables in this version (members first, legacy fallback)."""
    member_tables = [m.data_table for m in self.members.all()]
    if member_tables:
        return member_tables
    return [self.data_table] if self.data_table_id else []
```

Generate the migration (`makemigrations datahub`).

### 2. `services.py`

- `check_contract`: replace `schema = version.schema_snapshot or {}` with the
  union of member snapshots:

  ```python
  schema = dict(version.schema_snapshot or {})
  for member in version.members.all():
      for name, spec in (member.schema_snapshot or {}).items():
          schema.setdefault(name, spec)
  ```

  Keep the rest (quality/freshness checks) unchanged — they already read
  version-level aggregates.
- `mirror_health_to_catalog`: mirror per **member** table (loop over
  `version.tables`), using the member's `health_score` when present, falling
  back to the version's aggregate. Keep the existing single-table behavior for
  versions with no members (back-compat with `test_services.py`).

### 3. `ingest.py`

- Change `create_version` signature to accept a **list** while keeping the old
  single kwarg working:

  ```python
  def create_version(dataset, tables, *, source_type, source_ref, user=None,
                     auto_approve=False, contract=None) -> DatasetVersion:
      if isinstance(tables, DataTable):
          tables = [tables]
  ```

  Body refactor:
  - Per-table: DQ job + `gate_validity` + `compute_health` → one
    `DatasetVersionMember` per table (with `order` = index, `label` = '' unless
    provided).
  - Version-level `row_count` = sum of member `row_count`; version-level
    `health_score` = simple mean of member `health_score` (weighted by row count
    is over-engineering — use the plain mean and note it); `health_detail` =
    per-dimension mean across members; `schema_snapshot` = merged union of
    member snapshots (back-compat so single-table output is unchanged);
    `dq_job_id` = the **last** member's job id (single source is ambiguous for
    N tables; do not overthink — it is a trace pointer).
  - `data_table` = `tables[0]` (primary-table alias).
  - `lineage`, status, approval, contract evaluation: unchanged.
- Add a small convenience `create_version_from_tables(dataset, table_specs, ...)`
  where each `table_spec` is `{'table': DataTable}` or
  `{'columns': [...], 'rows': [...], 'label': '...'}` (creates the DataTable via
  the existing `create_data_table` + `write_rows`). **Keep this helper ~20 lines
  and only if it stays trivial** — if it grows, drop it and rely on
  `create_version` with a list of already-materialized tables.
- `ingest_rows` / `ingest_erp` / `ingest_csv` stay single-table (a CSV/ERP
  snapshot is naturally one table) and call `create_version(dataset, [table], ...)`.

### 4. `serializers.py`

- New `DatasetVersionMemberSerializer` (read-only): `id, data_table, order,
  label, row_count, schema_snapshot, health_score, health_detail, dq_job_id`.
- `DatasetVersionSerializer`: add `members = DatasetVersionMemberSerializer(many=True, read_only=True)`
  and add `'members'` to `fields`. Keep `data_table` in the output (back-compat).
- `DatasetSerializer` + `DatasetListSerializer`: add `'steward'` to `fields`
  (read-only for list).

### 5. `views.py`

`VersionListCreateView.post`: accept either the existing single `data_table` id
OR a new `data_tables` (list of ids):

- Validate: `data_tables` must be a non-empty list of valid DataTable pks, all
  in `dataset.module` (same module check as today).
- Resolve to `DataTable` instances, then
  `ingest_service.create_version(dataset, tables, source_type='api', source_ref='manual', user=request.user)`.
- Keep the single `data_table` branch unchanged (it just wraps `[table]`).

### 6. `admin.py`

- `DatasetVersionMember` as a `TabularInline` on `DatasetVersionAdmin`
  (readonly fields for the governance snapshot; `label` + `order` editable).
- Add `'steward'` to `DatasetAdmin.list_display`.

### 7. Tests — `backend/datahub/tests/test_composition.py`

Reuse `module_a` / `make_dataset` / `_table_for` fixtures. Cover:

1. **Model**: a `DatasetVersion` with 2 members — `version.tables` returns both
   in `order`; `unique_together` blocks the same table twice.
2. **Back-compat**: `DatasetVersion.objects.create(dataset, version_number, data_table=table)`
   (no members) → `version.tables == [table]`; existing `test_models.py`
   behavior unchanged.
3. **`create_version` with a list of 2 tables** → 2 members created, each with
   its own `health_score`/`schema_snapshot`/`dq_job_id`; `version.data_table ==
   tables[0]`; `row_count` = sum; `health_score` = mean.
4. **`create_version` with a single `DataTable` kwarg (old path)** → still
   creates 1 member AND sets `data_table` (single-table parity).
5. **`check_contract` across members**: contract `required_fields=['a', 'b']`
   where `a` lives in member 1 and `b` in member 2 → **zero** schema violations;
   a missing `c` → one violation.
6. **`mirror_health_to_catalog`** with members → an `AssetProfile` per member
   table gets the correct status.
7. **API**: `POST /datasets/{id}/versions/` with `data_tables:[id1,id2]` →
   201 + `members` in the response (use the `auth_client` fixture).
8. **Steward**: `DatasetSerializer` create/update accepts `steward` and it
   round-trips.

### DO NOT TOUCH

- Any `carbon-frontend/**` file (product editor screen = a later phase).
- `backend/dataschema/**`, `backend/dq/**`, `backend/catalog/**` (only READ
  `AssetProfile.steward` as a pattern; do not edit).
- `backend/datahub/tests/test_api.py`, `test_cbac.py`, `test_models.py`,
  `test_services.py` — extend only if a test breaks due to the model change
  (with back-compat they should NOT). Prefer NEW tests in `test_composition.py`.

## Verification Gate

```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check                  # → "System check identified no issues (0 silenced)"
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations datahub  # → generates 0002 (member + steward); then apply:
/home/ahmed/aast/carbon/.venv/bin/python manage.py migrate datahub
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run  # → "No changes detected"
PGPASSWORD=AdminPa_132 PGUSER=ahmed /home/ahmed/aast/carbon/.venv/bin/python -m pytest datahub -q   # → all green (43 existing + new composition tests)
```

> If the datahub suite needs the PostgreSQL env vars, keep the `PGPASSWORD`/
> `PGUSER` prefix shown above; if it runs without them in this repo, run plain
> `pytest datahub -q`. Report which form you used.

## Output contract

Append to `TASK-RESULTS.md` (Part B handoff format):
Summary → Task results (numbered ✅/❌) → Files Changed → Verification Output
(full paste) → Deviations → Issues Found → verdict (PASSED / PASSED WITH FINDINGS / FAILED).

## Notes for the Master

- This is the model-level promotion of Dataset → data product, nothing more.
  The **product editor screen** (compose N tables, per-table labels, lineage
  editing) is a separate frontend phase — do not scope-creep it here.
- The version-level `health_score = plain mean` of member scores is a deliberate
  simplification. Flag it in TASK-RESULTS; if you want a row-weighted mean later
  it is a 3-line change in `ingest.py`.
- `data_table` as "primary table" keeps every existing consumer
  (serializers, `mirror_health_to_catalog`, 43 tests) green. Do not null it.
- Commit with `feat(datahub): P1B — Dataset composition (1 dataset = N tables) + steward`.
