"""Publish the October sheet drafts through the People policy lifecycle.

Drafts are created by policy_service. The preparer submits. The same actor
is refused. A different user publishes. Version 2026.1 rows are not written.
"""

from __future__ import annotations

import copy
import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from catalog.models import GovernanceEvent
from people.governance.sod import SUBJECT_POLICY_VERSION, SoDViolation
from people.models import ComplianceRule, SoDPreparation
from people.permissions import _can
from people.policy_service import PolicyTransitionError, create_draft, publish, submit
from people.sheet_provisions import SHEET_PROVISIONS, SHEET_RULE_IDS, SHEET_VERSION, ensure_sheet_drafts


def _snapshot_2026_1():
    rows = {}
    for rule in ComplianceRule.objects.filter(version="2026.1").order_by("rule_id", "pk"):
        rows[(rule.rule_id, rule.pk)] = json.dumps(
            {
                "inputs_schema": rule.inputs_schema,
                "source_citation": rule.source_citation,
                "formula_ref": rule.formula_ref,
                "name": rule.name,
                "effective_date": str(rule.effective_date),
            },
            sort_keys=True,
            default=str,
        )
    return rows


class Command(BaseCommand):
    help = "Draft, submit, and second-person publish the 17 October sheet provisions."

    def add_arguments(self, parser):
        parser.add_argument("--preparer", default="ahmed")
        parser.add_argument("--publisher", default="admin")

    def handle(self, *args, **options):
        brand = (getattr(settings, "DJANGO_BRAND", None) or "").strip().lower()
        db_name = settings.DATABASES["default"]["NAME"]
        if brand != "nibras" or db_name != "nibras_dev":
            raise CommandError(f"refusing: brand={brand!r} database={db_name!r} (nibras_dev only)")

        User = get_user_model()
        preparer = User.objects.filter(username=options["preparer"]).first()
        publisher = User.objects.filter(username=options["publisher"]).first()
        if preparer is None or publisher is None:
            raise CommandError("preparer and publisher users must exist")
        if preparer.pk == publisher.pk:
            raise CommandError("preparer and publisher must be distinct")
        if not _can(preparer, "people:manage"):
            raise CommandError(f"{preparer.username} lacks people:manage")
        if not _can(publisher, "people:manage"):
            raise CommandError(f"{publisher.username} lacks people:manage")

        before = _snapshot_2026_1()
        created, skipped = ensure_sheet_drafts(preparer)
        self.stdout.write(f"drafts created={created} already_present={skipped}")

        specs = {row["rule_id"]: row for row in SHEET_PROVISIONS}
        same_actor_refused = 0
        published = 0
        already = 0
        for rule_id in SHEET_RULE_IDS:
            rule = ComplianceRule.objects.get(rule_id=rule_id, version=SHEET_VERSION)
            if rule.lifecycle == ComplianceRule.LIFECYCLE_AUTHORITATIVE:
                event = GovernanceEvent.objects.filter(
                    entity_type="ComplianceRule", entity_id=rule.pk, action="publish",
                ).first()
                if event is None:
                    self.stdout.write(self.style.WARNING(
                        f"removing unpublished authoritative shortcut {rule_id}"
                    ))
                    SoDPreparation.objects.filter(
                        subject_type=SUBJECT_POLICY_VERSION, subject_id=rule.pk,
                    ).delete()
                    rule.delete()
                    rule = create_draft(copy.deepcopy(specs[rule_id]), preparer)
                else:
                    prep = SoDPreparation.objects.filter(
                        subject_type=SUBJECT_POLICY_VERSION, subject_id=rule.pk,
                    ).first()
                    self.stdout.write(
                        f"already published {rule_id} id={rule.pk} "
                        f"preparer={getattr(prep, 'preparer_id', None)} "
                        f"publisher={event.user_id}"
                    )
                    already += 1
                    continue
            if rule.lifecycle == ComplianceRule.LIFECYCLE_DRAFT:
                rule = submit(rule, preparer)
            if rule.lifecycle != ComplianceRule.LIFECYCLE_IN_REVIEW:
                raise CommandError(f"{rule_id} is {rule.lifecycle}, expected in_review")
            try:
                publish(rule, preparer)
            except SoDViolation as exc:
                if exc.code != "sod_same_actor":
                    raise
                same_actor_refused += 1
            else:
                raise CommandError(f"same-actor publish was allowed for {rule_id}")
            try:
                rule = publish(rule, publisher)
            except (PolicyTransitionError, SoDViolation) as exc:
                raise CommandError(f"publish {rule_id} failed: {exc}") from exc
            published += 1
            prep = SoDPreparation.objects.get(
                subject_type=SUBJECT_POLICY_VERSION, subject_id=rule.pk,
            )
            event = GovernanceEvent.objects.filter(
                entity_type="ComplianceRule", entity_id=rule.pk, action="publish",
            ).order_by("-timestamp").first()
            self.stdout.write(
                f"published {rule_id} id={rule.pk} preparer={prep.preparer_id} "
                f"publisher={event.user_id} event={event.pk}"
            )

        after = _snapshot_2026_1()
        if before != after:
            raise CommandError("version 2026.1 bytes changed during publish")
        auth = ComplianceRule.objects.filter(
            rule_id__in=SHEET_RULE_IDS,
            version=SHEET_VERSION,
            lifecycle=ComplianceRule.LIFECYCLE_AUTHORITATIVE,
            is_authoritative=True,
        ).count()
        self.stdout.write(self.style.SUCCESS(
            f"DONE published_now={published} already={already} "
            f"same_actor_refused={same_actor_refused} authoritative={auth} "
            f"preparer={preparer.username}:{preparer.pk} publisher={publisher.username}:{publisher.pk}"
        ))
