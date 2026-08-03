# TASK-RESULTS-E2-B4 — Notifications, minimal

**Date:** 2026-08-03
**Role:** Backend Worker
**Status:** ✅ COMPLETE

---

## Summary

Implemented a minimal in-app notification system (`core.Notification` model + service + endpoints) and wired it into the emissions verification lifecycle and batch calculation.

## Files Changed

| File | Change |
|------|--------|
| `core/models.py` | Added `Notification` model (user FK, verb, message, link, read_at, created_at) |
| `core/services.py` | **Created.** `NotificationService.notify(user, verb, message, link)` |
| `core/serializers.py` | Added `NotificationSerializer` |
| `core/views.py` | Added `NotificationViewSet` with list (scoped to user, with `unread_count`), `mark_read`, `mark_all_read` |
| `core/urls.py` | Registered `notifications` route with core router |
| `emissions/services.py` | Added `_notify_user` / `_notify_period_event` helpers; wired notifications into `VerificationService.submit/verify/reject` and `CalculationEngineService.batch_calculate` |
| `core/tests/test_notifications.py` | **Created.** 17 tests |

## Model Design

```
Notification
├── user: FK → accounts.User (related_name='notifications')
├── verb: CharField(50) — 'submitted', 'verified', 'rejected', 'batch_complete'
├── message: TextField — human-readable body
├── link: CharField(500) — optional URL to related resource
├── read_at: DateTimeField(null=True)
├── created_at: DateTimeField(auto_now_add=True)
└── Meta: ordering=['-created_at'], indexes on (user, -created_at) and (user, read_at)
```

## Endpoints (under `/carbon-api/core/notifications/`)

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/notifications/` | Paginated list (own only), includes `unread_count` in response |
| POST | `/notifications/{id}/mark_read/` | Set `read_at = now()` |
| POST | `/notifications/mark_all_read/` | Mark all user's unread notifications as read |

## Lifecycle Emission Points

| Event | Recipient | Verb | Message |
|-------|-----------|------|---------|
| Period submitted | All users with `dataowners_group` ScopedRole | `submitted` | "Period {name} submitted for verification" |
| Period verified | Period's `created_by` user | `verified` | "Period {name} has been verified" |
| Period rejected | Period's `created_by` user | `rejected` | "Period {name} has been rejected: {notes}" |
| Batch calculation complete | Requesting user | `batch_complete` | "Batch calculation complete: {count} calculations" |

## Test Results

```
17 passed (core/tests/test_notifications.py)
383 passed total, 15 pre-existing failures (SBTi targets + swagger docs — unrelated)
0 regressions
```

### Test Coverage (17 tests)

**Model & Service (4):**
- `test_notification_creation` — basic creation
- `test_notification_ordering` — newest first
- `test_str_representation` — str includes verb + message prefix
- `test_notify_none_user_is_noop` — notify(None) silently no-ops

**Endpoints (9):**
- `test_list_only_own_notifications` — GET returns only requesting user's
- `test_list_another_user_sees_only_own` — user isolation
- `test_unread_count_in_response` — `unread_count` in list response
- `test_mark_read_sets_read_at` — POST mark_read sets timestamp
- `test_mark_read_idempotent` — double-mark is safe
- `test_mark_all_read` — marks all unread
- `test_mark_all_read_only_affects_self` — doesn't affect other users
- `test_unread_count_decrements_after_mark_read` — count updates
- `test_cannot_mark_others_notification_read` — 404 on other user's notification

**Lifecycle (3):**
- `test_notification_on_period_submit` — data owner notified on submit
- `test_notification_on_period_verify` — creator notified on verify
- `test_notification_on_period_reject` — creator notified on reject (with notes)

## Gates Check

| Gate | Status |
|------|--------|
| `python -m pytest --reuse-db -q` — all pass | ✅ 383 pass / 15 pre-existing |
| Migration applies cleanly | ✅ `core.0010_notification` applied |
| No import from emissions into core | ✅ Core only imports `accounts.User` (base layer) |
| ≥4 tests | ✅ 17 tests |
| Notification on submit | ✅ |
| Notification on verify | ✅ |
| Notification on reject | ✅ |
| mark_read sets read_at | ✅ |
| mark_all_read marks all unread | ✅ |
| GET only returns own notifications | ✅ |

## Notes

- **Data owner notification for submit**: Notifies ALL users with `dataowners_group` ScopedRole (not scoped per-module). A period has no direct module linkage — scoping to specific modules would require querying CalculationRules for the period's tables. This is noted as a future enhancement.
- **Batch notification**: Added after the batch calculation loop completes. Only fires when `user` is not None (regular API flow). Batch executions triggered without a user context (e.g., future Celery tasks) will not create notifications.
- **No cross-app import violation**: `emissions/services.py` imports from `core.services` (allowed — emissions may import core). Core never imports emissions.
- **ADR note**: Synchronous notification creation. If notification volume grows, consider moving to an async signal-based approach.
