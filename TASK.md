# TASK.md — RUN A1: Repo Hygiene & Doc Truth

---

## MASTER CONTEXT

**Protocol:** Master/Worker handoff (see `.clinerules/master-worker-protocol.md`)  
**Master:** Planner (this file's author)  
**Worker:** Raptor/Copilot (executor)  
**Active RUN sequence:** A0 ✅ → **A1** → A2 → A3 → A4 → A5 → A6

**Previous RUN (A0) findings:**
- ✅ Data-owner read scoping works perfectly
- ❌ Deployment blockers: DEBUG/SECRET_KEY hardcoded, secrets committed, dumps in git
- ⚠️ ai_copilot still wired despite strategy freeze
- ⚠️ 9 superseded TASK-RESULT*.md files + 5 data artifacts cluttering repo

**Roadmap:**
- **A0** ✅: Ground-truth audit (read-only) — COMPLETE
- **A1** (this RUN): Repo hygiene & doc truth — clean foundation before deeper work
- **A2**: Core governance RBAC fix (org-scope catalog/mdm/dq writes)
- **A3**: Data-owner scoped experience — verify & close gaps
- **A4**: Admin experience — verify & close gaps
- **A5**: Data Trust surfacing decision (React screens vs Pulse API feed)
- **A6**: Deployment-readiness gate

---

## 1. HEADER

**RUN ID:** A1  
**Title:** Repo Hygiene & Doc Truth  
**Type:** CLEANUP  
**Worker:** Raptor  
**Master:** Planner  
**Date Issued:** 2026-07-18

---

## 2. OBJECTIVE

Clean the repository foundation before deeper architectural work (A2–A6). Remove contradictions between strategy docs and live code, archive superseded artifacts, de-git committed secrets/dumps, and establish a single source of truth for project status. This creates a clean baseline so future workers (human or AI) aren't misled by stale/contradictory material.

**Success:** A clean, truthful repo where docs match code, no secrets/dumps in git, and one authoritative status log.

---

## 3. SCOPE — IN

- **Freeze/quarantine ai_copilot app** (strategy says superseded by Pulse)
- **Fix stale design doc** (`DESIGN_DATA_TRUST_CORE.md §3` still references removed `Project` model)
- **Archive superseded status docs** (9 TASK-RESULT*.md files → `docs/archive/`)
- **De-git committed secrets** (`.env.production` files)
- **De-git data artifacts** (4 dumps/SQL files, `dump.rdb`)
- **Update .gitignore** to prevent re-commit
- **Create single RUN log** (`docs/RUN_LOG.md`) as authoritative status tracker

---

## 4. SCOPE — OUT (DO NOT TOUCH)

- **No RBAC/permission changes** (that's A2)
- **No frontend work** (that's A3/A4/A5)
- **No deployment config changes** (DEBUG/SECRET_KEY/ALLOWED_HOSTS — that's A6)
- **No schema migrations** (additive or otherwise)
- **No deletion of ai_copilot code** — only quarantine (comment out URL wiring, add deprecation notice)
- **No Pulse/AI/LLM exploration**
- **No tenant work**

---

## 5. PRECONDITIONS / SETUP

1. **A0 audit complete** — `TASK-RESULT.md` exists with findings
2. **Working git** — `git status` shows clean or known-dirty state
3. **Backup before de-git operations** — worker must create a local backup of dumps/secrets before removing from git (in case they're needed for recovery)

---

## 6. CONSTRAINTS (MUST / MUST NOT)

### MUST:
- Create `docs/archive/` directory before moving files
- Backup `.env.production` and dump files to a **non-git location** (e.g., `~/carbon-backups/`) before removing from git
- Use `git rm --cached` (not `rm`) to remove files from git while keeping local copies
- Test that backend still boots after ai_copilot URL is commented out
- Commit changes in **logical groups** (one commit per major change: ai_copilot freeze, doc fixes, archive moves, de-git secrets, de-git dumps, .gitignore updates)
- Paste the exact git commands and their output

### MUST NOT:
- Delete any code files (only move/comment/document)
- Break the backend boot (test after each change)
- Remove files from disk that might be needed (backup first)
- Modify any permission/RBAC logic
- Change any model definitions or migrations

---

## 7. STEPS

### Step 1: Freeze ai_copilot App

**Objective:** Quarantine the ai_copilot app per strategy docs without deleting code (preserve for reference).

**Commands:**
```bash
cd /home/ahmed/aast/carbon/backend

# 1.1 Comment out ai_copilot URL wiring
# Edit config/urls.py: comment line 45 (path(f'{api_prefix}/ai/', include('ai_copilot.urls')))
# Add comment: "# FROZEN 2026-07-18: ai_copilot superseded by external Pulse (see STRATEGY_DATA_TRUST_PLATFORM.md)"

# 1.2 Create deprecation notice in ai_copilot/README.md
cat > ai_copilot/README.md << 'EOF'
# AI Copilot App — FROZEN

**Status:** DEPRECATED as of 2026-07-18  
**Reason:** Superseded by external Pulse system (see `docs/STRATEGY_DATA_TRUST_PLATFORM.md`)

This app is preserved for reference but is no longer active:
- URL routes commented out in `config/urls.py`
- No new features or fixes
- `chroma_db/` vector store frozen

**For AI/LLM features, use the external Pulse integration.**
EOF

# 1.3 Test backend boots
python manage.py check

# 1.4 Commit
git add config/urls.py ai_copilot/README.md
git commit -m "chore: freeze ai_copilot app (superseded by Pulse)"
```

**Record:**
- Exact line commented in `config/urls.py`
- `manage.py check` output (must be clean)
- Git commit hash

---

### Step 2: Fix Stale Design Doc

**Objective:** Update `DESIGN_DATA_TRUST_CORE.md §3` to reflect that `Project` was removed in favor of `OrgUnit`.

**Commands:**
```bash
cd /home/ahmed/aast/carbon

# 2.1 Locate the stale reference
grep -n "Project" docs/DESIGN_DATA_TRUST_CORE.md

# 2.2 Edit docs/DESIGN_DATA_TRUST_CORE.md
# Find the table in §3 that lists core models
# Replace any "Project" references with "OrgUnit" and note the change
# Add a footnote: "Note: Project model was replaced by OrgUnit in Phase 1 (see RUN 5 results)"

# 2.3 Commit
git add docs/DESIGN_DATA_TRUST_CORE.md
git commit -m "docs: fix stale Project reference in DESIGN_DATA_TRUST_CORE.md (replaced by OrgUnit)"
```

**Record:**
- Line numbers where "Project" was found
- Exact changes made
- Git commit hash

---

### Step 3: Archive Superseded Status Docs

**Objective:** Move 9 superseded TASK-RESULT*.md files to `docs/archive/` to declutter root.

**Commands:**
```bash
cd /home/ahmed/aast/carbon

# 3.1 Create archive directory
mkdir -p docs/archive

# 3.2 Move superseded files (keep current TASK.md and TASK-RESULT.md)
git mv TASK-RESULT-3.md docs/archive/
git mv TASK-RESULT-4.md docs/archive/
git mv TASK-RESULT-5.md docs/archive/
git mv TASK-RESULTS.md docs/archive/
git mv TASK-RESULTS-2.1.md docs/archive/
git mv DEMO_README.md docs/archive/
git mv QUICKSTART_AI_COPILOT.md docs/archive/
git mv progress.md docs/archive/

# 3.3 Commit
git commit -m "chore: archive superseded status docs to docs/archive/"
```

**Record:**
- List of files moved
- Git commit hash

---

### Step 4: De-git Committed Secrets

**Objective:** Remove `.env.production` from git while preserving local copy.

**Commands:**
```bash
cd /home/ahmed/aast/carbon

# 4.1 Backup to non-git location
mkdir -p ~/carbon-backups/secrets
cp backend/.env.production ~/carbon-backups/secrets/.env.production.backup-$(date +%Y%m%d)
ls -lh ~/carbon-backups/secrets/

# 4.2 Remove from git (keep local file)
git rm --cached backend/.env.production

# 4.3 Add to .gitignore
echo "" >> .gitignore
echo "# Environment files with secrets" >> .gitignore
echo ".env.production" >> .gitignore
echo "backend/.env.production" >> .gitignore

# 4.4 Commit
git add .gitignore
git commit -m "security: remove .env.production from git, add to .gitignore"
```

**Record:**
- Backup location and file size
- Git commit hash
- Confirm `.env.production` still exists locally: `ls -lh backend/.env.production`

---

### Step 5: De-git Data Artifacts

**Objective:** Remove 4 dump/SQL files and `dump.rdb` from git.

**Commands:**
```bash
cd /home/ahmed/aast/carbon

# 5.1 Backup to non-git location
mkdir -p ~/carbon-backups/dumps
cp backend/carbon_dev.dump ~/carbon-backups/dumps/
cp backend/carbon_dev_20260112.dump ~/carbon-backups/dumps/
cp backend/carbon_dev_20260112.sql ~/carbon-backups/dumps/
cp backend/carbon_data_20260112.json ~/carbon-backups/dumps/
cp backend/dump.rdb ~/carbon-backups/dumps/
ls -lh ~/carbon-backups/dumps/

# 5.2 Remove from git (keep local files for now)
git rm --cached backend/carbon_dev.dump
git rm --cached backend/carbon_dev_20260112.dump
git rm --cached backend/carbon_dev_20260112.sql
git rm --cached backend/carbon_data_20260112.json
git rm --cached backend/dump.rdb

# 5.3 Update .gitignore
echo "" >> .gitignore
echo "# Database dumps and backups" >> .gitignore
echo "*.dump" >> .gitignore
echo "*.sql" >> .gitignore
echo "dump.rdb" >> .gitignore
echo "backend/dump.rdb" >> .gitignore

# 5.4 Commit
git add .gitignore
git commit -m "chore: remove database dumps from git, add to .gitignore"
```

**Record:**
- Backup location and total size
- Git commit hash
- Confirm files still exist locally: `ls -lh backend/*.dump backend/*.sql backend/dump.rdb`

---

### Step 6: Update .gitignore for Data Directories

**Objective:** Prevent `chroma_db/` and `dataschema_uploads/` contents from being committed.

**Commands:**
```bash
cd /home/ahmed/aast/carbon

# 6.1 Add data directories to .gitignore
echo "" >> .gitignore
echo "# Data directories (contents should not be committed)" >> .gitignore
echo "backend/chroma_db/" >> .gitignore
echo "backend/dataschema_uploads/*" >> .gitignore
echo "!backend/dataschema_uploads/.gitkeep" >> .gitignore

# 6.2 Create .gitkeep to preserve directory structure
touch backend/dataschema_uploads/.gitkeep

# 6.3 Commit
git add .gitignore backend/dataschema_uploads/.gitkeep
git commit -m "chore: add data directories to .gitignore, preserve structure with .gitkeep"
```

**Record:**
- Git commit hash

---

### Step 7: Create Single RUN Log

**Objective:** Establish `docs/RUN_LOG.md` as the authoritative status tracker (replaces scattered TASK-RESULT*.md files).

**Commands:**
```bash
cd /home/ahmed/aast/carbon

# 7.1 Create RUN_LOG.md
cat > docs/RUN_LOG.md << 'EOF'
# Carbon Data Trust Platform — RUN Log

This is the authoritative log of all Master/Worker RUNs for the Carbon project.

## Active RUN Sequence (A0–A6)

| RUN | Title | Type | Status | Date | Result |
|-----|-------|------|--------|------|--------|
| A0 | Ground-truth audit | read-only | ✅ COMPLETE | 2026-07-18 | See `TASK-RESULT.md` (root) |
| A1 | Repo hygiene & doc truth | cleanup | 🔄 IN PROGRESS | 2026-07-18 | TBD |
| A2 | Core governance RBAC fix | backend | ⏳ PENDING | — | — |
| A3 | Data-owner scoped experience | backend+frontend | ⏳ PENDING | — | — |
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

### A1: Repo Hygiene & Doc Truth (2026-07-18) 🔄
**Objective:** Clean foundation before deeper work  
**Actions:**
- Freeze ai_copilot app (comment URL, add deprecation notice)
- Fix stale DESIGN_DATA_TRUST_CORE.md (Project → OrgUnit)
- Archive 9 superseded status docs to docs/archive/
- De-git .env.production and 5 data artifacts
- Update .gitignore to prevent re-commit
- Create this RUN_LOG.md as single source of truth

**Result:** TBD

---

## Archive

Superseded status documents moved to `docs/archive/`:
- TASK-RESULT-3.md, TASK-RESULT-4.md, TASK-RESULT-5.md
- TASK-RESULTS.md, TASK-RESULTS-2.1.md
- DEMO_README.md, QUICKSTART_AI_COPILOT.md
- progress.md

---

*For the Master/Worker protocol specification, see `.clinerules/master-worker-protocol.md`*
EOF

# 7.2 Commit
git add docs/RUN_LOG.md
git commit -m "docs: create RUN_LOG.md as authoritative status tracker"
```

**Record:**
- Git commit hash

---

### Step 8: Final Verification

**Objective:** Confirm backend still boots and git is clean.

**Commands:**
```bash
cd /home/ahmed/aast/carbon/backend

# 8.1 Test backend boots
python manage.py check

# 8.2 Check git status
cd ..
git status

# 8.3 Review commit history
git log --oneline -10

# 8.4 Verify backups exist
ls -lh ~/carbon-backups/secrets/
ls -lh ~/carbon-backups/dumps/
```

**Record:**
- `manage.py check` output (must be clean)
- `git status` output (should show untracked .clinerules/ and setup_carbon_dq.py only)
- Last 10 commit hashes
- Backup directory sizes

---

## 8. ACCEPTANCE CRITERIA

| # | Criterion | Pass Threshold | Status | Evidence Ref |
|---|-----------|----------------|--------|--------------|
| AC1 | ai_copilot URL commented out | Line 45 in config/urls.py commented + deprecation notice added | | Step 1 |
| AC2 | Backend boots after ai_copilot freeze | `manage.py check` exit 0 | | Step 1, 8 |
| AC3 | DESIGN doc fixed | "Project" replaced with "OrgUnit" in §3 | | Step 2 |
| AC4 | Status docs archived | 8 files moved to docs/archive/ | | Step 3 |
| AC5 | Secrets de-git | .env.production removed from git, backed up, in .gitignore | | Step 4 |
| AC6 | Dumps de-git | 5 files removed from git, backed up, in .gitignore | | Step 5 |
| AC7 | Data dirs in .gitignore | chroma_db/, dataschema_uploads/* added | | Step 6 |
| AC8 | RUN_LOG.md created | File exists at docs/RUN_LOG.md with A0–A6 table | | Step 7 |
| AC9 | Git commits logical | 7 commits (one per major change) with clear messages | | Steps 1-7 |
| AC10 | Backups verified | ~/carbon-backups/ contains secrets/ and dumps/ subdirs | | Step 8 |

**Worker: fill the "Status" column with PASS/FAIL and reference the step where evidence is found.**

---

## 9. DELIVERABLE FORMAT

**File:** `TASK-RESULT.md` (overwrite the A0 result, or create `TASK-RESULT-A1.md` if you prefer to preserve A0)

**Required structure:**

```markdown
# TASK-RESULT.md — RUN A1: Repo Hygiene & Doc Truth

## Summary
[One paragraph: what was done, overall outcome]

## Blockers
[List any blockers encountered, or state "None"]

## Step 1: Freeze ai_copilot App
**Commands:**
[paste commands]

**Output:**
[paste raw output]

**Verdict:**
[one-line assessment]

## Step 2: Fix Stale Design Doc
[same structure]

## Step 3: Archive Superseded Status Docs
[same structure]

## Step 4: De-git Committed Secrets
[same structure]

## Step 5: De-git Data Artifacts
[same structure]

## Step 6: Update .gitignore for Data Directories
[same structure]

## Step 7: Create Single RUN Log
[same structure]

## Step 8: Final Verification
[same structure]

## Acceptance Criteria Table
[Copy the AC table from TASK.md, fill Status column with PASS/FAIL + evidence refs]

## Git Commit Summary
[List all 7 commits with hashes and messages]

## Backup Verification
[Confirm ~/carbon-backups/ contents and sizes]

## Definition of Done Status
[Explicit statement: "DoD met" or "DoD not met because..."]

## Final Git Status
```
[paste output of `git status`]
```
```

---

## 10. DEFINITION OF DONE

- All 10 acceptance criteria filled with PASS
- Backend boots cleanly (`manage.py check` exit 0)
- 7 logical git commits pushed (or ready to push)
- Backups verified in `~/carbon-backups/`
- `TASK-RESULT.md` (or `TASK-RESULT-A1.md`) returned with all required sections
- **Gate:** A1 completion unblocks A2 (Core governance RBAC fix)

---

## 11. ESCALATION

**If blocked:**
1. Stop the blocked step immediately
2. Mark it `BLOCKED: <specific reason>` in the result
3. Continue with remaining independent steps
4. Summarize all blockers at the top of `TASK-RESULT.md`
5. Never guess, assume, or fabricate missing information

**If a file edit breaks the backend:** Revert the change, mark the step BLOCKED, report the error.

**If git operations fail:** Paste the error, mark the step BLOCKED, continue with non-git steps.

**If unsure about a file path:** Mark it `BLOCKED: unclear path`, explain why, continue.

---

**END OF TASK.md — RUN A1**

**Worker (Raptor):** Execute this RUN and return `TASK-RESULT.md`. Do ONLY A1. Good luck.
