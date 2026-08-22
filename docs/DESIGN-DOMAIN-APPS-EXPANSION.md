# DESIGN — Domain Apps Expansion Strategy

**Status:** Audit complete — Readiness assessment + recommendations
**Author:** Master Architect
**Date:** 2026-08-22
**Audience:** Backend Worker, Frontend Worker, QA Validator, Product Designer
**Purpose:** Answer "can we build HR/ERP-BI, academic/KPI, facility, sustainability, and Healthy AI apps on Carbon?"

---

## Executive Summary

**Verdict:** Carbon is a domain-app factory. The machinery (`appregistry/`, `ai/domain_protocol.py`, CBAC, Dataset Hub, TurnKey Bridge) is real and shipped. You can build new apps by cloning the `healthy/` pattern.

**The one gap:** It is **not** a missing analytical store. Carbon uses a deliberate two-layer model:
- **Trust layer** — `dataschema.DataRow.values = JSONField()`: governed, audited, DQ-scored raw snapshots (row-as-document).
- **BI layer** — typed relational domain models with real columns/FKs/indexes, e.g. `healthy.RepHealthCard.churn_probability = FloatField`.

**"Materialize"** = extract rows from the JSON trust layer → write typed Django models. `healthy/` already does this end-to-end. The real gap is that `hr.py` and the KPI apps have **no typed models yet** — not that Postgres can't do BI. At AASTMT scale (~5K staff, <10M fact rows), tuned Postgres 16 (typed tables + GIN + materialized views) is sufficient; no ClickHouse/DuckDB needed.

**Recommended sequence:**
1. ✅ **Healthy AI app** — already built, just extend (more pipelines/models)
2. ✅ **Facility management + Academic portfolio** — new apps, clean fit (asset CRUD, document artifacts)
3. ⚠️ **Sustainability goals** — extend `emissions/`, don't duplicate
4. 🔧 **HR/ERP-BI + KPI dashboards** — write typed models + materialize (clone `healthy/`); no new store required

---

## 1. Platform Readiness Audit — What's Real Today

### 1.1 App Registry (`appregistry/`)

**Models:** `AppManifest` (name, slug, version, entry_route, required_modules, required_capabilities, consumed_datasets, is_system, is_active) + `AppActivation`.

**Purpose:** Declares which apps exist, what they need, whether they're active. One deployment = one org (AASTMT), no multi-tenancy.

**Status:** ✅ Shipped. Tested. `healthy/` uses it.

**API:** `GET /carbon-api/apps/`, `POST /carbon-api/apps/{slug}/activate|deactivate`.

---

### 1.2 Domain Protocol (`ai/domain_protocol.py` + `ai/domain/`)

**Pattern:** `DomainAIOperations` ABC with:
- `app_identifier` + `app_display_name`
- `supported_task_types` (chat, nl_query, dq_validate, anomaly, report_draft, …)
- `entry_points` (buttons on domain pages: `{label, task_type, on_entity, icon}`)
- `starter_prompts` (context-aware chips: `{label, prompt, task_type}`)
- `system_prompt_extension` (domain vocabulary injected into T0)
- `validate_task_payload()` (fail-fast on malformed requests)
- `get_domain_context()` (knowledge/config enrichment)

**Shipped domains:**
- ✅ `emissions` (carbon footprint — tables + AI)
- ✅ `water` (water management — tables + AI)
- ✅ `admin` (platform governance — AI manifest-only)
- ✅ `mdm` (master data — reference sets, dedup, AI)
- ✅ `data_product` (governed datasets — AI)
- ✅ **`hr`** (advisory/drafting only, **no tables** — manifest-only vertical)
- ✅ **`finance`** (advisory/drafting only — manifest-only vertical)
- ✅ `customer` (customer ops advisory — manifest-only vertical)

**Status:** ✅ Shipped. `register_builtin_domains()` loads on startup. Adding a new domain = write `ai/domain/yourapp.py`, import in `__init__.py`.

---

### 1.3 CBAC (Capability-Based Access Control)

**Core:** `accounts/capabilities.py` — `Capability` (key/domain/action/label/category), `ScopedRole` (user/group + module/org_unit), `has_capability()`, `has_any_capability()`, `has_all_capabilities()`.

**Examples:** `healthy:view`, `healthy:manage`, `datahub:ingest`, `datahub:approve`, `turnkey:manage`.

**Scoping:** Module-level (`ScopedRole(module=X)` grants access to all `Dataset(module=X)`) + optional per-dataset override (`DatasetAccessPolicy`).

**Status:** ✅ Shipped. Every endpoint checks `@permission_classes([HasCapability('domain:action')])`.

---

### 1.4 Dataset Hub (`catalog.Dataset` + `DatasetVersion`)

**Models:**
- `Dataset`: name, slug, module (CBAC anchor), owner, steward, classification, domain, `current_version` pointer, status, tags.
- `DatasetVersion`: dataset FK, version_number, `data_table` FK (→ `dataschema.DataTable`), row_count, schema_snapshot, health_score, health_detail, dq_job_id, lineage, status (pending/approved/rejected), approval metadata.
- `DataContract`: required_fields, min_completeness, min_validity, min_health_score, freshness_hours, consumer_apps.
- `DataContractViolation`: contract FK, dataset_version FK, violation_type (schema/quality/freshness), detail.

**Lifecycle:** ingest → DQ gate → health_score → pending → approve → set as `current_version`.

**Lineage:** `{"source": {"type": "erp_snapshot"/"csv_upload"/"api", "ref": "<id>"}, "upstream_version_ids": […], "transforms": […]}`.

**Status:** ✅ Shipped. Used by `healthy/` for all 5 pipelines.

---

### 1.5 TurnKey Bridge (`integrations/turnkey/`)

**Models:**
- `TurnKeyConfig`: base_url, api_key_encrypted (Fernet), is_active.
- `TurnKeyModelLink`: dataset_version FK, turnkey_model_id, turnkey_version_id, purpose (training/inference), status (pending/registered/promoted).
- `PredictionRecord`: model_link FK, input_data_row FK, input_hash, prediction, actual (feedback loop), feedback_submitted_at.
- `DriftAlert`: model_link FK, turnkey_alert_id, metric, value, threshold, severity, dq_job_triggered, received_at.

**Client:** `integrations/turnkey/client.py` — `CarbonTurnKeyClient` (register_or_get_model, push_version, promote_to_production, list_models, get_model_metrics). Django-free, testable standalone.

**Callbacks:** `POST /carbon-api/integrations/turnkey/callback/predictions/`, `POST .../callback/drift-alerts/` (HMAC-SHA256 signed).

**Status:** ✅ Shipped. `healthy/` uses it for all 5 pipelines (returns, churn, sales-lines, AR-aging, production-cost).

---

### 1.6 Healthy Reference App (`healthy/`)

**Models:**
- `ERPSnapshot`: source_view, extract_params, row_count, dataset_version_id, data_source FK, status (running/done/failed), triggered_by.
- `LoadoutSheet`: week_start, rep_code, rep_name, prediction_ref, line_items (JSON).
- `RepHealthCard`: week_start, rep_code, churn_probability, active_customer_count, visit_coverage, avg_order_value, ar_overdue_amount.

**Services:**
- `ERPSnapshotService`: `extract_rows()`, `run_snapshot()` (ERP → DataTable → DatasetVersion).
- `HealthyPipelineService`: `run_pipeline()` (snapshot → DQ → TurnKey → predictions).
- `LoadoutService`: `generate_sheet()`, `submit_actuals()`.
- `DashboardService`: `summary()`, `ar_queue()`, `slow_movers()`.

**Pipelines (5):** returns, churn, sales-lines, ar-aging, production-cost.

**Domain AI:** `healthy/domain_ai.py` → `HealthyDomainAI(DomainAIOperations)` with manifest (task types, entry points, starter prompts, system prompt extension, default model).

**Status:** ✅ Shipped. Complete reference implementation. Any new app clones this pattern.

---

### 1.7 MDM (`mdm.OrgUnit`)

**Model:** `OrgUnit` (name, code, org_type, parent FK, level, path, is_active).

**Org types:** `university`, `college`, `department`, `division`, `team`, `facility`.

**Status:** ✅ Shipped. The academic hierarchy (`college` / `department` / `facility`) is already modeled.

---

### 1.8 Data Storage — Two Layers (Trust + BI), Not One Gap

Carbon is deliberately **two-layered**:

**Layer 1 — Trust (`dataschema.DataRow`)**
```python
# dataschema/models.py
class DataRow(models.Model):
    data_table = ForeignKey(DataTable, …)
    values = JSONField()  # one JSON document per row — raw, governed, audited
    created_at, updated_at, is_archived, version
    dq_flags = JSONField(default=list)
```

This is the *source of truth*: immutable row-as-document snapshots, DQ-scored, lineage-tracked, audit-friendly. It is **not** where you run BI queries.

**Layer 2 — BI (typed domain models, materialized from Layer 1)**

`healthy/` already demonstrates the pattern: `ERPSnapshotService` extracts rows from Layer 1 and writes **typed models with real columns, FKs, and indexes**:

```python
# healthy/models.py — materialized, queryable BI outputs
class RepHealthCard(models.Model):
    week_start = DateField(db_index=True)
    rep_code = CharField(db_index=True)
    churn_probability = FloatField()      # a real column, not a JSON key
    ar_overdue_amount = DecimalField()    # SUM/GROUP BY-friendly
```

**"Materialize"** = `extract JSON rows → transform → write typed Django models`. This is exactly how ERP-BI, KPI, and payroll aggregations should be built — and it is already shipped in `healthy/`.

**Infra:** One PostgreSQL 16 + Redis. Typed tables + GIN indexes + materialized views cover AASTMT scale.

**What Layer 1 (trust) is for:**
- ✅ Governed, audited, DQ-scored trust operations
- ✅ Tabular data CRUD + AI context assembly
- ✅ Immutable provenance + lineage

**What Layer 2 (typed models) is for:**
- ✅ ERP-BI aggregations (`SUM`/`GROUP BY` over real, indexed columns)
- ✅ KPI dashboards, time-series rollups, drill-downs
- ✅ Materialized views refreshed on schedule

**The actual gap (small):**
- ❌ `hr.py` is manifest-only — it has **zero typed models**. That's the gap, not a missing store.
- ❌ KPI apps need typed fact models + materialized views — a build step, not an infra decision.

**Verdict:** No new analytical store. Build typed models and materialize them from the trust layer — `healthy/` is the blueprint. Revisit only if fact tables exceed ~10M rows with sub-second ad-hoc OLAP requirements.

## 2. Your Four Proposed Apps — Readiness Assessment

### 2.1 HR / ERP Business Intelligence

**What you want:** HR module as part of ERP — headcount, attrition, payroll, attendance, leave, onboarding, workforce planning + BI dashboards (attrition by dept/college, payroll trends, performance KPIs).

**App machinery:** ✅ Ready
- `hr.py` domain manifest already exists (advisory/drafting)
- `appregistry/` can declare the app
- CBAC can scope `hr:view`, `hr:manage`

**Data layer:** ⚠️ **Gap (small)**
- `hr.py` today is manifest-only (explicitly: "no tables in the trust platform")
- To be a real ERP-BI app, clone `healthy/`:
  - HR typed models (`Employee`, `Department`, `PayrollRecord`, `Attendance`, `LeaveRequest`)
  - A `DataSource` to the ERP HR module (read-only)
  - Ingest path (ERP → `DataRow` trust layer → materialize typed models)
  - Materialized views for payroll/attrition rollups

**Verdict:** ⚠️ Half-ready. App shell + AI seam exist. Typed models + materialization are the remaining build step — no new store needed.

---

### 2.2 Academic Portfolio (staff)

**What you want:** Per-staff portfolio — publications, grants, courses taught, supervision, service, achievements.

**App machinery:** ✅ Ready

**Data layer:** ✅ Ready
- Portfolios are documents/artifacts (PDF, markdown, metadata)
- Storage model handles this well (not analytical)
- Module: `academic-portfolio`
- Models: `StaffMember`, `Publication`, `Grant`, `Course`, `Supervision`, `ServiceRecord`
- `DataTable` + `DataRow` can store these (each portfolio item = one row)

**Verdict:** ✅ Clean fit. Clone `healthy/` pattern, write models, done.

---

### 2.3 KPI for staff / depts / colleges

**What you want:** KPI dashboards — performance metrics, targets, trends, drill-downs by org unit.

**App machinery:** ✅ Ready

**Data layer:** ⚠️ **Gap (small)**
- KPIs are aggregations over fact tables (`SUM`, `AVG`, `GROUP BY`, time-series rollups)
- MDM already has the org tree (`college` / `department` / `facility`)
- You need typed fact models + materialized views (tuned Postgres), e.g.:
  - Fact tables (`KpiFact`, `Event`, `Transaction`) with real columns
  - `REFRESH MATERIALIZED VIEW CONCURRENTLY` jobs for rollups
  - Drill-down queries over `mdm.OrgUnit` FKs

**Verdict:** ⚠️ Half-ready. Org tree + app shell exist. Typed fact models + MVs are the remaining build step — no dedicated OLAP store needed at AASTMT scale.

---

### 2.4 Facility Management (servers, devices, labs)

**What you want:** Asset register — servers, devices, lab equipment, bookings, maintenance, location tracking.

**App machinery:** ✅ Ready

**Data layer:** ✅ Ready
- Asset CRUD + simple reports (not heavy analytics)
- Storage model handles this well
- Module: `facility-management`
- Models: `Asset` (type, location, status, owner), `Device`, `Lab`, `Booking`, `MaintenanceLog`
- `DataTable` + `DataRow` can store these
- MDM already has `facility` org type

**Verdict:** ✅ Clean fit. Clone `healthy/` pattern, write models, done.

---

### 2.5 Sustainability Goals Manager

**What you want:** Track sustainability targets, emissions reductions, renewable energy %, waste reduction.

**App machinery:** ✅ Ready

**Data layer:** ✅ **Already exists** — this is `emissions/`!

**Verdict:** ✅ Don't build a new app. Extend `emissions/`. It already has:
- Scopes 1/2/3
- Emission factors
- Targets
- Calculations
- Dashboards

Add "sustainability goals" as a new section within `emissions/` (targets, milestones, reporting). Don't duplicate.

---

### 2.6 Healthy AI App (TurnKey backend + extracted data)

**What you want:** AI-driven sales and operations intelligence for Healthy Foods Factory — use TurnKey for ML, extract data from Healthy ERP.

**App machinery:** ✅ Ready

**Data layer:** ✅ Ready

**TurnKey integration:** ✅ Ready

**Status:** ✅ **Already built and shipped.** This is the reference app (`healthy/`). It does exactly what you describe:
- 5 pipelines (returns, churn, sales-lines, AR-aging, production-cost)
- ERP snapshot from Azure PostgreSQL (read-only)
- DQ-gated DatasetVersion
- TurnKey model push/promote
- Predictions → load-out sheets + rep health cards
- Dashboards (AR queue, slow-movers)

**Work remaining:** Extend (more pipelines/models), not build from scratch.

---

## 3. The Real Work — Materialize Typed Models (No New Store)

There is no "analytics layer decision" to make. Carbon already has the answer in
`healthy/`: **extract JSON from the trust layer → write typed Django models with
real columns, FKs, and indexes.** Materialized views and GIN indexes make tuned
PostgreSQL 16 sufficient for AASTMT's scale.

### 3.1 The pattern (already shipped in `healthy/`)

1. **Typed fact/dimension models** with real columns (not JSON):
   ```python
   # hr/models.py
   class PayrollRecord(models.Model):
       employee = ForeignKey(Employee, on_delete=…)
       org_unit = ForeignKey(OrgUnit, on_delete=…)   # for GROUP BY / drill-down
       period = DateField(db_index=True)
       gross_pay = DecimalField(max_digits=12, decimal_places=2)
       net_pay = DecimalField(max_digits=12, decimal_places=2)
   ```

2. **GIN index on the trust layer** where JSON must be queried:
   ```python
   class DataRow(models.Model):
       values = JSONField()
       class Meta:
           indexes = [GinIndex(fields=['values'], name='datarow_values_gin')]
   ```

3. **Materialized views** for KPI rollups:
   ```sql
   CREATE MATERIALIZED VIEW kpi_payroll_by_dept AS
   SELECT org_unit_id, period, SUM(gross_pay), AVG(gross_pay), COUNT(*)
   FROM hr_payrollrecord
   GROUP BY org_unit_id, period;

   CREATE INDEX ON kpi_payroll_by_dept (org_unit_id, period);
   ```
   Refresh: `REFRESH MATERIALIZED VIEW CONCURRENTLY kpi_payroll_by_dept;` (scheduled job).

4. **Aggregate snapshot tables** for a versioned, queryable summary:
   ```python
   class KPISnapshot(models.Model):
       metric_key = CharField()          # e.g. "payroll_by_dept"
       org_unit = ForeignKey(OrgUnit, on_delete=…)
       period = DateField(db_index=True)
       value = DecimalField(max_digits=18, decimal_places=4)
       metadata = JSONField()
   ```

### 3.2 Scale guidance

| Condition | What to do |
|-----------|-----------|
| ≤ ~5K staff, ≤ 10M fact rows (AASTMT today) | Typed models + GIN + materialized views on the **existing** Postgres 16. Done. |
| > 10M rows or sub-second ad-hoc OLAP | Revisit later (DuckDB/ClickHouse read-replica). **Not now.** |

**Bottom line:** "Materialize" is a code task (write `models.py` + an extract/transform
service), not an infrastructure decision. Clone `healthy/ERPSnapshotService` +
`RepHealthCard` and you're done.

## 4. Concrete Recommendations — Sequencing

### Phase 1 (now): Low-hanging fruit

1. ✅ **Healthy AI** — extend (add more pipelines/models). Already built.
2. ✅ **Facility Management** — new app, clone `healthy/`. Clean fit.
3. ✅ **Academic Portfolio** — new app, clone `healthy/`. Clean fit.

**Effort:** 2 sprints per new app (models + ingest + domain AI + frontend).

**No blockers.**

---

### Phase 2 (3 months): Sustainability

4. ✅ **Sustainability Goals** — extend `emissions/` (don't build new app). Add targets/milestones/reporting UI.

**Effort:** 1 sprint (backend) + 1 sprint (frontend).

**No blockers.**

---

### Phase 3 (6 months): Materialize HR + KPI

5. 🔧 **HR/ERP-BI app:**
   - Build HR typed models (`Employee`, `PayrollRecord`, `Attendance`, …)
   - Ingest from ERP HR module (clone Healthy's `ERPSnapshotService`)
   - Materialize: extract trust-layer rows → typed models + MVs (see §3)
   - Domain AI manifest (`hr.py` already exists, extend with task types)
   - Frontend (dashboards, drill-downs)

6. 🔧 **KPI dashboards (staff/dept/college):**
   - Reuse the typed models + MVs from HR
   - Models: `KPIDefinition`, `KPISnapshot`, `KPITarget`
   - Dashboards: performance, attrition, productivity, research output
   - Drill-downs by org unit (reuse `mdm.OrgUnit`)

**Effort:** 4 sprints (HR + KPI).

**No blocker** — materialization is a normal build step, not a gated decision.

## 5. The Domain-App Checklist (Clone `healthy/`)

When building a new app, follow this pattern (all from `healthy/`):

### Backend
1. **App directory:** `backend/{yourapp}/`
2. **Models:** `models.py` (domain entities + artifacts)
3. **Services:** `services.py` (ingest, pipeline orchestration, dashboards)
4. **Domain AI:** `domain_ai.py` (manifest: `DomainAIOperations` subclass)
5. **Register:** Add to `ai/domain/__init__.py` → `register_builtin_domains()`
6. **Manifest:** Management command `register_{yourapp}_app.py` → creates `AppManifest` + `AppActivation`
7. **Migrations:** `python manage.py makemigrations {yourapp}`
8. **Tests:** `tests/` (20+ tests minimum)
9. **URLs:** `urls.py` → register in `config/urls.py`
10. **Serializers:** `serializers.py` (DRF)
11. **Views:** `views.py` (DRF ViewSets)
12. **Capabilities:** Add to `accounts/capabilities.py` (e.g. `{yourapp}:view`, `{yourapp}:manage`)

### Frontend
1. **App directory:** `carbon-frontend/src/pages/{yourapp}/`
2. **Routes:** Add to `src/App.jsx` router
3. **API client:** `src/api/{yourapp}.js`
4. **Pages:** Dashboard, list, detail, CRUD
5. **Menu:** Add entry to `src/shell/Navigation.jsx`

### Infra
1. **Module(s):** Create in `core.Module` via migration or admin
2. **DataSource:** If external (ERP/API), create in `connections.DataSource`
3. **Dataset(s):** Create in `catalog.Dataset` with module FK

**Time estimate:** 2 sprints (backend + frontend + tests).

---

## 6. Conclusion

**Yes, Carbon is ready for new domain apps.** The machinery is real, tested, and shipped. `healthy/` is the blueprint.

**There is no missing analytics store.** For apps that are primarily CRUD/documents (facility, portfolio), you're good to go. For BI-heavy apps (HR/ERP, KPI dashboards), the work is to **materialize typed models** from the trust layer — exactly what `healthy/` already does with `RepHealthCard`. Tuned Postgres 16 (typed tables + GIN + materialized views) is sufficient at AASTMT scale.

**Recommended sequence:**
1. Healthy (extend) → Facility + Portfolio (new) → Sustainability (extend `emissions/`)
2. Then materialize HR/ERP-BI + KPI (typed models + MVs)

**Next step:** Pick one app to build first (recommend: Facility Management, cleanest fit) and I'll write the full implementation spec with models, services, API surface, and frontend scaffold.

---

## References

- `backend/appregistry/models.py` — App Registry
- `backend/ai/domain_protocol.py` + `backend/ai/domain/` — Domain AI seams
- `backend/healthy/` — Reference app (complete implementation)
- `backend/integrations/turnkey/` — TurnKey Bridge
- `backend/catalog/models.py` — Dataset/DatasetVersion
- `backend/dataschema/models.py` — DataTable/DataRow (storage model)
- `backend/mdm/models.py` — OrgUnit (academic hierarchy)
- `backend/accounts/capabilities.py` — CBAC
- `docs/DESIGN-PLATFORM.md` — Platform architecture
- `docs/DESIGN-AGENT-CATALOG.md` — Agent catalog + domain protocol
- `.ai-toolkit/decisions/0010-domain-app-ai-contract.md` — Domain AI contract (if exists)
