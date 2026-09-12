# Framework Module: FastAPI (async) + SQLAlchemy

**Read this alongside your role file when `project.config.md → BACKEND_FRAMEWORK` is FastAPI.**
App package name, paths, and ports come from `project.config.md` — never hardcode them.

---

## Running the Server (via ops script ONLY)

```bash
# NEVER run uvicorn directly — it hangs the terminal
./manage.sh start             # start detached
./manage.sh logs 100          # check logs (bounded)
./manage.sh status            # confirm it's up
./manage.sh restart           # after code changes
./manage.sh test              # run tests
```

## Config — Always Pydantic Settings
```python
# WRONG — hardcoded
DATABASE_URL = "sqlite:///data/app.db"

# CORRECT — from settings (app package per project.config.md)
from <app>.config import settings
db_url = settings.database_url
```
Every config value comes from settings. Never hardcode ports, paths, or credentials.

## DB Sessions — Always the `get_db` Dependency
```python
from <app>.db.session import get_db

@router.get("/something")
async def something(db: AsyncSession = Depends(get_db)):
    ...
```
Never create raw sessions. Dependency injection manages the lifecycle.

## Auth — Always from `request.state`
```python
@router.get("/something")
async def something(request: Request):
    project_id  = request.state.project_id   # set by AuthMiddleware
    permissions = request.state.permissions
```
Every endpoint scopes to the caller's project. Never expose data across projects.

## Timestamps — Always UTC
```python
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
```

## Testing
```bash
./manage.sh test -v
```
Tests use in-memory SQLite (set by conftest). Never hardcode a test DB path.

## New Domain Modules
Follow the pattern: `models.py`, `schemas.py`, `service.py`, `router.py`.

---

*Source: ~/ai-toolkit/frameworks/fastapi.md — shared across all FastAPI projects*
