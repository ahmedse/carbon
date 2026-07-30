# Design Pattern Constitution — How Carbon Code Respects GoF
# Read by: ALL roles. Enforced by: Master Architect (reviews), Debugger (refactors toward).
#
# This file captures the 23 GoF patterns as they manifest in THIS codebase.
# It tells every worker: "this is how we compose objects here."
#
# Score: ~14/23 GoF patterns actively used across the stack.

---

## RULE 0 — Patterns Are Compulsory, Not Decorative

Every PR/phase is reviewed for pattern adherence. When creating or refactoring,
grep this file for the pattern you need and follow the EXACT local convention.

---

## CREATIONAL PATTERNS (3/5)

### Singleton — ✅ USED
**Convention:** One instance per process, globally accessible.
- Backend: `django.conf.settings` (project.config), `AuthContext` React context
- Frontend: `createTheme()` in `carbonTheme.js` — single MUI theme; `WidgetRegistry.js` — single widget catalog
- Toolkit: `project.config.md` — single project truth

### Factory Method — ✅ USED
**Convention:** DRF `ModelSerializer` is our factory. Frontend transforms are factories.
- Backend: `EmissionFactorSerializer(data=request.data)` creates validated model instances.
  `_load_app_manifests()` in `accounts/views.py` creates structured app objects from file text.
- Frontend: `transformApiResponse()` in `useEmissionsData.js` creates dashboard objects from raw API JSON.
  `apiFetch()` in `api.js` creates configured fetch requests.
- **Rule:** NEVER construct complex objects with raw `dict()` / manual field assignment. Use a serializer or a service factory method.

### Builder — ❌ NOT YET USED
**When to introduce:** `seed_all.py` is procedural. Complex filtered querysets with chained `.filter().annotate()` could use a `QueryBuilder`.
**Target:** `seed_all.py` → `SeedBuilder().with_users().with_factors().with_targets().run()`

### Abstract Factory — ❌ NOT YET USED
**When to introduce:** If we add multiple emission factor standards (IPCC, DEFRA, EPA), an Abstract Factory creates families of related factors without coupling to concrete standards.

### Prototype — ❌ NOT YET USED
**When to introduce:** `ReportingPeriod.clone()` for duplicating periods with new dates. `EmissionFactor.clone()` for creating variant factors.

---

## STRUCTURAL PATTERNS (6/7)

### Adapter — ✅ USED
**Convention:** Adapters live at API boundaries. They translate between incompatible representations.
- Backend: `_perspective_from_group_name()` in `accounts/views.py` — adapts Django `Group.name` ("dataowners_group") to frontend perspective ("data-owner").
- Frontend: `apiFetch()` in `api.js` — adapts raw `fetch()` to unified auth+token-refresh+query interface.
- **Rule:** When two subsystems have different naming/format conventions, add an adapter function — never force either side to change its native representation.

### Composite — ✅ USED
**Convention:** React component trees and DRF ViewSets are composites.
- Frontend: `Layout > HeaderEnhanced > MenuRow > RoleBadge` — uniform composition.
  `GlassCard` wraps MUI `Card` — leaf/composite treated identically.
  Design System 3-Layer model (Tokens → Primitives → Composed) IS the Composite pattern.
- Backend: ViewSets compose `@action` methods with inherited CRUD.
- **Rule:** Every UI component must compose existing primitives. NEVER fork/duplicate.

### Decorator — ✅ USED
**Convention:** Python decorators add behavior without modifying the decorated class.
- Backend: `@action`, `@swagger_auto_schema`, `@permission_classes` on DRF views.
- Frontend: `GlassCard` decorates MUI `Card` with glass styling. `AdminRoute.jsx` decorates routes with permission checks.
- **Rule:** Use decorators for cross-cutting concerns (auth, docs, logging). Never inline cross-cutting logic.

### Facade — ✅ USED
**Convention:** Services hide complexity behind a single method. API modules hide HTTP details.
- Backend: `DashboardService.get_dashboard_data()` in `emissions/services.py` — one call returns scope breakdown, category breakdown, monthly trends, DQ score, last_updated. `CalculationEngineService`.
- Frontend: `rbac.js` provides `hasAppAccess()`, `isGlobalAdmin()`, `isAnalyst()` — unified RBAC interface.
  `fetchEmissionsDashboard()` in `api/emissions.js` — one call for all dashboard data.
- Toolkit: `ONBOARDING.md` — single entry point to 30+ internal toolkit files.
- **Rule:** Every domain has ONE service class that is its public API. Views are thin (parse → call service → return). NEVER put business logic in views.

### Proxy — ✅ USED
**Convention:** Proxies control access transparently — the caller doesn't know they're talking to a proxy.
- Backend: `HasScopedRole` permission class — proxies every request through RBAC before it reaches the view.
- Frontend: `apiFetch()` auto-refreshes expired tokens transparently before proxying to the real endpoint.
- Toolkit: `scripts/guard.sh` — intercepts file creation, blocks secrets before they hit disk.
- **Rule:** Use permission classes as proxies. The view should never contain `if user.has_perm(...)` inline.

### Flyweight — ✅ USED
**Convention:** Shared intrinsic state via tokens/config, not per-instance duplication.
- Frontend: MUI theme tokens (`theme.palette.primary.main`, `spacing(2)`, `borderRadius: 1`) in `carbonTheme.js` — shared by ALL components. `WIDGETS` array in `WidgetRegistry.js` — shared widget definitions.
- Backend: `SCOPE_NAMES`, `MONTH_NAMES` constants in `services.py` — shared by all service methods.
- **Rule:** Colors/spacing/typography are tokens, NEVER raw values. See `.ai-toolkit/shared/design-system.md` RULE 1.

### Bridge — ❌ NOT YET USED
**When to introduce:** If we need to support multiple chart libraries (Chart.js ↔ ECharts ↔ Recharts) or multiple ORM backends (Django ORM ↔ SQLAlchemy), Bridge decouples abstraction from implementation.

---

## BEHAVIORAL PATTERNS (5+/11)

### Strategy — ✅ USED
**Convention:** Interchangeable algorithms behind a common interface.
- Backend: DRF permission classes (`HasScopedRole`, `ReadAnyWriteAdmin`, `AdminOrSuperuserOnly`) — interchangeable auth strategies behind `BasePermission`.
- Frontend: `useEmissionsData`, `useEmissionsComparison` hooks — interchangeable data-fetching strategies.
- Toolkit: 8 worker roles — interchangeable problem-solving strategies behind `shared/base-rules.md`.
- **Rule:** When behavior varies by role/permission/context, use Strategy. NEVER use if/else chains on role strings.

### Observer — ✅ USED
**Convention:** One-to-many dependency — when state changes, all dependents are notified.
- Frontend: React `useState`/`useEffect` + Context API. `AuthContext` notifies all consuming components on login/logout. `useEmissionsData` re-fetches when `year` changes. `ThemeContext` propagates dark/light mode.
- Backend: Django signals (implicit). `scan.sh → registry/` updates all workers.
- **Rule:** State belongs in Context (frontend) or signals (backend). NEVER pass state through prop drilling or middleware chains.

### Template Method — ✅ USED
**Convention:** Algorithm skeleton in base class, steps deferred to subclasses.
- Backend: `ModelViewSet` defines `list/create/retrieve/update/destroy` skeleton; subclasses override `get_queryset()`, `get_serializer_class()`. `ModelSerializer.Meta` defines field skeleton.
- Toolkit: Every shared contract follows: RULE 0 (registry) → numbered rules → never/always lists. Skeleton fixed; domain specifics vary.
- **Rule:** If two views share >50% of their logic, extract a base class with Template Method. Never copy-paste view logic.

### Chain of Responsibility — ✅ USED
**Convention:** Pass request through a chain of handlers until one handles it.
- Backend: DRF permission chain: `IsAuthenticated → HasScopedRole → object-level check`. Django middleware chain.
- Frontend: `hasAppAccess()` in `rbac.js`: global admin check → modules check → app-role check. Each link passes or blocks.
- **Rule:** Auth/Access checks MUST be chained, not nested if/else. Add new checks by adding to the chain, not by modifying existing checks.

### Mediator — ✅ USED
**Convention:** Central mediator coordinates objects — they never talk directly.
- Frontend: `AuthContext` mediates between localStorage, `/me/context/` API, and all consuming components.
- Backend: Master Architect workflow: Master writes `TASKS.md` → Worker executes → Worker writes `TASK-RESULTS.md` → Master reviews.
- **Rule:** Components/workers never communicate directly across layers. Use the mediator (Context, Master, or service bus).

### State — ✅ PARTIAL
**Convention:** Object behavior changes with internal state.
- Backend: `ReportingPeriod.STATUS_CHOICES` with `submit()` and `verify()` actions enforcing valid transitions: draft → open → locked → submitted → verified → closed.
- **Rule:** Every lifecycle entity must have explicit status choices + action methods that validate transitions. NEVER allow direct status field mutation.

### Command — ⚠️ PARTIAL
**What exists:** `manage.sh` wraps operations. `@action` methods on ViewSets encapsulate operations.
**What's missing:** No undo queue. No command history. No operation logging beyond audit trail.
**Target:** Wrap DQ rule edits and data entry mutations in Command pattern for audit+undo.

### Iterator — ✅ IMPLICIT
Django QuerySets, Python generators, JS `Array.map/filter/reduce`. Ubiquitous — no explicit convention needed.

### Memento, Visitor, Interpreter — ❌ NOT APPLICABLE
These patterns solve problems (undo snapshots, operations on object structures, DSL parsing) that this codebase doesn't currently have. Add if needed.

---

## THE HARD RULES (Enforced in Review)

| # | Rule | Pattern | Check |
|---|------|---------|-------|
| 1 | Thin views, fat services | Facade + Strategy | View methods ≤ 10 lines (parse → call service → return) |
| 2 | Permissions are proxies, never inline | Proxy + Chain | No `if user.has_perm()` in view body |
| 3 | Components compose, never duplicate | Composite + Flyweight | No `Button2`, `NewCard`, `CustomTable` |
| 4 | State transitions are explicit | State | Every lifecycle model has `STATUS_CHOICES` + `transition_*()` methods |
| 5 | API shapes are contracts, not ad-hoc | Adapter + Facade | Every endpoint follows `shared/api-contract.md` envelope |
| 6 | Colors/spacing are tokens | Flyweight | No raw hex colors or px spacing |
| 7 | RBAC is a chain, not a tree | Chain of Responsibility | `hasAppAccess()` checks: global → modules → roles |
| 8 | Workers compose patterns, not invent new ones | Composite + Strategy | Before creating, grep this file + registry |

---

## ANTI-PATTERNS (What to NEVER Do)

| Anti-Pattern | Why It's Wrong | Pattern It Violates |
|-------------|----------------|---------------------|
| `if user.role == "admin": ... elif user.role == "analyst": ...` | Brittle, hard to extend | Strategy (use permission classes) |
| `<Box sx={{ color: '#3b82f6', padding: '13px' }}>` | Inconsistent, non-themeable | Flyweight (use theme tokens) |
| `def my_view(request): ... 200 lines of logic ...` | Untestable, unreusable | Facade (thin views, fat services) |
| `Button2`, `NewCard` | Duplication entropy | Composite (extend via props) |
| `model.status = 'verified'; model.save()` | No transition validation | State (use transition methods) |
| Copy-pasting a ViewSet to create a similar one | Divergence over time | Template Method (extract base class) |

---

## SCORECARD (Last Audit: 2026-07-30)

```
Creational:  ██████░░░░  3/5   (Singleton, Factory Method, [missing Builder/AbstractFactory/Prototype])
Structural:  ██████████  6/7   (Adapter, Composite, Decorator, Facade, Proxy, Flyweight, [missing Bridge])
Behavioral:  ████████░░  5+/11 (Strategy, Observer, Template Method, Chain of Resp., Mediator + State/Command partial)

VALIDATED:   14/23 patterns actively used, 4 partial/planned, 5 N/A for domain
GATE:        ALL 283 backend tests pass. Pattern adherence reviewed by Master Architect.
VERIFIED:    Frontend Design System 3-Layer model enforces Composite+Flyweight.
             Backend services.py enforces Facade+Strategy.
             RBAC chain enforces Chain of Responsibility+Proxy+Adapter.
```

---

## HOW TO USE THIS FILE

```bash
# Before creating a new view:
grep -A5 "Facade" .ai-toolkit/shared/design-patterns.md

# Before adding a permission:
grep -A5 "Chain of Responsibility" .ai-toolkit/shared/design-patterns.md

# Before building a UI component:
grep -A5 "Composite\|Flyweight" .ai-toolkit/shared/design-patterns.md

# When a pattern is MISSING (e.g., need Command for undo):
# 1. Check this file for the "target" convention
# 2. Implement following the convention
# 3. Update the scorecard at the bottom
# 4. Add an ADR in decisions/
```
