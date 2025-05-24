# Design Document — Carbon Management Platform

## 1. Overview

The Carbon Management Platform enables organizations to capture, analyze, and report environmental data (carbon, water, electricity, etc.) across projects and reporting cycles.  
It is designed for flexibility, strong RBAC, auditability, and future-proof scaling.

---

## 2. Architecture Overview

**Baseline Tech Stack:**
- Frontend: React (Vite) + Material UI
- Backend: Django + DRF + JWT
- Database: PostgreSQL (MVP), MongoDB (future option)
- Containerization: Docker, Compose
- DevOps: CI/CD, NGINX (prod), Prometheus/Grafana (future)

**Key Concepts:**
- Projects, Cycles (Periods), Modules, ModuleData
- Context-aware RBAC (Role assignments per project/cycle/module)
- Calculation/Reporting
- Audit Logging

**High-Level Diagram:**  
_See: `diagrams/system-architecture.mmd`_

---

## 3. Data Model

- **User:** Identity, roles, and assignments
- **Role:** Permissions list (add_data, calculate, etc.)
- **Project:** Organization’s reporting context
- **Cycle:** Time window (year/quarter), non-overlapping
- **Module:** Data category (Water, Electricity, Vehicles, etc.)
- **ModuleData:** Data point per module/cycle/project
- **CalculationResult:** Output of carbon calculations
- **Context:** Scope for RBAC (global/project/cycle/module)
- **RoleAssignment:** User/role/context mapping

**ER Diagram:**  
_See: `diagrams/entity-relationship.mmd`_

---

## 4. Core Workflows

### 4.1. Admin Flow

- Create project and cycles  
- Define modules  
- Assign roles per context (e.g. Data Owner for Water 2024)  
- Configure initial data

**Diagram:** `diagrams/workflow-admin-project-setup.mmd`

### 4.2. Data Owner Flow

- Select assigned context (project/cycle/module)
- Enter or upload data (form or CSV)
- Review/edit before submission

**Diagram:** `diagrams/workflow-data-entry.mmd`

### 4.3. Auditor Flow

- Review submitted data
- Trigger calculation
- Review calculation results, generate reports

**Diagram:** `diagrams/workflow-auditor-review.mmd`

### 4.4. RBAC Enforcement (all roles)

- All actions checked against context-aware permissions.
- UI and API both enforce.

**RBAC Diagram:** `diagrams/rbac-enforcement.mmd`

---

## 5. API & Integration Outline

- RESTful endpoints for all entities.
- JWT authentication.  
- RBAC enforced at backend (custom permissions).
- Internationalization: API supports field translation (future).

---

## 6. Security & Audit

- Short-lived JWT for all user sessions.
- All sensitive actions logged (see AuditLog model).
- Data validation for all API endpoints.
- (Future) Consider append-only audit storage for compliance.

---

## 7. Extensibility & Future-Readiness

- **NoSQL/MongoDB:** For scaling flexible data, see `diagrams/nosql-data-model.mmd`
- **Multi-tenancy:** Add tenant field to all models; scope queries by tenant.
- **IoT Integration:** Plan APIs for real-time ingest (future).
- **Advanced Analytics:** Build on data model with BI/ML integration.
- **Bilingual/RTL Support:** React-i18next, modeltranslation (MVP: structure only).

---

## 8. Diagrams Index

- `diagrams/system-architecture.mmd` — High-level system components
- `diagrams/entity-relationship.mmd` — Data model/ERD
- `diagrams/workflow-admin-project-setup.mmd` — Project/cycle/module setup
- `diagrams/workflow-data-entry.mmd` — Data entry (owner)
- `diagrams/workflow-auditor-review.mmd` — Data review/calculation (auditor)
- `diagrams/rbac-enforcement.mmd` — RBAC enforcement
- `diagrams/nosql-data-model.mmd` — NoSQL/MongoDB model (future)
- `diagrams/feature-roadmap-gantt.mmd` — Roadmap timeline

---

## 9. Best Practices

- Always enforce RBAC both frontend and backend.
- Use migrations for all schema changes.
- Document all endpoints and workflows.
- Keep diagrams up to date as the system evolves.

---

*For implementation specifics, see backend and frontend README files.*