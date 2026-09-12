"""Regression tests for PULSE P1-01 — ``AI_STORE_BACKEND`` must fail closed.

The store backend is a persistence seam: defaulting to the ephemeral
in-memory store silently drops every durable write in any deployment that
forgets to set ``AI_STORE_BACKEND``. These tests pin the fail-closed contract
on both the settings loader (``_resolve_ai_store_backend``) and
``ai.store.get_store``.

Every environment assertion passes an explicit mapping into the resolver, so
the suite never depends on the ambient shell / pytest process environment.
"""
from __future__ import annotations

import pytest
from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from ai.store import DjangoStore, get_store, reset_store
from config.settings import _resolve_ai_store_backend


@pytest.fixture(autouse=True)
def _clean_store_singleton():
    """Keep the module-level Store singleton from leaking across tests."""
    reset_store()
    yield
    reset_store()


# ── settings loader (fail-closed resolution) ─────────────────────────────


def test_unset_backend_raises():
    with pytest.raises(ImproperlyConfigured):
        _resolve_ai_store_backend({})


def test_blank_backend_raises():
    with pytest.raises(ImproperlyConfigured):
        _resolve_ai_store_backend({"AI_STORE_BACKEND": "   "})


def test_django_backend_is_accepted():
    assert _resolve_ai_store_backend({"AI_STORE_BACKEND": "django"}) == "django"
    with override_settings(AI_STORE_BACKEND="django"):
        assert django_settings.AI_STORE_BACKEND == "django"


def test_inmemory_without_allow_flag_raises():
    with pytest.raises(ImproperlyConfigured):
        _resolve_ai_store_backend({"AI_STORE_BACKEND": "inmemory"})


def test_inmemory_with_pulse_allow_flag_is_accepted():
    resolved = _resolve_ai_store_backend(
        {"AI_STORE_BACKEND": "inmemory", "PULSE_ALLOW_INMEMORY": "1"}
    )
    assert resolved == "inmemory"


def test_unset_is_allowed_under_pytest():
    # Explicit mapping — does not read the real os.environ.
    assert _resolve_ai_store_backend({"PYTEST_CURRENT_TEST": "x"}) == "inmemory"


# ── get_store (never silently degrade to InMemoryStore) ──────────────────


def test_get_store_rejects_unknown_backend():
    with override_settings(AI_STORE_BACKEND="not-a-real-backend"):
        with pytest.raises(ImproperlyConfigured):
            get_store()


def test_get_store_builds_configured_django_backend():
    with override_settings(AI_STORE_BACKEND="django"):
        assert isinstance(get_store(), DjangoStore)
