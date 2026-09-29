# Screen Spec — Data Migration Studio

**ADR-0060 · frontend-ready 9 artifacts · attach to DMS-4 / DMS-7**  
**IA correction:** not a new Activity Bar studio. Not `/migrate`.  
**Primitives only:** `PageContainer`, `PageHeader`, `FilteredDataGrid`, `Wizard`,
`SearchSelect`, `FormField`, `SystemDialog` / `ConfirmDialog`,
`NotificationProvider`. No papaparse. No raw `<Select>`. No raw MUI Table as
the record list. No hand-rolled Stepper.

---

## Menus (where the user clicks)

Activity Bar is unchanged (`PLATFORM_STUDIOS` + app manifests). Two doors:

```
Activity Bar                    Sidebar (that studio)              Route
─────────────                   ─────────────────────              ─────
People                          Configuration                      /people/import
  (Groups icon)                   Policies                         /people/policies
                                  App Config                       /people/config
                                  Import          ← NEW            /people/import

Catalog Studio                  Connect & move                     (already exists)
  (LibraryBooks)                  Connections                      /catalog/connections
                                  Data Sources                     /catalog/sources
                                  Imports         ← UPGRADE        /catalog/imports
                                  Exports                          /catalog/exports
```

**People manifest** — add one item under the existing `Configuration` group
(not a new group, not a top-level peer):

```js
{ label: 'Import', path: '/people/import', role: '*' }
```

Visible when `inbound:prepare` **or** `inbound:commit` (plus People app access).
Hidden on My and Team. `emp_1067` never sees it.

**Catalog** — keep the existing **Imports** label and path. The page is replaced
by the same list+Wizard chrome with `kind` locked to `data_product`. Do not add
a second "Migration" row next to Imports.

**Breadcrumbs**
- People: `People` → `Import` → `{file name}`
- Catalog: `Catalog Studio` → `Imports` → `{file name}` (extend existing `/catalog/imports`)

**Command palette:** `People · Import` → `/people/import`. Catalog Imports
command already exists / keep it on `/catalog/imports`.

**Depth:** list → batch = 2 levels. Target picker is a `SystemDialog` on the
list, not a third route.

---

## Flow (People — emp_2378 then emp_2400)

```
People (activity) → Configuration → Import
        │
        ▼
[1] LIST  /people/import
        │  PageHeader primary "New import"
        │  SystemDialog: SearchSelect target
        │    Employee snapshot | Leave opening balance | Leave history
        │
        ▼
[2] STUDIO  /people/import/:id     (shared Wizard, 4 steps)
        1 Upload     CSV + encoding SearchSelect + 20-row sample grid
        2 Map        column → declared field SearchSelect + crosswalk dialog
        3 Smoke      counts + sample + reject download   (zero live writes)
        4 Commit     preview + ConfirmDialog             (hidden without inbound:commit)
        │
        ▼
     back to LIST  status=committed · reconcile in the row / reopen read-only
```

`emp_2378` prepares. On GOFSCO both 2378 and 2400 have `inbound:commit`
(`people_lead`), so Commit is **shown** and SoD **disables** it for the
preparer (API 403). A prepare-only user would not see the step.
`emp_2400` opens the same URL, Wizard `initialStep` = Smoke or Commit.

Catalog flow is identical except the door is Catalog → Imports and the
SearchSelect targets are DataTables the user may ingest.

---

## Screen A — `/people/import`  and  `/catalog/imports`

Owner: People / Catalog   IA: as above

### Story
As a preparer, I want a list of my batches and one primary action to start
another, so I can leave a smoke test and come back.

As a committer, I want the smoked batches without a New button I cannot use.

### Acceptance
- People list shows **typed** batches only. Catalog list shows **Data Product**
  batches only. Never a mixed kind on one door.
- Prepare: empty state + primary **New import**. Commit-only: no primary;
  empty = "Nothing waiting to commit".
- Neither cap + People access: forbidden state (not an empty grid).
- No-results ≠ no-data.
- New import: `SystemDialog` + `SearchSelect` of targets for this door.
  Confirm → `POST` batch → navigate `.../import/:id` (People) or
  `.../imports/:id` (Catalog).
- Row click highlights only (compact-ui). The eye icon opens the studio.
  Status chip + label (not color alone).

### Composition
```
PageContainer
 └─ PageHeader
      title: t('people:import.title') | t('catalog:imports.title')
      primary: New import   (prepare only) — ONE button, top-right
 └─ FilteredDataGrid
      getRowId: row.id
      search + filters: status, target
      columns: status, target_label, file_name, rows, rejects, updated_at, prepared_by, actions (eye)
      states: loading | empty | no-results | error | forbidden | loaded
 └─ SystemDialog  (New import)
      FormField + SearchSelect  targets
      actions: Cancel | Create
```

### State matrix
Page: idle | loading | empty | no-results | error | forbidden | loaded | stale  
Dialog: closed | open | submitting | field-error  
Primary: default | hidden (no prepare)

### Data contract
- `GET /carbon-api/inbound/batches/?kind=typed_object|data_product`
- `GET /carbon-api/inbound/targets/?kind=`
- `POST /carbon-api/inbound/batches/` `{kind, target_key}` → 201 `{id}`
- 403 → forbidden. 400 → field errors in the dialog.

### A11y / perf / i18n
Keyboard to New import and grid. Status = chip + text. Lazy People/Catalog
chunks (existing). Paginate 25. Strings in `people` + `catalog` namespaces
(not a new `migration` ns — stay in the app that owns the door). AR catalog
required. IDs `dir="ltr"`.

---

## Screen B — `/people/import/:id`  and  `/catalog/imports/:id`

### Story
As a preparer, I upload one CSV, map it, smoke it with zero writes, and
download rejects.

As a committer, I read the smoke envelope and confirm a live write.

### Acceptance
- Server parse (encoding override via `SearchSelect`: utf-8, windows-1256,
  cp1252). Sample ≤20 rows, ≤30 cols in `FilteredDataGrid`.
- Map options = cartridge declared fields (People) or `DataField`s (Catalog).
  `SearchSelect` per row. Required unmapped → Wizard `validate` blocks Next.
- Crosswalk: `SystemDialog` + `SearchSelect` of `ReferenceValue` (People) or
  table enums (Catalog). Never a free-text code dump as the only UI.
- Smoke: insert / update / skip / reject. Zero live writes. Reject file
  download. Next to Commit blocked while smoke missing.
- Commit: hidden without `inbound:commit`. Same-user People commit → 403 SoD
  (except superuser). `ConfirmDialog` names the target and row counts.
  Default no `allow_partial`.
- Refresh keeps batch id (server is the draft). Back = list.

### Journey
Entry from list → Upload → Map → Smoke → Commit confirm → list.  
Drop-off: Map invalid (Next blocked + step Alert).  
Committer join: list → open smoked → step 3 or 4.

### Composition
```
PageContainer
 └─ PageHeader  file name + status chip; no second primary (Wizard owns actions)
 └─ Wizard
      steps:
        upload  — dropzone + FormField encoding SearchSelect
                  + FilteredDataGrid sample
        map     — FilteredDataGrid: source | SearchSelect target | required
                  row action: Crosswalk → SystemDialog
        smoke   — Stat row (insert/update/skip/reject)
                  FilteredDataGrid projected sample
                  secondary: Download rejects
        commit  — read-only summary + reconcile preview
      finishLabel: t('…commit')
      disableFinish: !inbound:commit || smoke.reject && !allow_partial
      onFinish → ConfirmDialog then POST commit
      onCancel → /people/import or /catalog/imports
```

Reuse audit: `Wizard` not a new Stepper. No `BulkImportWizard` import.
`SearchSelect` not `<Select>`. `FilteredDataGrid` not raw Table.
`ConfirmDialog` for commit. `notify` / `notifyFromError`.

### State matrix
Page: loading | error | forbidden | loaded  
Upload: empty | parsing | parse-error | sampled  
Map: incomplete | complete | template-applied  
Smoke: idle | running | smoked | smoke-error  
Commit: hidden | ready | confirming | submitting | sod-forbidden | success  

### Data contract
As previously: file POST, mapping PUT, smoke POST, rejects GET, commit POST.
Kind is not sent by the user on the People door — the batch already has it.

### A11y / perf / i18n
Stepper current step announced (MUI Stepper in `Wizard`). Confirm dialog
focus trap. Smoke >1s: spinner on Next, page stays. No papaparse on the
route. Existing app i18n files. RTL: Wizard buttons already logical in MUI.

---

## Screen C — Cartridge definitions (Platform Admin)

Not a door. Not People. Route `/admin/migration/cartridges` and `/:id`.

**List:** `PageContainer` + `PageHeader` + `FilteredDataGrid`. Row click highlights. Eye opens the declaration. Primary action is New cartridge → `SystemDialog` (`FormField` + `TextField` + `SearchSelect` for required).

**Detail:** labels via `SystemDialog`. Fields grid, eye opens the field. Add field is the section action. Disable stays on a bound cartridge. Delete uses `ConfirmDialog` and is enabled only when the row is unbound and has no batches. Batches for this key are a second grid. Eye opens the People or Catalog door when that app owns the batch. Any other app stays on a read-only dialog.

States: loading | empty | no-results | error | forbidden | loaded.

A new key is a declaration only. The door does not list it until the owning app registers smoke and commit.

## What we will not build (toolkit / UX)

| Temptation | Rule |
|------------|------|
| New Activity Bar "Migration" / `/migrate` | RULE_5 · one nav per app · no new `PLATFORM_STUDIOS` |
| Import on My or Team | NSR / ESS — load is HR admin |
| Second Catalog item "Migration" beside Imports | RULE 12 · existing Imports is the door |
| Hand-rolled Stepper / `BulkImportWizard` as the page | design-system RULE 2 · `Wizard` |
| Raw `<Select>` for target, encoding, or field map | RULE 13 `SearchSelect` |
| Raw table for batch list or sample | RULE 14 `FilteredDataGrid` |
| Browser parse as source of truth | server file POST |
| Two primaries on the list | Page anatomy: ONE primary |
| Tabs on the list for "typed vs product" | kind is locked by the door |
| Pulse Chat Confirm | ADR-0046 |
| A cartridge whose smoke/commit is typed in the browser | Handler stays in the owning app |
