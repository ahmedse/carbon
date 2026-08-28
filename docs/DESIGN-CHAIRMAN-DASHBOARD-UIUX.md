# Chairman Dashboard — Detailed Plan & UI/UX Design

> Master Architect. Companion to `DESIGN-CHAIRMAN-DASHBOARD.md`. This is the
> **implementation plan (file-by-file)** and the **pixel-level UI/UX spec**.
> Every figure traces to existing services (`DashboardService`,
> `InventoryCoverageService`, `YearlyComparisonService`, `TargetService`,
> `ReportService`) — no fabricated data, no new persistence.

---

## Part 1 — Information Architecture (the "don't overwhelm" spine)

```
Chairman (1 screen)  →  Analyst (drill)  →  Auditor (lineage)
        │                     │                    │
  6 KPI cards         coverage matrix        calculation detail
  3 narrative panels   DQ heatmap            emission-factor snapshot
  "still to do" rail   SBTi progress         export audit
        │                     │                    │
        └───────────── Measure ─── Report ─── Act ─┘
```

The three verbs (Watershed pattern) map to **tabs**, not to new concepts:

| Tab | Verb | Audience | Existing surface |
|-----|------|----------|------------------|
| **Overview** | Measure | Chairman | NEW `ChairmanDashboard.jsx` |
| **Analytics & Trends** | Report | Analyst | `AnalyticsDashboard.jsx` (exists) |
| **Coverage & Actions** | Act | Ops lead | `InventoryCoveragePage.jsx` (exists) |

---

## Part 2 — Implementation Plan (file-by-file)

### Phase A — Chairman screen (ship tomorrow)

**A1. Backend service** — `backend/emissions/services.py`
Add `ChairmanService.get_chairman_data(user, period_id=None)` that composes
existing services into ONE payload (single round-trip, mirrors `ConsoleService`):

```
{
  "as_of": timezone.now(),                        # CB-04 aware
  "period": { name, start, end, status, days_remaining },
  "headline_kpis": [
    { key:"footprint",  value:9589,   unit:"t CO₂e", hint:"measured to date" },
    { key:"coverage",   value:7,      total:35,   pct:20.0, unit:"sources" },
    { key:"sbti",       value:3,      status:"draft" },
    { key:"quality",    value:2.0,    label:"PCAF avg tier", score:62 },
    { key:"actions",    value:7,      open:5, in_progress:2 },
  ],
  "scope_breakdown": [...],                       # from DashboardService
  "coverage": { total, covered, pct, per_campus[], per_scope[] },  # from InventoryCoverageService + group-by
  "trajectory": { actuals:[], targets:[], gap[] },  # from YearlyComparisonService._build_sbti_trajectory
  "actions": [ {id, source, type, status, due_date, owner} ],   # CoverageAction
}
```

- `per_campus[]` / `per_scope[]` need **two small aggregations** on
  `InventorySourceStatus` joined to `InventorySource.org_unit` / `.scope`
  (the exact SQL the audit shell already ran — port it into a service method).
- `trajectory` reuses `YearlyComparisonService.get_comparison(user, years)` and
  only needs the **actuals joined to target glidepath** for the period.

**A2. Backend view** — `backend/emissions/views.py`
`ChairmanAPIView(APIView)` → `permission_classes = [IsAuthenticated]`,
`ChairmanService.get_chairman_data`. Register in `backend/emissions/urls.py`:
`path('chairman/', ChairmanAPIView.as_view(), name='chairman')`.

**A3. Frontend API** — `carbon-frontend/src/api/emissions-extended.js`
`fetchChairmanData(token, periodId)` → `apiFetch(\`${API_ROUTES.emissionsAPI}chairman/\`, {token})`.

**A4. Route config** — `carbon-frontend/src/config.js`
`emissionsChairman: "carbon/chairman/"`.

**A5. New page** — `carbon-frontend/src/pages/carbon/ChairmanDashboard.jsx`
(see Part 3 wireframes). Registered as the **first tab** in `CarbonDashboardPage.jsx`.

### Phase B — Coverage matrix + DQ heatmap (analyst drill)

- Extend `ChairmanService` (or a new `CoverageMatrixService`) to return
  `coverage_matrix[]` = `[ {campus, scope1:{c,t}, scope2:{c,t}, scope3:{c,t}} ]`.
- `InventoryCoveragePage.jsx`: add a **Matrix tab** rendering the table in §4.1
  of the design doc, and a **Heatmap tab** rendering PCAF tier × campus.
- No backend changes for DQ heatmap — `InventorySourceStatus.data_quality_tier`
  is already exposed by `InventorySourceStatusViewSet`.

### Phase C — Official report upgrade

- `ReportService.generate_report`: add `coverage_statement` (from
  `InventoryCoverageService`) and `sbti_progress` (from `TargetService.get_progress`
  per target) to the return payload.
- `ReportAPIView`: pass period/org scope through.
- New **"Board pack"** print route: `ChairmanDashboard.jsx` gets a print-optimized
  mode (`@media print` + "Save as PDF") — zero backend dependency.

### Phase D — Polish & assurance

- Theme-token audit (no raw hex — reuse `chartPalette` / `SCOPE_META`).
- Empty/zero/loading/error states (per anti-flaw checklist §9 of design doc).
- `ChairmanService` must call `scope_calculations`/`get_visible_module_ids`
  so org-scope is respected.

---

## Part 3 — UI/UX Designs (wireframes)

### 3.1 Screen 1 — Chairman Overview (the single screen)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Carbon Data Trust · Chairman Overview                       FY25–26 · open ●  │
│                                                    [ Export board pack ▾ ]    │
├──────────────────────────────────────────────────────────────────────────────┤
│ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐   │
│ │ 9,589      │ │  7 / 35    │ │    3       │ │   T2 · 62  │ │    7       │   │
│ │ t CO₂e     │ │  20%       │ │ SBTi       │ │ quality    │ │  actions   │   │
│ │ MEASURED   │ │ COVERAGE   │ │ DRAFT      │ │ PCAF avg   │ │  TO DO     │   │
│ │  ▁▃▅▇ trend │ │ ▓▓▓░░░░░░ │ │  (policy)  │ │  ██▒░░░    │ │  5 open    │   │
│ └────────────┘ └────────────┘ └────────────┘ └────────────┘ └────────────┘   │
├───────────────────────────────────────────────┬──────────────────────────────┤
│  SCOPE BREAKDOWN            COVERAGE GAP      │  SBTi TRAJECTORY             │
│  ┌──────────────┐         7 of 35 measured    │  ┌────────────────────────┐  │
│  │  (donut)     │         ┌──────────────┐    │  │   dashed = target      │  │
│  │  S1 2,000    │         │ Abu Qir  ▓▓▓▓│80% │  │   solid  = actual      │  │
│  │  S2 6,800    │         │ SmartVlg ▓▓░░│18% │  │   shaded = gap         │  │
│  │  S3   789    │         │ Aswan    ░░░░│ 0% │  │                        │  │
│  └──────────────┘         └──────────────┘    │  └────────────────────────┘  │
│                                              │  STILL TO DO                │
│  "20% is the plan, not a failing grade —  │  ┌────────────────────────┐  │
│   Abu Qir is nearly done, Aswan is next."  │  │ ● Collect data (Aswan) │  │
│                                            │  │ ◐ Improve quality ...  │  │
│                                            │  │ ○ Obtain verification  │  │
│                                            │  └────────────────────────┘  │
├───────────────────────────────────────────────┴──────────────────────────────┤
│  As of 28 Aug 2026 14:02 UTC · every number clickable to source calculation  │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Design decisions (the "why"):**
1. **Six cards, one number each** — no decimal grids. The eye reads left→right in
   <2s: *footprint → coverage → targets → quality → to-do*.
2. **Coverage framed as `7 / 35`**, never a bare `20%`. The progress bar under it
   is the *plan* (28 declared sources still to measure), not a grade.
3. **The coverage gap panel** is the honest story: per-campus bars make the
   "where's next" obvious (Aswan 0% = the next win).
4. **SBTi trajectory** always pairs dashed **target** vs solid **actual** with a
   shaded **gap** — the insight is the gap, not the number (P5).
5. **"Still to do" rail** is a checklist with status glyphs (● open, ◐ in-progress,
   ○ done) — the chairman leaves knowing *exactly* what's next.

### 3.2 Screen 2 — Analytics & Trends (existing, +1 enhancement)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Analytics & Trends              [YTD ▾] [Baseline 2020]  [Export ▾]         │
├──────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────┐ ┌─────────────────────────────┐              │
│ │ Year-over-year (bar)        │ │ SBTi glidepath (line)       │              │
│ │ 2020 ▓ 2024 ▓ 2025 ▓ 2026 ▓ │ │  ── target   ── actual     │              │
│ │ baseline line ────────      │ │  gap callout: "+1,200 t"    │              │
│ └─────────────────────────────┘ └─────────────────────────────┘              │
│ ┌─────────────────────────────┐ ┌─────────────────────────────┐              │
│ │ Category top-10 (h-bar)     │ │ Monthly trend (stacked)     │              │
│ └─────────────────────────────┘ └─────────────────────────────┘              │
└──────────────────────────────────────────────────────────────────────────────┘
```
Enhancement: add a **baseline reference line** to the YoY bar (from
`baseline_year`), and a **gap callout** chip on the trajectory.

### 3.3 Screen 3 — Coverage & Actions (existing, +2 tabs)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Inventory Coverage     [Sources] [Matrix] [Heatmap] [Actions]               │
├──────────────────────────────────────────────────────────────────────────────┤
│ MATRIX tab:                                                                   │
│ ┌──────────────┬─────────┬─────────┬─────────┬────────┐                       │
│ │ Campus       │ Scope 1 │ Scope 2 │ Scope 3 │ Total  │                       │
│ ├──────────────┼─────────┼─────────┼─────────┼────────┤                       │
│ │ Abu Qir      │ 2/3 67% │ 1/1 100%│ 1/1 100%│ 4/5 80%│   ← tinted cells     │
│ │ Smart Village│ 1/6 17% │ 2/2 100%│ 0/6   0%│ 3/14 18%│                       │
│ │ Aswan        │ 0/1   0%│ 0/0   — │ 0/12  0%│ 0/13  0%│                       │
│ └──────────────┴─────────┴─────────┴─────────┴────────┘                       │
│ HEATMAP tab: cells = PCAF tier (T1 green … T5 red) × campus                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 4 — Design Token Map (enforce "no raw hex")

| Element | Token / source |
|---------|----------------|
| Scope 1/2/3 colors | `theme.palette.success / primary.light / warning.main` (already in `EmissionsDashboard`) |
| Chart series | `chartPalette` from `theme/carbonTheme` |
| Scope icons | `SCOPE_META` from `themeTokens.js` |
| Typography | `FONT.statValue / statLabel / chip / caption` |
| Spacing | `SPACING.md / lg` |
| Status colors | `QUALITY_CONFIG` (passing/warning/failing) + `StatusChip` in coverage page |
| DQ tier chips | `TierChip` (T1…T5) already defined in `InventoryCoveragePage.jsx` |

**Reuse existing components** to avoid duplication: `StatCard`, `GlassCard`,
`ScopeCard`, `ScopeChip`, `TierChip`, `StatusChip`, `CoverageBar` are all already
written and theme-compliant — the chairman screen composes them, it does not
reinvent them.

---

## Part 5 — Acceptance Criteria (definition of done)

- [ ] Chairman screen renders 6 KPI cards + 3 narrative panels + action rail in ONE viewport (no scroll at 1440×900).
- [ ] Every KPI card deep-links to its drill surface.
- [ ] Coverage numbers sourced ONLY from `InventoryCoverageService` (no frontend re-derivation).
- [ ] SBTi trajectory shows **draft** badge; no legal-commitment framing.
- [ ] All percentages guard `denominator > 0`; empty states render "no data yet".
- [ ] `as_of` timestamp timezone-aware; respects `scope_calculations` visibility.
- [ ] Zero raw hex; all colors via theme tokens / `chartPalette`.
- [ ] Fetch via `apiFetch` wrapper (JWT refresh), not raw `fetch`.
- [ ] `get_errors` clean on all touched files; `manage.py check` clean.
