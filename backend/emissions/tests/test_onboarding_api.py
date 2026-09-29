"""O1 onboarding HTTP surface (read-only GET)."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

User = get_user_model()


class OnboardingO1APITests(APITestCase):
    def setUp(self):
        self.url = reverse("carbon:onboarding-o1")
        self.user = User.objects.create_user(username="o1_reader", password="unused")

    def test_unauthenticated_is_unauthorized(self):
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, (401, 403))

    @override_settings(DJANGO_BRAND="nibras")
    def test_nibras_brand_is_forbidden(self):
        # O1-SEC-BRAND — nibras must not reach carbon onboarding
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403)
        assert resp.status_code == 403
        body = resp.json()
        detail = body.get("detail") or body.get("message") or ""
        self.assertTrue(
            "Carbon" in detail or "not enabled" in detail,
            detail,
        )

    @override_settings(DJANGO_BRAND="aastmt")
    def test_aastmt_authenticated_is_read_only(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["writes"])
        self.assertEqual(data["benchmark"], "O1")
