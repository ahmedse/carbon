"""Tests for ensure_pulse_instance management command.

Verify:
1. First call creates the Instance row.
2. Second call is idempotent (created=False, no duplicate/error).
3. The row id equals resolve_instance_id().
4. Optional --instance override works.
"""

import pytest
from django.core.management import call_command
from django.test import override_settings
from io import StringIO

from ai.instance_registry import resolve_instance_id
from ai.models.core import Instance


@pytest.mark.django_db
class TestEnsurePulseInstance:
    """Idempotent Instance bootstrap tests."""

    def test_first_call_creates_instance_row(self):
        """First call creates the Instance row with correct defaults."""
        # Ensure clean slate
        Instance.objects.all().delete()

        # Run command
        out = StringIO()
        with override_settings(DJANGO_BRAND="nibras"):
            call_command("ensure_pulse_instance", stdout=out)

        output = out.getvalue()
        assert "ensured instance nibras (created=True)" in output

        # Verify row exists with correct fields
        instance = Instance.objects.get(id="nibras")
        assert instance.name == "nibras"
        assert instance.status == "active"
        assert instance.host_db_url == ""
        # display_name should fallback to title-cased instance_id
        assert instance.display_name is not None

    def test_second_call_is_idempotent(self):
        """Second call reports created=False, no duplicate error."""
        # Ensure clean slate
        Instance.objects.all().delete()

        # First call
        out1 = StringIO()
        with override_settings(DJANGO_BRAND="nibras"):
            call_command("ensure_pulse_instance", stdout=out1)

        output1 = out1.getvalue()
        assert "created=True" in output1

        # Second call
        out2 = StringIO()
        with override_settings(DJANGO_BRAND="nibras"):
            call_command("ensure_pulse_instance", stdout=out2)

        output2 = out2.getvalue()
        assert "ensured instance nibras (created=False)" in output2

        # No duplicate rows
        assert Instance.objects.filter(id="nibras").count() == 1

    def test_row_id_equals_resolve_instance_id(self):
        """The created Instance.id equals resolve_instance_id()."""
        # Ensure clean slate
        Instance.objects.all().delete()

        out = StringIO()
        with override_settings(DJANGO_BRAND="carbon"):
            call_command("ensure_pulse_instance", stdout=out)
            expected_id = resolve_instance_id()  # resolved within the brand override → "carbon"

        instance = Instance.objects.get(id=expected_id)
        assert instance.id == expected_id
        assert instance.id == "carbon"

    def test_instance_override_option(self):
        """--instance option overrides resolved instance_id."""
        # Ensure clean slate
        Instance.objects.all().delete()

        out = StringIO()
        # Even though brand is carbon, --instance overrides to "custom"
        with override_settings(DJANGO_BRAND="carbon"):
            call_command("ensure_pulse_instance", instance="custom", stdout=out)

        output = out.getvalue()
        assert "ensured instance custom (created=True)" in output

        # Verify row has the override id
        instance = Instance.objects.get(id="custom")
        assert instance.name == "custom"

    def test_display_name_from_settings(self):
        """display_name uses INSTANCE_NAME from settings."""
        # Ensure clean slate
        Instance.objects.all().delete()

        out = StringIO()
        with override_settings(
            DJANGO_BRAND="nibras",
            INSTANCE_NAME="Nibras People & Payroll",
        ):
            call_command("ensure_pulse_instance", stdout=out)

        instance = Instance.objects.get(id="nibras")
        assert instance.display_name == "Nibras People & Payroll"

    def test_display_name_fallback_to_platform_name(self):
        """display_name falls back to PLATFORM_NAME if INSTANCE_NAME not set."""
        # Ensure clean slate
        Instance.objects.all().delete()

        out = StringIO()
        with override_settings(
            DJANGO_BRAND="carbon",
            INSTANCE_NAME=None,
            PLATFORM_NAME="Carbon Platform",
        ):
            call_command("ensure_pulse_instance", stdout=out)

        instance = Instance.objects.get(id="carbon")
        assert instance.display_name == "Carbon Platform"

    def test_display_name_fallback_to_title_case(self):
        """display_name falls back to title-cased instance_id if no settings."""
        # Ensure clean slate
        Instance.objects.all().delete()

        out = StringIO()
        with override_settings(
            DJANGO_BRAND="nibras",
            INSTANCE_NAME=None,
            PLATFORM_NAME=None,
        ):
            call_command("ensure_pulse_instance", stdout=out)

        instance = Instance.objects.get(id="nibras")
        # Should be "Nibras" (first letter uppercased)
        assert instance.display_name == "Nibras"

    def test_host_api_url_from_settings(self):
        """host_api_url uses DJANGO_API_PREFIX from settings."""
        # Ensure clean slate
        Instance.objects.all().delete()

        out = StringIO()
        with override_settings(
            DJANGO_BRAND="carbon",
            API_PREFIX="/custom-api/v2/",
        ):
            call_command("ensure_pulse_instance", stdout=out)

        instance = Instance.objects.get(id="carbon")
        assert instance.host_api_url == "/custom-api/v2/"

    def test_host_db_url_always_empty(self):
        """host_db_url is always empty (modular monolith)."""
        # Ensure clean slate
        Instance.objects.all().delete()

        out = StringIO()
        with override_settings(DJANGO_BRAND="nibras"):
            call_command("ensure_pulse_instance", stdout=out)

        instance = Instance.objects.get(id="nibras")
        assert instance.host_db_url == ""

    def test_status_always_active(self):
        """status is always 'active'."""
        # Ensure clean slate
        Instance.objects.all().delete()

        out = StringIO()
        with override_settings(DJANGO_BRAND="carbon"):
            call_command("ensure_pulse_instance", stdout=out)

        instance = Instance.objects.get(id="carbon")
        assert instance.status == "active"
