# Data Layer — Database & Data Conventions
# Read by: Backend Worker, Data/ML Worker, Debugger/Fixer.
# Purpose: one consistent way to model, migrate, and query data.

---

## RULE 0 — Consult the Registry First

Before adding a model or field:
```bash
cat .ai-toolkit/registry/models.md          # what models exist
grep -ri "<field_or_concept>" .ai-toolkit/registry/models.md
```
Reuse an existing model/field where possible. Don't create a parallel model for the same concept.

---

## Model Conventions

- Model names: singular PascalCase (`Prediction`, `DataRecord`, `ModelVersion`).
- Field names: snake_case (`created_at`, `actual_value`, `error_pct`).
- Booleans: `is_`/`has_` prefix (`is_active`, `has_actuals`).
- Timestamps: `created_at`, `updated_at` (auto), timezone-aware ALWAYS.
- FKs: name = the related noun (`engine`, `model_version`), with explicit `on_delete`.
- Every model has a `__str__` and a sensible `Meta.ordering`.

---

## Timezone (critical)

- ALL datetimes stored timezone-aware (UTC in DB). NEVER naive.
- Read/write via `django.utils.timezone`, never `datetime.now()`.
- Display timezone conversion happens at the presentation layer, not in the DB.
- See project.config.md → DEFAULT_TIMEZONE for the display zone.

---

## Migrations (safe by default)

```bash
./manage.sh manage makemigrations
./manage.sh manage showmigrations   # verify order / no conflicts
./manage.sh migrate
```

**NEVER:**
- Add a non-nullable field without a `default=` (locks the table / fails on existing rows).
- Rename/remove a field that live models or the frontend depend on (breaking change → ADR).
- Edit a migration that has already been applied in production. Add a new one.
- Squash migrations that are already deployed without a documented plan.

**ALWAYS:**
- One logical change per migration. Reversible where possible.
- Data migrations separate from schema migrations.
- Test the migration AND its reverse locally before shipping.

---

## Indexes & Performance

- Index columns used in frequent filters/joins/ordering (`db_index=True` or `Meta.indexes`).
- Composite index for multi-column filters that run together.
- For time-series: index the timestamp; consider partitioning if huge.
- Don't over-index — every index slows writes. Index the real query paths only.

---

## Query Rules (mirror backend ORM rules)

- List/aggregate over many rows: `select_related(None)` + `.defer()` heavy JSON fields.
- NEVER `select_related()` a JSONField-bearing parent in a list endpoint (known perf trap).
- Avoid N+1: use `select_related` (FK) / `prefetch_related` (M2M) deliberately, or `values()`.
- Bulk ops: `bulk_create`, `bulk_update`, `update()` — not per-row saves in a loop.
- Aggregate in the DB (`annotate`, `aggregate`), not in Python.

---

## Data Integrity

- Constraints in the DB, not just app code: `unique_together`/`UniqueConstraint`, `CheckConstraint`.
- Idempotency keys where writes can be retried (see project idempotency rule in project.config.md).
- Use transactions (`transaction.atomic`) for multi-step writes that must be all-or-nothing.
- Validate at the model (`clean()`) AND serializer boundary for anything critical.

---

## Managed / Derived Data

- Distinguish source-of-truth data from derived/backfilled data.
- Document which fields are backfilled and by what process (see project.config.md hard rules).
- Resetting derived data must clear ALL derived copies (not just the source) — a known gotcha class.

---

## Seeds, Fixtures & Backups

- Reproducible seed/fixture path for local dev (management command or fixtures).
- Backups before destructive migrations. Restore path documented (see manage.sh db-* commands).
- NEVER run manual DELETE/UPDATE SQL in production — use a management command (reviewable, reversible).

---

## Anti-Patterns (reject in review)

- Naive datetime stored or compared
- Non-nullable field added without default
- Editing an already-applied migration
- Raw SQL with string interpolation
- Per-row save() in a loop over hundreds of rows
- New model duplicating an existing concept in registry/models.md
- Manual prod SQL instead of a management command
