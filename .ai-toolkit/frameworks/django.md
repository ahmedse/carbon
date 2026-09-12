# Framework Module: Django + Django REST Framework

**Read this alongside your role file when `project.config.md → BACKEND_FRAMEWORK` is Django.**
App/module names, paths, and ports come from `project.config.md` — never hardcode them.

---

## Running the Server (via ops script ONLY)

```bash
# NEVER run manage.py runserver directly — it hangs the terminal
./manage.sh start backend       # start detached
./manage.sh logs backend 100    # check logs (bounded)
./manage.sh status              # confirm it's up
./manage.sh restart backend     # after code changes
./manage.sh migrate             # run migrations
./manage.sh shell               # Django shell
```
One-off Django commands: `./manage.sh manage <command>` (e.g. `./manage.sh manage run_inference`).

## Datetimes — Always Timezone-Aware
```python
# WRONG — naive
datetime.now()
datetime(2026, 7, 1)

# CORRECT — aware UTC
from django.utils import timezone
timezone.now()
```
Read `project.config.md → DEFAULT_TIMEZONE` for this project's timezone.

## ORM Performance — List/Aggregate Endpoints
```python
# For ANY endpoint returning many rows carrying JSONFields:
qs = qs.select_related(None)     # drop heavy parent joins
qs = qs.defer(                   # drop unused JSONFields
    'input_snapshot', 'output_snapshot', 'model_output', 'metadata',
)
# Annotate only what you need
qs = qs.annotate(temp=KeyTextTransform('Temperature_C', 'input_snapshot'))
```
Never `select_related()` on models that carry JSONFields — each row deserializes full JSON.

## Service Pattern
```python
class SomeService:
    def __init__(self):
        pass  # no global state

    def execute(self, *args, **kwargs) -> dict:
        # Returns {"success": bool, "data": ..., "error": str | None}
        # NEVER raises uncaught exceptions. NEVER returns None.
        pass
```
Views are THIN: validate → service call → serialize → return Response. Business logic lives in services.

## Migrations
```bash
python manage.py makemigrations
python manage.py showmigrations --plan | grep '\[ \]'  # verify order
python manage.py migrate
```
- NEVER add non-nullable fields without `default=`
- NEVER rename fields used in feature engineering

---

*Source: ~/ai-toolkit/frameworks/django.md — shared across all Django projects*
