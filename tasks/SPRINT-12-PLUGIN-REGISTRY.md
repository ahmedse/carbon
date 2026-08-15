# Sprint 12 — Tool/Workflow Plugin Registry (Carbon AI grows)

**Owner:** Master Architect · **Status:** Spec (implementation pending)
**Depends on:** Sprint 6–11 (AI core, workspace, domain, streaming, feedback, learning)
**Binding rules:** `ARCH_AI_EXTENSIBILITY` (`project.config.md`), `.ai-toolkit/shared/ai-contract.md`, RULE_18–RULE_21

---

## 1. Why this sprint exists (the insight)

Carbon AI's tools today are **generic API bridges**, not *processes*. `call_host_api`
is an HTTP bridge; `run_ops_workflow` is a generic ingestion workflow. There is no
first-class way to register a **well-defined, specific system process** — e.g.
"create a DQ rule" — as a named tool that the agent can reason about, confirm, and
execute.

The architecture already demands the end state (`ARCH_AI_EXTENSIBILITY`):

> New AI capability = register a tool/workflow, NOT a new app. Plugins:
> `ToolPlugin`/`WorkflowPlugin` ABC, self-register at startup.

This sprint turns that rule into code. After it lands, **growing Carbon AI is adding
a plugin — not writing a new Django app, and not editing a hardcoded list.**

The gradient we are building toward:

```
generic HTTP bridge (call_host_api)
        → specific process tool (create_dq_rule)
              → composite workflow tool (run_dq_rule_rollout)
                    → captured skill (invoke_skill: "my monthly DQ sweep")
```

Each level is more reusable and more auditable than the last.

---

## 2. Current state (verified against code — do not re-describe from memory)

| Concern | Where | Today |
|---|---|---|
| Static tools | `backend/ai/engine/agent/tools.py` | `STATIC_TOOL_DEFINITIONS` (11 OpenAI-function dicts) + `STATIC_TOOL_EXECUTORS` (dict name→async fn). Hardcoded. |
| Tool assembly | `tools.py::get_tool_definitions()` / `get_tool_executors()` | `STATIC + MCP`. Nothing else. |
| MCP tools | `mcp_client.py::MCPToolRegistry` + `tools.py::init_mcp_tools()` | Discovered **once at boot** from `settings.MCP_SERVERS` (JSON). Remote tools. |
| Host API calls | `executor.py::HostAPIExecutor` | httpx client, acts as the **authenticated user** (JWT). Mutations → `ToolExecution(status=pending_confirmation)`. |
| Specific workflows | `run_ops_workflow` → `ingestion/ops_workflow.py` | One generic declarative ingestion workflow. |
| Skills | `draft_skill` / `invoke_skill` | Per-user captured recipes; returned as data, **never auto-executed**. |
| Tool catalog read | `activation_api.py::_settings_tools()` → `tools_catalog` in `GET settings/` | `[{name, description}]` from `get_tool_definitions()` (static + MCP). Rendered by `EngineSettingsPanel` → `ToolsCatalog`. |
| Plugin ABC / self-registration | — | **Does not exist.** |
| Runtime CRUD over tools | — | **Does not exist** (growth is declarative: edit `tools.py` + redeploy). |

**Naming gotcha:** `engine/agent/registry.py` is the **AgentRegistry** (agent roles +
handoff edges), *not* a tool registry. This sprint adds a *tool/workflow* plugin
registry in a new module — it must not collide with `AgentRegistry`.

---

## 3. Design

### 3.1 `ToolPlugin` — a single, well-defined process

New module `backend/ai/engine/agent/plugins.py`:

```python
class ToolPlugin(ABC):
    """A well-defined, specific host process exposed to the agent as one tool."""

    name: str                      # "create_dq_rule"
    description: str               # what the process does + when to use it
    input_schema: dict             # JSON Schema for arguments
    requires_confirmation: bool = True   # mutations always confirm (RULE_21)
    capability: str | None = None  # e.g. "dq:manage_rules" — optional CBAC gate
    app_identifier: str | None = None    # bind to a domain app for scope (RULE_20)

    @abstractmethod
    async def execute(self, args: dict, *, ctx: ToolContext) -> dict: ...

    def to_definition(self) -> dict:
        """Serialize to the OpenAI function-call shape the agent consumes."""
```

`ToolContext` carries the injected deps a plugin may need: `db` (AsyncSession),
`host_api` (`HostAPIExecutor`, already JWT-authed), `user` identity, `instance_id`,
`conversation_id`. Plugins **never** import Django ORM/views directly — they go
through `host_api` (so the host's own RBAC applies) or the existing engine stores.

### 3.2 `WorkflowPlugin` — a declared multi-step process

```python
class WorkflowPlugin(ToolPlugin):
    """A composite process: an ordered list of steps, each referencing a tool."""

    steps: list[WorkflowStep]     # [{tool: "call_host_api"|"create_dq_rule", args: {...}}]
    dry_run: bool = True          # default preview; real write only after confirm

    async def execute(self, args, *, ctx): ...  # run steps; stop-and-ask on failure
```

Semantics mirror the existing `run_ops_workflow`: **preview first** (`dry_run=true`),
**stop and ask** on validation failure or when a real write needs confirmation. A
workflow step that calls a mutating tool inherits that tool's `requires_confirmation`.

### 3.3 Self-registering registry

A module-level `PLUGIN_REGISTRY` in `plugins.py`, populated by `register_plugin()`.
Discovery is **entry-point style**:

1. A `_PLUGINS: list[ToolPlugin]` list that built-in plugins (and later, app packages)
   append to at import time.
2. `load_plugins()` assembles the catalog: `STATIC_TOOL_DEFINITIONS` +
   `[p.to_definition() for p in _PLUGINS]` + `MCP_TOOLS`.
3. `tools.py::get_tool_definitions()` / `get_tool_executors()` delegate to
   `load_plugins()` so the agent sees the full merged catalog with **zero** further
   changes to `tools.py`.

**Growth = add a plugin class + register it.** No edit to the static lists.

### 3.4 Unified tool catalog (read API)

Extend `activation_api.py::_settings_tools()` to emit plugin-aware metadata:

```
{name, description, kind: "static"|"plugin"|"workflow"|"mcp",
 requires_confirmation, capability, app_identifier}
```

This is the **catalog** — read-only (RULE_21: AI suggests, Carbon executes). Runtime
CRUD over tools remains intentionally out of scope in this sprint; the catalog grows
by shipping plugins, and the console makes that growth *visible*.

---

## 4. Reference implementation — `create_dq_rule`

The first "specific-process" plugin, proving the whole contract:

```
User: "validate the email field, here are some examples"
Agent (create_dq_rule tool):
  1. dq.suggest  → candidate rule JSON (type, column, params, nl_check)
  2. dq.validate → {passed, explanation, failed_rows}
  3. returns a proposed rule + validation preview (DRY RUN — nothing written)
User confirms →
  4. host_api POST /carbon-api/dq/rules/  (JWT, requires_confirmation=True)
  5. returns the created DQRule + validation result
```

This is the exact DQ+AI target scenario from the ROADMAP north star, expressed as a
**named, reusable tool** instead of an ad-hoc `call_host_api` recipe. It binds to
`app_identifier="dq"`, gates on `dq:manage_rules`, and is confirmation-gated end to end.

---

## 5. Phases

### 12-A — Plugin ABCs + registry scaffolding (Backend)
- `engine/agent/plugins.py`: `ToolPlugin`, `WorkflowPlugin`, `ToolContext`,
  `PLUGIN_REGISTRY`, `register_plugin()`, `load_plugins()`.
- Wire `tools.py::get_tool_definitions()` / `get_tool_executors()` through
  `load_plugins()` (no change to static tool behavior).
- Tests: `ai/tests/test_plugins.py` (registration, dedup, definition shape, executor merge).

### 12-B — Unified catalog read API (Backend)
- Extend `_settings_tools()` to the plugin-aware shape in §3.4.
- Tests in `test_activation_api.py`.

### 12-C — Reference `create_dq_rule` plugin (Backend)
- `ai/domain/plugins/create_dq_rule.py` (or `ai/plugins/`) implementing §4.
- Register it; verify it appears in the merged catalog + settings `tools_catalog`.
- Tests: dry-run preview, confirmation-gated write, validation failure stops.

### 12-D — Tool catalog console (Frontend)
- Extend `ToolsPanel.jsx` (or `EngineSettingsPanel` → `ToolsCatalog`) to render
  `kind`, `requires_confirmation`, `capability` columns. Read-only (RULE_21).
- `aiPulse.js` helper if the catalog moves to its own endpoint.

### 12-E — Gates
- `cd backend && .venv/bin/python -m pytest ai dq accounts -q` (813 baseline + new).
- `cd carbon-frontend && npm run lint && npm test && npm run build`.

---

## 6. Acceptance criteria

1. A new `ToolPlugin`/`WorkflowPlugin` is **registered by adding one class + one
   `register_plugin()` call** — no edit to `STATIC_TOOL_DEFINITIONS`.
2. `get_tool_definitions()` returns static + plugin + workflow + MCP tools, with
   `get_tool_executors()` resolving every definition.
3. `GET settings/` → `tools_catalog` includes `kind`, `requires_confirmation`,
   `capability`, `app_identifier` per tool.
4. `create_dq_rule` runs the §4 flow: dry-run preview first, write only after user
   confirmation, host RBAC enforced via the user's JWT.
5. No tool ever performs an unconfirmed mutation (RULE_21); plugins that mutate
   default `requires_confirmation=True`.
6. Gates green (12-E).

---

## 7. Guardrails (non-negotiable)

- **RULE_21 (no auto-mutation):** every mutating plugin defaults to
  `requires_confirmation=True`; `MutationGuard` still validates provider responses.
- **RULE_20 (no data leakage):** plugins bind to `app_identifier`; `ScopeGuard` /
  `DataIsolationGuard` run before every call; plugins inherit scope from `ToolContext`.
- **RULE_18 (contract binding):** plugins are reached *only* through
  `CarbonIntelligence`; they never call a provider or Django view directly.
- **RULE_6 (in-hand engine):** plugin discovery is in-process at startup — no HTTP
  agent-card, no runtime provider swap.
- **Zero upward imports:** a plugin imports nothing from `catalog/mdm/dq/emissions/
  accounts/core`; it goes through `host_api` and the engine stores only.
