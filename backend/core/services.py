# File: core/services.py
# Cross-cutting service layer for core app — notifications, etc.
# Core MUST NOT import from emissions or other hosted apps.

from .models import Notification


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
