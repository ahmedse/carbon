# Workers Channel

This document is the shared coordination channel for Worker 1 and Worker 2 during parallel execution of the scoped owner apps task.

## Purpose

- Provide a lightweight shared place for coordination notes.
- Record any dependencies, handoffs, or integration checks between backend and frontend work.
- Capture quick status updates and blockers.

## Worker Roles

### Worker 1 — Backend (F1)
- F1.1: Harden `AssetProfileViewSet.get_queryset()` with org unit scoping
- F1.2: Verify `DQRuleViewSet` is restrictive
- F1.3: Add new `GET /carbon-api/emissions/owner-dashboard/` endpoint with full response contract
- F1.4: Register endpoint in `backend/emissions/urls.py`
- F1.5: Add at least 5 scoped access tests for owner dashboard and RBAC

### Worker 2 — Frontend (F2)
- F2.1: Add `fetchOwnerDashboard()` + `fetchReportingPeriods()` API client functions
- F2.2: Create `DataOwnerPortalPage.jsx` with domain cards and quality badges
- F2.3: Create `DataOwnerDashboardPage.jsx` with CO2e KPI tiles, DQ summary, and submission status
- F2.4: Create `DataOwnerAssetsPage.jsx` with simplified scoped asset browser
- F2.5–F2.7: Add routes, sidebar "My Data" section, and empty state handling

## Communication Guidelines

- Use this file for any data contract or scope clarification needed between workers.
- If Worker 1 changes the owner-dashboard API contract, document the final response structure here.
- If Worker 2 needs a mock endpoint or schema detail before the backend is ready, note it here.

## Shared API Contract

### `GET /carbon-api/emissions/owner-dashboard/`
Expected response shape (per TASK-CARBON-P1-SCOPED-OWNER-APPS.md F1.3):

```json
{
  "org_unit": {
    "id": 5,
    "name": "Smart Village Campus",
    "org_type": "campus"
  },
  "reporting_period": {
    "id": 2,
    "name": "FY 2025",
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
    "status": "open"
  },
  "emissions": {
    "total_co2e_tonne": 1240.5,
    "scope1_co2e_tonne": 320.1,
    "scope2_co2e_tonne": 850.4,
    "scope3_co2e_tonne": 70.0,
    "calculation_count": 1847,
    "previous_period_co2e_tonne": 1280.0,
    "change_pct": -3.1
  },
  "data_quality": {
    "avg_quality_score": 87.3,
    "passing_count": 12,
    "warning_count": 3,
    "failing_count": 1,
    "unknown_count": 2
  },
  "modules": {
    "total": 5,
    "with_data": 4,
    "without_data": 1,
    "without_data_names": ["Chilled Water S2"]
  },
  "recent_events": [
    {
      "id": 101,
      "action": "update",
      "entity_type": "AssetProfile",
      "timestamp": "2026-07-18T10:32:00Z",
      "user": "john.doe"
    }
  ]
}
```

## Status Updates

### Worker 2 (Frontend) — **COMPLETE & READY FOR INTEGRATION** ✅
**Date:** 2026-07-21 15:30 UTC

**Completed:**
- F2.1: Added `fetchOwnerDashboard()` and `fetchReportingPeriodsFiltered()` to `carbon-frontend/src/api/emissions.js`
- F2.1: Added route `emissionsOwnerDashboard` to config.js
- F2.2: Created `DataOwnerPortalPage.jsx` with domain cards, quick stats, and recent activity
- F2.3: Created `DataOwnerDashboardPage.jsx` with emissions KPI tiles (4 scopes), DQ summary card, and submission status card
- F2.4: Created `DataOwnerAssetsPage.jsx` with filterable asset grid (search, domain filter)
- F2.5: Registered 3 new routes in App.jsx under `/data-owner/`
- F2.6: Added `DataOwnerSidebar` to SidebarMenu.jsx with "My Data" section showing 3 routes
- F2.6: Sidebar dispatcher detects org_unit scope and shows DataOwnerSidebar

**Status:** All frontend pages compile and are wired. Ready to consume the backend API once F1 is complete.

**Awaiting from Worker 1:**
- F1.3: `GET /carbon-api/emissions/owner-dashboard/` endpoint implementation with the contract above
- F1.1: `AssetProfileViewSet.get_queryset()` org_unit scoping so `/catalog/assets/` returns only user's org assets

**Notes:**
- Frontend uses the exact API contract specified in TASK. No deviations.
- Empty state handling is in place — users with no org_units see a clear message.
- Quality status badges use color coding: green (passing), amber (warning), red (failing), gray (unknown).

### Worker 1 (Backend) — Status?
Please update with progress on F1.1–F1.5. Any blockers or scope clarifications needed?

## Notes

- **Worker 1 Progress (2026-07-21):**
  - ✅ F1.1: AssetProfileViewSet.get_queryset() hardened with org_unit scoping via ScopedRole
  - ✅ F1.2: DQRuleViewSet already has restrictive RBAC (confirmed in dq/views.py)
  - ✅ F1.3: OwnerDashboardAPIView created with org-unit scoping and response contract
  - ✅ F1.4: Endpoint registered as `GET /carbon-api/emissions/owner-dashboard/`
  - ✅ F1.5: 5 comprehensive RBAC tests added (catalog/tests/test_scoped_access.py)
  
- **API Contract Finalized:** See shared contract below
- **Ready for Worker 2:** Frontend can start integration using the mock contract or live backend

- If any worker discovers a blocker, add a short note here and mention the other worker.
- Use this page as the single source of truth for shared expectations.
