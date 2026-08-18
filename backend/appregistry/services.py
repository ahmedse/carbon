"""
appregistry/services.py — business logic for the App Registry.

Activation lifecycle rules (used by views + management command):
  * activate   → get-or-create AppActivation, flip on, record actor/timestamps
  * deactivate → non-system apps only; flip off, record actor/timestamps
"""
from django.utils import timezone

from .models import AppActivation, AppManifest


class AppRegistryService:
    """Activation lifecycle for AppManifest records."""

    @staticmethod
    def register_manifest(*, slug, name, version, description='', icon='',
                          entry_route='', required_modules=None,
                          required_capabilities=None, consumed_datasets=None,
                          is_system=False, is_active=True):
        """Declare (or update) an AppManifest + ensure an AppActivation row.

        Idempotent — INSERT-OR-UPDATE on slug. Returns (manifest, created).
        """
        manifest, created = AppManifest.objects.update_or_create(
            slug=slug,
            defaults={
                'name': name,
                'version': version,
                'description': description,
                'icon': icon,
                'entry_route': entry_route,
                'required_modules': required_modules or [],
                'required_capabilities': required_capabilities or [],
                'consumed_datasets': consumed_datasets or [],
                'is_system': is_system,
                'is_active': is_active,
            },
        )
        AppActivation.objects.get_or_create(app=manifest)
        return manifest, created

    @staticmethod
    def activate(app: AppManifest, user=None) -> AppActivation:
        """Activate an app. Idempotent."""
        activation, _ = AppActivation.objects.get_or_create(app=app)
        activation.is_active = True
        activation.deactivated_at = None
        activation.deactivated_by = None
        activation.activated_by = user
        if not activation.activated_at:
            activation.activated_at = timezone.now()
        activation.save(update_fields=[
            'is_active', 'activated_by', 'activated_at',
            'deactivated_at', 'deactivated_by',
        ])
        # Keep the manifest default in sync with the runtime record.
        if not app.is_active:
            app.is_active = True
            app.save(update_fields=['is_active', 'updated_at'])
        return activation

    @staticmethod
    def deactivate(app: AppManifest, user=None) -> AppActivation:
        """Deactivate an app. System apps (is_system=True) are rejected.

        Raises PermissionError for system apps (view returns 400).
        """
        if app.is_system:
            raise PermissionError(
                f"System app '{app.slug}' cannot be deactivated."
            )
        activation, _ = AppActivation.objects.get_or_create(app=app)
        activation.is_active = False
        activation.deactivated_at = timezone.now()
        activation.deactivated_by = user
        activation.save(update_fields=[
            'is_active', 'deactivated_at', 'deactivated_by',
        ])
        if app.is_active:
            app.is_active = False
            app.save(update_fields=['is_active', 'updated_at'])
        return activation

    @staticmethod
    def effective_is_active(app: AppManifest) -> bool:
        """Runtime activation state (activation record wins over manifest)."""
        activation = getattr(app, 'activation', None)
        return activation.is_active if activation else app.is_active
