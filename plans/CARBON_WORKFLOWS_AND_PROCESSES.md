# Carbon Emissions Data Management: Workflows & Processes

**Status:** Current System State Assessment  
**Date:** 2026-07-25  
**Purpose:** Define carbon-specific workflows for Scope 1, 2, 3 emissions management  

---

## Executive Summary: What's Ready Today

### ✅ Core Infrastructure (100% Complete)
- **RBAC:** Org-unit scoped access control with role hierarchies
- **Data entry system:** Generic multi-table data entry at `/carbon/data-entry`
- **Emission calculations:** `Calculation` model stores activity → CO2e results
- **Reporting periods:** `ReportingPeriod` model with workflow states (draft → open → locked → verified → closed)
- **Emission factors:** `EmissionFactor` model with Scope 1/2/3 classification and CRUD UI

### ⚠️ What's Missing for Carbon-Specific Workflows
1. **Dedicated Carbon data entry forms** (currently using generic dataschema tables)
2. **Scope-specific validation rules** (e.g., Scope 1 requires source type, Scope 2 requires grid region)
3. **Automated calculation triggers** (currently manual via API)
4. **Carbon workflow states** (submission → review → approval pipeline)
5. **Scope-based aggregation reports** (total by Scope 1/2/3)

---

## Terminology: Carbon Domain

**"Carbon Data Entry & Manipulation"** is typically called:

| Term | Definition | In This System |
|------|-----------|----------------|
| **Activity Data Collection** | Gathering raw activity amounts (kWh, liters, km) | ✅ `DataEntryPage` at `/carbon/data-entry/entry/:moduleId/:tableId` |
| **Emission Calculation** | Applying emission factors to activity data | ✅ `Calculation` model + API endpoints |
| **Carbon Accounting** | Full process: collect → calculate → verify → report | ⚠️ Partial (missing workflow automation) |
| **GHG Inventory Management** | Managing emissions across Scopes 1/2/3 | ⚠️ Partial (models exist, UI incomplete) |
| **Emission Source Tracking** | Tracking individual emission sources (vehicles, buildings) | ❌ Missing (needs Source registry) |

**Most accurate term for your system:** **"Carbon Accounting & GHG Inventory Management Platform"**

---

## Current System Architecture

### Backend Models (✅ Complete)

```
┌─────────────────────────────────────────────────────────────┐
│ ReportingPeriod                                             │
│ - Defines collection cycle (FY 2025, Q1 2025, etc.)       │
│ - Workflow: draft → open → locked → verified → closed     │
│ - Status gates: Data entry only allowed when "open"       │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ belongs to
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ DataTable (via dataschema app)                             │
│ - Generic tables for storing activity data                 │
│ - Example: "Vehicle Fleet Fuel Consumption"                │
│ - Fields: vehicle_id, fuel_type, liters, date             │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ contains
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ DataRow (activity data)                                     │
│ - values: {"vehicle_id": "V001", "liters": 100.5}         │
│ - Entered by: Data entry users (scoped to their org unit) │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ triggers calculation
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Calculation                                                  │
│ - activity_value: 100.5                                    │
│ - activity_unit: "liters"                                  │
│ - emission_factor: "Diesel_2024" (2.68 kg CO2e/liter)     │
│ - co2e_kg: 269.34 (calculated result)                     │
│ - scope: 1 (direct combustion)                            │
│ - category: "mobile_combustion"                           │
│ - reporting_period: FY 2025                                │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ aggregated into
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Report (JSON or CSV export)                                 │
│ - Total CO2e by Scope 1/2/3                                │
│ - Breakdown by category and org unit                       │
│ - Comparison to baseline period                            │
└─────────────────────────────────────────────────────────────┘
```

### Frontend Pages (✅ Partially Complete)

| Page | Path | Status | Users Can... |
|------|------|--------|-------------|
| **Data Entry Hub** | `/carbon/data-entry` | ✅ Exists | See modules assigned to their org unit |
| **Module Landing** | `/carbon/data-entry/module/:id` | ✅ Exists | See tables within a module |
| **Table Entry** | `/carbon/data-entry/entry/:moduleId/:tableId` | ✅ Exists | Add/edit rows of activity data |
| **Row Detail** | `/carbon/data-entry/row/:tableId/:rowId` | ✅ Exists | View/edit single row with validation |
| **Emission Factors** | `/emissions/factors` | ✅ Exists | Admins manage emission factors |
| **Reporting Periods** | `/emissions/periods` | ✅ Exists | Admins create/manage reporting cycles |
| **Report Generator** | `/emissions/reports` | ⚠️ Incomplete | Generate basic JSON reports (CSV missing) |
| **Data Owner Portal** | `/data-owner/portal` | ✅ Exists | See scoped dashboard for their org unit |
| **Data Owner Dashboard** | `/data-owner/dashboard` | ✅ Exists | View KPIs, scope breakdown, DQ metrics |

---

## GHG Protocol Scopes: Definitions & System Support

### Scope 1: Direct Emissions ✅
**Definition:** Emissions from sources owned or controlled by the organization

**Sources:**
- Stationary combustion (boilers, generators)
- Mobile combustion (company vehicles, fleet)
- Process emissions (manufacturing, chemical reactions)
- Fugitive emissions (refrigerants, gas leaks)

**System Support:**
- ✅ `EmissionFactor` model with `scope=1` classification
- ✅ Categories: `stationary_combustion`, `mobile_combustion`, `fugitive`, `process`
- ✅ Data entry via generic tables (need scope-specific forms)
- ✅ Calculation API: `POST /emissions/calculate/`

**Example Workflow:**
```
1. User enters: Vehicle V001 used 100 liters of diesel in Jan 2025
2. System finds: EmissionFactor "Diesel_2024" = 2.68 kg CO2e/liter
3. Calculation created: 100 × 2.68 = 268 kg CO2e (Scope 1, mobile)
4. Stored in Calculation table with reporting_period = FY2025
```

---

### Scope 2: Indirect Energy Emissions ✅
**Definition:** Emissions from purchased electricity, steam, heating, cooling

**Sources:**
- Grid electricity consumption
- Purchased steam
- District heating/cooling

**System Support:**
- ✅ `EmissionFactor` model with `scope=2` classification
- ✅ Categories: `electricity`
- ✅ Regional grid factors (e.g., "US_Grid_2024", "Egypt_Grid_2024")
- ✅ Data entry via generic tables (need grid region validation)
- ✅ Market-based vs. location-based factors (stored as separate EmissionFactors)

**Example Workflow:**
```
1. User enters: Building consumed 5000 kWh in Jan 2025
2. System asks: Which grid region? → User selects "Egypt_Grid_2024"
3. System finds: EmissionFactor "Egypt_Grid_2024" = 0.45 kg CO2e/kWh
4. Calculation: 5000 × 0.45 = 2250 kg CO2e (Scope 2, electricity)
```

---

### Scope 3: Value Chain Emissions ⚠️
**Definition:** All other indirect emissions in the value chain (upstream & downstream)

**15 GHG Protocol Categories:**
1. Purchased goods & services
2. Capital goods
3. Fuel/energy-related (not in Scope 1/2)
4. Upstream transportation
5. Waste generated
6. Business travel
7. Employee commuting
8. Upstream leased assets
9. Downstream transportation
10. Processing of sold products
11. Use of sold products
12. End-of-life treatment
13. Downstream leased assets
14. Franchises
15. Investments

**System Support:**
- ✅ `EmissionFactor` model with `scope=3` classification
- ✅ Categories: `transport`, `waste`, `water`, `materials`
- ⚠️ **Gap:** Only 4 of 15 categories mapped
- ⚠️ **Gap:** No supplier-specific factors
- ⚠️ **Gap:** No spend-based calculation method

**Example Workflow (Business Travel - Category 6):**
```
1. User enters: Employee flew 1200 km (round trip domestic)
2. System finds: EmissionFactor "Flight_Domestic" = 0.25 kg CO2e/km
3. Calculation: 1200 × 0.25 = 300 kg CO2e (Scope 3, transport)
```

---

## Current User Workflows (As-Is)

### Workflow 1: Data Entry (Scoped Users) ✅

**Actors:** Data entry users (org-unit scoped, non-admin)

**Steps:**
1. Login → System detects user's assigned org units via `ScopedRole`
2. Navigate to `/carbon/data-entry` → See modules filtered to their org units
3. Click module → See tables (e.g., "Vehicle Fleet Fuel")
4. Click table → Grid view shows existing rows (filtered to their org unit)
5. Click "Add Row" → Form opens with fields (vehicle_id, fuel_type, liters, date)
6. Fill form → Submit → `DataRow` created with `is_archived=False`
7. **Manual trigger:** Admin must call `POST /emissions/calculate/` to create `Calculation` records

**Current Limitations:**
- ❌ No scope-specific validation (e.g., require grid region for Scope 2)
- ❌ No automatic calculation trigger on row save
- ❌ No workflow states (submitted → approved)
- ❌ Generic forms don't enforce carbon-specific rules

---

### Workflow 2: Emission Factor Management (Admins) ✅

**Actors:** Admins (is_staff or is_superuser)

**Steps:**
1. Navigate to `/emissions/factors`
2. See table of all emission factors (Name, Category, Scope, Value, Unit)
3. Filter by: Category, Scope, or search by name
4. Click "Create Factor" → Drawer opens with form:
   - Name (e.g., "US Grid Average 2024")
   - Code (unique, e.g., "US_GRID_2024")
   - Category (dropdown: electricity, mobile_combustion, etc.)
   - Scope (dropdown: 1, 2, 3)
   - Factor Value (decimal, e.g., 0.417)
   - Factor Unit (always "kg CO2e")
   - Activity Unit (e.g., "kWh", "liter", "km")
   - Valid from/to dates
5. Submit → `EmissionFactor` created
6. Edit/Delete → Update or soft-delete (is_active=False)

**Current Capabilities:**
- ✅ Full CRUD with validation
- ✅ Historical versioning via valid_from/valid_to dates
- ✅ Search and filter
- ✅ Admin-only access enforced

---

### Workflow 3: Reporting Period Management (Admins) ✅

**Actors:** Admins

**Steps:**
1. Navigate to `/emissions/periods`
2. See list of reporting periods (Name, Type, Start, End, Status)
3. Click "Create Period" → Form opens:
   - Name (e.g., "FY 2025")
   - Period Type (Annual, Quarterly, Monthly, Custom)
   - Start Date, End Date
   - Status (Draft, Open, Locked, Verified, Closed)
4. Submit → `ReportingPeriod` created
5. **Status transitions:**
   - Draft → Open (opens data entry)
   - Open → Locked (prevents new data, allows review)
   - Locked → Verified (marks as audited)
   - Verified → Closed (finalizes for reporting)

**Current Capabilities:**
- ✅ Full CRUD with date validation
- ✅ Workflow states defined
- ⚠️ **Gap:** No automatic data entry lockout when status != "Open"
- ⚠️ **Gap:** No email notifications on status changes

---

### Workflow 4: Report Generation (Admins) ⚠️

**Actors:** Admins or managers

**Current State:**
1. Navigate to `/emissions/reports` (page exists but incomplete)
2. API endpoint exists: `GET /emissions/report/`
3. Query params:
   - `reporting_period_id` (optional, defaults to current)
   - `module_id` (optional, filter to specific org unit/module)
   - `scope` (optional, filter to Scope 1/2/3)
4. Returns JSON with:
   - `total_co2e_kg` (grand total)
   - `by_scope` (breakdown: Scope 1, 2, 3 totals)
   - `by_category` (electricity, mobile, etc.)
   - `by_module` (org unit totals)

**Gaps:**
- ❌ No CSV export (JSON only)
- ❌ No saved report templates
- ❌ No org_unit_id parameter (uses module_id which is confusing)
- ❌ No comparison to baseline period
- ❌ No chart visualizations

---

## Scoped User Experience: How RBAC Works

### Access Control Model ✅

```
User
  ↓ has
ScopedRole(s)
  ↓ grants access to
OrgUnit(s)
  ↓ contains
Module(s)
  ↓ contains
DataTable(s)
  ↓ contains
DataRow(s) ← User can only see/edit rows in their org unit's modules
```

**Example:**
```
User: alice@aastmt.edu (Data Entry role)
ScopedRole: org_unit_id=5 (Faculty of Medicine)
Visible Modules:
  - Module 10: "Medicine Transportation"
  - Module 11: "Medicine Energy Consumption"
Visible Tables in Module 10:
  - Table 50: "Bus Routes"
  - Table 51: "Vehicle Fuel"
Alice can CRUD rows in Table 50 & 51, but CANNOT see:
  - Module 12: "Engineering Energy" (different org unit)
```

### Frontend Enforcement ✅

**DataEntryPage** ([`carbon-frontend/src/pages/DataEntryPage.jsx`](carbon-frontend/src/pages/DataEntryPage.jsx)):
- Fetches rows: `GET /dataschema/rows/?data_table_id=X`
- Backend filters: `filter(data_table__module__org_unit_id__in=user_org_units)`
- Result: User only sees rows from their org unit

**DataHubHome** ([`carbon-frontend/src/pages/DataHubHome.jsx`](carbon-frontend/src/pages/DataHubHome.jsx)):
- Fetches modules: `GET /core/modules/`
- Backend filters: `filter(org_unit_id__in=user_org_units)`
- Result: User only sees modules in their org unit tree

**Data Owner Dashboard** ([`carbon-frontend/src/pages/data-owner/DataOwnerDashboardPage.jsx`](carbon-frontend/src/pages/data-owner/DataOwnerDashboardPage.jsx)):
- API: `GET /carbon-api/owner/dashboard/`
- Aggregates calculations filtered to user's org units
- Shows: Total CO2e, breakdown by scope, DQ scores

---

## Missing Workflows: Production Gaps

### 1. Scope-Specific Data Entry Forms ❌

**Current:** Generic `DataEntryPage` with arbitrary fields  
**Needed:** Carbon-optimized forms with scope-aware validation

**Example: Scope 1 Mobile Combustion Form**
```
┌───────────────────────────────────────────┐
│ Add Vehicle Fuel Consumption             │
├───────────────────────────────────────────┤
│ Vehicle ID*:        [V001        ▼]      │
│ Fuel Type*:         [Diesel      ▼]      │ ← Dropdown from EmissionFactor
│ Quantity*:          [100.5            ]   │
│ Unit:               liters (auto)         │ ← Auto-filled from factor
│ Activity Date*:     [2025-01-15      📅] │
│ Odometer Reading:   [45678            ]   │
│ Driver:             [John Doe     ▼]      │
│                                           │
│ 📊 Estimated Emission: 269.3 kg CO2e     │ ← Real-time preview
│                                           │
│        [Cancel]          [Save & Calculate] │
└───────────────────────────────────────────┘
```

**Implementation:**
- New page: `/carbon/data-entry/scope1/mobile`
- Form validates: fuel_type must match active EmissionFactor
- On save: Automatically triggers calculation
- Shows preview: activity × factor = estimated emission

---

### 2. Automatic Calculation Triggers ❌

**Current:** Manual API call required  
**Needed:** Auto-calculate on row save

**Trigger Logic:**
```python
# In DataRow.save()
def save(self, *args, **kwargs):
    super().save(*args, **kwargs)
    
    # Auto-calculate if table has calculation rules
    if self.data_table.calculation_rules.exists():
        for rule in self.data_table.calculation_rules.filter(is_active=True):
            create_calculation_from_rule(self, rule)
```

**Benefit:** Users don't need to manually trigger calculations

---

### 3. Workflow State Machine ❌

**Current:** ReportingPeriod has status field, but no enforcement  
**Needed:** State-based access control

**State Transitions:**
```
[Draft] → Admin creates period
   ↓
[Open] → Data entry enabled
   ↓ (Admin clicks "Lock for Review")
[Locked] → Data entry disabled, calculations frozen
   ↓ (Auditor approves)
[Verified] → Calculations certified
   ↓ (Admin closes)
[Closed] → Period archived, data immutable
```

**Enforcement:**
```python
# In DataRow.save()
if self.data_table.module.reporting_period.status != 'open':
    raise ValidationError("Data entry is locked for this period")
```

---

### 4. Scope-Based Aggregation Reports ⚠️

**Current:** JSON report exists, but incomplete  
**Needed:** Full GHG Protocol-compliant report

**Report Structure:**
```
Organization: AASTMT
Reporting Period: FY 2025 (Jan 1 - Dec 31, 2025)
Organizational Boundary: Operational Control

════════════════════════════════════════════════
SCOPE 1: DIRECT EMISSIONS
────────────────────────────────────────────────
Stationary Combustion:
  - Natural Gas (boilers)       1,234 kg CO2e
Mobile Combustion:
  - Diesel (vehicles)             567 kg CO2e
  - Gasoline (fleet)              234 kg CO2e
Fugitive Emissions:
  - Refrigerants (HVAC)            89 kg CO2e
────────────────────────────────────────────────
Scope 1 Total:                  2,124 kg CO2e

════════════════════════════════════════════════
SCOPE 2: INDIRECT ENERGY EMISSIONS
────────────────────────────────────────────────
Location-Based Method:
  - Grid Electricity            5,678 kg CO2e
Market-Based Method:
  - Grid Electricity            5,234 kg CO2e
  - Renewable Certificates       -200 kg CO2e
────────────────────────────────────────────────
Scope 2 Total (Location):       5,678 kg CO2e
Scope 2 Total (Market):         5,034 kg CO2e

════════════════════════════════════════════════
SCOPE 3: VALUE CHAIN EMISSIONS
────────────────────────────────────────────────
Category 6 - Business Travel:
  - Flights (domestic)            345 kg CO2e
  - Flights (international)       678 kg CO2e
Category 7 - Employee Commuting:
  - Personal vehicles           1,234 kg CO2e
────────────────────────────────────────────────
Scope 3 Total:                  2,257 kg CO2e

════════════════════════════════════════════════
TOTAL EMISSIONS (Location):     9,059 kg CO2e
TOTAL EMISSIONS (Market):       9,415 kg CO2e
════════════════════════════════════════════════

Comparison to Baseline (FY 2024):
  Scope 1: +5.2% (2,124 vs 2,018 kg CO2e)
  Scope 2: -2.1% (5,678 vs 5,800 kg CO2e)
  Scope 3: +12.3% (2,257 vs 2,010 kg CO2e)
  Total: +3.8% (9,059 vs 8,828 kg CO2e)
```

**Implementation:** Enhance `ReportAPIView` with full GHG Protocol structure

---

### 5. Data Quality Integration ⚠️

**Current:** DQ engine exists, but not integrated into carbon workflow  
**Needed:** Automatic quality checks on emission data

**Quality Rules for Carbon:**
```python
# Completeness: All required fields filled
DQRule(
    name="Scope 1 Fuel Data Complete",
    rule_type="not_null",
    data_field=field("fuel_quantity"),
    params={"severity": "critical"}
)

# Range: Reasonable values
DQRule(
    name="Fuel Quantity Within Expected Range",
    rule_type="range",
    data_field=field("fuel_quantity"),
    params={"min": 0, "max": 10000, "unit": "liters"}
)

# Reference Integrity: Fuel type exists in EmissionFactor
DQRule(
    name="Valid Fuel Type",
    rule_type="reference_integrity",
    data_field=field("fuel_type"),
    params={"reference_table": "EmissionFactor", "reference_field": "code"}
)
```

**Workflow Integration:**
- Run DQ checks on DataRow save
- Block calculation if critical rules fail
- Show quality warnings in data entry UI

---

## Recommended Implementation Priority

### Phase 1: Core Carbon Workflows (Week 1-2)
1. **Scope-specific data entry forms** (3 forms: Scope 1 mobile, Scope 1 stationary, Scope 2 electricity)
2. **Automatic calculation triggers** (on DataRow save, if calculation rules exist)
3. **Enhanced report export** (CSV format + org_unit filter)
4. **Reporting period enforcement** (block data entry when status != "open")

### Phase 2: Advanced Features (Week 3-4)
5. **Workflow state transitions** (email notifications, approval pipeline)
6. **Scope 3 expansion** (map all 15 categories, add spend-based method)
7. **Data quality integration** (automatic DQ checks on save, quality dashboard)
8. **Baseline comparison** (year-over-year trends, variance analysis)

### Phase 3: Production Hardening (Week 5-6)
9. **Bulk import/export** (CSV upload for activity data, bulk calculation)
10. **Audit trail enhancements** (track all changes, approval history)
11. **Performance optimization** (caching, query tuning for large datasets)
12. **User documentation** (video tutorials, step-by-step guides)

---

## Next Steps

To proceed with defining the exact workflows, I need clarity on:

1. **Data collection method:** Will users enter data row-by-row, or do you want bulk CSV import?
2. **Calculation timing:** Should calculations happen immediately on save, or batched (e.g., nightly)?
3. **Approval workflow:** Do emissions need manager/auditor approval before being finalized?
4. **Reporting frequency:** How often will users generate reports? (monthly, quarterly, annually)
5. **Scope 3 priority:** Which of the 15 Scope 3 categories are most critical for AASTMT?

Once you answer these, I can create detailed process diagrams and implementation specs for the carbon-specific workflows.

---

**Document Version:** 1.0  
**Last Updated:** 2026-07-25  
**Status:** Ready for stakeholder review