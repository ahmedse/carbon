# File: accounts/password_reset_signals.py
# Phase 1.6 — Custom PasswordResetView that fires a notification

from django.contrib.auth import views as auth_views


class NotifyingPasswordResetView(auth_views.PasswordResetView):
    """Extends Django's PasswordResetView to fire an in-app notification
    when a password reset is requested."""

    def form_valid(self, form):
        # Fire notification for the user who requested the reset
        email = form.cleaned_data.get('email', '')
        if email:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(email=email, is_active=True)
                from accounts.models import notify_event, NotificationRule

                # Ensure a default password_reset rule exists
                if not NotificationRule.objects.filter(
                    event_type=NotificationRule.EventType.PASSWORD_RESET, enabled=True
                ).exists():
                    NotificationRule.objects.create(
                        event_type=NotificationRule.EventType.PASSWORD_RESET,
                        min_severity=NotificationRule.Severity.WARNING,
                        channel=NotificationRule.ChannelType.IN_APP,
                        description='Auto-created by password reset view',
                    )

                notify_event(
                    event_type='password_reset',
                    title='Password Reset Requested',
                    body="A password reset was requested for your account. "
                         "If this wasn't you, please contact an administrator.",
                    severity='warning',
                    user=user,
                    category='security',
                )
            except Exception:
                pass  # Never break the reset flow

        return super().form_valid(form)
