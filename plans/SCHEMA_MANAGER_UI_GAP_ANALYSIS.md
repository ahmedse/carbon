# Schema Manager UI Gap Analysis

**Problem:** The Schema Manager page doesn't expose all the governance features that exist in the backend.

**Date:** 2026-07-20  
**Status:** UI Coverage Gap Identified

---

## 📊 BACKEND vs FRONTEND MISMATCH

### **What Backend Supports (Database Models)**

```
✅ DataTable (schema definition)
✅ DataField (9 field types with validation)
✅ DQRule (5 rule types: not_null, unique, allowed_values, range, regex)
✅ DQResult (rule execution tracking)
✅ TableProfile / FieldProfile (quality metrics)
✅ AssetProfile (governance: classification, owner, steward, domain)
✅ GovernanceEvent (audit trail)
✅ SchemaChangeLog (schema change history)
✅ TableRelation (table relationships & lineage)
✅ ReferenceSet (controlled vocabularies)
```

### **What Frontend Shows (Current UI)**

**SchemaManagerPage.jsx** (`/catalog/schema-manager`):
- ✅ List all tables
- ✅ Create table (title, description only)
- ✅ Edit table metadata (title, description)
- ✅ Delete table
- ❌ NO DQ rules management
- ❌ NO governance/classification UI
- ❌ NO asset profile editor
- ❌ NO schema change history viewer
- ❌ NO table relations editor
- ❌ NO lock/archive schema

**SchemaDetailPage.jsx** (`/catalog/schemas/{tableId}`):
- ✅ View schema overview (title, description, fields list)
- ✅ View table relations
- ✅ Edit metadata
- ❌ NO DQ rules management
- ❌ NO governance data
- ❌ NO quality metrics
- ❌ NO change history
- ❌ NO lineage visualization

---

## 🎯 MISSING UI SCREENS

### **1. DQ Rules Manager** ❌
**Backend Support:** ✅ Fully supported (DQRule, DQResult models)

**Missing UI for:**
- Create/edit DQ rules per table
- Set rule type (not_null, unique, allowed_values, range, regex)
- Configure severity (info, warn, error)
- Define rule scope (table-level or field-level)
- View rule execution results
- See which rows failed validation

**Would go:** `/catalog/schema-manager/{tableId}/dq-rules` or modal in SchemaDetailPage

---

### **2. Asset Profile / Governance Editor** ❌
**Backend Support:** ✅ Fully supported (AssetProfile model)

**Missing UI for:**
- Set table classification (public, internal, confidential, pii, sensitive)
- Assign domain (which business domain owns this?)
- Set owner (who is responsible?)
- Set steward (who maintains this?)
- View quality status (unknown, passing, warning, failing)
- View quality score (0-100)
- Add tags

**Would go:** `/catalog/schemas/{tableId}/governance` or tab in SchemaDetailPage

---

### **3. Governance Event Log** ⚠️
**Backend Support:** ✅ Fully supported (GovernanceEvent model)

**Current Status:**
- ✅ Backend tracks events (create/update/delete)
- ✅ Frontend has `/catalog/governance` (read-only view)
- ❌ NOT linked to Schema Manager
- ❌ Cannot see changes for specific table

**Improvement:** Link to SchemaDetailPage as audit tab

---

### **4. Schema Change History** ❌
**Backend Support:** ✅ Fully supported (SchemaChangeLog model)

**Missing UI for:**
- View all schema changes (field add/edit/delete)
- See before/after values (JSON diff)
- Filter by field or table
- Show who made change and when
- Restore previous schema version (future feature)

**Would go:** `/catalog/schemas/{tableId}/history` tab

---

### **5. Table Relations Editor** ❌
**Backend Support:** ✅ Partially supported (TableRelation model exists)

**Missing UI for:**
- Create table relations (specify from/to table and field)
- Set relation type (one_to_many, many_to_many, lookup)
- Add relation description
- Visualize lineage graph
- Edit/delete relations
- Export lineage as diagram

**Would go:** `/catalog/schemas/{tableId}/relations` tab

---

### **6. Quality Metrics Dashboard** ❌
**Backend Support:** ✅ Fully supported (TableProfile, FieldProfile, DQResult)

**Missing UI for:**
- View table quality score
- View completeness %
- View per-field statistics (null_count, distinct_count, etc.)
- See top values in each field
- Track quality over time

**Would go:** `/catalog/schemas/{tableId}/quality` tab

---

### **7. Schema Locking / Versioning** ❌
**Backend Support:** ⚠️ Partially (version field exists but no lock model)

**Missing UI for:**
- Lock schema to prevent changes
- Show current version
- Version history selector
- Deprecate schema
- Archive schema safely

**Would go:** Metadata editor or separate modal

---

## 🏗️ PROPOSED SCHEMA DETAIL PAGE REDESIGN

```
SchemaDetailPage.jsx - Add Tabs:

┌─────────────────────────────────────────┐
│ Schema: "Bus Routes"                    │
│ [Edit Metadata] [Lock] [Archive]        │
├─────────────────────────────────────────┤
│ [Overview] [Fields] [Relations] [QA] [Governance] [Rules] [History] │
├─────────────────────────────────────────┤
│                                         │
│ TAB 1: OVERVIEW (currently exists)      │
│ - Title, description, module            │
│ - Basic metadata                         │
│ - Edit button                           │
│                                         │
│ TAB 2: FIELDS (currently exists)        │
│ - List of fields with types/validation  │
│                                         │
│ TAB 3: RELATIONS (currently exists)     │
│ - Table relationships and lineage       │
│ - [+ Add Relation] button               │
│                                         │
│ TAB 4: QUALITY (NEW)                    │
│ - Quality score, completeness %         │
│ - Field-level statistics                │
│ - Quality trend chart                   │
│                                         │
│ TAB 5: GOVERNANCE (NEW)                 │
│ - Classification (public/confidential)  │
│ - Domain, owner, steward                │
│ - Tags, glossary terms                  │
│ - [Edit] button to change               │
│                                         │
│ TAB 6: DQ RULES (NEW)                   │
│ - List active rules                     │
│ - [+ Add Rule] button                   │
│ - Rule name, type, severity, scope      │
│ - Last execution results                │
│ - [Run Now] button                      │
│                                         │
│ TAB 7: AUDIT HISTORY (NEW)              │
│ - Changes to schema (add/edit/delete)   │
│ - Who made change, when, what changed   │
│ - Governance events (classify, etc.)    │
│ - Governance log for this table         │
│                                         │
└─────────────────────────────────────────┘
```

---

## 📋 UI COMPONENT CHECKLIST (What Needs Building)

### **HIGH PRIORITY (Enable Governance)**
- [ ] DQ Rules Tab + Manager (create/edit/delete rules)
- [ ] Governance Tab (classification, owner, steward, tags)
- [ ] Audit History Tab (schema changes + governance events)

### **MEDIUM PRIORITY (Complete Lineage Story)**
- [ ] Relations Tab Enhancement (add [+ Create] button and editor)
- [ ] Quality Metrics Tab (display profiles and trend)

### **LOW PRIORITY (Polish)**
- [ ] Schema locking UI
- [ ] Version selector
- [ ] Archive/restore buttons

---

## 🔗 API ENDPOINTS ALREADY EXIST

Backend API is ready (no new endpoints needed):

```bash
# DQ Rules
GET    /carbon-api/dq/rules/?data_table=X
POST   /carbon-api/dq/rules/
PATCH  /carbon-api/dq/rules/{id}/

# Asset Profiles (Governance)
GET    /carbon-api/catalog/assets/
POST   /carbon-api/catalog/assets/
PATCH  /carbon-api/catalog/assets/{id}/

# Governance Events (Audit Log)
GET    /carbon-api/catalog/governance/

# Schema Change Log
GET    /carbon-api/dataschema/schema-logs/?data_table=X

# Table Relations
GET    /carbon-api/dataschema/relations/?from_table=X
POST   /carbon-api/dataschema/relations/
PATCH  /carbon-api/dataschema/relations/{id}/

# DQ Metrics
GET    /carbon-api/dq/metrics/table/{tableId}/
```

---

## 💡 SUMMARY

**The UI is the bottleneck, NOT the backend.**

Everything is implemented on the backend, but the Schema Manager UIs only show 15% of the features:

| Component | Backend | Frontend |
|-----------|---------|----------|
| Schema CRUD | ✅ | ✅ 50% |
| DQ Rules | ✅ | ❌ 0% |
| Governance | ✅ | ❌ 0% |
| Audit Trail | ✅ | ❌ 0% |
| Relations | ✅ | ⚠️ 30% (view only) |
| Quality Metrics | ✅ | ❌ 0% |
| Lineage | ✅ | ❌ 0% |

**To fix:** Add 5-7 new tabs to SchemaDetailPage + manager components for each feature.