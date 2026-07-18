# Carbon Data Trust Platform — RUN Log

This is the authoritative log of all Master/Worker RUNs for the Carbon project.

## Active RUN Sequence (A0–A6)

| RUN | Title | Type | Status | Date | Result |
|-----|-------|------|--------|------|--------|
| A0 | Ground-truth audit | read-only | ✅ COMPLETE | 2026-07-18 | See `TASK-RESULT.md` (root) |
| A1 | Repo hygiene & doc truth | cleanup | ✅ COMPLETE | 2026-07-18 | See `TASK-RESULT-A1.md` (root) |
| A2 | Core governance RBAC fix | backend | ✅ COMPLETE | 2026-07-18 | See `TASK-RESULT-A2.md` (root) |
| A3 | Data-owner scoped experience | backend | ✅ COMPLETE | 2026-07-18 | See `TASK-RESULT-A3.md` (root) |
| A4 | Admin experience | backend+frontend | ⏳ PENDING | — | — |
| A5 | Data Trust surfacing decision | design+build | ⏳ PENDING | — | — |
| A6 | Deployment-readiness gate | ops | ⏳ PENDING | — | — |

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

---

## Archive

Superseded status documents moved to `docs/archive/`:
- TASK-RESULT-3.md, TASK-RESULT-4.md, TASK-RESULT-5.md
- TASK-RESULTS.md, TASK-RESULTS-2.1.md
- DEMO_README.md, QUICKSTART_AI_COPILOT.md
- progress.md

---

*For the Master/Worker protocol specification, see `.clinerules/master-worker-protocol.md`*
