from datetime import date

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from people.models import ComplianceRule


class ComplianceRuleModelTests(TestCase):
    def test_default_is_authoritative_false_and_provenance_none(self):
        rule = ComplianceRule.objects.create(
            rule_id="t-rule",
            version="2026.1",
            name="Test rule",
            category="other",
            effective_date=date(2026, 1, 1),
        )
        self.assertFalse(rule.is_authoritative)
        self.assertIsNone(rule.provenance)

    def test_unique_together_rule_id_version(self):
        ComplianceRule.objects.create(
            rule_id="t-eosi", version="2026.1", name="A", category="eosi",
            effective_date=date(2026, 1, 1),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ComplianceRule.objects.create(
                    rule_id="t-eosi", version="2026.1", name="B", category="eosi",
                    effective_date=date(2026, 1, 1),
                )

    def test_different_versions_of_same_rule_id_allowed(self):
        ComplianceRule.objects.create(
            rule_id="t-eosi", version="2026.1", name="A", category="eosi",
            effective_date=date(2026, 1, 1),
        )
        ComplianceRule.objects.create(
            rule_id="t-eosi", version="2026.2", name="A", category="eosi",
            effective_date=date(2026, 6, 1),
        )
        self.assertEqual(ComplianceRule.objects.filter(rule_id="t-eosi").count(), 2)


class SeedTestRulesCommandTests(TestCase):
    def test_seed_is_idempotent_and_all_non_authoritative(self):
        call_command("seed_test_rules")
        first_count = ComplianceRule.objects.count()
        call_command("seed_test_rules")
        second_count = ComplianceRule.objects.count()

        self.assertGreater(first_count, 0)
        self.assertEqual(first_count, second_count)

        for rule in ComplianceRule.objects.all():
            self.assertFalse(rule.is_authoritative)
            self.assertIsNone(rule.provenance)
            self.assertEqual(rule.source_citation, "")
            self.assertTrue(rule.name.startswith("[TEST ONLY — NON-AUTHORITATIVE]"))
