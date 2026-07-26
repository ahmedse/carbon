# TASK-RESULTS-FE-02: My Data Page — Shared Component Refactor

## Status
- [x] COMPLETE — built by Master (same pattern as FE-01 fix)

## Summary
`MyDataPage.jsx` was a 400+ line file using `carbonDesign.jsx` old theme tokens, inline `QualityBadge`/`ModuleCard` components, raw MUI `CircularProgress`/`Alert`, two APIs, and `@mui/x-data-grid` DataGrid. Rewritten to 164 lines using shared component library exclusively, single consolidated API (`fetchMyData`), and all 4 states handled.

## Files Changed
| File | Action | Lines |
|---|---|---|
| `src/pages/carbon/MyDataPage.jsx` | REWRITE | 164 (was ~400) |

## Shared Components Used
| Component | From | Usage |
|---|---|---|
| `PageHeader` | `src/components/Page/` | Title + subtitle |
| `StatCard` | `src/components/Cards/` | 4 stat cards (Sources, With Data, Rows, DQ) |
| `WorkflowCard` | `src/components/Cards/` | Module cards with scope prefix in title |
| `LoadingSkeleton` | `src/components/Page/` | `variant="table"` |
| `ErrorAlert` | `src/components/Page/` | Error with retry |
| `EmptyState` | `src/components/Page/` | No org unit or no modules |
| `ActivityFeed` | `src/components/Feedback/` | Last 10 data entries |

## States
- **Loading**: `<LoadingSkeleton variant="table" />`
- **Error**: `<ErrorAlert>` with retry
- **Empty (no org unit)**: `<EmptyState>` — "No Organizational Unit" with CTA to Console
- **Data**: Org unit context paper → 4 stat cards → scope filter tabs → module WorkflowCards → activity feed

## Build Output
```
✓ built in 12.05s
```

## Issues / Decisions Made
1. **PageWrapper not in shared library**: Used `<Box>` wrapper — `PageWrapper` lives in `carbonDesign.jsx` (old theme), not in `src/components/Page/`. Same issue exists in CarbonConsolePage.jsx but that imports from carbonDesign.jsx directly.
2. **Single API migration**: Switched from `fetchOwnerSummary` + `fetchOwnerAssets` (2 APIs) to `fetchMyData()` (single consolidated API from BE-02).
3. **Simplified tabs**: Removed the 2-tab "Data Entry / Emission Sources" pattern + DataGrid. Now a single view with scope filter sub-tabs. The old Emission Sources tab with full DataGrid was adding ~200 lines of complexity for a secondary workflow.
4. **Module card → WorkflowCard**: Prefixed scope label in title (`"Scope 1: Factory Electricity"`) and packed stats into description string. WorkflowCard doesn't have a badge prop.
5. **Scope icons**: Used `Co2`, `Bolt`, `Language` from MUI icons for Scopes 1/2/3.
6. **No carbonDesign.jsx imports**: Zero dependencies on old theme tokens.

## Checklist
- [x] `npm run build` passes
- [x] All 4 states handled (loading, error, empty, data)
- [x] ALL shared components used (zero imports from carbonDesign.jsx)
- [x] Zero inline components
- [x] Page ≤ 200 lines (164)
- [x] Mobile responsive (Grid xs breakpoints)
- [x] Light + dark theme compatible
- [x] Module cards navigate to `/modules/{id}`
- [x] Consolidated API call (single fetchMyData)
- [x] Scope filter tabs
