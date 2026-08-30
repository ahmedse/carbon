# TASK-RESULTS-EPH-3B — Freshness Monitoring + Staleness Alerts

**Date:** 2026-08-26
**Worker Role:** backend-worker
**Status:** IMPLEMENTED (verification gate pending — see below)

---

## What Was Built

Freshness monitoring for `dataschema.DataTable`, with a per-table `FreshnessPolicy`
SLA, a staleness-checking service, a periodic task entry point, and a CRUD API.
Reused the existing alerting plumbing (`accounts.notify_event` +
`NotificationRule.EventType.FRESHNESS_VIOLATION`) — **no alerting was recreated**.

Layer discipline: the API view is THIN (validate → serialize → respond); all
staleness/rate-limit business logic lives in `catalog/freshness_service.py`.

---

## Files Changed

| File | Change |
|------|--------|
| `backend/dataschema/models.py` | Added `last_data_updated_at = models.DateTimeField(null=True, blank=True)` to `DataTable` |
| `backend/dataschema/signals.py` | **NEW** — `post_save` on `DataRow` updates `DataTable.last_data_updated_at` via `QuerySet.update()` |
| `backend/dataschema/apps.py` | Registered `dataschema.signals` in `ready()` |
| `backend/dataschema/migrations/0010_datatable_last_data_updated_at.py` | **NEW** — `AddField` migration |
| `backend/catalog/models.py` | Added `FreshnessPolicy` (OneToOne → `dataschema.DataTable`, `max_age_hours`, `alert_level`, `enabled`, `last_checked_at`, `last_alerted_at`) |
| `backend/catalog/migrations/0010_freshnesspolicy.py` | **NEW** — `CreateModel` migration |
| `backend/catalog/freshness_service.py` | **NEW** — `check_freshness()` service |
| `backend/catalog/tasks.py` | **NEW** — `check_freshness_task()` periodic entry point |
| `backend/catalog/serializers.py` | Added `FreshnessPolicySerializer` (exposes `last_data_updated_at`) |
| `backend/catalog/views.py` | Added `FreshnessPolicyView` (GET/POST/DELETE) |
| `backend/catalog/urls.py` | Added `tables/<int:table_id>/freshness/` route |
| `backend/catalog/tests/test_freshness.py` | **NEW** — 5 tests |

---

## Tests (5)

All in `backend/catalog/tests/test_freshness.py`:

1. `test_datarow_save_updates_last_data_updated_at`
2. `test_check_freshness_alerts_when_stale`
3. `test_check_freshness_no_alert_when_fresh`
4. `test_rate_limit_skips_second_alert`
5. `test_get_freshness_404_when_no_policy`

Expected: **5 passed, 0 failed**.

---

## Verification Gate

⚠️ **I could not execute these commands** — no terminal tool is available in
this session. The commands below must be run by the user to complete the gate:

```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py migrate
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest catalog/tests/test_freshness.py -v
```

<details>
<summary>Paste full output here once run</summary>

```
[Paste `manage.py check` output]
[Paste `makemigrations --check --dry-run` output]
[Paste `migrate` output]
[Paste `pytest catalog/tests/test_freshness.py -v` output]
```
</details>

---

## Deviations / Issues

1. **Celery task → plain callable.** The spec asked for a "periodic Celery
   task", but this project has **no Celery/Redis scheduler** (HARD RULE — see
   `dq/jobs.py`: "no Celery/Redis/daemon/scheduler"). `catalog/tasks.py`
   therefore exposes a plain `check_freshness_task()` intended to be driven by
   the platform's existing external/APScheduler supervisor loop (same pattern
   as `backend/ai`). No `requirements.txt` change was needed (nothing new
   imported).

2. **`--reuse-db` schema gotcha.** The test DB is built from the **current
   models** (`pytest.ini` uses `--nomigrations --reuse-db`). If a stale test
   DB already exists from before this change, `pytest` will reuse the old
   schema and the new column/table won't exist. If `test_freshness.py` fails
   with "column does not exist", re-run with `--create-db` once:
   ```bash
   cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest catalog/tests/test_freshness.py -v --create-db
   ```

3. **Migration dependency** — `catalog/0010_freshnesspolicy` depends on
   `dataschema/0010_datatable_last_data_updated_at` (FK to `DataTable`, whose
   latest migration is the new `last_data_updated_at` field), mirroring how
   existing cross-app FK migrations in this repo list dependencies.

4. **No `admin.py` change** — not listed in the spec's "Files to Change", so
   `FreshnessPolicy` is not registered in Django admin (API-only for now).
