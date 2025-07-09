# File: accounts/apps.py
# Django app config for accounts app.

from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = "Accounts and RBAC"