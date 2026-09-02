"""Tests for F1-B entity mention annotation (ai/engine_runtime.py).

Deterministic, no live LLM: the annotator is a pure answer post-processor that
resolves user-accessible DataTable/DQRule/Module/OrgUnit names via the ORM and
rewrites matching spans as serialized refs (``[[kind:id:label]]``) for the
frontend EntityChip.

Scoping assertions use the canonical ``accounts.rbac_utils`` visibility helpers
through a real user + ``ScopedRole``, so these tests also prove the annotator
never resolves a name outside the requesting user's org subtree.
"""
import pytest

from core.models import Module
from dataschema.models import DataTable
from dq.models import DQRule, RuleFieldAssignment
from mdm.models import OrgUnit

from ai.engine_runtime import _annotate_entity_mentions


# ── Fixture helpers (plain factories, no LLM) ─────────────────────────────


def _make_org(name, slug, parent=None):
    return OrgUnit.objects.create(
        name=name, slug=slug, code=slug[:8].upper(), org_type="division",
        parent=parent,
    )


def _make_module(name, org):
    return Module.objects.create(name=name, org_unit=org)


def _make_table(name, module):
    return DataTable.objects.create(
        name=name, title=name.replace("_", " ").title(), module=module,
    )


def _make_rule(name, table):
    rule = DQRule.objects.create(name=name, rule_type="not_null", is_active=True)
    RuleFieldAssignment.objects.create(rule=rule, data_table=table)
    return rule


# ── Resolution + ref emission ──────────────────────────────────────────────


@pytest.mark.django_db
def test_annotates_table_by_name_with_correct_id(make_scoped_user):
    org = _make_org("South Valley", "south-valley")
    module = _make_module("Carbon Ledger", org)
    table = _make_table("emissions_fuel", module)
    user = make_scoped_user("table-user", group="dataowners_group", org=org)

    out = _annotate_entity_mentions("See the emissions_fuel table.", user.pk)

    assert out == f"See the [[table:{table.id}:emissions_fuel]] table."


@pytest.mark.django_db
def test_annotates_rule_and_org_unit_refs(make_scoped_user):
    org = _make_org("South Valley", "south-valley")
    module = _make_module("Carbon Ledger", org)
    table = _make_table("emissions_fuel", module)
    rule = _make_rule("email_not_null", table)
    user = make_scoped_user("multi-user", group="dataowners_group", org=org)

    out = _annotate_entity_mentions(
        "Rule email_not_null applies to South Valley.", user.pk,
    )

    assert f"[[rule:{rule.id}:email_not_null]]" in out
    assert f"[[org-unit:{org.id}:South Valley]]" in out


@pytest.mark.django_db
def test_annotates_module_ref(make_scoped_user):
    org = _make_org("South Valley", "south-valley")
    module = _make_module("Carbon Ledger", org)
    user = make_scoped_user("module-user", group="dataowners_group", org=org)

    out = _annotate_entity_mentions("Open the Carbon Ledger area.", user.pk)

    assert f"[[module:{module.id}:Carbon Ledger]]" in out


# ── Matching semantics ─────────────────────────────────────────────────────


@pytest.mark.django_db
def test_case_insensitive_and_word_boundary(make_scoped_user):
    org = _make_org("South Valley", "south-valley")
    user = make_scoped_user("word-user", group="dataowners_group", org=org)

    # Case-insensitive match on the exact phrase.
    assert f"[[org-unit:{org.id}:South Valley]]" in _annotate_entity_mentions(
        "visit south valley today.", user.pk,
    )
    # Concatenated (no word boundary) must NOT match.
    assert "[[org-unit" not in _annotate_entity_mentions(
        "the southvalley region is large.", user.pk,
    )


@pytest.mark.django_db
def test_longest_name_wins(make_scoped_user):
    root = _make_org("South Valley", "south-valley")
    campus = _make_org("South Valley Campus", "south-valley-campus", parent=root)
    user = make_scoped_user("longest-user", group="dataowners_group", org=root)

    out = _annotate_entity_mentions("Welcome to South Valley Campus.", user.pk)

    assert out == f"Welcome to [[org-unit:{campus.id}:South Valley Campus]]."
    # The shorter prefix "South Valley" must not be separately annotated.
    assert f"[[org-unit:{root.id}:South Valley]]" not in out


# ── Scoping / no cross-tenant leakage ──────────────────────────────────────


@pytest.mark.django_db
def test_no_cross_scope_leak(make_scoped_user):
    org_a = _make_org("North Campus", "north-campus")
    org_b = _make_org("South Campus", "south-campus")
    mod_a = _make_module("Electricity", org_a)
    mod_b = _make_module("Water", org_b)
    table_a = _make_table("electricity_usage", mod_a)
    table_b = _make_table("water_usage", mod_b)
    rule_a = _make_rule("email_not_null", table_a)
    rule_b = _make_rule("phone_valid", table_b)
    user = make_scoped_user("scoped-user", group="dataowners_group", org=org_a)

    out = _annotate_entity_mentions(
        "electricity_usage water_usage email_not_null phone_valid "
        "Electricity Water North Campus South Campus",
        user.pk,
    )

    # In-scope entities (org A) are annotated.
    assert f"[[table:{table_a.id}:electricity_usage]]" in out
    assert f"[[rule:{rule_a.id}:email_not_null]]" in out
    assert f"[[module:{mod_a.id}:Electricity]]" in out
    assert f"[[org-unit:{org_a.id}:North Campus]]" in out

    # Out-of-scope entities (org B) are never annotated.
    assert "water_usage]]" not in out
    assert "phone_valid]]" not in out
    assert "Water]]" not in out
    assert f"[[org-unit:{org_b.id}:South Campus]]" not in out


# ── Protected regions ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_skips_code_fence(make_scoped_user):
    org = _make_org("South Valley", "south-valley")
    user = make_scoped_user("fence-user", group="dataowners_group", org=org)

    answer = "```\nSouth Valley\n```"
    assert _annotate_entity_mentions(answer, user.pk) == answer


@pytest.mark.django_db
def test_skips_url(make_scoped_user):
    org = _make_org("South Valley", "south-valley")
    module = _make_module("Carbon Ledger", org)
    table = _make_table("emissions_fuel", module)
    user = make_scoped_user("url-user", group="dataowners_group", org=org)

    answer = "See https://example.com/emissions_fuel for details."
    assert _annotate_entity_mentions(answer, user.pk) == answer


@pytest.mark.django_db
def test_skips_existing_span(make_scoped_user):
    org = _make_org("South Valley", "south-valley")
    module = _make_module("Carbon Ledger", org)
    table = _make_table("emissions_fuel", module)
    user = make_scoped_user("span-user", group="dataowners_group", org=org)

    answer = "Pre-annotated: [[table:1:emissions_fuel]]"
    assert _annotate_entity_mentions(answer, user.pk) == answer


@pytest.mark.django_db
def test_plain_mention_annotated_despite_protected_occurrences(make_scoped_user):
    org = _make_org("South Valley", "south-valley")
    module = _make_module("Carbon Ledger", org)
    table = _make_table("emissions_fuel", module)
    user = make_scoped_user("combined-user", group="dataowners_group", org=org)

    answer = (
        "```\nemissions_fuel\n```\n"
        "https://example.com/emissions_fuel\n"
        "[[table:1:emissions_fuel]]\n"
        "plain emissions_fuel"
    )
    out = _annotate_entity_mentions(answer, user.pk)

    assert "```\nemissions_fuel\n```" in out
    assert "https://example.com/emissions_fuel" in out
    assert "[[table:1:emissions_fuel]]" in out
    assert f"plain [[table:{table.id}:emissions_fuel]]" in out


# ── Failure path ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_failure_returns_answer_unchanged():
    # No scope → no user → no resolution → answer unchanged.
    assert _annotate_entity_mentions("emissions_fuel here", None) == "emissions_fuel here"
    # Unresolvable scope handle → answer unchanged.
    assert _annotate_entity_mentions("emissions_fuel", "no-such-user") == "emissions_fuel"


@pytest.mark.django_db
def test_no_visible_entities_returns_answer_unchanged():
    from django.contrib.auth import get_user_model

    # A user with no roles at all can see nothing, even though the entities exist.
    org = _make_org("South Valley", "south-valley")
    module = _make_module("Carbon Ledger", org)
    _make_table("emissions_fuel", module)
    user = get_user_model().objects.create_user(
        username="bare-user", password="secret123",
    )

    assert _annotate_entity_mentions("emissions_fuel and South Valley", user.pk) == (
        "emissions_fuel and South Valley"
    )
