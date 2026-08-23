# File: accounts/platform_config.py
# Dynamically configure general platform settings (e.g. display timezone)
# from the DB-stored GeneralConfig singleton. Called from AppConfig.ready().

import logging

from django.conf import settings

logger = logging.getLogger('carbon.accounts.platform_config')


def configure_platform() -> None:
    """Apply the GeneralConfig singleton to Django settings at runtime.

    Mirrors ``email_config.configure_email``: safe to call before migrations
    (falls back to defaults), and lets admins change the display timezone
    without a code redeploy. Storage stays UTC (USE_TZ) — this only changes
    how times are *rendered* for humans via ``timezone.localtime``.
    """
    try:
        from .models import GeneralConfig

        cfg = GeneralConfig.load()
    except Exception as exc:  # noqa: BLE001 - pre-migration / import failure
        logger.debug("GeneralConfig not available (pre-migration?): %s", exc)
        return

    settings.TIME_ZONE = cfg.timezone
    logger.info("Platform timezone configured: %s", cfg.timezone)
