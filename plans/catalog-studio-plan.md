# Catalog Studio — Full Design Plan

> **Status:** Architect-approved design. Awaiting implementation approval.  
> **Scope:** Full CRUD for schema catalog, schema manager, reference data, data sources, data exports, and consuming-system connections.  
> **Principle:** Build on top of the already-existing `catalog/`, `dataschema/`, `mdm/`, and `dq/` backend apps. Add only what is missing.

---

## 1. What already exists (foundation)

| Layer | What exists | State |
|---|---|---|
| `backend/catalog/` | `DataDomain`, `GlossaryTerm`, `Tag`, `AssetProfile`, `GovernanceEvent` — full CRUD API | ✅ Done |
| `backend/dataschema/` | `DataTable`, `DataField`, `DataRow`, `SchemaChangeLog` — full CRUD API | ✅ Done |
| `backend/mdm/` | `ReferenceSet`, `ReferenceValue`, `OrgUnit` — models + serializers, no `urls.py` | ⚠️ Incomplete |
| `backend/dq/` | `DQRule`, `DQResult`, `FieldProfile`, `TableProfile` — partial | ⚠️ Incomplete |
| Frontend: `TableManagerPage` | Admin-only schema editor (tables + fields), hidden in `dataschema` studio | ✅ But misplaced |
| Frontend: Shell studios | `home`, `emissions`, `dataschema`, `admin`, `settings`, `help` | ✅ Done |
| Frontend: Catalog API | **Zero** — no `src/api/catalog.js` exists | ❌ Missing |
| Frontend: Catalog pages | **Zero** — no catalog-facing pages exist | ❌ Missing |

---

## 2. What we are building

```
CATALOG STUDIO
├── Schema Catalog          ← browse all DataTables with AssetProfile metadata
├── Schema Manager          ← full CRUD: tables, fields, relations
├── Domains & Glossary      ← DataDomains, GlossaryTerms, Tags
├── Reference Data          ← ReferenceSets + ReferenceValues (MDM Tier A)
├── Data Sources            ← source system connections (NEW backend app: connections)
├── Data Exports            ← export configurations + jobs (NEW backend app: importexport)
├── Consuming Connections   ← external system API access (in connections app)
└── Governance Log          ← GovernanceEvent audit trail
```

---

## 3. System architecture diagram

```
                ┌────────────────────────────────────────────┐
                │        CATALOG STUDIO (frontend)            │
                │  Schema Catalog · Schema Manager ·          │
                │  Domains · Glossary · Ref Data ·            │
                │  Sources · Exports · Connections ·          │
                │  Governance Log                             │
                └───────────┬────────────────────────────────┘
                            │ REST API
          ┌─────────────────┼──────────────────────┐
          │                 │                      │
   catalog/ (existing)  dataschema/          mdm/ connections/
   DataDomain            DataTable            ReferenceSet  DataSource
   GlossaryTerm          DataField            ReferenceValue ConsumingConn
   Tag                   DataRow              OrgUnit       ExportProject
   AssetProfile          SchemaChangeLog                    ImportJob/ExportJob
   GovernanceEvent
```

---

## 4. Backend — New apps

### 4.1 `connections/` Django app

Tracks **source systems** (where data comes from) and **consuming systems** (where data goes).

**Models:**

```python
class DataSource(models.Model):
    SOURCE_TYPES = [
        ('excel', 'Excel / CSV'),
        ('database', 'Database'),
        ('api', 'REST API'),
        ('mdm', 'MDM System'),
        ('iot', 'IoT / Sensor'),
        ('manual', 'Manual Entry'),
    ]
    STATUS_CHOICES = [('active','Active'), ('inactive','Inactive'), ('error','Error')]

    name              CharField(120)
    slug              SlugField(unique)
    source_type       CharField(choices=SOURCE_TYPES)
    description       TextField(blank)
    connection_config JSONField(default=dict)   # host/path/credentials (mask in API)
    status            CharField(choices=STATUS_CHOICES, default='active')
    domain            FK(catalog.DataDomain, null)
    owner             FK(User, null)
    last_tested_at    DateTimeField(null)
    last_test_status  CharField(null, blank)
    created_at        auto_now_add
    updated_at        auto_now

class ConsumingConnection(models.Model):
    SYSTEM_TYPES = [
        ('pulse',    'Pulse AI'),
        ('powerbi',  'Power BI'),
        ('tableau',  'Tableau'),
        ('api_key',  'API Client'),
        ('webhook',  'Webhook'),
    ]
    name         CharField(120)
    slug         SlugField(unique)
    system_type  CharField(choices=SYSTEM_TYPES)
    description  TextField(blank)
    api_key      CharField(64, blank)   # shown once on create, stored hashed
    scopes       JSONField(default=list) # list of DataTable IDs or domain slugs
    is_active    BooleanField(default=True)
    owner        FK(User, null)
    last_used_at DateTimeField(null)
    created_at   auto_now_add
    updated_at   auto_now
```

**API** (`/carbon-api/connections/…`):
- `GET/POST/PUT/DELETE /sources/`
- `GET/POST/PUT/DELETE /consuming/`
- `POST /sources/{id}/test/` — test connectivity, write `last_tested_at` + `last_test_status`
- `POST /consuming/{id}/rotate-key/` — regenerate API key

**RBAC:** Global admin for write; read limited to owners/stewards.

---

### 4.2 `importexport/` Django app

Handles bulk import jobs and named export projects/jobs (the app described in `docs/importexport_app/importexport-design-v1.0.md` — now implemented).

**Models:**

```python
class ExportProject(models.Model):
    FORMATS = [('csv','CSV'), ('excel','Excel'), ('json','JSON')]
    SCHEDULES = [('manual','Manual'), ('daily','Daily'), ('weekly','Weekly')]

    name         CharField(120)
    slug         SlugField(unique)
    description  TextField(blank)
    data_table   FK(dataschema.DataTable, null)  # null = multi-table export
    format       CharField(choices=FORMATS, default='excel')
    filters      JSONField(default=dict)          # field filters, date range, etc.
    schedule     CharField(choices=SCHEDULES, default='manual')
    is_active    BooleanField(default=True)
    owner        FK(User, null)
    created_at   auto_now_add
    updated_at   auto_now

class ImportJob(models.Model):
    STATUS = [('pending','Pending'),('running','Running'),('done','Done'),('failed','Failed')]

    data_table   FK(dataschema.DataTable)
    source       FK(connections.DataSource, null, blank)
    file         FileField(upload_to='imports/%Y/%m/')
    format       CharField(choices=[('csv','CSV'),('excel','Excel')], default='excel')
    status       CharField(choices=STATUS, default='pending')
    row_count    IntegerField(null)
    error_count  IntegerField(null)
    log          JSONField(default=list)           # list of {row, error} objects
    user         FK(User, null)
    started_at   DateTimeField(null)
    finished_at  DateTimeField(null)
    created_at   auto_now_add

class ExportJob(models.Model):
    STATUS = [('pending','Pending'),('running','Running'),('ready','Ready'),('failed','Failed')]

    export_project FK(ExportProject, null, blank)  # null = ad-hoc
    data_table     FK(dataschema.DataTable, null, blank)
    format         CharField(choices=[('csv','CSV'),('excel','Excel'),('json','JSON')])
    filters        JSONField(default=dict)
    file           FileField(null, blank, upload_to='exports/%Y/%m/')
    status         CharField(choices=STATUS, default='pending')
    row_count      IntegerField(null)
    user           FK(User, null)
    started_at     DateTimeField(null)
    finished_at    DateTimeField(null)
    created_at     auto_now_add
```

**API** (`/carbon-api/importexport/…`):
- `GET/POST/PUT/DELETE /export-projects/`
- `POST /import/` — upload file + table_id → creates ImportJob, runs sync (async-ready)
- `GET /import/{job_id}/` — job detail + log
- `POST /export/` — create ad-hoc ExportJob (table_id + filters + format)
- `POST /export-projects/{id}/run/` — trigger ExportJob from project
- `GET /export/{job_id}/download/` — download file when ready
- `GET /import/` + `GET /export/` — job history lists

---

### 4.3 `mdm/` — Complete missing URLs + views

`backend/mdm/` has models and serializers but no `urls.py` registered.

**Add:**
- `urls.py` with router: `reference-sets/`, `reference-values/`, `org-units/`
- `views.py` for all three models with full CRUD
- Register in `config/urls.py` under `/carbon-api/mdm/`

---

## 5. Backend — Additions to existing apps

### 5.1 `dataschema/` — Table Relations

Currently `DataField.reference_table` is a FK from one field to another DataTable — that is an implicit relation. We add an **explicit** `TableRelation` model for proper lineage and schema manager UI.

```python
class TableRelation(models.Model):
    RELATION_TYPES = [
        ('one_to_many',  'One → Many'),
        ('many_to_many', 'Many → Many'),
        ('lookup',       'Lookup'),
    ]
    from_table   FK(DataTable, related_name='outgoing_relations')
    from_field   FK(DataField, null, blank)  # the FK column on from_table
    to_table     FK(DataTable, related_name='incoming_relations')
    to_field     FK(DataField, null, blank)  # the PK/target column on to_table
    relation_type CharField(choices=RELATION_TYPES, default='one_to_many')
    label         CharField(120, blank)
    description   TextField(blank)
    created_by    FK(User, null)
    created_at    auto_now_add
```

**API additions to `dataschema/`:**
- `GET/POST /tables/{id}/relations/`
- `DELETE /relations/{id}/`

---

## 6. Frontend — Catalog Studio

### 6.1 New Studio in Shell

**`shell/Shell.jsx` changes:**
- Add `catalog` to `STUDIO_PATHS` → `/catalog`
- Add `catalog` to `studioFromPath` (paths starting with `/catalog`)

**`shell/useShellState.js` changes:**
- Add `catalog` studio entry: `{ id: 'catalog', label: 'Knowledge Catalog', icon: LibraryBooksIcon }`

**`shell/ShellSidebar.jsx` changes:**
Add `case 'catalog'` in `getSidebarItems()`:
```
- Schema Catalog       /catalog/schemas
- Schema Manager       /catalog/schema-manager
- Domains              /catalog/domains
- Business Glossary    /catalog/glossary
- Tags                 /catalog/tags
- Reference Data       /catalog/reference-data
- Data Sources         /catalog/sources
- Data Exports         /catalog/exports
- Connections          /catalog/connections
- Governance Log       /catalog/governance
```

---

### 6.2 New API module: `src/api/catalog.js`

Full wrapper for all catalog-related endpoints:
- `fetchDomains()`, `createDomain()`, `updateDomain()`, `deleteDomain()`
- `fetchGlossaryTerms()`, CRUD
- `fetchTags()`, CRUD
- `fetchAssetProfiles()`, `updateAssetProfile()`
- `searchCatalog(q)`
- `fetchGovernanceEvents()`
- `fetchReferenceSets()`, CRUD
- `fetchReferenceValues(setId)`, CRUD
- `fetchDataSources()`, CRUD, `testDataSource(id)`
- `fetchConsumingConnections()`, CRUD, `rotateApiKey(id)`
- `fetchExportProjects()`, CRUD, `runExportProject(id)`
- `fetchImportJobs()`, `createImportJob(file, tableId)`
- `fetchExportJobs()`, `createExportJob(tableId, format, filters)`
- `downloadExportJob(jobId)`

---

### 6.3 Pages (new directory: `src/pages/catalog/`)

| Route | Component | Description |
|---|---|---|
| `/catalog` | `CatalogHome.jsx` | Dashboard: asset count, quality summary, recent governance events, quick links |
| `/catalog/schemas` | `SchemaCatalogPage.jsx` | Card/grid browse of all DataTables with AssetProfile metadata, domain/quality/owner filters |
| `/catalog/schemas/:tableId` | `SchemaDetailPage.jsx` | Full detail: fields list, AssetProfile editor, DQ status, relations map, governance history |
| `/catalog/schema-manager` | `SchemaManagerPage.jsx` | Admin CRUD for DataTables + fields — replaces/supersedes `TableManagerPage` |
| `/catalog/schema-manager/:tableId` | `SchemaEditorPage.jsx` | Edit a single schema: fields, field types, order, validation, relations |
| `/catalog/domains` | `DomainsPage.jsx` | CRUD for DataDomains (tree view, parent/child) |
| `/catalog/glossary` | `GlossaryPage.jsx` | CRUD for GlossaryTerms with domain filter and status badges |
| `/catalog/tags` | `TagsPage.jsx` | CRUD for Tags with color picker |
| `/catalog/reference-data` | `ReferenceDataPage.jsx` | CRUD for ReferenceSets |
| `/catalog/reference-data/:setId` | `ReferenceValuesPage.jsx` | CRUD for ReferenceValues in a set |
| `/catalog/sources` | `DataSourcesPage.jsx` | CRUD for DataSource connections with test-connection button |
| `/catalog/exports` | `ExportsPage.jsx` | CRUD for ExportProjects + run history (ExportJobs) |
| `/catalog/imports` | `ImportsPage.jsx` | Import job history + new import wizard |
| `/catalog/connections` | `ConsumingConnectionsPage.jsx` | CRUD for ConsumingConnections (API keys, webhooks) |
| `/catalog/governance` | `GovernancePage.jsx` | Read-only log of GovernanceEvents |

---

### 6.4 Page detail: `SchemaCatalogPage`

The centerpiece page. Ataccama-style browsable schema registry.

**Features:**
- Cards or data grid: table title, domain badge, owner/steward avatars, classification chip, quality status icon (green/yellow/red)
- Filter bar: domain, quality_status, classification, owner, tag
- Search bar (calls `/catalog/search/?q=`)
- Click card → `SchemaDetailPage`
- Create button (admin only) → opens `SchemaEditorPage`

---

### 6.5 Page detail: `SchemaManagerPage` + `SchemaEditorPage`

Replaces `TableManagerPage.jsx` (which is orphaned in `dataschema` studio).

**`SchemaManagerPage`:**
- Table/module selector
- DataGrid of schemas: title, field count, row count, quality status, last modified
- Actions: Edit fields, Edit catalog metadata, Delete, Archive, View data

**`SchemaEditorPage` (per-table):**
- Two-panel layout:
  - Left: Field list (drag to reorder, add/edit/delete/archive)
  - Right: Field detail form (type, label, required, options, validation JSON, reference_set/reference_table)
- Relations tab: add/remove `TableRelation` entries (from_field → to_table/to_field)
- Catalog metadata tab: AssetProfile editor (description, domain, owner, steward, classification, glossary_term, tags)

---

### 6.6 Page detail: `DataSourcesPage`

```
DataSource card:
  icon (by type)  |  name + slug
  status badge (active/inactive/error)
  source_type chip
  description
  [Test Connection]  [Edit]  [Delete]
```

Test Connection calls `POST /sources/{id}/test/` and shows toast with result.

---

### 6.7 Page detail: `ExportsPage`

- List of ExportProjects (name, table, format, schedule, last run status)
- Create/edit project form (drawer)
- "Run Now" button → triggers ExportJob → polls status → "Download" button when ready
- Job history tab per project

---

### 6.8 Page detail: `ConsumingConnectionsPage`

- List of ConsumingConnections (name, system_type, scopes, is_active, last_used)
- Create: generates API key shown **once only** in a modal
- Edit: update name, scopes, is_active
- Rotate Key: calls `/consuming/{id}/rotate-key/`, shows new key once
- Delete

---

## 7. App.jsx route additions

```jsx
// Catalog Studio
<Route path="/catalog" element={<CatalogHome />} />
<Route path="/catalog/schemas" element={<SchemaCatalogPage />} />
<Route path="/catalog/schemas/:tableId" element={<SchemaDetailPage />} />
<Route path="/catalog/schema-manager" element={<SchemaManagerPage />} />
<Route path="/catalog/schema-manager/:tableId" element={<SchemaEditorPage />} />
<Route path="/catalog/domains" element={<DomainsPage />} />
<Route path="/catalog/glossary" element={<GlossaryPage />} />
<Route path="/catalog/tags" element={<TagsPage />} />
<Route path="/catalog/reference-data" element={<ReferenceDataPage />} />
<Route path="/catalog/reference-data/:setId" element={<ReferenceValuesPage />} />
<Route path="/catalog/sources" element={<DataSourcesPage />} />
<Route path="/catalog/exports" element={<ExportsPage />} />
<Route path="/catalog/imports" element={<ImportsPage />} />
<Route path="/catalog/connections" element={<ConsumingConnectionsPage />} />
<Route path="/catalog/governance" element={<GovernancePage />} />
```

---

## 8. RBAC mapping

| Area | Read | Write / Admin |
|---|---|---|
| Schema Catalog (browse) | Any authenticated user | — |
| AssetProfile metadata edit | Steward of asset OR global admin | ✅ |
| Schema Manager (create/delete tables) | Global admin | ✅ |
| Domains, Glossary, Tags | Any (read) | Global admin |
| Reference Data | Any (read) | Global admin or steward |
| Data Sources | Any (read) | Global admin |
| Consuming Connections | Owner + global admin | Owner + global admin |
| Export Projects | Any (read) | Owner + global admin |
| Import Jobs | Any (read) | Owner + global admin |
| Governance Log | Any (read) | Read-only |

---

## 9. Implementation order (suggested phasing)

### Phase 1 — Backend foundations
1. Complete `mdm/` app: add `urls.py`, register `reference-sets/` + `reference-values/` + `org-units/` in config/urls.py
2. Add `TableRelation` model to `dataschema/` with migration + API endpoint
3. Create `connections/` Django app: `DataSource`, `ConsumingConnection` models, serializers, views, urls, migration
4. Create `importexport/` Django app: `ExportProject`, `ImportJob`, `ExportJob` models, serializers, views, urls, migration

### Phase 2 — Frontend API layer
5. Create `src/api/catalog.js` — all catalog + MDM + connections + importexport endpoint wrappers

### Phase 3 — Shell integration
6. Add `catalog` studio to Shell (`ActivityBar`, `ShellSidebar`, `useShellState`, `studioFromPath`, `STUDIO_PATHS`, `App.jsx` routes)

### Phase 4 — Core catalog pages
7. `CatalogHome.jsx` — dashboard/overview
8. `SchemaCatalogPage.jsx` — schema browser with filters + search
9. `SchemaDetailPage.jsx` — per-table detail (fields, AssetProfile editor, relations, DQ, history)

### Phase 5 — Schema Manager
10. `SchemaManagerPage.jsx` — replaces/supersedes `TableManagerPage`
11. `SchemaEditorPage.jsx` — full per-table editor with fields + relations + catalog metadata tabs

### Phase 6 — Data governance primitives
12. `DomainsPage.jsx`, `GlossaryPage.jsx`, `TagsPage.jsx`
13. `ReferenceDataPage.jsx`, `ReferenceValuesPage.jsx`

### Phase 7 — Sources, Exports, Connections
14. `DataSourcesPage.jsx` + test-connection flow
15. `ExportsPage.jsx` + job polling + download
16. `ImportsPage.jsx` + upload wizard
17. `ConsumingConnectionsPage.jsx` + API key one-time reveal + rotate

### Phase 8 — Governance audit
18. `GovernancePage.jsx` — read-only event log with filters

---

## 10. Key decisions

| Decision | Choice | Rationale |
|---|---|---|
| Relations model | Add explicit `TableRelation` to `dataschema/` | `DataField.reference_table` is implicit; explicit model enables lineage UI and is needed for schema editor |
| Import/Export | New `importexport/` app (as already designed in docs) | Separation of concerns; `dataschema/` is schema-only |
| Connections | New `connections/` app | Separate from catalog metadata; different lifecycle and sensitivity |
| API key storage | Hash stored; plain shown once on create/rotate | Security best practice |
| Async jobs | Sync first (management command pattern), async-ready (Celery later) | Consistent with existing DQ pattern |
| TableManagerPage | Keep as-is temporarily; new `SchemaManagerPage` is the replacement in `catalog` studio | Strangler pattern; deprecate old page after new one ships |
| MDM Tier B (golden records) | Not in this plan | Already deferred in architecture docs to a later phase |

---

## 11. Files to create (summary)

### Backend
```
backend/connections/__init__.py
backend/connections/apps.py
backend/connections/models.py
backend/connections/serializers.py
backend/connections/views.py
backend/connections/urls.py
backend/connections/admin.py
backend/connections/migrations/0001_initial.py

backend/importexport/__init__.py
backend/importexport/apps.py
backend/importexport/models.py
backend/importexport/serializers.py
backend/importexport/views.py
backend/importexport/urls.py
backend/importexport/admin.py
backend/importexport/migrations/0001_initial.py

# Additions to existing:
backend/mdm/urls.py                         (new)
backend/dataschema/migrations/0003_tablerelation.py  (new)
```

### Frontend
```
carbon-frontend/src/api/catalog.js          (new)
carbon-frontend/src/pages/catalog/
  CatalogHome.jsx
  SchemaCatalogPage.jsx
  SchemaDetailPage.jsx
  SchemaManagerPage.jsx
  SchemaEditorPage.jsx
  DomainsPage.jsx
  GlossaryPage.jsx
  TagsPage.jsx
  ReferenceDataPage.jsx
  ReferenceValuesPage.jsx
  DataSourcesPage.jsx
  ExportsPage.jsx
  ImportsPage.jsx
  ConsumingConnectionsPage.jsx
  GovernancePage.jsx

# Modifications to existing:
carbon-frontend/src/shell/Shell.jsx         (add catalog studio)
carbon-frontend/src/shell/ShellSidebar.jsx  (add catalog sidebar items)
carbon-frontend/src/shell/useShellState.js  (add catalog studio definition)
carbon-frontend/src/App.jsx                 (add all /catalog/* routes)
backend/config/urls.py                      (register connections + importexport + mdm)
```
