# ClearTurn Trust Platform — Documentation Index

Modular monolith (Django + React) deployed as isolated brand instances (AASTMT · Nibras · Tectona).

> **Tasks:** repo-root [`TASKS.md`](../TASKS.md) (active only).  
> **ADRs:** [`.ai-toolkit/decisions/`](../.ai-toolkit/decisions/).  
> **Archive:** [`_archive/`](./_archive/) (DONE specs, sprints, audits, historical TASKS).

---

## Canonical architecture

| Doc | Role |
|-----|------|
| [CLEARTURN-PLATFORM-ARCHITECTURE.md](./CLEARTURN-PLATFORM-ARCHITECTURE.md) | Product-line / multi-instance model |
| [NIBRAS-MASTER-STRATEGY.md](./NIBRAS-MASTER-STRATEGY.md) | Nibras product + commercial north star |
| [DESIGN-PLATFORM.md](./DESIGN-PLATFORM.md) | Platform design (canonical deep dive) |
| [STORAGE-PATTERN-HOSTED-APPS.md](./STORAGE-PATTERN-HOSTED-APPS.md) | Typed models vs dataschema (ADR-0025) |
| [ENTERPRISE-SYSTEM-FRAMEWORK.md](./ENTERPRISE-SYSTEM-FRAMEWORK.md) | Enterprise framework |

## Nibras — People / My / Team

| Doc | Role |
|-----|------|
| [DESIGN-EOFFICE-CORRESPONDENCE.md](./DESIGN-EOFFICE-CORRESPONDENCE.md) | Correspondence spine + ESS/MSS surfaces (ADR-0030) |
| [DESIGN-NIBRAS-ENTERPRISE-HR-DATA-MODEL.md](./DESIGN-NIBRAS-ENTERPRISE-HR-DATA-MODEL.md) | HR data model |
| [DESIGN-MULTI-BRAND-NIBRAS.md](./DESIGN-MULTI-BRAND-NIBRAS.md) | Brand/instance enablement |
| [DESIGN-PEOPLE-ORG-PROFILES.md](./DESIGN-PEOPLE-ORG-PROFILES.md) | Org / employee profiles |
| [DESIGN-PEOPLE-REFERENCE-GOVERNANCE.md](./DESIGN-PEOPLE-REFERENCE-GOVERNANCE.md) | Governed lookups (ADR-0027) |
| [SCREEN-SPEC-COMPENSATION-LEDGER.md](./SCREEN-SPEC-COMPENSATION-LEDGER.md) | Compensation UI ready-spec (ADR-0029) |
| [SCREEN-SPEC-EMPLOYEE-WIZARD.md](./SCREEN-SPEC-EMPLOYEE-WIZARD.md) | Hire wizard acceptance (NSR-4B: manager, join_date, opening_basic) |
| [QA-MANUAL-PEOPLE-MY-TEAM.md](./QA-MANUAL-PEOPLE-MY-TEAM.md) | Manual QA for people/my/team |

## Pulse / AI

| Doc | Role |
|-----|------|
| [pulse/](./pulse/) | Pulse QA + UX living docs |
| [pulse/QA-CHAT-AGENTIC-SCENARIO-BANK.md](./pulse/QA-CHAT-AGENTIC-SCENARIO-BANK.md) | Chat + Agentic scenario banks + measurement gates (Master/QA) |
| [pulse/LIVE-QA-2026-09-16.md](./pulse/LIVE-QA-2026-09-16.md) | Live server QA findings (Chat/Agent UX) |
| [pulse/QA-FRAMEWORK.md](./pulse/QA-FRAMEWORK.md) | Canonical intelligence/feature measurement spec |
| [DESIGN_AI_WORKSPACE_V4.md](./DESIGN_AI_WORKSPACE_V4.md) | AI workspace implementation target |
| [DESIGN-AGENT-WORKFLOW-AND-UI.md](./DESIGN-AGENT-WORKFLOW-AND-UI.md) | Agent workflow + UI |
| [PULSE-COWORKER-IMPLEMENTATION-SPEC.md](./PULSE-COWORKER-IMPLEMENTATION-SPEC.md) | Coworker implementation |

## Operations

| Doc | Role |
|-----|------|
| [QUICKSTART_DEPLOYMENT.md](./QUICKSTART_DEPLOYMENT.md) | Fast path |
| [SECURITY_DEPLOYMENT.md](./SECURITY_DEPLOYMENT.md) | Security + deploy |
| [DEPLOYMENT_PLAN_AASTMT_CARBON.md](./DEPLOYMENT_PLAN_AASTMT_CARBON.md) | AASTMT deploy plan |
| [env.md](./env.md) · [deployment.md](./deployment.md) · [api.md](./api.md) | Short references |

## Developer / QA

| Doc | Role |
|-----|------|
| [TESTING_QA_GUIDE.md](./TESTING_QA_GUIDE.md) | Testing guide |
| [ADMIN_USER_GUIDE.md](./ADMIN_USER_GUIDE.md) | Admin guide |
| [SIMULATION-GOLDEN.json](./SIMULATION-GOLDEN.json) | Simulation baseline (do not delete) |

## Archive (do not treat as current)

- [`_archive/tasks-history/`](./_archive/tasks-history/) — full historical TASKS / RESULTS  
- [`_archive/sprints/`](./_archive/sprints/) — completed sprint specs  
- [`_archive/audits/`](./_archive/audits/) — one-off audits  
- [`_archive/plans/`](./_archive/plans/) — completed implementation plans  
- [`_archive/design-superseded/`](./_archive/design-superseded/) — research / exploratory / shipped screen specs  
- [`_archive/demos/`](./_archive/demos/) · [`_archive/out-of-scope/`](./_archive/out-of-scope/)  
- Older phase task/result markdown under [`_archive/`](./_archive/)

---

*Root: [README.md](../README.md) · Toolkit: [.ai-toolkit/](../.ai-toolkit/)*
