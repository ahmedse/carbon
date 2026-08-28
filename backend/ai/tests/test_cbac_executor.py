"""Phase A — CBAC org-scoping of AI host executor endpoints (Tier 2).

Verifies the RULE_12 / RULE_21 invariants enforced in the chat path:

* GLOBAL endpoints (factors, gwp, periods) return data for any authenticated
  user, and EXCLUDE inactive factors — no org filtering (factors are global).
* ORG-SCOPED endpoints (calculation summary, chairman overview) resolve the
  user through ``get_visible_module_ids``:
    - superuser / global admin  -> unrestricted (sees ALL orgs)
    - scoped user              -> ONLY their org subtree
    - multi-org user           -> union of granted orgs
* Read-only roles (viewers_group) still get read access (visibility roles).
* Missing/invalid user -> 401.

Fixture ``org_a_and_b`` creates two orgs each with one module + one
calculation with DIFFERENT footprints (1000 kWh @0.4584 vs 2000 kWh @1.0),
so summary totals discriminate between the two orgs.
"""
import pytest

from ai.tests.conftest import call, carbon_executor
from accounts.rbac_utils import get_visible_module_ids


@pytest.mark.django_db(transaction=True)
class TestFactorEndpointsGlobal:
    """RULE_12 — emission factors are GLOBAL reference data."""

    def test_factors_visible_to_org_scoped_user(self, make_scoped_user, org_a_and_b, seeded_factors):
        user = make_scoped_user("analyst-a", group="viewers_group", org=org_a_and_b["org_a"])
        resp = call(carbon_executor(user), "_emission_factors_in_process")
        assert resp["status_code"] == 200
        codes = {f["code"] for f in resp["data"]["results"]}
        assert "EG_GRID_2024" in codes
        assert "DIESEL_2024" in codes

    def test_factors_exclude_inactive(self, make_scoped_user, seeded_factors):
        user = make_scoped_user("analyst-a", group="viewers_group")
        resp = call(carbon_executor(user), "_emission_factors_in_process")
        assert resp["status_code"] == 200
        codes = {f["code"] for f in resp["data"]["results"]}
        assert "OLD_FACTOR" not in codes  # is_active=False must never surface

    def test_factors_require_auth(self, org_a_and_b):
        executor = carbon_executor(None)  # host_user_id missing
        resp = call(executor, "_emission_factors_in_process")
        assert resp["status_code"] == 401

    def test_factors_reject_non_get(self, make_scoped_user, seeded_factors):
        user = make_scoped_user("analyst-a", group="viewers_group")
        resp = call(carbon_executor(user), "_emission_factors_in_process",
                    method="POST", body={})
        assert resp["status_code"] == 405


@pytest.mark.django_db(transaction=True)
class TestCalculationSummaryOrgScoped:
    """ORG-SCOPED — summary must reflect exactly the user's visible subtree."""

    def test_superuser_sees_all_orgs(self, make_scoped_user, org_a_and_b):
        user = make_scoped_user("boss", superuser=True)
        assert get_visible_module_ids(user) is None  # unrestricted
        resp = call(carbon_executor(user), "_calculation_summary_in_process")
        assert resp["status_code"] == 200
        summary = resp["data"]
        assert summary["total_calculations"] == 2  # A (1000 kWh) + B (2000 kWh)
        module_names = {m["module_name"] for m in summary["by_module"]}
        assert module_names == {"Elec Alpha", "Elec Beta"}

    def test_restricted_user_sees_own_org_only(self, make_scoped_user, org_a_and_b):
        user = make_scoped_user("analyst-a", group="viewers_group", org=org_a_and_b["org_a"])
        visible = get_visible_module_ids(user)
        assert org_a_and_b["module_a"].pk in visible
        assert org_a_and_b["module_b"].pk not in visible

        resp = call(carbon_executor(user), "_calculation_summary_in_process")
        assert resp["status_code"] == 200
        summary = resp["data"]
        assert summary["total_calculations"] == 1
        module_names = {m["module_name"] for m in summary["by_module"]}
        assert module_names == {"Elec Alpha"}

    def test_multi_org_user_sees_union(self, make_scoped_user, org_a_and_b):
        user = make_scoped_user("analyst-ab", group="viewers_group", org=org_a_and_b["org_a"])
        from accounts.models import ScopedRole
        from django.contrib.auth.models import Group
        group = Group.objects.get(name="viewers_group")
        ScopedRole.objects.create(
            user=user, group=group, org_unit=org_a_and_b["org_b"], module=None,
            is_active=True,
        )
        visible = get_visible_module_ids(user)
        assert org_a_and_b["module_a"].pk in visible
        assert org_a_and_b["module_b"].pk in visible

        resp = call(carbon_executor(user), "_calculation_summary_in_process")
        assert resp["status_code"] == 200
        assert resp["data"]["total_calculations"] == 2

    def test_period_filter_applied(self, make_scoped_user, org_a_and_b):
        user = make_scoped_user("boss", superuser=True)
        resp = call(carbon_executor(user), "_calculation_summary_in_process",
                    params={"reporting_period_id": org_a_and_b["calc_a"].reporting_period_id})
        assert resp["status_code"] == 200
        assert resp["data"]["period_id"] == org_a_and_b["calc_a"].reporting_period_id
        assert resp["data"]["total_calculations"] == 1  # only A's period

    def test_read_only_role_can_read(self, make_scoped_user, org_a_and_b):
        """viewers_group is a visibility role -> read allowed, 200 not 403."""
        user = make_scoped_user("viewer", group="viewers_group", org=org_a_and_b["org_a"])
        resp = call(carbon_executor(user), "_calculation_summary_in_process")
        assert resp["status_code"] == 200
        assert resp["data"]["total_calculations"] == 1

    def test_summary_requires_auth(self, org_a_and_b):
        resp = call(carbon_executor(None), "_calculation_summary_in_process")
        assert resp["status_code"] == 401


@pytest.mark.django_db(transaction=True)
class TestChairmanOverviewOrgScoped:
    def test_superuser_footprint_spans_all(self, make_scoped_user, org_a_and_b):
        user = make_scoped_user("boss", superuser=True)
        resp = call(carbon_executor(user), "_chairman_overview_in_process")
        assert resp["status_code"] == 200
        # A: 1000*0.4584 = 458.4 kg -> 0.46 t ; B: 2000*1.0 = 2000 kg -> 2 t
        # headline rounds to 2 dp: 2.46
        assert float(resp["data"]["headline"]["footprint_tonnes"]) == pytest.approx(2.46, abs=0.01)

    def test_restricted_user_footprint_own_org_only(self, make_scoped_user, org_a_and_b):
        user = make_scoped_user("analyst-a", group="viewers_group", org=org_a_and_b["org_a"])
        resp = call(carbon_executor(user), "_chairman_overview_in_process")
        assert resp["status_code"] == 200
        assert float(resp["data"]["headline"]["footprint_tonnes"]) == pytest.approx(0.46, abs=0.01)

    def test_chairman_requires_auth(self, org_a_and_b):
        resp = call(carbon_executor(None), "_chairman_overview_in_process")
        assert resp["status_code"] == 401
