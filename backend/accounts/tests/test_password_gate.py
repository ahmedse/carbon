"""Light password policy and the forced-change gate."""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class LightPasswordPolicyTests(TestCase):
    def test_shared_dev_password_is_accepted(self):
        validate_password("AdminPa_132")

    def test_letter_and_digit_are_required(self):
        with self.assertRaises(ValidationError):
            validate_password("longpassword")
        with self.assertRaises(ValidationError):
            validate_password("short1")


@override_settings(DEBUG=True)
class PasswordChangeGateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="gated", password="AdminPa_132")
        self.user.must_change_password = True
        self.user.save(update_fields=["must_change_password"])
        access = str(RefreshToken.for_user(self.user).access_token)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_other_apis_stop_until_the_password_changes(self):
        blocked = self.client.get(reverse("my-roles"))
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()["code"], "password_change_required")

        changed = self.client.post(
            reverse("change-password"),
            {"current_password": "AdminPa_132", "new_password": "CampusPass1"},
            format="json",
        )
        self.assertEqual(changed.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertTrue(self.user.check_password("CampusPass1"))

        opened = self.client.get(reverse("my-roles"))
        self.assertNotEqual(opened.status_code, 403)
