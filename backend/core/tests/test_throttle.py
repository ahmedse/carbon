"""
EPH-5B — Rate limiting tests.

Covers the per-minute throttle complements (``user_minute`` / ``anon_minute``),
the scoped AI and heavy throttles, and the new ``DEFAULT_THROTTLE_RATES``
entries. Throttle buckets live in Django cache, so every test clears it in
``setUp`` to prevent cross-test leakage.

The conftest fixtures (``api_client`` / ``create_user`` / ``get_token_for_user``)
are pytest-only, so this TestCase reimplements the same helpers locally.

Note on rates: ``SimpleRateThrottle.THROTTLE_RATES`` is a class attribute
snapshot taken at import time, so ``override_settings(REST_FRAMEWORK=...)``
cannot change the effective rate at test time. The behavioral tests therefore
patch the class attribute with ``mock.patch.object`` — the documented DRF way
to drive 429s in tests.
"""
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.throttling import (
    AIRateThrottle,
    AnonMinuteRateThrottle,
    HeavyRateThrottle,
    UserMinuteRateThrottle,
)


def _patched_rates(**overrides):
    """THROTTLE_RATES snapshot with the given scope(s) overridden."""
    base = dict(UserMinuteRateThrottle.THROTTLE_RATES)
    base.update(overrides)
    return base


class ThrottleTestCase(TestCase):
    """Rate-limit behavior for the global and scoped throttle classes."""

    def setUp(self):
        # Throttle buckets live in Django cache — never leak between tests.
        cache.clear()
        self.client = APIClient()

    def _create_user(self, username='throttle_user', password='pass'):
        return get_user_model().objects.create_user(username=username, password=password)

    def _token_for(self, user):
        return str(RefreshToken.for_user(user).access_token)

    @mock.patch.object(
        UserMinuteRateThrottle,
        'THROTTLE_RATES',
        _patched_rates(user_minute='1/minute'),
    )
    def test_user_throttle_429_with_retry_after(self):
        """Per-user per-minute throttle trips after the allowed burst."""
        user = self._create_user('user_throttle')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self._token_for(user)}')

        first = self.client.get('/carbon-api/catalog/assets/')
        self.assertEqual(first.status_code, 200)

        second = self.client.get('/carbon-api/catalog/assets/')
        self.assertEqual(second.status_code, 429)
        self.assertIn('Retry-After', second)
        self.assertTrue(second['Retry-After'].isdigit())

    @mock.patch.object(
        AnonMinuteRateThrottle,
        'THROTTLE_RATES',
        _patched_rates(anon_minute='1/minute'),
    )
    def test_anon_throttle_triggers_at_lower_rate(self):
        """Anonymous per-minute throttle trips at a lower rate.

        Uses the JWT refresh endpoint (no ``throttle_classes`` override), so
        the global defaults — including ``AnonMinuteRateThrottle`` — apply to
        anonymous traffic. The bogus refresh token still passes through
        throttling and fails authentication (401) on the first request.
        """
        payload = {'refresh': 'bogus-token'}
        first = self.client.post('/carbon-api/token/refresh/', payload, format='json')
        self.assertEqual(first.status_code, 401)

        second = self.client.post('/carbon-api/token/refresh/', payload, format='json')
        self.assertEqual(second.status_code, 429)
        self.assertIn('Retry-After', second)
        self.assertTrue(second['Retry-After'].isdigit())

    def test_ai_throttle_wired(self):
        """AIRateThrottle is wired onto the AI workspace viewset."""
        from ai.workspace_api import WorkspaceConversationViewSet

        self.assertEqual(WorkspaceConversationViewSet.throttle_classes, [AIRateThrottle])

    def test_heavy_throttle_wired(self):
        """HeavyRateThrottle is wired onto the heavy import/export viewsets."""
        from importexport.views import ExportProjectViewSet, ImportJobViewSet

        self.assertEqual(ExportProjectViewSet.throttle_classes, [HeavyRateThrottle])
        self.assertEqual(ImportJobViewSet.throttle_classes, [HeavyRateThrottle])

    def test_default_rates_present(self):
        """The new per-minute/scoped rates exist in DEFAULT_THROTTLE_RATES."""
        rates = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']
        self.assertEqual(rates['user_minute'], '1000/min')
        self.assertEqual(rates['anon_minute'], '60/min')
        self.assertEqual(rates['ai'], '60/min')
        self.assertEqual(rates['heavy'], '10/min')
