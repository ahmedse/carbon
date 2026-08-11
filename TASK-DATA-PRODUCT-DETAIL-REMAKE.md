# TASK: Remake Data Product Detail Page (Enterprise-Grade)

**Role**: `frontend-worker` + `backend-worker`  
**Created**: 2026-08-11  
**Status**: Not started  
**Related**: TASK-DELETE-SAFETY-ENTERPRISE.md (pattern reference), ReferenceSetDetailPage (UI pattern)

---

## 1. AUDIT FINDINGS — Current Page Analysis

### A. Architecture Violations

| # | Flaw | Severity | Detail |
|---|------|----------|--------|
| A1 | **No BaseDetailPage pattern** | 🔴 Critical | Raw Grid+Card layout; ReferenceSetDetailPage already uses the standardized 3-column tab layout (BaseDetailPage + tabs). Every detail page MUST follow this. |
| A2 | **window.confirm anti-pattern** | 🔴 Critical | Two `window.confirm()` calls (lines 112, 139) violate compact-ui.md Hard Rule: "MUI Dialog replace window.confirm". Must use `ConfirmDialog` component. |
| A3 | **Module from context, not API** | 🔴 Critical | `const module = (context?.modules || []).find(...)` — stale. If module was just edited in the modal on this page, it won't refresh until `selectProject()` re-fetches all modules. Must fetch Module directly from `/core/modules/{id}/`. |
| A4 | **No tab organization** | 🟠 High | Flat page. ReferenceSetDetailPage has 4 tabs (Overview, Edit, Values, Metrics). Product detail needs: Overview, Tables, DQ, Audit at minimum. |
| A5 | **No metrics panel** | 🟠 High | No right sidebar with quick stats. ReferenceSetMetricsPanel shows pattern: MetricCard, MetricsGrid, MetricsSection. |
| A6 | **Card-based table listing wastes space** | 🟠 High | Each table renders a full `Card` with CardHeader+CardContent. For 5+ tables, scrolling is painful. Use compact DataGrid (compact-ui spec: `density="compact"`, `fontSize: '0.65rem'`). |
| A7 | **Inline Product Edit dialog duplicates DataProductsPage** | 🟠 Medium | The 4-field edit form (name, description, scope, org unit) is duplicated verbatim from the list page's `ProductDialog`. Must use shared component. |
| A8 | **No governance/locked display** | 🟡 Medium | `is_locked` field exists on Module model; backend enforces it in `destroy()`. Frontend shows nothing. |
| A9 | **No audit trail** | 🟡 Medium | `GovernanceEvent` model exists in catalog app but is never queried for this page. |
| A10 | **No quality summary** | 🟡 Medium | DQ status shows as a Chip with color but no aggregate score, pass/fail counts, or trend. |

### B. compact-ui.md Violations

| # | Rule Broken | Fix |
|---|-------------|-----|
| B1 | "Dialogs use theme defaults — no extra padding" | `DialogContent sx={{ pt: 2 }}` and `TextField margin="normal"` add non-standard spacing |
| B2 | "DataGrid uses density='compact'" | No DataGrid currently; when added, must use compact |
| B3 | "Chip/badge: borderRadius: 3, fontSize: '0.65rem'" | Scope chip inline, should use theme Chip overrides |
| B4 | "Scope badges use semantic colors" | `SCOPE_LABEL` shown as text, not color-coded Chips (scope1=error.main, scope2=warning.main, scope3=primary.main) |
| B5 | "ALWAYS use size='small' on inputs" | TextFields in dialogs don't explicitly set `size="small"` (though theme default may apply) |

### C. Backend Gaps

| # | Gap | Detail |
|---|------|--------|
| C1 | **No dedicated Module detail endpoint** | ModuleViewSet is a vanilla ModelViewSet — `retrieve()` works fine. But no aggregated stats (table_count, quality_summary, last_activity) in a single call. |
| C2 | **No module-level quality aggregation API** | DQ status is per-table via AssetProfile. No endpoint for "all tables in this module: aggregate quality". |
| C3 | **No governance events filtered by module** | `GovernanceEvent` has `entity_type` and `entity_id` but no FK to Module directly. Events for a module's tables aren't easily queried. |
| C4 | **No import/export history per product** | ImportExport models exist but aren't linked to Module in an aggregated view. |

---

## 2. REFERENCE PATTERNS STUDIED

### A. ReferenceSetDetailPage (Internal Pattern ✅)

```
ReferenceSetDetailPage.jsx
├── BaseDetailPage
│   ├── headerComponent: DetailHeader (breadcrumbs handled by shell)
│   ├── mainTabs: [Overview, Edit, Values]
│   ├── metricsTabs: [Metrics]
│   ├── storageKey: "carbonReferenceSetDetail"
│   ├── entityData={refSet}
│   └── additionalProps={{ selectOptions, values, onRefSetUpdated, onValuesUpdated }}
└── Tabs/
    ├── ReferenceSetOverviewTab.jsx → Read-only metadata (DetailTabContent + Table rows)
    ├── ReferenceSetEditTab.jsx → Form fields + lifecycle transitions
    ├── ReferenceSetValuesTab.jsx → DataGrid of child values
    └── ReferenceSetMetricsPanel.jsx → MetricCards + Divider + Governance summary
```

### B. Top Data Catalog Systems (External Research)

| System | Key Detail Page Features |
|--------|--------------------------|
| **Alation** | Overview tab: description, domain, stewards, tags, classification, quality score. Schema tab: columns with types, descriptions. Lineage tab: visual graph. Quality tab: rules results, trends. |
| **Unity Catalog (Databricks)** | Asset detail: schema browser, lineage graph, quality dashboard, tags/ownership, data profiling stats, permission viewer. |
| **Atlan** | Left: metadata panel (description, owners, tags, glossary). Center: schema with column-level details. Right: quality metrics, lineage, usage stats. |
| **Collibra** | Overview + Schema + Lineage + Quality + Issues + History tabs. Right panel: responsibility assignment matrix. |

**Common patterns across all 4 systems:**
1. Tab-based layout (Overview → Schema → Quality → Lineage → Audit)
2. Right panel with key metrics (owner, steward, quality score, freshness, row count)
3. Quality scores displayed as gauges/bars with color coding (green/amber/red)
4. Child assets (tables) shown as searchable table, not cards
5. Governance metadata prominently displayed (classification, domain, PII flags)
6. Audit/history trail with user, timestamp, action

---

## 3. TARGET ARCHITECTURE

### Page Structure (After Remake)

```
DataProductDetailPage.jsx
├── BaseDetailPage (standardized 3-column layout)
│   ├── headerComponent: DetailHeader
│   │   └── [Inventory2Icon] "Product Name" · Scope Chip · Org Unit · Locked Badge
│   │
│   ├── mainTabs:
│   │   ├── [1] Overview Tab → DataProductOverviewTab
│   │   │   ├── DetailTabContent
│   │   │   ├── Basic Info (name, scope, org unit, description, table count)
│   │   │   ├── Governance (locked status, created/updated dates)
│   │   │   └── Quality Summary (aggregate pass/warning/fail chart)
│   │   │
│   │   ├── [2] Tables Tab → DataProductTablesTab
│   │   │   ├── DetailTabContent
│   │   │   ├── FilterBar (search + scope filter)
│   │   │   ├── Compact DataGrid (density="compact")
│   │   │   │   ├── Name (navigable link)
│   │   │   │   ├── Description
│   │   │   │   ├── Quality Status (Chip)
│   │   │   │   ├── Fields Count
│   │   │   │   ├── Rows (if available)
│   │   │   │   ├── Last Modified
│   │   │   │   └── Actions (view/edit/delete — admin-gated)
│   │   │   ├── ConfirmDialog (delete confirmation)
│   │   │   └── TableDialog (create/edit form)
│   │   │
│   │   ├── [3] DQ Tab → DataProductDQTab
│   │   │   ├── DetailTabContent
│   │   │   ├── Overall quality score card
│   │   │   ├── Per-table quality breakdown (DataGrid)
│   │   │   └── Link to DQ Workspace for detailed rules
│   │   │
│   │   ├── [4] Edit Tab → DataProductEditTab (admin-gated)
│   │   │   ├── DetailTabContent
│   │   │   ├── Shared ProductForm (name, description, scope, org_unit)
│   │   │   ├── Lock/Unlock toggle
│   │   │   ├── Delete with ConfirmDialog (shows table count warning)
│   │   │   └── Save + Cancel buttons
│   │   │
│   │   └── [5] Audit Tab → DataProductAuditTab
│   │       ├── DetailTabContent
│   │       └── GovernanceEvents DataGrid (action, entity, user, timestamp)
│   │
│   ├── metricsTabs:
│   │   └── [1] Metrics → DataProductMetricsPanel
│   │       ├── MetricCard: Table Count
│   │       ├── MetricCard: Total Rows
│   │       ├── MetricCard: Quality Pass Rate
│   │       ├── MetricCard: Last Modified
│   │       ├── Divider
│   │       ├── Governance summary (org unit, scope, steward)
│   │       └── Locked status indicator
│   │
│   ├── storageKey: "carbonDataProductDetail"
│   └── entityData={product}
```

### Component Tree (Reusable)

```
src/
├── components/
│   ├── detail/
│   │   ├── BaseDetailPage.jsx        (existing, reuse)
│   │   ├── DetailHeader.jsx           (existing, reuse)
│   │   ├── DetailMainPanel.jsx        (existing, reuse)
│   │   └── DetailMetricsPanel.jsx     (existing, reuse)
│   ├── dataproducts/
│   │   └── ProductForm.jsx            (NEW — shared between list page dialog + detail edit tab)
│   ├── ConfirmDialog.jsx              (existing, reuse — replace window.confirm)
│   └── FilteredDataGrid.jsx           (existing, reuse for tables tab)
│
├── pages/
│   └── catalog/
│       ├── DataProductDetailPage.jsx   (REWRITE — thin shell using BaseDetailPage)
│       ├── DataProductsPage.jsx        (UPDATE — use shared ProductForm)
│       └── tabs/
│           ├── DataProductOverviewTab.jsx    (NEW)
│           ├── DataProductTablesTab.jsx      (NEW)
│           ├── DataProductDQTab.jsx          (NEW)
│           ├── DataProductEditTab.jsx        (NEW)
│           ├── DataProductAuditTab.jsx       (NEW)
│           └── DataProductMetricsPanel.jsx   (NEW)
```

---

## 4. BACKEND CHANGES REQUIRED

### 4.1 Module Detail Serializer Enhancement
**File**: `backend/core/serializers.py`

Add computed fields to `ModuleSerializer`:
- `table_count` (IntegerField, source='data_tables.count') — already accessible via related_name
- `is_locked` — already in fields list ✅
- `created_at` — needs to be added to model or serialized from first table creation

**Action**: Add `created_at`, `updated_at` fields to Module model (or compute from related tables).

### 4.2 Module Model Enhancement
**File**: `backend/core/models.py`

Add timestamp fields:
```python
created_at = models.DateTimeField(auto_now_add=True, null=True)
updated_at = models.DateTimeField(auto_now=True, null=True)
```

### 4.3 Module Quality Aggregation Endpoint
**File**: `backend/core/views.py`

Add `@action(detail=True, methods=['get'])` → `quality_summary`:
```python
@action(detail=True, methods=['get'])
def quality_summary(self, request, pk=None):
    """Aggregate DQ stats for all tables in this module."""
    module = self.get_object()
    tables = module.data_tables.all()
    assets = AssetProfile.objects.filter(data_table__in=tables, data_field__isnull=True)
    summary = {
        'total': assets.count(),
        'passing': assets.filter(quality_status='passing').count(),
        'warning': assets.filter(quality_status='warning').count(),
        'failing': assets.filter(quality_status='failing').count(),
        'unknown': assets.filter(quality_status='unknown').count(),
        'avg_score': assets.aggregate(avg=Avg('quality_score'))['avg'],
    }
    return Response(summary)
```

### 4.4 Module Audit Events Endpoint
**File**: `backend/core/views.py`

Add `@action(detail=True, methods=['get'])` → `audit_trail`:
```python
@action(detail=True, methods=['get'])
def audit_trail(self, request, pk=None):
    """Governance events for this module and its tables."""
    module = self.get_object()
    table_ids = list(module.data_tables.values_list('id', flat=True))
    events = GovernanceEvent.objects.filter(
        Q(entity_type='module', entity_id=module.id) |
        Q(entity_type='datatable', entity_id__in=table_ids)
    ).order_by('-timestamp')[:100]
    return Response(GovernanceEventSerializer(events, many=True).data)
```

---

## 5. FRONTEND CHANGES — Step by Step

### Phase 1: Shared ProductForm Component

**File**: `carbon-frontend/src/components/dataproducts/ProductForm.jsx` (NEW)

Extract the form from DataProductsPage.jsx `ProductDialog` into a reusable component:
- Props: `{ form, onChange, orgUnits, error, readOnly }`
- Fields: Name, Description, Scope (Autocomplete), OrgUnit (Autocomplete), IsLocked (Switch)
- Used by: DataProductsPage dialog AND DataProductEditTab
- MUST follow compact-ui: `size="small"`, no inline padding, theme colors

### Phase 2: Detail Page Shell

**File**: `carbon-frontend/src/pages/catalog/DataProductDetailPage.jsx` (REWRITE)

```jsx
export default function DataProductDetailPage() {
  // Fetch Module directly via API (NOT from context)
  // Fetch tables, asset profiles, org units, governance events
  // Use BaseDetailPage pattern EXACTLY as ReferenceSetDetailPage does
  
  const headerComponent = module ? (
    <DetailHeader
      title={module.name}
      description={`${module.description || ''}${module.org_unit_name ? ` · ${module.org_unit_name}` : ''}`}
      icon={Inventory2Icon}
      onClose={() => navigate(-1)}
    />
  ) : null;
  
  return (
    <BaseDetailPage
      headerComponent={headerComponent}
      mainTabs={[
        { label: 'Overview', component: DataProductOverviewTab },
        { label: 'Tables', component: DataProductTablesTab },
        { label: 'DQ', component: DataProductDQTab },
        ...(isAdmin ? [{ label: 'Edit', component: DataProductEditTab }] : []),
        { label: 'Audit', component: DataProductAuditTab },
      ]}
      metricsTabs={[
        { label: 'Metrics', component: DataProductMetricsPanel },
      ]}
      loading={loading}
      error={error}
      onClose={() => navigate(-1)}
      storageKey="carbonDataProductDetail"
      entityData={module}
      additionalProps={{ tables, assets, orgUnits, qualitySummary, auditEvents, isAdmin, onDataChanged }}
    />
  );
}
```

### Phase 3: Tab Components

#### 3.1 DataProductOverviewTab.jsx (NEW)
Pattern: `ReferenceSetOverviewTab.jsx`
- "Basic Information" table: Name, ID, Scope (Chip), Org Unit, Description
- "Governance" table: Locked Status (Chip), Created, Updated
- "Quality Summary" section: aggregate pass/warning/fail counts with colored Chips
- "Statistics" table: Table Count, Total Fields, Total Rows

#### 3.2 DataProductTablesTab.jsx (NEW)
Pattern: `FilteredDataGrid` from DataProductsPage
- Compact DataGrid (`density="compact"`, `fontSize: '0.65rem'`)
- Columns: Name (link), Description, Quality (Chip), Fields, Rows, Modified, Actions
- Toolbar: Search filter + Create button (admin-gated)
- Delete uses `ConfirmDialog`, not `window.confirm`
- Click row navigates to `/catalog/tables/{id}`

#### 3.3 DataProductDQTab.jsx (NEW)
- Overall quality score as a Card with large number + color
- Per-table breakdown: DataGrid of tables with quality columns
- Bar chart or gauge showing pass/warning/fail distribution
- Link to DQ Workspace for drill-down

#### 3.4 DataProductEditTab.jsx (NEW)
Pattern: `ReferenceSetEditTab.jsx`
- Uses shared `ProductForm` component
- Lock/Unlock Switch
- Delete section: ConfirmDialog with table count warning
- Uses AppFeedback error display (structured errors from backend)

#### 3.5 DataProductAuditTab.jsx (NEW)
- DataGrid of GovernanceEvents
- Columns: Action (Chip), Entity Type, Entity ID, User, Timestamp
- Default sort: timestamp descending

#### 3.6 DataProductMetricsPanel.jsx (NEW)
Pattern: `ReferenceSetMetricsPanel.jsx`
- MetricCards: Table Count, Total Rows, Quality Pass Rate, Last Activity
- Governance summary section
- Locked status with icon

### Phase 4: Anti-Pattern Fixes in DataProductsPage.jsx

- Replace inline `ProductDialog` with shared `ProductForm`
- Add `ConfirmDialog` wrapper (already exists in page, verify delete uses it)

---

## 6. ACCEPTANCE GATES

### Gate 1: Architecture Compliance
- [ ] Uses `BaseDetailPage` with tabs (not raw Grid+Card)
- [ ] Uses `DetailHeader` (breadcrumbs owned by shell)
- [ ] No `window.confirm` — all confirmations via `ConfirmDialog`
- [ ] All inputs use `size="small"`
- [ ] All spacing via theme tokens (`p:1`, `gap:1`), not raw px

### Gate 2: compact-ui.md Compliance
- [ ] No raw hex colors
- [ ] No raw font sizes (all via variant)
- [ ] DataGrid uses `density="compact"`
- [ ] Chips use theme size/color props
- [ ] Scope badges: scope1=error.main, scope2=warning.main, scope3=primary.main
- [ ] Dialog uses theme defaults (no extra padding)

### Gate 3: Functionality
- [ ] Module fetched directly via API (not from context)
- [ ] Tables listed in compact DataGrid with search/filter
- [ ] Table CRUD (create/edit/delete) works with ConfirmDialog
- [ ] Product edit with lock/unlock toggle
- [ ] Delete product with table-count warning + AppFeedback errors
- [ ] Quality summary tab shows aggregate DQ stats
- [ ] Audit tab shows governance events
- [ ] Metrics panel shows key stats
- [ ] Admin gating: Edit tab + Actions column hidden for non-admins

### Gate 4: No Regressions
- [ ] All 963 tests still pass
- [ ] DataProductsPage (`/catalog/products`) still works
- [ ] Table detail page (`/catalog/tables/:id`) still accessible
- [ ] DQ Workspace unaffected

### Gate 5: Visual Verification (browser)
- [ ] Page loads without MUI DataGrid "empty height" warnings
- [ ] Tab state persists across page reloads (localStorage)
- [ ] Metrics panel collapsible/resizable
- [ ] Responsive on narrow viewports (mobile-friendly)

---

## 7. FILES CHANGED SUMMARY

### Backend (4 files)
| File | Change |
|------|--------|
| `backend/core/models.py` | Add `created_at`, `updated_at` to Module |
| `backend/core/serializers.py` | Add computed fields (table_count, quality_summary) |
| `backend/core/views.py` | Add `quality_summary`, `audit_trail` @actions |
| `backend/core/migrations/` | Auto-generated migration |

### Frontend (9+ files)
| File | Change |
|------|--------|
| `carbon-frontend/src/components/dataproducts/ProductForm.jsx` | **NEW** — shared form component |
| `carbon-frontend/src/pages/catalog/DataProductDetailPage.jsx` | **REWRITE** — thin shell with BaseDetailPage |
| `carbon-frontend/src/pages/catalog/DataProductsPage.jsx` | **UPDATE** — use shared ProductForm |
| `carbon-frontend/src/pages/catalog/tabs/DataProductOverviewTab.jsx` | **NEW** |
| `carbon-frontend/src/pages/catalog/tabs/DataProductTablesTab.jsx` | **NEW** |
| `carbon-frontend/src/pages/catalog/tabs/DataProductDQTab.jsx` | **NEW** |
| `carbon-frontend/src/pages/catalog/tabs/DataProductEditTab.jsx` | **NEW** |
| `carbon-frontend/src/pages/catalog/tabs/DataProductAuditTab.jsx` | **NEW** |
| `carbon-frontend/src/pages/catalog/tabs/DataProductMetricsPanel.jsx` | **NEW** |
| `carbon-frontend/src/api/modules.js` | Add `fetchModule(id)`, `fetchModuleQualitySummary(id)`, `fetchModuleAuditTrail(id)` |

---

## 8. ROLLBACK PLAN

If the remake breaks functionality:
1. Revert DataProductDetailPage.jsx to current version
2. Remove new tab components (they're additive)
3. Backend @actions can stay (they're additive and harmless)
4. Shared ProductForm can stay (used by both pages)

---

## 9. ESTIMATED EFFORT

| Phase | Effort |
|-------|--------|
| Backend: Module timestamps + quality/audit endpoints | 30 min |
| Frontend: Shared ProductForm component | 20 min |
| Frontend: DataProductDetailPage shell (BaseDetailPage) | 30 min |
| Frontend: Overview Tab | 20 min |
| Frontend: Tables Tab (DataGrid + ConfirmDialog) | 45 min |
| Frontend: DQ Tab | 30 min |
| Frontend: Edit Tab (ProductForm + delete) | 25 min |
| Frontend: Audit Tab | 15 min |
| Frontend: Metrics Panel | 15 min |
| Frontend: DataProductsPage refactor (shared ProductForm) | 15 min |
| Testing + verification | 30 min |
| **Total** | **~4.5 hours** |
