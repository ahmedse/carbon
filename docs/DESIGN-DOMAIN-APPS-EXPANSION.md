# DESIGN — Domain Apps Expansion Strategy

**Status:** Audit complete — Readiness assessment + recommendations
**Author:** Master Architect
**Date:** 2026-08-22
**Audience:** Backend Worker, Frontend Worker, QA Validator, Product Designer
**Purpose:** Answer "can we build HR/ERP-BI, academic/KPI, facility, sustainability, and Healthy AI apps on Carbon?"

---

## Executive Summary

**Verdict:** Carbon is a domain-app factory. The machinery (`appregistry/`, `ai/domain_protocol.py`, CBAC, Dataset Hub, TurnKey Bridge) is real and shipped. You can build new apps by cloning the `healthy/` pattern.

**The one gap:** The data storage layer (`dataschema.DataRow.values = JSONField()`) is optimized for governed, audited, DQ-scored trust operations — not for analytical/BI workloads (ERP aggregations, KPI dashboards, cross-org analytics). For moderate-scale tabular data (thousands to low tens-of-thousands of rows) it's fine. For ERP-BI scale (millions of rows, `SUM/GROUP BY` over JSON), it will be slow without tuning.

**Recommended sequence:**
1. ✅ **Healthy AI app** — already built, just extend (more pipelines/models)
2. ✅ **Facility management + Academic portfolio** — new apps, clean fit (asset CRUD, document artifacts)
3. ⚠️ **Sustainability goals** — extend `emissions/`, don't duplicate
4. 🔧 **HR/ERP-BI + KPI dashboards** — build *after* deciding the analytics layer (Option A or B below)

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

### 1.8 Data Storage — The Honest Assessment

**Current model:**
```python
# dataschema/models.py
class DataRow(models.Model):
    data_table = ForeignKey(DataTable, …)
    values = JSONField()  # one JSON document per row
    created_at, updated_at, is_archived, version
    dq_flags = JSONField(default=list)
```

**Every row is a JSON document.** No GIN index on `values`. No columnar store. No materialized views. No star schema.

**Infra:** One PostgreSQL 16 + Redis. Transactional, not analytical.

**What this is good for:**
- ✅ Governed, audited, DQ-scored trust operations
- ✅ Tabular data CRUD (create/read/update/delete rows)
- ✅ AI context assembly (pull row → feed to LLM)
- ✅ Moderate-scale reads (thousands to low tens-of-thousands of rows)
- ✅ Document/artifact storage

**What this is NOT good for:**
- ❌ ERP-BI workloads: `SELECT SUM(payroll) FROM rows WHERE org_unit IN (…) GROUP BY department` over millions of rows → full-table JSONB scan, slow
- ❌ KPI dashboards: cross-org aggregations, time-series rollups, drill-downs
- ❌ Real-time analytics on large fact tables

**Why PostgreSQL 16 itself is capable but the current layer isn't:**
- Postgres can do BI. The problem is the abstraction: row-as-JSON with no GIN indexes, no aggregate tables, no materialized views. It's a generic trust layer, not an analytical one.

**Verdict:** The storage model is *correct* for what Carbon is (data trust core). It will hit a wall for ERP-BI / KPI-heavy apps without tuning.

---

## 2. Your Four Proposed Apps — Readiness Assessment

### 2.1 HR / ERP Business Intelligence

**What you want:** HR module as part of ERP — headcount, attrition, payroll, attendance, leave, onboarding, workforce planning + BI dashboards (attrition by dept/college, payroll trends, performance KPIs).

**App machinery:** ✅ Ready
- `hr.py` domain manifest already exists (advisory/drafting)
- `appregistry/` can declare the app
- CBAC can scope `hr:view`, `hr:manage`

**Data layer:** ⚠️ **Gap**
- `hr.py` today is manifest-only (explicitly: "no tables in the trust platform")
- To be a real ERP-BI app, you need:
  - HR data models (`Employee`, `Department`, `PayrollRecord`, `Attendance`, `LeaveRequest`)
  - A `DataSource` to the ERP HR module (read-only)
  - Ingest path (ERP → DatasetVersion, like Healthy)
  - **BI read layer** (this is the blocker — see §3)

**Verdict:** ⚠️ Half-ready. App shell + AI seam exist. Data model + analytics layer are the gaps.

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

**Data layer:** ⚠️ **Gap**
- KPIs are aggregations over fact tables (`SUM`, `AVG`, `GROUP BY`, time-series rollups)
- MDM already has the org tree (`college` / `department` / `facility`)
- You need:
  - Fact tables (events, transactions, outcomes)
  - Aggregation layer (materialized views or dedicated OLAP store)
  - Drill-down queries (same BI gap as HR)

**Verdict:** ⚠️ Half-ready. Org tree + app shell exist. Aggregation layer is the blocker.

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

## 3. The Storage Layer Gap — Two Options

### Option A: Tuned PostgreSQL (recommended for moderate scale)

**Approach:** Stay on PostgreSQL 16, but tune the layer for analytics.

**What to add:**
1. **Domain-specific tables with real columns** (not JSON) for fact tables:
   ```python
   # hr/models.py
   class PayrollRecord(models.Model):
       employee = ForeignKey(Employee, …)
       org_unit = ForeignKey(OrgUnit, …)  # for GROUP BY
       period = DateField(db_index=True)
       gross_pay = DecimalField()
       net_pay = DecimalField()
       …
   ```
   
2. **GIN indexes on JSONB** where you must keep JSON:
   ```python
   class DataRow(models.Model):
       values = JSONField()
       
       class Meta:
           indexes = [
               GinIndex(fields=['values'], name='datarow_values_gin'),
           ]
   ```

3. **Materialized views for KPIs:**
   ```sql
   CREATE MATERIALIZED VIEW kpi_payroll_by_dept AS
   SELECT org_unit_id, period, SUM(gross_pay), AVG(gross_pay), COUNT(*)
   FROM hr_payrollrecord
   GROUP BY org_unit_id, period;
   
   CREATE INDEX ON kpi_payroll_by_dept (org_unit_id, period);
   ```
   
   Refresh: `REFRESH MATERIALIZED VIEW CONCURRENTLY kpi_payroll_by_dept;` (scheduled job).

4. **Aggregate tables:**
   ```python
   class KPISnapshot(models.Model):
       metric_key = CharField()  # e.g. "payroll_by_dept"
       org_unit = ForeignKey(OrgUnit, …)
       period = DateField(db_index=True)
       value = DecimalField()
       metadata = JSONField()
   ```

**Pros:**
- No new infra
- PostgreSQL 16 can handle moderate-scale BI (millions of rows with proper indexing)
- Keep all data in one place (trust + analytics)

**Cons:**
- Need to write + maintain materialized view refresh jobs
- Still have to be careful about query patterns (avoid full JSONB scans)
- Won't scale to "true big data" (tens of millions of rows, real-time sub-second queries)

**When this works:**
- Org size: < 10,000 employees
- Fact tables: < 10M rows
- Query patterns: pre-aggregated dashboards, not ad-hoc drill-anywhere OLAP
- Update frequency: hourly/daily refreshes acceptable (not real-time)

**Verdict:** ✅ Recommended for AASTMT (one campus, ~5K staff, moderate data volume).

---

### Option B: Dedicated Analytical Store (for larger scale or real-time)

**Approach:** Keep Carbon as the trust core (governed, DQ-scored, audited). Add a separate analytical tier for BI/KPIs.

**Patterns:**
1. **DuckDB in-process** (for single-node BI queries):
   - Export DatasetVersion → Parquet
   - Query Parquet with DuckDB (columnar, fast)
   - Refresh: rebuild Parquet on version approval

2. **ClickHouse / TimescaleDB** (for distributed BI):
   - Push approved DatasetVersion → ClickHouse
   - Run BI queries there
   - Keep Carbon as source-of-truth; ClickHouse is read-replica

3. **Materialized views in a read-replica Postgres:**
   - Stand up a read-only Postgres replica
   - Build MVs there (keep the primary clean)

**Pros:**
- Scales to tens/hundreds of millions of rows
- Real-time or near-real-time analytics
- Dedicated infra = no risk of slowing down the trust core

**Cons:**
- New infra to maintain
- Data duplication (sync lag, consistency concerns)
- More complexity

**When you need this:**
- Org size: > 10,000 employees
- Fact tables: > 10M rows
- Query patterns: ad-hoc drill-anywhere OLAP, real-time dashboards
- Update frequency: real-time or sub-minute

**Verdict:** ⚠️ Overkill for AASTMT today. Consider only if Option A proves insufficient after 1 year.

---

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

### Phase 3 (6 months): Analytics layer decision + HR/KPI

5. 🔧 **Decide analytics layer:** Run a 1-week proof-of-concept for Option A (tuned Postgres). Build one KPI dashboard (e.g. headcount by dept/college over 12 months) on top of the existing `mdm.OrgUnit` tree + synthetic payroll data.
   - If query latency < 1s and refresh jobs are stable → commit to Option A.
   - If it's slow or brittle → evaluate Option B (dedicated store).

6. 🔧 **HR/ERP-BI app:**
   - Build HR data models (`Employee`, `PayrollRecord`, `Attendance`, …)
   - Ingest from ERP HR module (clone Healthy's `ERPSnapshotService`)
   - Build BI layer (MVs + aggregate tables, Option A)
   - Domain AI manifest (`hr.py` already exists, extend with task types)
   - Frontend (dashboards, drill-downs)

7. 🔧 **KPI dashboards (staff/dept/college):**
   - Reuse the BI layer from HR
   - Models: `KPIDefinition`, `KPISnapshot`, `KPITarget`
   - Dashboards: performance, attrition, productivity, research output
   - Drill-downs by org unit (reuse `mdm.OrgUnit`)

**Effort:** 4 sprints (PoC + HR + KPI).

**Blocker:** Analytics layer decision (Phase 3 gate 5).

---

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

**The one gap is the analytics layer.** For apps that are primarily CRUD/documents (facility, portfolio), you're good to go. For apps that are BI-heavy (HR/ERP, KPI dashboards), you need to decide: tuned Postgres (Option A, recommended) or dedicated store (Option B, overkill for AASTMT today).

**Recommended sequence:**
1. Healthy (extend) → Facility + Portfolio (new) → Sustainability (extend `emissions/`)
2. After those 4, run a 1-week PoC on the analytics layer
3. Then tackle HR/ERP-BI + KPI

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
