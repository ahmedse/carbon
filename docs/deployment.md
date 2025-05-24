# Deployment Guide — Carbon Management Platform

Instructions for deploying the platform to production/staging environments.

---

## 1. Prerequisites

- Ubuntu server with Docker & Docker Compose
- Domain name (for production)
- NGINX (as reverse proxy)
- SSL certificates (Let's Encrypt recommended)

---

## 2. Steps

1. Clone the repository to `/opt/carbon`
2. Edit the `.env` file with production credentials
3. Configure PostgreSQL (see [install.md](../install.md))
4. Start services:
    ```bash
    docker-compose up -d --build
    ```
5. Run migrations and create superuser:
    ```bash
    docker-compose exec backend python manage.py migrate
    docker-compose exec backend python manage.py createsuperuser
    ```
6. Configure NGINX (see sample config in this file)
7. Set up SSL

---

## 3. NGINX Sample Config

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5173;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 3. Security
Ensure ports 5173 and 8000 are not exposed to the public.
Use strong passwords and secrets.
Regularly back up your database.