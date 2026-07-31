# TASKS.md — Carbon Data Trust Platform Audit Remediation Plan
# Master Architect: Ahmed | Date: 2026-07-31 | Audit commit: bcebac1
#
# This document decomposes the 2026-07-31 full architecture audit into
# executable phases. Each phase names: role, files, contracts, verification gate.
# Phases are ordered by dependency — each builds on the previous.

---

## PHASE 1 — Quick Wins & Foundation Cleanup ✅ COMPLETE 2026-07-31
**Role:** Backend Worker | **Model:** DeepSeek | **Result:** TASKS-RESULT-P1.md — all 5 groups passed

**Delivered:**
- ✅ P1.1: PlatformAppConfig registered in Django admin
- ✅ P1.2: 8 ML deps removed (only numpy+pandas kept, verified imports)
- ✅ P1.3: 4 non-ML deps removed (SQLAlchemy, alembic — resolves P6-G1 dual ORM)
- ✅ P1.4: project.config.md updated (ChromaDB marked unused, debt items cleared)
- ✅ P1.5: No stale references to delete — confirmed absent
- **requirements.txt: 35 → 23 lines**

---

## PHASE 2 — Service Layer Extraction ✅ COMPLETE 2026-07-31
**Role:** Backend Worker | **Result:** TASKS-RESULT-P2.md — all 4 groups passed

**Delivered:**
- ✅ G1: accounts/services.py — RoleResolutionService, AppManifestService, PulseService (166 lines)
- ✅ G2: dataschema/services.py — BulkImportService, SchemaValidationService (160 lines)
- ✅ G3: mdm/services.py — ReferenceSetService, OrgUnitService (125 lines)
- ✅ G4: evidence, importexport, connections — 3 services, 180 lines total
- **Views: 2301 → 1963 lines (−338). Services: +631 lines. 100 tests passed.**
- All 6 apps now comply with Hard Rule #3 (views thin, logic in services)
grep -c "^def \|^class " backend/dataschema/services.py
grep -c "^def \|^class " backend/mdm/services.py
# All imports resolve
./manage.sh manage check --deploy 2>&1 | grep -i error || echo "No errors"
# Existing tests still pass
./manage.sh test accounts mdm dataschema --keepdb 2>&1 | tail -5
# API still responds
./manage.sh shell -c "from accounts.services import *; print('accounts services OK')"
```

---

## PHASE 3 — Test Coverage for Service-Heavy Apps ✅ COMPLETE 2026-07-31
**Role:** Backend Worker | **Result:** TASKS-RESULT-P3.md — 28 new tests, zero failures

**Delivered:**
- ✅ G1: emissions/test_services.py: 9→31 tests, now covers all 9 service classes (+22 new)
- ✅ G2: dq/test_executor.py: +3 direct _compute_quality unit tests
- ✅ G3: catalog/tests/test_services.py: +3 ensure_asset_profiles tests (create, idempotent, pre-existing)
- **Full suite: 310 passed + 10 subtests (was 100 in P2)**

---

## PHASE 4 — Frontend Health
**Role:** Frontend Worker | **Model:** Kimi K3 | **Est. tokens:** ~25K

### CONTRACT: shared/design-system.md, shared/ux-patterns.md

### P4-G1 — Extract custom hooks from inline data fetching
**Current state:** Only 1 hook (`useEnabledApps`). All other data fetching is inline in page components.
**Target:**
- CREATE `src/hooks/useEmissionsData.js` — extract from AnalyticsDashboard
- CREATE `src/hooks/useCatalogData.js` — extract from catalog pages
- CREATE `src/hooks/useDQData.js` — extract from DQ pages
- Each hook: loading/error/data states, caching where appropriate
- DO NOT change UI behavior — pure extraction

### P4-G2 — Delete or archive unused page files
**Files to audit for deadness:**
- `src/pages/Dashboard.jsx` — used at `/dashboard-legacy`. Is it still needed?
- `src/pages/ScopeInfoPage.jsx` — check if routed anywhere
- `src/pages/DataEntryPage.jsx` — check if routed anywhere
- `src/pages/Help.jsx` — check if routed anywhere
- `src/pages/Feedback.jsx` — check if routed anywhere
- Report findings; delete only if confirmed dead

### Verification Gate (P4)
```bash
cd carbon-frontend
npm run build 2>&1 | tail -3  # must pass
npm run lint 2>&1 | tail -5    # if linter configured
# Count hooks
ls src/hooks/*.js | wc -l  # should be >= 4 after P4-G1
```

---

## PHASE 5 — Advanced Patterns & Tech Debt
**Role:** Backend Worker (G1, G3), Frontend Worker (G2) | **Model:** DeepSeek / Kimi K3

### P5-G1 — seed_all.py Builder pattern refactor
**Why:** 26K lines of procedural seeding. Known tech debt.
**Files:**
- REFACTOR `backend/seed_all.py` → `SeedBuilder` class with chainable methods
- Pattern: Builder (design-patterns.md §Builder)
- `SeedBuilder().with_users().with_factors().with_targets().run()`
- DO NOT change seed data — only structure

### P5-G2 — Frontend inline sx → theme tokens
**Why:** Known tech debt per project.config.md. `HeaderEnhanced.jsx` and others.
**Files:**
- AUDIT: find all `sx={{` with raw px/hex values in src/
- REFACTOR: move to theme tokens or styled components
- DO NOT change visual appearance

### P5-G3 — Command/Undo pattern for DQ and data entry
**Why:** No undo in DQ rules, data entry, schema changes. Pattern gap.
**Files:**
- DESIGN only (Master Architect task): spec the Command pattern interface
- Which operations need undo? DQ rule create/edit/delete, data row edit, schema field change?
- Write ADR-0002: Command Pattern for Reversible Operations

### Verification Gate (P5)
```bash
# Builder: seed succeeds
./manage.sh manage seed_all 2>&1 | tail -5
# No raw sx with px/hex (verify.sh antipatterns)
./.ai-toolkit/scripts/verify.sh frontend
# ADR written
ls .ai-toolkit/decisions/0002-command-pattern.md
```

---

## PHASE 6 — Remaining Audit Items (Lower Priority)
**Role:** Various | **Model:** Budget-appropriate

### P6-G1 — Dual ORM resolution ✅ RESOLVED by P1-G3
**Why:** SQLAlchemy + alembic removed in Phase 1 — zero imports found anywhere.

### P6-G2 — Frontend test scaffolding (Frontend Worker)
**Why:** Zero frontend tests.
**Target:** Add Vitest + React Testing Library. Write 3 smoke tests.
**Files:** CREATE `carbon-frontend/src/__tests__/PlatformHome.test.jsx`

### P6-G3 — Regenerate registry (any role)
**Why:** Registry was last generated 2026-07-29, now stale after ai_copilot removal + dashboard cleanup.
**Run:** `./.ai-toolkit/scripts/scan.sh` → commit updated registry

---

## DEPENDENCY GRAPH
```
P1 (Quick Wins) ─────────────────────────────────────────────────────────────┐
    ↓                                                                         │
P2 (Service Extraction) ── depends on P1 (clean foundation)                   │
    ↓                                                                         │
P3 (Tests) ─────────────── depends on P2 (services exist to test)             │
    ↓                                                                         │
P4 (Frontend) ──────────── independent of P2/P3, can run parallel             │
    ↓                                                                         │
P5 (Advanced Patterns) ─── depends on P2 (services in place) + P3 (safe refactor)
    ↓                                                                         │
P6 (Remaining) ─────────── independent, can run anytime                       │
```

## EXECUTION ORDER
```
P1 → P2-G1 → P2-G2 → P2-G3 → P2-G4 → P3-G1 → P3-G2 → P3-G3 → P4-G1 → P4-G2 → P5-G1 → P5-G2 → P5-G3 → P6-G1 → P6-G2 → P6-G3
              \                                                              /
               P4 can start anytime after P1 ──────────────────────────────
```

## ROLE ASSIGNMENT SUMMARY
| Phase | Role | Model | Est. Tokens |
|---|---|---|---|
| P1 | Backend Worker | DeepSeek | 15K |
| P2-G1→G4 | Backend Worker | DeepSeek | 40K |
| P3-G1→G3 | Backend Worker | DeepSeek | 35K |
| P4-G1→G2 | Frontend Worker | Kimi K3 | 25K |
| P5-G1 | Backend Worker | DeepSeek | 20K |
| P5-G2 | Frontend Worker | Kimi K3 | 10K |
| P5-G3 | Master Architect | DeepSeek-R1 | 5K |
| P6 | As assigned | Budget | 15K |
| **Total** | | | **~165K tokens** |
