"""Tests for verification workflow (submit/verify/reject) and VerificationRecordViewSet."""
from django.urls import reverse
from rest_framework.test import APIClient
from django.test import TestCase
from django.contrib.auth.models import Group

from accounts.models import User, ScopedRole
from emissions.models import ReportingPeriod, VerificationRecord


class VerificationWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='verifier', password='pass')
        self.admin = User.objects.create_user(username='adminuser', password='pass', is_superuser=True)
        admins_group, _ = Group.objects.get_or_create(name='admins_group')
        self.admin.groups.add(admins_group)
        self.period = ReportingPeriod.objects.create(
            name='Q1 2026', start_date='2026-01-01', end_date='2026-03-31', status='draft'
        )
        self.client = APIClient()

    def test_submit_draft_period(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('emissions:reporting-period-submit', args=[self.period.id]))
        self.assertEqual(resp.status_code, 200)
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'submitted')
        self.assertIsNotNone(self.period.submitted_at)

    def test_submit_non_draft_fails(self):
        self.period.status = 'submitted'
        self.period.save()
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('emissions:reporting-period-submit', args=[self.period.id]))
        self.assertEqual(resp.status_code, 400)

    def test_verify_creates_record(self):
        self.period.status = 'submitted'
        self.period.save()
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('emissions:reporting-period-verify', args=[self.period.id]))
        self.assertEqual(resp.status_code, 201)
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'verified')
        self.assertTrue(VerificationRecord.objects.filter(reporting_period=self.period).exists())

    def test_verify_non_submitted_fails(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('emissions:reporting-period-verify', args=[self.period.id]))
        self.assertEqual(resp.status_code, 400)

    def test_verify_by_non_admin_blocked(self):
        self.period.status = 'submitted'
        self.period.save()
        self.client.force_authenticate(self.user)
        resp = self.client.post(reverse('emissions:reporting-period-verify', args=[self.period.id]))
        self.assertEqual(resp.status_code, 403)

    def test_reject_with_notes(self):
        self.period.status = 'submitted'
        self.period.save()
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse('emissions:reporting-period-reject', args=[self.period.id]),
            {'notes': 'Missing Scope 3 data'}, format='json'
        )
        self.assertEqual(resp.status_code, 201)
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'rejected')
        record = VerificationRecord.objects.get(reporting_period=self.period)
        self.assertIn('Missing Scope 3', record.notes)

    def test_verifications_filter_by_period(self):
        self.period.status = 'submitted'
        self.period.save()
        self.client.force_authenticate(self.admin)
        self.client.post(reverse('emissions:reporting-period-verify', args=[self.period.id]))
        resp = self.client.get(f"{reverse('emissions:verification-list')}?period_id={self.period.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_verifier_name_in_response(self):
        self.period.status = 'submitted'
        self.period.save()
        self.client.force_authenticate(self.admin)
        self.client.post(reverse('emissions:reporting-period-verify', args=[self.period.id]))
        resp = self.client.get(reverse('emissions:verification-list'))
        data = resp.json()
        self.assertEqual(data[0]['verifier_name'], 'adminuser')
