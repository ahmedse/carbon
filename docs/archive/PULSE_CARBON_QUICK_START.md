# Pulse for Carbon — Quick Integration Guide

> **Context:** Pulse is already running in dev/prod with Gigacast. We're adding Carbon as a second instance.  
> **Time Required:** ~2-3 hours  
> **Pattern:** Identical to Gigacast — just domain-specific configuration

---

## Prerequisites

- ✅ Pulse service running (port 9100 for Gigacast)
- ✅ Pulse widget built and served
- ✅ Carbon backend running (port 8009)
- ✅ Carbon frontend running (port 5173 dev / 8001 prod)
- ✅ PostgreSQL access to Carbon DB

---

## Step 1: Create Instance Configuration (30 minutes)

### 1.1 Create Instance File

**Location:** `/home/ahmed/clearturn/pulse/instances/carbon/instance.yaml`

**Quick Start:** Copy from Gigacast template:
```bash
cd /home/ahmed/clearturn/pulse/instances
cp -r gigacast carbon
cd carbon
```

### 1.2 Edit Metadata

Update these fields in `instance.yaml`:

```yaml
name: carbon
display_name: Carbon Data Trust Platform
description: >
  Carbon accounting and sustainability data management platform for AASTMT.
  Manages GHG emissions tracking (Scope 1/2/3), org-scoped data collection,
  master data, data quality, and catalog governance.

domain: carbon_accounting_sustainability
timezone: Africa/Cairo
languages: [en, ar]
```

### 1.3 Update API Catalog

Replace Gigacast endpoints with Carbon's:

**Remove:**
- `/datahub/v2/*` endpoints
- `/aihub/*` endpoints

**Add:**
```yaml
api_catalog:
  # Core
  - name: list_modules
    method: GET
    path: /core/modules/
    description: List data collection modules with org unit association
    requires_auth: true
    requires_confirmation: false

  # DataSchema (metadata-driven data layer)
  - name: list_data_tables
    method: GET
    path: /dataschema/tables/
    description: List data tables with module and field count
    requires_auth: true
    requires_confirmation: false

  - name: list_data_rows
    method: GET
    path: /dataschema/rows/
    description: Get data rows with filtering
    requires_auth: true
    requires_confirmation: false

  # Emissions
  - name: list_calculations
    method: GET
    path: /emissions/calculations/
    description: List emission calculations with results and scope
    requires_auth: true
    requires_confirmation: false

  - name: get_emissions_dashboard
    method: GET
    path: /emissions/dashboard/
    description: Get emissions summary by scope, period, org
    requires_auth: true
    requires_confirmation: false

  - name: list_emission_factors
    method: GET
    path: /emissions/factors/
    description: List emission factors with categories
    requires_auth: true
    requires_confirmation: false

  # Catalog, MDM, DQ
  - name: list_asset_profiles
    method: GET
    path: /catalog/profiles/
    description: List cataloged data assets
    requires_auth: true
    requires_confirmation: false

  - name: list_org_units
    method: GET
    path: /mdm/org-units/
    description: List organizational units (AASTMT tree)
    requires_auth: true
    requires_confirmation: false

  - name: list_dq_results
    method: GET
    path: /dq/results/
    description: List data quality rule results
    requires_auth: true
    requires_confirmation: false
```

### 1.4 Update Business Rules

Replace power forecasting rules with carbon accounting:

```yaml
business_rules:
  - "GHG Protocol defines three scopes: Scope 1 (direct), Scope 2 (purchased energy), Scope 3 (value chain)"
  - "Calculations = activity_data × emission_factor × GWP"
  - "Emission factors are in kg CO2e per activity unit (e.g., per liter diesel)"
  - "Data is org-scoped via Module.org_unit → OrgUnit tree"
  - "OrgUnit structure: AASTMT → Campus → College → Department"
  - "Reference data (factors, org units) is global; activity data is org-scoped"
  - "DataSchema engine stores table/field definitions as data (not migrations)"
  - "Admins see all; dataowners see their org subtree; auditors read-only"
```

### 1.5 Update Glossary

Replace power terms with carbon terms:

```yaml
glossary:
  GHG_Scope: "Classification: Scope 1 (direct), Scope 2 (indirect energy), Scope 3 (value chain)"
  Emission_Factor: "Conversion factor: kg CO2e per activity unit"
  Activity_Data: "Raw operational data that generates emissions (liters fuel, kWh electricity)"
  Calculation: "Computed emission = activity × factor × GWP"
  Module: "Data collection area within a GHG scope (e.g., Transportation - Fleet)"
  DataTable: "Metadata-driven table schema (part of DataSchema engine)"
  DataRow: "Single data record in a DataTable, stored as JSON"
  OrgUnit: "Organizational unit in AASTMT tree (university, campus, college, department)"
  ScopedRole: "Role assignment (admin/dataowner/auditor) scoped to org or module"
  AssetProfile: "Catalog metadata for a data asset (table/field) with owner, quality score"
  ReferenceSet: "Master data collection (emission scopes, org types, fuel types)"
  DQRule: "Data quality validation rule (completeness, range, pattern)"
  ReportingPeriod: "Time window for reporting (monthly, quarterly, annual)"
```

### 1.6 Update Cognition Monitors

Replace model health checks with data quality checks:

```yaml
cognition:
  monitors:
    - name: data_freshness
      description: Alert when data rows not updated recently
      check: last_row_timestamp
      max_age_hours: 168  # 1 week

    - name: calculation_errors
      description: Alert on failed emission calculations
      check: calculation_status
      look_back_hours: 24

    - name: data_quality_degradation
      description: Alert when DQ pass rate drops
      check: dq_pass_rate
      warning_threshold: 80.0
      critical_threshold: 60.0

    - name: missing_emission_factors
      description: Alert on calculations missing factors
      check: calculation_errors_missing_factor
      look_back_hours: 24
```

---

## Step 2: Environment Configuration (15 minutes)

### 2.1 Create Read-Only DB User

**In Carbon PostgreSQL:**

```sql
-- Connect to Carbon DB
\c carbon_db

-- Create read-only user for Pulse
CREATE USER pulse_readonly WITH PASSWORD 'your_secure_password';
GRANT CONNECT ON DATABASE carbon_db TO pulse_readonly;
GRANT USAGE ON SCHEMA public TO pulse_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO pulse_readonly;

-- Future tables also read-only
ALTER DEFAULT PRIVILEGES IN SCHEMA public 
  GRANT SELECT ON TABLES TO pulse_readonly;
```

### 2.2 Get Carbon Admin JWT

```bash
# Get admin token for Pulse to use
curl -X POST http://localhost:8009/api/v1/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your_admin_password"}' \
  | jq -r '.access'

# Save the token (starts with "eyJ...")
```

### 2.3 Update Pulse `.env`

**Add to `/home/ahmed/clearturn/pulse/.env`:**

```env
# Carbon Instance (add alongside Gigacast vars)
CARBON_DB_URL=postgresql://pulse_readonly:your_secure_password@localhost:5432/carbon_db
CARBON_API_URL=http://127.0.0.1:8009/api/v1
CARBON_API_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Update CORS to include Carbon frontend
CORS_ORIGINS=http://localhost:5173,http://localhost:8001,http://localhost:8009,http://localhost:9100
```

---

## Step 3: Bootstrap Carbon Instance (10 minutes)

### 3.1 Create Instance in Pulse

**Option A: Via Pulse Studio UI** (if available)
1. Open `http://localhost:9100/studio`
2. Go to Instances → Add New
3. Fill form with Carbon details
4. Click "Create Instance"

**Option B: Via API**

```bash
cd /home/ahmed/clearturn/pulse

# Create instance
curl -X POST http://localhost:9100/admin/instances \
  -H "Content-Type: application/json" \
  -d '{
    "name": "carbon",
    "display_name": "Carbon Data Trust Platform",
    "host_db_url": "'"$CARBON_DB_URL"'",
    "host_api_url": "'"$CARBON_API_URL"'",
    "host_api_token": "'"$CARBON_API_TOKEN"'",
    "status": "active",
    "config": {}
  }' | jq

# Save the returned ID
CARBON_INSTANCE_ID="<uuid-from-response>"
```

### 3.2 Trigger Schema Introspection

```bash
# Introspect Carbon DB schema
curl -X POST http://localhost:9100/admin/instances/$CARBON_INSTANCE_ID/introspect

# Check logs for progress
tail -f /home/ahmed/clearturn/pulse/logs/pulse.log
```

**Expected:** Introspection finds ~40-50 tables from Carbon DB (core, accounts, dataschema, emissions, catalog, mdm, dq, etc.)

### 3.3 Verify Knowledge Entities

```bash
# Check if entities were created
sqlite3 /home/ahmed/clearturn/pulse/data/pulse.db \
  "SELECT count(*) FROM knowledge_entities WHERE instance_id = '$CARBON_INSTANCE_ID';"

# Should return 40+
```

---

## Step 4: Widget Integration (20 minutes)

### 4.1 Add Widget to Carbon Frontend

**Edit `/home/ahmed/aast/carbon/carbon-frontend/index.html`:**

Find the closing `</body>` tag and add before it:

```html
  <!-- Pulse AI Assistant Widget -->
  <script 
    src="http://localhost:9100/widget/pulse.js" 
    data-instance="carbon"
    data-api-url="http://localhost:9100">
  </script>
</body>
```

### 4.2 Restart Carbon Frontend

```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run dev
```

### 4.3 Test Widget Loads

1. Open browser: `http://localhost:5173`
2. Look for Pulse floating button (bottom-right corner, purple/blue icon)
3. Click button → chat drawer should slide in from right
4. Type "Hello" → should get response from Pulse

---

## Step 5: Test & Validate (1 hour)

### 5.1 Test Basic Queries

In the Pulse widget, try these:

```
1. "What is Carbon?"
   → Should reference Carbon Data Trust Platform, AASTMT, emissions

2. "How many emission calculations do we have?"
   → Should query emissions_calculation table, return count

3. "What's the difference between Scope 1 and Scope 2?"
   → Should reference GHG Protocol, explain direct vs indirect emissions

4. "Show me the organizational units"
   → Should list OrgUnits (AASTMT, campuses, colleges)

5. "Which modules exist for data collection?"
   → Should list Modules with their names and scopes

6. "What emission factors are available?"
   → Should query emissions_emissionfactor table
```

### 5.2 Test Page Context

1. Navigate to different Carbon pages (e.g., `/emissions`, `/catalog`, `/admin/org-units`)
2. Ask Pulse: "Where am I?"
3. Verify Pulse knows the current page from `window.location.pathname`

### 5.3 Test Tool Execution

Ask complex question that requires DB query:

```
"How many Scope 1 calculations were done in January 2026?"
```

**Expected flow:**
1. Pulse searches knowledge for "calculations scope"
2. Finds `emissions_calculation` table
3. Executes query: `SELECT count(*) FROM emissions_calculation WHERE scope = '1' AND ...`
4. Returns answer with count

Check Pulse logs for tool execution:
```bash
tail -f /home/ahmed/clearturn/pulse/logs/pulse.log | grep "tool_execution"
```

### 5.4 Verify No Data Leakage

**Important:** Since we're using admin JWT, Pulse currently sees ALL data (no org scoping yet).

Test that Carbon's own RBAC still works:
1. Login to Carbon as a data-owner user (not admin)
2. Verify Carbon UI shows only their org's data
3. Note: Pulse will still show full data (admin view) — this is Phase 6 work (user-context-aware auth)

---

## Step 6: Refine Domain Knowledge (30 minutes)

### 6.1 Test Complex Domain Questions

```
"What are the emission factors for diesel fuel?"
"Which org units have incomplete data for January 2026?"
"Explain the DataSchema engine"
"What's the difference between a Module and an OrgUnit?"
"How do I calculate Scope 2 emissions for electricity?"
```

### 6.2 Review and Edit Entity Descriptions

If Pulse Studio is available:
1. Open `http://localhost:9100/studio`
2. Select Carbon instance
3. Go to Knowledge → Entities
4. Review LLM-generated descriptions for tables
5. Edit any that are inaccurate or incomplete

### 6.3 Add Documentation (Optional)

If you have Carbon documentation (markdown files), you can ingest them:

```bash
# Copy docs to Pulse knowledge folder (if RAG is implemented)
cp /home/ahmed/aast/carbon/docs/*.md \
   /home/ahmed/clearturn/pulse/instances/carbon/docs/

# Trigger doc ingestion
curl -X POST http://localhost:9100/admin/instances/$CARBON_INSTANCE_ID/ingest-docs
```

---

## Complete! 🎉

**Total Time:** ~2-3 hours

**What You Have:**
- ✅ Pulse understands Carbon's schema (40+ tables)
- ✅ Widget embedded in Carbon frontend
- ✅ Can answer domain questions about carbon accounting
- ✅ Can query Carbon DB for live data
- ✅ Can call Carbon APIs (with admin access)
- ✅ Business rules and glossary loaded

**What's Next (Future Enhancements):**

1. **User-Context-Aware Auth** (Phase 6)
   - Pass user's JWT to Pulse widget
   - Pulse respects org-scoped RBAC
   - Data-owners see only their org's data via Pulse

2. **Cognition Loop** (Phase 5)
   - Enable background monitoring
   - Proactive alerts for data quality, freshness, calculation errors
   - Requires implementing monitor logic in Pulse

3. **Action Confirmation** (Phase 3 extension)
   - Enable write operations via Carbon APIs
   - Requires user confirmation before execution
   - E.g., "Create a new emission calculation for January 2026"

4. **Production Deployment** (Phase 7)
   - Configure production URLs, SSL, CORS
   - Set up monitoring, logging, alerts
   - Load testing

---

## Troubleshooting

### Widget Doesn't Appear
- Check browser console for errors
- Verify Pulse service is running: `curl http://localhost:9100/health`
- Check CORS: Carbon frontend origin must be in `CORS_ORIGINS`
- Verify widget URL is correct in `index.html`

### Chat Doesn't Respond
- Check WebSocket connection in browser DevTools (Network tab, WS filter)
- Verify Pulse logs: `tail -f /home/ahmed/clearturn/pulse/logs/pulse.log`
- Check instance status: `curl http://localhost:9100/admin/instances`

### Introspection Failed
- Verify DB credentials in `.env`
- Test DB connection: `psql $CARBON_DB_URL -c "SELECT count(*) FROM core_module;"`
- Check Pulse logs for errors
- Ensure `pulse_readonly` user has SELECT privileges

### Wrong Answers / No Domain Knowledge
- Verify `instance.yaml` was loaded correctly
- Check instance config: `curl http://localhost:9100/admin/instances/$CARBON_INSTANCE_ID`
- Re-trigger introspection to refresh knowledge
- Review business rules and glossary in `instance.yaml`

---

## Files Modified

### New Files Created:
- `/home/ahmed/clearturn/pulse/instances/carbon/instance.yaml`

### Files Modified:
- `/home/ahmed/clearturn/pulse/.env` (added Carbon connection vars)
- `/home/ahmed/aast/carbon/carbon-frontend/index.html` (added widget script tag)

### Database Changes:
- Carbon PostgreSQL: created `pulse_readonly` user
- Pulse SQLite: added Carbon instance + 40+ knowledge entities

---

**For detailed architecture and future phases, see:** [`PULSE_CARBON_INTEGRATION_PLAN.md`](PULSE_CARBON_INTEGRATION_PLAN.md)
