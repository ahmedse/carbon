# File: accounts/email_config.py
# Phase 1.1 — Dynamically configure Django email from DB-stored EmailConfig.
# Called from AppConfig.ready() at startup.

import logging, os
from django.conf import settings
from django.core.mail import mail_admins

logger = logging.getLogger('carbon.accounts.email_config')


def _configure_from_env() -> bool:
    """Check for SMTP_* environment variables and auto-configure EmailConfig.
    Returns True if env-based config was applied."""
    env_backend = os.environ.get('SMTP_BACKEND', '')
    if not env_backend:
        return False

    try:
        from .models import EmailConfig
        cfg = EmailConfig.load()
        cfg.backend = env_backend
        cfg.host = os.environ.get('SMTP_HOST', cfg.host)
        cfg.port = int(os.environ.get('SMTP_PORT', cfg.port))
        cfg.username = os.environ.get('SMTP_USERNAME', cfg.username)
        cfg.password = os.environ.get('SMTP_PASSWORD', cfg.password)
        cfg.from_email = os.environ.get('SMTP_FROM_EMAIL', cfg.from_email)
        cfg.from_name = os.environ.get('SMTP_FROM_NAME', cfg.from_name)
        cfg.use_tls = os.environ.get('SMTP_USE_TLS', 'true').lower() in ('true', '1', 'yes')
        cfg.use_ssl = os.environ.get('SMTP_USE_SSL', 'false').lower() in ('true', '1', 'yes')
        cfg.enabled = os.environ.get('SMTP_ENABLED', 'true').lower() in ('true', '1', 'yes')
        cfg.save()
        logger.info("EmailConfig auto-configured from SMTP_* env vars")
        return True
    except Exception as exc:
        logger.warning("Failed to apply env-based email config: %s", exc)
        return False


def configure_email() -> None:
    """Read EmailConfig singleton from DB and apply to Django settings at runtime.
    Safe to call before migrations — falls back to defaults.

    Environment variable overrides (SMTP_BACKEND, SMTP_HOST, etc.) are applied
    before the DB config is read, allowing deployment without DB admin access."""
    try:
        from .models import EmailConfig

        # G4: Auto-configure from env vars if SMTP_BACKEND is set
        _configure_from_env()

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
            subject='[Data Trust] Email Configuration Test',
            message=(
                'This is a test email from the Data Trust Platform.\n\n'
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
