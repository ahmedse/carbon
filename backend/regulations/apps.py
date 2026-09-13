from django.apps import AppConfig


class RegulationsConfig(AppConfig):
    name = 'regulations'
    verbose_name = 'Regulations Audit Engine'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        # Domain apps register their evaluators via their own AppConfig.ready().
        # Nothing to import here — the registry is populated by the domain apps.
        pass
