# RUN A10 PROPOSAL — Data Quality Integration & Dashboard

**Status:** 📋 AWAITING A9 COMPLETION  
**Date:** 2026-07-19  
**Priority:** HIGH

---

## Current Situation

RUN A9 (Bulk Import/Export) is **70% complete**:
- ✅ Phase 1: Backend bulk-import endpoint (`/carbon-api/datarows/bulk-import/`)
- ✅ Phase 2: Frontend BulkImportWizard component (3-step wizard with auto-mapping)
- ⏳ Phase 3: Template download endpoint (missing)
- ⏳ Phase 4: Enhanced export features (missing)
- ⏳ Phase 5: Testing, validation, documentation (missing)

**Recommendation:** Complete RUN A9 phases 3-5 before starting RUN A10.

---

## RUN A10 Scope (Post-A9)

Once A9 is complete, RUN A10 will focus on **Data Quality Integration** — bringing Data Quality features from the separate `/dataschema/dq` dashboard into the main Data Hub context.

### Core Objectives

1. **Integrated DQ Dashboard in Data Hub**
   - Display data quality metrics alongside data tables
   - Show scope-specific DQ assessments (Scope 1/2/3)
   - Keep DQ context within Data Hub (no fly-away navigation)

2. **DQ Rules & Checks Visibility**
   - Show active DQ rules per module/table
   - Display rule results for data rows
   - Audit trail of rule executions

3. **Data Quality Score Card**
   - Org unit health indicators
   - Module-level quality metrics
   - Trend visualization

4. **Integration with Evidence**
   - Link evidence files as DQ correction proof
   - Track remediation status

---

## Why A10 After A9?

**Logical Sequence:**
1. A0-A6: Core platform foundation ✅
2. A8: Evidence & Attachments (audit trail) ✅
3. A9: Bulk Import/Export (data operations) → Must complete for data consistency
4. **A10: Data Quality Integration** (data validation + context)
5. A11: Reporting & Analytics (business insights)
6. A12: Deployment Readiness (production hardening)

**Data Flow Dependency:**
- Bulk import (A9) creates/modifies rows → DQ checks should validate them
- DQ results (A10) inform data quality stories
- Quality assurance flows into reports (A11)

---

## Master/Worker Protocol

**Current Phase:** A9 completion (Worker: Raptor executes phases 3-5)

**Next Phase:** A10 execution
- Master (Architect): Create TASK-A10.md with clear acceptance criteria
- Worker (Raptor): Execute phases in sequence (typically 4-5 phases)
- Master: Review each phase result, validate against criteria, approve/request fixes
- Deliverable: TASK-RESULT-A10.md with full validation

---

## Estimated Scope for A10

- **Backend:** 3-4 new DQ API endpoints (metrics, rules, assessment results)
- **Frontend:** 3-4 new components (DQDashboard, RulesList, ScoreCard)
- **Integration:** Link to ModuleLandingPage, DataHubHome, TableDataPage
- **Testing:** ~25-30 automated tests (backend API + RBAC + components)
- **Documentation:** Complete TASK-RESULT-A10.md with evidence

---

## Action Items

- [ ] Wait for A9 phases 3-5 completion + TASK-RESULT-A9.md creation
- [ ] Master validates A9 against acceptance criteria
- [ ] Upon A9 sign-off, create detailed TASK-A10.md
- [ ] Hand off to Worker for RUN A10 execution
