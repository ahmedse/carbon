# TASK RESULTS — E2-B2: Verification workflow + ReportingPeriod state machine

**Date:** 2026-08-03  
**Role:** backend-worker  
**Status:** ✅ DONE

---

## Files Changed

| File | Change | Summary |
|------|--------|---------|
| `backend/emissions/models.py` | Modified | Added `VALID_TRANSITIONS` dict, `can_transition_to()`, and `transition_to()` to `ReportingPeriod` (lines ~98–144). Pattern follows `mdm/models.py` `ReferenceSet` state machine. |
| `backend/emissions/services.py` | Modified | Added `VerificationService` class with `submit()`, `verify()`, `reject()` static methods. Uses `update_or_create` to fix the `unique_together` IntegrityError bug. |
| `backend/emissions/views.py` | Modified | Thinned out `submit`/`verify`/`reject` actions in `ReportingPeriodViewSet` — now thin wrappers delegating to `VerificationService`. Invalid transitions return 409. Added `verify`/`reject` custom actions to `VerificationRecordViewSet`. Added `PermissionDenied` and `VerificationService` imports. |
| `backend/emissions/serializers.py` | Modified | `VerificationRecordSerializer` now exposes `period_label`, `total_co2e_tonnes`, and `scope_summary` fields for the verification grid. |
| `backend/emissions/tests/test_verification.py` | Rewritten | Updated all 8 existing tests + added 6 new tests (14 total). Old tests adapted to new state machine (e.g., `locked` as pre-submit state). |
| `backend/accounts/tests/test_e2_b1_rbac.py` | Modified | `test_verify_allowed_for_scopedrole_admin`: changed expected status from 201→200 (verify now returns 200 via update_or_create). |

---

## Test Results

### Verification tests (14/14 pass)
```
cd backend && ../.venv/bin/python -m pytest emissions/tests/test_verification.py --reuse-db -q
..............                                                           [100%]
14 passed, 2 warnings in 4.21s
```

### All related tests (56/56 pass)
```
emissions/tests/test_verification.py accounts/tests/test_e2_b1_rbac.py emissions/tests/test_services.py
........................................................                 [100%]
56 passed, 2 warnings in 10.14s
```

### Full suite (349 pass, 15 pre-existing failures)
The 15 failures are all pre-existing and unrelated:
- **4 SBTi target tests**: wrong reverse name `targets-list` → should be `sbti-target-list`
- **11 swagger doc tests**: missing endpoint descriptions (pre-existing)

### New tests added (≥6):
| # | Test | What it covers |
|---|------|---------------|
| 1 | `test_submit_from_locked_succeeds` | Submit from locked → submitted, creates pending VerificationRecord |
| 2 | `test_submit_from_draft_blocked_409` | Draft → submitted is invalid transition → 409 |
| 3 | `test_double_verify_by_same_admin_no_500` | Re-verify by same verifier → 200 (update_or_create fix, no IntegrityError) |
| 4 | `test_reject_by_non_admin_blocked_403` | Non-admin reject → 403 |
| 5 | `test_reject_from_draft_blocked_409` | Draft → rejected is invalid transition → 409 |
| 6 | `test_serializer_includes_scope_summary` | Serializer exposes `period_label`, `total_co2e_tonnes`, `scope_summary` |
| 7 | `test_submit_already_submitted_returns_200` | Same-state transition is a no-op → 200 |
| 8 | `test_resubmit_from_rejected` | Rejected → submitted (resubmit path) → 200 |

---

## Gates

| Gate | Result |
|------|--------|
| `pytest --reuse-db -q` (verification) | ✅ 14/14 pass |
| `pytest --reuse-db -q` (full suite, mine) | ✅ 349 pass, 15 pre-existing failures |
| `python manage.py check` | ✅ No issues |
| `.ai-toolkit/scripts/verify.sh backend` | ✅ GATE PASSED |
| `transition_to` raises ValueError on invalid | ✅ Returns 409 |
| `update_or_create` fixes duplicate 500 | ✅ double-verify → 200 |
| Audit events emitted on transition | ✅ via `emit_governance_event` |
| All existing tests still pass | ✅ (with deliberate 201→200 update) |

---

## Bugs Found & Fixed

1. **`unique_together(reporting_period, verifier)` → 500 on re-verify**: Fixed by using `VerificationRecord.objects.update_or_create()` in all three service methods. Same admin re-verifying now updates the existing record instead of raising `IntegrityError`.

2. **E2-B1 test expected 201 from verify**: E2-B1 `test_verify_allowed_for_scopedrole_admin` expected `resp.status_code == 201` but `update_or_create` returns 200. Updated to 200.

3. **Pre-existing SBTi target test bug**: `test_targets.py` uses `reverse('targets-list')` but the router registers as `basename='sbti-target'`. Not fixed (out of scope for E2-B2).

---

## Architecture Notes

- **State machine pattern**: Follows `mdm/models.py` `ReferenceSet.transition_to()` exactly — `VALID_TRANSITIONS` dict, `can_transition_to()`, `transition_to()` with audit emission.
- **Thin views**: `ReportingPeriodViewSet.submit/verify/reject` now delegate entirely to `VerificationService`. Views only handle HTTP translation (ValueError → 409, PermissionDenied → 403).
- **VerificationRecordViewSet**: Now has `verify` and `reject` custom actions that operate on the record's linked `reporting_period`, enabling the frontend to call `POST /verifications/{id}/verify/` and `POST /verifications/{id}/reject/`.
- **Serializer**: `VerificationRecordSerializer` now aggregates `total_co2e_tonnes` and `scope_summary` from `Calculation` records linked to the period.
