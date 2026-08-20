from django.apps import AppConfig


class HealthyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'healthy'
    verbose_name = 'Healthy Foods Factory'

    def ready(self):
        # Register HealthyDomainAI with the platform domain registry.
        # ``register_domain`` is idempotent (guarded by has_domain), so this is
        # safe to run on every Django startup and under autoreload.
        from . import domain_ai  # noqa: F401
