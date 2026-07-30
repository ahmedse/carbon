# ADR-0001: Design Pattern Architecture for Carbon Platform

## Status
Accepted (2026-07-30)

## Context
The Carbon Data Trust Platform has been developed iteratively by multiple AI
workers across 4 workstreams (W1: seed_users, W2: seed_all, W3: RBAC mapping,
W4: dashboards). A full GoF pattern audit was conducted to determine:

1. Which of the 23 Gang of Four patterns are actively in use
2. Whether the patterns are used correctly (problem-driven, not pattern-hunting)
3. What patterns are missing that would improve the architecture
4. Whether the code respects the GoF principle "favor object composition over class inheritance"

## Decision
We adopt the following pattern architecture as the project constitution:

### Backend (Django + DRF)
- **Facade**: ALL business logic in `services.py` classes (DashboardService, CalculationEngineService, etc.). Views are thin — parse parameters, call service, return response.
- **Strategy**: DRF permission classes (HasScopedRole, ReadAnyWriteAdmin, AdminOrSuperuserOnly) as interchangeable auth strategies.
- **Proxy**: Permission classes proxy every request — no inline `if user.has_perm()` in views.
- **Chain of Responsibility**: RBAC checks: IsAuthenticated → HasScopedRole → object-level.
- **Template Method**: ModelViewSet defines CRUD skeleton; subclasses override `get_queryset()`, `get_serializer_class()`.
- **Adapter**: `_perspective_from_group_name()` adapts Django Group names to frontend perspectives.
- **State**: Every lifecycle entity (ReportingPeriod, etc.) has STATUS_CHOICES + explicit transition methods.

### Frontend (React + MUI)
- **Composite**: Design System 3-Layer model (Tokens → Primitives → Composed). Components compose, never fork.
- **Flyweight**: MUI theme tokens shared by all components — no raw colors/spacing.
- **Observer**: React Context (AuthContext, ThemeContext) + hooks for state propagation.
- **Strategy**: Custom hooks (useEmissionsData, useEmissionsComparison) as interchangeable data-fetching strategies.
- **Adapter**: `transformApiResponse()` adapts raw API JSON to dashboard-friendly objects.
- **Decorator**: `GlassCard` wraps MUI Card; `AdminRoute` wraps routes with permission checks.
- **Chain of Responsibility**: `hasAppAccess()`: global admin → modules → app-specific roles.

### AI Toolkit
- **Facade**: `ONBOARDING.md` as single entry point.
- **Strategy**: 8 interchangeable worker roles.
- **Mediator**: Master Architect coordinates workers via TASKS.md / TASK-RESULTS.md.
- **Template Method**: Every shared contract follows the same skeleton.
- **Proxy**: `guard.sh` intercepts file creation, blocks secrets.
- **Observer**: `scan.sh` regenerates registry; workers observe before building.

## Consequences

### Positive
- Pattern vocabulary enables faster communication between AI workers ("use Facade here" → instant understanding)
- New workers onboard faster — they recognize the pattern architecture
- Anti-patterns are documented and enforceable
- Future refactoring has clear targets (missing patterns → ADR + implementation plan)

### Negative
- Increased abstraction — more files (services.py, permission classes, custom hooks) than a naive implementation
- Learning curve for workers unfamiliar with GoF patterns
- Risk of pattern-hunting if workers apply patterns without understanding the problem

### Mitigations
- `shared/design-patterns.md` provides exact local conventions for each pattern
- HARD RULES in `project.config.md` explicitly forbid pattern-hunting
- Master Architect reviews every phase for pattern appropriateness

## Scorecard
See `shared/design-patterns.md` for full breakdown. Current: 14/23 patterns actively used.

- Creational: 3/5 (Singleton, Factory Method; Builder/AbstractFactory/Prototype planned)
- Structural: 6/7 (all except Bridge)
- Behavioral: 5+/11 (Strategy, Observer, Template Method, Chain of Resp., Mediator + State/Command partial)

## References
- Gamma, Helm, Johnson, Vlissides — "Design Patterns: Elements of Reusable Object-Oriented Software" (1994)
- `.ai-toolkit/shared/design-patterns.md` — full pattern audit with local conventions
- `.ai-toolkit/shared/design-system.md` — Composite + Flyweight enforcement for UI
- `.ai-toolkit/shared/api-contract.md` — Adapter + Facade enforcement for APIs
