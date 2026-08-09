# File: accounts/apps.py
# Django app config for accounts app.

import warnings
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = "Accounts and RBAC"

    def ready(self):
        """Configure email backend from DB-stored EmailConfig at startup."""
        try:
            from .email_config import configure_email
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    'ignore',
                    message=r'Accessing the database during app initialization',
                    category=RuntimeWarning,
                )
                configure_email()
        except Exception:
            pass  # Pre-migration / import failures are non-fatal