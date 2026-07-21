# TASK: Schema Manager UI Enhancement - Governance Features

**Task ID:** A-SCHEMA-GOV-UI  
**Status:** Planning  
**Priority:** HIGH  
**Scope:** Frontend UI to expose existing backend governance features

---

## 📋 EXECUTIVE SUMMARY

The Carbon platform has a **complete backend data governance system** (78% implemented) but the Schema Manager UI only exposes 15% of these features. This task adds the missing UI tabs and components to make governance, data quality, and audit features accessible to users.

**Deliverable:** Enhanced `SchemaDetailPage.jsx` with 4 new tabs + 4 new manager components

---

## 🎯 ACCEPTANCE CRITERIA

### **AC1: DQ Rules Tab Implemented** ✓
- [ ] New tab in SchemaDetailPage: `[DQ Rules]`
- [ ] Show list of all DQ rules for this table
- [ ] Display columns: Rule Name, Type, Severity, Scope, Last Run, Status
- [ ] [+ Add Rule] button opens DQRuleDialog
- [ ] [Edit] icon on each rule → opens editor
- [ ] [Delete] icon on each rule → confirms delete
- [ ] Show "No rules defined" message if empty
- [ ] Real-time loading/error handling

### **AC2: DQ Rule Dialog (Create/Edit)** ✓
- [ ] Modal form for creating/editing DQ rules
- [ ] Fields:
  - Name (text, required)
  - Rule Type (dropdown: not_null, unique, allowed_values, range, regex)
  - Scope (radio: table-level or field-level)
  - Target Field (dropdown, required if field-level, optional if table-level)
  - Severity (dropdown: info, warn, error)
  - Parameters (JSON editor or type-specific inputs)
  - Active toggle
- [ ] Submit calls backend API
- [ ] Close after successful save
- [ ] Show error messages on failure

### **AC3: Governance Tab Implemented** ✓
- [ ] New tab in SchemaDetailPage: `[Governance]`
- [ ] Display form with fields:
  - Classification (dropdown: public, internal, confidential, pii, sensitive)
  - Domain (dropdown, fetched from backend)
  - Owner (text/lookup)
  - Steward (text/lookup)
  - Tags (multi-select or chip input)
  - Quality Status (read-only badge: unknown, passing, warning, failing)
  - Quality Score (read-only: 0-100)
- [ ] [Edit] button → enables form fields
- [ ] [Save] button → submits to backend
- [ ] Show "Not classified" message if no profile exists
- [ ] Real-time loading/error handling

### **AC4: Audit History Tab Implemented** ✓
- [ ] New tab in SchemaDetailPage: `[Audit History]`
- [ ] Show two sections:
  - **Schema Changes** (from SchemaChangeLog)
    - Columns: Date, User, Action, Field/Table, Before, After
    - Filter by action (add/edit/delete/archive/restore)
  - **Governance Events** (from GovernanceEvent)
    - Columns: Date, User, Action, Details
- [ ] Sort by date descending (newest first)
- [ ] Pagination or lazy load if > 50 items
- [ ] Before/After JSON displayed in readable format (collapsible)
- [ ] Real-time loading/error handling

### **AC5: Quality Metrics Tab (Optional Phase 2)** ⏸
- [ ] New tab in SchemaDetailPage: `[Quality]`
- [ ] Display cards:
  - Table Quality Score (large badge)
  - Completeness % (progress bar)
  - Row Count
  - Last Profiled Date
- [ ] Per-field metrics table:
  - Field Name, Type, Completeness %, Null Count, Distinct Count, Min/Max values
- [ ] Real-time loading/error handling

---

## 🏗️ TECHNICAL IMPLEMENTATION

### **Files to Create/Modify**

**New Components:**
1. `carbon-frontend/src/components/dataschema/DQRulesTab.jsx` (300 lines)
   - Display list of DQ rules
   - Pass callbacks for add/edit/delete

2. `carbon-frontend/src/components/dataschema/DQRuleDialog.jsx` (400 lines)
   - Form for creating/editing rules
   - Dynamic params input based on rule type

3. `carbon-frontend/src/components/dataschema/GovernanceTab.jsx` (350 lines)
   - Display governance data (classification, owner, steward)
   - Edit mode toggle

4. `carbon-frontend/src/components/dataschema/AuditHistoryTab.jsx` (400 lines)
   - Display schema changes + governance events
   - Collapsible before/after JSON

5. `carbon-frontend/src/components/dataschema/QualityMetricsTab.jsx` (300 lines) [Optional]
   - Display quality profile
   - Per-field statistics

**Modified Files:**
1. `carbon-frontend/src/pages/catalog/SchemaDetailPage.jsx`
   - Import new tab components
   - Add tab navigation (MUI Tabs)
   - Add state management for new tabs
   - Add API calls for new data

---

### **API Endpoints to Use**

Backend APIs already exist and are ready:

```javascript
// DQ Rules
GET    /carbon-api/dq/rules/?data_table=X
POST   /carbon-api/dq/rules/
PATCH  /carbon-api/dq/rules/{id}/
DELETE /carbon-api/dq/rules/{id}/

// Asset Profile (Governance)
GET    /carbon-api/catalog/assets/?data_table=X
POST   /carbon-api/catalog/assets/
PATCH  /carbon-api/catalog/assets/{id}/
DELETE /carbon-api/catalog/assets/{id}/

// Governance Events (Audit)
GET    /carbon-api/catalog/governance/?asset_id=X

// Schema Change Log
GET    /carbon-api/dataschema/schema-logs/?data_table=X

// Reference Data
GET    /carbon-api/catalog/domains/  (for classification)
GET    /carbon-api/mdm/reference-sets/  (for lookups)

// Quality Metrics (optional)
GET    /carbon-api/dq/metrics/table/{tableId}/
```

---

### **API Request/Response Examples**

**DQ Rules:**
```javascript
// GET /dq/rules/?data_table=1
[
  {
    "id": 1,
    "name": "Bus Type Valid",
    "rule_type": "allowed_values",
    "severity": "error",
    "scope": "field",
    "data_field": 5,
    "params": {"allowed": ["electric", "diesel"]},
    "is_active": true,
    "created_at": "2026-07-20T...",
    "results": [
      {"passed": true, "failed_count": 0, "run_at": "2026-07-20T..."}
    ]
  }
]

// POST /dq/rules/ (create)
{
  "data_table": 1,
  "name": "Route ID Unique",
  "rule_type": "unique",
  "severity": "error",
  "scope": "field",
  "data_field": 3,
  "params": {},
  "is_active": true
}
```

**Asset Profile (Governance):**
```javascript
// GET /catalog/assets/?data_table=1
{
  "id": 1,
  "data_table": 1,
  "classification": "internal",
  "domain": 2,
  "owner": "transport_steward",
  "steward": "data_owner",
  "quality_status": "passing",
  "quality_score": 95,
  "tags": ["critical", "daily-update"]
}

// PATCH /catalog/assets/1/
{
  "classification": "confidential",
  "owner": "transport_admin",
  "steward": "chief_data_officer",
  "quality_status": "warning"
}
```

**Governance Events:**
```javascript
// GET /catalog/governance/?asset_id=1
[
  {
    "id": 1,
    "entity_type": "AssetProfile",
    "entity_id": 1,
    "action": "update",
    "user": "admin",
    "timestamp": "2026-07-20T08:00:00Z",
    "before": {"classification": "public"},
    "after": {"classification": "internal"}
  }
]
```

---

## 📐 UI MOCKUP

```
┌──────────────────────────────────────────────────────────────────┐
│ Bus Routes Schema Detail                                          │
│ [Edit Metadata] [Lock] [Archive]                                 │
├─────────────────────────────────────────────────────────────────┤
│ [Overview] [Fields] [Relations] [Quality] [Governance] [Rules] [Audit] │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ TAB: DQ RULES                                                     │
│                                                                   │
│   [+ Add Rule]                                                    │
│                                                                   │
│   Name               | Type           | Severity | Scope    | ... │
│   ─────────────────────────────────────────────────────────      │
│   Bus Type Valid     | allowed_values | error    | field    | ✎ ✕│
│   Route ID Unique    | unique         | error    | field    | ✎ ✕│
│   Has Description    | not_null       | warn     | field    | ✎ ✕│
│                                                                   │
│ TAB: GOVERNANCE                                                   │
│                                                                   │
│   Classification: [Internal ▼]                                    │
│   Domain: [Transportation ▼]                                      │
│   Owner: [transport_steward _]  [Edit]                           │
│   Steward: [chief_data_officer _]                                │
│   Tags: [critical] [daily-update] [+ Add]                        │
│   Quality: [Passing] 95/100                                       │
│                                                                   │
│ TAB: AUDIT HISTORY                                                │
│                                                                   │
│   📋 Schema Changes                                               │
│   ─────────────────────────────────────────────────────────      │
│   2026-07-20 10:15  | admin    | edit   | Table: added description│
│   2026-07-15 14:22  | admin    | add    | Field: route_id        │
│                                                                   │
│   📊 Governance Events                                            │
│   ─────────────────────────────────────────────────────────      │
│   2026-07-19 09:00  | steward  | update | classification        │
│                     |          |        | public → internal      │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📊 IMPLEMENTATION PHASES

### **Phase 1: Core Governance (1 week)** ← START HERE
- [ ] DQ Rules Tab + Dialog
- [ ] Governance Tab (classification, owner, steward)
- [ ] Audit History Tab

### **Phase 2: Enhanced Features (1 week)**
- [ ] Quality Metrics Tab
- [ ] Relations Tab: Add [+ Create Relation] button

### **Phase 3: Polish (3 days)**
- [ ] Schema locking UI
- [ ] Version management
- [ ] Archive/restore buttons

---

## ✅ TESTING CHECKLIST

- [ ] Tab navigation works (no console errors)
- [ ] Data loads on tab change (loading spinner visible)
- [ ] DQ Rules CRUD fully functional
- [ ] Governance classification saves to backend
- [ ] Audit history displays correctly (sorted by date)
- [ ] JSON diffs readable and collapsible
- [ ] Error messages show on API failures
- [ ] Responsive on mobile/tablet
- [ ] No broken links or 404s
- [ ] API errors handled gracefully

---

## 📚 REFERENCE DOCUMENTATION

- **Backend Models:** [`backend/dq/models.py`](backend/dq/models.py), [`backend/catalog/models.py`](backend/catalog/models.py), [`backend/dataschema/models.py`](backend/dataschema/models.py:110-132)
- **Current Implementation:** [`carbon-frontend/src/pages/catalog/SchemaDetailPage.jsx`](carbon-frontend/src/pages/catalog/SchemaDetailPage.jsx)
- **Related Tabs:** See GovernancePage, SchemaCatalogPage for similar patterns
- **Audit Report:** [`plans/SCHEMA_MANAGER_UI_GAP_ANALYSIS.md`](plans/SCHEMA_MANAGER_UI_GAP_ANALYSIS.md)

---

## 🎬 EXECUTION PROTOCOL

**Mode:** Code  
**Effort:** 2 weeks (Phase 1 + 2)  
**Skill Level:** Senior Frontend (React, MUI, API integration)  

**Start with Phase 1 (core governance features).**  
**Report blockers via GitHub Issues.**

---

## 🔗 RELATED TASKS

- **A-SCHEMA-GOV-API:** Backend API validation (completed ✅)
- **A-SCHEMA-GOV-TESTS:** Add E2E tests for new features
- **A-SCHEMA-LINEAGE-VIZ:** Data lineage visualization (future)

---

**Next:** Provide this prompt to worker in Code mode.