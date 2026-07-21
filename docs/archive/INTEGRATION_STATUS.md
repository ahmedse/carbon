# Pulse + Carbon Integration Status

**Date:** 2026-07-18  
**Status:** Instance configuration created, ready for environment setup

---

## ✅ Completed

1. **Architecture Planning**
   - Comprehensive integration plan documented ([`PULSE_CARBON_INTEGRATION_PLAN.md`](PULSE_CARBON_INTEGRATION_PLAN.md))
   - Quick start guide created ([`PULSE_CARBON_QUICK_START.md`](PULSE_CARBON_QUICK_START.md))

2. **Instance Configuration**
   - Created `/home/ahmed/clearturn/pulse/instances/carbon/instance.yaml`
   - Configured for Carbon Data Trust Platform
   - API catalog: 20+ endpoints mapped (dataschema, emissions, catalog, mdm, dq, accounts)
   - Business rules: Carbon accounting domain (GHG Protocol, scopes, calculations)
   - Glossary: 15 domain terms defined
   - Cognition monitors: 5 monitors configured (data freshness, calculation errors, DQ, etc.)
   - Navigation map: Carbon frontend routes

---

## 📋 Next Steps (Manual)

### Step 1: Environment Configuration

**Add to `/home/ahmed/clearturn/pulse/.env`:**

```env
# ── Carbon Instance (add these to existing .env) ──
CARBON_DB_URL=postgresql://pulse_readonly:PASSWORD@localhost:5432/carbon_db
CARBON_DB_SCHEMA=public
CARBON_API_URL=http://127.0.0.1:8009/api/v1
CARBON_API_TOKEN=<get-from-carbon-admin-login>
CARBON_FRONTEND_URL=http://localhost:5173

# Update CORS to include Carbon frontend
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:5177,http://127.0.0.1:5177,http://localhost:8001,http://127.0.0.1:8001,http://localhost:8009,http://127.0.0.1:8009
```

**Get Carbon admin JWT token:**
```bash
curl -X POST http://localhost:8009/api/v1/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"YOUR_ADMIN_PASSWORD"}' \
  | jq -r '.access'
```

### Step 2: Create Read-Only Database User

**In Carbon PostgreSQL (as superuser):**

```sql
-- Connect to Carbon database
\c carbon_db

-- Create read-only user for Pulse
CREATE USER pulse_readonly WITH PASSWORD 'secure_password_here';
GRANT CONNECT ON DATABASE carbon_db TO pulse_readonly;
GRANT USAGE ON SCHEMA public TO pulse_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO pulse_readonly;

-- Future tables also read-only
ALTER DEFAULT PRIVILEGES IN SCHEMA public 
  GRANT SELECT ON TABLES TO pulse_readonly;

-- Verify
\du pulse_readonly
```

### Step 3: Register Carbon Instance in Pulse

**Option A: Via Pulse API**
```bash
cd /home/ahmed/clearturn/pulse

# Source .env to get connection details
source .env

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

# Save the returned instance ID
```

**Option B: Via Pulse Studio**
1. Open `http://localhost:9100/studio` (if Studio is running)
2. Go to Instances → Add New
3. Fill form with Carbon details from `.env`
4. Click "Create Instance"

### Step 4: Trigger Schema Introspection

```bash
# Get Carbon instance ID from previous step
CARBON_INSTANCE_ID="<uuid-from-response>"

# Trigger introspection
curl -X POST http://localhost:9100/admin/instances/$CARBON_INSTANCE_ID/introspect

# Watch logs
tail -f /home/ahmed/clearturn/pulse/logs/pulse.log
```

**Expected:** Introspection discovers ~40-50 tables:
- `accounts_*` (User, ScopedRole)
- `core_*` (Module, Project, Cycle)
- `dataschema_*` (DataTable, DataField, DataRow)
- `emissions_*` (Calculation, EmissionFactor, ReportingPeriod)
- `catalog_*` (AssetProfile, GlossaryTerm)
- `mdm_*` (OrgUnit, ReferenceSet)
- `dq_*` (FieldProfile, DQRule, DQResult)

### Step 5: Verify Knowledge Entities

```bash
# Check entity count
sqlite3 /home/ahmed/clearturn/pulse/data/pulse.db \
  "SELECT count(*) FROM knowledge_entities WHERE instance_id = '$CARBON_INSTANCE_ID';"

# Should return 40+

# List entities
sqlite3 /home/ahmed/clearturn/pulse/data/pulse.db \
  "SELECT name, entity_type FROM knowledge_entities WHERE instance_id = '$CARBON_INSTANCE_ID' ORDER BY name;"
```

### Step 6: Widget Integration

**Edit `/home/ahmed/aast/carbon/carbon-frontend/index.html`:**

Add before closing `</body>` tag:

```html
  <!-- Pulse AI Assistant Widget -->
  <script 
    src="http://localhost:9100/widget/pulse.js" 
    data-instance="carbon"
    data-api-url="http://localhost:9100">
  </script>
</body>
```

**Restart Carbon frontend:**
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run dev
```

### Step 7: Test Integration

**Open browser: `http://localhost:5173`**

1. Verify Pulse floating button appears (bottom-right)
2. Click button to open chat drawer
3. Test queries:
   - "What is Carbon?"
   - "How many emission calculations do we have?"
   - "What's the difference between Scope 1 and Scope 2?"
   - "Show me the organizational units"
   - "Which modules exist for data collection?"

---

## 📊 Configuration Summary

### Instance Details
- **Name:** carbon
- **Display Name:** Carbon Data Trust Platform
- **Domain:** carbon_accounting_sustainability
- **Timezone:** Africa/Cairo
- **Languages:** English, Arabic

### Integration Points
- **Database:** PostgreSQL (read-only via `pulse_readonly` user)
- **API:** Django REST Framework (authenticated via JWT)
- **Widget:** Embedded in Carbon frontend via script tag
- **Communication:** WebSocket for chat, HTTP for API calls

### Domain Knowledge
- **API Endpoints:** 20+ mapped (core, dataschema, emissions, catalog, mdm, dq, accounts)
- **Business Rules:** 10 rules for carbon accounting (GHG Protocol, calculations, org scoping)
- **Glossary:** 15 terms (GHG Scope, Emission Factor, Module, OrgUnit, DataSchema, etc.)
- **Monitors:** 5 proactive checks (freshness, calculation errors, DQ degradation, completeness)

### Architecture Pattern
- **Standalone FastAPI service** (Pulse runs separately from Carbon)
- **Read-only DB access** (no writes to Carbon DB)
- **Admin agent** (Phase 1: uses admin JWT, future: user-context-aware)
- **Instance-based config** (YAML file + env vars, no hardcoding)
- **Zero changes to Carbon backend** (external integration only)

---

## 🔍 Verification Checklist

After completing setup steps:

- [ ] Pulse `.env` has Carbon connection vars (`CARBON_DB_URL`, `CARBON_API_URL`, `CARBON_API_TOKEN`)
- [ ] `pulse_readonly` user exists in Carbon DB with SELECT privileges
- [ ] Carbon instance registered in Pulse (visible via `/admin/instances` API or Studio)
- [ ] Schema introspection completed (40+ entities in `knowledge_entities` table)
- [ ] Widget script tag added to Carbon `index.html`
- [ ] CORS configured to allow Carbon frontend origin
- [ ] Pulse button appears in Carbon UI
- [ ] Chat drawer opens and responds to messages
- [ ] Domain queries work ("What is Carbon?", "How many calculations?")
- [ ] Tool execution works (DB queries, knowledge search)

---

## 📚 Documentation References

- **Architecture:** [`PULSE_CARBON_INTEGRATION_PLAN.md`](PULSE_CARBON_INTEGRATION_PLAN.md)
- **Quick Start:** [`PULSE_CARBON_QUICK_START.md`](PULSE_CARBON_QUICK_START.md)
- **Instance Config:** `/home/ahmed/clearturn/pulse/instances/carbon/instance.yaml`
- **Pulse Blueprint:** `/home/ahmed/clearturn/pulse/docs/BLUEPRINT.md`
- **Carbon Strategy:** `/home/ahmed/aast/carbon/docs/STRATEGY_DATA_TRUST_PLATFORM.md`

---

## ⏱️ Estimated Time to Complete

- **Environment setup:** 15 minutes (DB user, .env, JWT token)
- **Instance registration:** 10 minutes (API call or Studio)
- **Schema introspection:** 5-10 minutes (automatic, just wait)
- **Widget integration:** 10 minutes (edit HTML, restart frontend)
- **Testing & validation:** 30 minutes (test queries, verify functionality)

**Total:** ~1-1.5 hours from this point

---

## 🚀 Future Enhancements

**Phase 2: Cognition Loop** (proactive monitoring)
- Implement monitor logic in Pulse
- Enable background health checks
- Display alerts in widget

**Phase 3: User-Context-Aware Auth** (org-scoped RBAC)
- Carbon frontend passes user JWT to widget
- Pulse respects user's org-scoped access
- Data-owners see only their org's data

**Phase 4: Production Deployment**
- Configure production URLs, SSL, CORS
- Set up monitoring, logging, alerts
- Load testing and performance optimization

---

**Status:** Ready for manual execution of environment setup and instance registration.
