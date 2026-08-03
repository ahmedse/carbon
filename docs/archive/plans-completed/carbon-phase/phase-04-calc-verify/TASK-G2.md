# TASK-G2 — Phase 04 Frontend: Calculations & Verification UI

## Summary
Build the two main Phase 04 pages — Calculations Browser (with per-row traceability, DQ overlay, recalculate actions) and Verification Workflow (period review, approve/reject). Uses enriched Phase 04 backend endpoints from G1.

---

## Architecture

```
/carbon/calculations          → CalculationsPage (list/drill-down browser)
/carbon/verification          → VerificationPage (period review workflow)
```

Both pages use the project's `EntityDetailShell` three-column pattern:
- **Left/Main**: DataGrid or tabbed content
- **Right panel**: Entity metadata + actions (collapsible, resizable)
- **Header**: `PageHeader` with title + period selector

---

## D1 — CalculationsPage (`src/pages/carbon/CalculationsPage.jsx`)

**Route**: `/carbon/calculations`

**Purpose**: Browser for emission calculations with per-row traceability. Answers: "What was calculated, by which rule/factor, when, and what's the DQ status?"

### Layout
Three-column via `EntityDetailShell`:

**Main panel** — `DataGrid` table:
| Column | Source |
|--------|--------|
| ID | `id` |
| Module | `module_name` (from G1 enriched serializer) |
| Scope | `scope` (badge: 1=error.main / 2=warning.main / 3=info.main) |
| Category | `category` |
| CO2e (t) | `co2e_kg / 1000` (1 decimal) |
| Factor | `emission_factor__name` |
| Data Row | `data_row_id` (linked) |
| Date | `activity_date` or `calculated_at` (compact format) |

**Filters bar** above grid:
- `reporting_period_id` — dropdown (fetch from `/emissions/periods/`)
- `module_id` — dropdown (from context.modules, scope-filtered)
- `scope` — select 1/2/3
- `category` — text input or select
- `?detail=true` toggle → full serialized objects with traceability

**Row click** → highlight row, show right panel with:

**Right panel tabs**:
- **Traceability** — factor name, factor code, factor value, activity_value, formula (value × factor = co2e), data_table name, data_row link
- **Audit** — last CalculationAudit entries for this period/rule (fetch from `/calculation-audits/?period_id=N`)
- **DQ** — quality_score from catalog AssetProfile if available (fetch from `/catalog/assets/?data_table=N`)

**Actions** in header:
- **Recalculate** button → POST `/batch-calculate/` for selected period
- **Calculate Single Rule** dropdown → select rule → POST `/calculate/`
- Refresh icon

### API calls
```js
// From emissions-extended.js (add these functions):
fetchCalculations({ period_id, module_id, scope, category, detail })
fetchCalculationSummary(period_id)
// From existing:
fetchCalculationAudits({ period_id, trigger_type })
fetchCalculationRules()  // for rule dropdown
```

### State
- `selectedPeriod` (initial: active period from fetchActiveReportingPeriod)
- `selectedRow` (for right panel)
- `calculations[]`
- `summary{}` from D3 summary endpoint
- Loading/error states

---

## D2 — VerificationPage (`src/pages/carbon/VerificationPage.jsx`)

**Route**: `/carbon/verification`

**Purpose**: Verification workflow dashboard. Answers: "Which periods need review? Can I approve or reject them?"

### Layout

**Main panel** — tabbed:

**Tab 1: Pending Review** — DataGrid of periods with `status='submitted'`:
| Column | Source |
|--------|--------|
| Period | `name` |
| Dates | `start_date` – `end_date` |
| Type | `period_type` (annual/quarterly/monthly) |
| Submitted | `submitted_at` |
| Org Unit | org_unit name if applicable |
| Emissions (tCO2e) | aggregated from calculations |
| Actions | Approve / Reject buttons |

**Tab 2: Verified** — DataGrid of periods with `status='verified'`:
| Column | Source |
|--------|--------|
| Period | `name` |
| Verified By | from VerificationRecord `verifier_name` |
| Verified At | `verified_at` |
| Verification Notes | `notes` |

**Tab 3: All Periods** — full period list with status badges (draft/submitted/verified/rejected/reopened)

**Reject dialog** — opens on reject click:
- Text field for notes (required)
- Confirm/Cancel

**Approve** — direct action with confirmation:
- POST `/periods/{id}/verify/`
- On success: move from "Pending Review" to "Verified" tab

**Right panel** (when period selected):
- **Overview** — period name + dates + status badge + emission totals
- **Verification History** — list of VerificationRecords for this period (who, when, action, notes)

### API calls
```js
// From emissions-extended.js:
fetchReportingPeriods()          // existing
fetchVerificationRecords({ period_id })  // existing (D4 enriches)
// Period actions (existing endpoints):
submitPeriod(id)                 // POST /periods/{id}/submit/
verifyPeriod(id)                 // POST /periods/{id}/verify/
rejectPeriod(id, { notes })      // POST /periods/{id}/reject/
// Summary:
fetchCalculationSummary(period_id)  // from D3
```

### State
- `periods[]`
- `pendingPeriods[]` (filtered: status='submitted')
- `verifiedPeriods[]` (filtered: status='verified')
- `selectedPeriod` (for right panel)
- `verificationRecords[]`
- `rejectDialog { open, period }`

---

## D3 — API Client Functions (enhance `src/api/emissions-extended.js`)

Add these functions:
```js
fetchCalculations({ period_id, module_id, scope, category, detail } = {}, token)
fetchCalculationSummary(period_id, token)
fetchVerificationRecords({ period_id } = {}, token)
verifyPeriod(periodId, token)
rejectPeriod(periodId, notes, token)
submitPeriod(periodId, token)
fetchCalculationRules(token)  // if not already present
```

All use existing `apiFetch()` from `src/api/api.js`.

---

## D4 — Routes + Navigation (App.jsx + Sidebar)

### Route registration in `App.jsx`:
```jsx
<Route path="/carbon/calculations" element={<CalculationsPage />} />
<Route path="/carbon/verification" element={<VerificationPage />} />
```

### Sidebar entries (add to Carbon section):
```jsx
{ label: 'Calculations', path: '/carbon/calculations', icon: <CalculateIcon /> },
{ label: 'Verification', path: '/carbon/verification', icon: <VerifiedIcon /> },
```

Check `apps/carbon/manifest.js` for existing nav configuration — may need to add there instead.

### config.js `API_ROUTES` — verify these keys exist:
```js
calculations: `${emissionsPrefix}calculations/`,
calculationSummary: `${emissionsPrefix}calculations/summary/`,
verifications: `${emissionsPrefix}verifications/`,
rules: `${emissionsPrefix}rules/`,
batchCalculate: `${emissionsPrefix}batch-calculate/`,
calculate: `${emissionsPrefix}calculate/`,
```

---

## Files to Create/Change

| File | Action |
|------|--------|
| `src/pages/carbon/CalculationsPage.jsx` | **NEW** — D1 |
| `src/pages/carbon/VerificationPage.jsx` | **NEW** — D2 |
| `src/api/emissions-extended.js` | **ENHANCE** — D3: add ~7 functions |
| `src/App.jsx` | **ENHANCE** — D4: add 2 routes |
| `src/config.js` | **VERIFY** — D4: ensure API_ROUTES exist |
| `src/apps/carbon/manifest.js` | **ENHANCE** — D4: add nav entries |

---

## DO-NOT-TOUCH

- ❌ No backend files
- ❌ No auth changes (AuthContext, login, token management)
- ❌ No theme changes (carbonTheme.js)
- ❌ No existing pages (CarbonConsolePage, MyDataPage, etc.)
- ❌ No layout shell components (Sidebar.jsx, Layout.jsx, HeaderEnhanced.jsx)
- ❌ No package.json dependency changes
- ❌ No api.js changes (the apiFetch helper)
- ❌ No imports from `entity/EntityDetailShell` — copy its pattern inline if needed, but do not modify EntityDetailShell itself

---

## Verification

```bash
# 1. Build must pass
cd carbon-frontend && npm run build

# 2. No new antipatterns
cd .. && bash .ai-toolkit/scripts/verify.sh antipatterns

# 3. Browser checklist (backend must be running: ./manage.sh start):
#    - /carbon/calculations loads and shows calculation grid
#    - Filter by period/module/scope works
#    - Row click shows right panel with traceability
#    - /carbon/verification loads and shows periods by status
#    - Approve/reject dialogs work (test with ahmed/AdminPa_132)
#    - Sidebar has Calculations + Verification entries
```

## Success Criteria

- [ ] `npm run build` — no errors
- [ ] `verify.sh antipatterns` — no new violations
- [ ] `/carbon/calculations` — calculation grid renders with data
- [ ] `/carbon/calculations` — period selector filters results
- [ ] `/carbon/calculations` — row click shows traceability panel (factor name, formula)
- [ ] `/carbon/calculations` — DQ tab shows quality status from catalog
- [ ] `/carbon/verification` — pending reviews tab shows submitted periods
- [ ] `/carbon/verification` — approve action moves period to verified
- [ ] `/carbon/verification` — reject opens dialog, requires notes
- [ ] Sidebar navigation to both pages works
- [ ] No files outside the listed files changed
