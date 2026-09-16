# Master/Worker Handoff Protocol (Carbon)

This project uses the `.ai-toolkit/` Master→Worker system. Authoritative bootstrap:
`.ai-toolkit/ONBOARDING.md` → `project.config.md` → `roles/<role>.md`.

## Roles & models

| Role | Model | Writes |
|------|-------|--------|
| **Master Architect** | DeepSeek V4-Pro (`deepseek-v4-pro`) | `TASKS.md` phases, ADRs |
| **All other roles** (backend, frontend, devops, data-ml, debugger-fixer, qa-validator, product-designer, researcher, curator) | DeepSeek V4.1-Flash (`deepseek-flash`) | Code / evidence per role |

Kimi / V3 / R1 are **retired** — never assign them.

## Handoff loop

1. Master writes a `TASKS.md` phase (role, files to read, contract, verification gate).
2. Worker reads `project.config.md` + `shared/base-rules.md` + role + registry, then builds.
3. Worker runs `./.ai-toolkit/scripts/verify.sh` for the relevant target and records **terminal proof** in `TASK-RESULTS.md`.
4. Master reviews proof → next phase or done.
5. After bug fixes: regression test + `troubleshooting/playbook.md` entry (never-fix-twice).

## Project constraints (always on)

- **No multi-tenant / Project model** — single-tenant multi-instance (ADR-0015).
- **Core ↛ domain imports** — domain apps may import core; never reverse (RULE_3).
- **Pulse is in-hand** — `backend/ai/engine/` co-deployed; no runtime provider swap (ADR-0007, RULE_6/13).
- **AI surface** — bind to `shared/ai-contract.md` (RULE_18–21).
- **Routes** — absolute + namespace-prefixed; no dangling targets (RULE_5/15/22); FE audit = `scripts/audit-routes.py`.
- **One breadcrumb** — `carbon-frontend/src/shell/Breadcrumbs.jsx` only (RULE_9).
- **Venv** — repo-root `.venv` (`/home/ahmed/ws/carbon/.venv`), never `backend/venv`.

## Commands

```bash
./.ai-toolkit/scripts/activate.sh <role>
./.ai-toolkit/scripts/scan.sh
./.ai-toolkit/scripts/verify.sh full
./.ai-toolkit/scripts/guard.sh   # also wired via .github/hooks/guard-secrets.json
```

## Current task

See `TASKS.md` / `TASK-RESULTS.md` at the repository root.
