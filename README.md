# Carbon Data Trust Platform

**An AI-driven, multi-tenant Data Trust Platform that hosts governed domain applications on a trusted data core.**

Carbon is enterprise infrastructure for *trusted, governed data* — a governed data core (catalog, data quality, master data, lineage) with capability-based access control, a portable AI engine, and pluggable domain apps. The flagship domain app is **Carbon Footprint** (GHG Protocol emissions accounting), joined by **People (HR & Payroll)** and **e-office Correspondence**. Multiple organization brands run as isolated tenants on the same codebase.

---

## Why Carbon

Data products earn trust through governance. Carbon wraps every dataset in:

- **Catalog & governance** — data products, metadata, domains, tags, and field-level policies.
- **Data Quality** — profiling, rules, and scoring with a closed remediation loop.
- **Master Data (MDM)** — golden records and org-unit scoping.
- **Data Schema & Lineage** — schema authoring and traceability.
- **Connections & Evidence** — source onboarding with auditable evidence.

On top of that core sit **domain apps** (emissions, people/HR, e-office), each activated through an **App Registry** with **capability-based access control (CBAC)** — a single, declarative permission model mirrored across backend and frontend.

---

## Key Capabilities

- **Multi-tenant / multi-brand isolation** — `aastmt`, `nibras`, `medos`, `tectona` run as isolated tenants (separate database, Redis index, media, Chroma, and branding) flipped via one command.
- **Carbon Footprint** — Scope 1/2/3 tracking, SBTi targets, emission factors, calculation rules, verification, and GHG inventory reporting aligned to VVB standards.
- **HR & Payroll** (`nibras`) — employee lifecycle, payroll engine, payslips, loans, leave, attendance, and self-service/manager approval workflows.
- **e-office Correspondence** — inbox routing, approval FSM (approve/reject/send-back), notifications, and audit trail.
- **Portable AI engine** — a domain-agnostic intelligence kernel (`backend/ai/engine/`) with cognition, memory, and learning layers; zero domain terms in the core.
- **TurnKey ML bridge** — bidirectional link to an ML serving tier: push artifacts, receive predictions and drift alerts.
- **Role & capability security** — JWT + ScopedRole RBAC plus frontend CBAC gating on every route, menu, and action.

---

## Architecture

| Layer | Technology |
|---|---|
| Backend | Django 5.2 + DRF, Python 3.12, PostgreSQL 16, Redis |
| Frontend | React 19 + Vite 6, Material UI v7 |
| Auth | JWT (SimpleJWT) + ScopedRole RBAC + CBAC capabilities |
| AI engine | Vendored in-process (`backend/ai/engine/`), LLM via API key |
| Ops | `./manage.sh` single controller; Docker Compose for production |
| Ports | Backend `:8009`, Frontend `:5179` |

### System map

```
Domain Apps  (may use core; core NEVER imports domain)
  emissions/   healthy/   people/   correspondence/

Platform Layers
  datahub/             integrations/turnkey/      appregistry/
  Dataset versioning   Push artifacts             App manifests
  Health scoring       Receive predictions        Activation + CBAC

Platform Core
  accounts  catalog  mdm  dq  dataschema  connections  evidence  importexport  ai/  core
```

The dependency rule is strict: each layer imports only downward. The **AI engine** is a portable intelligence kernel — bootstrapping it into a new project means copying `backend/ai/engine/` unchanged and writing one `instance.yaml` config. See `ARCHITECTURE.md` and ADR-0017 for the full contract.

---

## Repository Structure

```
carbon/
├── backend/              # Django apps (accounts, catalog, dq, mdm, emissions, people, …)
├── carbon-frontend/      # React app (MUI 7, routing, dashboards, CBAC)
├── docs/                 # Architecture, API, data model, deployment, designs
├── .ai-toolkit/          # Agent instructions, ADRs, scripts, patterns
├── docker-compose.yml
├── manage.sh             # Single ops controller (build/run/switch/health)
└── ARCHITECTURE.md       # Single source of truth
```

---

## Quick Start

```bash
git clone <repo-url> && cd carbon
./manage.sh setup          # create venv, install deps, migrate
./manage.sh start          # backend + frontend
./manage.sh health         # verify all services
```

`./manage.sh` drives everything — environment loading, brand switching, superuser checks, and service control. See `.ai-toolkit/ONBOARDING.md` for the full onboarding flow.

---

## Documentation

- [Architecture](./ARCHITECTURE.md) — system map, layers, AI kernel contract
- [API Reference](./docs/api.md)
- [Data Model](./docs/data-model.md)
- [Deployment](./docs/deployment.md)
- [Roadmap](./ROADMAP.md)

---

## Testing

```bash
cd backend && python -m pytest --reuse-db -q   # ≥431 tests
cd carbon-frontend && npm test -- --run        # frontend tests
```

---

## License

See [LICENSE](./LICENSE) for details.

---

**For questions, refer to the [docs/](./docs) folder or contact the maintainers.**
