## [2026-08-16] Frontend Worker — Phase 7A: Domain Manifest Frontend Wiring

### Summary
7/7 gates passed. 5 files changed (2 created, 3 modified). 3 new tests added; full suite 399 passed, 0 failed, 0 skipped.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Add `listDomainManifests` to `src/api/aiPulse.js` | ✅ | 1 function, reuses `BASE` + `apiFetch` |
| 2 | Extend `AIEmptyState.jsx` with `manifests` + `onStartStarter` | ✅ | Chips above "Start a Chat", generic fallback preserved |
| 3 | Wire manifests + starter handler into `AIWorkspace.jsx` | ✅ | `useState` + mount `useEffect` + `handleStartStarter`, both empty-state sites |
| 4 | Create `AIDomainManifest.test.jsx` | ✅ | 3 tests: chip render, exact arg forward, fallback |

### Files Changed
| Action | File | Lines | What |
|--------|------|-------|------|
| MODIFY | `carbon-frontend/src/api/aiPulse.js` | +9 | Added `listDomainManifests(token)` → `GET ai/pulse/apps/` |
| MODIFY | `carbon-frontend/src/shell/AIEmptyState.jsx` | +62 | Added `manifests`/`onStartStarter` props + starter-chip section + propTypes |
| MODIFY | `carbon-frontend/src/shell/AIWorkspace.jsx` | +40 | `listDomainManifests` + `sendMessage` imports, `manifests` state, mount effect, `handleStartStarter`, both `<AIEmptyState>` sites |
| MODIFY | `carbon-frontend/src/__tests__/AIWorkspace.shell.test.jsx` | +5 | Mocked `../api/aiPulse` (`listDomainManifests` resolves `{ apps: [] }`) + added `sendMessage` to aiWorkspace mock |
| CREATE | `carbon-frontend/src/__tests__/AIDomainManifest.test.jsx` | 87 | 3 manifest-wiring unit tests |

### Verification Output
```
$ npx vitest run src/__tests__/AIDomainManifest.test.jsx
 RUN  v4.1.10 /home/ahmed/aast/carbon/carbon-frontend
 Test Files  1 passed (1)
      Tests  3 passed (3)

$ npm test -- --run
 Test Files  18 passed (18)
      Tests  399 passed (399)

$ npm run lint
> eslint .

(exit 0 — clean)

$ npm run build
vite v6.3.5 building for production...
✓ 12825 modules transformed.
✓ built in 13.84s

$ ./.ai-toolkit/scripts/verify.sh frontend
Verification gate: frontend
── Frontend ────────────────────────────
✓ lint
✓ build
── Routes ──────────────────────────────
✓ route audit clean: 72 referenced path(s) resolve, 16 namespace root(s) covered
✓ route/URL audit
════════════════════════════════════════
GATE PASSED

$ grep -rn "\bitem\b.*xs=\|<Grid item\b" src/ --include="*.jsx"
(no output — empty)
```

### Deviations
NONE — implemented exactly per spec. Two pre-existing `AIWorkspace.shell.test.jsx` mock adjustments were required (mock `../api/aiPulse`, add `sendMessage`) because the component now imports those symbols; this is required for the existing suite to remain deterministic, not a spec deviation.

### Issues Found
- The `emissions` manifest's `starter_prompts.default` includes a `dq_validate` chip with no `table_id` context; task-driven chips with no entity scope open an empty conversation of that type. Entity-scoped entry points (with `table_id`) arrive in Phase 7b. (Not fixed — out of scope.)

---

## [2026-08-16] Frontend Worker — Phase 7C: Entity-Scoped Entry Points

### Summary
All gates passed. 8 files changed (4 created, 4 edited). 9 new tests added; full suite 408 passed, 0 failed.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Remove `dq_validate` from `starter_prompts.default` (Gap A) | ✅ | `emissions.py` — `default` now only `chat`; `dq_validate` still reachable via `entry_points` + `starter_prompts.table` |
| 2 | Create `useDomainManifests` hook (NEW) | ✅ | module-level cache, silent failure → `[]` |
| 3 | Create `AIDomainEntryPoints` (NEW) | ✅ | filters by `on_entity`, icon map, renders `null` on no match, always passes `app_identifier` |
| 4 | Replace hardcoded `Ask AI` in `SchemaDetailPage` | ✅ | removed `AutoAwesomeIcon`/`useAITaskTransfer`/`handleAskAI`/`tableLabel`; now `<AIDomainEntryPoints entityType="table">` |
| 5 | Add entry points to `DataProductDetailPage` | ✅ | `actions` slot with `<AIDomainEntryPoints entityType="module">` |
| 6 | Extend `enrichPayload` (Gap C, defensive) | ✅ | `dq_validate`/`investigate` table fields, `report_draft` module+period, `chat` table+module; all `?? null` |
| 7 | Create `AIDomainEntryPoints.test.jsx` (NEW) | ✅ | 5 tests: filter, null, table dispatch, module dispatch, `*` chat dispatch |
| 8 | Create `AITaskTransferContext.test.jsx` (NEW) | ✅ | 4 `enrichPayload` normalization tests |

### Files Changed
| Action | File | Lines | What |
|--------|------|-------|------|
| MODIFY | `backend/ai/domain/emissions.py` | -7 | Removed `dq_validate` from `starter_prompts.default` |
| CREATE | `carbon-frontend/src/hooks/useDomainManifests.js` | 34 | Shared manifest fetch + module cache |
| CREATE | `carbon-frontend/src/shell/AIDomainEntryPoints.jsx` | 126 | Manifest-driven entity entry points |
| MODIFY | `carbon-frontend/src/pages/catalog/SchemaDetailPage.jsx` | -35 / +9 | Hardcoded `Ask AI` → `AIDomainEntryPoints` |
| MODIFY | `carbon-frontend/src/pages/catalog/DataProductDetailPage.jsx` | +9 | `actions` slot with entry points |
| MODIFY | `carbon-frontend/src/shell/AITaskTransferContext.jsx` | +27 | `enrichPayload` cases for entity task types |
| CREATE | `carbon-frontend/src/__tests__/AIDomainEntryPoints.test.jsx` | 116 | 5 unit tests |
| CREATE | `carbon-frontend/src/__tests__/AITaskTransferContext.test.jsx` | 104 | 4 `enrichPayload` tests |

### Verification Output
```
$ cd backend && .venv/bin/python manage.py check
System check identified no issues (0 silenced).

$ .venv/bin/python manage.py makemigrations --check --dry-run
No changes detected

$ .venv/bin/python -m pytest ai -q
348 passed in 12.36s

$ cd carbon-frontend && npm test -- --run
Test Files  20 passed (20)
     Tests  408 passed (408)

$ npm run lint          # exit 0 (clean — baseline was also clean, no new errors)
$ npm run build         # ✓ built in 13.13s
$ grep -rn "\bitem\b.*xs=\|<Grid item\b" src/ --include="*.jsx"   # (no output)
```

### Deviations
NONE — implemented verbatim per spec. One note: `useDomainManifests` is used by `AIDomainEntryPoints` only; `AIWorkspace.jsx` still does its own inline `listDomainManifests` fetch (not listed in "Files to Change", so left untouched to respect scope). Flagging for a future dedup pass.

### Issues Found
- **Uncommitted working tree (pre-existing):** `git status` shows substantial uncommitted changes from Phases 6/7A/7B (backend `ai/` files, migrations, tests, docs) that predate this phase and were never committed. My 7C edits to `emissions.py` and `AITaskTransferContext.jsx` are interleaved with that prior work. I did **not** commit to avoid entangling unrelated changes — awaiting direction on commit/push scope.
