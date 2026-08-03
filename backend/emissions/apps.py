from django.apps import AppConfig


class EmissionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'emissions'

    def ready(self):
        import emissions.signals  # noqa: F401 — register signal handlers
