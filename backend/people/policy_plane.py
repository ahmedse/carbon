# People plane for the domain-free policy lifecycle.
# Payroll formula execution and regulation packs stay here.
# Catalog never imports this module; People registers it.

from __future__ import annotations

import copy
from datetime import datetime

from django.db.models import Q

from catalog.policy_lifecycle import (
    AUTHORITATIVE,
    DRAFT,
    evaluate_examples,
    evaluate_floors,
)
from people.governance.sod import (
    ACTION_PUBLISH,
    SUBJECT_POLICY_VERSION,
    get_preparer,
    record_preparer,
    require_distinct_actor,
)
from people.models import ComplianceRule

_MUTABLE = {
    "name",
    "description",
    "jurisdiction",
    "category",
    "effective_date",
    "formula_ref",
    "source_citation",
    "inputs_schema",
    "provenance",
    "test_cases",
    "rule_id",
    "version",
}


def _as_date(value):
    if value in (None, ""):
        return None
    if hasattr(value, "year") and hasattr(value, "month"):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


class PeoplePolicyPlane:
    """First store: ComplianceRule. Lifecycle writes go through catalog."""

    key = "versioned_policy"
    entity_type = "ComplianceRule"

    def find(self, pk):
        return ComplianceRule.objects.filter(pk=pk).first()

    def lock(self, pk):
        return ComplianceRule.objects.select_for_update().get(pk=pk)

    def policy_id(self, row) -> str:
        return row.rule_id

    def version_of(self, row) -> str:
        return row.version

    def display_name(self, row) -> str:
        return row.name

    def state(self, row) -> str:
        return row.lifecycle

    def citation(self, row) -> str:
        return row.source_citation or ""

    def effective_on(self, row) -> str:
        value = row.effective_date
        if value is None:
            return ""
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)[:10]

    def preparer_id(self, row):
        preparer = get_preparer(
            subject_type=SUBJECT_POLICY_VERSION,
            subject_id=row.pk,
        )
        return preparer.pk if preparer else None

    def iter_rows(self, *, state="", query=""):
        qs = ComplianceRule.objects.all().order_by("rule_id", "version")
        if state:
            qs = qs.filter(lifecycle=state)
        text = (query or "").strip()
        if text:
            qs = qs.filter(
                Q(rule_id__icontains=text)
                | Q(version__icontains=text)
                | Q(name__icontains=text)
            )
        return list(qs)

    def set_state(self, row, lifecycle, authoritative):
        row.lifecycle = lifecycle
        row.is_authoritative = authoritative
        row.save()

    def stamp(self, row, user):
        record_preparer(
            subject_type=SUBJECT_POLICY_VERSION,
            subject_id=row.pk,
            user=user,
            process_key="people.policy.publish",
            overwrite=True,
        )

    def require_distinct(self, row, user):
        require_distinct_actor(
            subject_type=SUBJECT_POLICY_VERSION,
            subject_id=row.pk,
            actor=user,
            action=ACTION_PUBLISH,
        )

    def create(self, data):
        from people.serializers import ComplianceRuleSerializer

        payload = dict(data)
        payload.pop("is_authoritative", None)
        payload.pop("lifecycle", None)
        serializer = ComplianceRuleSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        return serializer.save(lifecycle=DRAFT, is_authoritative=False)

    def apply(self, row, data):
        from people.serializers import ComplianceRuleSerializer

        payload = {key: value for key, value in dict(data).items() if key in _MUTABLE}
        serializer = ComplianceRuleSerializer(row, data=payload, partial=True)
        serializer.is_valid(raise_exception=True)
        return serializer.save(lifecycle=DRAFT, is_authoritative=False)

    def remove(self, row):
        row.delete()

    def version_exists(self, row, version: str) -> bool:
        return ComplianceRule.objects.filter(rule_id=row.rule_id, version=version).exists()

    def next_version(self, row) -> str:
        current = row.version
        head, sep, tail = current.rpartition(".")
        if sep and tail.isdigit():
            number = int(tail)
            while True:
                number += 1
                candidate = f"{head}.{number}"
                if not ComplianceRule.objects.filter(
                    rule_id=row.rule_id, version=candidate,
                ).exists():
                    return candidate
        number = 2
        while True:
            candidate = f"{current}.{number}"
            if not ComplianceRule.objects.filter(
                rule_id=row.rule_id, version=candidate,
            ).exists():
                return candidate
            number += 1

    def clone(self, row, version, effective_date):
        draft = ComplianceRule(
            rule_id=row.rule_id,
            version=version,
            name=row.name,
            description=row.description,
            jurisdiction=row.jurisdiction,
            category=row.category,
            effective_date=_as_date(effective_date) or row.effective_date,
            formula_ref=row.formula_ref,
            source_citation=row.source_citation,
            inputs_schema=copy.deepcopy(row.inputs_schema or {}),
            is_authoritative=False,
            lifecycle=DRAFT,
            provenance=copy.deepcopy(row.provenance) if row.provenance else None,
            test_cases=copy.deepcopy(row.test_cases or []),
        )
        draft.save()
        return draft

    def authoritative_others(self, row):
        return list(
            ComplianceRule.objects.select_for_update().filter(
                rule_id=row.rule_id,
                lifecycle=AUTHORITATIVE,
            ).exclude(pk=row.pk)
        )

    def prior_authoritative(self, row):
        return (
            ComplianceRule.objects.filter(
                rule_id=row.rule_id,
                lifecycle=AUTHORITATIVE,
            )
            .exclude(pk=row.pk)
            .order_by("-effective_date")
            .first()
        )

    def snapshot(self, row):
        if row is None:
            return None
        return {
            "name": row.name,
            "citation": row.source_citation or "",
            "effective_date": self.effective_on(row),
            "schema": row.inputs_schema or {},
            "examples": row.test_cases or [],
        }

    def example_report(self, row) -> dict:
        from people.calculation_engine import calculate

        def run_case(inputs):
            return calculate(row, inputs, allow_non_authoritative=True)

        return evaluate_examples(row.test_cases or [], run_case)

    def _resolve(self, schema: dict):
        from people.regulation_pack import PackMissing, load_pack

        ref = schema.get("regulation_ref") or {}
        if ref.get("pack"):
            version = ref.get("version")
            try:
                return load_pack(ref["pack"], version)
            except PackMissing:
                return {
                    "_missing": True,
                    "code": "regulation_missing",
                    "error": (
                        f"cited regulation pack {ref.get('pack')} {version} is missing"
                    ),
                }
        rule_id = ref.get("rule_id")
        version = ref.get("version")
        if not rule_id or not version:
            return None
        cited = ComplianceRule.objects.filter(rule_id=rule_id, version=version).first()
        if cited is None:
            return {
                "_missing": True,
                "code": "regulation_missing",
                "error": f"cited regulation {rule_id} {version} is missing",
            }
        return {
            "floors": (cited.inputs_schema or {}).get("floors") or [],
            "funds": [],
        }

    def floor_report(self, row) -> dict:
        return evaluate_floors(row.inputs_schema or {}, self._resolve)


PLANE = PeoplePolicyPlane()


def register():
    from catalog.policy_lifecycle import register_plane

    register_plane(PLANE)
