# File: accounts/apps.py
# Purpose: Django app configuration for the accounts app.

from django.apps import AppConfig

class AccountsConfig(AppConfig):
    """
    AppConfig for the accounts application.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'