# File: accounts/apps.py
# Django app config for accounts app.

import warnings
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = "Accounts and RBAC"

    def ready(self):
        """Configure email + platform settings from DB singletons at startup."""
        try:
            from .email_config import configure_email
            from .platform_config import configure_platform
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    'ignore',
                    message=r'Accessing the database during app initialization',
                    category=RuntimeWarning,
                )
                configure_email()
                configure_platform()
        except Exception:
            pass  # Pre-migration / import failures are non-fatal