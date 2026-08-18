"""
appregistry/models.py — Phase P3: App Registry (control plane for domain apps).

Declares what domain apps exist, what capabilities and modules they need,
and whether they are active. One deployment = one organisation → the registry
is a flat list of AppManifests with activation state (no multi-tenancy).

Dependency direction: appregistry imports accounts (User) only. No other app
imports appregistry except accounts/ai_scoping.py (read-only: active app slugs
for the AI Scope). Core apps may import appregistry; appregistry must never
import emissions.
"""
import uuid

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class AppManifest(models.Model):
    """Declarative specification for a domain app.

    An AppManifest is declared once (usually via the ``register_app``
    management command) by the app itself. It is the contract between the
    app and the platform.

    required_modules: list of Module.name values this app needs to exist.
    required_capabilities: list of Capability.key values users need to use this app.
    datasets: list of Dataset.slug values this app will access (informational;
              actual access still governed by ScopedRole on dataset.module).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    version = models.CharField(max_length=20)  # semver string e.g. "1.0.0"
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=80, blank=True)  # e.g. "FactoryIcon"
    entry_route = models.CharField(
        max_length=200, blank=True,
        help_text='Frontend React router path e.g. /apps/healthy',
    )
    required_modules = models.JSONField(default=list)
    required_capabilities = models.JSONField(default=list)
    consumed_datasets = models.JSONField(
        default=list,
        help_text='Dataset.slug values this app reads (informational).',
    )
    is_system = models.BooleanField(
        default=False,
        help_text='System apps (emissions) cannot be deactivated.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} v{self.version}"


class AppActivation(models.Model):
    """Records that an AppManifest has been activated in this deployment.

    Deactivating an app hides it from the UI and blocks API access.
    System apps (is_system=True) cannot be deactivated.
    """
    app = models.OneToOneField(AppManifest, on_delete=models.CASCADE,
                               related_name='activation')
    is_active = models.BooleanField(default=True)
    activated_by = models.ForeignKey(User, null=True, blank=True,
                                     on_delete=models.SET_NULL,
                                     related_name='activated_apps')
    activated_at = models.DateTimeField(auto_now_add=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivated_by = models.ForeignKey(User, null=True, blank=True,
                                       on_delete=models.SET_NULL,
                                       related_name='deactivated_apps')

    def __str__(self):
        return f"{self.app.name} — {'active' if self.is_active else 'inactive'}"
