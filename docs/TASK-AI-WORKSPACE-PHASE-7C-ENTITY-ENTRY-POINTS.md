# TASK — AI Workspace Phase 7C: Entity-Scoped Entry Points

**Date:** 2026-08-16
**Spec owner:** Master Architect
**Status:** SPEC — ready for worker
**Depends on:** Phase 7A (manifest wiring, done) + Phase 7B fix (auto-registration + manifest-driven conversation types, done)
**Design source:** `docs/DESIGN_AI_WORKSPACE_V4.md §19` (manifest contract) + `§18` C5 (context-aware entry points)

---

## 1. Goal

The manifest already declares **entry points** (per-entity action buttons) and **entity-scoped starter prompts** (`table`/`module`), but nothing renders them on the actual entity pages. Today the only AI affordance on a table is a hardcoded `Ask AI` button (in `SchemaDetailPage`) that always transfers a `chat` task; the module detail page has no AI affordance at all.

This phase:

1. Renders the manifest `entry_points` on **table** and **module** detail pages, scoped to the actual entity (`table_id` / `module_id` carried in `task_payload`).
2. Replaces the hardcoded `Ask AI` button with the manifest-driven one (the manifest already declares `{"label": "Ask about this", "task_type": "chat", "on_entity": "*"}`).
3. Closes the **deferred 7A bug**: the `emissions` manifest `starter_prompts.default` contained a `dq_validate` chip, which opens an empty conversation with no `table_id` (validation fails at send time).

---

## 2. The two gaps being closed (why this phase exists)

### Gap A — entity-requiring tasks surfaced in a context-free empty state
`emissions.py` `starter_prompts.default` currently includes:

```python
{"label": "Run a data quality check", "prompt": "", "task_type": "dq_validate"},
```

`AIEmptyState` renders this chip; `handleStartStarter` creates a `dq_validate` conversation with **no `task_payload`** and no seeded prompt. `EmissionsDomainAI.validate_task_payload("dq_validate", {})` → `(False, "'dq_validate' requires 'table_id'…")`, so the conversation is unusable.

**Fix:** remove entity-requiring tasks from `default`. They belong on entity pages via `entry_points`. `default` keeps only context-free `chat` chips.

### Gap B — entry points never rendered on entity pages
`entry_points` is served by `GET /ai/pulse/apps/` but no page consumes it for rendering buttons. The only AI button is the hardcoded `Ask AI` in `SchemaDetailPage.jsx:185`.

**Fix:** a reusable `AIDomainEntryPoints` component that filters `entry_points` by `on_entity`, renders them in the detail header, and dispatches via the existing `useAITaskTransfer.transferTask`.

### Gap C — `app_identifier` not inferable from catalog pages (latent bug)
`normalizeAppIdentifier()` (`src/shell/aiTaskTransferUtils.js`) only resolves `"emissions"` when:
- `metadata.app_identifier` or `payload.app_identifier` is in `VALID_DOMAIN_APP_IDS`, **or**
- `source_page` starts with `/emissions` or `emissions`.

Catalog detail pages (`catalog-schema-detail`, `catalog-data-product-detail`) match **none** of these → `app_identifier` resolves to `null`. Since every entry point originates from a specific manifest, the component must pass `app_identifier: manifest.app_identifier` explicitly in `metadata`.

---

## 3. Contract

### 3.1 Entry-point rendering
For an entity page with `entityType` ∈ {`table`, `module`}, render every manifest `entry_point` where `on_entity === entityType || on_entity === "*"`, in manifest order, as compact outlined buttons (icon + label) in the `DetailHeader` `actions` slot.

### 3.2 Dispatch payload (table)
For `entityType === "table"`:

```js
transferTask(entryPoint.task_type, {
  table_id: entityId,
  table_name: entity.name,
  row_count: entity.row_count ?? null,
  module_id: entity.module_id ?? context.module_id ?? null,
  module_name: context.module_name ?? null,
}, {
  app_identifier: manifest.app_identifier,   // REQUIRED (Gap C)
  title: `${entryPoint.label}: ${entity.name}`,
  source_page: 'catalog-schema-detail',
  workspaceContext: { ... },                 // §3.4
});
```

### 3.3 Dispatch payload (module)
For `entityType === "module"`:

```js
transferTask(entryPoint.task_type, {
  module_id: entityId,
  module_name: entity.name,
}, {
  app_identifier: manifest.app_identifier,
  title: `${entryPoint.label}: ${entity.name}`,
  source_page: 'catalog-data-product-detail',
  workspaceContext: { ... },
});
```

### 3.4 `workspaceContext` (WorkspaceContext v2 seed)
```js
{
  workspace: 'catalog',
  current_view: entityType === 'table' ? 'table_detail' : 'module_detail',
  entity_type: entityType,
  entity_id: entityId,
  entity_name: entity.name,
  intent_signal: entryPoint.task_type,
  recent_actions: [],
}
```

### 3.5 Backend validation is the source of truth
`transferTask` still wraps `task_payload: { type, ...normalizedPayload }`. The backend `validate_task_payload` (`needs_table` / `needs_module`) is what fails fast if the entity context is missing. The frontend must simply ensure `table_id`/`module_id` are populated when the entry point requires them — the payload builder in §3.2/§3.3 does this.

---

## 4. File-by-file changes

### Backend (1 file)

#### 4.1 `backend/ai/domain/emissions.py`
Remove the `dq_validate` item from `starter_prompts.default`. Keep `table` / `module` sections unchanged (they are the entity-scoped starters that Phase 7 full Smart Context will surface later).

Before (lines ~100–107 in `starter_prompts`):
```python
        "default": [
            {
                "label": "What can I ask here?",
                "prompt": "What questions can you answer about the Carbon emissions data for AASTMT?",
                "task_type": "chat",
            },
            {
                "label": "Run a data quality check",
                "prompt": "",
                "task_type": "dq_validate",
            },
        ],
```

After:
```python
        "default": [
            {
                "label": "What can I ask here?",
                "prompt": "What questions can you answer about the Carbon emissions data for AASTMT?",
                "task_type": "chat",
            },
        ],
```

`dq_validate` remains reachable via `entry_points` ("Validate DQ", `on_entity: "table"`) and `starter_prompts.table`. No backend test asserts `default` contains `dq_validate` (verified `test_manifest_starter_prompts_have_required_fields` only checks keys/label/task_type exist), so this is test-neutral.

### Frontend (6 files: 2 new, 4 edited)

#### 4.2 `carbon-frontend/src/hooks/useDomainManifests.js` (NEW)
Shared manifest fetch with module-level cache, so `AIWorkspace` and the entry-point components don't each refetch.

```js
// useDomainManifests — fetch + cache all domain-app manifests.
// Silent failure: returns [] (UI degrades to no entry points).
import { useEffect, useState } from 'react';
import { listDomainManifests } from '../api/aiPulse';

let cache = null;

export function useDomainManifests(token) {
  const [manifests, setManifests] = useState(cache || []);

  useEffect(() => {
    let active = true;
    if (cache) {
      setManifests(cache);
      return;
    }
    listDomainManifests(token)
      .then((data) => {
        cache = data?.apps || [];
        if (active) setManifests(cache);
      })
      .catch(() => {
        if (active) setManifests([]);
      });
    return () => { active = false; };
  }, [token]);

  return { manifests };
}
```

> Note: module-level cache means manifests are fetched once per SPA session. Acceptable — manifest registration is static within a running backend. If a worker later adds runtime manifest reload, switch to a context provider.

#### 4.3 `carbon-frontend/src/shell/AIDomainEntryPoints.jsx` (NEW)
Reusable entry-point button cluster.

Props:
- `entityType` (`'table' | 'module'`)
- `entityId` (string|number)
- `entity` (`{ id, name, row_count?, module_id? }`) — the already-loaded entity object
- `context` (optional `{ module_id?, module_name? }`) — extra parent info

Behavior:
1. `useDomainManifests(token)` → filter `manifests` for entry points where `on_entity === entityType || on_entity === '*'`.
2. Render compact `Button` (size="small", variant="outlined", `startIcon`) per entry point. Resolve `icon` name → MUI icon via a small lookup map (`FactCheck`, `AutoFixHigh`, `ManageSearch`, `Description`, `Chat`; fallback `AutoAwesome`). Reuse the icon-name convention from `PlatformHome.jsx:28` and `useShellState.js:34`.
3. On click, call `transferTask(entryPoint.task_type, payload, metadata)` per §3.2/§3.3/§3.4, with `app_identifier: manifest.app_identifier` **always set** (§2 Gap C).
4. Render `null` when there are no matching entry points.

```jsx
import React from 'react';
import { Box, Button } from '@mui/material';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import ManageSearchIcon from '@mui/icons-material/ManageSearch';
import DescriptionIcon from '@mui/icons-material/Description';
import ChatIcon from '@mui/icons-material/Chat';
import { useAuth } from '../auth/AuthContext';
import { useDomainManifests } from '../hooks/useDomainManifests';
import { useAITaskTransfer } from './useAITaskTransfer';

const ICON_MAP = {
  FactCheck: FactCheckIcon,
  AutoFixHigh: AutoFixHighIcon,
  ManageSearch: ManageSearchIcon,
  Description: DescriptionIcon,
  Chat: ChatIcon,
};

function buildPayload(entityType, entityId, entity, context) {
  if (entityType === 'table') {
    return {
      table_id: entityId,
      table_name: entity?.name ?? null,
      row_count: entity?.row_count ?? null,
      module_id: entity?.module_id ?? context?.module_id ?? null,
      module_name: context?.module_name ?? null,
    };
  }
  return {
    module_id: entityId,
    module_name: entity?.name ?? null,
  };
}

export default function AIDomainEntryPoints({ entityType, entityId, entity, context }) {
  const { token } = useAuth();
  const { manifests } = useDomainManifests(token);
  const { transferTask } = useAITaskTransfer();

  const points = [];
  for (const manifest of manifests) {
    for (const ep of manifest?.entry_points || []) {
      if (ep?.on_entity === entityType || ep?.on_entity === '*') {
        points.push({ ...ep, app_identifier: manifest.app_identifier });
      }
    }
  }
  if (points.length === 0) return null;

  const handle = async (point) => {
    await transferTask(
      point.task_type,
      buildPayload(entityType, entityId, entity, context),
      {
        app_identifier: point.app_identifier,
        title: `${point.label}: ${entity?.name ?? entityId}`,
        source_page: entityType === 'table' ? 'catalog-schema-detail' : 'catalog-data-product-detail',
        workspaceContext: {
          workspace: 'catalog',
          current_view: entityType === 'table' ? 'table_detail' : 'module_detail',
          entity_type: entityType,
          entity_id: entityId,
          entity_name: entity?.name ?? null,
          intent_signal: point.task_type,
          recent_actions: [],
        },
      },
    );
  };

  return (
    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
      {points.map((point) => {
        const Icon = ICON_MAP[point.icon] || AutoAwesomeIcon;
        return (
          <Button
            key={`${point.app_identifier}:${point.task_type}:${point.label}`}
            size="small"
            variant="outlined"
            startIcon={<Icon />}
            onClick={() => handle(point)}
          >
            {point.label}
          </Button>
        );
      })}
    </Box>
  );
}
```

#### 4.4 `carbon-frontend/src/pages/catalog/SchemaDetailPage.jsx` (edit)
Replace the hardcoded `Ask AI` button + `handleAskAI` with the manifest-driven component.

1. Remove the `AutoAwesomeIcon` import and the `handleAskAI` callback (lines ~105–129), and the inline `Ask AI` `<Button>` (lines ~185–194).
2. Add import: `import AIDomainEntryPoints from '../../shell/AIDomainEntryPoints';`
3. In `headerComponent` `actions`, render:
   ```jsx
   <AIDomainEntryPoints
     entityType="table"
     entityId={table?.id ?? tableId}
     entity={table}
   />
   ```
   > `table` is the `fetchDataSchemaTable` result. Confirm it carries `id` and `name`; if `row_count`/`module_id` are not on the table object, leave them null — the payload builder already guards with `?? null` and `validate_task_payload` only hard-requires `table_id`.

Keep `useAITaskTransfer` import removed if no longer used directly (the component now owns the transfer). Verify no other caller of `transferTask` in this file remains before removing.

#### 4.5 `carbon-frontend/src/pages/catalog/DataProductDetailPage.jsx` (edit)
Add entry points to the module detail header.

1. Add import: `import AIDomainEntryPoints from '../../shell/AIDomainEntryPoints';`
2. In the `headerComponent` `DetailHeader`, add an `actions` slot:
   ```jsx
   actions={
     <AIDomainEntryPoints
       entityType="module"
       entityId={product?.id ?? moduleId}
       entity={product}
     />
   }
   ```
   > The `product` object is the `fetchModule` result (has `id`, `name`, `org_unit_name`). `report_draft`'s `validate_task_payload` accepts `module_id` (satisfied). `period_id` remains optional.

#### 4.6 `carbon-frontend/src/shell/AITaskTransferContext.jsx` (edit, defensive)
Extend `enrichPayload` to normalize entity fields for the new entry-point task types so `task_payload` is consistent regardless of which page dispatched it. This is defensive — the `AIDomainEntryPoints` builder already provides `table_id`/`module_id` — but it makes the transfer contract explicit and testable.

Add before the final `return base;`:

```js
if (type === 'dq_validate' || type === 'investigate') {
  return {
    ...base,
    table_id: payload.table_id ?? null,
    table_name: payload.table_name ?? payload.table ?? null,
    row_count: payload.row_count ?? null,
    module_id: payload.module_id ?? null,
    module_name: payload.module_name ?? null,
  };
}

if (type === 'report_draft') {
  return {
    ...base,
    module_id: payload.module_id ?? null,
    module_name: payload.module_name ?? null,
    period_id: payload.period_id ?? null,
  };
}

if (type === 'chat') {
  return {
    ...base,
    table_id: payload.table_id ?? null,
    table_name: payload.table_name ?? payload.table ?? null,
    module_id: payload.module_id ?? null,
    module_name: payload.module_name ?? null,
  };
}
```

### Tests (2 files: 1 new, 1 edit)

#### 4.7 `carbon-frontend/src/__tests__/AIDomainEntryPoints.test.jsx` (NEW)
Mock `useAuth`, `useAITaskTransfer`, and `useDomainManifests` (via `vi.mock`). Cases:

1. **Filters by entity type** — manifests with `on_entity: 'table'` + `'*'` render on a table page; `on_entity: 'module'` does not.
2. **Renders null when no matching entry points.**
3. **Click dispatches with entity payload + explicit app_identifier** — assert `transferTask` called with `('dq_validate', { table_id, table_name, ... }, { app_identifier: 'emissions', ... })`.
4. **Module entry point** dispatches `('report_draft', { module_id, module_name }, …)`.
5. **`chat` entry point with `on_entity: '*'` renders and dispatches `('chat', …, { app_identifier: 'emissions', … })`.**

#### 4.8 `carbon-frontend/src/__tests__/AITaskTransferContext.test.jsx` (edit) or add cases to existing
Add `enrichPayload` assertions for `dq_validate`/`investigate`/`report_draft`/`chat` normalization (preserve `table_id`/`module_id`, default `null` when absent).

> The existing `AIDomainManifest.test.jsx` uses a self-contained fixture with `default: [chat, dq_validate]` and is unaffected by the backend manifest edit. Leave it as-is (it tests `AIEmptyState` rendering behavior, not the live manifest data).

---

## 5. Gates

Backend:
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q            # still 348 passed (no logic change)
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run   # "No changes"
```

Frontend:
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm test -- --run          # includes AIDomainEntryPoints + transfer-context tests
npm run lint               # 0 new errors (baseline 6 err / ~62 warn is pre-existing)
npm run build              # clean
```

## 6. Browser checklist

1. Log in as `ahmed` / superuser; open a Carbon table detail (`/catalog/tables/:id` with a real table). Expect **Validate DQ**, **Suggest Rules**, **Investigate**, and **Ask about this** buttons in the header (the old hardcoded single `Ask AI` is gone).
2. Click **Validate DQ** → AI pane opens a `dq_validate` conversation titled `Validate DQ: <table>`. Open the backend/context: the conversation's `task_payload` carries `table_id`; typing a message does **not** return a `validate_task_payload` error.
3. Click **Ask about this** → opens a `chat` conversation scoped to the table.
4. Open a data product detail (`/catalog/products/:id`) → expect **Draft Report** + **Ask about this** buttons.
5. Open the AI workspace empty state (delete/archive all conversations) → the `Run a data quality check` chip is **gone**; only `What can I ask here?` + `Start a Chat` remain.
6. A user with no domain apps / manifests still sees the plain empty-state fallback (no entry points on entity pages).

## 7. Out of scope / follow-ups

- **`normalizeAppIdentifier` hardcoded `VALID_DOMAIN_APP_IDS = new Set(['emissions'])`** — future domain apps (water) won't resolve unless added here or the set is derived from manifests. Not this phase; flag for the multi-domain phase.
- **Entity-scoped starter chips** (`starter_prompts.table`/`module`) inside the AI workspace empty state are **not** wired here — those depend on Smart Context (WorkspaceContext v2 `current_view`/`entity`) and land in the full **Phase 7** work, not 7C.
- **`period_id` for `report_draft`** is optional and not sourced from the module page (no reporting-period picker). Follow-up in Phase 8 (Execute Mode) if report drafting needs a specific period.
- **Icon map duplication** — `ICON_MAP` here vs `PlatformHome.jsx`/`useShellState.js` icon lookups could be unified later; not required now.
