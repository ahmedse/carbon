# File: people/tests/test_normalize_genders.py
# PAQ-4A — canonical gender normalization for Employee.gender (free-text field).
#
# Employee.gender is NOT a governed enum; dirty imports can leave M/F/Male/…
# variants behind. This command collapses them to male/female, leaves blanks
# untouched (never invent a gender), and leaves unknown non-blank values alone.

from datetime import date
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from mdm.models import OrgUnit

from people.models import Employee


class NormalizeEmployeeGendersTests(TestCase):
    def setUp(self):
        self.org = OrgUnit.objects.create(name="Test Org", slug="test-org")
        self.out = StringIO()

    def _make_employee(self, employee_no, gender):
        return Employee.objects.create(
            org_unit=self.org,
            employee_no=employee_no,
            full_name=f"Emp {employee_no}",
            basic_salary="1000.000",
            join_date=date(2026, 1, 1),
            gender=gender,
        )

    def _run(self, **kwargs):
        kwargs.setdefault("stdout", self.out)
        call_command("normalize_employee_genders", **kwargs)

    def _gender_map(self):
        return {
            emp.employee_no: emp.gender
            for emp in Employee.objects.all()
        }

    def test_variants_normalize_to_male(self):
        for i, raw in enumerate(["m", "M", "Male", "MALE"]):
            self._make_employee(f"M-{i}", raw)

        self._run()

        result = self._gender_map()
        for i in range(4):
            assert result[f"M-{i}"] == "male"

    def test_variants_normalize_to_female(self):
        for i, raw in enumerate(["f", "F", "Female", "FEMALE"]):
            self._make_employee(f"F-{i}", raw)

        self._run()

        result = self._gender_map()
        for i in range(4):
            assert result[f"F-{i}"] == "female"

    def test_blank_stays_blank(self):
        emp = self._make_employee("BLANK", "")

        self._run()

        emp.refresh_from_db()
        assert emp.gender == ""

    def test_blank_with_whitespace_stays_blank(self):
        emp = self._make_employee("SPACES", "   ")

        self._run()

        emp.refresh_from_db()
        assert emp.gender == ""

    def test_already_canonical_not_rewritten_and_idempotent(self):
        male = self._make_employee("CANON-M", "male")
        female = self._make_employee("CANON-F", "female")

        # First run: canonical values are left as-is.
        self._run()
        male.refresh_from_db()
        female.refresh_from_db()
        assert male.gender == "male"
        assert female.gender == "female"

        # Second run reports 0 changes (idempotent).
        self.out = StringIO()
        self._run()
        assert "0 normalized" in self.out.getvalue()
        assert male.gender == "male"
        assert female.gender == "female"

    def test_unknown_value_left_unchanged(self):
        emp = self._make_employee("UNKNOWN", "X")

        self._run()

        emp.refresh_from_db()
        assert emp.gender == "X"
        assert "1 unknown non-blank" in self.out.getvalue()
        assert "'X'" in self.out.getvalue()

    def test_dry_run_makes_no_writes(self):
        self._make_employee("DRY-M", "m")
        self._make_employee("DRY-F", "F")

        self._run(dry_run=True)

        result = self._gender_map()
        assert result["DRY-M"] == "m"
        assert result["DRY-F"] == "F"
        assert "[dry-run]" in self.out.getvalue()

    def test_mixed_run_counts_and_writes(self):
        self._make_employee("B", "")
        self._make_employee("C-M", "male")
        self._make_employee("V-M", "m")
        self._make_employee("V-F", "F")
        self._make_employee("U", "X")

        self._run()

        result = self._gender_map()
        assert result["B"] == ""
        assert result["C-M"] == "male"
        assert result["V-M"] == "male"
        assert result["V-F"] == "female"
        assert result["U"] == "X"

        # Second run: no further changes (idempotent).
        self.out = StringIO()
        self._run()
        assert "0 normalized" in self.out.getvalue()
