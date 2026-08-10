# File: accounts/tests/test_phase1_6_notifications.py
# Phase 1.6 — Notification system tests

import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.conf import settings

from accounts.models import UserAlert, NotificationChannel, NotificationRule, notify_event

User = get_user_model()


@pytest.mark.django_db
class TestUserAlertModel:
    def test_create_alert(self, create_user):
        user = create_user("alice")
        alert = UserAlert.objects.create(
            user=user,
            title="Test Alert",
            body="This is a test",
            category=UserAlert.Category.SYSTEM,
        )
        assert alert.title == "Test Alert"
        assert alert.is_read is False
        assert str(alert).startswith("system:")

    def test_alerts_ordered_by_date(self, create_user):
        user = create_user("alice")
        a1 = UserAlert.objects.create(user=user, title="First")
        a2 = UserAlert.objects.create(user=user, title="Second")
        alerts = list(UserAlert.objects.filter(user=user))
        assert alerts[0].title == "Second"  # newest first
        assert alerts[1].title == "First"


@pytest.mark.django_db
class TestNotificationChannel:
    def test_default_channel(self, create_user):
        user = create_user("bob")
        channel, created = NotificationChannel.objects.get_or_create(user=user)
        assert channel.channel_type == NotificationChannel.ChannelType.IN_APP
        assert channel.enabled is True

    def test_user_has_one_channel(self, create_user):
        user = create_user("bob")
        NotificationChannel.objects.create(user=user)
        with pytest.raises(Exception):
            NotificationChannel.objects.create(user=user)  # OneToOne


@pytest.mark.django_db
class TestNotificationRule:
    def test_create_rule(self, create_user):
        rule = NotificationRule.objects.create(
            event_type=NotificationRule.EventType.DQ_VIOLATION,
            min_severity=NotificationRule.Severity.WARNING,
            description="Notify on DQ failures",
        )
        assert str(rule)
        assert rule.enabled is True

    def test_rule_str_contains_event_type(self, create_user):
        rule = NotificationRule.objects.create(
            event_type=NotificationRule.EventType.SYSTEM_ALERT,
        )
        assert "System Alert" in str(rule)


@pytest.mark.django_db
class TestNotifyEventFunction:
    def test_notify_single_user(self, create_user):
        user = create_user("charlie")
        NotificationRule.objects.create(
            event_type=NotificationRule.EventType.PASSWORD_RESET,
            min_severity=NotificationRule.Severity.WARNING,
            enabled=True,
        )
        notify_event(
            event_type='password_reset',
            title='Password Reset',
            body='You requested a reset.',
            severity='warning',
            user=user,
        )
        assert UserAlert.objects.filter(user=user, category='security').exists()

    def test_notify_respects_disabled_channel(self, create_user):
        user = create_user("dave")
        NotificationChannel.objects.create(user=user, enabled=False)
        NotificationRule.objects.create(
            event_type=NotificationRule.EventType.SYSTEM_ALERT,
            min_severity=NotificationRule.Severity.CRITICAL,
            enabled=True,
        )
        notify_event(
            event_type='system_alert',
            title='System Down',
            body='Maintenance',
            severity='critical',
            user=user,
        )
        assert UserAlert.objects.filter(user=user).count() == 0

    def test_notify_without_rules_is_noop(self, create_user):
        """No rules configured — even with a specific user, nothing is created."""
        user = create_user("eve")
        count_before = UserAlert.objects.count()
        notify_event(
            event_type='dq_violation',
            title='DQ Fail',
            body='Rule failed',
            severity='warning',
            user=user,
        )
        assert UserAlert.objects.count() == count_before  # No matching rule

    def test_notify_with_matching_rule(self, create_user):
        user = create_user("frank")
        NotificationRule.objects.create(
            event_type=NotificationRule.EventType.DQ_VIOLATION,
            min_severity=NotificationRule.Severity.WARNING,
            enabled=True,
        )
        notify_event(
            event_type='dq_violation',
            title='DQ Fail',
            body='Rule failed',
            severity='error',
        )
        assert UserAlert.objects.filter(user=user, category='dq_violation').exists()

    def test_notify_severity_filtering(self, create_user):
        """Rule with min_severity=ERROR should NOT fire for warning events."""
        user = create_user("grace")
        NotificationRule.objects.create(
            event_type=NotificationRule.EventType.DQ_VIOLATION,
            min_severity=NotificationRule.Severity.ERROR,
            enabled=True,
        )
        notify_event(
            event_type='dq_violation',
            title='Minor',
            body='Just a warning',
            severity='warning',
            user=user,
        )
        assert UserAlert.objects.filter(user=user).count() == 0  # severity too low

    def test_notify_fires_for_exact_severity(self, create_user):
        user = create_user("heidi")
        NotificationRule.objects.create(
            event_type=NotificationRule.EventType.DQ_VIOLATION,
            min_severity=NotificationRule.Severity.WARNING,
            enabled=True,
        )
        notify_event(
            event_type='dq_violation',
            title='Warning',
            body='Exactly warning',
            severity='warning',
            user=user,
        )
        assert UserAlert.objects.filter(user=user).count() == 1


@pytest.mark.django_db
class TestNotificationAPI:
    def _auth(self, api_client, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(user).access_token)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_list_own_notifications(self, api_client, create_user):
        user = create_user("ivan")
        UserAlert.objects.create(user=user, title="Alert 1", category=UserAlert.Category.SYSTEM)
        UserAlert.objects.create(user=user, title="Alert 2", category=UserAlert.Category.SYSTEM)
        self._auth(api_client, user)

        response = api_client.get(reverse("user-alert-list"))
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_only_own_notifications(self, api_client, create_user):
        alice = create_user("alice2")
        bob = create_user("bob2")
        UserAlert.objects.create(user=alice, title="Alice's")
        UserAlert.objects.create(user=bob, title="Bob's")
        self._auth(api_client, alice)

        response = api_client.get(reverse("user-alert-list"))
        data = response.json()
        assert len(data) == 1
        assert data[0]['title'] == "Alice's"

    def test_mark_read_single(self, api_client, create_user):
        user = create_user("john")
        alert = UserAlert.objects.create(user=user, title="Unread")
        self._auth(api_client, user)

        url = reverse("user-alert-mark-read", args=[alert.id])
        response = api_client.post(url)
        assert response.status_code == 200
        alert.refresh_from_db()
        assert alert.is_read is True

    def test_mark_all_read(self, api_client, create_user):
        user = create_user("kate")
        UserAlert.objects.create(user=user, title="A")
        UserAlert.objects.create(user=user, title="B")
        self._auth(api_client, user)

        response = api_client.post(reverse("user-alert-mark-all-read"))
        assert response.status_code == 200
        assert UserAlert.objects.filter(user=user, is_read=False).count() == 0

    def test_unread_count(self, api_client, create_user):
        user = create_user("lee")
        UserAlert.objects.create(user=user, title="Unread 1")
        UserAlert.objects.create(user=user, title="Unread 2")
        self._auth(api_client, user)

        response = api_client.get(reverse("user-alert-unread-count"))
        data = response.json()
        assert data['unread_count'] == 2

    def test_requires_auth(self, api_client):
        response = api_client.get(reverse("user-alert-list"))
        assert response.status_code == 401


@pytest.mark.django_db
class TestDQSignal:
    def test_failed_dq_result_triggers_notification(self, api_client, create_user):
        """Signal on DQResult.post_save — but needs a matching rule to fire."""
        from dq.models import DQRule, DQResult
        from dataschema.models import DataTable, Module

        user = create_user("mike")
        NotificationRule.objects.create(
            event_type=NotificationRule.EventType.DQ_VIOLATION,
            min_severity=NotificationRule.Severity.WARNING,
            enabled=True,
        )

        module = Module.objects.create(name="test_module")
        table = DataTable.objects.create(title="test_table", name="test_table", module=module)
        rule = DQRule.objects.create(
            name="not_null_rule",
            rule_type="not_null",
            params={"column": "id"},
            is_active=True,
        )
        from dq.models import RuleFieldAssignment
        RuleFieldAssignment.objects.create(rule=rule, data_table=table)
        # Create a failed DQ result — should trigger signal → notification
        DQResult.objects.create(
            rule=rule,
            passed=False,
            checked_count=100,
            failed_count=42,
            score=58,
        )

        assert UserAlert.objects.filter(user=user, category='dq_violation').exists()
