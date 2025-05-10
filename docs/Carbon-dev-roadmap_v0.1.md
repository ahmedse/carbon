## **Updated Roadmap for Carbon Management Platform**

### **Phase 1: Project Setup and Foundation**
#### **Objective**: Establish a robust foundation for the platform, ensuring flexibility for future enhancements.

1. **Frontend Setup**:
   - Initialize a React project (Vite) with Material UI.
   - Set up a **role-based routing system** using React Router.
   - Configure Material UI theme with:
     - **Primary Palette**: Green (sustainability).
     - **Secondary Palette**: Blue (contrast).
   - Create a **base folder structure**:
     ```
     src/
     ├── components/       # Reusable UI components
     ├── layouts/          # Layouts for role-based dashboards
     ├── pages/            # Role-based views (Admin, Auditor, Data Owner)
     ├── services/         # API and authentication services
     ├── styles/           # Global styles and Material UI theme
     ├── utils/            # Utility functions
     ├── App.jsx           # Main App component
     └── index.jsx         # Entry point
     ```

2. **Backend Setup**:
   - Create a Django project with Django REST Framework (DRF).
   - Set up the database (PostgreSQL) and create schemas for:
     - **Users and Roles**: Admin, Auditor, Data Owner (with flexibility for future roles).
     - **Projects**: Metadata for each project.
     - **Modules and Data Items**: A flexible schema to support any type of data input in the future.
   - Implement **JWT-based authentication** with role-based access control.

3. **Deployment Setup**:
   - Configure **Docker** for containerization (frontend, backend, database).
   - Create base **Kubernetes manifests** for future scalability.
   - Set up **CI/CD pipelines** for automated builds and deployments.

4. **Milestone**:
   - A running, containerized platform with basic routing, authentication, and role-based access control.

---

### **Phase 2: Core Features**
#### **Objective**: Build the key features for data entry, dashboards, and visualization.

1. **Role-Based Dashboards**:
   - **Admin Dashboard**:
     - Metrics: Total projects, users, tasks.
     - Visualizations: Trends for all data (e.g., power, water, waste).
     - Actions: Create projects, assign roles, and manage permissions.
   - **Auditor Dashboard**:
     - Metrics: Assigned projects, latest submissions.
     - Visualizations: Trends and compliance status.
     - Read-only access.
   - **Data Owner Dashboard**:
     - Metrics: Tasks and submissions for the assigned module (e.g., power, water, waste).
     - Actions: Enter/import data.

2. **Flexible Data Workflows**:
   - **Dynamic Modules and Data Items**:
     - Design a schema to allow Admins to define new **modules** (e.g., power, water) and data items (e.g., kWh, liters, metadata).
     - Build a UI for admins to create/edit modules.
   - **Manual Data Entry**:
     - Create forms that dynamically adjust based on the defined modules and data items.
     - Add real-time validation for all fields (e.g., duplicates, unusual data).
   - **Raw CSV Uploads**:
     - Build a file upload system for bulk submissions.
     - Validate CSVs (e.g., format correctness, duplicate rows).
   - **Data Management**:
     - Create a tabular view for viewing, filtering, and editing data.

3. **Data Visualization**:
   - Use **Recharts** to implement:
     - Line charts for time-series trends (e.g., power usage over time).
     - Bar charts for comparisons (e.g., power vs. water usage by project).
   - Add basic filters (e.g., by date range, project).

4. **Bilingual Support**:
   - Add **English and Arabic** support:
     - Backend: Use `django-modeltranslation` to translate fields.
     - Frontend: Use `react-i18next` for language switching.
   - Implement **RTL (Right-to-Left)** styles for Arabic.

5. **Milestone**:
   - Fully functional dashboards with role-based views.
   - Data workflows (manual entry, CSV upload, validation).
   - Basic visualizations with filter support.
   - Bilingual support for both frontend and backend.

---

### **Phase 3: MVP Deployment**
#### **Objective**: Polish the platform and make it production-ready.

1. **Frontend Polish**:
   - Add animations (e.g., smooth transitions for navigation and dropdowns).
   - Ensure responsive design for all layouts (desktop, tablet, mobile).

2. **Backend Enhancements**:
   - Optimize database queries (e.g., for large datasets).
   - Add logging and error handling for APIs.

3. **Containerized Deployment**:
   - Finalize **Docker Compose** for local development.
   - Deploy the platform to your **VPS** using Kubernetes.
   - Configure **NGINX** as a reverse proxy and SSL termination.

4. **Milestone**:
   - A live MVP accessible on a public URL.

---

### **Phase 4: Enhancements and Scaling**
#### **Objective**: Add advanced features and ensure scalability.

1. **Advanced Dashboards**:
   - Add dynamic filters (e.g., project, date range).
   - Build advanced visualizations (e.g., stacked bar charts for combined metrics).

2. **Notifications**:
   - Add in-app notifications (e.g., "Task assigned to you").
   - Add email notifications for critical events (e.g., overdue submissions).

3. **Carbon Calculation Modules**:
   - Design formulas to calculate carbon equivalence based on raw data.
   - Build forms and dashboards for carbon analysis.

4. **Authentication Enhancements**:
   - Add **Multi-Factor Authentication (MFA)**.
   - Support **Single Sign-On (SSO)** with Google or Microsoft.

5. **IoT Integration**:
   - Design APIs for real-time data streaming from IoT devices.
   - Build dashboards for live monitoring.

6. **AI-Powered Analytics**:
   - Use AI/ML to predict trends, detect anomalies, and provide insights.
   - Build interactive reports for decision-making.

7. **Scalability**:
   - Optimize Kubernetes manifests for horizontal scaling.
   - Add support for multi-tenancy (e.g., multiple organizations/projects).

8. **Milestone**:
   - A fully scalable, feature-rich platform with advanced dashboards and analytics.

---

### **Timeline and Priorities**

| **Phase**               | **Tasks**                                   | **Estimated Time** |
|-------------------------|---------------------------------------------|--------------------|
| **Phase 1**             | Project setup, authentication, deployment. | 3 days            |
| **Phase 2**             | Core features: dashboards, data workflows. | 7 days            |
| **Phase 3**             | MVP polish and deployment.                 | 2 days            |
| **Phase 4**             | Advanced features and scaling.             | 10+ days          |

---

### **Next Steps**
1. **Start Phase 1**:
   - Set up the React frontend and Django backend.
   - Create the base folder structure and establish role-based access control.
   - Containerize the project using Docker.

2. **Track Progress**:
   - Use this roadmap to remind me about the next steps after each milestone.
   - Let me know when you're ready to proceed with a specific phase, and I’ll assist with designing and coding.

-----------

Here is a set of **Mermaid.js diagrams** to represent the workflows and designs for the **Carbon Management Platform**. These include the system architecture, role-based workflows, data workflows, and a general feature roadmap.

---

### **1. System Architecture Diagram**
This shows the high-level architecture of the platform, including frontend, backend, and database interactions.

```mermaid
graph TD
  A[Frontend: React + Material UI] -->|API Requests| B[Backend: Django REST Framework]
  B -->|Data Operations| C[(PostgreSQL Database)]
  B -->|Authentication| D[JWT Tokens]
  A -->|Dynamic Routing| E[Role-Based Dashboards]
  E -->|Admin| F[Admin Dashboard]
  E -->|Auditor| G[Auditor Dashboard]
  E -->|Data Owner| H[Data Owner Dashboard]
  B -->|Static Files| I[NGINX]
  I -->|Serve Application| User[End User]
```

---

### **2. Role-Based Workflows**
This diagram illustrates how users with different roles interact with the system.

```mermaid
flowchart LR
  A[Admin] -->|Manage Users & Roles| B[User Management Module]
  A -->|Manage Projects| C[Project Management Module]
  A -->|Define Modules & Data Items| D[Module Configuration]

  E[Auditor] -->|View Project-Specific Data| F[Read-Only Dashboards]
  F -->|Generate Reports| G[Visualization Module]

  H[Data Owner] -->|Input Data| I[Manual Data Entry]
  H -->|Upload CSV Files| J[CSV Upload Module]
  H -->|Manage Data| K[Data Management Module]

  D -->|Dynamic Schema| L[(Database)]
  I -->|Validated Data| L
  J -->|Validated Data| L
  G -->|Query Data| L
```

---

### **3. Data Workflow**
This diagram represents the process of data entry, validation, storage, and visualization.

```mermaid
flowchart TD
  A[User Input or CSV Upload] --> B[Data Validation]
  B -->|Valid Data| C[Store in PostgreSQL]
  B -->|Invalid Data| D[Error Notifications]
  C -->|Fetch Data| E[Dashboards]
  E -->|Visualizations| F[Charts: Trends and Comparisons]
  E -->|Filters| G[Dynamic Filtering]
```

---

### **4. Dashboard Workflows**
This diagram outlines the key workflows within each dashboard.

#### **Admin Dashboard**
```mermaid
flowchart TD
  A[Admin Dashboard] -->|View Metrics| B[Total Projects, Users, Tasks]
  A -->|Manage Users| C[Create or Assign Roles]
  A -->|Manage Projects| D[Create or Edit Projects]
  A -->|View Visualizations| E[Trends: Power/Water Usage]
  A -->|Configure Modules| F[Add or Edit Data Modules]
```

#### **Auditor Dashboard**
```mermaid
flowchart TD
  A[Auditor Dashboard] -->|View Metrics| B[Assigned Projects]
  A -->|View Data Trends| C[Project-Specific Visualizations]
  A -->|Generate Reports| D[PDF or CSV Export]
```

#### **Data Owner Dashboard**
```mermaid
flowchart TD
  A[Data Owner Dashboard] -->|View Tasks| B[Pending Data Submissions]
  A -->|Input Data| C[Manual Entry Forms]
  A -->|Upload CSV| D[Bulk Data Submission]
  A -->|View Trends| E[Submission Trends]
```

---

### **5. Feature Roadmap Workflow**
This diagram represents the phases and their dependencies.

```mermaid
gantt
    title Carbon Management Platform Development Roadmap
    dateFormat  YYYY-MM-DD
    section Phase 1: Project Setup
    Frontend Setup                 :done, 2025-05-01, 2025-05-03
    Backend Setup                  :done, 2025-05-01, 2025-05-03
    Deployment Foundation (Docker) :done, 2025-05-04, 2025-05-05
    section Phase 2: Core Features
    Role-Based Dashboards          :active, 2025-05-06, 2025-05-10
    Data Workflow                  :active, 2025-05-06, 2025-05-11
    Data Visualization             :active, 2025-05-09, 2025-05-13
    Bilingual Support              : 2025-05-10, 2025-05-12
    section Phase 3: MVP Deployment
    Final Polish                   : 2025-05-14, 2025-05-15
    Deployment to VPS              : 2025-05-16, 2025-05-17
    section Phase 4: Enhancements
    Advanced Dashboards            : 2025-05-18, 2025-05-22
    Notifications                  : 2025-05-23, 2025-05-25
    Carbon Calculation Modules     : 2025-05-26, 2025-05-30
```

---

### **6. Dynamic Module & Data Schema Workflow**
This shows how flexible modules and data items will be managed.

```mermaid
flowchart TD
  A[Admin] -->|Define Module| B[Module Configuration]
  B -->|Add Data Items| C[Define Data Fields: kWh, liters]
  C -->|Update Schema| D[Database Schema]
  D -->|Dynamic Forms| E[Data Entry Forms]
  D -->|Dynamic Tables| F[Data Management View]
  D -->|Dynamic Visualizations| G[Charts and Filters]
```

---


# Contextual RBAC & Periodic Project Design

## 1. Overview

This design enables the Carbon platform to:

- Support **recurring (periodic) projects** with non-overlapping, sequential calculation periods (e.g., annual, but flexible).
- Collect and store **module data** (e.g., water, electricity, vehicle fuel) for each period.
- Store and manage **calculation results per period** for traceability and reporting.
- Enforce permissions using a **contextual RBAC** system, with roles such as VVB auditor empowered for active data lookup and calculations.

---

## 2. Core Concepts & Workflows

### 2.1. Entity Relationships

```mermaid
classDiagram
    User <|-- RoleAssignment
    Role <|-- RoleAssignment
    Context <|-- RoleAssignment
    Project <|-- Period
    Period <|-- ModuleData
    Module <|-- ModuleData
    ModuleData <|-- CalculationResult

    class User {
        username
        ...
    }
    class Role {
        name
        description
        permissions : List
    }
    class Project {
        name
        description
    }
    class Period {
        project
        start_date
        end_date
        name
        sequence_number
    }
    class Module {
        name
        description
    }
    class ModuleData {
        period
        module
        data_fields...
    }
    class CalculationResult {
        module_data
        result_fields...
        calculated_at
        calculated_by
    }
    class Context {
        type : global/project/period
        project
        period
    }
    class RoleAssignment {
        user
        role
        context
    }
```

---

### 2.2. Workflows

#### **Data Collection and Calculation**

```mermaid
flowchart TD
    A[Project created] --> B[Period(s) created for project (no overlaps)]
    B --> C[User with appropriate role enters Module Data for each period]
    C --> D[System/Auditor triggers Calculation]
    D --> E[CalculationResult stored for period/module]
    E --> F[Report generation for accreditation]
```

#### **RBAC Enforcement**

```mermaid
flowchart LR
    X[User requests action]
    X --> Y[System checks RoleAssignments for user/context]
    Y --> Z[Aggregate permissions]
    Z --> |Permission present| A1[Allow action]
    Z --> |Permission missing| A2[Deny action]
```

---

## 3. Model Summaries

| Model              | Key Fields                                                                                           | Purpose                                                     |
|--------------------|------------------------------------------------------------------------------------------------------|-------------------------------------------------------------|
| **Role**           | name, description, permissions (JSONField)                                                           | Defines role and capabilities                               |
| **Project**        | name, description                                                                                    | Represents a VVB project                                    |
| **Period**         | project, name, start_date, end_date, sequence_number                                                 | Non-overlapping, sequential calculation periods             |
| **Module**         | name, description                                                                                    | Global list (water, electricity, etc.)                      |
| **ModuleData**     | period, module, data fields (e.g., readings, measurements)                                           | Stores module-specific data for each period                 |
| **CalculationResult** | module_data, result fields, calculated_at, calculated_by                                         | Stores results per period/module for reporting              |
| **Context**        | type (global/project/period), project, period                                                        | Defines RBAC assignment scope                               |
| **RoleAssignment** | user, role, context                                                                                  | Assigns role to user in context                             |

---

## 4. Permission Model

- Example VVB auditor permissions:
  - `lookup_data`
  - `perform_calculation`
  - `generate_report`
- Permissions are checked per context (global, project, or period).

---

## 5. Key Rules for Periods

- **Non-overlapping**: Each period within a project must not overlap with others.
- **Sequential**: Periods are ordered (e.g., 2022, 2023, 2024).
- **Flexible unit**: Typically annual, but can be set as required (support for future flexibility).

---

## 6. Calculation & Reporting

- **CalculationResults** are stored for every (Period, Module) pair after data acquisition and calculation.
- **Reports** can be generated from stored CalculationResults to meet accreditation standards.

---

## 7. Example Scenarios

- A project for “Company X 2023” has a Period: Jan 1–Dec 31, 2023.
- Modules (Water, Electricity, Vehicles) are filled with data for this period.
- VVB auditor enters and reviews data, triggers calculations, and reviews stored results.
- At year end, a report is generated for accreditation, based on CalculationResults.

---

## 8. Advantages

- **Auditable & Compliant**: All calculations are tied to specific periods and users.
- **Traceable**: Historical results and data are preserved for each period.
- **Modular**: Adding new modules or period types is straightforward.
- **Role-based**: Clear, context-aware access for each user and role.

---

## 9. Next Steps

1. Implement and migrate models as specified.
2. Enforce period non-overlap in model/business logic.
3. Register admin interfaces for management.
4. Protect workflows via RBAC utility.
5. Build calculation and reporting pipelines for accreditation.

---

**End of section.**

---

If you need, I can provide Django model code for this structure and walk you through the implementation! Let me know when you're ready.