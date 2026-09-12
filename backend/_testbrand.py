"""Pytest early-load plugin: pin the test suite to the Carbon (aastmt) brand.

The AI layer is brand-aware (``ai/instance_registry.py`` resolves
``DJANGO_BRAND`` -> instance/app), and the existing test suite asserts
Carbon-domain behavior (DQ, emissions, catalog, "carbon" app defaults). The dev
``backend/.env`` sets ``DJANGO_BRAND=nibras``.

pytest-django force-imports Django settings in its ``pytest_load_initial_conftests``
hook — which runs *before* any ``conftest.py`` module body is executed. So this
override must live in a ``-p`` plugin (imported during ``Config._preparse``,
before that hook). ``load_dotenv(override=False)`` in ``config/settings.py`` then
leaves our value alone. Nibras behavior is exercised separately via
``override_settings(DJANGO_BRAND=...)`` in dedicated tests.

The same ordering applies to ``AI_STORE_BACKEND`` (PULSE P1-01): settings now
fails closed if it is unset, but ``PYTEST_CURRENT_TEST`` is not yet defined when
pytest-django imports settings. Pin the durable backend here so the suite boots
even in CI without a ``backend/.env``. Tests may still override it per case.
"""
import os

os.environ.setdefault("DJANGO_BRAND", "aastmt")
# Fail-closed settings require a durable store backend; `.env` is not present in
# CI, so pin it before Django settings are force-imported (PULSE P1-01).
os.environ.setdefault("AI_STORE_BACKEND", "django")
