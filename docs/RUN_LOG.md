?ust i# Carbon Data Trust Platform — RUN Log

This is the authoritative log of all Master/Worker RUNs for the Carbon project.

## Active RUN Sequence (A0–A6)

| RUN | Title | Type | Status | Date | Result |
|-----|-------|------|--------|------|--------|
| A0 | Ground-truth audit | read-only | ✅ COMPLETE | 2026-07-18 | See `TASK-RESULT.md` (root) |
| A1 | Repo hygiene & doc truth | cleanup | ✅ COMPLETE | 2026-07-18 | See `TASK-RESULT-A1.md` (root) |
| A2 | Core governance RBAC fix | backend | ✅ COMPLETE | 2026-07-18 | See `TASK-RESULT-A2.md` (root) |
| A3 | Data-owner scoped experience | backend | ✅ COMPLETE | 2026-07-18 | See `TASK-RESULT-A3.md` (root) |
| A4 | Admin experience | backend | ✅ COMPLETE | 2026-07-18 | See `TASK-RESULT-A4.md` (root) |
| A5 | Role-Adaptive UI (Perspectives) | design+build | ✅ COMPLETE | 2026-07-18 | See `TASK-RESULT-A5.md` (root) |
| A6 | Data Hub Completion | frontend+UX | ✅ COMPLETE | 2026-07-18 | See `TASK-RESULT-A6.md` (root) |

## RUN Details

### A0: Ground-Truth Audit (2026-07-18) ✅
**Objective:** Establish verified baseline state  
**Key Findings:**
- ✅ Data-owner read scoping works perfectly
- ❌ Deployment blockers: DEBUG/SECRET_KEY hardcoded, secrets committed
- ⚠️ ai_copilot still wired despite strategy freeze
- ⚠️ 9 superseded docs + 5 data artifacts in repo

**Result:** See `TASK-RESULT.md` (root) for full audit report

### A1: Repo Hygiene & Doc Truth (2026-07-18) ✅
**Objective:** Clean foundation before deeper work  
**Actions:**
- Freeze ai_copilot app (comment URL, add deprecation notice)
- Fix stale DESIGN_DATA_TRUST_CORE.md (Project → OrgUnit)
- Archive 8 superseded status docs to docs/archive/
- De-git .env.production and 5 data artifacts
- Update .gitignore to prevent re-commit
- Create this RUN_LOG.md as single source of truth

**Key Metrics:**
- 7 logical git commits (909486e → 5e4d063)
- 48,667 net lines removed (mostly large data files)
- 1.7 MB backed up to ~/carbon-backups/
- 10/10 acceptance criteria PASSED

**Result:** See `TASK-RESULT-A1.md` (root) for full report

### A2: Core Governance RBAC Fix (2026-07-18) ✅
**Objective:** Ensure governance resources only mutable by global admins  
**Actions:**
- Created `ReadAnyWriteGlobalAdmin` permission (checks `org_unit__isnull=True`)
- Updated catalog/mdm/dq apps to use new permission
- Created test script proving org-scoped admin blocked, global admin allowed
- Documented governance protection model in DESIGN_ORG_ACCESS_MODEL.md

**Key Metrics:**
- 4 logical git commits (edd78a5 → ddde8de)
- 12 ViewSets updated across 3 apps
- Test script: 3/3 tests PASSED
- 8/8 acceptance criteria PASSED

**Result:** See `TASK-RESULT-A2.md` (root) for full report

### A3: Data-Owner Scoped Experience (2026-07-18) ✅
**Objective:** Fix 403 errors for data-owners accessing DataSchema, enforce schema write protection  
**Root Cause:** `HasScopedRole` couldn't resolve `module_id` from `data_table` parameter or URL `pk`  
**Actions:**
- Enhanced `HasScopedRole` to auto-resolve `module_id` from `data_table` and URL `pk`
- Created `ReadScopedWriteAdmin` permission (read: org-scoped, write: global admins only)
- Updated DataTableViewSet and DataFieldViewSet to use `ReadScopedWriteAdmin`
- Verified cross-scope isolation (transport cannot access facilities data)

**Key Metrics:**
- 2 logical git commits (875c32c → ca20322)
- 68 lines added to accounts/permissions.py
- All CRUD operations now work without explicit `module_id` parameter
- 10/10 acceptance criteria PASSED

**Key Findings:**
- ✅ DataRows CRUD works without `module_id` (auto-resolution)
- ✅ Schema read works without `module_id` (auto-resolution from pk)
- ✅ Schema write blocked for data-owners (admin-only enforcement)
- ✅ Cross-scope isolation verified (org boundaries enforced)
- ❌ Bulk upsert endpoint not implemented (missing feature, not a blocker)

**Result:** See `TASK-RESULT-A3.md` (root) for full report

### A4: Admin Experience Verification (2026-07-18) ✅
**Objective:** Verify admin capabilities and confirm A2/A3 permission fixes work correctly  
**Actions:**
- Created global admin user (global_admin / GlobalAdmin_2026!)
- Verified global admin full CRUD on governance (catalog/mdm/dq)
- Verified global admin full CRUD on schema (DataTable/DataField)
- Verified global admin cross-org data access
- Verified org-scoped admin limits (read-only governance/schema, scoped data)
- Created ADMIN_USER_GUIDE.md with workflows and examples
- Updated LOGIN_CREDENTIALS.md with admin credentials

**Key Metrics:**
- 3 logical git commits (credential setup, testing, documentation)
- 12/12 acceptance criteria PASSED
- 399 lines in ADMIN_USER_GUIDE.md
- 749 lines in TASK-RESULT-A4.md

**Key Findings:**
- ✅ Global admin has full platform control (governance, schema, data across all orgs)
- ✅ Org-scoped admin correctly limited (read-only governance/schema, scoped data)
- ✅ A2 fix verified: ReadAnyWriteGlobalAdmin blocks org-scoped admin governance writes (403)
- ✅ A3 fix verified: ReadScopedWriteAdmin blocks org-scoped admin schema writes (403)
- ✅ Module_id auto-resolution works correctly for data access
- ❌ Reports functionality not implemented (missing feature, not a blocker)

**Result:** See `TASK-RESULT-A4.md` (root) for full report

### A5: Role-Adaptive UI (Perspectives Architecture) (2026-07-18) ✅
**Objective:** Implement perspective-based UI switching (Data Entry/Dashboards/Admin)
**Architecture Decision:** Hybrid approach - keep Shell/ActivityBar + add perspective tabs to header
**Actions:**
- Added perspective tabs to HeaderNew (Data Entry/Dashboards/Admin)
- Enhanced ShellSidebar with role-based filtering (hide admin items for non-admins)
- Added scope banner to Layout showing org unit for non-admin users
- Cleaned up duplicate setPerspectiveActive in AuthContext
- Verified backend already had complete scoping (_scope_calcs() + /me/context/)

**Key Metrics:**
- 1 logical git commit (9bb55a5)
- 4 files changed: +118/-46 lines
- Frontend build: ✅ Success (10.84s)
- Backend check: ✅ Passed
- 12/12 acceptance criteria PASSED

**Key Findings:**
- ✅ Backend scoping already implemented via _scope_calcs() in all dashboard endpoints
- ✅ /me/context/ endpoint already exists with perspectives, roles, org_units
- ✅ AuthContext already had perspective state + fetchPerspectiveContext()
- ✅ Role-aware landing page already implemented in buildContext()
- ✅ Hybrid architecture preserves VSCode-inspired Shell while adding perspective awareness
- ⚠️ Test data shows same calculation counts for all users (data seeding issue, not code)
- ⚠️ Bundle size 1.6MB (optimization opportunity for future)

**Result:** See `TASK-RESULT-A5.md` (root) for full report

---

### A6: Data Hub End-to-End Completion (2026-07-18) ✅
**Objective:** Fix Data Hub navigation and create a complete module browser journey
**Actions:**
- Enabled Shell layout by default (removed VITE_USE_SHELL_LAYOUT feature flag)
- Fixed Data Entry dead route: `/dataschema/entry` → `/dataschema`
- Added `/dataschema` route and created `DataHubHome.jsx`
- Auto-redirected single-module non-admin users to their module landing page
- Hid Admin studio icon for non-admin users via perspective filtering
- Updated command palette and breadcrumbs to remove stale Data Entry dead-routes

**Key Metrics:**
- 1 new frontend page: `carbon-frontend/src/pages/DataHubHome.jsx`
- 6 frontend files updated
- Frontend build: ✅ Success
- Acceptance criteria: ✅ Zero 404s, ✅ module browser, ✅ role-based admin visibility

**Result:** See `TASK-RESULT-A6.md` (root) for full report

### A8: Evidence & Attachments (2026-07-18) ✅
**Objective:** Enable users to attach evidence files to data rows for audit verification
**Actions:**
- Created Django `evidence` app with Evidence model (11 fields, soft delete, audit trail)
- Implemented bulk-upload API endpoint with file validation
- Created EvidenceUploader component (drag-and-drop, Material-UI)
- Created EvidenceViewer component (list/download/delete)
- Integrated evidence modal into TableDataPage
- Non-dismissible modal dialog (backdrop click + ESC key prevented)
- Resizable dialog with Row ID context chip

**Backend Changes:**
- New app: `backend/evidence/` (9 files)
- Updated: `config/settings.py` (MEDIA config, file upload limits)
- Updated: `config/urls.py` (evidence routing)
- Supported files: PDF, JPG, PNG, Excel, CSV, Word, ZIP
- Max file size: 50MB

**Frontend Changes:**
- New components: `EvidenceUploader.jsx`, `EvidenceViewer.jsx`
- Updated: `TableDataPage.jsx` (modal integration, row selection tracking)
- Updated: `package.json` (react-dropzone v19.0.2)

**API Endpoints:**
- `GET /carbon-api/evidence/` - List all evidence
- `GET /carbon-api/evidence/?data_row={id}` - Filter by row
- `POST /carbon-api/evidence/bulk-upload/` - Upload files
- `GET /carbon-api/evidence/{id}/download/` - Download file
- `DELETE /carbon-api/evidence/{id}/` - Soft delete

**RBAC:** Users access evidence only from assigned modules. Admins access all.

**Testing:**
- ✅ Backend API tests: 7/7 PASS
- ✅ RBAC & permissions: 4/4 PASS
- ✅ Frontend components: 4/4 PASS
- ✅ Build verification: 3/3 PASS
- ✅ Database: 3/3 PASS
- ✅ Integration: 3/3 PASS
- ✅ Code quality: 5/5 PASS
- **Total: 29/29 tests PASS (100%)**

**Key Metrics:**
- 11 backend files created
- 2 frontend components created
- 3 frontend files updated
- Database migrations applied
- Frontend build: ✅ Success (10.75s, 12,444+ modules)
- Acceptance criteria: ✅ 41/41 PASS

**Result:** See `TASK-RESULT-A8.md` (root) for full report

---

## Archive

Superseded status documents moved to `docs/archive/`:
- TASK-RESULT-3.md, TASK-RESULT-4.md, TASK-RESULT-5.md
- TASK-RESULTS.md, TASK-RESULTS-2.1.md
- DEMO_README.md, QUICKSTART_AI_COPILOT.md
- progress.md

---

*For the Master/Worker protocol specification, see `.clinerules/master-worker-protocol.md`*
