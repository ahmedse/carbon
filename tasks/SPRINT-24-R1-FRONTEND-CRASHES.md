# Sprint 24 — R1: Frontend admin-console crash fixes (F-01, F-02, F-03)

**Owner:** Master Architect · **Worker Role:** frontend-worker · **Model:** DeepSeek V4-Flash
**Status:** 🚀 READY for dispatch
**Source:** `docs/TASK-RESULT-QA-AI-PULSE-SIMULATION.md` findings F-01, F-02, F-03
**Priority:** P1 — three of the five active P1s, all mechanical.

## Goal
Fix two frontend crash/data-blind defects in the AI admin console:
1. **F-01** — `/admin/ai/engine-settings` full-page crash (ChipList renders agent objects).
2. **F-02/F-03** — MUI X DataGrid v8.5 `valueFormatter` signature migration breaks
   `LearningFlywheelPanel` (crash on null cells) and `BudgetUsagePanel` (silent `'—'` on all
   numeric cells). One signature fix heals both panels.

## Root causes (verified — do NOT re-discover)

### F-01 — ChipList renders objects
`carbon-frontend/src/pages/admin/ai/EngineSettingsPanel.jsx:77-89`:
```jsx
function ChipList({ title, items }) {
  ...
  {items.map((item) => (
    <Chip key={item} size="small" variant="outlined" label={item} />
  ))}
```
Called at line 313: `<ChipList title="Agents" items={data.agents ?? []} />`.
`data.agents` is now an **array of objects** `{id, name, role, tool_set, is_active}`
(W1-A enriched `backend/ai/activation_api.py::_settings_agents()`). Rendering `label={item}`
throws `Objects are not valid as a React child`; `key={item}` yields duplicate `[object Object]` keys.

### F-02/F-03 — MUI X v8 positional valueFormatter
Installed `@mui/x-data-grid@8.5.0` calls `colDef.valueFormatter(value, row, colDef, apiRef)`
positionally (verified in `node_modules/@mui/x-data-grid/esm/hooks/features/rows/useGridParamsApi.js`).
The panels use v7-style destructure `({ value }) => …`:
- Non-null cell → destructuring a number/string returns `undefined` → `'—'` (F-03, silent).
- Null cell → `TypeError: Cannot destructure property 'value' of 'object null'` (F-02, crash).

14 occurrences, exactly 2 files:
- `carbon-frontend/src/pages/admin/ai/LearningFlywheelPanel.jsx:119,121,122,129,130,131,132,133`
- `carbon-frontend/src/pages/admin/ai/BudgetUsagePanel.jsx:86,87,88,96,97,98`

## Files to Change
- `carbon-frontend/src/pages/admin/ai/EngineSettingsPanel.jsx` — MODIFY `ChipList`.
- `carbon-frontend/src/pages/admin/ai/LearningFlywheelPanel.jsx` — MODIFY 8 `valueFormatter`s.
- `carbon-frontend/src/pages/admin/ai/BudgetUsagePanel.jsx` — MODIFY 6 `valueFormatter`s.
- `carbon-frontend/src/__tests__/EngineSettingsPanel.test.jsx` — ADD (if no test file exists, add `AdminConsoleCrashFixes.test.jsx`).

## Tasks

### 1. Fix ChipList (F-01)
In `EngineSettingsPanel.jsx`, make `ChipList` handle both string and object items:
```jsx
{items.map((item) => {
  const label = typeof item === 'string' ? item : item.name;
  const key = typeof item === 'string' ? item : item.id;
  const toolCount = typeof item === 'object' && Array.isArray(item.tool_set) ? item.tool_set.length : null;
  return (
    <Chip key={key} size="small" variant="outlined"
      label={toolCount != null ? `${label} (${toolCount})` : label} />
  );
})}
```
- `key` must be stable (use `item.id`), never `[object Object]`.
- Do NOT change `backend/ai/activation_api.py::_settings_agents()` — the object shape is correct
  and consumed by `AIAgentPanel` (W2-A).

### 2. Fix valueFormatter signature (F-02/F-03)
Replace every `valueFormatter: ({ value }) => …` with the v8 positional `(value) => …` in both
files. Examples:
- `({ value }) => value ?? '—'` → `(value) => value ?? '—'`
- `({ value }) => formatInt(value)` → `(value) => formatInt(value)`
- `({ value }) => formatUsd(value)` → `(value) => formatUsd(value)`
- `({ value }) => formatDate(value)` → `(value) => formatDate(value)`
- `({ value }) => value || '—'` → `(value) => value || '—'`

Do NOT add a `row`/`colDef` param unless a formatter needs it — none of these do.

### 3. Tests
- Assert `ChipList` renders `item.name` and stable `item.id` keys for object items (no
  `[object Object]`, no duplicate-key warning).
- Assert both grids render a real number (not `'—'`) for a non-null numeric cell, and that a
  null cell renders `'—'`/`0` without throwing.

## DO NOT TOUCH
- Backend files (`activation_api.py` agents shape is correct).
- `AIAgentPanel.jsx` / `AIActionRunner.jsx` (W2-A surface).
- Any other `valueFormatter` outside the 2 named files (verified there are none).

## Verification Gate
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint
npx vitest run src/__tests__/EngineSettingsPanel.test.jsx src/__tests__/AdminConsoleCrashFixes.test.jsx
npm run build
```
Then load `/admin/ai/engine-settings`, `/admin/ai/learning-flywheel`, `/admin/ai/budget-usage`
in the dev server and confirm: no ErrorBoundary crash, and numeric cells show real values
(not `'—'`).

## Hard rules
- Theme tokens only (RULE_8). MUI v6 Grid `<Grid size={{...}}>`. `apiFetch` only (RULE_10).

## Output contract
Append a `R1` section (Summary / Files Changed / Verification Output / Deviations) to
`TASK-RESULTS.md`.

## Notes for the Master
- Acceptance: engine-settings renders an Agents section (no crash), learning-flywheel renders
  a populated grid (no `Cannot destructure`), budget-usage numeric cells show real values.
