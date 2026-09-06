"""In-app notifications for correspondence events (Phase OF-5)."""

from .models import Notification


def notify(corr, *, user_ids, type, title, body=''):
    """Create a Notification row for each user id. Best-effort (no raise)."""
    Notification.objects.bulk_create([
        Notification(user_id=uid, correspondence=corr, type=type,
                     title=title, body=body)
        for uid in dict.fromkeys(uid for uid in user_ids if uid)
    ])
