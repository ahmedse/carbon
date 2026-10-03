# Carbon — Data completeness capability specification

| Field | Value |
|---|---|
| **Status** | Draft for owner review · two decisions open (see §7, M3 and H2). No "coverage complete" claim. |
| **Version** | 1.0 |
| **Date** | 3 October 2026 |
| **Applies to** | Carbon on AASTMT · open reporting period **Calendar year 2026 (period 17)** |
| **Capability owner** | Carbon Inventory Lead |
| **Open decisions owner** | Master Architect / Master (owner of Carbon) |
| **User-facing rename** | "Coverage Targets" → **"Data completeness"** (decision made; UI copy + docs only) |
| **Implementation owner** | Fixed by other workers — this document plans and constrains, it does not implement. |
| **Related locks** | `domain_packs/carbon/assurance/coverage_target_contract.yaml` (2 Oct 2026) · `domain_packs/carbon/assurance/data_entry_contract.yaml` (2 Oct 2026) |
| **Related ADRs / rules** | ADR-0018 (i18n) · ADR-0019 (drawer) · ADR-0037 (typography) · ADR-0050 (domain-free engine) · RULE 1,2,3,4,5,8,11,13,14 |
| **Related principles** | P-03 declared denominator · P-05 quality ≠ completeness · P-06 exclusion is a record · P-16 one dataset for act and report |
| **Evidence state at time of writing** | The measurement core is fixed for D1–D6 and covered by `backend/emissions/tests/test_coverage_targets.py` (**55 passing**, re-run 3 Oct 2026; the named causality test `T:test_task_completion_moves_the_measured_counts` is present and green). **D6 (tasks move progress) is closed** — see §0.1. The coverage UI is conformed including **M4** (scope labels localize the translatable word and bdi-isolate the Latin GHG code). This spec still does **not** claim "coverage complete". |

> **Changelog — 3 Oct 2026.** Measurement core D1–D6 fixed and test-backed
> (`emissions/coverage_targets.py` + `emissions/serializers.py`;
> `test_coverage_targets.py` 55 passing); coverage UI conformed to the audit
> including **M4** scope labels (39 frontend coverage tests in the two targets
> suites; `npm run i18n:check` 5755-key EN/AR parity); board and detail share the
> measured / excluded wording; feature renamed user-facing to
> **Data completeness**. **D6 closed** (tasks are causal through the real rows
> they produce); **L2 and L3 met** (see §5).

> **Rule of reading.** Where this spec and an existing lock disagree, the lock in
> `coverage_target_contract.yaml` / `data_entry_contract.yaml` wins, and the
> disagreement is a defect to be filed, not a licence to re-interpret.

---

## 0. Change record — the rename, and what stays

The feature formerly called **"Coverage Targets"** is renamed user-facing to
**"Data completeness"**. The rename is **presentation only**:

| Renamed (user-facing) | Unchanged (identifiers — do not rename in code) |
|---|---|
| Page titles, sidebar label, tab labels, EN/AR catalog strings, board copy | `CoverageTarget`, `CoverageTask` models |
| Documentation headings (this file, canvas section) | `emissions/coverage_targets.py` module + functions |
| Tooltips / helper text that said "coverage target" | Routes `/carbon/admin/coverage-targets[/:targetId]` |
| | Migrations `0016_coveragetarget_coveragetask_and_more.py`, `0017_coverage_target_campus.py` |
| | Locked contract ids (`L-COV-TWO-LAYER`, `L-TARGET-SHAPE`, `L-TARGET-TASKS`, `L-COV-SINGLE-REPORTER-2`, `L-BENCHMARK-RECONCILE`) |

**Why:** the owner chose the clearer product name. Renaming identifiers, routes,
or migrations would be an unrelated, riskier change and would break the locked
contract references. A future identifier rename is its own decision with its own
migration, and is explicitly **out of scope here**.

### 0.1 Measurement defects D1–D6 — status at 3 Oct 2026

D1–D6 are fixed in `emissions/coverage_targets.py` (plus `emissions/serializers.py`
for the D2 write validation) and proved by `backend/emissions/tests/test_coverage_targets.py`
(**55 passing**, re-run 3 Oct 2026). D6 is **fixed** by making tasks causal without
faking: `target_progress()` still derives every measured count from real stream
state only, and the new `task_closure()` / `next_actions` derivation binds each
task to the live gap it declares and reports whether the underlying data actually
moved. A done status alone changes no measured count. The status column is kept
honest.

| Id | Defect (verified) | Where the fix lives | Status at 3 Oct 2026 | Evidence |
|---|---|---|---|---|
| **D1** | The quality floor (`min_quality_tier`) is stored and displayed but was **never enforced**: a Tier-4 Estimated stream counted toward a Tier-2 Verified target. | `target_progress()` floor gate in `emissions/coverage_targets.py` | **DONE** | `T:test_below_floor_stream_does_not_satisfy_the_floor`, `T:test_measured_stream_with_no_tier_is_not_credited_against_a_floor` |
| **D2** | Absolute goals compared `kgCO2e` against a free-text `goal_unit`, and an absolute‑kgCO2e goal is an **emissions target**, not a completeness KPI. | `_CO2E_UNIT_FACTORS` / `co2e_unit_factor` / `canonical_co2e_unit` + `target_progress()` `metric='absolute_emissions'`, `goal_concept='emissions_value'` in `emissions/coverage_targets.py`; write validation in `emissions/serializers.py` | **DONE** | `T:test_absolute_goal_reports_kg_only_from_real_calculations`, `T:test_absolute_co2e_goal_reports_value_in_goal_unit`, `T:test_absolute_goal_rejects_a_non_co2e_unit`, `T:test_absolute_goal_accepts_a_co2e_mass_unit`, `T:test_absolute_goal_needs_a_unit` |
| **D3** | Exclusions inflated the score: `settled = entered + excluded` and `measured_pct = settled / required` could read 100% with zero measured kg. | `target_progress()` in `emissions/coverage_targets.py` (`measured_pct` floor-blind; `excluded_pct` separate; `settled_pct` transparency-only) | **DONE** | `T:test_excluded_counts_as_settled_not_entered`, `T:test_missing_stream_is_not_a_percent_claim` |
| **D4** | Campus targets measured nothing: sources matched on exact `org_unit_id` with **no descendant rollup**. | `target_sources()` via `OrgUnit.get_descendant_ids(include_self=True)` + `no_declared_sources` finding in `target_progress()` in `emissions/coverage_targets.py` | **DONE** | `T:test_target_rolls_up_descendant_unit_streams`, `T:test_narrower_unit_target_does_not_see_the_parent_stream`, `T:test_zero_source_boundary_reports_explicit_finding` |
| **D5** | "Entered" credited a stream with **no kg**, which is looser than the locked "covered" (link **and** a same-period Calculation). | `source_state()` `L-COVERED` branch in `emissions/coverage_targets.py` | **DONE** | `T:test_entered_requires_calculation_on_the_same_period`, `T:test_raw_row_without_calculation_is_in_progress_not_entered` |
| **D6** | Tasks never move progress: completing a task does not change the measured counts (the feature reports intake more than it drives it). | `target_progress()` derives a per-target `next_actions` list from the live gap set; `task_gap_code()` / `_task_gap_changed()` / `task_closure()` in `emissions/coverage_targets.py` bind a task to the gap it declares and expose `closes`; the ratio still moves **only** through the real row/Calculation, never the status flag | **DONE** | `T:test_task_completion_moves_the_measured_counts` (both halves: a forced done flip moves no measured count and does not read closed; entering the real row/Calculation moves the counts and flips the task to `closed`), `T:test_next_actions_name_the_real_gap_and_its_prefilled_stream`, `T:test_empty_universe_requests_declared_sources`, `T:test_payload_exposes_task_closes_and_next_actions`, `T:test_bound_table_without_a_stream_is_open_not_closed` |

### 0.2 Audit verdict on the coverage page family

A UI/UX design-system audit of the `coverage` page family found:

- **Verdict:** the **targets pages are the best-built of the family** — they use
  `PageContainer`/`PageHeader`, `FilteredDataGrid`, `SearchSelect`, the shared
  `SystemDialog`, shared Intl number/percent and date formatters, theme tokens,
  `bdi`, and the `PROGRESS` tooltip. The real violations found were **i18n,
  component reuse, and grid behaviour**, and they lived mostly on the **streams
  page** (`InventoryCoveragePage.jsx`) and the **shared layer** — not on the
  targets grid/detail themselves.
- **Already fixed (do not re-open):** shared Intl number/percent formatter,
  shared date formatter, inline `fontWeight` → `variant`, `PROGRESS` tooltip,
  icon-button `aria-label`s.
- **Conformed by the frontend worker (3 Oct 2026; coverage target suites green +
  `npm run i18n:check` 5755-key EN/AR parity):** H1 `InventoryCoveragePage`
  strings moved behind `t(...)`; H2 page-local `StatCard`/chips/`CoverageBar`
  replaced by shared primitives (`components/Cards/StatCard`, shared atoms in
  `coverageTargetsShared.jsx`, `LtrText`); H3 governed enums use `SearchSelect`
  (`components/Form`); M1 row click highlights only and the explicit Open action
  navigates; M2 targets grid exposes search + scope/status filters; M3 target
  detail is a neutral, target-derived counts rollup with no stream-state
  vocabulary; M6 streams grid has search (no `hideSearch`); L1/L2 page-local
  styling/`Ltr` removed.
- **M4 resolved — glossary-Latin scope labels:** tier labels are EN+AR
  translated (`inventoryCoverage.tier1..5`), and the **scope** label is now
  localized too. `coverageTargetsShared.jsx` exports `ScopeLabel`, which renders
  the translatable word from `coverageTargets.scopeWord` / `scopeCategoryWord`
  ("Scope" / "Cat" → "النطاق" / "الفئة") while wrapping only the Latin GHG code
  (`1+2`, a category number) in the shared bdi primitive (`LtrText`). The string
  form `scopeLabel(t, target)` is used for filter options and i18n
  interpolation, also localized. The backend `get_scope_display()` value stays
  the English-Latin domain code **by glossary decision** (documented on
  `TARGET_SCOPE_CHOICES` in `models.py`): translating it there would create a
  second, API-owned copy of a UI string. This closes the last L3 item.
- Verified done on this pass: the two coverage target suites (39 tests) green;
  `npm run i18n:check` **5755-key** EN/AR parity; `eslint` clean; no page-local
  `fontSize`/hex; board and detail reuse the same measured / excluded keys.

### 0.3 Deployment prerequisite (must stay prominent)

Any deploy that serves this capability **must apply BOTH**:

1. `backend/emissions/migrations/0016_coveragetarget_coveragetask_and_more.py`
   (creates `CoverageTarget` + `CoverageTask`; without it the board and detail
   500).
2. `backend/emissions/migrations/0017_coverage_target_campus.py`
   (adds the `CoverageTarget.campus` FK and the campuses / org-units / owners
   lookups; without it the form pickers have nothing to load).

Neither migration carries a data migration and neither touches an existing
table. The deploy gate is a **release condition**, not a nice-to-have.

---

## 1. Purpose and scope

### 1.1 What this capability IS

A per-cycle, board-first KPI surface where a **Carbon Lead** sets measurable
targets for **how complete the organisation's carbon ACTIVITY data is** for the
**open reporting period**, per **campus / org-unit** and per **GHG scope**
(optionally a Scope 3 category). A target carries a **goal**, a **quality
floor**, a **due date**, an **owner**, and child **tasks**. Progress is
**derived from real data rows** and is labelled **"measured, not claimed"**.
A task completes only on **real host evidence**. **Streams** (not targets)
remain the **sole** reporter of Missing / Entered / Excluded.

Layers (locked, `L-COV-TWO-LAYER`):

- **TARGETS** — the KPI layer, one target per reporting cycle.
- **STREAMS** — the declared universe (`InventorySource` +
  per-period `InventorySourceStatus`) a target is measured over.
- **TASKS** — things to achieve under a target, gated by host evidence.

### 1.2 What this capability IS NOT

- **NOT the GHG completeness assertion.** This is *declared-universe fill-rate
  and quality*, not a statement that the inventory is complete under the GHG
  Protocol. It never publishes a single "coverage complete" percent.
- **NOT an emissions target board.** A CO2e mass goal is an **emissions-value**
  figure and is presented as such; it is not relabelled as a completeness KPI
  (D2).
- **NOT a second Missing / Entered / Excluded reporter.** Streams own that
  vocabulary; the targets surface must not re-present the chips (M3 risk).
- **NOT a generic OKR / task manager.** Tasks exist only to move a named
  completeness gap or secure a named factor; they are not a backlog tool.
- **NOT a second reporting-period or state store.** One open period
  (`Calendar year 2026`). No target writes a kilogram, opens a period, or
  promotes a `CoverageGoal`.
- **NOT an authoring flow for Data Products.** Catalog-admin request/approval
  remains a Master decision and is **not built**.

---

## 2. Principles

Durable principles for this capability. Each is enforceable by a rule in §3.

| Id | Principle | Consequence if violated |
|---|---|---|
| **P-DC-1** | **Measured, not claimed.** Every ratio is derived from real rows on the target's period and labelled `measured_not_claimed`; the payload never says `coverage_complete`. | The surface becomes a brochure. |
| **P-DC-2** | **Streams are the sole state reporter.** Missing / Entered / Excluded is owned by the streams surface only; a target shows counts it derives, never a second state vocabulary. | Two sources of truth for one period (`L-COV-SINGLE-REPORTER`). |
| **P-DC-3** | **Nothing green without host evidence.** A task may be marked done only when `task_evidence()` is met; a stream counts only with real activity/calculations. | Status becomes a hand-set claim. |
| **P-DC-4** | **A number that cannot be defended is not shipped.** If the basis (denominator, floor, unit, boundary) is not stated and testable, the number does not render. | Unexplainable KPI. |
| **P-DC-5** | **No silent zero.** Missing is not `0 kg`; an empty universe is an explicit finding, not a blank or a `0%`. | Absence reads as success. |
| **P-DC-6** | **Measured and excluded are reported separately.** Excluded streams are never blended into a "measured" ratio. | Exclusions inflate the score (D3). |
| **P-DC-7** | **Domain words live in the pack; the engine stays domain-free** (ADR-0050). | Not portable; budget gate fails. |
| **P-DC-8** | **Compose shared primitives; a page-local copy is debt.** No second chip, bar, formatter, date util, or bidi helper on this surface. | Multi-agent frontend rot; M4/L2 defects. |

---

## 3. Rules (binding)

Each rule names its source (ADR/RULE/principle/defect) and the **enforcement
test** that must exist and pass. Tests under
`backend/emissions/tests/test_coverage_targets.py` are abbreviated `T:`; frontend
tests under `carbon-frontend/src/pages/carbon/__tests__/` are abbreviated `F:`.

### R-DC-01 — The quality floor is enforced on the settled-at-target gate
The floor does **not** remove a stream from `measured_pct`: `measured` counts
every stream settled **with a real kilogram** (the `L-COVERED` definition),
regardless of tier. The floor gates **settlement at target**: a measured stream
counts as `settled_at_target` only when its
`InventorySourceStatus.data_quality_tier` is **at least as good as** the target's
`min_quality_tier` (smaller-is-better, PCAF). A Tier-4 Estimated stream toward a
Tier-2 Verified target therefore stays in `measured_pct` but is counted in
`below_floor` and never settles at target, so it cannot satisfy a **percent**
target's `met` state. A measured stream with no declared tier is counted in
`tier_unknown` and is likewise not credited. If `min_quality_tier` is null, no
floor is applied and every measured stream settles at target. The percent goal's
`met`/`short` state is decided on `settled_at_target_pct`, never on
`measured_pct`; an absolute goal's `met`/`short` state is decided on
`measured_kg` (the floor gates settlement only — the raw kilogram is not hidden;
see `L-TARGET-QUALITY-FLOOR`).
*Source:* P-05; defect **D1**; `L-TARGET-QUALITY-FLOOR`; `L-TARGET-SHAPE`.
*Enforcement:* `T:test_below_floor_stream_does_not_satisfy_the_floor` (the T4
stream keeps `measured_pct` 100.00 but `settled_at_target_pct` 0.00 and `state`
short) and `T:test_measured_stream_with_no_tier_is_not_credited_against_a_floor`.

### R-DC-02 — Absolute goals are CO2e mass, presented as an emissions value
`goal_kind == 'absolute'` is restricted to **CO2e mass** (`kgCO2e`) and rendered
as an **emissions-value** figure, explicitly **not** a completeness percent. The
unit is not free text; `goal_unit` is validated against the allowed CO2e mass
unit set. An absolute goal never contributes to, or reads as, a completion ratio.
*Source:* defect **D2**; `L-TARGET-SHAPE` ("an absolute goal is an EMISSIONS
target, not a completeness KPI").
*Enforcement:* `T:test_absolute_co2e_goal_reports_value_in_goal_unit` and
`T:test_absolute_goal_accepts_a_co2e_mass_unit` (an absolute goal renders
`metric='absolute_emissions'` / `goal_concept='emissions_value'`) plus
`T:test_absolute_goal_rejects_a_non_co2e_unit` (shipped, D2 fixed).

### R-DC-03 — Measured and excluded are always reported separately
`measured_pct` counts **only measured (entered-with-kg) streams** over all
`required` streams in scope (a floor-blind denominator). Formally excluded
streams are reported as their own count (`excluded` / `excluded_pct`) and are
**never** added into the measured numerator; `settled = measured + excluded` and
`settled_pct` are reported for transparency only and are **never** the gate. A
fully-excluded scenario reads `measured_pct` 0.00 and `settled_at_target_pct`
0.00, so its `state` is `short`, never `met`. For a percent goal the `met`/`short`
state is decided on `settled_at_target_pct` (R-DC-01); for an absolute goal it is
decided on `measured_kg` (R-DC-02).
*Source:* P-06; defect **D3**; `L-TARGET-MEASURED-VS-EXCLUDED`; `L-COV-SINGLE-REPORTER-2` (Excluded is a record).
*Enforcement:* `T:test_excluded_counts_as_settled_not_entered` asserts
`measured_pct` 0.00, `excluded_pct` 100.00, `settled_pct` 100.00,
`settled_at_target_pct` 0.00 and `state` short (the shipped, intended semantics);
`T:test_entered_requires_calculation_on_the_same_period` asserts `measured_pct`
100.00 and `state` met.

### R-DC-04 — Campus / org-unit boundaries roll up descendants
A target keyed to a campus (or any org unit with children) measures the union of
its **real descendant** `InventorySource` rows (MDM `OrgUnit` parent hierarchy),
not only sources with an exact `org_unit_id`. A campus target with descendant
sources must have `required > 0`.
*Source:* defect **D4**; ADR-0028 (instance-gated org tree); `L-TARGET-SHAPE`
("per campus/org-unit").
*Enforcement:* `T:test_target_rolls_up_descendant_unit_streams`,
`T:test_narrower_unit_target_does_not_see_the_parent_stream`, and
`T:test_zero_source_boundary_reports_explicit_finding` (shipped, D4 fixed).

### R-DC-05 — "No declared sources" is an explicit finding
When `required == 0`, progress returns an explicit `state = "empty"` with a
human-readable finding ("no declared sources for this boundary/scope"), never a
blank row, never `0%`. The UI renders that finding as its own empty state.
*Source:* P-03, P-DC-5; `test_empty_universe_is_absent_not_zero` (exists);
`F:CoverageTargetsPage.test.jsx` empty-state case.
*Enforcement:* `T:test_empty_universe_is_absent_not_zero` +
`T:test_zero_source_boundary_reports_explicit_finding` (the `no_declared_sources`
finding code is asserted, not just the state).

### R-DC-06 — "Entered" (measured) requires a real kilogram
A stream counts as **measured** only when it has a link **and** a same-period,
non-stale, non-superseded `Calculation` on a non-archived `DataRow` — i.e. the
locked "covered" definition (`CR-COV-01`, `L-COVERED`). A stream with a row but
no kg is reported as **entered-without-kg / awaiting factor**, distinct from
measured, and does **not** raise the measured ratio.
*Source:* defect **D5**; `L-COVERED`; P-15 (activity before factor).
*Enforcement:* `T:test_entered_requires_calculation_on_the_same_period` and
`T:test_raw_row_without_calculation_is_in_progress_not_entered` (shipped, D5 fixed).

### R-DC-07 — Tasks drive progress, and complete only on host evidence
Completing a task must be reflected in the measured counts by the **real row it
produces** (a bound `DataTable` with a `DataRow` reaching `through_month`, a real
`fill_gap` row, an active factor), never by the task status flag alone. A done
transition without evidence returns `400 task_evidence`.
*Source:* defect **D6**; `L-TARGET-TASKS`; P-DC-3.
*Enforcement:* `CoverageTaskEvidenceTests` (evidence gating — a done transition
without evidence returns `400 task_evidence`) and the causality test
`T:test_task_completion_moves_the_measured_counts` (D6 closed, §0.1): a forced
done flip moves no measured count and does not read `closed`; entering the real
row/Calculation the verb produces moves the counts and flips the task to
`closed`. The task payload exposes `closes` (`awaiting_evidence` / `open` /
`closed`), and the target payload exposes `next_actions` derived from the live
gap set. This rule is **met**.

### R-DC-08 — Every user-facing string has EN + AR parity (ADR-0018)
No hardcoded English in the feature surface. Tier and scope labels are translated
or wrapped in the shared bidi primitive (`bdi`), never left as raw English inside
an RTL sentence. Parity is a gate, not a review opinion.
*Source:* ADR-0018; audit **H1, M4**; ADR-0037.
*Enforcement:* `npm run i18n:check` (`scripts/check-i18n-keys.js`) asserts full
EN/AR key parity (5755 keys, re-run 3 Oct 2026). No dedicated static
no-hardcoded-string test exists; the feature page tests render through the i18n
provider and assert real EN copy. The scope word ("Scope" / "Cat") is localized
through `coverageTargets.scopeWord` / `scopeCategoryWord`, and only the Latin GHG
code is `bdi`-isolated by the shared `ScopeLabel` (M4; `F:` RTL test asserts the
code renders as `<bdi dir="ltr">`).

### R-DC-09 — Shared components and shared formatters only
Use `SearchSelect` (`src/components/Form/SearchSelect.jsx`) for every governed /
data-driven enum; `FilteredDataGrid` for every record list; the shared number /
percent formatter (`src/utils/formatNumber.js`) and date formatter
(`src/utils/dateUtils.js`); the shared `SystemDialog`, `PageContainer`,
`PageHeader`, `EmptyState`, and bidi primitive. No page-local `StatCard`,
near-copy chips, hand-rolled bar, page-local `formatDate`, or page-local `Ltr`.
Adding/extending a shared **Layer-2** primitive requires Master authority
(see §7, H2).
*Source:* RULE 2, RULE 13, RULE 14; audit **H2, H3, M4, L2, L1**; ADR-0018.
*Enforcement:* a static check that the feature surface imports no page-local
duplicate of an existing shared primitive; `F:` page tests render through the
shared components.

### R-DC-10 — Grid behaviour is the RULE-14 contract
Every record list has **search across the fields a person would type**, the
**relevant** filters (not one per column), column sort with a sensible default,
and paging. **Row click highlights only**; opening a record is an explicit
labelled action. `hideSearch` is not permitted on a growable record list.
*Source:* RULE 14; `compact-ui.md`; audit **M1, M2, M6**.
*Enforcement:* `F:CoverageTargetsPage.test.jsx` asserts search + filter presence
(no `hideSearch`), and a row-click test asserts the route does
**not** change on click and **does** change on the explicit action.

### R-DC-11 — Every denominator / ratio states its basis
The denominator basis is conveyed by the `required` count together with the
`quality_floor_applied` boolean and the separated ratio fields (`measured_pct`,
`excluded_pct`, `settled_pct`, `settled_at_target_pct`). The payload also carries
`basis`, which is a **stable identifier** — the shipped constant
`streams_with_a_real_row_on_the_target_period` — naming the denominator rule; it
does **not** vary per target. The floor/exclusion distinction is carried by the
separate boolean and ratio fields above, not by `basis`. A progress response
that omits `basis`, `required`, `quality_floor_applied`, or the separated ratios
fails the rule.
*Source:* P-DC-4; `target_progress()` return shape in
`emissions/coverage_targets.py`.
*Resolution (3 Oct 2026):* doc-only alignment — `basis` stays a stable
identifier and the floor/exclusion distinction is read from the separate fields;
no code change was made.
*Enforcement:* the shipped return shape in `target_progress()`; the separated
fields are asserted by `T:test_below_floor_stream_does_not_satisfy_the_floor`,
`T:test_excluded_counts_as_settled_not_entered` and
`T:test_empty_universe_is_absent_not_zero`. No dedicated `basis`-string test
exists; the coverage UI reads the separated ratios and the counts, not `basis`.

### R-DC-12 — No page-local typography, colour, or number/date formatting
No inline `fontSize`, `fontWeight`, hex colour, or rgb on this surface
(ADR-0037 / RULE 1 / RULE 8). Numeric columns are right-aligned and monospace.
*Source:* RULE 1, RULE 3, RULE 8; ADR-0037; audit **L1**.
*Enforcement:* static grep-based check for `fontSize`/`#rrggbb` in the feature
files (a lint assertion, not a review).

### R-DC-13 — Single-reporter guard on the target detail
The target's progress shows **counts and a measured ratio**; it must not
re-present Missing/Entered/Excluded as a stream-state vocabulary. The counts are
labelled as target-derived; any stream-level state links to the streams surface
instead of copying it. Whether the chips remain as a neutral counts rollup or are
removed is **open (M3)**; the shipped detail currently renders a neutral,
target-derived counts rollup with no stream-state vocabulary
(`F:CoverageTargetDetailPage.test.jsx`), pending formal M3 acceptance (§7.1).
*Source:* P-DC-2; `L-COV-SINGLE-REPORTER`; audit **M3**.
*Enforcement:* `F:CoverageTargetDetailPage.test.jsx` asserts the detail does not
render a stream-state chip whose label duplicates the streams vocabulary; the
formal M3 acceptance stays with Master.

### R-DC-14 — Deployment requires 0016 + 0017
No release that serves this capability ships without both migrations applied; a
release check asserts both are present in the deploy's migration set.
*Source:* §0.3; `L-TARGET-SHAPE`; observed live 500 without 0016.
*Enforcement:* a release/CI assertion (script or checklist item) that both
migration files are in the applied set.

### R-DC-15 — Catalog-admin Data Product authoring stays Master-gated
`bind_data_product` may reference an **existing** `DataTable` only. The
catalog-admin request/approval flow is not built and is not claimed.
*Source:* `data_entry_contract.yaml` `L-CONTRACT`, `L-TARGET-TASKS`;
`coverage_target_contract.yaml` `limit`.
*Enforcement:* existing `T:test_bind_data_product_cannot_be_done_without_a_table`
+ a test that no code path creates a `Module`/`DataTable`/`DataField` from a
coverage task.

---

## 4. Benchmarks (measurable success for THIS capability)

Each benchmark states its **threshold** and **how it is measured**. Thresholds
are structural/parity/behavioural, not invented business quantities.

| Id | Benchmark | Threshold | Measured by |
|---|---|---|---|
| **B-01** | Quality floor regression | The D1 regression passes: a T4 stream toward a T2 target stays in `measured_pct` but is excluded from `settled_at_target` (the percent `met` gate) and counts in `below_floor` | `T:test_below_floor_stream_does_not_satisfy_the_floor`, `T:test_measured_stream_with_no_tier_is_not_credited_against_a_floor` |
| **B-02** | Absolute goal is an emissions value | The D2 tests pass; an absolute goal renders `metric='absolute_emissions'` / `goal_concept='emissions_value'`, never enters a completeness ratio, and rejects a non-CO2e unit | `T:test_absolute_co2e_goal_reports_value_in_goal_unit`, `T:test_absolute_goal_accepts_a_co2e_mass_unit`, `T:test_absolute_goal_rejects_a_non_co2e_unit` |
| **B-03** | Excluded never inflates | A fully-excluded scenario reads `measured_pct` **0.00** and `settled_at_target_pct` 0.00 → `state` **short**, with exclusions reported separately (`excluded_pct` 100.00) | `T:test_excluded_counts_as_settled_not_entered` |
| **B-04** | Campus rollup | A campus target with descendant sources has `required > 0`; a campus with none returns `empty` with the `no_declared_sources` finding | `T:test_target_rolls_up_descendant_unit_streams`, `T:test_zero_source_boundary_reports_explicit_finding` |
| **B-05** | Entered requires a kg | A row without a same-period Calculation is **not** measured (reported `in_progress`) | `T:test_raw_row_without_calculation_is_in_progress_not_entered` |
| **B-06** | Tasks move progress | Completing an evidence-backed task changes the measured counts through the real row it produces; no-evidence done is refused (400); a done status without the data moves nothing and does not read `closed`. **Met** (D6 closed) | `T:CoverageTaskEvidenceTests` (evidence gating); `T:test_task_completion_moves_the_measured_counts`, `T:test_next_actions_name_the_real_gap_and_its_prefilled_stream`, `T:test_bound_table_without_a_stream_is_open_not_closed` |
| **B-07** | No silent zero | `required == 0` returns `state="empty"` **with a named `no_declared_sources` finding**, never `0%` or blank | `T:test_zero_source_boundary_reports_explicit_finding`, `T:test_empty_universe_is_absent_not_zero`, `F:` empty-state case |
| **B-08** | i18n parity | Every feature string exists in EN **and** AR; the checked-in parity count is equal | `npm run i18n:check` (5755-key EN/AR parity, 3 Oct 2026) |
| **B-09** | Denominator basis | Every returned progress carries the stable `basis` identifier plus `required`, `quality_floor_applied`, and the separated ratio fields (R-DC-11) | return shape in `emissions/coverage_targets.py`; separated fields asserted by `T:test_below_floor_stream_does_not_satisfy_the_floor`, `T:test_excluded_counts_as_settled_not_entered` |
| **B-10** | No page-local styling/formatting | Zero `fontSize`, `fontWeight`, hex/rgb, or page-local date/number formatting on the feature surface | static lint assertion (R-DC-12) |
| **B-11** | Grid is a RULE-14 list | Search + relevant filters present (no `hideSearch`); row click does **not** navigate; an explicit action does | `F:CoverageTargetsPage.test.jsx`, row-click test (R-DC-10) |
| **B-12** | Single reporter respected | The target detail does not duplicate the streams Missing/Entered/Excluded vocabulary | `F:CoverageTargetDetailPage.test.jsx` (resolution per M3) |
| **B-13** | Deploy gate | A release check asserts both 0016 and 0017 are applied | release/CI assertion (R-DC-14) |
| **B-14** | No fabricated kg | No benchmark path writes a 2026 kilogram without a real Calculation | existing `T:test_absolute_goal_reports_kg_only_from_real_calculations`, `T:test_missing_stream_is_not_a_percent_claim` |

---

## 5. Excellence ladder

Each rung is **objectively scorable from tests/evidence**, never from prose.
**A higher rung requires every lower rung.** "Today" is 3 October 2026. The
measurement core D1–D6 is fixed and test-backed (§0.1): **D6 (tasks move
progress) is closed**, D4 rollup is green, and the M4 scope-label item is
resolved, so **L2 and L3 are met**. L6/L7 are not defined for this capability and
must not be claimed.

| Rung | Name | Objective definition (scored from) | Achieved today (3 Oct 2026) |
|---|---|---|---|
| **L0** | **Surface & contract** | Board + detail + tasks exist; progress is derived (not hand-set); payload returns `claim="measured_not_claimed"` and `coverage_complete=false`; no fabricated kg. *Scored from:* `T:test_empty_universe_is_absent_not_zero`, `T:test_missing_stream_is_not_a_percent_claim`, `T:test_absolute_goal_reports_kg_only_from_real_calculations`, `F:` board honesty test. | **MET** — shipped; the measurement core is now fixed for D1–D6 (§0.1). L0 does not imply L2. |
| **L1** | **Honest measurement core** | The measurement-core ratio semantics are enforced and regression-tested: the floor gates settlement at target (D1); an absolute goal is a CO2e emissions value with a rejected non-CO2e unit (D2); measured ≠ excluded and exclusions never read as met (D3); entered requires the locked L-COVERED path with a same-period Calculation (D5). Boundary rollup (D4) and task causality (D6) are scored at L2. *Scored from:* B-01, B-02, B-03, B-05. | **MET** — `test_coverage_targets.py` **55 passing** (re-run 3 Oct 2026): B-01/B-02/B-03/B-05 all green. D6 is not part of L1. |
| **L2** | **Boundary & drive correct** | L1 **and** descendant rollup is exercised against a real org tree (D4), **and** a task completion demonstrably moves the measured counts through the row it produces (D6). *Scored from:* B-04 (D4) and B-06 (D6) in a multi-level tree fixture. | **MET** — D4 rollup is green (B-04) and **D6 is closed** (B-06): `T:test_task_completion_moves_the_measured_counts` asserts both that a forced done flip moves no measured count and does not read `closed`, and that entering the real row/Calculation moves the counts and flips the task to `closed`. The target payload's `next_actions` names the live gap and its affected stream; the task payload's `closes` reports `awaiting_evidence` / `open` / `closed`. |
| **L3** | **UI conformance** | L2 **and** EN+AR parity asserted for every feature string; `SearchSelect`/`FilteredDataGrid`/shared formatters only; grid search+filters present; row click highlight-only; no page-local `fontSize`/hex/duplicate primitive. *Scored from:* B-08 … B-12. | **MET** — L2 met; the last audit item **M4 is resolved**: `ScopeLabel` localizes the scope word (EN "Scope" / AR "النطاق") and bdi-isolates only the Latin GHG code, with the backend display value kept English-Latin by documented glossary decision. Verified: 39 tests in the two coverage target suites pass; `npm run i18n:check` **5755-key** EN/AR parity; shared `SearchSelect`/`StatCard`/`NumericText`/`LtrText`; grid search+filters; row-click highlight-only; neutral counts rollup; board and detail reuse the same measured / excluded keys. |
| **L4** | **Governed authoring & provenance** | L3 **and** every ratio states a defensible basis (B-09); the catalog-admin Data Product authoring flow is Master-approved and built (or its absence is explicitly accepted); the 0016+0017 deploy gate is enforced (B-13). *Scored from:* B-09, B-13 + Master decision record. | **NOT MET** — the denominator basis is carried by shipped fields (B-09); authoring is still Master-gated and not built. |
| **L5** | **Operated, assurance-grade** | L4 **and** the capability holds across a **dated** live window with named host evidence, and a regression in any rung re-opens the rung. *Scored from:* a dated live evidence file + a no-regression window, **never** from a file pinned in code. | **NOT CLAIMED.** |

**State of the ladder today:** **L0, L1, L2, and L3 met** (measurement core
D1–D6 fixed; `test_coverage_targets.py` 55 passing, 3 Oct 2026). **L2 met:** D4
rollup green (B-04) and D6 task causality closed (B-06) — a task moves the
measured counts only through the real row it produces, and an evidence-less done
moves nothing. **L3 met:** UI conformance is complete now that M4 scope labels
localize the translatable word and bdi-isolate the Latin code (EN/AR parity
5755 keys). **L4–L5 not met / not claimed.** No L6/L7 for this capability.

---

## 6. Anti-patterns / do-not-build

- **Do not build a generic OKR / task manager.** Tasks are not a backlog; every
  task names a completeness gap or a factor to secure.
- **Do not build a second Missing / Entered / Excluded reporter.** The streams
  surface owns that vocabulary (`L-COV-SINGLE-REPORTER`). No second state store,
  no duplicated chips presented as stream state.
- **Do not allow per-target custom formulas.** A target chooses a goal kind, a
  floor, and a boundary; it does not carry a bespoke expression.
- **Do not duplicate threshold approval.** The quality floor is set once on the
  target and enforced in the measurement core; do not add a parallel
  approval/threshold path in the UI or the API.
- **Do not present AI-generated targets as measures.** Any suggested target is a
  proposal, never a measured value, and never writes without human consent
  (ADR-0046).
- **Do not show any "completeness %" to leadership without the floor and the
  measured-vs-excluded split.** A blended percentage is an anti-pattern (D3).
- **Do not loosen goldens to pass.** If a golden disagrees with committed host
  evidence, the golden is corrected only with named evidence, never relaxed.
- **Do not rename identifiers, routes, or migrations** to match the user-facing
  "Data completeness" rename (§0).
- **Do not claim L6/L7**, "coverage complete", or an assured inventory from this
  capability.

---

## 7. Open decisions owned by Master

These are **not decided here**. They are recorded with a recommendation and the
rationale; Master owns the call.

### 7.1 M3 — target-detail counts: drop the chips, or keep a neutral counts rollup?

**Question.** The target detail previously re-presented `required / entered /
excluded / awaiting_factor / missing` as chips (`COUNT_CHIPS` in
`CoverageTargetDetailPage.jsx`). This is the second-reporter risk. The shipped
detail now renders a neutral, target-derived counts rollup with no stream-state
vocabulary (`F:CoverageTargetDetailPage.test.jsx`), following the recommendation
below; the decision remains for Master's formal acceptance. Do we
**remove** the Missing/Entered/Excluded chips from the target detail entirely, or
**keep a neutral counts rollup** that is clearly target-derived (counts only, no
stream-state vocabulary) while the streams surface remains the sole reporter?

**Recommendation: keep a neutral, target-derived counts rollup — do not remove.**
Rationale: the counts are *the target's own derived progress*, not a stream-state
reporter; removing them would strip the owner's at-a-glance view of what is
outstanding. The fix is **labelling and vocabulary**, not deletion: rename the
rollup to target-derived counts, drop the "Missing/Entered/Excluded" verbs from
the target surface, keep a cross-link to the streams row for the underlying
state, and assert in a test that no stream-state verb is duplicated. Removing
them (the alternative) is acceptable but reduces the target's usefulness and
still needs the same test to prevent re-introduction.

### 7.2 H2 — authority to add/extend shared Layer-2 primitives in `src/components`

**Question.** The audit found duplicated/one-off components (page-local
`StatCard`, near-copy chips, hand-rolled `CoverageBar`, page-local `Ltr`, local
`formatDate`). Fixing this properly requires either (a) adding/extending shared
**Layer-2** primitives in `src/components` (e.g. a shared stat/metric primitive,
a shared progress/coverage bar, a shared bidi primitive, a shared tier chip), or
(b) constraining the fix to reusing what already exists and deleting duplicates,
without touching the shared layer.

**Recommendation: grant the shared-layer extension — add narrowly-scoped shared
primitives and delete the duplicates.** Rationale: RULE 2 / the design-system
3-layer model make "if a primitive is missing, that is a Master Architect
decision to add to Layer 2." The duplicated `CoverageBar`, `StatCard`, chips, and
`Ltr` are exactly the missing/unused-primitive case; a page-local fix would
propagate the same debt to the next page. The grant must be **narrow**: only the
primitives the audit names, extended via props where possible, with the shared
layer as the single source of truth. The alternative (b) is safe but leaves the
shared layer incomplete and the duplication likely to recur.

---

## 8. Evidence map (where the facts live)

| Concern | File |
|---|---|
| Target / task models | `backend/emissions/models.py` (`CoverageTarget` line 1742, `CoverageTask` line 1844) |
| Derived progress + evidence | `backend/emissions/coverage_targets.py` (`target_sources`, `source_state`, `target_progress`, `task_evidence`) |
| Target API + board | `backend/emissions/views.py` (`CoverageTargetViewSet`); routes in `backend/emissions/urls.py` (`coverage-targets`); `emissions/tests/test_coverage_targets.py` |
| Migrations (deploy gate) | `backend/emissions/migrations/0016_coveragetarget_coveragetask_and_more.py`, `0017_coverage_target_campus.py` |
| Targets UI (best-built) | `carbon-frontend/src/pages/carbon/CoverageTargetsPage.jsx`, `CoverageTargetDetailPage.jsx`, `coverageTargetsShared.jsx` |
| Streams UI (main audit site) | `carbon-frontend/src/pages/carbon/InventoryCoveragePage.jsx` |
| Shared primitives | `carbon-frontend/src/components/{Form/SearchSelect.jsx,FilteredDataGrid.jsx,SystemDialog.jsx}` |
| Shared formatters | `carbon-frontend/src/utils/formatNumber.js`, `carbon-frontend/src/utils/dateUtils.js` |
| i18n gate | `carbon-frontend/scripts/check-i18n-keys.js` (`npm run i18n:check`) |
| Locked contracts | `domain_packs/carbon/assurance/coverage_target_contract.yaml`, `data_entry_contract.yaml` |

---

*Local only. This spec changes no feature code, deploys nothing, commits nothing,
and does not touch `backend/ai/engine/**`. D1–D6 and the UI conformance work were
implemented by other workers and are scored here from their tests; **D6 (tasks
move progress) is now closed** and the last L3 item (M4) is resolved. This
document constrains and scores them; it does not re-fix them.*
