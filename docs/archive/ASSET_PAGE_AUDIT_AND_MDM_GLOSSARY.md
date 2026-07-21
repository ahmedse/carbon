# Asset Page Audit & Master Data / Reference Sets Glossary

**Date:** July 20, 2026  
**Focus:** Catalog Studio - Asset Profiles, Reference Data Management, and UI/UX analysis

---

## TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
2. [Business Glossary: Master Data vs Reference Sets vs Asset Profiles](#business-glossary)
3. [Data Model Relationships & Architecture](#data-model-relationships)
4. [Asset Page UI/UX Audit](#asset-page-uiux-audit)
5. [Gap Analysis](#gap-analysis)
6. [Design Recommendations](#design-recommendations)
7. [Implementation Roadmap](#implementation-roadmap)

---

## EXECUTIVE SUMMARY

The **Asset Page** is a critical governance interface in the Carbon platform's Catalog Studio, but its current UI/UX is severely underdeveloped. The page displays only 4 basic fields (Name, Type, Description, Owner) while the backend [`AssetProfile`](backend/catalog/models.py:59) model provides **14+ rich governance fields** that are either invisible or inaccessible to users.

### Key Findings

| Finding | Impact | Priority |
|---------|--------|----------|
| Asset Page shows only 20% of available metadata | Users cannot see classification, domain, steward, quality status, or tags | **CRITICAL** |
| No filters or search beyond basic table view | Asset discovery inefficient; no domain/classification scoping | **HIGH** |
| Dialog form is shallow and disconnected | Cannot assign domains, stewards, or quality governance in UI | **HIGH** |
| Mismatch between backend capabilities and UI | `PATCH` endpoints exist but UI doesn't use them for partial updates | **MEDIUM** |
| Comparison with Reference Data Page shows pattern gap | Asset Page is outdated compared to Reference Data's richer presentation | **MEDIUM** |
| No visual quality status indicators | Critical governance metadata (quality_status, quality_score) invisible | **HIGH** |
| Asset type abstraction is weak | Both table and field assets shown in single view; no type differentiation | **MEDIUM** |

---

## BUSINESS GLOSSARY

### What is Master Data?

**Master Data** is the **authoritative, reusable, cross-organizational reference information** that underpins data governance and operational consistency.

#### Characteristics
- **Single source of truth** — one canonical version per entity type across the platform
- **Steward-managed** — owned and maintained by designated data stewards, not ad-hoc users
- **Cross-functional** — used by multiple applications, teams, and business processes
- **Slow-moving** — changes infrequently, carefully governed, audited
- **Hierarchical or structured** — organized by type, domain, or business category

#### Examples in Carbon
- Organizational units (university → campus → college → department hierarchy)
- Emission scopes (Scope 1, Scope 2, Scope 3)
- Emission categories (e.g., Purchased Electricity, Natural Gas)
- Data domains (Emissions, Facilities, Transportation)
- Users and their roles/permissions

#### Why It Matters
- **Data quality:** Master data ensures consistent definitions across all tables
- **Traceability:** Changes to master data are audited for compliance
- **Integration:** External systems (like Pulse ERP) reference the same master data
- **Scalability:** Prevents data silos and duplication

---

### What is Reference Data?

**Reference Data** (or **Reference Sets**) is **governed lookup values** — the set of allowed/valid codes and labels for specific data fields.

#### Characteristics
- **Controlled vocabulary** — a finite, enumerated set of valid values
- **Bind-able to fields** — linked to `DataField.type='reference'` for data validation
- **Version-aware** — supports temporal validity (valid_from/valid_to dates)
- **Hierarchical values** — optional metadata and sort order
- **Active/inactive states** — soft-delete without breaking references

#### Structure: [`ReferenceSet`](backend/mdm/models.py:8) → [`ReferenceValue`](backend/mdm/models.py:42)

**ReferenceSet** (the container)
- `name` — "Emission Scopes", "Department Status", etc.
- `slug` — system identifier, auto-generated from name
- `description` — what this set is for and when to use it
- `steward` — user responsible for maintaining the set
- `domain` — optional business domain scoping
- `is_active` — soft-delete flag
- `version` — governance tracking

**ReferenceValue** (the individual entry)
- `code` — system code (e.g., `scope_1`, `approved`)
- `label` — human-readable display label (e.g., "Scope 1", "Approved")
- `description` — optional context
- `is_active` — can be marked inactive without deleting
- `sort_order` — controls dropdown/list ordering
- `valid_from` / `valid_to` — optional temporal validity window
- `metadata` — JSON for extensibility (e.g., color, emoji, icon name)

#### Examples in Carbon
- **Emission Scopes:** code=`scope1`, label="Scope 1"; code=`scope2`, label="Scope 2"; code=`scope3`, label="Scope 3"
- **Facility Status:** code=`active`, label="Active"; code=`inactive`, label="Inactive"; code=`planned`, label="Planned"
- **Transportation Modes:** code=`bus`, label="Bus"; code=`car`, label="Car"; code=`rail`, label="Rail"

#### How It Integrates
```
DataField (e.g., "facility_status")
  ↓ type='reference' + reference_set_id
ReferenceSet (e.g., "Facility Status")
  ↓ contains
ReferenceValue[] (Active, Inactive, Planned, ...)
```

When a user enters data in a row:
1. UI fetches allowed values from the `ReferenceSet`
2. Presents dropdown/autocomplete
3. Validates input against active `ReferenceValue.code`
4. Stores the code in the row
5. On display, looks up label from `ReferenceValue.label`

---

### What is an Asset Profile?

**Asset Profile** is the **governance metadata wrapper** around a data schema asset (a table or field), capturing ownership, classification, quality, and business context.

#### Characteristics
- **Per-asset metadata** — one `AssetProfile` per `DataTable` or `DataField`
- **Rich governance** — classification, quality status, stewardship, domain mapping
- **Semantic context** — links to business glossary terms and tags
- **Quality tracking** — rolls up from DQ profiling and rule runs
- **Audit trail** — every change emits a `GovernanceEvent`
- **Auto-provisioned** — created on first catalog read if missing

#### Structure: [`AssetProfile`](backend/catalog/models.py:59)

**Core Fields**
- `data_table` / `data_field` — which asset this metadata is for (mutually exclusive)
- `description` — business context and usage guidelines
- `domain` → [`DataDomain`](backend/catalog/models.py:22) — which business domain (Emissions, Facilities, etc.)

**Stewardship**
- `owner` — executive/manager accountable for asset value
- `steward` — technical steward responsible for quality
- `classification` — sensitivity level (public, internal, confidential, pii, sensitive)

**Semantic**
- `semantic_type` — e.g., "dimension", "measure", "identifier"
- `glossary_term` → [`GlossaryTerm`](backend/catalog/models.py:35) — canonical business definition
- `tags` → [`Tag[]`](backend/catalog/models.py:50) — free multi-select labels

**Quality (Read-Only, Written by DQ Engine)**
- `quality_status` — unknown | passing | warning | failing
- `quality_score` — 0–100 percentile
- `updated_by` — who/when last updated

#### Examples in Carbon
```
AssetProfile for DataTable "Facility Emissions"
├─ domain: Emissions
├─ owner: Emissions Manager
├─ steward: Data Analyst
├─ classification: internal
├─ description: Monthly emissions calculated from facility energy consumption
├─ tags: [emissions, monthly, aggregated]
├─ glossary_term: "Facility Emissions Inventory"
└─ quality_status: passing (quality_score: 94)

AssetProfile for DataField "facility_status" (in Facilities table)
├─ domain: Facilities
├─ steward: Facilities Steward
├─ classification: public
├─ semantic_type: dimension
├─ description: Current operational status of the facility
├─ glossary_term: "Facility Status"
├─ tags: [categorical, status]
└─ quality_status: warning (quality_score: 78)
```

---

### Key Distinctions

| Aspect | Reference Data | Master Data | Asset Profile |
|--------|---|---|---|
| **Purpose** | Valid lookup values | Authoritative business entities | Governance metadata |
| **Who manages** | Steward of the reference set | Domain/org steward | Data steward / admin |
| **Where used** | Field validation, dropdowns | Integration, calculations | Catalog search, governance |
| **Mutability** | Slow (values added/retired carefully) | Slow (hierarchies, codes change) | Moderate (ownership, tags updated) |
| **Scope** | Global (never org-scoped) | Global or domain-scoped | Asset-level |
| **Example** | ReferenceSet "Scopes" with values 1, 2, 3 | OrgUnit tree (Uni → Campus → Dept) | AssetProfile for "CO2e Emissions" table |

---

## DATA MODEL RELATIONSHIPS

### Conceptual Architecture

```
CATALOG (Governance Layer)
├─ DataDomain
│  ├─ name, slug, description, owner
│  ├─ relates_to: AssetProfile[] (assets in this domain)
│  └─ relates_to: ReferenceSet[] (reference data in this domain)
│
├─ AssetProfile (Metadata for Tables/Fields)
│  ├─ data_table OR data_field (one per)
│  ├─ domain (FK → DataDomain)
│  ├─ owner, steward (FK → User)
│  ├─ classification, semantic_type
│  ├─ glossary_term (FK → GlossaryTerm)
│  ├─ tags (M2M → Tag)
│  ├─ quality_status, quality_score (from DQ engine)
│  └─ events (→ GovernanceEvent[])
│
├─ GlossaryTerm
│  ├─ term, definition, status (draft/approved/deprecated)
│  └─ steward (FK → User)
│
└─ Tag
   └─ name, slug, color

MDM / REFERENCE DATA (Lookup Management)
├─ ReferenceSet
│  ├─ name, slug, description
│  ├─ domain (FK → DataDomain, nullable)
│  ├─ steward (FK → User)
│  ├─ is_active, version
│  └─ values (→ ReferenceValue[])
│
└─ ReferenceValue
   ├─ code, label, description
   ├─ is_active, sort_order
   ├─ valid_from, valid_to (temporal)
   └─ metadata (JSON)

DATASCHEMA (Core)
├─ DataTable
│  ├─ name, title, module
│  ├─ fields (→ DataField[])
│  └─ catalog_profile (→ AssetProfile, FK)
│
└─ DataField
   ├─ name, label, type
   ├─ reference_set (FK → ReferenceSet, for type='reference')
   └─ catalog_profile (→ AssetProfile, FK)
```

### Data Flow Example: Emission Scopes

```
Scenario: User enters emissions data for Scope 1

1. ReferenceSet "Emission Scopes" is created/steward-managed
   ├─ ReferenceValue { code: 'scope1', label: 'Scope 1' }
   ├─ ReferenceValue { code: 'scope2', label: 'Scope 2' }
   └─ ReferenceValue { code: 'scope3', label: 'Scope 3' }

2. DataField "emission_scope" in table "Monthly Emissions" 
   ├─ type: 'reference'
   └─ reference_set_id: <Emission Scopes ID>

3. AssetProfile for "Monthly Emissions" table
   ├─ domain: Emissions
   ├─ classification: internal
   ├─ quality_status: passing
   └─ steward: Emissions Lead

4. UI Data Entry Flow
   a) User opens Monthly Emissions table
   b) For "emission_scope" field → fetch ReferenceSet values
   c) Render dropdown with ["Scope 1", "Scope 2", "Scope 3"]
   d) User selects "Scope 1" (stores code 'scope1' in database)
   e) On display, looks up label 'Scope 1' for UI rendering
   f) If steward later changes label to "Direct Emissions", 
      UI automatically shows new label everywhere (no data migration)
```

---

## ASSET PAGE UI/UX AUDIT

### Current State: AssetsPage.jsx

**Screenshot reference:** `localhost:5179/carbon/catalog/assets`

#### Page Structure
```
┌─────────────────────────────────────────────────┐
│ Asset Profiles              [+ New Asset]        │
├─────────────────────────────────────────────────┤
│ NAME    │ TYPE   │ DESCRIPTION  │ OWNER │ ACTIONS
├─────────────────────────────────────────────────┤
│ (empty rows, no seed data)                      │
└─────────────────────────────────────────────────┘
```

#### Dialog (Create/Edit)
```
┌────────────────────────────────────────┐
│ New Asset Profile                      │
├────────────────────────────────────────┤
│ Name:      [_______________]           │
│ Asset Type: [Table ▼]                  │
│ Description: [_______________]         │
│             [_______________]          │
│             [_______________]          │
│ Owner:     [_______________]           │
├────────────────────────────────────────┤
│ [Cancel]  [Create]                     │
└────────────────────────────────────────┘
```

### Current Implementation Analysis

#### Frontend Code: [`AssetsPage.jsx`](carbon-frontend/src/pages/catalog/AssetsPage.jsx)

**Displays (5 columns)**
```jsx
<TableCell>Name</TableCell>
<TableCell>Type</TableCell>
<TableCell>Description</TableCell>
<TableCell>Owner</TableCell>
<TableCell align="right">Actions</TableCell>
```

**Form Fields (Dialog)**
```jsx
name
asset_type (select: table, field, report, dashboard)
description (multiline)
owner (text input, not a select)
```

**State**
```jsx
const [assets, setAssets] = useState([]);
const [editingAsset, setEditingAsset] = useState(null);
const [formData, setFormData] = useState({
  name: '',
  asset_type: 'table',
  description: '',
  owner: '',
});
```

**API Usage**
```jsx
fetchAssetProfiles(token)           // read all
createAssetProfile(token, formData)  // POST
updateAssetProfile(token, id, formData)  // PUT (full)
deleteAssetProfile(token, id)       // DELETE
// Note: patchAssetProfile exists but is NOT used
```

### Backend Capabilities: AssetProfileSerializer

#### Available Fields (14 serialized)

From [`catalog/serializers.py:AssetProfileSerializer`](backend/catalog/serializers.py:27):

```python
fields = [
    'id',                    # ✅ display
    'asset_type',           # ✅ display (computed: table vs field)
    'title',                # ❌ not displayed (computed from table/field)
    'data_table',           # ❌ not displayed
    'data_field',           # ❌ not displayed
    'description',          # ✅ display (truncated)
    'domain',               # ❌ NOT ACCESSIBLE in form
    'owner',                # ✅ display (text-only, not user select)
    'steward',              # ❌ NOT ACCESSIBLE in form
    'classification',       # ❌ NOT ACCESSIBLE in form
    'semantic_type',        # ❌ NOT ACCESSIBLE in form
    'glossary_term',        # ❌ NOT ACCESSIBLE in form
    'tags',                 # ❌ NOT ACCESSIBLE in form
    'quality_status',       # ❌ READONLY (from DQ engine)
    'quality_score',        # ❌ READONLY (from DQ engine)
    'updated_at',           # ❌ not displayed
    'updated_by',           # ❌ not displayed
]

read_only_fields = [
    'id', 'asset_type', 'title', 'data_table', 'data_field',
    'quality_status', 'quality_score', 'updated_at', 'updated_by'
]
```

**Editable fields (backend allows):** description, domain, owner, steward, classification, semantic_type, glossary_term, tags

**Editable fields (UI exposes):** name, asset_type, description, owner (+ only 3 out of 8 actual editable fields)

---

### Comparison: Reference Data Page vs Asset Page

#### Reference Data Page: [`ReferenceDataPage.jsx`](carbon-frontend/src/pages/catalog/ReferenceDataPage.jsx)

**Displays (4 columns)**
```jsx
<TableCell>Name</TableCell>
<TableCell>Description</TableCell>
<TableCell>Values</TableCell>           // ← shows value_count
<TableCell align="right">Actions</TableCell>
```

**Strengths**
- Header layout with icon + title + subtitle (professional UX)
- Notification feedback for all operations (create, update, delete)
- Error state management
- Shows `value_count` at a glance (metadata visibility)
- Consistent spacing and alignment

**Form fields**
```jsx
name
description
```

**Comparison**
| Feature | Asset Page | Reference Data Page |
|---------|------------|---------------------|
| Header design | Basic typography | Icon + title + subtitle |
| Metadata shown | 4 fields | 4 fields + value_count |
| Error handling | Basic (Alert) | Notification system |
| Success feedback | None | Toast notifications |
| Create dialog | Simple | Simple |
| Edit inline | No | No |
| Filters | None | None |
| Search | None | None |

**Verdict:** Reference Data Page is marginally better in UX polish, but both pages lack critical features (filters, search, metadata visibility).

---

### Comparison: Domains Page

Reference: If a `DomainsPage` exists, would show:
- Better hierarchy visualization
- Owner/steward display
- Asset count roll-up
- Drill-down navigation

**Asset Page lacks:** Similar visual hierarchy and discoverability.

---

## GAP ANALYSIS

### Gap 1: Missing Metadata Display

| Field | Backend | Frontend | Gap | Impact |
|-------|---------|----------|-----|--------|
| `domain` | ✅ available, editable | ❌ hidden | Not visible to users | **Users cannot see which domain an asset belongs to** |
| `steward` | ✅ available, editable | ❌ hidden | Not accessible | **Stewardship responsibility is invisible** |
| `classification` | ✅ available, editable | ❌ hidden | Not accessible | **Data sensitivity/PII status not surfaced** |
| `quality_status` | ✅ available, readonly | ❌ hidden | Not displayed | **Critical: users don't see data quality** |
| `quality_score` | ✅ available, readonly | ❌ hidden | Not displayed | **Quality percentile invisible** |
| `semantic_type` | ✅ available, editable | ❌ hidden | Not accessible | **Business context (dimension/measure) unknown** |
| `glossary_term` | ✅ available, editable | ❌ hidden | Not accessible | **Link to business definitions unavailable** |
| `tags` | ✅ available, editable | ❌ hidden | Not accessible | **Free-form classification invisible** |
| `updated_by` | ✅ available, readonly | ❌ hidden | Not displayed | **Audit trail (who changed) not shown** |
| `updated_at` | ✅ available, readonly | ❌ hidden | Not displayed | **Audit trail (when changed) not shown** |

**Severity:** 🔴 CRITICAL — Asset Page is missing 10+ fields that governance users need.

---

### Gap 2: Form Doesn't Match Backend

**Form fields**
```
name            → NOT in backend schema (backend has title)
asset_type      → NOT in backend schema (computed from table/field FKs)
description     → ✅ matches
owner           → ✅ matches (but input is text, should be user select)
```

**Backend-only editable fields NOT in form**
```
domain          → dropdown select (FK to DataDomain)
steward         → user select (FK to User)
classification  → select (choices: public, internal, confidential, pii, sensitive)
semantic_type   → text or select
glossary_term   → autocomplete select (FK to GlossaryTerm)
tags            → multi-select (M2M to Tag)
```

**Root cause:** Frontend is using generic form structure; backend schema is governance-rich.

**Severity:** 🔴 CRITICAL — Users cannot perform essential governance tasks (assign stewards, set classification).

---

### Gap 3: No Filters or Search

**Current:** Assets shown as flat table, all in one view.

**Missing:**
- Filter by domain
- Filter by classification
- Filter by quality status
- Filter by asset type (table vs field)
- Filter by owner/steward
- Search by name/description

**Reference Data Page also lacks this**, but Asset Page needs it more due to potentially 100+ assets.

**Severity:** 🟠 HIGH — Asset discovery is inefficient.

---

### Gap 4: No Differentiation Between Table and Field Assets

**Current behavior:**
```
Asset Type column shows "table" or "field"
Both rendered in same row
No grouping or visual distinction
```

**Issue:** 
- Table assets (e.g., "Emissions Monthly") and field assets (e.g., "emissions_scope") are different entities
- Users need different workflows for each
- No way to navigate from field asset back to its table

**Severity:** 🟡 MEDIUM — UX is confusing; missing navigation context.

---

### Gap 5: Asset Auto-Creation Not Surfaced

**Backend:** [`ensure_asset_profiles()`](backend/catalog/services.py:6) creates AssetProfile for every table/field on first catalog read.

**Frontend:** User sees all assets, but doesn't understand they're auto-created, not user-managed.

**Severity:** 🟡 MEDIUM — Expectation mismatch (users think they're creating assets manually when they already exist).

---

### Gap 6: Dialog Form Uses Shallow Update

**Current:** `updateAssetProfile()` uses full PUT (requires all fields).

**Better:** `patchAssetProfile()` exists but unused — supports partial updates.

**Impact:** If backend schema changes, existing frontends break; PATCH is safer.

**Severity:** 🟡 MEDIUM — Technical debt, not urgent for users.

---

### Gap 7: No Inline Edit or Quick Actions

**Current:**
- Click edit → dialog opens
- Change field → save → dialog closes → refresh
- 3 clicks for simple edit

**Better (not critical, but UX improvement):**
- Click edit on table cell → edit in place
- Keyboard Enter to save
- 1 click

**Severity:** 🟢 LOW — Nice-to-have, not blocking governance.

---

### Gap 8: Quality Status Visual Indicators

**Backend:** `quality_status` is categorical (unknown, passing, warning, failing).

**Frontend:** Status hidden entirely.

**Better:** Color-coded badges or icons (🟢 passing, 🟡 warning, 🔴 failing, ⚪ unknown).

**Severity:** 🔴 CRITICAL — Data quality is invisible to stewards.

---

## DESIGN RECOMMENDATIONS

### Recommendation 1: Expand Table Display (Columns)

**Current:** 5 columns (Name, Type, Description, Owner, Actions)

**Recommended:** 9 columns with intelligent defaults and optional visibility toggle

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Asset Profiles [Showing 45 of 87 assets]  [Filters ▼] [View ▼]  [+ New Asset]   │
├─────────────────────────────────────────────────────────────────────────────────┤
│ NAME              TYPE     DOMAIN      CLASSIFICATION  QUALITY  TAGS      STEWARD │
├─────────────────────────────────────────────────────────────────────────────────┤
│ CO2e Monthly      table    Emissions   internal        🟢 94%    [emissions] Sarah │
│ facility_status   field    Facilities  public          🟡 78%    [status]    John │
│ ...
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Column Details**

| Column | Display | Type | Sortable | Width |
|--------|---------|------|----------|-------|
| NAME | "CO2e Monthly" or "emissions_scope (table)" | text | ✅ | 25% |
| TYPE | 🏠 table / 📄 field | icon badge | ✅ | 8% |
| DOMAIN | "Emissions" | text/chip | ✅ | 12% |
| CLASSIFICATION | 🔐 PII / 🔒 Confidential / 🟢 Internal / ⚪ Public | colored badge | ✅ | 12% |
| QUALITY | 🟢 Passing 94% / 🟡 Warning 78% | status badge | ✅ | 10% |
| TAGS | [emissions] [monthly] [approved] | chips (max 3, +N more) | ❌ | 15% |
| STEWARD | "Sarah Chen" | text | ✅ | 12% |
| ACTIONS | 📝 Edit / 🔗 View Details / ⋯ More | icon buttons | ❌ | 6% |

**Implementation Notes**
- Use column visibility menu (top right) to allow users to hide/show domain, steward, tags
- Default visible: NAME, TYPE, CLASSIFICATION, QUALITY, STEWARD, ACTIONS
- Optional: DOMAIN, TAGS
- Sort by NAME, TYPE, DOMAIN, QUALITY, STEWARD

---

### Recommendation 2: Add Filters & Search

**UI Location:** Above table, below header

```
┌──────────────────────────────────────────────────────────────────────┐
│ [🔍 Search by name...]  [Domain ▼] [Classification ▼] [Quality ▼]   │
│                         [Steward ▼] [Asset Type ▼]   [Clear Filters] │
└──────────────────────────────────────────────────────────────────────┘
```

**Filters**
- **Search:** Name or description contains (free text)
- **Domain:** single select dropdown (Emissions, Facilities, Transportation, etc.)
- **Classification:** multi-select (public, internal, confidential, pii, sensitive)
- **Quality Status:** multi-select (passing, warning, failing, unknown)
- **Asset Type:** toggle (all, table, field)
- **Steward:** user select (by role scope)

**Reset Button:** "Clear Filters" to reset all to defaults

---

### Recommendation 3: Improve Dialog Form

**Current Dialog**
```
┌────────────────────────────────────┐
│ New Asset Profile                  │
├────────────────────────────────────┤
│ Name:       [___________]          │ ← not in backend
│ Asset Type: [table ▼]              │ ← immutable (computed)
│ Description:[___________]          │
│             [___________]          │
│ Owner:      [___________]          │ ← text input (should be select)
├────────────────────────────────────┤
│ [Cancel]  [Create]                 │
└────────────────────────────────────┘
```

**Proposed Dialog (Tabbed for Clarity)**

**Tab 1: Core Metadata** (Auto-filled)
```
┌──────────────────────────────────────────┐
│ ● Core   ○ Classification   ○ Governance │
├──────────────────────────────────────────┤
│ Asset:       CO2e Monthly (Table)        │
│              [read-only text]            │
│                                          │
│ Description: [_____________________]     │
│              [_____________________]     │
│                                          │
│ Semantic Type: [Measure ▼]               │
├──────────────────────────────────────────┤
│ [Cancel]  [Next >]                       │
└──────────────────────────────────────────┘

Legend:
- Asset: immutable, display what table/field this metadata is for
- Description: editable, rich text optional
- Semantic Type: select from [Measure, Dimension, Identifier, Metadata]
```

**Tab 2: Classification** (Governance)
```
┌──────────────────────────────────────────┐
│ ● Core   ○ Classification   ○ Governance │
├──────────────────────────────────────────┤
│ Data Classification:                     │
│  ○ Public        (no restrictions)       │
│  ⦿ Internal      (employees only)        │
│  ○ Confidential   (management only)      │
│  ○ PII            (GDPR protected)       │
│  ○ Sensitive      (custom policy)        │
│                                          │
│ Domain: [Emissions ▼]                    │
│                                          │
│ Glossary Term: [CO2e Scope 1 ▼]          │
│                [+ Create New]            │
│                                          │
│ Tags: [emissions ✕] [monthly ✕]          │
│       [+ Add Tag] [+ Create New]         │
├──────────────────────────────────────────┤
│ [< Back]  [Next >]                       │
└──────────────────────────────────────────┘
```

**Tab 3: Governance & Responsibility**
```
┌──────────────────────────────────────────┐
│ ● Core   ○ Classification   ○ Governance │
├──────────────────────────────────────────┤
│ Owner: [Sarah Chen (Manager) ▼]          │
│        [Accountable for asset value]     │
│                                          │
│ Steward: [John Doe (Data Analyst) ▼]     │
│          [Responsible for quality]       │
│                                          │
│ Quality Status: Passing (94%)            │
│                 [read-only, from DQ]     │
│                                          │
│ Last Updated: 2026-07-15 by Sarah Chen   │
│              [read-only audit]           │
├──────────────────────────────────────────┤
│ [< Back]  [Cancel]  [Save]               │
└──────────────────────────────────────────┘
```

**Interaction Flow**
1. Click [+ New Asset] or [Edit] on table row
2. System detects asset type (table vs field)
3. Tab 1 (Core): Show asset name/type read-only, description, semantic type
4. Tab 2 (Classification): Classification, domain, glossary, tags
5. Tab 3 (Governance): Owner, steward (read-only quality status)
6. [Save] → PATCH backend with only changed fields
7. Toast: "Asset updated" or error

---

### Recommendation 4: Detail Page (Asset Detail View)

**Route:** `/catalog/assets/:id` or click "View Details" action

**Purpose:** Deep-dive governance view with full audit history

```
┌─────────────────────────────────────────────────────────────────┐
│ ← Back to Assets                                                │
│                                                                  │
│ CO2e Monthly Emissions                    [Edit] [⋯ More Actions]
│ 🏠 Table in Emissions Domain                                    │
│                                                                  │
│ ┌─ Core Metadata ────────────────────────────────────────────┐ │
│ │ Description: Monthly CO2e calculated from...              │ │
│ │ Semantic Type: Measure                                    │ │
│ │ Classification: 🔒 Internal (employees only)              │ │
│ │ Owner: Sarah Chen (Manager)                              │ │
│ │ Steward: John Doe (Data Analyst)                         │ │
│ │ Quality: 🟢 Passing (94%)                                │ │
│ └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ ┌─ Business Context ──────────────────────────────────────────┐ │
│ │ Glossary: CO2e Scope 1                                    │ │
│ │ Tags: [emissions] [monthly] [approved]                   │ │
│ │ Domain: Emissions                                         │ │
│ └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ ┌─ Related Assets ────────────────────────────────────────────┐ │
│ │ Fields in this table:                                     │ │
│ │  • emission_scope (code: scope1, scope2, scope3)         │ │
│ │  • facility_id (reference: Facilities)                   │ │
│ │  • co2e_value (measure)                                  │ │
│ │  • reporting_month (date)                                │ │
│ └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ ┌─ Audit History ─────────────────────────────────────────────┐ │
│ │ 2026-07-15 10:30  Sarah Chen  Updated classification     │ │
│ │ 2026-07-14 14:22  John Doe    Updated steward            │ │
│ │ 2026-07-01 09:15  Admin       Created asset profile      │ │
│ └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ ┌─ Data Quality Metrics ──────────────────────────────────────┐ │
│ │ Completeness: 100% (no nulls)                             │ │
│ │ Uniqueness: 99.8% (0.2% duplicates)                       │ │
│ │ Validity: 94% (6% invalid scopes)                         │ │
│ │ Freshness: 2 hours old (updated 2026-07-15 12:30)        │ │
│ └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ ┌─ Quality Rules ─────────────────────────────────────────────┐ │
│ │ ✅ [not_null] emission_scope: Passing                     │ │
│ │ ⚠️ [allowed_values] emission_scope: Warning (6 failures)  │ │
│ │ ✅ [unique] emission_id: Passing                          │ │
│ └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

### Recommendation 5: Quick-Action Menu

**Add icon button [⋯] to each table row**

```
[Edit] [View Details] [⋯ More]

More Menu Options:
├─ Copy Asset ID (for API)
├─ View Quality Rules
├─ View Audit History
├─ Assign to Domain
├─ Download as JSON
├─ ─────────────────
└─ Delete (with confirmation)
```

---

### Recommendation 6: Empty State & Data Seeding

**Current:** Page shows "No assets found" even though backend auto-creates them.

**Issue:** User doesn't understand that assets already exist and are auto-managed.

**Solution:**
```
┌─────────────────────────────────────────────────────────────┐
│ Asset Profiles                           [+ New Asset]      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│          📚 No assets found                                 │
│                                                              │
│  Assets are auto-created for all tables and fields.         │
│  To see them, navigate to Data Entry or create a new table. │
│                                                              │
│  Or: [Create Demo Data] (for testing)                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

### Recommendation 7: Integration with Data Entry

**Current:** Asset Page is isolated from DataEntry/RowDetail.

**Better:**
- From row detail view → click table name → navigate to AssetProfile
- From AssetProfile → click "View Table Data" → navigate to DataEntry
- Bidirectional linking improves discoverability

---

## IMPLEMENTATION ROADMAP

### Phase 1: Quick Wins (Week 1)

**Goal:** Display more governance metadata without major refactoring

**Tasks**
1. Extend table to show 8 columns: Name, Type, Domain, Classification, Quality, Tags, Steward, Actions
2. Add quality status badges (🟢 🟡 🔴 ⚪) with color coding
3. Add column visibility toggle (3-dot menu)
4. Fetch full `AssetProfile` data (backend already returns it)

**Files to Update**
- [`carbon-frontend/src/pages/catalog/AssetsPage.jsx`](carbon-frontend/src/pages/catalog/AssetsPage.jsx) — expand table
- Add component [`carbon-frontend/src/components/QualityBadge.jsx`](carbon-frontend/src/components/QualityBadge.jsx) — new
- Add component [`carbon-frontend/src/components/ClassificationBadge.jsx`](carbon-frontend/src/components/ClassificationBadge.jsx) — new

**Effort:** 2–3 hours

---

### Phase 2: Form Overhaul (Week 1–2)

**Goal:** Expose all editable governance fields in UI

**Tasks**
1. Replace simple dialog with tabbed dialog (Core / Classification / Governance tabs)
2. Add selects for: domain, steward, classification, glossary_term
3. Add multi-select for tags
4. Add semantic_type select
5. Use PATCH endpoint for partial updates

**Files to Update**
- Refactor [`carbon-frontend/src/pages/catalog/AssetsPage.jsx`](carbon-frontend/src/pages/catalog/AssetsPage.jsx) — split form logic
- Create [`carbon-frontend/src/components/AssetFormTabs.jsx`](carbon-frontend/src/components/AssetFormTabs.jsx) — new
- Update [`carbon-frontend/src/api/catalog.js`](carbon-frontend/src/api/catalog.js) — use patchAssetProfile

**Dependencies**
- Backend must expose select options (domains list, users list, glossary terms, tags)
- Create API endpoints if missing: `GET /catalog/domains/`, `GET /accounts/users/`, etc.

**Effort:** 4–6 hours

---

### Phase 3: Filters & Search (Week 2)

**Goal:** Enable asset discovery at scale

**Tasks**
1. Add filter bar above table (domain, classification, quality, steward, type)
2. Add search input (name/description free text)
3. Persist filters in URL query params
4. Add "Clear Filters" button

**Files to Update**
- Update [`carbon-frontend/src/pages/catalog/AssetsPage.jsx`](carbon-frontend/src/pages/catalog/AssetsPage.jsx) — add filter state
- Create [`carbon-frontend/src/components/AssetFilterBar.jsx`](carbon-frontend/src/components/AssetFilterBar.jsx) — new

**Effort:** 3–4 hours

---

### Phase 4: Detail Page (Week 2–3)

**Goal:** Deep governance view with audit history and related assets

**Tasks**
1. Create new route: `/catalog/assets/:id`
2. Fetch asset, related fields/table, audit events, DQ metrics
3. Display in rich layout with tabs (Metadata / Audit / Quality Rules / Related)
4. Add "View Table" button to navigate to DataEntry

**Files to Create**
- [`carbon-frontend/src/pages/catalog/AssetDetailPage.jsx`](carbon-frontend/src/pages/catalog/AssetDetailPage.jsx) — new
- [`carbon-frontend/src/pages/catalog/tabs/AssetDetailTab.jsx`](carbon-frontend/src/pages/catalog/tabs/AssetDetailTab.jsx) — new
- [`carbon-frontend/src/pages/catalog/tabs/AssetAuditTab.jsx`](carbon-frontend/src/pages/catalog/tabs/AssetAuditTab.jsx) — new
- [`carbon-frontend/src/pages/catalog/tabs/AssetQualityTab.jsx`](carbon-frontend/src/pages/catalog/tabs/AssetQualityTab.jsx) — new

**Effort:** 6–8 hours

---

### Phase 5: Polish & Integration (Week 3)

**Goal:** Integrate with other pages; improve UX polish

**Tasks**
1. Add bidirectional navigation (Asset → Table → Asset)
2. Inline quick-action menu (⋯ More)
3. Toast notifications (success/error)
4. Sorting (click column headers)
5. Pagination or infinite scroll for 100+ assets

**Files to Update**
- [`carbon-frontend/src/pages/catalog/AssetsPage.jsx`](carbon-frontend/src/pages/catalog/AssetsPage.jsx) — add sorting, pagination
- Create [`carbon-frontend/src/components/AssetQuickActions.jsx`](carbon-frontend/src/components/AssetQuickActions.jsx) — new

**Effort:** 3–4 hours

---

### Total Effort: 18–25 hours over 3 weeks

---

## ACCEPTANCE CRITERIA

### For Phase 1
- [ ] Table displays 8 columns (Name, Type, Domain, Classification, Quality, Tags, Steward, Actions)
- [ ] Quality status shows color-coded badges (🟢 🟡 🔴 ⚪) with tooltips
- [ ] Classification shows security level icons
- [ ] Tags display as chips (max 3, +N indicator)
- [ ] Column visibility toggle works
- [ ] No data loss when toggling columns

### For Phase 2
- [ ] Dialog has 3 tabs (Core / Classification / Governance)
- [ ] Domain select populated from backend
- [ ] Steward select populated by user role
- [ ] Classification radio buttons work
- [ ] Tags multi-select works
- [ ] Semantic type select works
- [ ] PATCH endpoint used for partial updates
- [ ] Form validation prevents invalid input (e.g., required fields)
- [ ] Dialog shows owner/steward in Governance tab

### For Phase 3
- [ ] Filters display in filter bar
- [ ] Search by name/description works
- [ ] Filter results update table immediately
- [ ] Clear Filters button resets all
- [ ] URL query params reflect active filters (bookmarkable)
- [ ] Filters persist across page reload

### For Phase 4
- [ ] Asset detail page loads and displays all metadata
- [ ] Related fields section shows all fields in table
- [ ] Audit history displays governance events
- [ ] Quality metrics display (completeness, uniqueness, validity)
- [ ] "View Table" button navigates to DataEntry
- [ ] Breadcrumb shows: Catalog > Assets > [Asset Name]

### For Phase 5
- [ ] Click table name in Asset Detail → navigates to AssetProfile
- [ ] Sorting works on Name, Domain, Classification, Quality, Steward columns
- [ ] Pagination or infinite scroll for 100+ items
- [ ] Toast notifications appear for create/update/delete
- [ ] Keyboard shortcuts for quick navigation (optional)

---

## GLOSSARY & TERMINOLOGY SUMMARY

| Term | Definition | Example |
|------|-----------|---------|
| **Asset Profile** | Governance metadata wrapper for a table or field | AssetProfile for "CO2e Monthly" table |
| **Master Data** | Authoritative, reusable business entities | OrgUnit tree, emission scopes |
| **Reference Data** | Controlled lookup values for fields | ReferenceSet "Emission Scopes" with values 1, 2, 3 |
| **Reference Set** | Container for enumerated values | "Facility Status" → {Active, Inactive, Planned} |
| **Reference Value** | Individual entry in a set | Code "scope1", Label "Scope 1" |
| **Data Domain** | Business category/namespace | Emissions, Facilities, Transportation |
| **Glossary Term** | Canonical business definition | "Scope 1 emissions" definition |
| **Tag** | Free-form label for classification | [emissions], [monthly], [approved] |
| **Steward** | Person responsible for data quality | Emissions Data Analyst |
| **Owner** | Person accountable for asset value | Emissions Manager |
| **Classification** | Data sensitivity level | public, internal, confidential, pii, sensitive |
| **Quality Status** | Data quality assessment | passing, warning, failing, unknown |

---

## NEXT STEPS

1. **Review this plan** with product/UX team
2. **Prioritize phases** based on governance needs (recommend Phase 1 + 2 first)
3. **Allocate resources** (frontend + backend support for data fetching)
4. **Create design mocks** for tabbed dialog and detail page
5. **Begin Phase 1** implementation
6. **Gather user feedback** after Phase 1 before proceeding

---

**END OF AUDIT REPORT**
