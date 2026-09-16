# Registry — Auto-Generated Codebase Inventory

Generated: 2026-09-16 19:49
Command: `./.ai-toolkit/scripts/scan.sh`

**Purpose:** the single source of truth for WHAT ALREADY EXISTS.
Consult before building anything. This is how we prevent duplicate work.

| File | What it lists |
|------|---------------|
| [api.md](api.md) | All API endpoints & custom @action routes |
| [services.md](services.md) | Backend service classes + management commands |
| [models.md](models.md) | All data models |
| [components.md](components.md) | Frontend components, hooks, API modules |
| [config-keys.md](config-keys.md) | Every env/config key (no-hardcoding reference) |

**Workflow:** Master runs `scan.sh` before planning. Workers grep the registry
before creating anything new. Regenerate after any structural change.
