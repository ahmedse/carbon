"""Tests for E2-B4: Notifications — model, service, endpoints, lifecycle emission."""
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from django.test import TestCase
from django.contrib.auth.models import Group

from accounts.models import User, ScopedRole
from core.models import Notification
from core.services import NotificationService
from emissions.models import ReportingPeriod


class NotificationModelTests(TestCase):
    """Model-level tests for Notification."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass')

    def test_notification_creation(self):
        n = Notification.objects.create(
            user=self.user, verb='submitted', message='Period Q1 submitted'
        )
        self.assertEqual(n.verb, 'submitted')
        self.assertEqual(n.user, self.user)
        self.assertIsNone(n.read_at)
        self.assertIsNotNone(n.created_at)

    def test_notification_ordering(self):
        n1 = Notification.objects.create(user=self.user, verb='a', message='older')
        n2 = Notification.objects.create(user=self.user, verb='b', message='newer')
        qs = list(Notification.objects.filter(user=self.user))
        self.assertEqual(qs[0].id, n2.id)
        self.assertEqual(qs[1].id, n1.id)

    def test_str_representation(self):
        n = Notification.objects.create(
            user=self.user, verb='verified', message='Period FY2025 has been verified'
        )
        self.assertIn('verified', str(n))
        self.assertIn('Period FY2025', str(n))


class NotificationServiceTests(TestCase):
    """Tests for NotificationService.notify()."""

    def setUp(self):
        self.user = User.objects.create_user(username='svcuser', password='pass')

    def test_notify_creates_record(self):
        n = NotificationService.notify(self.user, 'submitted', 'Test message', '/some/link')
        self.assertIsNotNone(n)
        self.assertEqual(n.user, self.user)
        self.assertEqual(n.verb, 'submitted')
        self.assertEqual(n.message, 'Test message')
        self.assertEqual(n.link, '/some/link')

    def test_notify_none_user_is_noop(self):
        n = NotificationService.notify(None, 'submitted', 'Should not create')
        self.assertIsNone(n)
        self.assertEqual(Notification.objects.count(), 0)


class NotificationEndpointTests(TestCase):
    """Tests for NotificationViewSet endpoints."""

    def setUp(self):
        self.user_a = User.objects.create_user(username='usera', password='pass')
        self.user_b = User.objects.create_user(username='userb', password='pass')
        self.client = APIClient()

        # Create notifications for user_a
        Notification.objects.create(user=self.user_a, verb='submitted', message='A: Q1 submitted')
        Notification.objects.create(user=self.user_a, verb='verified', message='A: Q1 verified')
        # Create notification for user_b
        Notification.objects.create(user=self.user_b, verb='submitted', message='B: Q2 submitted')

    def test_list_only_own_notifications(self):
        """GET returns only notifications for the requesting user."""
        self.client.force_authenticate(self.user_a)
        resp = self.client.get(reverse('notification-list'))
        self.assertEqual(resp.status_code, 200)
        results = resp.data['results']
        self.assertEqual(len(results), 2)
        for item in results:
            self.assertEqual(item['user'], self.user_a.id)

    def test_list_another_user_sees_only_own(self):
        """User B sees only their own notification."""
        self.client.force_authenticate(self.user_b)
        resp = self.client.get(reverse('notification-list'))
        self.assertEqual(resp.status_code, 200)
        results = resp.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['user'], self.user_b.id)

    def test_unread_count_in_response(self):
        """List response includes unread_count."""
        self.client.force_authenticate(self.user_a)
        resp = self.client.get(reverse('notification-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['unread_count'], 2)

    def test_mark_read_sets_read_at(self):
        """POST mark_read sets read_at to now."""
        self.client.force_authenticate(self.user_a)
        n = Notification.objects.filter(user=self.user_a).first()
        self.assertIsNone(n.read_at)

        resp = self.client.post(reverse('notification-mark-read', args=[n.id]))
        self.assertEqual(resp.status_code, 200)
        n.refresh_from_db()
        self.assertIsNotNone(n.read_at)

    def test_mark_read_idempotent(self):
        """Marking an already-read notification is idempotent."""
        self.client.force_authenticate(self.user_a)
        n = Notification.objects.filter(user=self.user_a).first()
        # Pre-mark as read
        n.read_at = timezone.now()
        n.save()

        resp = self.client.post(reverse('notification-mark-read', args=[n.id]))
        self.assertEqual(resp.status_code, 200)
        n.refresh_from_db()
        self.assertIsNotNone(n.read_at)

    def test_mark_all_read(self):
        """POST mark_all_read marks all unread as read."""
        self.client.force_authenticate(self.user_a)
        self.assertEqual(
            Notification.objects.filter(user=self.user_a, read_at__isnull=True).count(),
            2,
        )

        resp = self.client.post(reverse('notification-mark-all-read'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['marked_read'], 2)
        self.assertEqual(
            Notification.objects.filter(user=self.user_a, read_at__isnull=True).count(),
            0,
        )

    def test_mark_all_read_only_affects_self(self):
        """mark_all_read does not affect other users' notifications."""
        self.client.force_authenticate(self.user_a)
        resp = self.client.post(reverse('notification-mark-all-read'))
        self.assertEqual(resp.status_code, 200)
        # user_b's notification should remain unread
        self.assertEqual(
            Notification.objects.filter(user=self.user_b, read_at__isnull=True).count(),
            1,
        )

    def test_unread_count_decrements_after_mark_read(self):
        """After marking a notification read, unread_count decreases."""
        self.client.force_authenticate(self.user_a)
        n = Notification.objects.filter(user=self.user_a).first()

        # Initial count should be 2
        resp = self.client.get(reverse('notification-list'))
        self.assertEqual(resp.data['unread_count'], 2)

        # Mark one read
        self.client.post(reverse('notification-mark-read', args=[n.id]))
        resp = self.client.get(reverse('notification-list'))
        self.assertEqual(resp.data['unread_count'], 1)

    def test_cannot_mark_others_notification_read(self):
        """User cannot mark another user's notification as read (404)."""
        self.client.force_authenticate(self.user_a)
        other_n = Notification.objects.filter(user=self.user_b).first()
        resp = self.client.post(reverse('notification-mark-read', args=[other_n.id]))
        self.assertEqual(resp.status_code, 404)


class NotificationLifecycleTests(TestCase):
    """Tests that notifications are emitted on verification lifecycle events."""

    def setUp(self):
        self.admin = User.objects.create_superuser(username='ntfadmin', password='pass')
        admins_group, _ = Group.objects.get_or_create(name='admins_group')
        self.admin.groups.add(admins_group)
        ScopedRole.objects.create(
            user=self.admin, group=admins_group, is_active=True,
        )

        dataowners_group, _ = Group.objects.get_or_create(name='dataowners_group')
        self.data_owner = User.objects.create_user(username='ntfdowner', password='pass')
        self.data_owner.groups.add(dataowners_group)
        ScopedRole.objects.create(
            user=self.data_owner, group=dataowners_group, is_active=True,
        )

        self.period = ReportingPeriod.objects.create(
            name='NTF Q1 2026', start_date='2026-01-01', end_date='2026-03-31',
            status='draft', created_by=self.admin,
        )
        self.client = APIClient()

    def _set_status(self, status):
        self.period.status = status
        self.period.save()

    def test_notification_on_period_submit(self):
        """Notification created for data owners when period is submitted."""
        self._set_status('locked')
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'locked')
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse('emissions:reporting-period-submit', args=[self.period.id])
        )
        self.assertEqual(resp.status_code, 200, f"Got {resp.status_code}: {resp.data}")
        # Data owner should have a 'submitted' notification
        self.assertTrue(
            Notification.objects.filter(
                user=self.data_owner, verb='submitted',
                message__contains='submitted for verification',
            ).exists()
        )

    def test_notification_on_period_verify(self):
        """Notification created for period creator when period is verified."""
        self._set_status('submitted')
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse('emissions:reporting-period-verify', args=[self.period.id])
        )
        self.assertEqual(resp.status_code, 200)
        # Creator (admin) should have a 'verified' notification
        self.assertTrue(
            Notification.objects.filter(
                user=self.admin, verb='verified',
                message__contains='has been verified',
            ).exists()
        )

    def test_notification_on_period_reject(self):
        """Notification created for period creator when period is rejected."""
        self._set_status('submitted')
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse('emissions:reporting-period-reject', args=[self.period.id]),
            {'notes': 'Missing data in scope 2'},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        # Creator (admin) should have a 'rejected' notification with notes
        n = Notification.objects.filter(
            user=self.admin, verb='rejected',
            message__contains='has been rejected',
        ).first()
        self.assertIsNotNone(n)
        self.assertIn('Missing data in scope 2', n.message)
