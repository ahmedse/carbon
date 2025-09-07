graph LR
  subgraph Users
    Admin
    DataOwner["Data Owner"]
    Auditor
  end
  Frontend[Frontend (React, MUI)]
  Backend[Backend (Django, DRF, JWT)]
  DB[(PostgreSQL / MongoDB)]
  CI[CI/CD]
  NGINX[NGINX (Production)]
  Monitoring[Prometheus/Grafana (Future)]

  Admin -- uses --> Frontend
  DataOwner -- uses --> Frontend
  Auditor -- uses --> Frontend
  Frontend -- REST API --> Backend
  Backend -- ORM / ODM --> DB
  Backend -- serves --> NGINX
  CI -- deploys --> Backend
  NGINX -- serves --> Frontend
  Backend -- metrics --> Monitoring