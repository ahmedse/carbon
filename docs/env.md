---

## 3. `docs/env.md`

```markdown
# Environment Variables Reference

Document all environment variables used by the platform.

---

## Backend

| Variable        | Example Value        | Description                  |
|-----------------|---------------------|------------------------------|
| DB_NAME         | carbon              | PostgreSQL DB name           |
| DB_USER         | carbon_user         | PostgreSQL user              |
| DB_PASSWORD     | securepassword123   | PostgreSQL password          |
| DB_HOST         | localhost           | PostgreSQL host              |
| DB_PORT         | 5432                | PostgreSQL port              |
| DJANGO_SECRET_KEY | <your-secret>     | Django cryptographic secret  |
| ALLOWED_HOSTS   | localhost,127.0.0.1 | Allowed hosts for Django     |

## Frontend

| Variable        | Example Value        | Description                  |
|-----------------|---------------------|------------------------------|
| VITE_API_URL    | http://localhost:8000 | Backend API base URL        |

---

*Copy `.env.example` and edit as needed!*