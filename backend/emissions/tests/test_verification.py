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

    # ── helpers ───────────────────────────────────────────────────────

    def _set_status(self, status):
        """Bypass state machine to set up test preconditions."""
        self.period.status = status
        self.period.save()

    # ── submit tests ───────────────────────────────────────────────────

    def test_submit_from_locked_succeeds(self):
        """Submit from locked → submitted, creates pending VerificationRecord."""
        self._set_status('locked')
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('emissions:reporting-period-submit', args=[self.period.id]))
        self.assertEqual(resp.status_code, 200)
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'submitted')
        self.assertIsNotNone(self.period.submitted_at)
        # Pending verification record created with submitter as verifier
        self.assertTrue(
            VerificationRecord.objects.filter(
                reporting_period=self.period, verifier=self.admin, status='pending'
            ).exists()
        )

    def test_submit_from_draft_blocked_409(self):
        """Draft → submitted is not a valid transition (must go via open→locked)."""
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('emissions:reporting-period-submit', args=[self.period.id]))
        self.assertEqual(resp.status_code, 409)

    def test_submit_already_submitted_returns_200(self):
        """Submitting an already-submitted period is a no-op (same state)."""
        self._set_status('submitted')
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('emissions:reporting-period-submit', args=[self.period.id]))
        self.assertEqual(resp.status_code, 200)

    # ── verify tests ──────────────────────────────────────────────────

    def test_verify_creates_record(self):
        """Admin verify → period verified, VerificationRecord created."""
        self._set_status('submitted')
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('emissions:reporting-period-verify', args=[self.period.id]))
        self.assertEqual(resp.status_code, 200)
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'verified')
        self.assertTrue(
            VerificationRecord.objects.filter(
                reporting_period=self.period, verifier=self.admin, status='verified'
            ).exists()
        )

    def test_verify_non_submitted_blocked_409(self):
        """Draft → verified is invalid; expect 409."""
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('emissions:reporting-period-verify', args=[self.period.id]))
        self.assertEqual(resp.status_code, 409)

    def test_verify_by_non_admin_blocked_403(self):
        """Non-admin cannot verify."""
        self._set_status('submitted')
        self.client.force_authenticate(self.user)
        resp = self.client.post(reverse('emissions:reporting-period-verify', args=[self.period.id]))
        self.assertEqual(resp.status_code, 403)

    def test_double_verify_by_same_admin_no_500(self):
        """Re-verify by same verifier updates record — no IntegrityError."""
        self._set_status('submitted')
        self.client.force_authenticate(self.admin)
        resp1 = self.client.post(reverse('emissions:reporting-period-verify', args=[self.period.id]))
        self.assertEqual(resp1.status_code, 200)

        # Reset period to submitted for re-verify
        self._set_status('submitted')
        resp2 = self.client.post(reverse('emissions:reporting-period-verify', args=[self.period.id]))
        self.assertEqual(resp2.status_code, 200)
        # Only one verified record for this (period, verifier) pair
        self.assertEqual(
            VerificationRecord.objects.filter(
                reporting_period=self.period, verifier=self.admin, status='verified'
            ).count(),
            1,
        )

    # ── reject tests ──────────────────────────────────────────────────

    def test_reject_with_notes(self):
        """Admin reject → period rejected, notes captured in VerificationRecord."""
        self._set_status('submitted')
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse('emissions:reporting-period-reject', args=[self.period.id]),
            {'notes': 'Missing Scope 3 data'}, format='json'
        )
        self.assertEqual(resp.status_code, 200)
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'rejected')
        record = VerificationRecord.objects.get(
            reporting_period=self.period, verifier=self.admin, status='rejected'
        )
        self.assertIn('Missing Scope 3', record.notes)

    def test_reject_by_non_admin_blocked_403(self):
        """Non-admin cannot reject."""
        self._set_status('submitted')
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            reverse('emissions:reporting-period-reject', args=[self.period.id]),
            {'notes': 'bad'}, format='json'
        )
        self.assertEqual(resp.status_code, 403)

    def test_reject_from_draft_blocked_409(self):
        """Draft → rejected is invalid; expect 409."""
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse('emissions:reporting-period-reject', args=[self.period.id]),
            {'notes': 'bad'}, format='json'
        )
        self.assertEqual(resp.status_code, 409)

    # ── list / serialiser tests ───────────────────────────────────────

    def test_verifications_filter_by_period(self):
        """GET verifications?period_id=X returns records for that period."""
        self._set_status('submitted')
        self.client.force_authenticate(self.admin)
        self.client.post(reverse('emissions:reporting-period-verify', args=[self.period.id]))
        resp = self.client.get(f"{reverse('emissions:verification-list')}?period_id={self.period.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_verifier_name_in_response(self):
        """Verification list includes verifier_name."""
        self._set_status('submitted')
        self.client.force_authenticate(self.admin)
        self.client.post(reverse('emissions:reporting-period-verify', args=[self.period.id]))
        resp = self.client.get(reverse('emissions:verification-list'))
        data = resp.json()
        self.assertEqual(data[0]['verifier_name'], 'adminuser')

    def test_serializer_includes_scope_summary(self):
        """VerificationRecordSerializer exposes period_label, total_co2e_tonnes, scope_summary."""
        self._set_status('submitted')
        self.client.force_authenticate(self.admin)
        self.client.post(reverse('emissions:reporting-period-verify', args=[self.period.id]))
        resp = self.client.get(reverse('emissions:verification-list'))
        data = resp.json()
        self.assertIn('period_label', data[0])
        self.assertIn('total_co2e_tonnes', data[0])
        self.assertIn('scope_summary', data[0])

    # ── resubmit (rejected → submitted) ───────────────────────────────

    def test_resubmit_from_rejected(self):
        """Rejected period can be resubmitted."""
        self._set_status('rejected')
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('emissions:reporting-period-submit', args=[self.period.id]))
        self.assertEqual(resp.status_code, 200)
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'submitted')
