# TASK: RIGHT-PANEL-STANDARDIZATION — Unified Enterprise Right Panel
# ======================================================================
# Phase: My Data Right Panel Standardization & Related Tab Redesign
# Assigned to: Frontend Worker (Medium budget, DeepSeek-V3)
# Author: Master Architect
# Date: 2026-08-03
# Status: READY FOR ASSIGNMENT

---

## 1. PROBLEM STATEMENT

Every right-panel tab across the My Data flow uses a **different display pattern**:

| Component | Pattern | Issue |
|---|---|---|
| `DQRulesTab` (catalog) | MUI `<Table>` with head/body | ✅ THE GOLD STANDARD |
| `DQMetricsTab` | `<Box>` + `<Stack>` with custom icons | Not a table, no structure |
| `RelatedRecordsTab` | Raw `<Box>` divs, `borderBottom`, `cursor:pointer` | Same-table dump, 0.58rem chips |
| `RowHistoryTab` | `<Box>` flex with plain text | 40+ "update —" entries |
| `RowLineageTab` | Custom `<Box>` cards, `borderLeft` accent | Non-standard card pattern |
| `TrustTab` (L1) | `<Box>` with `display:grid` rows | Semi-structured but not a table |
| `ImpactTab` (L1) | `<Box>` with `display:grid` rows | Semi-structured but not a table |
| `ModuleHealthTab` (L2) | `<Box>` flex with CircularProgress | Mixed patterns |
| `ModuleLineageTab` (L2) | `<Box>` with `borderLeft` dividers | Same as RowLineageTab |
| `ModuleGovernanceTab` (L2) | `<Box>` with scattered components | Mixed patterns |

**Root cause**: Each dev invented their own layout. No shared panel component library.

---

## 2. THE GOAL

One unified pattern for ALL right-panel tabs, modeled after `DQRulesTab`:

```
┌─────────────────────────────────────┐
│ TAB HEADER                          │
│ Title                    [Actions]  │
├─────────────────────────────────────┤
│ ┌───────┬────────┬───────┬────────┐ │
│ │Header1│Header2 │Header3│Actions │ │  ← MUI TableHead (grey.100)
│ ├───────┼────────┼───────┼────────┤ │
│ │value  │Chip    │42%    │[icons] │ │  ← TableBody with hover
│ │value  │Chip    │87%    │[icons] │ │
│ └───────┴────────┴───────┴────────┘ │
│                                     │
│  1–N of M    [<] [>]                │  ← optional pagination
└─────────────────────────────────────┘
```

**Design tokens (ALL tabs MUST use these):**

| Token | Value | Usage |
|---|---|---|
| Table size | `small` | Compact enterprise look |
| Header bg | `grey.100` | Distinct header row |
| Header font | `fontWeight: 600` | Bold headers |
| Row font | `fontSize: '0.75rem'` | Body cells |
| Chip height | `20px` | ALL chips everywhere |
| Chip font | `fontSize: '0.68rem'` | Chip labels |
| Hover row | `'&:hover': { bgcolor: 'grey.50' }` | Row hover |
| Empty state | `<Alert severity="info">` | Not custom typography |
| Loading | `<CircularProgress>` centered | Consistent spinner |
| Actions | `<Tooltip>` + `<IconButton size="small">` | Icon buttons |
| Padding | `p: 2` outer, `px: 1.5` cells | Consistent spacing |

---

## 3. SHARED COMPONENTS TO CREATE

### 3.1 `PanelTable.jsx` — Reusable panel table wrapper

```jsx
// src/components/panel/PanelTable.jsx
// Props: title, subtitle, columns, rows, emptyText, loading, actions, pagination

<PanelTable
  title="Data Quality Rules"
  subtitle="3 rules, 2 passing"
  actions={<Button startIcon={<AddIcon />}>Add Rule</Button>}
  columns={[
    { key: 'name', header: 'Name', width: '40%', render: (v) => <Typography>{v}</Typography> },
    { key: 'severity', header: 'Severity', width: '20%', render: (v) => <Chip label={v} size="small" color={...} /> },
    { key: 'actions', header: '', width: '10%', align: 'right', render: () => <IconButton>...</IconButton> },
  ]}
  rows={rules}
  emptyText="No rules defined for this table."
  loading={loading}
  pagination={{ page, pageSize, total, onChange }}
/>
```

### 3.2 `PanelMetricRow.jsx` — Key-value detail row

```jsx
// src/components/panel/PanelMetricRow.jsx
// For simple label-value pairs (replaces DetailRow pattern everywhere)

<PanelMetricRow label="Locked" value="Yes" />
<PanelMetricRow label="Last verified" value="2026-07-15" />
```

### 3.3 `PanelGauge.jsx` — DQ circular gauge

```jsx
// src/components/panel/PanelGauge.jsx
// Replaces duplicated CircularProgress gauge code in MyDataPage.jsx and ModuleWorkspacePage.jsx

<PanelGauge score={dqScore} size={72} />
```

---

## 4. ALL TABS — BEFORE/AFTER

### 4.1 `DQMetricsTab` (RowDetailPage right panel)

**Current**: `<Stack spacing={2}>` → Status badge box → timestamp → re-run button → `<Divider />` → custom Box per result with `borderLeft` accent

**After**: 

```
┌──────────────────────────────────────────┐
│ DQ Metrics                  [Re-run ⭮]   │
├──────────────────────────────────────────┤
│ ┌─────────┬──────────┬─────────────────┐ │
│ │Status   │Rule      │Detail           │ │
│ ├─────────┼──────────┼─────────────────┤ │
│ │✅ Pass  │completen…│Completeness: …  │ │
│ │❌ Fail  │freshness…│Last updated: …  │ │
│ │⚠ Warn   │accuracy_…│Field: building  │ │
│ └─────────┴──────────┴─────────────────┘ │
│                                          │
│ Last run: 2026-08-03 14:22               │
│ 2/3 passing                              │
└──────────────────────────────────────────┘
```

Columns: Status (Chip✅/❌/⚠), Rule Name (Typography), Detail (Typography secondary)

### 4.2 `RelatedRecordsTab` — COMPLETE REDESIGN ← MAIN TASK

**Current**: Fetches `dataschema/rows/?data_table=${tableId}&page_size=8`, dumps ALL rows as clickable Box divs with tiny 0.58rem chips showing random key-value pairs. Page size ignored. No filtering. No grouping. No meaning.

**What it should do instead — THE MEANINGFUL REDESIGN:**

Given a row in table T, find related rows **through actual data relationships**, not just same-table neighbors.

**Algorithm:**

```
1. Read the row's values (JSON field)
2. For each value key in the row:
   a. Find DataField entries where name matches the key AND reference_table IS NOT NULL
   b. These are FK fields — the value points to a row in another table
3. For each FK field found:
   a. Query the referenced table: dataschema/rows/?data_table={refTableId}&search={fkValue}
   b. Group results by relationship type
4. ALSO: Query dataschema/relations/ for explicit TableRelations where:
   a. from_table = current table (outgoing FK) OR
   b. to_table = current table (incoming FK)
5. Build relationship groups:
   - "Linked by Building": 3 rows in Facilities - Water (same building_id)
   - "Same emission factor": 12 rows across 2 tables
   - "Referenced by": 1 row in Procurement - Supplier Contracts
6. Each group is a collapsible section with count + table name
7. Click group → expands to show actual rows in MUI Table
```

**API calls:**

```
# 1. Find FK fields on this table
GET dataschema/fields/?data_table={tableId}

# 2. Find explicit relations
GET dataschema/relations/?from_table={tableId}
GET dataschema/relations/?to_table={tableId}

# 3. For each FK field that has a value in this row, find linked rows
GET dataschema/rows/?data_table={refTableId}&{fkFieldName}={fkValue}

# 4. Get calculation links (rows in same calc batch)
GET carbon/calculations/?data_row_id={rowId}
```

**The UI — NOT a stupid DB dump:**

```
┌──────────────────────────────────────────────┐
│ Related Records                              │
├──────────────────────────────────────────────┤
│                                              │
│ ┌─ Linked by Building ────────────────────┐  │
│ │ Building ID: BLDG-014                    │  │
│ │                                         │  │
│ │ Facilities - Water          3 rows  ▸   │  │  ← clickable group
│ │ Facilities - Chilled Water  2 rows  ▸   │  │
│ └─────────────────────────────────────────┘  │
│                                              │
│ ┌─ Linked by Emission Factor ─────────────┐  │
│ │ EF: EG-Grid-2024 (0.42 kgCO₂e/kWh)      │  │
│ │                                         │  │
│ │ This table                  5 rows  ▸   │  │
│ │ Transport - Fleet Fuel      2 rows  ▸   │  │
│ └─────────────────────────────────────────┘  │
│                                              │
│ ┌─ Temporal Neighbors ────────────────────┐  │
│ │ Same building, adjacent months           │  │
│ │                                         │  │
│ │ ← Previous: Feb 2026    34,521 kWh  ▸   │  │
│ │ → Next:     Apr 2026    36,102 kWh  ▸   │  │
│ └─────────────────────────────────────────┘  │
│                                              │
│ No other relationships found.                │
└──────────────────────────────────────────────┘
```

Each group:
- **Collapsible** (Accordion or click-to-expand)
- Shows **relationship type** as header
- Shows **the shared value** (building name, factor code, period)
- Lists **target tables** with row counts
- Clicking a table row expands to show **actual rows in a nested MUI Table**
- Each nested row is **clickable** → navigates to that row's detail page

**Empty state when no FK relationships exist:**
Fall back to showing "Temporal neighbors" (previous/next row in same table, sorted by period_month if available). If that also fails, show "No related records found — this row has no foreign key relationships or temporal neighbors."

### 4.3 `RowHistoryTab` (RowDetailPage inline)

**Current**: Fetches `carbon/calculation-audits/`, maps to events with action/description/timestamp. Shows plain Box list. 40+ "update —" entries.

**After**:

```
┌──────────────────────────────────────────┐
│ Activity Log                             │
├──────────────────────────────────────────┤
│ ┌────────┬──────────────────┬──────────┐ │
│ │Type    │Detail            │When      │ │
│ ├────────┼──────────────────┼──────────┤ │
│ │Calc    │CO₂e calculated   │Aug 3     │ │
│ │Data    │Row updated       │Aug 2     │ │
│ │Data    │Row created       │Jul 28    │ │
│ └────────┴──────────────────┴──────────┘ │
│                                          │
│ 1–10 of 42    [<] [>]                    │
└──────────────────────────────────────────┘
```

- Add **pagination** (page_size=10 default)
- Fetch from `dataschema/schema-logs/?data_table={tableId}&row_id={rowId}` instead of calculation-audits (or merge both)
- Columns: Type (Chip: Data/Calc/DQ/Gov), Detail (Typography), When (Typography secondary + relative time)
- If detail is empty, show action as detail — never show "update —"

### 4.4 `RowLineageTab` (RowDetailPage inline)

**Current**: `<Box>` with `borderLeft: '2px solid'` + custom cards per calculation. Factor name → code → scope/category chips → CO₂e output.

**After**:

```
┌──────────────────────────────────────────────┐
│ Emission Lineage                             │
├──────────────────────────────────────────────┤
│ ┌──────────────┬──────────┬────────────────┐ │
│ │Factor        │Scope     │Output          │ │
│ ├──────────────┼──────────┼────────────────┤ │
│ │EG-Grid-2024  │Scope 2   │12.543 tCO₂e   │ │
│ │  (EG-GRID)   │Energy    │Aug 3, 2026     │ │
│ ├──────────────┼──────────┼────────────────┤ │
│ │NG-Stationary │Scope 1   │8.210 tCO₂e    │ │
│ │  (NG-STAT)   │Stationary│Aug 3, 2026     │ │
│ └──────────────┴──────────┴────────────────┘ │
│ Total: 20.753 tCO₂e                          │
└──────────────────────────────────────────────┘
```

Columns: Factor (name + code monospace), Scope/Category (Chip + Chip), Output (tCO₂e bold + calculated date)

### 4.5 L1 `TrustTab` (MyDataPage)

**Current**: `display:grid` with `gridTemplateColumns: '120px 1fr'`, DQ gauge outside the grid

**After**:

```
┌──────────────────────────────────────┐
│ Trust                                │
├──────────────────────────────────────┤
│          ╭─────╮                     │
│          │ 78% │   DQ Score          │
│          ╰─────╯   Passing           │
│                                      │
│ ┌────────────────┬─────────────────┐ │
│ │Failing rules   │2                │ │
│ │Locked          │No               │ │
│ │Last verified   │Jul 15, 2026     │ │
│ │Evidence        │5 docs           │ │
│ │Quality status  │Passing          │ │
│ └────────────────┴─────────────────┘ │
└──────────────────────────────────────┘
```

Use `PanelTable` with 2 columns: Metric (12 chars max, secondary), Value (bold). DQ gauge stays as-is but wrapped in `PanelGauge`.

### 4.6 L1 `ImpactTab` (MyDataPage)

**Current**: Same `display:grid` pattern + custom dependency chain chips

**After**:

```
┌──────────────────────────────────────┐
│ Impact                               │
├──────────────────────────────────────┤
│ Source → Tables → Calc → Reports     │  ← keep chip chain
│ ─────────────────────────────────    │
│ ┌────────────────┬─────────────────┐ │
│ │SBTi targets    │2 reference this │ │
│ │Calculations    │1,840 records    │ │
│ │Data consumers  │[Carbon app]     │ │
│ └────────────────┴─────────────────┘ │
└──────────────────────────────────────┘
```

Dependency chain is the only non-table visual that makes sense — keep it. Rest → `PanelTable`.

### 4.7 L2 `ModuleHealthTab` (ModuleWorkspacePage)

**Current**: Custom Box with CircularProgress gauge, LinearProgress, per-table score bars

**After**:

```
┌──────────────────────────────────────┐
│ Health                               │
├──────────────────────────────────────┤
│          ╭─────╮                     │
│          │ 82% │   DQ Score          │
│          ╰─────╯   Passing           │
│                                      │
│ Completion   ████████████░   91%     │
│              10/11 tables            │
│                                      │
│ Table Quality                        │
│ ┌──────────────────┬──────┬────────┐ │
│ │Table             │DQ%   │Failing │ │
│ ├──────────────────┼──────┼────────┤ │
│ │Monthly Electric   │92%   │0/3     │ │
│ │Daily Water        │88%   │1/4     │ │
│ │Chilled Water      │  —   │0/0     │ │
│ └──────────────────┴──────┴────────┘ │
└──────────────────────────────────────┘
```

Top section: `PanelGauge` + completion bar (keep LinearProgress). Bottom: `PanelTable` with columns: Table (Typography bold), DQ% (colored Typography), Failing (Typography secondary).

### 4.8 L2 `ModuleLineageTab` (ModuleWorkspacePage)

**Current**: Custom Upstream/Downstream sections with `borderLeft` cards

**After**:

```
┌──────────────────────────────────────┐
│ Lineage                              │
├──────────────────────────────────────┤
│ Upstream (2)                         │
│ ┌──────────────────┬────────────────┐│
│ │Source Table      │Relation        ││
│ ├──────────────────┼────────────────┤│
│ │Facilities Meters │one_to_many     ││
│ │Building Registry  │lookup          ││
│ └──────────────────┴────────────────┘│
│                                      │
│ Downstream (1)                       │
│ ┌──────────────────┬────────────────┐│
│ │Target Table      │Relation        ││
│ ├──────────────────┼────────────────┤│
│ │Carbon Report     │consumes        ││
│ └──────────────────┴────────────────┘│
└──────────────────────────────────────┘
```

Use `PanelTable` with section headers. Columns: Table name, Relation type (Chip).

### 4.9 L2 `ModuleGovernanceTab` (ModuleWorkspacePage)

**Current**: Mixed lock icon + DetailRow + policy list

**After**:

```
┌──────────────────────────────────────┐
│ Governance                           │
├──────────────────────────────────────┤
│ 🔒 Locked — Write operations blocked │
│ ─────────────────────────────────    │
│ ┌────────────────┬─────────────────┐ │
│ │Org unit        │AAST Facilities  │ │
│ │Last verified   │Jul 15, 2026     │ │
│ │Tables          │11               │ │
│ └────────────────┴─────────────────┘ │
│                                      │
│ Active Policies (2)                  │
│ ┌──────────────────┬───────────────┐ │
│ │Policy            │Type / Scope   │ │
│ ├──────────────────┼───────────────┤ │
│ │Data Retention    │retention·org  │ │
│ │DQ Threshold      │quality ·table │ │
│ └──────────────────┴───────────────┘ │
└──────────────────────────────────────┘
```

Lock status stays as prominent icon. Detail rows → `PanelTable`. Policies → `PanelTable`.

---

## 5. CONFIGURABLE RIGHT PANEL

The `EntityDetailShell` + `useDetailPanel` already support:
- Resizable panel width (stored in localStorage)
- Toggle open/close (`›` button)
- Tab switching with localStorage persistence

**What we add:**

### 5.1 Panel Config Button (gear icon)

```
┌──────────────────────────────────────────┐
│ [Trust] [Impact] [Activity]    [⚙] [✕]  │  ← tabs + gear + close
├──────────────────────────────────────────┤
│ ...panel content...                      │
└──────────────────────────────────────────┘
```

Clicking ⚙ opens a `PanelConfigDialog`:

```
┌────────────────────────────────┐
│ Configure Right Panel          │
│                                │
│ Visible Tabs:                  │
│ ☑ Trust                       │
│ ☑ Impact                      │
│ ☑ Activity                    │
│ ☐ Lineage      (available)    │
│                                │
│ Default Tab: [Trust ▾]        │
│                                │
│ Panel Width: [━━━━━●━━] 350px │
│                                │
│ [Reset to Defaults] [Save]    │
└────────────────────────────────┘
```

### 5.2 Implementation

Extend `useDetailPanel` with:

```jsx
const {
  metricsPanel,
  metricsTabs,         // ALL available tabs
  visibleTabs,         // filtered by user config
  activeMetricsTab,
  onMetricsTabChange,
  resetTab,
  panelConfig,         // { visible, defaultTab, width }
  updatePanelConfig,   // (patch) => void
  resetPanelConfig,    // () => void
  PanelConfigButton,   // <IconButton> ready to render
} = useDetailPanel({
  tabs: [...],
  storageKey: 'myData:panel',
  configurable: true,  // ← NEW: enables gear icon + dialog
  allAvailableTabs: [  // ← NEW: tabs user can add
    { label: 'Lineage', render: () => <LineageTab /> },
  ],
});
```

### 5.3 Configuration per page

| Page | Default visible tabs | Available hidden tabs |
|---|---|---|
| MyDataPage (L1) | Trust, Impact, Activity | Lineage (add later) |
| ModuleWorkspacePage (L2) | Health, Lineage, Governance, Activity | Audit Trail (future) |
| RowDetailPage (L4) | DQ Metrics, Lineage, Related | Calculations (future) |

Config stored as: `localStorage['myData:panel:config'] = JSON.stringify({ visible: ['Trust','Impact','Activity'], defaultTab: 0, width: 350 })`

---

## 6. FILE MANIFEST

### New files to create:
```
carbon-frontend/src/components/panel/
├── PanelTable.jsx          # Reusable table wrapper
├── PanelMetricRow.jsx      # Key-value detail row
├── PanelGauge.jsx          # Circular DQ gauge
├── PanelConfigDialog.jsx   # Configuration dialog
└── index.js                # Barrel export
```

### Files to modify:
```
carbon-frontend/src/components/entity/useDetailPanel.js   # Add configurable support
carbon-frontend/src/pages/dataschema/metrics/
├── DQMetricsTab.jsx          # → PanelTable pattern
├── RelatedRecordsTab.jsx     # → COMPLETE REDESIGN (FK-linked)
├── DataLineageTab.jsx        # → PanelTable pattern
carbon-frontend/src/pages/dataschema/RowDetailPage.jsx    # Update tab imports, add config button
carbon-frontend/src/pages/carbon/MyDataPage.jsx           # TrustTab/ImpactTab → PanelTable
carbon-frontend/src/pages/carbon/ModuleWorkspacePage.jsx  # All 4 tabs → PanelTable
```

### Files to NOT touch:
```
carbon-frontend/src/components/entity/EntityDetailShell.jsx  # Already solid
carbon-frontend/src/api/                                      # No API changes needed
backend/                                                      # Backend stays as-is
```

---

## 7. DO NOT

- Do NOT create a generic "TableRenderer" that tries to handle every possible data shape — `PanelTable` has a well-defined column/render contract
- Do NOT change the EntityDetailShell layout — it's proven and stable
- Do NOT break existing localStorage keys — migrate old keys if needed
- Do NOT remove the DQ gauge — it stays, just wrap it in `PanelGauge`
- Do NOT touch backend code — this is frontend-only
- Do NOT use hardcoded hex colors — theme.palette ONLY
- Do NOT use `sx` for colors when `color` prop on Chip works

---

## 8. VERIFICATION

```bash
cd carbon-frontend && npm run build 2>&1 | tail -5
# Must build clean — 0 errors

./.ai-toolkit/scripts/verify.sh antipatterns
# Must pass — 0 hardcoded hex, 0 sx={{ color: '#...' }}
```

Manual checks:
1. Open `/carbon/my-data` → click a row → all 3 right-panel tabs use PanelTable
2. Open `/carbon/my-data/33` → Health tab uses PanelGauge + PanelTable
3. Open `/carbon/my-data/row/69/476` → Related tab shows FK-linked groups, not same-table dump
4. Click gear icon → config dialog opens → uncheck a tab → tab disappears
5. Refresh → config persists
6. Dark mode → all tables, chips, gauges adjust correctly

---

## 9. RELATED TAB — Business Logic Spec

This is the most important redesign. Here's the exact algorithm:

### Step 1: Determine the row's "identity"
```
From the row's values JSON, extract identity fields:
- building_id, building, meter_id, meter
- supplier, supplier_id
- period_month, period, month, year
- Any field that has a corresponding DataField with reference_table != null
```

### Step 2: Find FK relationships
```
GET dataschema/fields/?data_table={tableId}
→ For each field where reference_table is not null AND the row has a value for field.name:
  → This is a live FK
  → Store: { fkField, fkValue, refTableId }
```

### Step 3: Find explicit TableRelations
```
GET dataschema/relations/?from_table={tableId}
GET dataschema/relations/?to_table={tableId}
→ Build list of related tables with relation_type and label
```

### Step 4: For each FK relationship, fetch related rows
```
For each FK:
  GET dataschema/rows/?data_table={refTableId}&{fkField.name}={fkValue}
  → Group by refTableId
  → Label: "Linked by {fkField.label}" (e.g., "Linked by Building")
```

### Step 5: Find temporal neighbors (same table, adjacent rows)
```
If the row has period_month or month:
  GET dataschema/rows/?data_table={tableId}&ordering=period_month
  → Find previous and next row by period_month
  → Show as "Temporal Neighbors" group
```

### Step 6: Find calculation-linked rows
```
GET carbon/calculations/?data_row_id={rowId}
→ Extract emission_factor_id from each calculation
→ Find other rows using the same emission factor:
  GET carbon/calculations/?emission_factor_id={factorId}
  → Group by table
  → Show as "Same Emission Factor" group
```

### Step 7: Build the display
```
Group results by relationship type with meaningful labels:
- "Linked by Building" (FK on building_id)
- "Linked by Supplier" (FK on supplier_id)
- "Same Emission Factor" (same EF)
- "Temporal Neighbors" (prev/next period)

Each group:
- Collapsible Accordion
- Header shows: relationship label + total row count
- Expanded content: MUI Table with columns:
  [Table Name, Row Label, Key Values, DQ%]
- Clicking a row navigates to that row's detail page
```

### Empty state (no relationships found at all):
```
"Nothing to relate — this row has no foreign keys to other tables, 
no temporal neighbors, and no calculation links."
```

---

## 10. IMPLEMENTATION ORDER

1. **Create `PanelTable.jsx`** — the foundation everything else uses
2. **Create `PanelGauge.jsx`** — shared DQ gauge
3. **Create `PanelMetricRow.jsx`** — shared key-value row
4. **Standardize DQMetricsTab** → PanelTable (simplest, good warmup)
5. **Standardize RowLineageTab** → PanelTable
6. **Standardize RowHistoryTab** → PanelTable with pagination
7. **REDESIGN RelatedRecordsTab** → FK-linked smart groups (the main event)
8. **Standardize L1 TrustTab + ImpactTab** → PanelTable + PanelGauge
9. **Standardize L2 all 4 tabs** → PanelTable + PanelGauge
10. **Add configurable panel** → gear icon + PanelConfigDialog
11. **Build + verify**

---

*End of TASK spec. Assign to Frontend Worker with model DeepSeek-V3.*
