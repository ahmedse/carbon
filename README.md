# Carbon Data Trust Platform

Enterprise carbon emissions management platform. Multi-scope GHG tracking, data quality governance, role-based access control, and auditable reporting. Django 5.2 + DRF 3.16 backend, React 18 + MUI 7.1 frontend.

---

## 🚀 Overview

- **Multi-scope emissions tracking** (Scope 1/2/3, SBTi targets)
- **Data quality governance** with profiling, rules, and scoring
- **Granular role-based access control (RBAC)** with org-unit scoping
- **Excel GHG inventory** exportable with full audit trail
- **Modern React frontend** (MUI 7) & Django REST backend
- **Containerized deployment** via Docker Compose

---

## 🏗️ Architecture

- **Frontend**: React 18 (Vite) + Material UI 7.1 — port 5179, base `/carbon/`
- **Backend**: Django 5.2 + DRF 3.16 + JWT Auth — port 8009, prefix `/carbon-api/`
- **Database**: PostgreSQL + Redis (caching)
- **DevOps**: Docker, Docker Compose
- **AI Toolkit**: `.ai-toolkit/` — agent instructions, decisions registry, project config

> **Scheduler sidecar** — `docker-compose.yml` also runs a `scheduler` service
> (`manage.py run_cognition_loop`) for the conscious cognition loop. It builds
> the same backend image, shares `./backend/.env`, and depends on `backend`,
> but publishes no ports. It runs the `AsyncIOScheduler` jobs on a dedicated
> asyncio event loop and blocks until SIGINT/SIGTERM.

---

## 📂 Repository Structure

```
carbon/
├── backend/              # Django apps (accounts, catalog, emissions, dq, mdm, …)
├── carbon-frontend/      # React app (MUI, routing, dashboards)
├── docs/                 # Architecture, API, workflows, deployment guides
│   └── archive/          # Historical task/phase records
├── plans/                # Architecture & strategy plans
├── .ai-toolkit/          # Agent customization, ADRs, scripts, patterns
├── docker-compose.yml
├── manage.sh             # Management script
└── README.md
```

---

## 🛠️ Quick Start

```bash
git clone <repo-url> && cd carbon
# Backend
cd backend && cp .env.example .env && pip install -r requirements.txt
python manage.py migrate && python manage.py runserver 0.0.0.0:8009
# Frontend
cd carbon-frontend && npm install && npm run dev
```

See [docs/QUICKSTART_DEPLOYMENT.md](./docs/QUICKSTART_DEPLOYMENT.md) for Docker setup.

---

## 🧭 Documentation

- [Documentation Index](./docs/index.md) — full doc listing
- [API Reference](./docs/api.md)
- [Data Model](./docs/data-model.md)
- [Deployment Guide](./docs/SECURITY_DEPLOYMENT.md)
- [AI Toolkit](./.ai-toolkit/ONBOARDING.md)

---

## 🧪 Testing

```bash
cd backend && python -m pytest --reuse-db -q  # ≥431 tests
cd carbon-frontend && npm test -- --run       # ≥25 tests
```

---

## 📄 License

See [LICENSE](./LICENSE) for details.

---

**For questions, refer to the [docs/](./docs) folder, or contact the maintainers.**
