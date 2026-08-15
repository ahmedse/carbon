# TASKS.md — Pulse Frontend Phase B (wire the gated console panels)

**Status:** FINAL
**Role:** Backend + Frontend Worker
**Model:** DeepSeek V4 Flash (customendpoint)
**Prerequisite:** Phase 2c committed (`745a3cb`) — read-only ops API `/carbon-api/ai/pulse/` (`health/`, `modules/`, `tasks/<id>/`) + all 10 task types wired (2b-3b) + 49 ai models in `backend/ai/models/`.
**Primary context:** `backend/ai/ops_api.py` + `ops_urls.py` (existing pulse surface), `backend/ai/models/core.py` + `knowledge_graph.py` (49 models), `carbon-frontend/src/pages/admin/ai/*` (3 live panels + 14 placeholders), `carbon-frontend/src/api/aiWorkspace.js` (api client pattern), `carbon-frontend/src/components/DataGrid/CarbonDataGrid.jsx`.

## Objective

Replace the 14 `PulseModulePlaceholder` panels in the ai-admin studio with **real,
read-only, grounded panels** that show the durable AI state the engine actually
writes — never fabricated data. Each panel lists rows from its backing ai models;
panels whose tables are empty show a grounded empty state (not a hardcoded "coming
soon"). This is admin **observability**, not mutation.

This phase is full-stack despite the name: a small read-only backend read layer is
required (Phase 2c explicitly deferred "model-backed read viewsets until the console
panels need them" — this is that moment), plus the frontend panels.

## Scope boundary (GROUNDED — do NOT over-build)

- Wire **all 14** placeholder routes. 12 are model-backed data panels, 1 (MCP) reads
  the `Instance` config, 1 (Archetypes) lists the vendored engine's declarative bundles.
- Read-only. No create/update/delete endpoints. No mutation actions.
- **NOT in scope** (defer): CBAC capability gating on the new endpoints (the studio is
  already `isGlobalAdmin`-gated on the frontend; the backend uses `IsAuthenticated` to
  match `ops_api.py`/`workspace_api.py`); per-row detail pages; write flows; pgvector.

---

## PART 1 — Backend read layer (`/carbon-api/ai/pulse/`)

### 1.1 CREATE `backend/ai/observability_api.py`

**Model registry** — a single curated `dict[str, list[type[Model]]]` mapping panel keys
to backing ai models. Import models from `ai.models.core` and `ai.models.knowledge_graph`.
Exact mapping (use these model class names):

| Panel key | Backing models |
|---|---|
| `knowledge` | `KnowledgeEntity`, `KnowledgeNode`, `KnowledgeEdge`, `Insight` |
| `memory` | `MemoryLongTerm`, `MemoryEpisodic` |
| `graph` | `KnowledgeNode`, `KnowledgeEdge`, `KgNode`, `KgEdge`, `KgProvenance`, `KgQueryPlan`, `KgPlanStep`, `KgBootstrapRun` |
| `agents` | `Agent`, `AgentHandoff` |
| `mcp` | `Instance` |
| `tools` | `ToolExecution`, `TaskExecution` |
| `skills` | `Skill`, `SkillAdmissionLog` |
| `prompts` | `PromptVersion`, `PromptEval`, `PlaybookBlock` |
| `feedback` | `Feedback`, `KgFeedbackRecord`, `KgQueryFeedback`, `KgReviewItem`, `KgGoldenPair` |
| `learning` | `OpsRun`, `Run`, `RunStep`, `Trajectory`, `KgQualityScore`, `KgRecoveryLog` |
| `monitoring` | `SystemSnapshot`, `Notification`, `Insight`, `KgProactiveTrigger`, `KgProactiveInsight` |
| `audit` | `AuditLog` |
| `logs` | `LLMCallLog`, `ToolExecution`, `TaskExecution`, `TurnLedgerRow`, `ConversationContextRecord` |

Panel labels (for the inventory): `knowledge=Knowledge Base`, `memory=Memory`,
`graph=Knowledge Graph`, `agents=Agents`, `mcp=MCP Servers`, `tools=Tools`,
`skills=Skills Catalog`, `prompts=Prompts & Playbook`, `feedback=Feedback Review`,
`learning=Learning Jobs`, `monitoring=Monitoring`, `audit=AI Audit Trail`, `logs=AI Logs`.
(`archetypes` is NOT in the model registry — it is a filesystem surface, see 1.2.)

**Generic serializer factory** (DRY — no 49 bespoke serializers):
```python
def _make_serializer(model):
    # exclude any field whose name hints at a secret
    excluded = {f.name for f in model._meta.get_fields()
                if re.search(r"token|secret|password|api_key", f.name, re.I)}
    attrs = {"Meta": type("Meta", (), {"model": model, "fields": "__all__",
                                       "exclude": tuple(excluded)})}
    return type(f"{model.__name__}Serializer", (serializers.ModelSerializer,), attrs)
```
- **HARD RULE (security)**: `Instance.host_api_token` MUST be excluded (it matches
  `token`). Additionally, in `PulseDataView`'s serializer context, recursively redact any
  JSON-field values under keys matching `token|secret|password|api_key` (case-insensitive)
  before returning (applies to `Instance.config` and any `*_json` fields). This is the
  same spirit as the E1 masked-config lesson — never leak a host token.

**Views** (all `APIView`, `permission_classes = [IsAuthenticated]` — match `ops_api.py`):

1. `PulseInventoryView` — `GET inventory/`
   → `{"panels": [{"key": k, "label": LABELS[k], "count": total_rows, "models": [m.__name__ ...]}, ...]}`,
   sorted by label, where `total_rows = sum(Model.objects.count() for Model in registry[k])`.
   Always 200, even when every count is 0.

2. `PulseDataView` — `GET data/<str:key>/`
   → 404 `{"error": "unknown_panel"}` if `key` not in registry.
   Otherwise merge rows across the panel's models: serialize each row with the model's
   factory serializer, tag every row with `"_type": Model.__name__`, flatten into one
   list ordered by each model's most-recent timestamp field when present (else natural
   order), cap at `?limit` (default 50, max 200). Return:
   `{"key", "label", "count": total, "models": [...], "results": [{...tagged rows}]}`.
   Do NOT raise on empty tables — return `count: 0, results: []`.

3. `PulseArchetypesView` — `GET archetypes/`
   → walk `backend/ai/engine/archetypes/` top-level subdirectories (skip `__init__.py`,
   `README.md`, `__pycache__`). Return `{"bundles": [{"name": dirname, "kind": "bundle"}]}`.
   No filesystem secrets; read-only directory listing only. Wrap in try/except → on error
   return `{"bundles": [], "error": str(exc)}` (never 500).

Import style: `from ai.models.core import ...`, `from ai.models.knowledge_graph import ...`,
`from rest_framework.views import APIView`, `from rest_framework.permissions import IsAuthenticated`,
`from rest_framework.response import Response`. No Carbon domain imports.

### 1.2 MODIFY `backend/ai/ops_urls.py`

Add imports + 3 paths (keep the existing 3 `health/modules/tasks` paths untouched):
```python
from ai.observability_api import PulseInventoryView, PulseDataView, PulseArchetypesView
# ...
    path("inventory/", PulseInventoryView.as_view(), name="ai-pulse-inventory"),
    path("data/<str:key>/", PulseDataView.as_view(), name="ai-pulse-data"),
    path("archetypes/", PulseArchetypesView.as_view(), name="ai-pulse-archetypes"),
```
No change to `config/urls.py` (the `ai/pulse/` mount already exists).

### 1.3 CREATE `backend/ai/tests/test_observability_api.py` (pytest-django, `@pytest.mark.django_db`)

Mirror the auth pattern from `test_ops_api.py` (conftest `api_client` + `get_token_for_user`):
- `test_inventory_requires_auth` — anonymous GET → 401.
- `test_inventory_returns_all_panels` — authed GET → 200, `len(panels) == 13`, every panel
  has `key`/`label`/`count`/`models`, and keys == the 13 registry keys.
- `test_data_unknown_panel_404` — `GET data/nope/` → 404.
- `test_data_logs_merges_and_tags` — seed one `LLMCallLog` row, GET `data/logs/` → 200,
  `count >= 1`, every result has a `_type` field, and the seeded row is present.
- `test_instance_token_redacted` — seed an `Instance` with `host_api_token="sekrit"`, GET
  `data/mcp/` → the serialized row has NO `host_api_token` key (and no value `"sekrit"`).
- `test_archetypes_lists_bundles` — GET `archetypes/` → 200, `bundles` contains
  `devops-workspace`, `test-lab`, `twin-mind`.
- `test_read_only_no_write_methods` — POST/PUT/DELETE on `inventory/` → 405.

---

## PART 2 — Frontend panels

### 2.1 CREATE `carbon-frontend/src/api/aiPulse.js`

Mirror `aiWorkspace.js` (uses `apiFetch` from `./api`). `const BASE = 'ai/pulse/'`.
Exports:
- `getPulseInventory(token)` → `apiFetch(\`${BASE}inventory/\`, { token })`
- `getPulseData(token, key)` → `apiFetch(\`${BASE}data/${encodeURIComponent(key)}/\`, { token })`
- `getPulseArchetypes(token)` → `apiFetch(\`${BASE}archetypes/\`, { token })`

### 2.2 CREATE `carbon-frontend/src/pages/admin/ai/PulseDataPanel.jsx`

Generic read-only panel component. Props: `{ title, description, dataKey, emptyHint }`.
- `useDocumentTitle(title)`; wrap in `PageContainer`.
- Fetch `getPulseData(token, dataKey)` on mount + when `token`/`dataKey` change
  (mirror `PulseOverviewPage`'s cancelled-fetch pattern).
- States: loading (`CircularProgress`), error/offline (Paper + `CloudOffIcon` +
  "Data unavailable — the Pulse read API is offline"), empty (`count === 0` →
  Paper + `emptyHint` copy), loaded (render rows).
- Loaded: header `Typography` + a `Chip` showing `count`. Render a `CarbonDataGrid`
  with a **type** column (`_type`, first column, 140px) + dynamic columns derived from
  the union of keys in `results[0]` (exclude `_type` and the `AppScopeMixin` columns
  `app_identifier`/`org_unit_id`/`host_user_id`/`visibility` — show those 4 in a compact
  secondary line or a single "scope" column instead of 4 wide columns). For nested
  object/array cell values, JSON-stringify. RULE_8 tokens only (no raw hex).
- Column rendering must be defensive: `value === null/undefined → '—'`; arrays/objects
  → `JSON.stringify(v)` truncated to ~80 chars.

### 2.3 CREATE `carbon-frontend/src/pages/admin/ai/PulseArchetypesPanel.jsx`

Same structure; fetch `getPulseArchetypes(token)`; render the bundle names as a simple
list/table (name + `kind`). Empty/error degrade like `PulseDataPanel`.

### 2.4 CREATE 13 thin page wrappers (one per model-backed route) under `pages/admin/ai/`

Each is ~6 lines: a default-export component that renders
`<PulseDataPanel title dataKey emptyHint />`. Use these exact `dataKey`s and titles:

| Route | Component file | title | dataKey | emptyHint |
|---|---|---|---|---|
| `/admin/ai/knowledge` | `KnowledgeBasePanel.jsx` | Knowledge Base | `knowledge` | "No knowledge entities recorded yet." |
| `/admin/ai/memory` | `MemoryPanel.jsx` | Memory | `memory` | "No memory rows recorded yet." |
| `/admin/ai/graph` | `KnowledgeGraphPanel.jsx` | Knowledge Graph | `graph` | "No graph nodes or edges yet. Run schema analysis to bootstrap the graph." |
| `/admin/ai/agents` | `AgentsPanel.jsx` | Agents | `agents` | "No agents registered yet." |
| `/admin/ai/mcp` | `McpServersPanel.jsx` | MCP Servers | `mcp` | "No Pulse instances configured." |
| `/admin/ai/tools` | `ToolsPanel.jsx` | Tools | `tools` | "No tool executions recorded yet." |
| `/admin/ai/skills` | `SkillsPanel.jsx` | Skills Catalog | `skills` | "No skills admitted yet." |
| `/admin/ai/prompts` | `PromptsPanel.jsx` | Prompts & Playbook | `prompts` | "No prompt versions or playbook blocks yet." |
| `/admin/ai/feedback` | `FeedbackPanel.jsx` | Feedback Review | `feedback` | "No feedback records yet." |
| `/admin/ai/learning` | `LearningJobsPanel.jsx` | Learning Jobs | `learning` | "No learning jobs or runs yet." |
| `/admin/ai/monitoring` | `MonitoringPanel.jsx` | Monitoring | `monitoring` | "No system snapshots or proactive insights yet." |
| `/admin/ai/audit` | `AuditPanel.jsx` | AI Audit Trail | `audit` | "No AI audit entries yet." |
| `/admin/ai/logs` | `AILogsPanel.jsx` | AI Logs | `logs` | "No LLM call logs yet. Run a chat or task to populate." |

### 2.5 MODIFY `carbon-frontend/src/App.jsx`

Replace the 14 `PulseModulePlaceholder` lazy routes (currently lines ~300–313) with
`React.lazy` imports + `<AdminRoute>` routes for: the 13 `*Panel` components above, plus
`PulseArchetypesPanel` for `/admin/ai/archetypes` (title "Archetypes"). Keep the
`PulseModulePlaceholder` import **only if still referenced**; if it becomes unused, remove
the import + the `PulseModulePlaceholder.jsx` file is safe to leave in place (or delete —
worker's choice, must not break build).

---

## DO NOT TOUCH
- `backend/ai/engine_runtime.py`, `intelligence.py`, `providers/pulse.py`, `store.py`, `engine/**`, `models/**` (reuse, do NOT modify).
- `backend/ai/ops_api.py` (reuse `PulseHealthView`/`PulseModulesView`/`PulseTaskStatusView` — do NOT change).
- `backend/config/urls.py` (mount already exists).
- `carbon-frontend/src/shell/**`, `api/api.js`, `theme/**`, `config.js`.

## HARD RULES
- Read-only. No write endpoints, no `ModelViewSet` mutation actions.
- No new Django models/migrations (`makemigrations --check` must report "No changes detected").
- No raw SQLAlchemy, no hardcoded secrets, no naive datetimes, no `print()`.
- RULE_8 (theme tokens, no raw hex), RULE_10 (apiFetch only, no raw fetch), RULE_16 (PageContainer).
- **Never leak `Instance.host_api_token` or any JSON value under a `token|secret|password|api_key` key.**

## GATES (worker must run; Master will independently re-run ALL)
```
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests -q
cd /home/ahmed/aast/carbon && bash ./.ai-toolkit/scripts/verify.sh backend
cd /home/ahmed/aast/carbon/carbon-frontend && npm run build
cd /home/ahmed/aast/carbon && bash ./.ai-toolkit/scripts/verify.sh frontend
```

## Report
Write deviations + test/build summary to `plans/TASK-RESULTS-PULSE-VENDOR-FRONTEND-PHASE-B.md`.
