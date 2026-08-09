# File: accounts/email_config.py
# Phase 1.1 — Dynamically configure Django email from DB-stored EmailConfig.
# Called from AppConfig.ready() at startup.

import logging
from django.conf import settings
from django.core.mail import mail_admins

logger = logging.getLogger('carbon.accounts.email_config')


def configure_email() -> None:
    """Read EmailConfig singleton from DB and apply to Django settings at runtime.
    Safe to call before migrations — falls back to defaults."""
    try:
        from .models import EmailConfig
        cfg = EmailConfig.load()
    except Exception as exc:
        logger.debug("EmailConfig not available (pre-migration?): %s", exc)
        return

    if not cfg.enabled:
        logger.info("Email is disabled via EmailConfig.enabled = False")
        return

    django_settings = cfg.as_django_settings()

    # Apply all email settings
    for key, value in django_settings.items():
        if key == 'ANYMAIL':
            # Merge anymail settings
            current = getattr(settings, 'ANYMAIL', {})
            current.update(value)
            setattr(settings, 'ANYMAIL', current)
        else:
            setattr(settings, key, value)

    logger.info("Email configured: backend=%s from=%s", cfg.backend, cfg.from_email)


def send_test_email(to_email: str) -> dict:
    """Send a test email using current configuration. Returns success/error dict."""
    from django.core.mail import send_mail
    from .models import EmailConfig

    cfg = EmailConfig.load()
    if not cfg.enabled:
        return {'success': False, 'error': 'Email is disabled in configuration'}

    try:
        count = send_mail(
            subject='[Carbon] Email Configuration Test',
            message=(
                'This is a test email from the Carbon Data Trust Platform.\n\n'
                f'Backend: {cfg.backend}\n'
                f'From: {cfg.from_email}\n'
                'If you received this, email delivery is working correctly.\n'
            ),
            from_email=cfg.from_email,
            recipient_list=[to_email],
            fail_silently=False,
        )
        return {'success': True, 'sent': count}
    except Exception as exc:
        logger.exception("Test email failed")
        return {'success': False, 'error': str(exc)}
