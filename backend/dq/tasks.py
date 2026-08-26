# dq/tasks.py — Async task entrypoints for DQ profiling (EPH-3A).
#
# ``profile_table_task`` is the task used by the async profile endpoint
# (POST /dq/tables/{id}/profile/run/). The platform runs deterministic DQ jobs
# inline (no Celery worker in dev — see dq/jobs.py hard rule), so when Celery
# is not installed the task degrades to a synchronous call and profiling still
# completes; the endpoint returns 202 + task_id either way.
import logging

logger = logging.getLogger(__name__)

try:  # Celery is an optional dependency (not installed in this project).
    from celery import shared_task as _celery_shared_task
    _HAS_CELERY = True
except ImportError:  # pragma: no cover - optional dependency
    _celery_shared_task = None
    _HAS_CELERY = False


def _profile_table_impl(table_id: int) -> dict:
    """Run profiling via the profiling service and persist profile records."""
    from .profiling_service import profile_table
    return profile_table(table_id)


if _HAS_CELERY:  # pragma: no cover - optional dependency
    profile_table_task = _celery_shared_task(_profile_table_impl)
else:
    def profile_table_task(table_id: int) -> dict:
        return _profile_table_impl(table_id)
