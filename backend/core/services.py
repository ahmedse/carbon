# File: core/services.py
# Cross-cutting service layer for core app — notifications, etc.
# Core MUST NOT import from emissions or other hosted apps.

from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import Notification

User = get_user_model()


class NotificationService:
    """Service for creating in-app notifications."""

    @staticmethod
    def notify(user, verb, message, link=''):
        """Create a notification for a single user.

        Args:
            user: User instance (or None — silently no-ops)
            verb: str, e.g. 'submitted', 'verified', 'rejected', 'batch_complete'
            message: str, human-readable
            link: str, optional URL to related resource
        """
        if user is None:
            return None
        return Notification.objects.create(
            user=user,
            verb=verb,
            message=message,
            link=link,
        )

    @staticmethod
    def notify_admins(verb, message, link=''):
        """Create notifications for all active admin users.

        Admins = superusers + members of admins_group.
        """
        admin_users = User.objects.filter(
            Q(is_superuser=True)
            | Q(groups__name='admins_group')
        ).distinct()
        notifications = [
            Notification(user=u, verb=verb, message=message, link=link)
            for u in admin_users
        ]
        return Notification.objects.bulk_create(notifications)

    @staticmethod
    def on_period_submitted(period, user):
        """Emit when a reporting period is submitted for verification."""
        msg = f'Period "{period.name}" was submitted for verification by {user.username}.'
        NotificationService.notify_admins(
            verb='submitted', message=msg,
            link=f'/carbon/emissions/periods/{period.id}',
        )

    @staticmethod
    def on_period_verified(period, user):
        """Emit when a reporting period is verified."""
        msg = f'Period "{period.name}" was verified by {user.username}.'
        NotificationService.notify_admins(
            verb='verified', message=msg,
            link=f'/carbon/emissions/periods/{period.id}',
        )

    @staticmethod
    def on_period_rejected(period, user, notes=''):
        """Emit when a reporting period is rejected."""
        detail = f': {notes}' if notes else ''
        msg = f'Period "{period.name}" was rejected by {user.username}{detail}.'
        NotificationService.notify_admins(
            verb='rejected', message=msg,
            link=f'/carbon/emissions/periods/{period.id}',
        )

    @staticmethod
    def on_batch_calculation_complete(period_name, tables_count, calculations_count):
        """Emit when a batch calculation finishes."""
        msg = (
            f'Batch calculation complete for period "{period_name}": '
            f'{calculations_count} calculations across {tables_count} tables.'
        )
        NotificationService.notify_admins(verb='batch_complete', message=msg)
