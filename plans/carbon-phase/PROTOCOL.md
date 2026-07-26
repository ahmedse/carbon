# Carbon Domain — Master-Worker Protocol v1.0

## Roles

| Role | Who | Responsibility |
|---|---|---|
| **Master** | GitHub Copilot (DeepSeek V4 Pro) | Architect, task definition, review gate, final merge |
| **Worker BE** | DeepSeek Flash session | Backend: Django models, APIs, serializers, tests, docs |
| **Worker FE** | DeepSeek Flash session | Frontend: React pages, components, routing, state |

## Communication Flow

```
Master creates TASK-BE-NN.md + TASK-FE-NN.md
     │
     ▼
User copies prompt → Worker BE / Worker FE
     │
     ▼
Worker delivers → TASK-RESULTS-BE-NN.md / TASK-RESULTS-FE-NN.md
     │
     ▼
Master reviews → Approves or rejects with fixes
     │
     ▼
Master integrates → git commit, next task
```

## Task File Format (Master → Worker)

Every TASK file must contain:

```markdown
# TASK-BE-01: [Title]

## Context (from master)
[Why this task exists, what phase it belongs to]

## Scope — DO
- [Exact, verifiable deliverables]
- [File paths, function names, API endpoints]

## Scope — DO NOT
- [Things explicitly out of scope]
- [Files not to touch]

## Prerequisites
- Read SHARED-CONTEXT.md before starting
- [Specific files to read first]

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## API Contract (if BE task)
| Method | Endpoint | Request | Response |
|---|---|---|---|

## Page Contract (if FE task)
| Route | Component | Props from API | States |
|---|---|---|---|

## Deliverables
1. Exact file paths changed/created
2. Test evidence (curl commands + output, or screenshots)
3. Known limitations / follow-ups
```

## Results File Format (Worker → Master)

```markdown
# TASK-RESULTS-BE-01: [Title]

## Summary
[2-3 sentences]

## Files Changed
| File | Action | Lines |
|---|---|---|

## API Endpoints Added/Modified
| Method | Endpoint | Status |

## Test Evidence
[curl commands + responses, or pytest output]

## Issues / Decisions Made
[Anything the master should know]

## Checklist
- [ ] All acceptance criteria met
- [ ] Tests pass
- [ ] No breaking changes to existing APIs
```

## Review Gates

1. **Syntax gate**: File parses (no syntax errors)
2. **Contract gate**: API matches TASK contract exactly
3. **Test gate**: Evidence provided and passes
4. **Integration gate**: BE + FE contracts align
5. **Style gate**: Follows PROTOCOL conventions

Master rejects if any gate fails. Worker fixes and resubmits.

## Global DO's (both workers)

- DO read SHARED-CONTEXT.md before starting ANY task
- DO follow existing code patterns (don't invent new ones)
- DO use `apiFetch()` for all frontend API calls (from `src/api/client.js`)
- DO use MUI 5 components (no custom CSS unless unavoidable)
- DO use Django REST Framework ViewSets for CRUD, APIView for custom
- DO return structured errors: `AppFeedback` exception or `{"error": "...", "code": "..."}` 
- DO add `@action` decorators for non-CRUD ViewSet endpoints
- DO include docstrings on all new functions/classes
- DO scope queries by org_unit where applicable
- DO write tests for new endpoints
- DO use the `authContext` / `useAuth()` hook for user/role info
- DO confirm file saves before declaring done
- DO append results to TASK-RESULTS.md immediately on completion

## Global DON'Ts (both workers)

- DON'T touch files outside your assigned scope
- DON'T change existing API signatures without master approval
- DON'T remove or rename existing models/fields
- DON'T introduce new npm/pip dependencies without master approval
- DON'T use `any` type in TypeScript
- DON'T hardcode URLs — use `config.js` routes or Django `reverse()`
- DON'T skip error handling
- DON'T leave console.log in production code
- DON'T create new Django apps — use existing `emissions`, `core`, `dataschema`, `mdm`, `catalog`
- DON'T reference `Tenant` (it was removed)
- DON'T import `emissions` from `core/dataschema/catalog/mdm` apps
- DON'T use inline styles — use MUI `sx` prop or `styled()`
- DON'T create pages larger than 400 lines — extract sub-components

## UI/UX Conventions (FE Worker) — FINALIZED 2026-07-26

### Density
- **Compact (B)**: `size="small"` on ALL inputs, 24px table row height, 16px card padding
- No excessive whitespace — information density over breathing room

### Color System
- **Light theme (default)**: Blue `#2563eb` primary + Zinc/slate neutrals
- **Dark theme**: Blue `#3b82f6` primary + Zinc dark neutrals
- **Theme switch**: Button in header to toggle light/dark
- Semantic colors: success `#16a34a`, warning `#d97706`, error `#dc2626` (both themes)

### Typography
- System font stack: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
- Hierarchy via `fontWeight` (400/500/600/700), not size
- No custom fonts. No Google Fonts.

### Navigation
- **Sidebar** (left, existing) for top-level app switching
- **Breadcrumb** at page top for location context
- **Tabs** for sub-page navigation (e.g., My Data: Modules | Sources)
- **Right collapsible/resizable panel** for entity metadata (click a row → side panel opens with details, lineage, DQ, audit)

### Cards
- **Style A — Minimal bordered**: `border: 1px solid divider`, `borderRadius: 2` (8px), `p: 2`, NO shadow
- Hover: border color shifts to `primary.light`, subtle

### Tables — Unified Standard (see `src/components/DataGrid/`)
- Every table in the system MUST use the shared `CarbonDataGrid` component
- Features: pagination, sortable headers (click to toggle asc/desc), resizable columns, show/hide columns menu, hover row highlight, selected row highlight, last column reserved for action icons (16px), top filter bar + global search
- NEVER create ad-hoc tables — always use `CarbonDataGrid`

### Data Presentation
- **Balanced (C)**: Charts and tables equal weight. Sparklines in stat cards. Tables for precision, charts for trends.

### Page Width
- **Full fluid (A)**: `maxWidth: false` — content fills viewport. No max-width constraint.

### Animations
- **Subtle (B)**: Hover color shifts only. No page transitions. Max 200ms.

### Empty States
- **Illustrated (B)**: Icon (48px, `text.disabled`) + Title (h6) + Description (body2) + CTA Button
- NEVER show a blank page or just "No data"

### Forms — Unified Standard (see `src/components/Form/`)
- Single-column, labels ABOVE fields, `size="small"`, inline validation on blur
- Save bar pinned to bottom with Cancel + Save buttons
- NEVER create ad-hoc form layouts

### Loading
- Page load: `<Skeleton>` matching layout shape
- Button action: `<CircularProgress size={16} />` inside button
- NEVER show full-page spinner

### Errors
- Page-level: `<Alert severity="error">` at top, with retry button
- Field-level: `<FormHelperText error>` below field
- NEVER toast-only for errors

### Responsive
- Mobile: 1 column, stacked
- Tablet: 2 columns
- Desktop: full fluid, 3-4 columns max for card grids

### Never
- ❌ Hero sections, jumbotrons, gradient backgrounds
- ❌ Custom CSS files — use MUI `sx` prop or `styled()`
- ❌ Inline `style={{}}` — always use `sx`
- ❌ `console.log` in production code
- ❌ Pages > 400 lines — extract sub-components
- ❌ Toast-only errors
- ❌ Blank empty states
- ❌ Ad-hoc tables or forms — use shared components
- ❌ Shadows heavier than `boxShadow: 1`
- ❌ Custom fonts or Google Fonts
- ❌ Animations > 200ms

## API Conventions (BE Worker)

- **URL prefix**: All emissions endpoints under `/api/v1/emissions/`
- **Naming**: kebab-case in URLs, snake_case in Python, camelCase in JSON responses
- **Pagination**: `PageNumberPagination`, default 20, max 100
- **Filtering**: `django-filter` with `filterset_fields` on ViewSets
- **Permissions**: `IsAuthenticated` minimum; org-scoped via `get_queryset()` override
- **Serializers**: Separate read/list/detail serializers where field sets differ
- **Validation**: `validate_<field>()` methods, not custom `validate()`
- **Soft delete**: Use `is_deleted` boolean, never hard delete
- **Audit**: All state changes → GovernanceEvent (via `catalog.audit.audit_change`)
- **Errors**: `{"detail": "...", "code": "validation_error", "fields": {"field_name": ["error"]}}`

## MCP Tools Available to Master

Master uses these for review:
- `pylanceFileSyntaxErrors` — verify no syntax errors in worker output
- `pylanceLSP textDocument/diagnostic` — check Pylance type issues
- `run_in_terminal` — run pytest, npm build, curl tests

## Phase Sequence

| Phase | Page/Workflow | BE Task | FE Task | Depends On |
|---|---|---|---|---|
| 00 | Component Library Foundation | — | FE-00 | — |
| 01 | Carbon Console | BE-01 | FE-01 | Phase 00 |
| 02 | My Data (Entry + Sources) | BE-02 | FE-02 | Phase 01 |
| 03 | Emissions Dashboard | BE-03 | FE-03 | Phase 02 |
| 04 | Calculations & Verification | BE-04 | FE-04 | Phase 03 |
| 05 | Report Generator + Saved | BE-05 | FE-05 | Phase 04 |
| 06 | Admin (Factors, Rules, Periods) | BE-06 | FE-06 | Phase 01 |
| 07 | Targets & Goals | BE-07 | FE-07 | Phase 03 |
| 08 | Integration hardening, DQ wiring, RBAC | BE-08 | FE-08 | All |
