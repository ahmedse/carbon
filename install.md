# Installation & Setup Guide  
*Carbon Management Platform*

This guide describes how to set up the platform for **development, testing, or demo purposes** on Ubuntu Linux.  
You can use either **Docker** (recommended for most users) or **manual installation**.

---

## Table of Contents

1. [Quickstart (Docker)](#1-quickstart-docker)
2. [Manual Setup (Ubuntu)](#2-manual-setup-ubuntu)
    - [Backend: Django & PostgreSQL](#backend-django--postgresql)
    - [Frontend: React (Vite)](#frontend-react-vite)
3. [Post-Install Checks](#3-post-install-checks)
4. [Common Commands](#4-common-commands)
5. [Troubleshooting](#5-troubleshooting)
6. [Resources & Documentation](#6-resources--documentation)

---

## 1. Quickstart (Docker)

**Recommended for most users!**

### Prerequisites

- [Docker](https://docs.docker.com/engine/install/ubuntu/)
- [Docker Compose](https://docs.docker.com/compose/install/)

### Steps

```bash
git clone https://github.com/your-org/carbon-management-platform.git
cd carbon-management-platform
cp .env.example .env  # Edit if needed, see docs/env.md
docker-compose up --build
```

- The backend (Django API) will be accessible at [http://localhost:8000](http://localhost:8000)
- The frontend (React) at [http://localhost:5173](http://localhost:5173)

#### First-time setup:

Initialize the database and create a superuser:

```bash
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py createsuperuser
```

---

## 2. Manual Setup (Ubuntu)

**Advanced: Use if you want to run backend and frontend directly on your system.**

### Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- PostgreSQL 13+ (or use Docker for DB only)
- Git

### Backend: Django & PostgreSQL

#### 1. Install Node.js (if not already)

```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

#### 2. Install PostgreSQL

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib libpq-dev
```

#### 3. Create Database and User

```bash
sudo -u postgres psql
CREATE DATABASE carbon;
CREATE USER carbon_user WITH PASSWORD 'securepassword123';
GRANT ALL PRIVILEGES ON DATABASE carbon TO carbon_user;
\q
```

#### 4. Django Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Or manually:
# pip install django djangorestframework psycopg2-binary djangorestframework-simplejwt django-cors-headers
```

- Edit `backend/settings.py` or `.env` to use your database credentials:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'carbon',
        'USER': 'carbon_user',
        'PASSWORD': 'securepassword123',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

#### 5. Run Migrations and Create Superuser

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

#### 6. Start Backend

```bash
python manage.py runserver
# API will be at http://localhost:8000
```

---

### Frontend: React (Vite)

```bash
cd ../frontend
npm install
npm run dev
# App will be at http://localhost:5173
```

---

## 3. Post-Install Checks

- Visit [http://localhost:8000/api/](http://localhost:8000/api/) to check the API is running.
- Visit [http://localhost:5173](http://localhost:5173) to check the frontend app.
- Log in with your superuser credentials.

---

## 4. Common Commands

- **Backend shell:**  
  ```bash
  docker-compose exec backend python manage.py shell
  ```
- **Run backend tests:**  
  ```bash
  docker-compose exec backend python manage.py test
  ```
- **Run frontend tests (if present):**  
  ```bash
  cd frontend && npm test
  ```
- **Stop all services:**  
  ```bash
  docker-compose down
  ```

---

## 5. Troubleshooting

- **DB connection errors:**  
  Make sure PostgreSQL is running and credentials are correct.

- **Port conflicts:**  
  Change port numbers in `docker-compose.yml` or `.env` if ports 8000/5173 are in use.

- **Static files:**  
  For production, configure NGINX or serve static files as documented in `docs/deployment.md`.

---

## 6. Resources & Documentation

- **Platform Design & API:** [`docs/`](./docs)
- **Progress & Tasks:** [`progress.md`](./progress.md)
- **Debugging:** [`docs/debug.md`](./docs/debug.md)
- **Environment Variables:** [`docs/env.md`](./docs/env.md)
- **Deployment:** [`docs/deployment.md`](./docs/deployment.md)

---

*For any issues, please check the [progress.md](./progress.md), [docs/](./docs) folder, or contact the maintainers.*
```