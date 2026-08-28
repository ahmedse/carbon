# Chairman-Grade Dashboard, Analytics & Official Reports — Design

> Master Architect deliverable. Grounded in the Carbon Data Trust Platform **actuals**
> (9,589 tCO2e measured, 35-source declared universe at 20% coverage, 3 SBTi targets
> in draft, 2 coverage goals, 7 coverage actions) and in the research on top
> enterprise carbon systems (Watershed, Persefoni, Salesforce Net Zero Cloud,
> Microsoft Sustainability Manager, Sphera, Workiva) plus the GHG Protocol
> Corporate Standard / Scope 2 / Scope 3 Standards.

---

## 1. The Story (what the chairman sees in 30 seconds)

One sentence: **"We have begun measuring our footprint with real, auditable data —
and we know exactly what remains to be measured."**

The dashboard must tell a **three-beat narrative**, not dump data:

1. **We know our number** → `9,589 tCO2e` measured, scope-by-scope, campus-by-campus.
2. **We know our coverage** → `35 sources declared, 7 measured (20%)` — this is the
   *honest completeness* story, framed as a **plan**, not a failure.
3. **We know where we're going and what's left** → 3 SBTi targets (draft, pending
   board ratification) + 7 concrete coverage actions ("still to do").

Framing rule (critical): the 20% coverage figure is presented as **"7 of 35
accountable sources now measured"** with a **forward-looking gap list** — never as
a bare 20% score that reads as a poor grade.

---

## 2. Design Principles (from enterprise research)

| # | Principle | Enterprise source | What it means here |
|---|-----------|-------------------|--------------------|
| P1 | **3-tier information hierarchy** | Watershed / MSM | Chairman (1 screen) → Analyst (drill) → Auditor (lineage) |
| P2 | **Measure → Report → Act** | Watershed | The whole app is organized as these 3 verbs |
| P3 | **Full lineage & audit trail** | Watershed, Persefoni | Every number clickable → factor → source → calculation |
| P4 | **Data-quality tiering is first-class** | Verdantix #1 criterion | PCAF 1–5 / IPCC 1–3 surfaced as a DQ score, not buried |
| P5 | **Target progress vs glidepath** | All leaders | Actuals plotted *against* the SBTi linear trajectory, with "gap" |
| P6 | **Declared universe → measured → excluded** | GHG Protocol / ADR-0020 | Coverage is completeness vs an *explicit* universe, never fuzzy |
| P7 | **Progressive disclosure** | All leaders | Chairman sees 6 KPI cards + 1 chart; analysts click in |
| P8 | **No raw hex, theme tokens only** | platform rule | `chartPalette` + `FONT` from `themeTokens.js` |

---

## 3. The Chairman's Single Screen (Tier 1)

Layout: one viewport, **6 headline KPI cards** in a row, then **3 charts** and a
**"still to do" list**. No scroll required on a laptop.

### 3.1 Headline KPI cards (row of 6)

| Card | Value (live) | Source |
|------|--------------|--------|
| **Total footprint** | `9,589 tCO2e` | `DashboardService.get_dashboard_data` → `total_co2e_tonnes` |
| **Inventory coverage** | `7 / 35 · 20%` | `InventoryCoverageService.compute_coverage` → `covered`/`total` |
| **SBTi targets** | `3` (draft) | `SBTiTarget` count + status badge |
| **Data quality** | PCAF tier avg + IPCC score | `compute_coverage.avg_quality_tier` + `DashboardService.data_quality_score` |
| **Open actions** | `7` | `CoverageAction` status `open`/`in_progress` |
| **Reporting period** | `FY25–26 · open` | `ConsoleService.get_console_data.active_period` |

Each card is **clickable** → jumps to its Tier-2 surface (P7, P3).

### 3.2 Narrative row (3 charts + action list)

1. **Scope donut** — Scope 1/2/3 share of the 9,589 tCO2e (react-chartjs-2 Doughnut,
   `chartPalette`). Sub-label per scope = tCO2e + %.
2. **Coverage funnel / donut** — `7 measured · 28 declared` per the declared universe,
   broken by campus (Abu Qir 80%, Smart Village 17.6%, Aswan 0%). This is the
   *single most important* chart — it is the completeness story.
3. **SBTi trajectory** — actual `9,589` plotted against the linear glidepath toward
   each target's `reduction_pct` (line chart). Dashed target line, solid actual,
   shaded "gap".
4. **Still to do** (right rail) — the 7 coverage actions as a compact checklist with
   status chips (open / in_progress / done / blocked) and due dates.

### 3.3 Anti-overwhelm mechanics

- **One number per card**, no grids of decimals.
- **Status color = meaning**: green = measured/verified, amber = declared/planned,
  zinc = excluded/not-assessed. (No rainbow.)
- **"As of" timestamp** top-right (from `last_updated`), so the chairman trusts recency.
- **"Export / report" button** top-left → official report (Section 6).

---

## 4. Tier 2 — Analyst Drill-Down (click any KPI)

Each KPI card deep-links to an existing surface (minimizing new build):

| KPI | Existing surface | Needs |
|-----|------------------|-------|
| Total footprint | `AnalyticsDashboard.jsx` (date-range, YoY, scope/category) | add campus filter |
| Inventory coverage | `InventoryCoveragePage.jsx` | add period selector + per-scope × per-campus matrix |
| SBTi targets | `SBTiTargetsPage.jsx` | add `progress` sparkline (endpoint exists: `targets/<id>/progress/`) |
| Data quality | new **DQ matrix** | PCAF tier × campus heatmap |
| Open actions | `CoverageAction` list | status filter + assignee |
| Reporting period | `ReportingPeriodsPage.jsx` | state machine is already modeled (`transition_to`) |

### 4.1 The coverage × campus × scope matrix (new, high-value)

A single table: **rows = 3 campuses, columns = Scope 1/2/3**, cells = `measured/total
sources` with a coverage % tint. This one table *is* the completeness story for
analysts and is the natural bridge to the chairman's funnel. Data exists in
`InventorySource` + `InventorySourceStatus`; needs one aggregation query (see §7).

### 4.2 Data-quality heatmap

Grid of **campus × source** colored by PCAF tier (1 = best, 5 = worst). Directly
maps `InventorySourceStatus.data_quality_tier`. Surfaces the "some data is better
than others" nuance the chairman doesn't need but auditors do.

---

## 5. Analytics Layer (Tier 2, "Report")

Maps to existing `YearlyComparisonService` + `AnalyticsDashboard`:

- **Year-over-year** — `get_comparison(user, years)` → `yearly_comparison[]` with
  `reduction_from_baseline` + `yoy_change`. Add a **baseline reference line**.
- **SBTi trajectory** — `_build_sbti_trajectory` already linear-interpolates from
  committed/approved targets. **Gap callout**: `actual − target` per year, green if
  below, red if above.
- **Category breakdown** — `_build_category_breakdown` (top 10 categories).
- **Monthly trend** — `_build_monthly_trend` (12-month stacked bar, scope-stacked).
- **By-gas** — `ReportService._build_by_gas` (CO2/CH4/N2O stacked).

**Analytics principle:** every chart pairs an **actual** with a **target/reference**
line — the "gap" is the insight, not the raw value (P5).

---

## 6. Official Reports (Tier 3, "Act" + disclosure)

Built on `ReportService.generate_report` (JSON/CSV/XLSX already implemented, writes
`ExportAudit`). Add a thin **"official report"** wrapper that composes:

1. **Executive Summary** (Tier-1 headline KPIs, auto-filled).
2. **Scope 1/2/3 detail** — `scope_details` (already).
3. **By-gas** — `by_gas` (already, E3-1).
4. **Org-unit rollup** — `org_unit_rollup` (already).
5. **Coverage statement** — declared/measured/excluded + completeness definition
   (from `InventoryCoverageService`, **add to the report payload**).
6. **SBTi progress** — targets + actual vs glidepath (add from `TargetService`).
7. **Verification status** — `VerificationRecord` for the period.

Formats: **XLSX** (auditor/regulator), **PDF** (chairman/board — the highest-value
addition; xlsxwriter exists but PDF needs `reportlab` or browser print-to-PDF), and
**JSON** (machine). A **"board pack"** mode generates the chairman's 1-pager.

> PDF is the single biggest reporting gap. Two options: (a) server-side `reportlab`,
> (b) a print-optimized React route → browser "Save as PDF". Recommend (b) first —
> zero new backend dependency, theme-consistent, and the chairman prints from the
> live dashboard.

---

## 7. Gap Analysis (what's already built vs what to build)

| Capability | Status | Effort |
|-----------|--------|--------|
| Dashboard scope/category/monthly + DQ score | ✅ built (`DashboardService`) | — |
| Yearly comparison + SBTi trajectory | ✅ built (`YearlyComparisonService`) | — |
| JSON/CSV/XLSX report + export audit | ✅ built (`ReportService`) | — |
| Coverage computation (declared/covered/excluded) | ✅ built (`InventoryCoverageService`) | — |
| SBTi target progress endpoint | ✅ built (`TargetService.get_progress`) | — |
| **Chairman single-screen (6 KPI + narrative)** | ❌ needs build | 1 endpoint + 1 page |
| **Coverage × campus × scope matrix** | ❌ needs one aggregation query | small |
| **DQ heatmap (PCAF tier × campus)** | ❌ new | small |
| **Coverage statement in official report** | ❌ add to report payload | small |
| **SBTi progress in official report** | ❌ add to report payload | small |
| **PDF "board pack"** | ❌ new | medium (print-to-PDF path) |
| **"Still to do" action rail** | ❌ new (data exists) | small |

**New backend work is small** — one **"ExecutiveSummaryService"** (or extend
`ConsoleService`) that returns the chairman payload in a single call, mirroring how
`ConsoleService` already aggregates everything for the landing page.

---

## 8. Proposed Implementation Plan (phased)

### Phase A — One endpoint, one screen (chairman-visible tomorrow)
1. Add `ExecutiveSummaryService.get_chairman_data(user, period_id)` returning:
   `headline_kpis[]`, `scope_breakdown`, `coverage` (from `InventoryCoverageService`),
   `sbti_trajectory`, `actions[]`, `last_updated`.
2. New `GET /emissions/chairman/` view (thin, fat service — RULE_7).
3. New `ChairmanDashboard.jsx` (Tier-1 screen), wired as the **default tab** of
   `CarbonDashboardPage` (or a "Board view" toggle).

### Phase B — Coverage matrix + DQ heatmap (analyst drill-down)
4. Extend coverage aggregation → `coverage_matrix[]` (campus × scope).
5. Add PCAF-tier heatmap to `InventoryCoveragePage`.

### Phase C — Official report upgrade
6. Add `coverage_statement` + `sbti_progress` to `ReportService.generate_report`.
7. Print-optimized "board pack" route → PDF (browser print).

### Phase D — Polish & assurance
8. Theme-token audit (no raw hex), accessibility pass, empty/zero-state handling,
   loading skeletons, error boundaries.

---

## 9. Anti-Flaw Checklist (the "avoid flaws" requirement)

- [ ] **No fabricated numbers** — every figure traces to `Calculation` / `InventorySource` /
      `SBTiTarget`. The 9,589 tCO2e is the live `SUM(co2e_kg)`.
- [ ] **Coverage denominator is explicit** — `total − exclusions` only when
      `completeness_definition == 'materiality_bounded'` (already handled by
      `InventoryCoverageService`).
- [ ] **SBTi targets marked DRAFT** — the UI must show "draft, pending board
      ratification"; trajectory is *illustrative*, not a committed claim.
- [ ] **Egypt NDC context** — no net-zero target in the NDC (42% RE by 2030); the
      dashboard reports *SBTi-aligned* ambition, not a legal commitment.
- [ ] **Timezone-aware datetimes** (CB-04) — `last_updated` uses `timezone.now()`.
- [ ] **Scope visibility respected** — all services already call `scope_calculations`/
      `get_visible_module_ids`; the chairman endpoint must too.
- [ ] **No raw `fetch`** — use the `apiFetch` wrapper (JWT refresh).
- [ ] **Theme tokens only** — `chartPalette`, no inline hex.
- [ ] **Division-by-zero** — every percentage guards `denominator > 0` (coverage,
      reduction, yoy all already do).
- [ ] **Empty states** — 0 sources / 0 calculations must render "no data yet", never
      NaN or a broken chart.
- [ ] **Single source of truth** — coverage numbers come ONLY from
      `InventoryCoverageService`; do not re-derive in the frontend.

---

## 10. Data provenance map (number → source → code)

| Chairman-facing number | Backing model | Service |
|------------------------|---------------|---------|
| 9,589 tCO2e | `Calculation.co2e_kg` sum | `DashboardService` |
| 7 / 35 · 20% coverage | `InventorySource` + `InventorySourceStatus` | `InventoryCoverageService` |
| 3 SBTi targets | `SBTiTarget` | `SBTiTargetViewSet` |
| DQ tier / score | `InventorySourceStatus.data_quality_tier`, `Calculation.quality_score` | coverage + `DashboardService` |
| 7 actions | `CoverageAction` | `CoverageActionViewSet` |
| SBTi glidepath | `SBTiTarget.reduction_pct` | `YearlyComparisonService._build_sbti_trajectory` |
| FY25–26 open period | `ReportingPeriod` | `ConsoleService` |

---

*Ready to execute Phase A on request — the new work is small and additive, building
on services that already exist and are verified.*
