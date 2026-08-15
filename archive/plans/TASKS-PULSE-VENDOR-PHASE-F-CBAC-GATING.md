# TASKS — PULSE VENDOR PHASE F: CBAC Capability-Gating on the AI Admin Read Surface

**Role:** backend-worker + frontend-worker (one scoped full-stack worker; see §3)
**Model:** DeepSeek V4 Flash (customendpoint)
**Domain:** backend (Django + vendored Pulse engine) + frontend (React 19 + Vite + MUI)
**Status:** Ready for execution
**Precedes:** — (closes the AI Admin console CBAC gap; no later phase depends on it)

---

## 0. Goal

Close the last open Pulse gap from Phase E: the AI Admin console read surface is
currently gated **`IsAuthenticated` only**, and the frontend `ai-admin` studio is
gated **`isGlobalAdmin` only** (not CBAC). This phase:

1. **Adds an `ai:view_console` capability** to the CBAC single source of truth
   (`accounts/capabilities.py`).
2. **Gates all 10 Pulse read endpoints** on that capability via the canonical
   `AdminOrSuperuserOnly` permission class.
3. **Applies the `AppScopeMixin` tenancy filter** (app + visibility + org subtree)
   consistently to every model-backed read path — especially the new normalized
   `graph/` endpoint — so scope/visibility partitioning matches the engine's
   `_apply_tenancy_filter` semantics.
4. **Mirrors the capability in the frontend** (`capabilities.js` + `authz.js` +
   `AdminRoute` `requiredCapability` + `useShellState` studio gate).

**Out of scope (DO NOT build):** any `ai:manage_*` write capability (there are no
AI write endpoints yet), new groups/roles, Celery, new LLM work, changes to
`ai/store.py` or `ai/engine/*`, changes to `ai/models/*`.

---

## 1. CRITICAL FACTS (read before touching anything)

1. **Interpreter:** `/home/ahmed/aast/carbon/.venv/bin/python` (repo-root venv,
   NOT `backend/.venv`). Django commands: `cd backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py ...`.
2. **CBAC single source of truth:** `backend/accounts/capabilities.py`.
   - `Capability` dataclass: `key/domain/action/label/description/category(default "general")/default_roles`.
   - `ALL_CAPABILITIES: Dict[str, Capability]` — master registry (add new cap here).
   - `IMPLIES` — transitive inheritance (manage → view).
   - `GROUP_CAPABILITIES` — group → cap set. `"admin"` and `"admins_group"` map to
     `{"*"}` (wildcard = ALL capabilities incl. future ones). **No group change is
     needed for this phase** — global admins already get `ai:view_console` via `*`.
   - `has_capability(user, key)` resolves superuser → `{"*"}`; global role → full caps;
     scoped wildcard → read-only view caps only (DD-1).
3. **Permission class (canonical, reuse — DO NOT invent a new one):**
   `accounts/permissions.py::AdminOrSuperuserOnly` gates **all** access on the view's
   `required_capability`. Resolution: (1) superuser → True; (2) global admin
   (`ScopedRole group__name__in=['admin','admins_group']` with `org_unit__isnull=True,
   module__isnull=True`) → True; (3) `has_capability(user, required_capability)`; (4)
   legacy `domain_lead_groups` fallback. **Set `required_capability = "ai:view_console"`
   on each view.**
4. **`AppScopeMixin` fields (exact, from `ai/models/base.py`):**
   - `app_identifier = CharField(64, default "carbon")`
   - `org_unit_id = BigIntegerField(null=True, blank=True)`
   - `host_user_id = CharField(255, null=True, blank=True)`  ← **STRING field**
   - `visibility = CharField(16, default "private")`  (values `global|shared|private`)
   - Tenancy semantics (mirror `ai/store.py::scope_q`): `global` → visible to all;
     `shared` → visible within the app; `private` → only `host_user_id == str(user.id)`.
5. **The `ai` package purity rule:** `ai/models/*`, `ai/store.py`, `ai/engine/*` must
   NOT import `accounts`/`catalog`/`mdm`/`dq`/`emissions`/`core`. The **read-layer API
   views** (`ai/observability_api.py`, `ai/graph_api.py`, `ai/activation_api.py`,
   `ai/sweeps_api.py`, `ai/ops_api.py`) ARE the query boundary and MAY import
   `accounts.*` (precedent: `ai/intelligence.py` already lazily imports
   `accounts.models` + `dq.services`). **Do NOT add accounts imports to models/store/engine.**
6. **10 Pulse read views** (all currently `permission_classes = [IsAuthenticated]`):
   - `ai/ops_api.py` → `PulseHealthView` (health/), `PulseModulesView` (modules/),
     `PulseTaskStatusView` (tasks/<task_id>/)
   - `ai/observability_api.py` → `PulseInventoryView` (inventory/), `PulseDataView`
     (data/<key>/), `PulseArchetypesView` (archetypes/)
   - `ai/graph_api.py` → `GraphDataView` (graph/)
   - `ai/activation_api.py` → `PulseUsageView` (usage/), `PulseSettingsView` (settings/)
   - `ai/sweeps_api.py` → `SweepsStatusView` (sweeps/)
   - Mounted in `ai/ops_urls.py` under `/carbon-api/ai/pulse/`.
7. **Existing AI read tests use a PLAIN user and assert 200.** `conftest.py` exposes
   `create_user(username, ..., is_staff=False, is_superuser=False)` and
   `get_token_for_user(user)`. The test files (`test_ops_api.py`,
   `test_observability_api.py`, `test_graph_api.py`, `test_activation_api.py`,
   `test_cognition_scheduler.py`) each define their own `user` fixture via
   `User.objects.create_user(...)`. **After gating these will get 403 — update the
   fixtures and add 403 tests (see §4).**
8. **Frontend auth facts:**
   - `carbon-frontend/src/capabilities.js` is the frontend mirror (exports constants +
     `expandCapabilities`, `hasCap`, `hasAnyCap`, `hasAllCaps`, `ROUTE_CAPABILITIES`,
     `MENU_ITEM_CAPABILITIES`, …). **No `ai:*` capability exists there yet.**
   - `carbon-frontend/src/authz.js` re-exports `ROUTE_CAPABILITIES`, `hasCap`, etc.,
     and has `can(user, action, resource, ctx)` with a global-admin bypass. The
     `access_route` action resolves `ROUTE_CAPABILITIES[path]` (exact + prefix).
   - `carbon-frontend/src/components/AdminRoute.jsx` supports `requiredCapability={...}`
     (explicit capability check) in addition to `appId`/platform modes.
   - `/admin/ai/*` routes in `App.jsx` (lines ~312–330) are all wrapped in bare
     `<AdminRoute>` (no `appId`, no `requiredCapability`).
   - `carbon-frontend/src/shell/useShellState.js` gates the `ai-admin` studio on
     `isGlobalAdmin(...)` only — this is the frontend gap to close.
9. **Seeded demo data** (`ai/management/commands/seed_ai_demo.py`, run earlier this
   session) uses `visibility="shared"`, `org_unit_id=None`, `host_user_id=None`. After
   gating, a superuser/global admin still sees it all (bypass). A future `ai_lead`
   (non-global) would see it too (shared + null org = visible to all capability holders).

---

## 2. DESIGN DECISIONS (locked)

- **Capability key = `ai:view_console`** (mirrors the existing `carbon:view_console`
  naming; the AI Admin console is the Pulse console). Category `"admin"`.
- **No `ai:manage_*`** — there is no AI write surface yet.
- **No group changes** — `"admin"`/`"admins_group"` wildcard `{"*"}` already grants
  `ai:view_console` to global admins; superusers bypass via step 1. A future
  `ai_lead` group can be added later without code changes.
- **Permission = `AdminOrSuperuserOnly`** with `required_capability="ai:view_console"`.
  Read AND the (nonexistent) write both require the capability — correct for an
  admin console.
- **Scope filter helper lives in `accounts/`** (new `accounts/ai_scoping.py`), NOT in
  the `ai` package — keeps the `ai` models/store/engine pure while owning org-scope
  logic in `accounts`. Read-layer views import it at the query boundary.
- **Scope filter bypass = superuser OR global admin** (matches `_check_write_capability`
  steps 1–2). Non-global capability holders get visibility + org-subtree filtering.

---

## 3. TASKS

### Task A — Capability + permission gating (backend)

**A1. `backend/accounts/capabilities.py`** — add the capability:

```python
# ── AI (Pulse) domain capabilities ─────────────────────────────────
AI_VIEW_CONSOLE = Capability(
    key="ai:view_console",
    domain="ai",
    action="view_console",
    label="View AI Admin Console",
    description="View the Pulse AI admin console (health, modules, tasks, inventory, data, archetypes, graph, usage, settings, sweeps)",
    category="admin",
)
```

Register it in `ALL_CAPABILITIES` (add under a new `# AI` section, alongside the
other domain sections). **No `IMPLIES` entry, no `GROUP_CAPABILITIES` change.**

**A2. Gate all 10 views** — in each of the 5 API files, replace
`permission_classes = [IsAuthenticated]` with:

```python
from accounts.permissions import AdminOrSuperuserOnly
...
class XxxView(APIView):
    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "ai:view_console"
```

Files/views:
- `ai/ops_api.py`: `PulseHealthView`, `PulseModulesView`, `PulseTaskStatusView`
- `ai/observability_api.py`: `PulseInventoryView`, `PulseDataView`, `PulseArchetypesView`
- `ai/graph_api.py`: `GraphDataView`
- `ai/activation_api.py`: `PulseUsageView`, `PulseSettingsView`
- `ai/sweeps_api.py`: `SweepsStatusView`

Keep the `IsAuthenticated` import only if still used elsewhere in the file; otherwise
remove it to avoid an unused import. The `AdminOrSuperuserOnly` class itself returns
`False` for anonymous users (it checks `user.is_authenticated`), so the 401 behavior is preserved.

### Task B — Visibility/scope filter on model-backed reads (backend)

**B1. New `backend/accounts/ai_scoping.py`:**

```python
"""CBAC tenancy scoping for the AI read layer (Phase F).

Applies the ``AppScopeMixin`` partition (app + visibility + org subtree) to a
read-layer queryset. Lives in ``accounts`` so the ``ai`` models/store/engine stay
pure; the ``ai`` read-layer views import it at the query boundary.
"""
from django.db.models import Q

from .constants import ADMIN_ROLES
from .rbac_utils import get_allowed_org_unit_ids, user_is_global_admin


def scope_ai_queryset(qs, user):
    """Filter an AI read queryset by app + visibility + org scope.

    Superusers and global admins see everything (bypass — matches
    ``_check_write_capability`` steps 1-2).  Everyone else sees:
      - ``visibility`` in (global, shared) rows, plus their own ``private`` rows
      - rows in their allowed org subtree (or null-org rows if they hold no org role)
    """
    qs = qs.filter(app_identifier="carbon")
    if user.is_superuser or user_is_global_admin(user):
        return qs
    uid = str(user.id)
    vis = (
        Q(visibility__in=["global", "shared"])
        | Q(visibility="private", host_user_id=uid)
    )
    qs = qs.filter(vis)
    allowed = get_allowed_org_unit_ids(user, ADMIN_ROLES)
    if allowed:
        qs = qs.filter(Q(org_unit_id__in=allowed) | Q(org_unit_id__isnull=True))
    else:
        qs = qs.filter(org_unit_id__isnull=True)
    return qs
```

**B2. Apply `scope_ai_queryset` at the query boundary** (wrap the base queryset
BEFORE `.aggregate()`, `.values().annotate()`, `.count()`, iteration, or `.order_by()`):

- `ai/observability_api.py::PulseInventoryView` — wrap `model.objects` before `.count()`.
- `ai/observability_api.py::PulseDataView` — wrap `model.objects.all()` before
  ordering/slicing.
- `ai/graph_api.py::GraphDataView` — wrap the `KnowledgeNode`/`KnowledgeEdge`/
  `KgNode`/`KgEdge` querysets (all four inherit `AppScopeMixin`).
- `ai/activation_api.py::PulseUsageView` — wrap `LLMCallLog.objects` once, then reuse
  the scoped qs for `today_agg`, `total_agg`, `by_model`, `by_day`.
- `ai/sweeps_api.py::SweepsStatusView` — wrap `CognitionSweepRun.objects` before
  `.order_by("task_name", "-last_run")`.
- **No scope filter** on `PulseHealthView`, `PulseModulesView`, `PulseTaskStatusView`
  (no model rows), `PulseSettingsView` (engine config, no model rows), or
  `PulseArchetypesView` (filesystem listing, no model rows).

### Task C — Frontend mirror + gating

**C1. `carbon-frontend/src/capabilities.js`** — add the constant and the route mapping:

```js
export const AI_VIEW_CONSOLE = 'ai:view_console';
```

Add to `ROUTE_CAPABILITIES`:

```js
'/admin/ai': AI_VIEW_CONSOLE,
```

(The `access_route` prefix-match in `authz.js` then covers every `/admin/ai/*` path.)

**C2. `carbon-frontend/src/App.jsx`** — import `AI_VIEW_CONSOLE` (add to the existing
`import { ... } from "./capabilities"` block) and add
`requiredCapability={AI_VIEW_CONSOLE}` to each of the 19 `/admin/ai/*` `<AdminRoute>`
wrappers (lines ~312–330). This makes the gate explicit and capability-driven.

**C3. `carbon-frontend/src/shell/useShellState.js`** — gate the `ai-admin` studio on
capability (keeping `isGlobalAdmin` as the existing bypass). Add `AI_VIEW_CONSOLE`
and `hasCap`/`expandCapabilities` imports as needed, and change the `ai-admin`
condition to also pass for a capability holder. Preserve the existing
`studioFromPath` `/admin/ai`-before-`/admin` ordering (DO NOT reorder).

> Note: `isGlobalAdmin` already implies `ai:view_console` (global admins get `*`),
> so this is purely additive — it lets a future `ai_lead` holder reach the studio
> without being a global admin. The backend 403 will still enforce the hard boundary.

---

## 4. TEST PLAN (backend — MUST update existing fixtures)

1. **Update the 5 existing test files** so the happy-path `user` fixture is a
   **superuser** (the capability gate bypasses via `is_superuser`). Minimal change in
   each file's `user` fixture:
   ```python
   user = User.objects.create_user(username="...", password="...")
   user.is_superuser = True
   user.is_staff = True
   user.save()
   return user
   ```
   (Alternatively use the shared `create_user` fixture with `is_superuser=True`.)
   The anonymous-401 tests remain unchanged.

2. **Add new 403 + scope tests** (new file `ai/tests/test_cbac_gating.py`):
   - Plain authenticated user (no capability, not superuser, no global admin role)
     → **403** on all 10 endpoints (spot-check at least: graph, inventory, data,
     usage, settings, sweeps, health).
   - Global admin (a user with a `ScopedRole(admins_group, org_unit=None, module=None)`)
     → **200** (bypass via step 2).
   - **Scope filter**: create `KnowledgeNode` rows with `visibility="private",
     host_user_id=str(other_user.id)` and `visibility="shared"`; assert a
     non-global capability-holder sees only the shared row (and global admin sees all).
   - Reuse `create_user`, `create_scoped_role`, `get_token_for_user` from `conftest.py`.

3. **No new tests for `settings/`, `health/`, `modules/`, `tasks/`, `archetypes/`
   scope filtering** (they carry no model rows) — but DO assert 403 on a plain user
   for at least `health/` and `settings/`.

---

## 5. GATES (run in this exact order, show full output)

```bash
cd backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check
cd backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check   # expect "No changes" (no model changes)
cd backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests dq/tests -q
# verify.sh backend + antipatterns (NO new accounts imports in ai/models|store|engine)
cd carbon-frontend && npm run build
cd carbon-frontend && npm test
```

Regression bar: current `pytest ai+dq` = **397 passed**; must be ≥ 397 + new tests,
**0 failed**.

---

## 6. DEFINITION OF DONE

- [ ] `ai:view_console` in `ALL_CAPABILITIES` (backend) + `capabilities.js` (frontend).
- [ ] All 10 Pulse read views gated `AdminOrSuperuserOnly` + `required_capability="ai:view_console"`.
- [ ] `accounts/ai_scoping.py::scope_ai_queryset` exists and is applied to the 5
      model-backed read paths (inventory/data/graph/usage/sweeps).
- [ ] No `accounts`/`catalog`/`mdm`/`dq`/`emissions`/`core` import added to
      `ai/models/*`, `ai/store.py`, or `ai/engine/*` (grep clean).
- [ ] Existing 5 AI read test files updated to superuser fixtures; new 403 + scope
      tests in `ai/tests/test_cbac_gating.py`.
- [ ] All gates green (check, makemigrations --check, pytest ≥ 397 + new, verify.sh,
      npm build, npm test).
- [ ] Results written to `plans/TASK-RESULTS-PULSE-VENDOR-PHASE-F-CBAC-GATING.md`.
- [ ] NOT committed (Master does not `git add -A`; user commits).
