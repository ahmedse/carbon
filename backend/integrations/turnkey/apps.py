from django.apps import AppConfig


class TurnkeyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'integrations.turnkey'
    verbose_name = 'TurnKey Bridge'
