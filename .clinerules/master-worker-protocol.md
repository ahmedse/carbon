# Master/Worker Handoff Protocol (Carbon Project)

This project uses the Master/Worker handoff protocol for structured task execution.

**See the full protocol specification at:** `~/Documents/Cline/Rules/master-worker-protocol.md`

## Current Project Context

- **Repository:** Carbon Data Trust Platform (Django/DRF backend + React frontend)
- **Master:** Planner (writes TASK.md)
- **Worker:** Raptor/Copilot (executes TASK.md, returns TASK-RESULT.md)

## Active RUN Sequence (A0–A6)

| RUN | Title | Type | Status |
|-----|-------|------|--------|
| A0 | Ground-truth audit | read-only | NEXT |
| A1 | Repo hygiene & doc truth | cleanup | pending |
| A2 | Core governance RBAC fix | backend | pending |
| A3 | Data-owner scoped experience | backend+frontend | pending |
| A4 | Admin experience | backend+frontend | pending |
| A5 | Data Trust surfacing decision | design+build | pending |
| A6 | Deployment-readiness gate | ops | pending |

## Project-Specific Constraints

All RUNs must respect:
- **One-way dependencies:** `emissions → core` (catalog/mdm/dq/dataschema), never reverse
- **Additive migrations only:** No destructive schema changes
- **No Pulse/AI/LLM work:** The `ai_copilot` app is frozen (superseded by external Pulse)
- **No tenant work:** Multi-tenancy is explicitly out of scope
- **Authoritative docs:** `docs/STRATEGY_DATA_TRUST_PLATFORM.md`, `docs/DESIGN_DATA_TRUST_CORE.md`, `docs/PLAN_DATA_TRUST_PHASES.md`, `docs/DESIGN_ORG_ACCESS_MODEL.md`

## Current TASK

See `TASK.md` in the repository root for the active RUN specification.
