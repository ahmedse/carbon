from django.apps import AppConfig

class DataschemaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dataschema'

    def ready(self):
        # Register signal handlers for search vector updates
        from catalog import search_index  # noqa: F401
        from . import signals  # noqa: F401
