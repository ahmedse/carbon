# CARBON SYSTEM AUDIT & CLEANUP MANIFEST

**Date:** 2026-07-29
**Auditor:** Master Architect
**Scope:** Entire `/home/ahmed/aast/carbon` workspace (excl. `.git`, `node_modules`, `venv/`)
**Total clean project size:** 23MB (excl venvs/node_modules/.git)

---

## EXECUTIVE SUMMARY

| Category | Count | Est. Savings | Priority |
|---|---|---|---|
| Root TASK/TASK-RESULT files | 27 files | ~500KB | **P0** |
| Root other .md plans | 10 files | ~300KB | **P0** |
| Superseded `ai_copilot` app | 1 app dir | ~100KB | **P0** |
| Frontend AI copilot components | 7 files | ~65KB | **P0** |
| Backend dump/data files | 5 files | ~1.7MB | **P0** |
| Backend `venv/` (1.5GB!) | 1 dir | **1.5GB** | **P0** |
| Frontend duplicate components | 7 files | ~40KB | **P1** |
| Docs binary/xlsx/csv | 5 files | ~150KB | **P1** |
| Docs deprecated app folders | 3 dirs | ~100KB | **P1** |
| Docs archive/ | 20 files | ~200KB | **P1** |
| Raw/ (proposal materials) | 8 files | ~2MB | **P1** |
| Logs, runtime artifacts | various | ~70KB | **P1** |
| Root utility scripts | 2 files | ~10KB | **P2** |
| Plans/ historical | 15+ files | ~200KB | **P2** |
| `backend/venv/` vs `.venv/` | 1 conflict | 1.5GB | **P0** |
| `.clinerules/`, `.continue/` | 2 dirs | ~10KB | **P2** |
| | | | |
| **TOTAL POTENTIAL SAVINGS** | | **~1.5GB+** | |

---

## 1. ROOT LEVEL — 38 Markdown Files (MASSIVE CLUTTER)

### 1A. TASK Spec Files (15 files) — REMOVE or ARCHIVE
These are completed task specifications. All have corresponding TASK-RESULT files.

```
TASK-API-DOCUMENTATION-COMPLETENESS.md       (56 KB)
TASK-CARBON-ARCHITECTURE-FIXES.md
TASK-CARBON-P1-SCOPED-OWNER-APPS.md
TASK-CARBON-P2-REPORT-FACTOR.md
TASK-CARBON-PHASE1-UI-WORKFLOWS.md
TASK-CARBON-PRODUCTION-WORKFLOWS.md
TASK-DATA-ENTRY-TOOL.md
TASK-DQ-DASHBOARD-UI.md
TASK-DQ-EXECUTION-PHASE1.md
TASK-GOVERNANCE-AUDIT-TRAIL.md
TASK-MOVE1-CARBON-SEAM.md
TASK-MOVE2-CARBON-REGISTRY.md
TASK-OPERATIONAL-EXCELLENCE.md
TASK-PLATFORM-RBAC-ADMIN.md
TASK-REFERENCE-DATA-GOVERNANCE.md
```

### 1B. TASK-RESULT Files (12 files) — REMOVE or ARCHIVE
Task execution results. All tasks are complete.

```
TASK-RESULT-CARBON-ARCHITECTURE-FIXES-COMPLETE.md
TASK-RESULT-CARBON-P2-COMPLETE.md
TASK-RESULT-CARBON-P2-G1.md
TASK-RESULT-CARBON-P2-G2-PARTIAL.md
TASK-RESULT-DQ-EXECUTION-PHASE1.md
TASK-RESULT-GOVERNANCE-AUDIT-TRAIL.md
TASK-RESULT-MOVE1-G1.md
TASK-RESULT-MOVE1-G2.md
TASK-RESULT-MOVE2-G1.md
TASK-RESULT-MOVE2-G2.md
TASK-RESULT-OPERATIONAL-EXCELLENCE.md
TASK-RESULT-REFERENCE-DATA-GOVERNANCE.md
```

### 1C. Other Root Plans (10 files) — CONSOLIDATE into docs/ or REMOVE
```
CARBON_P1_SCOPED_OWNER_APPS_SYSTEM_AUDIT.md
CARBON_PRODUCTION_ROADMAP.md
CARBON_WORKFLOWS_AND_PROCESSES.md
DEPLOYMENT_PLAN_AASTMT_CARBON.md
DESIGN_ROW_DETAIL_PAGE_REFINED.md
MASTER-WORKER-PROTOCOL.md
PLAN_GROUPS_ROLES_COMPLETE_MGMT.md
QUICKSTART_DEPLOYMENT.md
TRACK_E_EXECUTION_PLAN.md
install.md
```

### 1D. Non-MD Root Files
| File | Verdict |
|---|---|
| `index_project.py` | REMOVE — one-off indexing script, references old files (progress.md, Carbon-design-v1.0.md) |
| `combined-apps_nginx.example` | MOVE to docs/ or backend/ |
| `manage.sh` | KEEP (operational) |
| `docker-compose.yml` | KEEP |
| `README.md` | KEEP |

---

## 2. BACKEND — 1.5GB of Cruft

### 2A. CRITICAL: Duplicate Virtual Environments
| Path | Size | Action |
|---|---|---|
| `backend/venv/` | **1.5 GB** | REMOVE — venvs belong OUTSIDE the source tree or gitignored |
| `.venv/` (root) | 13 MB | KEEP — this is the project `.venv` |

**RECOMMENDATION:** Delete `backend/venv/`. The project should use a single `.venv/` at root. If both are needed, at minimum gitignore `backend/venv/`.

### 2B. Superseded App: `backend/ai_copilot/` — REMOVE
Marked as **SUPERSEDED** in `project.config.md`. Pulse is the external AI/RAG system.

Files to remove:
```
backend/ai_copilot/__init__.py
backend/ai_copilot/admin.py
backend/ai_copilot/apps.py
backend/ai_copilot/models.py
backend/ai_copilot/serializers.py
backend/ai_copilot/urls.py
backend/ai_copilot/views.py
backend/ai_copilot/README.md
backend/ai_copilot/management/commands/ingest_knowledge.py   (13.6 KB)
backend/ai_copilot/management/commands/test_ai_copilot.py    (3.9 KB)
backend/ai_copilot/services/context_engine.py
backend/ai_copilot/services/document_loader.py
backend/ai_copilot/services/memory.py
backend/ai_copilot/services/poe_client.py
backend/ai_copilot/services/rag_engine.py
backend/ai_copilot/services/text_chunker.py
```

**Also remove** the `ai_copilot` entry from `INSTALLED_APPS` in `backend/config/settings.py`.

### 2C. Database Dumps & Binary Artifacts — REMOVE
| File | Size | Note |
|---|---|---|
| `backend/carbon_data_20260112.json` | 911 KB | Seed data dump |
| `backend/carbon_dev_20260112.sql` | 491 KB | SQL dump |
| `backend/carbon_dev.dump` | 156 KB | Binary pg_dump |
| `backend/carbon_dev_20260112.dump` | 146 KB | Binary pg_dump |
| `backend/dump.rdb` | 5.3 KB | Redis dump |

.gitignore already covers `*.dump`, `*.sql`, and `dump.rdb` — these should never have been committed.

### 2D. `backend/chroma_db/` (1.7 MB) — REMOVE
Pulse's Chroma vector store. Runtime data, not source code. Already gitignored.

### 2E. Backend `package.json` / `package-lock.json` — REMOVE
Frontend tooling inside backend directory. These belong in `carbon-frontend/` only.

### 2F. `backend/assets/style.css` — REMOVE
Django admin static theme override. Unused in Carbon.

### 2G. Test Artifacts — REMOVE
- `backend/.coverage` (52 KB)
- `backend/.pytest_cache/` (44 KB)

---

## 3. FRONTEND — Duplicates & Superseded Code

### 3A. Duplicate Header Generations (3 versions!)
| File | Lines | Status |
|---|---|---|
| `components/Header.jsx` | 180 | V1 — remove |
| `components/HeaderEnhanced.jsx` | 300 | V2 — remove |
| `components/HeaderNew.jsx` | 459 | V3 — **KEEP, rename to Header.jsx** |

### 3B. Duplicate Footer Generations
| File | Lines | Status |
|---|---|---|
| `components/Footer.jsx` | 15 | V1 — remove |
| `components/FooterNew.jsx` | 72 | V2 — **KEEP, rename to Footer.jsx** |

### 3C. Duplicate Sidebar Evolutions
| File | Lines | Status |
|---|---|---|
| `components/Sidebar.jsx` | 95 | V1 — remove |
| `components/SidebarMenu.jsx` | 664 | V2 — verify if used, else remove |
| `shell/ShellSidebar.jsx` | 394 | V3 in shell — **KEEP** |

### 3D. Duplicate PageHeader
| File | Lines | Status |
|---|---|---|
| `components/Page/PageHeader.jsx` | — | Part of reusable primitives |
| `components/layout/PageHeader.jsx` | — | Duplicate — **CONSOLIDATE** |

### 3E. Superseded AI Components — REMOVE
Pulse replaced `ai_copilot`. These are dead code:
```
components/ai/AICopilotPanel.jsx         (20 KB)
components/ai/AICopilotPanel_old.jsx     (26 KB!) — "old" in filename = instant removal
components/ai/AIPreferencesDialog.jsx    (6 KB)
components/ai/ChatMessage.jsx            (9 KB)
components/ai/ProactiveInsightCard.jsx   (3 KB)
components/ai/index.js
api/aiCopilot.js
shell/CopilotPane.jsx                    (5 KB)
```

### 3F. Legacy Theme — REMOVE
| File | Note |
|---|---|
| `src/theme.js` | Superseded by `src/theme/carbonTheme.js` |

---

## 4. DOCS — Data Files, Deprecated Apps, Archive

### 4A. Binary/Data Files (NOT documentation) — REMOVE
```
docs/Medicine Staff Transportation for Summer.csv
docs/Medicine Staff Transportation for Summer.xlsx
docs/Smart_ AASTMT Carbon Emmission_07-07-2025_Magdy.xlsx
docs/Transportation_Summary_by_BusLine_and_Date.csv
docs/Transportation_Summary_by_BusLine_and_Date.xlsx
```

### 4B. Deprecated App Folders — REMOVE
These are design docs for old app structures:
```
docs/dataschema_app/dataschema-design-v1.0.md
docs/importexport_app/importexport-design-v1.0.md
docs/reports_app/CARBON_INTELLIGENCE_MANIFESTO.md       (59 KB)
docs/reports_app/BACKEND_MVP_COMPLETE.md
docs/reports_app/REPORT_MANAGER_DESIGN.md
docs/reports_app/AI_COPILOT_ARCHITECTURE.md
```

### 4C. Archive — REMOVE
20 historical files in `docs/archive/`. All obsolete task results, cleanup manifests, old plans.

### 4D. Other Doc Issues
- `docs/tmp.md` — temporary notes, REMOVE
- `docs/RUN_LOG.md` — runtime log, REMOVE

---

## 5. RAW — Original Proposal Materials — ARCHIVE OUTSIDE REPO
The entire `raw/` directory (8 files, 2.1 MB) contains original proposal materials:
```
raw/Carbon-design-v1.0.md                              (26 KB)
raw/Carbon-dev-roadmap_v0.1.md                         (27 KB)
raw/Carbon-v1.0.txt
raw/Proposal for AAST IT Infrastructure for Carbon Reporting.pptx  (591 KB)
raw/Smart_ AASTMT Carbon Emmission_07-07-2025_Magdy (2).xlsx        (53 KB)
raw/Smart_ AASTMT Carbon Emmission_07-07-2025_Magdy.xlsx            (53 KB)
raw/VVB - IT role proposal v0.3.docx                                (171 KB)
raw/presentation/*.png                                              (~2 MB)
```

These are source materials, not project deliverables. Move to a shared drive or archive repo.

---

## 6. PLANS — Historical Planning — CONSOLIDATE

15 markdown files + `carbon-phase/` subdirectory. These were phase planning documents. Consider:
- Merge critical architectural decisions into `.ai-toolkit/decisions/`
- Archive the rest in `docs/archive/`
- Keep ACTIVE plans only (if any remain active)

---

## 7. LOGS & RUNTIME — CLEAN
| Path | Action |
|---|---|
| `logs/backend.log` (64 KB) | TRUNCATE (keep as empty file) |
| `logs/frontend.log` (1.2 KB) | TRUNCATE |
| `logs/archive/` | REMOVE |
| `backend/logs/carbon.log` (2.8 MB) | REMOVE |
| `.pids/` | REMOVE (runtime, already partially gitignored) |

---

## 8. HIDDEN DIRECTORIES
| Path | Action |
|---|---|
| `.clinerules/` (1 file) | REMOVE — superseded by `.ai-toolkit` |
| `.continue/` (mcpServers) | KEEP or REMOVE — alternative AI tool config |

---

## 9. GITIGNORE FIXES NEEDED

Missing entries to add to `.gitignore`:
```gitignore
# Test artifacts
backend/.coverage
backend/.pytest_cache/

# Upload/runtime data directories
backend/dataschema_uploads/*
!backend/dataschema_uploads/.gitkeep
backend/mediafiles/

# Backend logs
backend/logs/

# PID files
.pids/
*.pid

# External tools
.clinerules/

# Indexing output
indexed_src/

# Project logs
logs/

# Backend venv (if keeping root .venv)
backend/venv/
```

---

## 10. PRIORITIZED CLEANUP PLAN

### PHASE 0 — Immediate (safe, high impact)
1. **Delete `backend/venv/`** — 1.5GB reclaimed, instant
2. **Delete database dumps** (5 files: *.dump, *.sql, *.json, dump.rdb)
3. **Delete `backend/chroma_db/`**
4. **Delete `backend/.coverage`, `.pytest_cache/`**
5. **Truncate logs** (backend.log, frontend.log, carbon.log)

### PHASE 1 — Superseded & Dead Code
6. **Remove `backend/ai_copilot/`** entire app + remove from INSTALLED_APPS
7. **Remove frontend AI components** (7 files in `components/ai/` + `api/aiCopilot.js` + `shell/CopilotPane.jsx`)
8. **Remove duplicate components** (Header.jsx, HeaderEnhanced.jsx, Footer.jsx, Sidebar.jsx)
9. **Remove legacy `src/theme.js`**

### PHASE 2 — Root Clutter
10. **Archive all TASK/TASK-RESULT files** → move to `docs/archive/`
11. **Archive root .md plans** → move to `docs/archive/` or `plans/`
12. **Delete `index_project.py`**, `install.md`(if not maintained)

### PHASE 3 — Docs Cleanup
13. **Delete binary data files** from docs/ (csv, xlsx)
14. **Delete deprecated app folders** (dataschema_app, importexport_app, reports_app)
15. **Delete docs/archive/** contents

### PHASE 4 — Raw & Plans
16. **Move `raw/`** out of repo entirely
17. **Consolidate `plans/`** — keep active, archive rest

### PHASE 5 — Fix .gitignore
18. **Add missing gitignore entries** (see Section 9)

---

## 11. SIDE-BY-SIDE: BEFORE / AFTER

| Metric | Before | After |
|---|---|---|
| Root files | 42 items | ~8 items |
| Backend apps | 12+1 superseded | 11 active apps |
| Frontend components | ~70 files | ~55 files (no dupes) |
| Docs items | 43 items | ~15 items |
| Disk usage (no venvs) | 23 MB | ~18 MB |
| `backend/venv/` | **1.5 GB** | **0** |

---

## 12. DECISION REQUIRED FROM USER

1. **TASK files:** Archive to `docs/archive/` or delete permanently?
2. **`raw/` directory:** Move to Google Drive / SharePoint, or delete?
3. **`plans/` directory:** Which plans are still active?
4. **`.continue/` directory:** Still using Continue.dev alongside Copilot?
5. **`backend/venv/` vs `.venv/`:** Which is the canonical Python environment? Keep one.
