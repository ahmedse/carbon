# Debugging & Troubleshooting Guide

This file documents common errors, debugging tips, and support commands for the Carbon Management Platform.

---

## 1. Backend

### Common Commands

- Start shell:  
  `python manage.py shell`

- List users:  
  ```python
  from accounts.models import User
  User.objects.all()

Test JWT:
```bash
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin1","password":"your-password"}'
```

Common Issues
Database connection errors:

Check settings.py DB config and that PostgreSQL is running.
Migrations:

Run: python manage.py makemigrations && python manage.py migrate
2. Frontend
Dev server not starting:

Check Node.js version, run npm install, then npm run dev
Console errors:

Use browser DevTools, check API URLs in .env
3. Docker
Backend/DB not starting:

Run docker-compose logs backend or docker-compose logs db
Check port conflicts.
To restart everything:

```bash
docker-compose down
docker-compose up --build
```