"""Host SoD gate tests (ADR-0045 / NPS-1) — same actor refuse, distinct OK."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from mdm.models import OrgUnit
from people.governance.sod import (
    ACTION_APPROVE,
    ACTION_COMMIT,
    SUBJECT_ATTENDANCE_PERMISSION,
    SUBJECT_EMPLOYEE,
    SUBJECT_PAYROLL_RUN,
    SUBJECT_WPS_FILING,
    SoDViolation,
    get_preparer,
    record_preparer,
    require_distinct_actor,
)
from people.models import AttendancePermission, Employee, PayrollRun, WpsFiling
from people.payroll_service import PayrollRunService
from people.tests.ref_helpers import ensure_ref


User = get_user_model()


class SoDUnitTests(TestCase):
    def setUp(self):
        self.prep = User.objects.create_user("sod_prep", password="x")
        self.appr = User.objects.create_user("sod_appr", password="x")

    def test_same_actor_refused(self):
        record_preparer(
            subject_type=SUBJECT_PAYROLL_RUN, subject_id=1, user=self.prep,
        )
        with self.assertRaises(SoDViolation) as ctx:
            require_distinct_actor(
                subject_type=SUBJECT_PAYROLL_RUN,
                subject_id=1,
                actor=self.prep,
                action=ACTION_COMMIT,
            )
        self.assertEqual(ctx.exception.code, "sod_same_actor")

    def test_distinct_actor_ok(self):
        record_preparer(
            subject_type=SUBJECT_PAYROLL_RUN, subject_id=2, user=self.prep,
        )
        require_distinct_actor(
            subject_type=SUBJECT_PAYROLL_RUN,
            subject_id=2,
            actor=self.appr,
            action=ACTION_COMMIT,
        )

    def test_missing_preparer_fail_closed(self):
        with self.assertRaises(SoDViolation) as ctx:
            require_distinct_actor(
                subject_type=SUBJECT_PAYROLL_RUN,
                subject_id=99999,
                actor=self.appr,
                action=ACTION_COMMIT,
            )
        self.assertEqual(ctx.exception.code, "sod_missing_preparer")

    def test_first_writer_wins(self):
        record_preparer(
            subject_type=SUBJECT_EMPLOYEE, subject_id=7, user=self.prep,
        )
        record_preparer(
            subject_type=SUBJECT_EMPLOYEE, subject_id=7, user=self.appr,
        )
        self.assertEqual(get_preparer(subject_type=SUBJECT_EMPLOYEE, subject_id=7), self.prep)


class PayrollSoDServiceTests(TestCase):
    def setUp(self):
        self.prep = User.objects.create_user("pay_prep", password="x")
        self.appr = User.objects.create_user("pay_appr", password="x")
        self.org = OrgUnit.objects.create(name="SoD Org", code="SOD1")

    def _validated_run(self):
        run = PayrollRun.objects.create(
            org_unit=self.org,
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            status="validated",
        )
        record_preparer(
            subject_type=SUBJECT_PAYROLL_RUN,
            subject_id=run.pk,
            user=self.prep,
            process_key="payroll.run.lifecycle",
        )
        return run

    def test_commit_same_actor_raises(self):
        run = self._validated_run()
        with self.assertRaises(SoDViolation):
            PayrollRunService().commit(run, user=self.prep)

    def test_commit_distinct_actor_ok(self):
        run = self._validated_run()
        # commit re-validates; empty run with no lines should pass empty validation
        result = PayrollRunService().commit(run, user=self.appr)
        self.assertEqual(result["status"], "committed")


class WpsSoDServiceTests(TestCase):
    def setUp(self):
        self.prep = User.objects.create_user("wps_prep", password="x")
        self.appr = User.objects.create_user("wps_appr", password="x")
        self.org = OrgUnit.objects.create(name="WPS Org", code="WPS1")
        self.run = PayrollRun.objects.create(
            org_unit=self.org,
            period_start=date(2026, 5, 1),
            period_end=date(2026, 5, 31),
            status="committed",
        )
        self.filing = WpsFiling.objects.create(
            payroll_run=self.run,
            status="validated",
            content_hash="abc",
            record_count=1,
            csv_bytes=b"a,b\n1,2\n",
            validation_passed=True,
        )
        record_preparer(
            subject_type=SUBJECT_WPS_FILING,
            subject_id=self.filing.pk,
            user=self.prep,
            process_key="gosi_wps.sif.lifecycle",
            overwrite=True,
        )

    def test_submit_same_actor_raises(self):
        with self.assertRaises(SoDViolation):
            PayrollRunService().wps_submit_filing(self.run, user=self.prep)

    def test_submit_distinct_actor_ok(self):
        result = PayrollRunService().wps_submit_filing(self.run, user=self.appr)
        self.assertEqual(result["status"], "submitted")


class AttendanceSoDApiTests(TestCase):
    def setUp(self):
        self.prep = User.objects.create_user("att_prep", password="x", is_staff=True)
        self.appr = User.objects.create_user("att_appr", password="x", is_staff=True)
        # Global admin bypass for PeopleAccess in tests
        self.prep.is_superuser = True
        self.prep.save()
        self.appr.is_superuser = True
        self.appr.save()
        self.org = OrgUnit.objects.create(name="Att Org", code="ATT1")
        self.emp = Employee.objects.create(
            employee_no="ATT100",
            full_name="Att Emp",
            org_unit=self.org,
            join_date=date(2026, 1, 1),
            basic_salary=Decimal("500.000"),
            is_active=True,
        )
        ensure_ref("permission_type", "personal")
        self.client = APIClient()

    def test_approve_same_actor_403(self):
        self.client.force_authenticate(self.prep)
        r = self.client.post(
            "/carbon-api/people/attendance-permissions/",
            {
                "employee": self.emp.pk,
                "date": "2026-06-01",
                "permission_type": "personal",
                "hours": "2.00",
                "notes": "sod",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        pid = r.json()["id"]
        bad = self.client.patch(
            f"/carbon-api/people/attendance-permissions/{pid}/",
            {"approved": True},
            format="json",
        )
        self.assertEqual(bad.status_code, 403, bad.content)
        self.assertEqual(bad.json().get("code"), "sod_same_actor")

    def test_approve_distinct_actor_200(self):
        self.client.force_authenticate(self.prep)
        r = self.client.post(
            "/carbon-api/people/attendance-permissions/",
            {
                "employee": self.emp.pk,
                "date": "2026-06-02",
                "permission_type": "personal",
                "hours": "1.50",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        pid = r.json()["id"]
        self.client.force_authenticate(self.appr)
        ok = self.client.patch(
            f"/carbon-api/people/attendance-permissions/{pid}/",
            {"approved": True},
            format="json",
        )
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertTrue(ok.json().get("approved"))


class OnboardingSoDApiTests(TestCase):
    def setUp(self):
        self.prep = User.objects.create_user("on_prep", password="x", is_superuser=True)
        self.appr = User.objects.create_user("on_appr", password="x", is_superuser=True)
        self.org = OrgUnit.objects.create(name="On Org", code="ON1")
        self.client = APIClient()

    def test_activate_same_actor_403(self):
        self.client.force_authenticate(self.prep)
        r = self.client.post(
            "/carbon-api/people/employees/",
            {
                "employee_no": "ONB001",
                "full_name": "Onboard SoD",
                "org_unit": self.org.pk,
                "join_date": "2026-05-01",
                "basic_salary": "400.000",
                "is_active": False,
            },
            format="json",
        )
        self.assertIn(r.status_code, (200, 201), r.content)
        eid = r.json()["id"]
        bad = self.client.patch(
            f"/carbon-api/people/employees/{eid}/",
            {"is_active": True},
            format="json",
        )
        self.assertEqual(bad.status_code, 403, bad.content)

    def test_activate_distinct_actor_200(self):
        self.client.force_authenticate(self.prep)
        r = self.client.post(
            "/carbon-api/people/employees/",
            {
                "employee_no": "ONB002",
                "full_name": "Onboard SoD 2",
                "org_unit": self.org.pk,
                "join_date": "2026-05-02",
                "basic_salary": "400.000",
                "is_active": False,
            },
            format="json",
        )
        self.assertIn(r.status_code, (200, 201), r.content)
        eid = r.json()["id"]
        self.client.force_authenticate(self.appr)
        ok = self.client.patch(
            f"/carbon-api/people/employees/{eid}/",
            {"is_active": True},
            format="json",
        )
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertTrue(ok.json().get("is_active"))
