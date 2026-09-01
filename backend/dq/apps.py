from django.apps import AppConfig


class DqConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dq'

    def ready(self):
        # Phase 1.6: wire notification signals for DQ violations
        import dq.signals  # noqa: F401

        # Wave D1 (Pulse 0.2): presence-driven progress. Register the DQ
        # refresher so the operations SSE stream advances in-flight DQ jobs
        # (polling Pulse) and streams their narrated progress frames.
        from ai.ops_progress import register_progress_refresher
        from dq.jobs import refresh_active_pulse_jobs

        register_progress_refresher(refresh_active_pulse_jobs)
