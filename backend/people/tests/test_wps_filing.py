"""Honest GOSI/WPS SIF filing lifecycle (generate → validate → submit)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from mdm.models import OrgUnit
from people.models import Employee, PayrollRun, PayslipLine, WpsFiling
from people.payroll_service import PayrollRunService, PayrollServiceError
from people.tests.test_payroll_service import (
    _gosi_rule,
    _gross_rule,
    _net_rule,
    _verified_basic_line,
    _wps_rule,
)


class WpsFilingLifecycleTests(TestCase):
    def setUp(self):
        self.hq = OrgUnit.objects.create(name="WPS HQ", slug="wps-hq-filing")
        self.emp = Employee.objects.create(
            org_unit=self.hq,
            employee_no="WPS-1",
            full_name="WPS Emp",
            basic_salary=Decimal("1000.000"),
            join_date=date(2024, 1, 1),
        )
        _verified_basic_line(self.emp, Decimal("1000.000"))
        _gross_rule()
        _gosi_rule()
        _net_rule()
        _wps_rule(authoritative=True)
        self.service = PayrollRunService()
        User = get_user_model()
        self.prep = User.objects.create_superuser(
            username="wps-filing-prep", password="x"
        )
        self.appr = User.objects.create_superuser(
            username="wps-filing-appr", password="x"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.prep)

    def _committed_run(self):
        run = PayrollRun.objects.create(
            org_unit=self.hq,
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
        )
        self.service.compute(run, user=self.prep)
        self.service.validate(run, user=self.prep)
        self.service.commit(run, user=self.appr)
        run.refresh_from_db()
        return run

    def test_generate_validate_submit_happy(self):
        run = self._committed_run()
        self.client.force_authenticate(user=self.prep)
        r = self.client.post(f"/carbon-api/people/payroll-runs/{run.pk}/wps/generate/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["status"], "generated")
        self.assertTrue(WpsFiling.objects.filter(payroll_run=run).exists())

        r2 = self.client.post(f"/carbon-api/people/payroll-runs/{run.pk}/wps/validate/")
        self.assertEqual(r2.status_code, 200, r2.content)
        self.assertTrue(r2.json()["passed"])

        # Same actor submit must refuse (ADR-0045)
        bad = self.client.post(f"/carbon-api/people/payroll-runs/{run.pk}/wps/submit/")
        self.assertEqual(bad.status_code, 403, bad.content)

        self.client.force_authenticate(user=self.appr)
        r3 = self.client.post(f"/carbon-api/people/payroll-runs/{run.pk}/wps/submit/")
        self.assertEqual(r3.status_code, 200, r3.content)
        body = r3.json()
        self.assertEqual(body["status"], "submitted")
        self.assertTrue(body["receipt_id"])
        filing = WpsFiling.objects.get(payroll_run=run)
        self.assertTrue(filing.reconciled)

        r4 = self.client.post(f"/carbon-api/people/payroll-runs/{run.pk}/wps/submit/")
        self.assertEqual(r4.status_code, 200)
        self.assertTrue(r4.json().get("idempotent"))

        detail = self.client.get(f"/carbon-api/people/payroll-runs/{run.pk}/wps/filing/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["status"], "submitted")

    def test_submit_without_generate_refuses(self):
        run = PayrollRun.objects.create(
            org_unit=self.hq,
            period_start=date(2030, 1, 1),
            period_end=date(2030, 1, 31),
            status="committed",
        )
        with self.assertRaises(PayrollServiceError):
            self.service.wps_submit_filing(run, user=self.appr)
    def test_generate_refuses_draft(self):
        run = PayrollRun.objects.create(
            org_unit=self.hq,
            period_start=date(2030, 2, 1),
            period_end=date(2030, 2, 28),
            status="draft",
        )
        with self.assertRaises(PayrollServiceError):
            self.service.wps_generate(run)


def test_people_route_joins_wps_action():
    from ai.host_executor import _people_route

    assert _people_route("carbon-api/people/payroll-runs/9/wps/generate") == (
        "payroll-runs",
        "9",
        "wps/generate",
    )
