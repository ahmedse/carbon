# Pulse for Carbon — Integration Architecture & Implementation Plan

> **Created:** 2026-07-18  
> **Status:** Approved Architecture  
> **Pattern:** Identical to Gigacast+Pulse integration (standalone semantic agent)

---

## 1. Executive Summary

Integrate **Pulse** (standalone AI semantic agent) with **Carbon** (Data Trust Platform) following the exact same pattern as Gigacast+Pulse:

- **Pulse runs as a separate FastAPI service** (port 9200) — never embedded in Carbon backend
- **Carbon backend remains unchanged** — Django + DRF continues as-is
- **Read-only database access** — Pulse introspects Carbon's PostgreSQL schema
- **API integration** — Pulse calls Carbon REST APIs for actions (with user confirmation)
- **Widget embedding** — Carbon frontend embeds Pulse chat widget
- **Instance-based configuration** — `instances/carbon/instance.yaml` defines domain knowledge

**Architecture Principle:** Pulse is a **peer system** that understands and assists with Carbon, not a module within Carbon.

---

## 2. Current State Analysis

### 2.1 Carbon Platform (Host System)

**Technology Stack:**
- Backend: Django 4.x + DRF + PostgreSQL
- Frontend: React (Vite) + Material UI
- Auth: JWT (simplejwt)
- Port: 8009 (backend API), 5173 (frontend dev), 8001 (production)
- API Prefix: `/api/v1/` (configurable via `DJANGO_API_PREFIX`)

**Domain:** Carbon accounting & sustainability data management for AASTMT university
- Multi-tenant via OrgUnit tree (university → campus → college → department)
- Org-scoped RBAC (admins, dataowners, auditors)
- GHG emissions calculation (Scope 1/2/3)
- Data Trust core: Catalog, MDM, Data Quality, DataSchema engine

**Key Django Apps:**
- `accounts` — User, ScopedRole, RBAC
- `core` — Module (data collection areas), Project, Cycle
- `dataschema` — DataTable, DataField, DataRow (metadata-driven schema)
- `emissions` — Calculation, EmissionFactor, ReportingPeriod
- `catalog` — AssetProfile, GlossaryTerm, DataDomain
- `mdm` — OrgUnit (tree), ReferenceSet, ReferenceValue
- `dq` — FieldProfile, TableProfile, DQRule, DQResult
- `ai_copilot` — **FROZEN 2026-07-18** (superseded by external Pulse)

**Database Schema:**
- ~40+ tables across 8 apps
- Org-scoped data via `Module.org_unit` FK → `mdm.OrgUnit`
- Calculations link to modules: `Calculation.module` → `Module` → `OrgUnit`

**API Endpoints (selected):**
- `/api/v1/token/` — JWT auth
- `/api/v1/accounts/users/` — User management
- `/api/v1/core/modules/` — Module list (org-scoped)
- `/api/v1/dataschema/tables/`, `/fields/`, `/rows/` — Schema & data CRUD
- `/api/v1/emissions/calculations/`, `/factors/`, `/dashboard/` — Emissions
- `/api/v1/catalog/profiles/`, `/glossary/` — Catalog
- `/api/v1/mdm/org-units/`, `/reference-sets/` — Master data
- `/api/v1/dq/profiles/`, `/rules/` — Data quality

**Frontend:**
- Vite + React + Material UI
- Routes: `/`, `/data-entry`, `/emissions`, `/catalog`, `/admin/org-units`, `/admin/users`
- Auth: `AuthContext` with JWT
- Org-aware: `user.org_context` (allowed modules, org units)

### 2.2 Pulse System (Semantic Agent)

**Technology Stack:**
- Backend: FastAPI + SQLAlchemy 2.0 + SQLite (Pulse's own DB)
- Vector Store: ChromaDB (embedded, file-based)
- LLM: OpenAI-compatible (Poe API, Claude-Sonnet-4)
- Port: 9100 (Gigacast), **9200 (Carbon)**
- Widget: React (Vite, built as IIFE bundle `pulse.js`)

**Architecture Modules:**
- `core/` — Config, database, models, exceptions
- `knowledge/` — Schema introspection, semantic enrichment, knowledge store
- `memory/` — Short-term (conversation), long-term (facts), episodic (events)
- `agent/` — Reasoning, tools, planning, execution
- `llm/` — Provider abstraction, prompts, embeddings
- `api/` — FastAPI routers (chat, admin, health, widget)
- `cognition/` — Background monitoring loop (health checks, alerts)
- `instances/{instance_name}/` — Per-host configuration (YAML)

**Integration Pattern (Gigacast proven):**
1. **Schema introspection:** Pulse connects to host DB read-only, queries `information_schema`
2. **Semantic enrichment:** LLM generates business descriptions for tables/columns
3. **Knowledge store:** Entities stored in SQLite + ChromaDB for semantic search
4. **Chat widget:** Embedded in host frontend, communicates via WebSocket
5. **Tool execution:** Agent can query DB (SELECT only), search knowledge, call host APIs
6. **Cognition loop:** Periodic health checks, data freshness monitoring, proactive alerts

---

## 3. Integration Architecture

### 3.1 Deployment Topology

```
┌────────────────────────────────────────────────────────────┐
│  CARBON FRONTEND (React, port 5173 dev / 8001 prod)       │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  <script src="http://localhost:9200/widget/pulse.js"│  │
│  │          data-instance="carbon"></script>            │  │
│  │                                                       │  │
│  │  Pulse Widget (floating button + drawer)             │  │
│  │  ├─ Reads window.location.pathname (page context)    │  │
│  │  ├─ WebSocket → ws://localhost:9200/ws/chat/carbon   │  │
│  │  └─ User auth: Carbon JWT passed to Pulse            │  │
│  └─────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
                             │ WebSocket
                             ▼
┌────────────────────────────────────────────────────────────┐
│  PULSE SERVICE (FastAPI, port 9200)                        │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  API Layer                                            │ │
│  │  ├─ /ws/chat/carbon — WebSocket chat                 │ │
│  │  ├─ /chat/carbon — REST chat                         │ │
│  │  ├─ /admin/instances — Instance management           │ │
│  │  ├─ /admin/instances/carbon/introspect — Trigger     │ │
│  │  └─ /widget/pulse.js — Widget bundle                 │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐ │
│  │Knowledge │ │ Memory   │ │ Agent    │ │ Cognition    │ │
│  │ Store    │ │ Manager  │ │ Reasoning│ │ Loop         │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘ │
│                                                             │
│  SQLite (pulse.db) + ChromaDB (vectors)                    │
└────────────────────────────────────────────────────────────┘
          │ READ-ONLY              │ HTTP (authenticated)
          ▼                        ▼
┌──────────────────────┐  ┌──────────────────────────────────┐
│  Carbon PostgreSQL   │  │  CARBON BACKEND (Django, 8009)   │
│  (schema introspect) │  │  ├─ /api/v1/token/ (JWT)         │
│                      │  │  ├─ /api/v1/core/modules/        │
│                      │  │  ├─ /api/v1/dataschema/tables/   │
│                      │  │  ├─ /api/v1/emissions/calcs/     │
│                      │  │  └─ /api/v1/catalog/profiles/    │
└──────────────────────┘  └──────────────────────────────────┘
```

### 3.2 Connection Details

| Component | Protocol | From | To | Purpose |
|---|---|---|---|---|
| **Schema Introspection** | PostgreSQL | Pulse | Carbon DB | Read-only, `information_schema` queries |
| **Data Queries** | PostgreSQL | Pulse | Carbon DB | SELECT only, timeout enforced |
| **API Calls** | HTTP REST | Pulse | Carbon API | Authenticated actions (with user confirmation) |
| **Widget Chat** | WebSocket | Carbon Frontend | Pulse API | Real-time chat, streaming responses |
| **Widget Bundle** | HTTP | Carbon Frontend | Pulse API | Serve `pulse.js` file |

### 3.3 Environment Configuration

**Pulse `.env` (new variables for Carbon instance):**
```env
# ── Pulse Core ──
PULSE_ENV=development
PULSE_PORT=9200
PULSE_SECRET_KEY=<generate-secret>
PULSE_DB_PATH=./data/pulse.db
PULSE_LOG_LEVEL=INFO

# ── Carbon Host System ──
HOST_DB_URL=postgresql://carbon_user:password@localhost:5432/carbon_db
HOST_DB_SCHEMA=public
HOST_DB_READ_ONLY=true
HOST_API_URL=http://127.0.0.1:8009/api/v1
HOST_API_TOKEN=<carbon-admin-jwt-token>

# ── LLM ──
LLM_API_KEY=<poe-api-key>
LLM_BASE_URL=https://api.poe.com/v1
LLM_MODEL=Claude-Sonnet-4
LLM_EMBEDDING_MODEL=text-embedding-3-small
LLM_COGNITION_MODEL=Claude-Haiku

# ── Cognition Loop ──
COGNITION_HEALTH_INTERVAL=3600
COGNITION_FRESHNESS_INTERVAL=21600
COGNITION_SNAPSHOT_INTERVAL=86400
COGNITION_ERROR_CHECK_INTERVAL=3600

# ── Embedding Store ──
CHROMA_PERSIST_DIR=./data/chroma

# ── CORS ──
CORS_ORIGINS=http://localhost:5173,http://localhost:8001,http://127.0.0.1:8009
```

**Carbon `.env` (no changes required):**
- Carbon backend continues using existing config
- No new environment variables needed
- Pulse integrates externally, not as Django app

### 3.4 Authentication & Authorization

**Approach:** Pulse operates as a **trusted admin agent** initially, then evolves to **user-context-aware**.

#### Phase 1: Admin Agent (MVP)
- Pulse uses a **long-lived admin JWT token** from Carbon (`HOST_API_TOKEN`)
- All API calls authenticated as global admin
- Widget users interact with Pulse, but Pulse sees full data (no user-level scoping yet)
- **Sufficient for:** Data exploration, diagnostics, schema understanding, dashboard Q&A

#### Phase 2: User-Context-Aware (Future)
- Carbon frontend passes **user's JWT** to Pulse widget on init
- Pulse validates JWT with Carbon's public key (or introspects `/api/v1/accounts/me/`)
- Pulse queries become **org-scoped** per user's `ScopedRole`
- Respects Carbon's RBAC: data-owner sees only their org's data, auditor sees read-only
- **Enables:** True multi-user deployment, steward-scoped assistance

**Implementation Note:** Phase 1 is identical to Gigacast pattern. Phase 2 requires Carbon frontend to pass `user.token` to widget.

---

## 4. Pulse Instance Configuration for Carbon

### 4.1 Instance YAML Structure

**File:** `pulse/instances/carbon/instance.yaml`

```yaml
# Carbon Instance Configuration
# Defines how Pulse connects to and understands the Carbon Data Trust Platform

name: carbon
display_name: Carbon Data Trust Platform
description: >
  Carbon accounting and sustainability data management platform for AASTMT.
  Manages GHG emissions tracking (Scope 1/2/3), org-scoped data collection,
  master data, data quality, and catalog governance. Built with Django + React.

domain: carbon_accounting_sustainability
timezone: Africa/Cairo
languages: [en, ar]

host:
  db_url: ${HOST_DB_URL}
  db_schema: ${HOST_DB_SCHEMA}
  api_url: ${HOST_API_URL}
  api_token: ${HOST_API_TOKEN}
  frontend_url: http://localhost:5173

# ── API Catalog ──
# Carbon REST API endpoints that Pulse can use
api_catalog:
  # --- Authentication ---
  - name: get_current_user
    method: GET
    path: /accounts/me/
    description: Get current authenticated user profile and org context
    requires_auth: true
    requires_confirmation: false

  # --- Modules & Organization ---
  - name: list_modules
    method: GET
    path: /core/modules/
    description: List all modules (data collection areas) with org unit association
    requires_auth: true
    requires_confirmation: false

  - name: list_org_units
    method: GET
    path: /mdm/org-units/
    description: List organizational units (AASTMT tree structure)
    requires_auth: true
    requires_confirmation: false

  # --- DataSchema (Metadata-Driven Data) ---
  - name: list_data_tables
    method: GET
    path: /dataschema/tables/
    description: List data tables with module association and field count
    requires_auth: true
    requires_confirmation: false

  - name: get_data_table
    method: GET
    path: /dataschema/tables/{id}/
    description: Get full table schema including all fields
    requires_auth: true
    requires_confirmation: false

  - name: list_data_fields
    method: GET
    path: /dataschema/fields/
    description: List fields for a specific data table with validation rules
    requires_auth: true
    requires_confirmation: false

  - name: list_data_rows
    method: GET
    path: /dataschema/rows/
    description: Retrieve data rows from a table with filtering by period, org
    requires_auth: true
    requires_confirmation: false

  # --- Emissions Calculations ---
  - name: list_calculations
    method: GET
    path: /emissions/calculations/
    description: List emission calculations with results, scope, and source data
    requires_auth: true
    requires_confirmation: false

  - name: get_emissions_dashboard
    method: GET
    path: /emissions/dashboard/
    description: Get emissions summary dashboard (by scope, period, org unit)
    requires_auth: true
    requires_confirmation: false

  - name: list_emission_factors
    method: GET
    path: /emissions/factors/
    description: List available emission factors with categories and scopes
    requires_auth: true
    requires_confirmation: false

  - name: list_reporting_periods
    method: GET
    path: /emissions/periods/
    description: List active reporting periods (monthly, quarterly, annual)
    requires_auth: true
    requires_confirmation: false

  # --- Catalog (Data Governance) ---
  - name: list_asset_profiles
    method: GET
    path: /catalog/profiles/
    description: List cataloged assets with descriptions, owners, and quality scores
    requires_auth: true
    requires_confirmation: false

  - name: list_glossary_terms
    method: GET
    path: /catalog/glossary/
    description: List business glossary terms and definitions
    requires_auth: true
    requires_confirmation: false

  - name: list_data_domains
    method: GET
    path: /catalog/domains/
    description: List data domains for classification
    requires_auth: true
    requires_confirmation: false

  # --- Master Data (MDM) ---
  - name: list_reference_sets
    method: GET
    path: /mdm/reference-sets/
    description: List reference data sets (e.g., emission scopes, org types)
    requires_auth: true
    requires_confirmation: false

  - name: get_reference_values
    method: GET
    path: /mdm/reference-sets/{id}/values/
    description: Get all values for a specific reference set
    requires_auth: true
    requires_confirmation: false

  # --- Data Quality ---
  - name: list_field_profiles
    method: GET
    path: /dq/profiles/
    description: List data quality profiles for fields (completeness, uniqueness)
    requires_auth: true
    requires_confirmation: false

  - name: list_dq_rules
    method: GET
    path: /dq/rules/
    description: List data quality rules and their definitions
    requires_auth: true
    requires_confirmation: false

  - name: list_dq_results
    method: GET
    path: /dq/results/
    description: List data quality rule execution results with pass/fail status
    requires_auth: true
    requires_confirmation: false

  # --- Users & Access Control ---
  - name: list_users
    method: GET
    path: /accounts/users/
    description: List users in the system (admin only)
    requires_auth: true
    requires_confirmation: false

  - name: list_scoped_roles
    method: GET
    path: /accounts/scoped-roles/
    description: List role assignments with org/module scopes
    requires_auth: true
    requires_confirmation: false

# ── Cognition Monitors ──
# What Pulse should watch for and alert on
cognition:
  monitors:
    - name: data_freshness
      description: Alert when data rows have not been updated recently
      check: last_row_timestamp
      max_age_hours: 168  # 1 week

    - name: calculation_errors
      description: Alert on failed emission calculations
      check: calculation_status
      look_back_hours: 24

    - name: data_quality_degradation
      description: Alert when DQ rule pass rate drops
      check: dq_pass_rate
      warning_threshold: 80.0
      critical_threshold: 60.0

    - name: incomplete_data_tables
      description: Alert on tables with low completeness
      check: table_completeness
      warning_threshold: 70.0
      critical_threshold: 50.0

    - name: missing_emission_factors
      description: Alert when calculations fail due to missing factors
      check: calculation_errors_missing_factor
      look_back_hours: 24

# ── Business Rules ──
# Domain-specific knowledge for Carbon accounting
business_rules:
  - "GHG Protocol defines three scopes: Scope 1 (direct emissions), Scope 2 (purchased energy), Scope 3 (value chain)"
  - "Calculations require: activity data (DataRow), emission factor, and reporting period"
  - "Emission Factor = kg CO2e per activity unit (e.g., kg CO2e per liter diesel)"
  - "Calculations are automatically scoped to the module's org unit for RBAC"
  - "Data quality checks run on completeness, uniqueness, range, and pattern validation"
  - "OrgUnit tree structure: AASTMT → Campus → College → Department"
  - "Reference data (emission factors, org units) is global; activity data is org-scoped"
  - "DataSchema engine stores schema as data (DataTable/DataField) for flexibility"
  - "Catalog AssetProfiles provide governance metadata (owner, description, quality)"
  - "Admins have global access; dataowners see only their org subtree; auditors read-only"

# ── Glossary ──
# Carbon domain terminology
glossary:
  GHG_Scope: "Classification of greenhouse gas emissions: Scope 1 (direct), Scope 2 (indirect energy), Scope 3 (value chain)"
  Emission_Factor: "Conversion factor that transforms activity data into CO2 equivalent emissions (e.g., kg CO2e per liter fuel)"
  Activity_Data: "Raw operational data that generates emissions (e.g., liters of diesel consumed, kWh electricity used)"
  Calculation: "A computed emission result = activity_data × emission_factor × GWP, stored with audit trail"
  Module: "A data collection area within a GHG scope (e.g., 'Transportation - Fleet' for Scope 1 diesel)"
  DataTable: "A metadata-driven table schema (part of DataSchema engine) containing activity data"
  DataRow: "A single data record in a DataTable, containing activity values as JSON"
  OrgUnit: "An organizational unit in the AASTMT tree (university, campus, college, department)"
  ScopedRole: "A role assignment (admin/dataowner/auditor) scoped to an org unit or module"
  AssetProfile: "Catalog metadata for a data asset (table or field) with owner, description, quality score"
  ReferenceSet: "Master data collection (e.g., list of emission scopes, org types, fuel types)"
  DQRule: "Data quality validation rule (completeness, range, pattern) applied to fields or tables"
  ReportingPeriod: "Time window for emissions reporting (monthly, quarterly, annual)"
  GWP: "Global Warming Potential — factor to convert non-CO2 gases to CO2 equivalent"
  DataSchema_Engine: "Metadata-driven schema management where table/field definitions are stored as data, not migrations"

# ── Navigation Map ──
# Maps concepts to Carbon frontend routes
navigation:
  dashboard: /
  data_entry: /data-entry
  emissions_dashboard: /emissions
  calculations: /emissions/calculations
  emission_factors: /emissions/factors
  catalog: /catalog
  glossary: /catalog/glossary
  data_quality: /dq
  org_units: /admin/org-units
  users: /admin/users
  access_control: /admin/access-control
  modules: /admin/modules
  settings: /settings
```

### 4.2 Schema Introspection Strategy

**Tables to Prioritize for Semantic Enrichment:**

| Priority | Tables | Reason |
|---|---|---|
| **High** | `core_module`, `dataschema_datatable`, `dataschema_datafield`, `dataschema_datarow` | Core data schema engine — most queries will involve these |
| **High** | `emissions_calculation`, `emissions_emissionfactor`, `emissions_reportingperiod` | Primary domain objects for emissions |
| **High** | `mdm_orgunit`, `mdm_referenceset`, `mdm_referencevalue` | Org structure and master data |
| **Medium** | `catalog_assetprofile`, `catalog_glossaryterm` | Governance metadata |
| **Medium** | `dq_fieldprofile`, `dq_tableprofile`, `dq_dqrule` | Data quality layer |
| **Medium** | `accounts_user`, `accounts_scopedrole` | User and RBAC |
| **Low** | `django_*`, `auth_*`, `rest_framework_*` | Framework tables (skip or minimal) |

**Introspection Process:**
1. Query `information_schema.tables` for `public` schema
2. For each table, query `information_schema.columns` for structure
3. Query `information_schema.table_constraints` and `key_column_usage` for relationships
4. Query `SELECT count(*) FROM {table}` for row counts (context for LLM)
5. LLM enrichment: batch tables (10 at a time), generate business descriptions
6. Store in `knowledge_entities` table + ChromaDB embeddings

**Example Enriched Entity:**
```json
{
  "entity_type": "table",
  "name": "emissions_calculation",
  "schema_json": {
    "columns": [
      {"name": "id", "type": "integer", "nullable": false},
      {"name": "module_id", "type": "integer", "nullable": false, "fk": "core_module"},
      {"name": "emission_factor_id", "type": "integer", "nullable": true, "fk": "emissions_emissionfactor"},
      {"name": "activity_value", "type": "numeric", "nullable": false},
      {"name": "result_co2e_kg", "type": "numeric", "nullable": true},
      {"name": "scope", "type": "varchar", "nullable": true}
    ]
  },
  "semantic_description": "Stores computed greenhouse gas emissions. Each calculation links activity data (from DataRows) to an emission factor, producing CO2-equivalent results. Scoped to a module (and thus an organizational unit) for access control. Critical for GHG reporting and dashboards.",
  "relationships": [
    {"type": "many_to_one", "target": "core_module", "description": "belongs to a data collection module"},
    {"type": "many_to_one", "target": "emissions_emissionfactor", "description": "uses an emission factor for conversion"}
  ]
}
```

---

## 5. Implementation Phases

### Phase 1: Foundation (Pulse Setup)
**Goal:** Get Pulse running standalone, connected to Carbon DB, basic chat working

**Tasks:**
1. Create `instances/carbon/instance.yaml` (copy from Gigacast, adapt to Carbon domain)
2. Update Pulse `.env` with Carbon connection details
3. Bootstrap Pulse DB: `python -m api.admin init-db`
4. Create Carbon instance via Pulse admin API
5. Trigger introspection: `POST /admin/instances/{carbon_id}/introspect`
6. Verify knowledge entities populated (tables, relationships, descriptions)
7. Test chat API: `POST /chat/carbon` with simple queries

**Acceptance Criteria:**
- [ ] Pulse service starts on port 9200
- [ ] Schema introspection completes (40+ tables detected)
- [ ] Knowledge entities stored in SQLite + ChromaDB
- [ ] Chat endpoint responds with Carbon-aware answers
- [ ] No errors in Pulse logs

**Estimated Duration:** 1-2 days

---

### Phase 2: Widget Integration
**Goal:** Embed Pulse chat widget in Carbon frontend

**Tasks:**
1. Build Pulse widget: `cd widget && npm run build` → `dist/pulse.js`
2. Serve widget via Pulse API: `GET /widget/pulse.js`
3. Add widget script tag to Carbon frontend `index.html`:
   ```html
   <script src="http://localhost:9200/widget/pulse.js" 
           data-instance="carbon"
           data-api-url="http://localhost:9200"></script>
   ```
4. Configure CORS in Pulse to allow Carbon frontend origin
5. Test widget loads, floating button appears
6. Test WebSocket chat connection works
7. Test page context sent with messages (`window.location.pathname`)

**Acceptance Criteria:**
- [ ] Widget loads in Carbon frontend without errors
- [ ] Floating Pulse button visible in bottom-right
- [ ] Chat drawer opens/closes smoothly
- [ ] Messages send and receive via WebSocket
- [ ] Page context logged in Pulse (e.g., "user is on /emissions")

**Estimated Duration:** 1 day

---

### Phase 3: Tool Integration (Agent Actions)
**Goal:** Enable Pulse to query Carbon DB and call Carbon APIs

**Tools to Implement:**
1. **`query_host_db`** — Execute SELECT queries on Carbon DB (read-only, timeout enforced)
2. **`search_knowledge`** — Semantic search over introspected schema
3. **`get_entity_details`** — Get full schema for a table/field
4. **`call_host_api`** — Call Carbon REST APIs (with confirmation for mutations)

**Example Tool Use:**
```
User: "How many calculations do we have for Scope 1?"

Pulse Agent:
1. search_knowledge("calculations scope 1") → finds `emissions_calculation` table
2. query_host_db("SELECT count(*) FROM emissions_calculation WHERE scope = '1'")
3. Returns: "There are 127 Scope 1 calculations in the system."
```

**Tasks:**
1. Implement tools in `agent/tools.py`
2. Add SQL safety checks (block non-SELECT, enforce timeout)
3. Test tool execution in conversation
4. Add confirmation flow for write APIs (future phase)

**Acceptance Criteria:**
- [ ] Agent can query Carbon DB for counts, lists, filters
- [ ] SQL injection protection works
- [ ] Timeout enforced (5s max query time)
- [ ] Tool responses integrated into chat answers
- [ ] Error handling for failed queries

**Estimated Duration:** 2 days

---

### Phase 4: Domain Knowledge Refinement
**Goal:** Make Pulse truly expert in Carbon domain

**Tasks:**
1. Refine `instance.yaml` business rules (expand from Gigacast template)
2. Add Carbon-specific glossary terms (GHG scope, emission factor, data schema engine)
3. Test complex domain queries:
   - "What's the difference between Scope 1 and Scope 2?"
   - "Which org units have incomplete data for January 2026?"
   - "Show me the emission factors for diesel fuel"
4. Admin review and edit entity descriptions via Pulse Studio
5. Ingest Carbon documentation into knowledge base (optional RAG)

**Acceptance Criteria:**
- [ ] Pulse answers domain questions correctly (90%+ accuracy)
- [ ] Glossary terms used in responses
- [ ] Business rules inform recommendations
- [ ] Entity descriptions reviewed by Carbon team

**Estimated Duration:** 2-3 days

---

### Phase 5: Cognition Loop (Proactive Monitoring)
**Goal:** Enable background health checks and alerts

**Monitors to Implement:**
1. **Data freshness:** Check `max(dataschema_datarow.updated_at)` per module
2. **Calculation errors:** Check `emissions_calculation` for failed calculations
3. **DQ degradation:** Check `dq_dqresult.pass_rate` trends
4. **Missing factors:** Check calculations with `emission_factor_id IS NULL`

**Tasks:**
1. Implement monitors in `cognition/monitors.py`
2. Configure intervals in `.env` (hourly, 6h, daily)
3. Start cognition loop: `start_scheduler()` in `main.py`
4. Test alert generation → `notifications` table
5. Display alerts in Pulse widget (proactive notifications)

**Acceptance Criteria:**
- [ ] Monitors run on schedule
- [ ] Notifications created when thresholds breached
- [ ] Alerts visible in widget and admin UI
- [ ] No false positives

**Estimated Duration:** 2-3 days

---

### Phase 6: User-Context-Aware Auth (Future Enhancement)
**Goal:** Respect Carbon's org-scoped RBAC in Pulse

**Tasks:**
1. Carbon frontend passes user's JWT to Pulse widget on init
2. Pulse validates JWT (shared secret or public key verification)
3. Pulse calls `/api/v1/accounts/me/` to get user's org context
4. Pulse filters DB queries by user's allowed modules
5. Tool execution respects user's role (dataowner vs auditor)

**Acceptance Criteria:**
- [ ] Data-owner user sees only their org's data via Pulse
- [ ] Auditor user cannot trigger write actions
- [ ] Admin user sees everything
- [ ] No data leakage across org boundaries

**Estimated Duration:** 3-4 days

---

### Phase 7: Production Deployment
**Goal:** Deploy Pulse+Carbon to production environment

**Tasks:**
1. Create production `.env` for Pulse (use production DB URL, API URL)
2. Deploy Pulse as systemd service or Docker container
3. Configure nginx reverse proxy for Pulse (port 9200)
4. Update Carbon frontend to use production Pulse URL
5. Set up SSL/TLS for Pulse API
6. Configure CORS for production domains
7. Set up monitoring (Pulse logs, uptime checks)
8. Load testing (concurrent users, widget performance)

**Acceptance Criteria:**
- [ ] Pulse service runs reliably in production
- [ ] Widget loads over HTTPS without CORS errors
- [ ] Chat responses within 2s (p95)
- [ ] No memory leaks after 24h operation
- [ ] Logs captured and monitored

**Estimated Duration:** 3-5 days

---

## 6. Technical Specifications

### 6.1 Pulse Service Requirements

**Hardware (Minimum):**
- 2 CPU cores
- 4 GB RAM
- 10 GB disk (SQLite DB + ChromaDB vectors + logs)

**Software:**
- Python 3.12+
- FastAPI
- PostgreSQL client libraries (psycopg2)
- ChromaDB (embedded)

**Network:**
- Port 9200 (Pulse API)
- Outbound HTTPS to Poe API (LLM provider)
- Inbound from Carbon frontend (CORS configured)
- Outbound to Carbon backend API (HTTP)
- Outbound to Carbon PostgreSQL (5432)

### 6.2 Carbon Integration Points

**No Changes Required in Carbon Backend:**
- Pulse integrates via existing REST APIs
- Read-only DB access (separate connection pool)
- No new Django apps or middleware

**Minimal Changes in Carbon Frontend:**
- Add `<script>` tag to load Pulse widget (1 line in `index.html`)
- Optional: Pass user JWT to widget for user-aware mode (Phase 6)

**Database Access:**
- Pulse user: `pulse_readonly` (PostgreSQL role)
- Permissions: `SELECT` on all tables in `public` schema
- Connection pooling: max 5 connections
- Read replica recommended for production (if available)

### 6.3 Security Considerations

**Database Security:**
- Pulse DB user has `SELECT`-only privileges
- Connection uses SSL/TLS in production
- Queries timeout after 5 seconds
- No DDL or DML allowed (enforced by DB role and app code)

**API Security:**
- Pulse API requires JWT for authenticated endpoints
- CORS restricted to Carbon frontend domains
- Rate limiting on chat endpoints (10 req/min per user)
- Input sanitization for SQL queries (parameterized queries only)

**LLM Security:**
- No PII sent to LLM (data is aggregated/anonymized)
- System prompts prevent prompt injection
- API keys stored in `.env`, never in code
- LLM responses sanitized before display

**Widget Security:**
- Widget served over HTTPS in production
- Content Security Policy headers
- No inline scripts (CSP compliant)
- WebSocket connection authenticated

### 6.4 Monitoring & Observability

**Pulse Metrics to Track:**
- Chat requests per hour
- Average response time (LLM latency)
- Tool execution success rate
- DB query performance (slow query log)
- Memory usage, CPU usage
- WebSocket connection count

**Alerts:**
- Pulse service down
- LLM API errors (>5% error rate)
- DB connection failures
- High latency (p95 > 5s)
- Memory leak (RSS > 2GB)

**Logging:**
- Structured JSON logs
- Levels: DEBUG (dev), INFO (prod)
- Log rotation (daily, keep 30 days)
- Centralized logging (optional: ship to ELK/Loki)

---

## 7. Comparison with Gigacast Integration

| Aspect | Gigacast | Carbon | Notes |
|---|---|---|---|
| **Domain** | Power forecasting | Carbon accounting | Different domain knowledge |
| **Backend** | Django + PostgreSQL | Django + PostgreSQL | **Identical tech stack** |
| **API Pattern** | DRF ViewSets | DRF ViewSets | **Identical REST API pattern** |
| **Auth** | JWT | JWT | **Identical auth mechanism** |
| **RBAC** | User roles | Org-scoped roles | Carbon has richer RBAC |
| **Frontend** | React | React | **Identical widget integration** |
| **Pulse Port** | 9100 | 9200 | Different port, same architecture |
| **Instance Config** | `instances/gigacast/` | `instances/carbon/` | **Same YAML structure** |
| **Cognition Loop** | Model health, data freshness | DQ monitoring, calc errors | Different monitors, same framework |
| **Deployment** | Standalone FastAPI | Standalone FastAPI | **Identical deployment pattern** |

**Key Insight:** The integration architecture is **95% identical**. Only domain-specific content (business rules, glossary, API catalog, monitors) differs.

---

## 8. Success Metrics

### 8.1 Technical Metrics
- [ ] Schema introspection covers 100% of Carbon tables (40+ tables)
- [ ] Widget loads in <1s
- [ ] Chat response time <2s (p95)
- [ ] Tool execution success rate >95%
- [ ] Zero data leakage (org-scoped queries verified)
- [ ] Uptime >99.5%

### 8.2 User Experience Metrics
- [ ] Users can ask domain questions and get accurate answers (>90% accuracy)
- [ ] Widget adoption rate >50% of active Carbon users
- [ ] Average conversation length >3 messages (engagement)
- [ ] Positive feedback rate >80% (thumbs up)
- [ ] Proactive alerts acknowledged within 1 hour

### 8.3 Business Metrics
- [ ] Reduced support tickets (users self-serve via Pulse)
- [ ] Faster onboarding (new users learn Carbon via chat)
- [ ] Data quality improvement (proactive alerts caught early)
- [ ] Increased platform usage (widget makes Carbon more accessible)

---

## 9. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| **LLM API downtime** | High | Low | Cache responses, fallback to simple Q&A, show "AI unavailable" message |
| **DB query performance** | Medium | Medium | Query timeout, index optimization, read replica |
| **Widget CORS errors** | High | Low | Test CORS config thoroughly, document domains |
| **User confusion** | Medium | Medium | Clear widget UI, help text, example questions |
| **Data leakage (org RBAC)** | Critical | Low | Thorough testing, Phase 6 (user-aware auth) |
| **Cost overrun (LLM API)** | Medium | Medium | Budget alerts, use smaller models for cognition loop |

---

## 10. Next Steps

1. **Approval:** Review this plan with Carbon team and Pulse maintainers
2. **Environment Setup:** Prepare `.env` files, create `pulse_readonly` DB user
3. **Phase 1 Start:** Create `instances/carbon/instance.yaml`, run introspection
4. **Weekly Checkpoints:** Review progress, adjust timeline as needed
5. **Production Readiness:** Security audit, load testing, deployment plan

---

## 11. References

**Gigacast+Pulse Integration:**
- `/home/ahmed/clearturn/pulse/instances/gigacast/instance.yaml`
- `/home/ahmed/clearturn/pulse/docs/BLUEPRINT.md`
- `/home/ahmed/clearturn/pulse/docs/ARCHITECTURE.md`

**Carbon Platform:**
- `/home/ahmed/aast/carbon/docs/STRATEGY_DATA_TRUST_PLATFORM.md`
- `/home/ahmed/aast/carbon/docs/DESIGN_ORG_ACCESS_MODEL.md`
- `/home/ahmed/aast/carbon/docs/DESIGN_DATA_TRUST_CORE.md`
- `/home/ahmed/aast/carbon/backend/config/settings.py`

**Pulse Documentation:**
- Pulse Blueprint: `/home/ahmed/clearturn/pulse/docs/BLUEPRINT.md`
- Pulse Architecture: `/home/ahmed/clearturn/pulse/docs/ARCHITECTURE.md`

---

**END OF PLAN**
