"""Scheduled background tasks for catalog governance.

The platform runs with no Celery/Redis scheduler (see ``dq/jobs.py`` hard
rule), so these are plain callables intended to be invoked by an external
periodic scheduler (e.g. the APScheduler-driven supervisor loop used by
``backend/ai``). Each returns a small summary dict for observability.
"""


def check_freshness_task():
    """Periodic entry point — run one freshness pass across all policies."""
    from .freshness_service import check_freshness
    return check_freshness()
