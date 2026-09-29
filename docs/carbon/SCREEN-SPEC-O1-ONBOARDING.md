# Screen Spec — Inventory onboarding (O1)

**ADR-0020 · ADR-0046 · frontend-ready 9 artifacts**  
**Route:** `/carbon/onboarding`  
**Owner:** carbon-inventory-lead  
**IA:** Carbon app → group Onboarding → “Inventory onboarding”  
**Locked:** 2026-09-29  
**Limit:** This page reads one GET. It does not submit a footprint.

---

## 1. Story

As the inventory lead on AASTMT Carbon, I open one reporting period and see
whether Smart Village electricity and diesel are declared, so that staff work
the leaf instead of quoting a tonne that is not in a tool payload.

Acceptance:

- The page title is Inventory onboarding (EN) / تهيئة المخزون (AR).
- Refresh is the only primary header button.
- The checklist text comes from `evaluate_o1` codes via i18n `onboarding.*`.
- Count 0 shows EmptyState. Count 2 lists each period by name, id, type, and dates.
- A `factor_value` or `target_coverage_pct` on the payload is not shown.
- Chat is not asked to write a period.

## 2. Journey

```
Carbon (activity) → Onboarding → Inventory onboarding
        │
        ▼
GET /carbon-api/carbon/onboarding/o1/
        │
        ├─ loading     LoadingSkeleton variant console
        ├─ error       Alert + common:retry
        ├─ count 0     EmptyState
        └─ otherwise   ul of Typography lines + eight WorkflowCards
                │
                ├─ Name the boundary     → /carbon/admin/boundaries
                ├─ Open one period       → /carbon/reporting/periods
                ├─ Declare the sources   → /carbon/admin/inventory-coverage
                ├─ Bind the factors      → /carbon/admin/factors
                ├─ Enter activity        → /carbon/my-data
                ├─ Run the calculation   → /carbon/calculations
                ├─ Cover or exclude      → /carbon/admin/inventory-coverage
                └─ Quote only the summary  (no path)
```

Process ids match `inventory.onboarding.lifecycle.yaml`:
`name_boundary`, `open_period`, `declare_sources`, `bind_factors`,
`enter_activity`, `calculate`, `cover_or_exclude`, `verify_quote`.

## 3. IA

| Surface | Value |
|---------|--------|
| App | carbon (`AppEnabledRoute`) |
| Group | Onboarding (`group.onboarding`) |
| Label | Inventory onboarding (`nav.inventoryOnboarding`) |
| Role | `*` — do not add `MENU_ITEM_CAPABILITIES` for this label |
| Breadcrumb parent | `/carbon/console` |
| Icon | `AssignmentTurnedInIcon` |

Nibras hides the carbon app. That redirect is expected.

## 4. Composition

```
PageContainer
 └─ PageHeader
 │    icon AssignmentTurnedInIcon
 │    title / subtitle / description from emissions:onboarding
 │    actions: one Button variant contained, size small → load()
 └─ LoadingSkeleton variant="console"          (phase loading)
 └─ Alert severity error + Button common:retry (phase error)
 └─ EmptyState                                 (count 0 only)
 └─ Alert severity warning + Button Open periods (count > 1 only; navigate, no POST)
 └─ Box component="ul" of Typography li        (checklist)
 └─ WorkflowCard grid                          (eight steps)
```

Primitives only. No hex. No MUI Table. No raw HTML table. No FilteredDataGrid
— this is a server checklist, not a record list. No POST dialog.

## 5. State matrix

| Phase | Condition | Render |
|-------|-----------|--------|
| loading | in-flight GET | Skeleton. No source names. |
| error | fetch throws | Alert with `err.message` or `onboarding.loadFailed`. Retry calls load. |
| empty | `open_period_id` null, one check `open_period_count`, count 0 | EmptyState. WorkflowCards still show after the empty block when phase is loaded. |
| two open | same code, `count` > 1, `periods.length` > 0 | Alert severity warning (not error). Copy `onboarding.tooManyOpen` / `tooManyOpenHint` (Lock, not Close; this page does not lock). Alert action is one Button that navigates to `/carbon/reporting/periods`. It does not POST. Then the count sentence and one `openPeriodNamed` line per period. Color `warning.main`. No kilogram. |
| one period | other codes | One line per check. `met` true → `success.main`, else `warning.main`. |
| forbidden | brand without carbon | Route redirect / API 403. Not an EmptyState on this page. |

## 6. Data contract

`GET /carbon-api/carbon/onboarding/o1/`  
Permissions: `IsAuthenticated`, `CarbonBrandPermission`.  
`writes: false`.

When count ≠ 1:

```json
{
  "benchmark": "O1",
  "benchmark_status": "open",
  "open_period_id": null,
  "writes": false,
  "checks": [
    {
      "id": "CR-PER-01",
      "code": "open_period_count",
      "met": false,
      "count": 2,
      "periods": [
        {"id": 15, "name": "FY 2023-24", "period_type": "annual",
         "start_date": "2023-07-01", "end_date": "2024-06-30", "status": "open"}
      ]
    }
  ]
}
```

`id` on a check is the rule id. A factor or goal row id is `record_id`.
Omit `factor_value` and `target_coverage_pct`.

Client: `fetchOnboardingO1` in `emissions-extended.js`,
config key `emissionsOnboardingO1`.

## 7. Accessibility

- Page title via `useDocumentTitle`.
- Header button is a real Button, not a div.
- Checklist is a list (`ul` / `li`).
- Alert has an action control.
- EmptyState has title and description.
- EN and AR strings exist for every COPY code.
- Color is not the only meaning: each line is a full sentence.

## 7a. Host periods screen (O1-USE-PERIODS)

Route `/carbon/reporting/periods`. Capability `carbon:manage_reporting_periods`.

When the loaded list has more than one row with `status` equal to `open`:

- Alert severity warning (not error).
- Copy flat keys `tooManyOpenPeriods` / `tooManyOpenPeriodsHint`.
- Name each open period. Do not invent a kilogram.
- The Alert does not POST, lock, or close.
- Close from Open stays 409 on the host. The next legal action is Lock
  (open → locked) on the existing admin-gated control (`canManageAllModules`).
- Do not add a close-from-open button. Do not rewrite the period table in this slice.

One open period: this Alert is absent.

## 8. Performance

One GET on mount and on Refresh. No interval. No calculation on the client.
Do not declare a millisecond SLO.

## 9. i18n / RTL

Namespace `emissions`, keys `onboarding.*`. Shell labels in `shell.json`.
Arabic lives in `ar/emissions.json`. `blankCountryLabel` uses `فارغ` when
`i18n.language` starts with `ar`. RTL is the shell’s job; this page adds
no `dir` override.
