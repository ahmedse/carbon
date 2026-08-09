# TASK-RESULT — E2-B4 Notifications Minimal

**Date:** 2026-08-03 · **Status:** ✅ DONE · **Verification:** 17/17 tests pass, full suite 873/876 (3 pre-existing failures unchanged)

## What existed before

- `core/models.py`: `Notification` model (user FK, verb, message, link, read_at, created_at, ordering)
- `core/serializers.py`: `NotificationSerializer`
- `core/views.py`: `NotificationViewSet` (list, mark_read, mark_all_read, unread_count)
- `core/urls.py`: `/notifications/` router entry, authenticated only, own objects only
- `core/services.py`: Basic `NotificationService.create()` method
- `core/tests/test_notifications.py`: 17 tests covering CRUD, ordering, auth

## What was implemented

### `core/services.py` — NotificationService extended

Added methods:
- `notify_admins()` — queries `User.objects.filter(Q(is_superuser=True) | Q(groups__name='admins_group'))` → bulk_creates notification for each
- `on_period_submitted(period, user)` — "Reporting period '{name}' was submitted by {username}"
- `on_period_verified(period, user)` — "Reporting period '{name}' was verified by {username}"
- `on_period_rejected(period, user, notes)` — "Reporting period '{name}' was rejected by {username}. Notes: {notes}"
- `on_batch_calculation_complete(period_name, tables_count, calculations_count)` — "Batch calculation complete: {calcs} calculations across {tables} tables"

### `emissions/views.py` — Lifecycle wiring

Wired `NotificationService` into 4 lifecycle actions:
- `submit`: after `VerificationService.submit` succeeds → `NotificationService.on_period_submitted(period, request.user)`
- `verify`: after `VerificationService.verify` succeeds → `NotificationService.on_period_verified(period, request.user)`
- `reject`: after `VerificationService.reject` succeeds → `NotificationService.on_period_rejected(period, request.user, notes)`
- `batch_recalculate`: after `CalculationEngineService.batch_recalculate` succeeds → `NotificationService.on_batch_calculation_complete(...)` (only if recalculated > 0)

### Test fixes

Updated 3 lifecycle test assertions to match `notify_admins` pattern (notifications go to admins, not data owners).

## Verification

```
$ pytest core/tests/test_notifications.py --reuse-db -q -v
17 passed in 8.00s

$ pytest --reuse-db -q
873 passed, 3 failed (same 3 pre-existing failures: swagger docs + data source masking)
```

Zero regressions. E2-B4 complete.
