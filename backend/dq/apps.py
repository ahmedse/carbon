from django.apps import AppConfig


class DqConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dq'

    def ready(self):
        # Phase 1.6: wire notification signals for DQ violations
        import dq.signals  # noqa: F401
