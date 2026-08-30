# TASK — AI Emissions Data Grounding (Tier 1, read-only)

| Field | Value |
|---|---|
| Phase ID | AI-EMISSIONS-GROUNDING |
| Role | `backend-worker` (V4-Flash) |
| Model | DeepSeek V4-Flash (RULE_24 — only Master Architect uses V4-Pro) |
| Status | not-started |
| Depends on | none |
| Tier | Tier 1 — READ-ONLY grounding only |

---

## 1. Why this exists (root cause from the audit)

A user asked the AI about emission factors and got generic textbook speech with **zero
system data**. Root cause is 4 stacked defects:

1. **`api_catalog` has no emissions endpoints** — `backend/ai/engine/instances/carbon/instance.yaml`
   lists only `dq`/`dataschema` endpoints. The AI has no declared way to read emissions data.
2. **`_IN_PROCESS_ENDPOINTS` has no emissions routes** — `backend/ai/host_executor.py` only maps
   `dq`/`dataschema`/memory. Even if the catalog declared them, the in-process executor would
   raise `ToolExecutionError("…not available for in-process execution")`.
3. **Phantom `query_host_db` tool** — `backend/ai/engine/llm/prompt_synthesizer.py` lines **89**
   and **347** tell the LLM to call `query_host_db`, but that tool is **not registered** in
   `STATIC_TOOL_DEFINITIONS`. The real tool is `call_host_api`.
4. **Wrong unit + no grounding instruction** — `backend/ai/domain/emissions.py`
   `system_prompt_extension` says *"Emission factors are in tCO₂e per unit activity"* — but the
   seeded factors are **kg CO2e**. It also never teaches the unit hierarchy nor instructs the AI
   to read live data instead of reciting factor values from memory.

This task fixes all four. The measurable success criterion: the AI can read a live
`EmissionFactor`, a `Calculation` total, and a `dashboard` total and report the **real** numbers.

---

## 2. Scope decisions (Master Architect rulings — do NOT deviate)

### 2.1 Tier 1 only — 5 read-only GET endpoints

| Tool name (catalog) | Canonical endpoint | Handler key | Data scope |
|---|---|---|---|
| `list_emission_factors` | `carbon-api/carbon/factors` | `emission_factors` | **GLOBAL** (RULE_12) |
| `list_gwp_gases` | `carbon-api/carbon/gwp` | `gwp_gases` | **GLOBAL** (RULE_12) |
| `list_reporting_periods` | `carbon-api/carbon/periods` | `reporting_periods` | **GLOBAL** |
| `get_calculation_summary` | `carbon-api/carbon/calculations/summary` | `calculation_summary` | **ORG-SCOPED** |
| `get_chairman_overview` | `carbon-api/carbon/chairman` | `chairman_overview` | **ORG-SCOPED** |

- The mount path is `/carbon-api/carbon/` (namespace `carbon`, app `emissions`) —
  confirmed in `backend/config/urls.py:79`.
- `chairman/` is the single-call Tier-1 aggregate (`ChairmanService.get_chairman_data`) and
  already composes dashboard + coverage + SBTi + actions + trajectory — prefer it over
  `dashboard/`/`yearly-comparison/`/`coverage/` for "how are we doing" questions.

### 2.2 Read gating — any authenticated user

- `factors`, `gwp`, `periods` are **GLOBAL reference data** (RULE_12: *"reference data
  (EmissionFactor, GWP, ReferenceSet) is GLOBAL"*). The HTTP `AdminOrSuperuserOnly` on
  `EmissionFactorViewSet`/`GWPViewSet` is a **write** guard; RULE_21 already blocks AI mutation,
  so the AI path may READ these for any authenticated user. Do **NOT** add an admin gate to reads.
- `calculation_summary` and `chairman_overview` inherit org-scoping from
  `scope_calculations()` / `get_visible_org_units()` inside the services. The handlers MUST call
  the services — do **not** re-implement scoping.

### 2.3 Explicitly OUT of scope (RULE_21)

Do **NOT** add, map, or document: `calculate/`, `batch-calculate/`, `rules/{id}/execute/`,
`report-configs/{id}/run/`, `verifications/{id}/verify/`, or any `POST`/`PUT`/`DELETE`.

### 2.4 Deferred (log separately — do NOT fix here)

`InventorySourceStatusViewSet.get_queryset()` (views.py) is **not** org-scoped (only filters
`reporting_period`/`source`). This blocks `coverage/`/`inventory-source-statuses/` from ever
entering Tier 2. **Record it in the worker report as a follow-up bug; do not touch it in this task.**

---

## 3. File-by-file changes

### 3.1 `backend/emissions/services.py` — extract `CalculationSummaryService`

Move the aggregation logic out of `CalculationSummaryAPIView.get()` (views.py ~605) into a new
service so both HTTP and in-process paths share it (no drift):

```python
class CalculationSummaryService:
    @staticmethod
    def get_summary(user, period_id=None):
        # EXACT body of CalculationSummaryAPIView.get(), returning the same dict shape:
        # {period_id, total_calculations, stale_count, by_scope, by_status, by_module,
        #  latest_run_at, last_audit}
```

### 3.2 `backend/emissions/views.py` — delegate

`CalculationSummaryAPIView.get()` becomes a thin wrapper:

```python
def get(self, request):
    period_id = request.query_params.get('reporting_period_id')
    return Response(CalculationSummaryService.get_summary(
        request.user, int(period_id) if period_id else None))
```

### 3.3 `backend/ai/host_executor.py` — map + 5 handler coroutines

**(a)** Add to `_IN_PROCESS_ENDPOINTS`:

```python
"carbon-api/carbon/factors": "emission_factors",
"carbon-api/carbon/gwp": "gwp_gases",
"carbon-api/carbon/periods": "reporting_periods",
"carbon-api/carbon/calculations/summary": "calculation_summary",
"carbon-api/carbon/chairman": "chairman_overview",
```

**(b)** Add 5 coroutines, **mirroring the exact signature, `sync_to_async(..., thread_sensitive=True)`
pattern, and return shape of `_list_dq_rules_in_process`**. All are GET-only: return
`{"status_code": 405, "data": {"detail": "Method not allowed"}}` for non-GET. Resolve user via
`self._resolve_user()`; `None` → 401.

- `_emission_factors_in_process` — `EmissionFactor.objects.filter(is_active=True)` (cap 200),
  serialize to `{"status_code": 200, "data": {"results": [...]}}`. Fields: `id, name, code,
  category, subcategory, scope, factor_value (float), factor_unit, activity_unit, country,
  source, tags`. **Convert `Decimal` → `float`.**
- `_gwp_gases_in_process` — `GWP.objects.all()` (cap 200) → `results` of
  `id, gas_name, gas_formula, gwp_ar5_100yr, gwp_ar6_100yr, gwp_ar5_20yr, gwp_ar6_20yr` (floats).
- `_reporting_periods_in_process` — `ReportingPeriod.objects.order_by('-start_date')` (cap 50) →
  `results` of `id, name, start_date, end_date, status, is_baseline`.
- `_calculation_summary_in_process` — read `period_id = params.get('reporting_period_id')`, call
  `CalculationSummaryService.get_summary(user, period_id)`, return `{"status_code": 200, "data": summary}`.
- `_chairman_overview_in_process` — read `period_id = params.get('reporting_period_id')`, call
  `ChairmanService.get_chairman_data(user, period_id)`, return `{"status_code": 200, "data": payload}`.

### 3.4 `backend/ai/engine/instances/carbon/instance.yaml` — `api_catalog` entries

Add 5 entries under the existing `api_catalog` list, matching the existing entry shape
(`name`, `description`, `method`, `endpoint`, `params`, `requires_confirmation`):

- All five: `requires_confirmation: false` (read-only).
- `endpoint` values = the canonical paths in §2.1 (no scheme/host).
- `get_calculation_summary` and `get_chairman_overview` document the optional
  `reporting_period_id` query param.
- `description` must state the data scope (global vs org-scoped) and the unit (kg CO₂e).
- Keep descriptions concise (RULE_25/26 — these live in the stable prompt prefix).

### 3.5 `backend/ai/domain/emissions.py` — fix `system_prompt_extension`

Replace the wrong unit and add grounding instruction:

- Change `"Emission factors are in tCO₂e per unit activity. "` →
  `"Emission factors are stored in kg CO₂e per unit activity (e.g., 0.4584 kg CO₂e/kWh). "`
- Append a unit-hierarchy + grounding line:
  `"Unit hierarchy: factors (kg CO₂e per activity unit) → calculations (kg CO₂e) → `
  `dashboard/report totals (tonnes CO₂e = kg ÷ 1000). To answer any question about factors, `
  `calculations, or totals, call the host API to read live data — never state a factor value from memory."`

### 3.6 `backend/ai/engine/llm/prompt_synthesizer.py` — kill the phantom tool

- Line **89**: remove `vs `query_host_db` (for analytical queries)` — consolidate to
  `call_host_api` + `search_knowledge` only.
- Line **347** (`- Use `query_host_db` for analytical queries`): delete the line.

---

## 4. Verification gate (regression tests — RULE_11)

New file `backend/ai/tests/test_emissions_grounding.py` (pytest, `--reuse-db`). Seed before
assert (CB-08 pattern). Minimum:

1. **`test_factors_in_process_returns_seeded_factor`** — create user + an active `EmissionFactor`
   (`code='EG_GRID_2024'`, `factor_value=Decimal('0.4584')`, `activity_unit='kWh'`); instantiate
   `CarbonHostExecutor(host_user_id=user.id)` (verify the real constructor arg); call
   `_emission_factors_in_process`; assert a result with `code == 'EG_GRID_2024'` and
   `factor_value == 0.4584`.
2. **`test_chairman_overview_returns_footprint`** — seed a `Calculation` + `ReportingPeriod`;
   call `_chairman_overview_in_process`; assert `data['headline']['footprint_tonnes']` is present
   (a number, not error).
3. **`test_summary_is_org_scoped`** *(recommended, adapt fixtures)* — a second user with no module
   visibility gets `total_calculations == 0` while the scoped user sees `>= 1`.

Run: `cd /home/ahmed/aast/carbon && source .venv/bin/activate && cd backend && python manage.py test ai.tests.test_emissions_grounding -v2` (or pytest with `--reuse-db`).

---

## 5. Definition of Done

- [ ] 5 catalog entries + 5 `_IN_PROCESS_ENDPOINTS` keys + 5 handler coroutines, all read-only.
- [ ] `CalculationSummaryService` extracted; view delegates (no logic drift).
- [ ] `system_prompt_extension` unit fixed + hierarchy + "read live data" instruction.
- [ ] Phantom `query_host_db` removed from both prompt_synthesizer lines.
- [ ] 2 mandatory regression tests pass (factors + chairman); org-scope test if feasible.
- [ ] No mutation endpoints added (RULE_21); `InventorySourceStatusViewSet` bug logged, not fixed.
