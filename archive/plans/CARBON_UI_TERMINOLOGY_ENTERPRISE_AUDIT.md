# Carbon UI & Terminology — Enterprise Best Practices Audit

**Date:** 2026-07-25  
**Purpose:** Audit current UI naming/menus against enterprise carbon/sustainability platforms  
**Philosophy:** Carbon sits on top of Data Trust Platform as a domain app  

---

## Current State Analysis

### Current UI Structure
```
Sidebar (carbon-frontend/src/components/SidebarMenu.jsx):
├── Scope 1 (Direct emissions)
│   ├── Module: Vehicle Fleet
│   ├── Module: Natural Gas
│   └── Tables...
├── Scope 2 (Indirect energy)
│   ├── Module: Electricity
│   └── Tables...
├── Scope 3 (Value chain)
│   ├── Module: Business Travel
│   └── Tables...
└── Apps:
    ├── Executive Summary
    ├── Emission Factors
    ├── Report Generator
    └── Saved Reports

Data Owner View (carbon-frontend/src/components/SidebarMenu.jsx):
├── Portal (Overview of domain assets)
├── Dashboard (Emissions KPIs)
├── Assets (Scoped asset browser)
```

### Current Terminology Issues

| Current Term | Issue | Enterprise Standard |
|--------------|-------|---------------------|
| "Data Entry" | Too generic, not carbon-specific | "Activity Data Collection" or "Emissions Data Entry" |
| "Data Hub Home" | Platform terminology, not domain-specific | "Carbon Management Console" or "Inventory Management" |
| "Modules" | Platform jargon, confusing to carbon users | "Emission Sources" or "Data Collection Areas" |
| "Tables" | Technical database term | "Activity Datasets" or "Emission Records" |
| "Emission Factors" | ✅ Correct | Industry standard (keep) |
| "Report Generator" | ✅ Good | Common term (keep) |
| "Executive Summary" | Too generic | "Carbon Footprint Dashboard" or "GHG Inventory Overview" |
| "Data Owner" | Platform role, not carbon domain | "Facility Manager" or "Site Coordinator" |
| "/carbon/" URL | ✅ Good | Better than /emissions/ |
| "Scope 1/2/3" labels | ✅ Correct | GHG Protocol standard (keep) |

---

## Enterprise Carbon Platform Benchmarking

### Leading Enterprise Platforms

#### 1. **Watershed** (watershed.com)
```
Navigation:
├── Dashboard
├── Footprint
│   ├── Activity Data
│   ├── Emission Factors
│   └── Suppliers
├── Reports
│   ├── Inventory Report
│   ├── Climate Disclosures
│   └── Analytics
├── Goals & Targets
├── Offsets & RECs
└── Settings
```

**Key Terms:**
- "Footprint" (not "emissions")
- "Activity Data" (not "data entry")
- "Inventory Report" (GHG Protocol term)
- "Climate Disclosures" (TCFD/CDP terminology)

#### 2. **Persefoni** (persefoni.com)
```
Navigation:
├── Home
├── Carbon Inventory
│   ├── Activity Data
│   ├── Calculation Engine
│   └── Data Quality
├── Reporting
│   ├── GHG Inventory
│   ├── CDP Response
│   └── TCFD Report
├── Target Setting
├── Reduction Initiatives
└── Assurance
```

**Key Terms:**
- "Carbon Inventory" (central concept)
- "Calculation Engine" (transparent process)
- "Assurance" (third-party verification)
- "Reduction Initiatives" (action-oriented)

#### 3. **Enablon (Wolters Kluwer)** (enablon.com)
```
Navigation:
├── Dashboard
├── Environmental Data Collection
│   ├── Emissions
│   ├── Energy
│   ├── Waste
│   └── Water
├── GHG Accounting
│   ├── Scope 1 Direct
│   ├── Scope 2 Indirect Energy
│   └── Scope 3 Value Chain
├── Sustainability Reporting
│   ├── Annual Report
│   ├── CDP Submission
│   └── ESG Disclosures
└── Performance Management
```

**Key Terms:**
- "Environmental Data Collection" (broader than carbon)
- "GHG Accounting" (financial analogy)
- "Sustainability Reporting" (not just carbon)
- "ESG Disclosures" (investor terminology)

#### 4. **Measurabl** (measurabl.com)
```
Navigation:
├── Portfolio Dashboard
├── Data Management
│   ├── Energy & Utilities
│   ├── Waste & Water
│   └── Tenant Surveys
├── Carbon & GHG
│   ├── Emissions Inventory
│   ├── Emission Factors
│   └── Renewable Energy
├── ESG Reporting
│   ├── GRESB
│   ├── ENERGY STAR
│   └── Custom Reports
└── Certifications
```

**Key Terms:**
- "Portfolio Dashboard" (asset-centric for real estate)
- "Data Management" (platform capability)
- "Emissions Inventory" (GHG Protocol)
- "Certifications" (LEED, ENERGY STAR badges)

#### 5. **Greenly** (greenly.earth)
```
Navigation (French/English):
├── Tableau de bord / Dashboard
├── Bilan Carbone / Carbon Footprint
│   ├── Collecte de données / Data Collection
│   ├── Facteurs d'émission / Emission Factors
│   └── Résultats / Results
├── Plans d'action / Action Plans
├── Rapports / Reports
│   ├── Réglementaire / Regulatory
│   └── Personnalisé / Custom
└── Formation / Training
```

**Key Terms:**
- "Bilan Carbone" (French standard, = Carbon Footprint)
- "Plans d'action" (reduction strategies)
- "Réglementaire" (regulatory compliance)
- "Formation" (user training/onboarding)

---

## Gap Analysis: Current vs. Enterprise Standard

### Critical Gaps

#### Gap 1: No Carbon-Specific Landing Page
**Current:** Users land on generic "Data Hub Home"  
**Enterprise Standard:** Dedicated "Carbon Management Console" or "GHG Inventory Dashboard"

**Impact:** Users don't immediately understand this is a carbon platform

**Fix:**
```
NEW: Carbon Management Console (/carbon/console)
├── Quick Stats: Total Footprint, YoY Change, Data Completeness
├── Recent Activity: Latest submissions, pending approvals
├── Shortcuts: Enter Activity Data, View Reports, Manage Factors
└── Alerts: Period closing, missing data, factor updates
```

#### Gap 2: Generic "Data Entry" Terminology
**Current:** "Data Entry" link in sidebar  
**Enterprise Standard:** "Activity Data Collection" or "Emissions Data Entry"

**Impact:** Doesn't communicate carbon domain clearly

**Fix:**
```
RENAME: 
- "Data Entry" → "Activity Data Collection"
- "Data Hub Home" → "Carbon Console" or "Inventory Management"
- "/carbon/data-entry" → "/carbon/activity-data" or "/carbon/collect"
```

#### Gap 3: Missing Key Carbon Navigation Categories
**Current:** Flat list of Scope 1/2/3 modules  
**Enterprise Standard:** Grouped by workflow stage (Collect → Calculate → Report → Act)

**Impact:** Navigation doesn't reflect carbon workflow

**Fix:**
```
NEW SIDEBAR STRUCTURE:

Carbon (Domain App)
├── 📊 Overview
│   ├── Carbon Console (landing page)
│   └── GHG Inventory Dashboard
├── 📥 Collect
│   ├── Activity Data Entry
│   │   ├── Scope 1 Sources
│   │   ├── Scope 2 Sources
│   │   └── Scope 3 Sources
│   ├── Bulk Import (CSV)
│   └── Data Quality Review
├── 🧮 Calculate
│   ├── Emission Factors Library
│   ├── Calculation Engine (trigger)
│   └── GWP Configuration
├── 📈 Report
│   ├── Reporting Periods
│   ├── GHG Inventory Report
│   ├── Report Generator
│   └── Saved Reports
├── 🎯 Act (Future)
│   ├── Reduction Targets
│   ├── Action Plans
│   └── Progress Tracking
└── ⚙️ Settings
    ├── Organization Structure
    ├── User Roles
    └── Emission Sources Registry
```

#### Gap 4: No Breadcrumb Context
**Current:** Users navigate without clear workflow context  
**Enterprise Standard:** Breadcrumbs show: Console > Collect > Scope 1 > Vehicle Fleet

**Impact:** Users get lost in deep navigation

**Fix:**
```jsx
// Add to all carbon pages
<Breadcrumbs>
  <Link to="/carbon/console">Carbon Console</Link>
  <Link to="/carbon/collect">Collect</Link>
  <Link to="/carbon/collect/scope1">Scope 1 Direct Emissions</Link>
  <Typography color="text.primary">Vehicle Fleet</Typography>
</Breadcrumbs>
```

#### Gap 5: Technical Jargon in User-Facing UI
**Current:**
- "Modules" (platform term)
- "Tables" (database term)
- "Data Rows" (technical term)
- "Asset Profile" (catalog jargon)

**Enterprise Standard:**
- "Emission Sources" (domain term)
- "Activity Datasets" (carbon term)
- "Emission Records" (user-friendly)
- "Source Configuration" (carbon context)

**Impact:** Confuses non-technical carbon managers

**Fix:** UI translation layer

```jsx
// carbon-frontend/src/utils/terminology.js
export const CARBON_TERMINOLOGY = {
  platform: {
    module: 'Emission Source',
    table: 'Activity Dataset',
    row: 'Emission Record',
    data_entry: 'Activity Data Collection',
  },
  
  // Preserve technical terms in API/backend
  api: {
    module: 'module',
    table: 'data_table',
    row: 'data_row',
  },
};

// Use in UI
<Typography>{CARBON_TERMINOLOGY.platform.module}</Typography> // "Emission Source"
```

#### Gap 6: Missing "Why" Context for Carbon Users
**Current:** Assumes users understand GHG Protocol  
**Enterprise Standard:** Inline help, tooltips, contextual guidance

**Impact:** Steep learning curve for new users

**Fix:**
```jsx
// Add contextual help everywhere
<Tooltip title="Scope 1 covers direct emissions from sources you own or control, like company vehicles and on-site fuel combustion">
  <InfoIcon fontSize="small" color="action" />
</Tooltip>

// Add "Learn More" links
<Link to="/carbon/help/scope1-guide">
  What qualifies as Scope 1?
</Link>
```

#### Gap 7: No Progress Indicators
**Current:** Users don't know completion status  
**Enterprise Standard:** Progress bars, completion %, status badges

**Impact:** Users don't know if they're done

**Fix:**
```jsx
// Carbon Console - show progress
<Card title="January 2025 Reporting Period">
  <LinearProgress value={65} />
  <Typography>65% complete • 3 of 8 facilities submitted</Typography>
  
  <List>
    <ListItem>
      <Chip label="Complete" color="success" /> Scope 1: Direct Emissions
    </ListItem>
    <ListItem>
      <Chip label="In Progress" color="warning" /> Scope 2: Energy
    </ListItem>
    <ListItem>
      <Chip label="Not Started" color="default" /> Scope 3: Travel
    </ListItem>
  </List>
</Card>
```

---

## Recommended Enterprise Terminology

### Primary Navigation Labels

| Current | Recommended | Rationale |
|---------|-------------|-----------|
| Data Hub Home | **Carbon Console** | Central command center metaphor |
| Data Entry | **Activity Data** | GHG Protocol term |
| Modules | **Emission Sources** | Carbon domain language |
| Tables | **Activity Datasets** | User-friendly term |
| Executive Summary | **GHG Inventory Dashboard** | Industry standard |
| Emission Factors | **Emission Factors Library** | More descriptive |
| Report Generator | **Reporting & Disclosures** | Broader scope |
| Saved Reports | **Report Archive** | Clearer purpose |

### Page Titles

| Current | Recommended |
|---------|-------------|
| "DataEntryPage" | "Activity Data Collection" |
| "ModuleLandingPage" | "Emission Source Overview" |
| "TableDetailPage" | "Activity Dataset: [Name]" |
| "EmissionsDashboard" | "GHG Inventory Dashboard" |
| "EmissionsReport" | "GHG Inventory Report" |
| "DataOwnerDashboard" | "Facility Dashboard" or "Site Overview" |

### Workflow Stage Labels

| Stage | Label | Description |
|-------|-------|-------------|
| 1 | **Collect** | Gather activity data (fuel, electricity, travel) |
| 2 | **Calculate** | Apply emission factors → CO2e |
| 3 | **Review** | Data quality checks, verify calculations |
| 4 | **Report** | Generate GHG inventory, disclosures |
| 5 | **Act** | Set targets, track reduction initiatives |

### Role Labels

| Platform Role | Carbon Domain Label |
|---------------|---------------------|
| Data Owner | **Facility Manager** or **Site Coordinator** |
| Admin | **Carbon Program Manager** or **Sustainability Lead** |
| Viewer | **Stakeholder** or **Reporter** |
| Auditor | **Assurance Provider** or **Verifier** |

---

## Recommended UI Information Architecture

### Top-Level Navigation (Sidebar)

```
🌍 Carbon Management
├── 🏠 Console (landing page)
│   Quick stats, recent activity, alerts
│
├── 📥 COLLECT Activity Data
│   ├── Scope 1: Direct Emissions
│   │   ├── Stationary Combustion
│   │   │   └── [List of facilities/sources]
│   │   ├── Mobile Combustion
│   │   │   └── [List of vehicle fleets]
│   │   └── Fugitive Emissions
│   │       └── [List of refrigeration systems]
│   │
│   ├── Scope 2: Indirect Energy
│   │   ├── Purchased Electricity
│   │   │   └── [List of buildings/meters]
│   │   ├── Purchased Steam
│   │   └── Purchased Heating/Cooling
│   │
│   ├── Scope 3: Value Chain
│   │   ├── Category 1: Purchased Goods
│   │   ├── Category 3: Fuel/Energy Activities
│   │   ├── Category 6: Business Travel
│   │   └── Category 7: Employee Commuting
│   │
│   └── 📤 Bulk Import (CSV templates)
│
├── 🧮 CALCULATE Emissions
│   ├── Emission Factors Library
│   ├── Calculation Engine (manual trigger)
│   ├── GWP Configuration
│   └── Calculation History
│
├── 📊 MONITOR Data Quality
│   ├── Data Completeness
│   ├── Outlier Detection
│   ├── Validation Rules
│   └── Quality Score
│
├── 📈 REPORT & Disclose
│   ├── Reporting Periods
│   ├── GHG Inventory Report
│   │   ├── Annual Inventory
│   │   ├── Quarterly Summary
│   │   └── Custom Date Range
│   │
│   ├── Regulatory Disclosures
│   │   ├── CDP Climate Response
│   │   ├── TCFD Report
│   │   └── National Registry Submission
│   │
│   └── Report Archive
│
├── 🎯 TARGETS & Actions (Future Phase)
│   ├── Science-Based Targets
│   ├── Reduction Initiatives
│   ├── Progress Tracking
│   └── ROI Calculator
│
└── ⚙️ SETTINGS
    ├── Organization Structure
    ├── Emission Sources Registry
    ├── User Roles & Permissions
    └── Reporting Period Configuration
```

### Breadcrumb Examples

```
Console > Collect > Scope 1 Direct Emissions > Mobile Combustion > Vehicle Fleet

Console > Calculate > Emission Factors Library > Scope 2 Electricity

Console > Report > GHG Inventory Report > Annual 2025

Console > Settings > Emission Sources Registry > Add New Source
```

### Status Indicators

```jsx
// Reporting Period Status
<Chip label="Open for Submissions" color="success" icon={<LockOpen />} />
<Chip label="Locked for Review" color="warning" icon={<Lock />} />
<Chip label="Verified & Closed" color="info" icon={<CheckCircle />} />

// Data Quality Status
<Chip label="Complete" color="success" />  // 100% data submitted
<Chip label="In Progress" color="warning" />  // 50-99% complete
<Chip label="Not Started" color="default" />  // 0% complete
<Chip label="Quality Issues" color="error" />  // Has DQ failures

// Calculation Status
<Chip label="Calculated" color="success" icon={<Calculate />} />
<Chip label="Pending Calculation" color="warning" />
<Chip label="Calculation Error" color="error" />
```

---

## Implementation Recommendations

### Phase 1: Quick Wins (1 week)
1. **Rename key pages:**
   - "Data Entry" → "Activity Data"
   - "Emission Factors" → "Emission Factors Library"
   - "Executive Summary" → "GHG Inventory Dashboard"

2. **Add breadcrumbs** to all carbon pages

3. **Add page descriptions** under titles:
   ```jsx
   <Typography variant="h4">Activity Data Collection</Typography>
   <Typography variant="body2" color="text.secondary">
     Enter fuel consumption, electricity usage, and travel data for emissions calculation
   </Typography>
   ```

4. **Add tooltips** to Scope labels in sidebar:
   ```jsx
   <Tooltip title="Direct emissions from sources you own or control">
     <ListItemText primary="Scope 1: Direct Emissions" />
   </Tooltip>
   ```

### Phase 2: UI Restructure (2 weeks)
1. **Create Carbon Console landing page** at `/carbon/console`
2. **Reorganize sidebar** into workflow stages (Collect → Calculate → Report)
3. **Add progress indicators** to reporting periods
4. **Create contextual help system** (inline tooltips, help links)

### Phase 3: Terminology Translation Layer (1 week)
1. **Create `carbon-terminology.js`** utility
2. **Replace all "Module" → "Emission Source" in UI**
3. **Replace all "Table" → "Activity Dataset" in UI**
4. **Keep technical terms in API/backend** (no breaking changes)

### Phase 4: Advanced Features (2-3 weeks)
1. **Add "Targets & Actions" section** (future phase)
2. **Add "Regulatory Disclosures" templates** (CDP, TCFD)
3. **Add "Assurance" workflow** (third-party verification)
4. **Add "Carbon Console" widgets** (customizable dashboard)

---

## URL Structure Recommendations

### Current vs. Recommended

| Current URL | Recommended URL | Notes |
|-------------|-----------------|-------|
| `/carbon/data-entry` | `/carbon/collect` or `/carbon/activity-data` | Shorter, clearer |
| `/carbon/data-entry/module/:id` | `/carbon/collect/source/:id` | Domain terminology |
| `/dataschema/entry/:moduleId/:tableId` | `/carbon/collect/scope1/:sourceId/:datasetId` | Carbon-specific |
| `/emissions/factors` | `/carbon/factors` | Consistency |
| `/emissions/report` | `/carbon/report/inventory` | Clearer purpose |
| `/data-owner/portal` | `/carbon/facility` or `/carbon/site` | Domain role |

### Recommended URL Hierarchy

```
/carbon/
├── console                    # Landing page
├── collect/
│   ├── scope1/:sourceId
│   ├── scope2/:sourceId
│   ├── scope3/:sourceId
│   └── import                 # Bulk CSV
├── calculate/
│   ├── factors                # Emission Factors Library
│   ├── trigger                # Manual calculation
│   └── history
├── quality/
│   ├── completeness
│   ├── outliers
│   └── rules
├── report/
│   ├── periods
│   ├── inventory/:periodId    # GHG Inventory Report
│   ├── disclosures            # CDP, TCFD
│   └── archive
├── targets/                   # Future
│   ├── sbt                    # Science-Based Targets
│   ├── initiatives
│   └── progress
└── settings/
    ├── sources                # Emission Sources Registry
    ├── periods
    └── users
```

---

## Color Palette Recommendations

### Enterprise Carbon Platforms Use:
- **Primary:** Green shades (#10b981 to #059669) — sustainability
- **Scope 1:** Red/Orange (#ef4444 to #f97316) — direct fire/combustion
- **Scope 2:** Blue (#3b82f6 to #2563eb) — energy/electricity
- **Scope 3:** Purple/Teal (#8b5cf6 to #14b8a6) — value chain
- **Success:** Emerald green (#10b981)
- **Warning:** Amber (#f59e0b)
- **Error:** Red (#ef4444)

**Current Implementation:** ✅ Already follows this pattern (keep)

---

## Summary: Enterprise Best Practices

### What Enterprises Do Well

1. **Workflow-Based Navigation:** Collect → Calculate → Report → Act
2. **Clear Progress Indicators:** "65% complete, 3 of 8 facilities"
3. **Contextual Help:** Tooltips, inline guidance, "Learn More" links
4. **Domain-Specific Terminology:** "Activity Data" not "Data Entry"
5. **Role-Specific Views:** "Facility Manager" not "Data Owner"
6. **Status Transparency:** Chips for period status, data completeness
7. **Breadcrumb Context:** Always show where you are in the workflow
8. **Landing Page:** Dedicated "Console" or "Dashboard" as entry point

### What Our Platform Does Well ✅

1. **Scope-based organization** (Scope 1/2/3 in sidebar)
2. **Color coding** for scopes (green/blue/orange)
3. **RBAC scoping** (org-unit filtering)
4. **Technical foundation** (platform + domain separation)

### Critical Gaps to Fix

1. ❌ **No Carbon Console landing page**
2. ❌ **Generic terminology** ("Data Entry", "Modules", "Tables")
3. ❌ **Missing workflow stages** (Collect → Calculate → Report)
4. ❌ **No progress indicators**
5. ❌ **No breadcrumbs**
6. ❌ **No contextual help**
7. ❌ **Technical jargon** in user-facing UI

---

## Next Steps

1. **User Approval:** Review terminology recommendations
2. **Prioritize:** Which gaps to fix first (suggest Phase 1 + 2)
3. **Implementation:** 2-3 week sprint for UI restructure
4. **Testing:** User acceptance testing with carbon managers
5. **Rollout:** Gradual migration from current to new terminology

**Key Decision:** Should we implement Phase 1 (quick wins) immediately, or wait for full UI restructure (Phase 2)?
