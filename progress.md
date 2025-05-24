# Progress & Task Tracker
*Carbon Management Platform*

This file helps the team track project progress at both a high level (phases) and a granular level (tasks).  
**Update this file regularly** as you work!

---

## 🟢 How to Use This File

- **Check a box** `[x]` when you finish a task.
- **Add notes/dates/links** as needed.
- Move items between Kanban sections as they progress.

---

## ☑️ Macro Tasks (Phases)

- [x] Core project scaffolding (backend, frontend)
- [x] Database setup (PostgreSQL, initial schema)
- [ ] RBAC & authentication (backend)
- [ ] Core data models (Project, Period, Module, ModuleData)
- [ ] API endpoints (CRUD, calculations)
- [ ] Frontend layout & theming
- [ ] Frontend authentication & routing
- [ ] Role-based dashboards & pages
- [ ] Initial DevOps (Docker, Compose)
- [ ] CI/CD setup
- [ ] Documentation & API specs
- [ ] MVP testing & QA
- [ ] Deployment (staging/production)
- [ ] Advanced features (multi-tenancy, NoSQL, analytics)
- [ ] **Dynamic Data Collection & Configuration** (NEW)

---

## 📋 Micro Tasks (Granular)

### Backend

- [x] Scaffold Django project & main apps
- [x] Implement User & Role models
- [x] JWT-based authentication
- [ ] Context & RoleAssignment models
- [ ] Project, Period, Module models
- [ ] ModuleData, CalculationResult models
- [ ] CRUD API endpoints
- [ ] RBAC permission checks
- [ ] Calculation endpoint
- [ ] Unit tests for RBAC, models
- [ ] Admin registration for all models
- [ ] Logging/audit trail
- [ ] Seed script for demo data

#### Dynamic Data Collection & Configuration (Backend)

- [ ] **Data Model Enhancements**
  - [x] Create ReadingItemDefinition model
      - [x] name, description, data type, validation rules, required/optional, category, tags, evidence rules, editable flag
  - [x] Create ReadingTemplate model
      - [x] name, description, version, status, assigned contexts, fields (with order), M2M with ReadingItemDefinition
  - [x] Create ReadingEntry model
      - [x] template, template version, context, data (JSON), submitted_by, submitted_at, status, audit log
  - [x] Create EvidenceFile model
      - [x] reading_entry, reading_item, file_path, file_type, uploaded_at, covers_period_start, covers_period_end
  - [ ] Adapt Context, Project, Module models for assignment logic

- [ ] **API Endpoints**
  - [ ] CRUD for ReadingItemDefinition
  - [ ] CRUD for ReadingTemplate (with versioning)
  - [ ] Assign templates to contexts, assign staff
  - [ ] CRUD for ReadingEntry (create, update, submit, retrieve)
  - [ ] Evidence file upload/download (type/size validation)
  - [ ] Fetch assigned tasks/forms per user/context
  - [ ] Calculation/reporting endpoint

- [ ] **RBAC & Permissions**
  - [ ] Admin-only for template/item definition and assignment
  - [ ] Restrict ReadingEntry endpoints by role/context
  - [ ] Restrict EvidenceFile actions
  - [ ] Restrict auditor actions (review, calculation, reporting)

- [ ] **Validation & Evidence Handling**
  - [ ] Dynamic field validation (min/max, units, required, etc.)
  - [ ] Evidence file restrictions (type/size, multi-file, period coverage)
  - [ ] Admin override of validation defaults

- [ ] **Audit & Logging**
  - [ ] Audit log for all actions (template change, data entry, evidence upload, review)
  - [ ] Store before/after states and user info
  - [ ] Reference template version in ReadingEntry

- [ ] **Import/Export**
  - [ ] Manual and CSV import for data/templates
  - [ ] Export (CSV, PDF) of submissions/reports

### Frontend

- [x] Setup Vite+React project
- [x] Material UI integration & theme
- [ ] Base routing & folder structure
- [ ] Login/logout with JWT
- [ ] Store user/role context in state
- [ ] Role-based navigation (sidebar, dashboards)
- [ ] Dashboard home widgets
- [ ] Modules page (list, cards)
- [ ] Data entry forms (skeleton)
- [ ] Toast/snackbar notifications
- [ ] Responsive design for all pages
- [ ] Accessibility (a11y) basics
- [ ] Language/i18n structure

#### Dynamic Data Collection & Configuration (Frontend)

- [ ] **Admin UI**
  - [ ] CRUD for ReadingItemDefinitions (with validation config)
  - [ ] UI for building/assigning ReadingTemplates (add/reorder fields, assign context)
  - [ ] UI for assigning Data Owners
  - [ ] Versioning/audit trail display

- [ ] **Data Owner UI**
  - [ ] Dashboard: assigned data entry tasks per time unit/context
  - [ ] Dynamic form rendering (based on template/context)
  - [ ] Inline field validation
  - [ ] Evidence upload widget (multi-file, period selection, type/size enforcement)
  - [ ] Save draft, submit, restrict edits after deadline

- [ ] **Auditor UI**
  - [ ] Dashboard for reviewing submissions (filter by project/module/branch/period)
  - [ ] Integrated display of submitted data & evidence
  - [ ] Approve/reject/resubmit actions
  - [ ] Calculation/reporting display
  - [ ] Audit trail view

- [ ] **Notifications & Alarms**
  - [ ] System triggers for missing/incomplete submissions
  - [ ] Notification UI for Data Owners/Admins/Auditors

- [ ] **General**
  - [ ] Full RBAC in UI (conditional rendering/actions)
  - [ ] Responsive design for new UIs
  - [ ] Accessibility/i18n for new features

### DevOps

- [x] Dockerize backend & frontend
- [x] Docker Compose for local dev
- [ ] NGINX config (for production)
- [ ] CI/CD pipeline (GitHub Actions, etc.)
- [ ] Deployment scripts & docs
- [ ] Migration scripts for new models
- [ ] Update Docker Compose for dependencies if needed
- [ ] Automated tests for new endpoints/workflows

### Documentation

- [x] Initial README.md
- [x] install.md (setup guide)
- [ ] API documentation (OpenAPI, etc.)
- [ ] Data model/ER diagrams
- [ ] Usage/testing guide
- [ ] Contribution guidelines
- [ ] Update docs with new data collection flows

---

## 🗂️ Kanban Board

### TODO

- RBAC permission checks (backend)
- Calculation endpoint
- CRUD API endpoints
- Data entry forms (frontend)
- Dashboard widgets
- CI/CD pipeline
- API documentation
- NGINX config
- **All new sub-tasks for Dynamic Data Collection & Configuration**

### IN PROGRESS

- ModuleData, CalculationResult models
- Role-based navigation (frontend)
- Responsive design (frontend)
- Any sub-tasks actively being worked on

### DONE

- Project scaffolding
- Docker Compose setup
- User & Role models
- JWT authentication
- Vite+React setup
- Material UI integration
- Any completed sub-tasks for Dynamic Data Collection & Configuration

---

## 🏁 Milestones & Deadlines

| Milestone                         | Target Date | Status      |
|-----------------------------------|-------------|-------------|
| Core setup                        | yyyy-mm-dd  | ✅ Complete |
| Backend MVP                       | yyyy-mm-dd  | ⬜ Pending  |
| Frontend MVP                      | yyyy-mm-dd  | ⬜ Pending  |
| Dockerized local dev              | yyyy-mm-dd  | ✅ Complete |
| Staging deployment                | yyyy-mm-dd  | ⬜ Pending  |
| User testing                      | yyyy-mm-dd  | ⬜ Pending  |
| **Dynamic Data Collection Models**| yyyy-mm-dd  | ⬜ Pending  |
| **Dynamic Data Entry UI MVP**     | yyyy-mm-dd  | ⬜ Pending  |
| **Auditor/Reporting MVP**         | yyyy-mm-dd  | ⬜ Pending  |

*Update with actual dates as your team sets them!*

---

## 📄 Notes / Blockers

- _Add current blockers or issues here (e.g., “Waiting for API spec,” “Need DB migration script”)_

---

## 🔗 References

- [Design docs & diagrams](./docs/)
- [API documentation](./docs/api.md)
- [Install & setup](./install.md)
- [Debugging](./docs/debug.md)

---

*For major updates, please notify the team or open a pull request.*

---

This progress.md is now enhanced for detailed, feature-level, and sub-task-level tracking, following the best practices and structure recommended in your documentation [[1]](https://poe.com/citation?message_id=395400491407&citation=1)[[3]](https://poe.com/citation?message_id=395400491407&citation=3)[[4]](https://poe.com/citation?message_id=395400491407&citation=4)[[5]](https://poe.com/citation?message_id=395400491407&citation=5).