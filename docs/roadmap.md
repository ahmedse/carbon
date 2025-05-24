# Roadmap — Carbon Management Platform

This roadmap outlines the phased development and long-term vision for the platform.

---

## Phase 1: MVP Foundation (Est. 2-3 weeks)

- Project scaffolding (Django, React, Docker)
- Core data models: User, Role, Project, Cycle, Module, ModuleData
- RBAC (contextual, basic)
- Basic CRUD APIs and authentication
- Frontend: login, context selection, dashboards (skeleton)
- Docker Compose for local dev
- Initial documentation and diagrams

_Milestone: End-to-end data flow for a single tenant, single project, single period._

---

## Phase 2: Core Features (Est. 4-5 weeks)

- Complete CRUD for all entities
- Role-based dashboards (admin, auditor, data owner)
- Data entry forms, CSV import
- Calculation engine (backend)
- Data visualization with Recharts (frontend)
- Bilingual support (EN/AR structure)
- Auditing/logging core actions
- Initial CI/CD pipeline

_Milestone: Platform ready for internal testing with real data._

---

## Phase 3: Productionization (Est. 2-3 weeks)

- Responsive UI polish (desktop/tablet/mobile)
- Automated tests (backend/unit, frontend/e2e)
- Enhanced error handling and logging
- NGINX reverse proxy setup
- Kubernetes manifests (for future scalability)
- Security hardening
- Documentation and user guides

_Milestone: MVP live on staging/production._

---

## Phase 4: Advanced & Scaling (Est. 5+ weeks, parallel tracks)

- Multi-tenancy (tenant field, scoped queries)
- NoSQL (MongoDB) for dynamic module data (see design docs)
- Advanced dashboards (filters, custom analytics)
- Notifications (in-app, email)
- SSO/MFA (optional)
- IoT data integration
- AI/ML analytics (optional)
- Regulatory/compliance features (audit export, versioning)
- API rate limiting, monitoring, Prometheus/Grafana

_Milestone: Enterprise-ready, scalable product._

---

## Visual Timeline

See: `diagrams/feature-roadmap-gantt.mmd`

---

## Long-Term Vision (Suggested)

- **Marketplace for modules/calculations**
- **White-label deployment for orgs**
- **Integrations with external carbon registries**
- **Role-based mobile app**
- **Sustainability scoring and benchmarking**

---

## How to Use This Roadmap

- Revisit and update after each major milestone.
- Use as a reference for sprint planning and onboarding.
- Keep the `feature-roadmap-gantt.mmd` diagram up to date.

---

*For more details on each phase, see the main [design.md](./design.md) and diagrams folder.*