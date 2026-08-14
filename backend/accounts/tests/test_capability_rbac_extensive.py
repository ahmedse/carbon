"""
Comprehensive Capability-Based RBAC Test Suite.

Covers:
  - Capability definition integrity
  - Inheritance (IMPLIES) expansion — transitive closure
  - Group → capability mapping correctness
  - Utility functions (get_user_capabilities, has_capability, has_any, has_all)
  - Permission classes (AdminOrSuperuserOnly, ReadAnyWriteAdmin)
  - API integration (me_context, capability-matrix endpoint)
  - Edge cases (deactivated roles, multiple roles, empty sets, None user, wildcard)
  - Cross-domain (catalog_lead, dq_lead, mdm_lead)
  - Boundary (unknown group, unknown capability, superuser, unauthenticated)
"""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import ScopedRole, User
from accounts.capabilities import (
    # Capability definitions
    ALL_CAPABILITIES,
    IMPLIES,
    GROUP_CAPABILITIES,
    # Capability constants
    CARBON_VIEW_CONSOLE,
    CARBON_VIEW_DASHBOARD,
    CARBON_VIEW_ANALYTICS,
    CARBON_ENTER_DATA,
    CARBON_VIEW_MY_DATA,
    CARBON_MANAGE_EMISSION_FACTORS,
    CARBON_MANAGE_CALCULATION_RULES,
    CARBON_MANAGE_GWP,
    CARBON_MANAGE_SBTI_TARGETS,
    CARBON_MANAGE_REPORTING_PERIODS,
    CARBON_TRIGGER_CALCULATIONS,
    CARBON_VERIFY_DATA,
    CARBON_GENERATE_REPORTS,
    CARBON_VIEW_CALCULATIONS,
    CARBON_VIEW_VERIFICATION,
    CARBON_VIEW_REPORTING_PERIODS,
    CATALOG_VIEW,
    CATALOG_MANAGE_PRODUCTS,
    CATALOG_MANAGE_METADATA,
    CATALOG_MANAGE_POLICIES,
    CATALOG_VIEW_GOVERNANCE,
    DQ_VIEW,
    DQ_MANAGE_RULES,
    MDM_VIEW,
    MDM_MANAGE,
    CONNECTIONS_VIEW,
    CONNECTIONS_MANAGE,
    IMPORTEXPORT_VIEW,
    IMPORTEXPORT_MANAGE,
    DATASCHEMA_VIEW,
    DATASCHEMA_MANAGE,
    EVIDENCE_VIEW,
    EVIDENCE_MANAGE,
    AI_VIEW_CONSOLE,
    AI_MANAGE_CONSOLE,
    PLATFORM_ADMIN,
    PLATFORM_MANAGE_USERS,
    PLATFORM_MANAGE_GROUPS,
    PLATFORM_MANAGE_ORG_UNITS,
    PLATFORM_MANAGE_ACCESS,
    PLATFORM_VIEW_AUDIT,
    PLATFORM_MANAGE_APPS,
    # Functions
    _expand_capabilities,
    get_user_capabilities,
    has_capability,
    has_any_capability,
    has_all_capabilities,
    get_capability,
    get_capability_matrix,
    get_capabilities_for_frontend,
)


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════

def _make_user_with_groups(groups, username="testuser", is_superuser=False):
    """Create a user and assign active ScopedRoles for the given group names."""
    user = User.objects.create_user(username=username, password="test")
    user.is_superuser = is_superuser
    user.save()
    for g in groups:
        group, _ = Group.objects.get_or_create(name=g)
        ScopedRole.objects.create(user=user, group=group, is_active=True)
    return user


@pytest.fixture
def superuser():
    return _make_user_with_groups([], username="super", is_superuser=True)

@pytest.fixture
def admin_user():
    return _make_user_with_groups(["admin"], username="admin")

@pytest.fixture
def carbon_lead_user():
    return _make_user_with_groups(["carbon_lead"], username="clead")

@pytest.fixture
def catalog_lead_user():
    return _make_user_with_groups(["catalog_lead"], username="catlead")

@pytest.fixture
def mdm_lead_user():
    return _make_user_with_groups(["mdm_lead"], username="mdmlead")

@pytest.fixture
def dq_lead_user():
    return _make_user_with_groups(["dq_lead"], username="dqlead")

@pytest.fixture
def data_owner_user():
    return _make_user_with_groups(["dataowners_group"], username="downer")

@pytest.fixture
def analyst_user():
    return _make_user_with_groups(["analysts_group"], username="analyst")

@pytest.fixture
def viewer_user():
    return _make_user_with_groups(["viewers_group"], username="viewer")

@pytest.fixture
def auditor_user():
    return _make_user_with_groups(["auditors_group"], username="auditor")

@pytest.fixture
def multi_role_user():
    """User with multiple ScopedRoles — dataowners_group + analysts_group."""
    u = User.objects.create_user(username="multi", password="test")
    u.save()
    for g in ["dataowners_group", "analysts_group"]:
        group, _ = Group.objects.get_or_create(name=g)
        ScopedRole.objects.create(user=u, group=group, is_active=True)
    return u

@pytest.fixture
def deactivated_role_user():
    """User with a deactivated ScopedRole (carbon_lead but is_active=False)."""
    u = User.objects.create_user(username="deactivated", password="test")
    u.save()
    group, _ = Group.objects.get_or_create(name="carbon_lead")
    ScopedRole.objects.create(user=u, group=group, is_active=False)
    return u

@pytest.fixture
def no_role_user():
    """User with zero ScopedRoles."""
    return User.objects.create_user(username="norole", password="test")

@pytest.fixture
def unauthenticated_user():
    """Anonymous user (used for permission checks)."""
    from django.contrib.auth.models import AnonymousUser
    return AnonymousUser()


# ═══════════════════════════════════════════════════════════════════════
# SECTION 1: CAPABILITY DEFINITION INTEGRITY
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCapabilityDefinitions:
    """Verify every capability is well-formed and consistent."""

    def test_all_capabilities_have_required_fields(self):
        """Every capability must have key, domain, action, label, description."""
        for key, cap in ALL_CAPABILITIES.items():
            assert cap.key == key, f"Key mismatch: {cap.key} vs {key}"
            assert cap.domain, f"Missing domain: {key}"
            assert cap.action, f"Missing action: {key}"
            assert cap.label, f"Missing label: {key}"
            assert cap.description, f"Missing description: {key}"

    def test_capability_keys_are_namespaced(self):
        """Every key must follow domain:action pattern."""
        for key in ALL_CAPABILITIES:
            parts = key.split(":")
            assert len(parts) == 2, f"Key '{key}' should be domain:action"
            domain, action = parts
            assert domain, f"Empty domain in '{key}'"
            assert action, f"Empty action in '{key}'"
            assert " " not in key, f"Space in key '{key}'"

    def test_no_duplicate_capability_keys(self):
        """No two capabilities should have the same key."""
        assert len(ALL_CAPABILITIES) == len({c.key for c in ALL_CAPABILITIES.values()})

    def test_capability_count(self):
        """Sanity check: we expect ~38 capabilities."""
        count = len(ALL_CAPABILITIES)
        assert count >= 30, f"Expected at least 30 capabilities, got {count}"
        assert count <= 50, f"Expected at most 50 capabilities, got {count}"

    @pytest.mark.parametrize("domain,min_count", [
        ("carbon", 15),
        ("platform", 7),
        ("catalog", 4),
        ("dq", 1),
        ("mdm", 1),
        ("connections", 1),
        ("importexport", 1),
        ("dataschema", 1),
    ])
    def test_domain_has_minimum_capabilities(self, domain, min_count):
        """Each domain should have its expected capabilities."""
        domain_caps = [c for c in ALL_CAPABILITIES.values() if c.domain == domain]
        assert len(domain_caps) >= min_count, \
            f"Domain '{domain}' has {len(domain_caps)} caps, expected at least {min_count}"


# ═══════════════════════════════════════════════════════════════════════
# SECTION 2: CAPABILITY INHERITANCE (IMPLIES)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCapabilityInheritance:
    """Verify IMPLIES transitive closure works correctly."""

    def test_expand_empty_set(self):
        """Expanding empty set returns empty set."""
        result = _expand_capabilities(set())
        assert result == frozenset()

    def test_expand_no_inheritance(self):
        """A capability with no IMPLIES entries stays unchanged."""
        # view_console is a leaf — nothing implies it further
        result = _expand_capabilities({CARBON_VIEW_CONSOLE.key})
        assert CARBON_VIEW_CONSOLE.key in result
        # It should not expand to anything else
        assert result == {CARBON_VIEW_CONSOLE.key}

    def test_expand_single_level(self):
        """manage_emission_factors → view_console (single level)."""
        result = _expand_capabilities({CARBON_MANAGE_EMISSION_FACTORS.key})
        assert CARBON_MANAGE_EMISSION_FACTORS.key in result
        assert CARBON_VIEW_CONSOLE.key in result, \
            "manage_emission_factors should imply view_console"

    def test_expand_multi_level(self):
        """platform:admin → platform:manage_users, etc. (multi-level chain)."""
        result = _expand_capabilities({PLATFORM_ADMIN.key})
        assert PLATFORM_ADMIN.key in result
        assert PLATFORM_MANAGE_USERS.key in result
        assert PLATFORM_MANAGE_GROUPS.key in result
        assert PLATFORM_MANAGE_ORG_UNITS.key in result
        assert PLATFORM_MANAGE_ACCESS.key in result
        assert PLATFORM_VIEW_AUDIT.key in result
        assert PLATFORM_MANAGE_APPS.key in result

    def test_expand_transitive_closure(self):
        """enter_data → view_my_data → view_console. All should be present."""
        result = _expand_capabilities({CARBON_ENTER_DATA.key})
        assert CARBON_ENTER_DATA.key in result
        assert CARBON_VIEW_MY_DATA.key in result, \
            "enter_data should imply view_my_data"
        assert CARBON_VIEW_CONSOLE.key in result, \
            "view_my_data implied by enter_data should also be present"

    def test_expand_multiple_caps(self):
        """Expanding multiple capabilities should merge all inheritances."""
        caps = {CARBON_MANAGE_EMISSION_FACTORS.key, CARBON_ENTER_DATA.key}
        result = _expand_capabilities(caps)
        assert CARBON_VIEW_CONSOLE.key in result
        assert CARBON_VIEW_MY_DATA.key in result

    def test_expand_is_idempotent(self):
        """Expanding already-expanded set should not change it."""
        first = _expand_capabilities({CARBON_MANAGE_EMISSION_FACTORS.key})
        second = _expand_capabilities(set(first))
        assert first == second

    def test_every_implies_key_exists_in_all_capabilities(self):
        """Every key in IMPLIES and every implied value must be valid."""
        for from_key, to_set in IMPLIES.items():
            assert from_key in ALL_CAPABILITIES, f"IMPLIES key '{from_key}' not in ALL_CAPABILITIES"
            for to_key in to_set:
                assert to_key in ALL_CAPABILITIES, \
                    f"IMPLIES target '{to_key}' (from '{from_key}') not in ALL_CAPABILITIES"

    def test_no_self_reference_in_implies(self):
        """A capability should not imply itself."""
        for from_key, to_set in IMPLIES.items():
            assert from_key not in to_set, \
                f"Self-referencing IMPLIES: {from_key} → {from_key}"

    def test_no_circular_implies(self):
        """IMPLIES should not have direct cycles A→B and B→A."""
        for from_key, to_set in IMPLIES.items():
            for to_key in to_set:
                if to_key in IMPLIES:
                    assert from_key not in IMPLIES[to_key], \
                        f"Circular IMPLIES: {from_key} ↔ {to_key}"


# ═══════════════════════════════════════════════════════════════════════
# SECTION 3: GROUP → CAPABILITY MAPPING
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestGroupCapabilityMappings:
    """Verify GROUP_CAPABILITIES are correct and inheritance-aware."""

    def test_all_groups_in_mapping_are_declared(self):
        """Every group name used in GROUP_CAPABILITIES should be documented."""
        expected_groups = {
            "admin", "admins_group",
            "carbon_lead", "catalog_lead", "mdm_lead", "dq_lead",
            "dataowners_group", "analysts_group", "viewers_group", "auditors_group",
        }
        assert set(GROUP_CAPABILITIES.keys()) == expected_groups, \
            f"Unexpected groups: {set(GROUP_CAPABILITIES.keys()) ^ expected_groups}"

    def test_admin_has_wildcard(self):
        """Admin groups should have '*' wildcard granting all capabilities."""
        assert "*" in GROUP_CAPABILITIES["admin"]
        assert "*" in GROUP_CAPABILITIES["admins_group"]

    def test_carbon_lead_has_all_admin_caps(self):
        """carbon_lead should have emission factor, calculation, GWP, SBTi, period management."""
        caps = GROUP_CAPABILITIES["carbon_lead"]
        assert CARBON_MANAGE_EMISSION_FACTORS.key in caps
        assert CARBON_MANAGE_CALCULATION_RULES.key in caps
        assert CARBON_MANAGE_GWP.key in caps
        assert CARBON_MANAGE_SBTI_TARGETS.key in caps
        assert CARBON_MANAGE_REPORTING_PERIODS.key in caps
        assert CARBON_TRIGGER_CALCULATIONS.key in caps
        assert CARBON_VERIFY_DATA.key in caps
        assert CARBON_ENTER_DATA.key in caps
        assert CARBON_GENERATE_REPORTS.key in caps
        assert CARBON_VIEW_ANALYTICS.key in caps

    def test_carbon_lead_should_not_have_platform_caps(self):
        """carbon_lead should NOT have platform administration capabilities."""
        caps = GROUP_CAPABILITIES["carbon_lead"]
        assert PLATFORM_MANAGE_USERS.key not in caps
        assert PLATFORM_MANAGE_GROUPS.key not in caps
        assert PLATFORM_MANAGE_ORG_UNITS.key not in caps

    def test_catalog_lead_mapping(self):
        """catalog_lead should have catalog admin caps."""
        caps = GROUP_CAPABILITIES["catalog_lead"]
        assert CATALOG_MANAGE_PRODUCTS.key in caps
        assert CATALOG_MANAGE_METADATA.key in caps
        assert CATALOG_MANAGE_POLICIES.key in caps

    def test_mdm_lead_mapping(self):
        """mdm_lead should have MDM manage."""
        caps = GROUP_CAPABILITIES["mdm_lead"]
        assert MDM_MANAGE.key in caps

    def test_dq_lead_mapping(self):
        """dq_lead should have DQ manage rules."""
        caps = GROUP_CAPABILITIES["dq_lead"]
        assert DQ_MANAGE_RULES.key in caps

    def test_data_owner_mapping(self):
        """dataowners_group should have enter_data, view_calc, view_verify."""
        caps = GROUP_CAPABILITIES["dataowners_group"]
        assert CARBON_ENTER_DATA.key in caps
        assert CARBON_VIEW_CALCULATIONS.key in caps
        assert CARBON_VIEW_VERIFICATION.key in caps
        assert CARBON_VIEW_CONSOLE.key in caps

    def test_data_owner_should_not_have_admin_caps(self):
        """dataowners_group should NOT have admin caps."""
        caps = GROUP_CAPABILITIES["dataowners_group"]
        assert CARBON_MANAGE_EMISSION_FACTORS.key not in caps
        assert CARBON_MANAGE_CALCULATION_RULES.key not in caps
        assert CARBON_MANAGE_GWP.key not in caps
        assert CARBON_VERIFY_DATA.key not in caps

    def test_analyst_mapping(self):
        """analysts_group should have view + analytics + reports."""
        caps = GROUP_CAPABILITIES["analysts_group"]
        assert CARBON_VIEW_ANALYTICS.key in caps
        assert CARBON_GENERATE_REPORTS.key in caps
        assert CARBON_VIEW_CALCULATIONS.key in caps
        assert CARBON_VIEW_REPORTING_PERIODS.key in caps

    def test_analyst_should_not_have_write_or_admin(self):
        """analysts_group should NOT have enter_data or admin caps."""
        caps = GROUP_CAPABILITIES["analysts_group"]
        assert CARBON_ENTER_DATA.key not in caps
        assert CARBON_MANAGE_EMISSION_FACTORS.key not in caps

    def test_viewer_mapping(self):
        """viewers_group should have read-only view caps but no writes."""
        caps = GROUP_CAPABILITIES["viewers_group"]
        assert CARBON_VIEW_CALCULATIONS.key in caps
        assert CARBON_VIEW_CONSOLE.key in caps
        assert CARBON_VIEW_DASHBOARD.key in caps
        assert CARBON_VIEW_MY_DATA.key in caps
        assert CARBON_ENTER_DATA.key not in caps
        assert CARBON_GENERATE_REPORTS.key not in caps

    def test_auditor_mapping(self):
        """auditors_group should have view_verification and governance audit."""
        caps = GROUP_CAPABILITIES["auditors_group"]
        assert CARBON_VIEW_VERIFICATION.key in caps
        assert CATALOG_VIEW_GOVERNANCE.key in caps
        assert CARBON_ENTER_DATA.key not in caps

    def test_group_capabilities_only_use_valid_keys(self):
        """Every capability key used in GROUP_CAPABILITIES must exist in ALL_CAPABILITIES."""
        for group_name, caps in GROUP_CAPABILITIES.items():
            for cap in caps:
                if cap == "*":
                    continue
                assert cap in ALL_CAPABILITIES, \
                    f"Group '{group_name}' references unknown capability '{cap}'"

    # ── DD-2 (TASK-CBAC-TRUST-CORE-SWAP): data groups get trust-core view caps ──
    @pytest.mark.parametrize("group_name", [
        "dataowners_group", "analysts_group", "viewers_group", "auditors_group",
    ])
    def test_data_groups_have_trust_core_view_caps(self, group_name):
        """Every data group can view all trust-core apps."""
        caps = GROUP_CAPABILITIES[group_name]
        for view_cap in (
            CATALOG_VIEW, DQ_VIEW, MDM_VIEW,
            CONNECTIONS_VIEW, IMPORTEXPORT_VIEW, DATASCHEMA_VIEW, EVIDENCE_VIEW,
        ):
            assert view_cap.key in caps, f"{group_name} missing {view_cap.key}"

    # ── DD-3 (TASK-CBAC-TRUST-CORE-SWAP): evidence capabilities ──
    def test_evidence_capabilities_exist(self):
        """evidence:view + evidence:manage registered; manage implies view."""
        assert EVIDENCE_VIEW.key in ALL_CAPABILITIES
        assert EVIDENCE_MANAGE.key in ALL_CAPABILITIES
        assert EVIDENCE_VIEW.key in IMPLIES[EVIDENCE_MANAGE.key]

    def test_data_groups_do_not_get_evidence_manage(self):
        """Only admin/wildcard groups manage evidence; data groups view-only."""
        for group_name in ("dataowners_group", "analysts_group", "viewers_group", "auditors_group"):
            assert EVIDENCE_MANAGE.key not in GROUP_CAPABILITIES[group_name]

    # ── AI (Pulse) capabilities ──
    def test_ai_capabilities_exist(self):
        """ai:view_console + ai:manage_console registered; manage implies view."""
        assert AI_VIEW_CONSOLE.key in ALL_CAPABILITIES
        assert AI_MANAGE_CONSOLE.key in ALL_CAPABILITIES
        assert AI_VIEW_CONSOLE.key in IMPLIES[AI_MANAGE_CONSOLE.key]
        expanded = _expand_capabilities({AI_MANAGE_CONSOLE.key})
        assert AI_VIEW_CONSOLE.key in expanded


# ═══════════════════════════════════════════════════════════════════════
# SECTION 4: UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestUtilityFunctions:
    """get_user_capabilities, has_capability, has_any, has_all."""

    # ── get_user_capabilities ──────────────────────────────────

    def test_superuser_gets_wildcard(self, superuser):
        caps = get_user_capabilities(superuser)
        assert "*" in caps

    def test_superuser_has_all_caps(self, superuser):
        caps = get_user_capabilities(superuser)
        assert CARBON_VIEW_CONSOLE.key in caps or "*" in caps

    def test_admin_gets_all_caps(self, admin_user):
        caps = get_user_capabilities(admin_user)
        # "admin" group has "*" wildcard — expanded to ALL capability keys
        assert len(caps) == len(ALL_CAPABILITIES), \
            f"Expected {len(ALL_CAPABILITIES)} caps, got {len(caps)}"
        assert CARBON_VIEW_CONSOLE.key in caps
        assert PLATFORM_MANAGE_USERS.key in caps

    def test_carbon_lead_caps_include_view_console(self, carbon_lead_user):
        """carbon_lead has manage_emission_factors → implies view_console."""
        caps = get_user_capabilities(carbon_lead_user)
        assert CARBON_VIEW_CONSOLE.key in caps

    def test_carbon_lead_caps_include_manage_factors(self, carbon_lead_user):
        caps = get_user_capabilities(carbon_lead_user)
        assert CARBON_MANAGE_EMISSION_FACTORS.key in caps

    def test_carbon_lead_caps_include_enter_data(self, carbon_lead_user):
        caps = get_user_capabilities(carbon_lead_user)
        assert CARBON_ENTER_DATA.key in caps

    def test_carbon_lead_caps_include_view_my_data_inherited(self, carbon_lead_user):
        """enter_data → view_my_data via IMPLIES."""
        caps = get_user_capabilities(carbon_lead_user)
        assert CARBON_VIEW_MY_DATA.key in caps

    def test_carbon_lead_caps_include_view_verification_inherited(self, carbon_lead_user):
        """verify_data → view_verification via IMPLIES."""
        caps = get_user_capabilities(carbon_lead_user)
        assert CARBON_VIEW_VERIFICATION.key in caps

    def test_carbon_lead_caps_exclude_platform(self, carbon_lead_user):
        """carbon_lead must NOT have platform admin caps."""
        caps = get_user_capabilities(carbon_lead_user)
        assert PLATFORM_MANAGE_USERS.key not in caps
        assert PLATFORM_MANAGE_GROUPS.key not in caps
        assert PLATFORM_MANAGE_ORG_UNITS.key not in caps

    def test_data_owner_caps(self, data_owner_user):
        caps = get_user_capabilities(data_owner_user)
        assert CARBON_ENTER_DATA.key in caps
        assert CARBON_VIEW_CONSOLE.key in caps
        assert CARBON_VIEW_MY_DATA.key in caps

    def test_data_owner_cannot_admin(self, data_owner_user):
        caps = get_user_capabilities(data_owner_user)
        assert CARBON_MANAGE_EMISSION_FACTORS.key not in caps

    def test_analyst_caps(self, analyst_user):
        caps = get_user_capabilities(analyst_user)
        assert CARBON_GENERATE_REPORTS.key in caps
        assert CARBON_VIEW_ANALYTICS.key in caps
        assert CARBON_VIEW_DASHBOARD.key in caps  # inherited from view_analytics

    def test_analyst_cannot_enter_data(self, analyst_user):
        caps = get_user_capabilities(analyst_user)
        assert CARBON_ENTER_DATA.key not in caps

    def test_viewer_caps(self, viewer_user):
        caps = get_user_capabilities(viewer_user)
        assert CARBON_VIEW_CONSOLE.key in caps
        assert CARBON_ENTER_DATA.key not in caps
        assert CARBON_VERIFY_DATA.key not in caps

    def test_auditor_caps(self, auditor_user):
        caps = get_user_capabilities(auditor_user)
        assert CARBON_VIEW_VERIFICATION.key in caps
        assert CATALOG_VIEW_GOVERNANCE.key in caps

    def test_catalog_lead_caps(self, catalog_lead_user):
        caps = get_user_capabilities(catalog_lead_user)
        assert CATALOG_MANAGE_PRODUCTS.key in caps
        assert CATALOG_MANAGE_METADATA.key in caps
        assert CATALOG_MANAGE_POLICIES.key in caps
        assert CATALOG_VIEW.key in caps  # inherited

    def test_mdm_lead_caps(self, mdm_lead_user):
        caps = get_user_capabilities(mdm_lead_user)
        assert MDM_MANAGE.key in caps
        assert MDM_VIEW.key in caps  # inherited

    def test_dq_lead_caps(self, dq_lead_user):
        caps = get_user_capabilities(dq_lead_user)
        assert DQ_MANAGE_RULES.key in caps
        assert DQ_VIEW.key in caps  # inherited

    def test_multi_role_user_union(self, multi_role_user):
        """User with dataowners_group + analysts_group should get union of caps."""
        caps = get_user_capabilities(multi_role_user)
        # From dataowners_group
        assert CARBON_ENTER_DATA.key in caps
        # From analysts_group
        assert CARBON_VIEW_ANALYTICS.key in caps
        assert CARBON_GENERATE_REPORTS.key in caps

    def test_deactivated_role_gives_no_caps(self, deactivated_role_user):
        caps = get_user_capabilities(deactivated_role_user)
        assert caps == frozenset()

    def test_no_role_user_gets_empty(self, no_role_user):
        caps = get_user_capabilities(no_role_user)
        assert caps == frozenset()

    def test_null_user_gets_empty(self):
        caps = get_user_capabilities(None)
        assert caps == frozenset()

    def test_unauthenticated_user_gets_empty(self, unauthenticated_user):
        caps = get_user_capabilities(unauthenticated_user)
        assert caps == frozenset()

    # ── Request-level cache ────────────────────────────────────

    def test_user_caps_are_cached(self, carbon_lead_user):
        """Second call should return same frozen set (cached)."""
        caps1 = get_user_capabilities(carbon_lead_user)
        caps2 = get_user_capabilities(carbon_lead_user)
        assert caps1 is caps2, "Caps should be cached on user object"

    # ── has_capability ─────────────────────────────────────────

    def test_has_capability_true(self, carbon_lead_user):
        assert has_capability(carbon_lead_user, CARBON_MANAGE_EMISSION_FACTORS.key) is True

    def test_has_capability_inherited_true(self, carbon_lead_user):
        """view_console is inherited from manage_emission_factors."""
        assert has_capability(carbon_lead_user, CARBON_VIEW_CONSOLE.key) is True

    def test_has_capability_false(self, carbon_lead_user):
        """carbon_lead should not have platform manage_users."""
        assert has_capability(carbon_lead_user, PLATFORM_MANAGE_USERS.key) is False

    def test_has_capability_superuser_always_true(self, superuser):
        assert has_capability(superuser, "bogus:fake") is True

    def test_has_capability_none_user(self):
        assert has_capability(None, CARBON_VIEW_CONSOLE.key) is False

    def test_has_capability_no_role_user(self, no_role_user):
        assert has_capability(no_role_user, CARBON_VIEW_CONSOLE.key) is False

    def test_has_capability_unknown_cap_string(self, carbon_lead_user):
        """Unknown capability string should return False (not crash)."""
        assert has_capability(carbon_lead_user, "nonexistent:fake") is False

    # ── has_any_capability ─────────────────────────────────────

    def test_has_any_true(self, carbon_lead_user):
        assert has_any_capability(carbon_lead_user, {
            PLATFORM_MANAGE_USERS.key,  # no
            CARBON_MANAGE_EMISSION_FACTORS.key,  # yes
        }) is True

    def test_has_any_false(self, data_owner_user):
        assert has_any_capability(data_owner_user, {
            CARBON_MANAGE_EMISSION_FACTORS.key,
            CARBON_VERIFY_DATA.key,
            PLATFORM_MANAGE_USERS.key,
        }) is False

    def test_has_any_empty_set(self, carbon_lead_user):
        assert has_any_capability(carbon_lead_user, set()) is False

    def test_has_any_superuser(self, superuser):
        assert has_any_capability(superuser, set()) is True

    # ── has_all_capabilities ───────────────────────────────────

    def test_has_all_true(self, carbon_lead_user):
        assert has_all_capabilities(carbon_lead_user, {
            CARBON_MANAGE_EMISSION_FACTORS.key,
            CARBON_ENTER_DATA.key,
        }) is True

    def test_has_all_false(self, carbon_lead_user):
        assert has_all_capabilities(carbon_lead_user, {
            CARBON_MANAGE_EMISSION_FACTORS.key,
            PLATFORM_MANAGE_USERS.key,
        }) is False

    def test_has_all_empty_set(self, carbon_lead_user):
        assert has_all_capabilities(carbon_lead_user, set()) is True

    def test_has_all_superuser(self, superuser):
        assert has_all_capabilities(superuser, {"bogus:fake"}) is True

    # ── get_capability ─────────────────────────────────────────

    def test_get_capability_valid(self):
        cap = get_capability(CARBON_VIEW_CONSOLE.key)
        assert cap is not None
        assert cap.key == CARBON_VIEW_CONSOLE.key
        assert cap.label == "View Carbon Console"

    def test_get_capability_invalid(self):
        assert get_capability("nonexistent:fake") is None

    # ── get_capability_matrix ──────────────────────────────────

    def test_matrix_has_all_groups(self):
        matrix = get_capability_matrix()
        group_names = {row["group"] for row in matrix}
        assert "admin" in group_names
        assert "carbon_lead" in group_names
        assert "dataowners_group" in group_names
        assert "viewers_group" in group_names

    def test_matrix_wildcard_groups_have_all_caps(self):
        matrix = get_capability_matrix()
        for row in matrix:
            if row["is_wildcard"]:
                assert len(row["capabilities"]) == len(ALL_CAPABILITIES)

    def test_matrix_inherited_flag(self):
        """Carbon lead should show some inherited and some direct caps."""
        matrix = get_capability_matrix()
        clead_row = next(r for r in matrix if r["group"] == "carbon_lead")
        inherited = [c for c in clead_row["capabilities"] if c["inherited"]]
        direct = [c for c in clead_row["capabilities"] if not c["inherited"]]
        assert len(inherited) > 0, "Carbon lead should have inherited capabilities"
        assert len(direct) > 0, "Carbon lead should have direct capabilities"
        # view_console should be inherited
        console_entries = [c for c in inherited if c["key"] == CARBON_VIEW_CONSOLE.key]
        assert len(console_entries) > 0, "view_console should be inherited for carbon_lead"

    # ── get_capabilities_for_frontend ──────────────────────────

    def test_frontend_caps_structure(self, carbon_lead_user):
        caps = get_capabilities_for_frontend(carbon_lead_user)
        assert isinstance(caps, list)
        assert len(caps) > 0
        first = caps[0]
        assert "key" in first
        assert "domain" in first
        assert "action" in first
        assert "label" in first
        assert "category" in first

    def test_frontend_caps_sorted(self, carbon_lead_user):
        caps = get_capabilities_for_frontend(carbon_lead_user)
        # Sorted by (domain, category, label)
        for i in range(len(caps) - 1):
            a = (caps[i]["domain"], caps[i]["category"], caps[i]["label"])
            b = (caps[i + 1]["domain"], caps[i + 1]["category"], caps[i + 1]["label"])
            assert a <= b, f"Not sorted at index {i}: {a} > {b}"

    def test_frontend_caps_superuser_returns_all(self, superuser):
        caps = get_capabilities_for_frontend(superuser)
        assert len(caps) == len(ALL_CAPABILITIES)


# ═══════════════════════════════════════════════════════════════════════
# SECTION 5: PERMISSION CLASSES
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAdminOrSuperuserOnly:
    """The AdminOrSuperuserOnly permission class with capability system."""

    def _make_request(self, user, method="GET"):
        from rest_framework.test import APIRequestFactory
        factory = APIRequestFactory()
        if method == "GET":
            request = factory.get("/fake/")
        elif method == "POST":
            request = factory.post("/fake/", {}, format="json")
        elif method == "DELETE":
            request = factory.delete("/fake/")
        else:
            request = factory.get("/fake/")
        request.user = user
        return request

    def _make_view(self, **attrs):
        """Create a mock view with given attributes."""
        from types import SimpleNamespace
        view = SimpleNamespace()
        for k, v in attrs.items():
            setattr(view, k, v)
        return view

    def test_superuser_passes(self, superuser):
        from accounts.permissions import AdminOrSuperuserOnly
        perm = AdminOrSuperuserOnly()
        request = self._make_request(superuser)
        view = self._make_view(required_capability=CARBON_MANAGE_EMISSION_FACTORS.key)
        assert perm.has_permission(request, view) is True

    def test_global_admin_passes(self, admin_user):
        from accounts.permissions import AdminOrSuperuserOnly
        perm = AdminOrSuperuserOnly()
        request = self._make_request(admin_user)
        view = self._make_view(required_capability=CARBON_MANAGE_EMISSION_FACTORS.key)
        assert perm.has_permission(request, view) is True

    def test_carbon_lead_passes_for_manage_factors(self, carbon_lead_user):
        from accounts.permissions import AdminOrSuperuserOnly
        perm = AdminOrSuperuserOnly()
        request = self._make_request(carbon_lead_user)
        view = self._make_view(required_capability=CARBON_MANAGE_EMISSION_FACTORS.key)
        assert perm.has_permission(request, view) is True

    def test_carbon_lead_denied_for_platform_manage_users(self, carbon_lead_user):
        from accounts.permissions import AdminOrSuperuserOnly
        perm = AdminOrSuperuserOnly()
        request = self._make_request(carbon_lead_user)
        view = self._make_view(required_capability=PLATFORM_MANAGE_USERS.key)
        assert perm.has_permission(request, view) is False

    def test_data_owner_denied_for_manage_factors(self, data_owner_user):
        from accounts.permissions import AdminOrSuperuserOnly
        perm = AdminOrSuperuserOnly()
        request = self._make_request(data_owner_user)
        view = self._make_view(required_capability=CARBON_MANAGE_EMISSION_FACTORS.key)
        assert perm.has_permission(request, view) is False

    def test_viewer_denied_for_manage_factors(self, viewer_user):
        from accounts.permissions import AdminOrSuperuserOnly
        perm = AdminOrSuperuserOnly()
        request = self._make_request(viewer_user)
        view = self._make_view(required_capability=CARBON_MANAGE_EMISSION_FACTORS.key)
        assert perm.has_permission(request, view) is False

    def test_analyst_denied_for_manage_factors(self, analyst_user):
        from accounts.permissions import AdminOrSuperuserOnly
        perm = AdminOrSuperuserOnly()
        request = self._make_request(analyst_user)
        view = self._make_view(required_capability=CARBON_MANAGE_EMISSION_FACTORS.key)
        assert perm.has_permission(request, view) is False

    def test_auditor_denied_for_manage_factors(self, auditor_user):
        from accounts.permissions import AdminOrSuperuserOnly
        perm = AdminOrSuperuserOnly()
        request = self._make_request(auditor_user)
        view = self._make_view(required_capability=CARBON_MANAGE_EMISSION_FACTORS.key)
        assert perm.has_permission(request, view) is False

    def test_unauthenticated_denied(self):
        from accounts.permissions import AdminOrSuperuserOnly
        from django.contrib.auth.models import AnonymousUser
        perm = AdminOrSuperuserOnly()
        request = self._make_request(AnonymousUser())
        view = self._make_view(required_capability=CARBON_MANAGE_EMISSION_FACTORS.key)
        assert perm.has_permission(request, view) is False

    def test_no_required_capability_denied(self, carbon_lead_user):
        """View without required_capability should deny if no fallback."""
        from accounts.permissions import AdminOrSuperuserOnly
        perm = AdminOrSuperuserOnly()
        request = self._make_request(carbon_lead_user)
        view = self._make_view()  # No required_capability, no domain_lead_groups
        assert perm.has_permission(request, view) is False

    def test_catalog_lead_passes_for_catalog_manage_products(self, catalog_lead_user):
        from accounts.permissions import AdminOrSuperuserOnly
        perm = AdminOrSuperuserOnly()
        request = self._make_request(catalog_lead_user)
        view = self._make_view(required_capability=CATALOG_MANAGE_PRODUCTS.key)
        assert perm.has_permission(request, view) is True

    def test_mdm_lead_passes_for_mdm_manage(self, mdm_lead_user):
        from accounts.permissions import AdminOrSuperuserOnly
        perm = AdminOrSuperuserOnly()
        request = self._make_request(mdm_lead_user)
        view = self._make_view(required_capability=MDM_MANAGE.key)
        assert perm.has_permission(request, view) is True

    def test_dq_lead_passes_for_dq_manage_rules(self, dq_lead_user):
        from accounts.permissions import AdminOrSuperuserOnly
        perm = AdminOrSuperuserOnly()
        request = self._make_request(dq_lead_user)
        view = self._make_view(required_capability=DQ_MANAGE_RULES.key)
        assert perm.has_permission(request, view) is True

    def test_multi_role_passes(self, multi_role_user):
        """Multi-role user with dataowner+analyst can access calculate endpoints."""
        from accounts.permissions import AdminOrSuperuserOnly
        perm = AdminOrSuperuserOnly()
        request = self._make_request(multi_role_user)
        view = self._make_view(required_capability=CARBON_VIEW_CALCULATIONS.key)
        assert perm.has_permission(request, view) is True

    def test_deactivated_role_denied(self, deactivated_role_user):
        from accounts.permissions import AdminOrSuperuserOnly
        perm = AdminOrSuperuserOnly()
        request = self._make_request(deactivated_role_user)
        view = self._make_view(required_capability=CARBON_MANAGE_EMISSION_FACTORS.key)
        assert perm.has_permission(request, view) is False

    def test_no_role_user_denied(self, no_role_user):
        from accounts.permissions import AdminOrSuperuserOnly
        perm = AdminOrSuperuserOnly()
        request = self._make_request(no_role_user)
        view = self._make_view(required_capability=CARBON_VIEW_CONSOLE.key)
        assert perm.has_permission(request, view) is False

    def test_list_of_capabilities_any_match(self, carbon_lead_user):
        """required_capability as a list: user needs ANY one of them."""
        from accounts.permissions import AdminOrSuperuserOnly
        perm = AdminOrSuperuserOnly()
        request = self._make_request(carbon_lead_user)
        view = self._make_view(required_capability=[
            PLATFORM_MANAGE_USERS.key,  # no
            CARBON_MANAGE_EMISSION_FACTORS.key,  # yes
        ])
        assert perm.has_permission(request, view) is True

    def test_list_of_capabilities_none_match(self, carbon_lead_user):
        """required_capability as a list: user has none → denied."""
        from accounts.permissions import AdminOrSuperuserOnly
        perm = AdminOrSuperuserOnly()
        request = self._make_request(carbon_lead_user)
        view = self._make_view(required_capability=[
            PLATFORM_MANAGE_USERS.key,
            PLATFORM_MANAGE_GROUPS.key,
        ])
        assert perm.has_permission(request, view) is False

    def test_legacy_domain_lead_groups_fallback(self, carbon_lead_user):
        """Without required_capability, domain_lead_groups should still work."""
        from accounts.permissions import AdminOrSuperuserOnly
        perm = AdminOrSuperuserOnly()
        request = self._make_request(carbon_lead_user)
        view = self._make_view(domain_lead_groups=["carbon_lead"])
        assert perm.has_permission(request, view) is True


@pytest.mark.django_db
class TestReadAnyWriteAdmin:
    """ReadAnyWriteAdmin: anyone can read, write requires capability."""

    def _make_request(self, user, method="GET"):
        from rest_framework.test import APIRequestFactory
        factory = APIRequestFactory()
        if method == "GET":
            request = factory.get("/fake/")
        elif method == "POST":
            request = factory.post("/fake/", {}, format="json")
        elif method == "PUT":
            request = factory.put("/fake/", {}, format="json")
        elif method == "PATCH":
            request = factory.patch("/fake/", {}, format="json")
        elif method == "DELETE":
            request = factory.delete("/fake/")
        else:
            request = factory.get("/fake/")
        request.user = user
        return request

    def _make_view(self, **attrs):
        from types import SimpleNamespace
        view = SimpleNamespace()
        for k, v in attrs.items():
            setattr(view, k, v)
        return view

    def test_anyone_can_read(self, viewer_user, data_owner_user, analyst_user):
        from accounts.permissions import ReadAnyWriteAdmin
        perm = ReadAnyWriteAdmin()
        view = self._make_view(required_write_capability=CARBON_MANAGE_EMISSION_FACTORS.key)
        for user in [viewer_user, data_owner_user, analyst_user]:
            request = self._make_request(user, "GET")
            assert perm.has_permission(request, view) is True, \
                f"{user.username} should be able to GET"

    def test_write_requires_capability_passes_for_lead(self, carbon_lead_user):
        from accounts.permissions import ReadAnyWriteAdmin
        perm = ReadAnyWriteAdmin()
        view = self._make_view(required_write_capability=CARBON_MANAGE_EMISSION_FACTORS.key)
        request = self._make_request(carbon_lead_user, "POST")
        assert perm.has_permission(request, view) is True

    def test_write_requires_capability_denied_for_viewer(self, viewer_user):
        from accounts.permissions import ReadAnyWriteAdmin
        perm = ReadAnyWriteAdmin()
        view = self._make_view(required_write_capability=CARBON_MANAGE_EMISSION_FACTORS.key)
        request = self._make_request(viewer_user, "POST")
        assert perm.has_permission(request, view) is False

    def test_write_requires_capability_denied_for_analyst(self, analyst_user):
        from accounts.permissions import ReadAnyWriteAdmin
        perm = ReadAnyWriteAdmin()
        view = self._make_view(required_write_capability=CARBON_MANAGE_EMISSION_FACTORS.key)
        request = self._make_request(analyst_user, "POST")
        assert perm.has_permission(request, view) is False

    def test_write_data_owner_denied_for_admin_caps(self, data_owner_user):
        from accounts.permissions import ReadAnyWriteAdmin
        perm = ReadAnyWriteAdmin()
        view = self._make_view(required_write_capability=CARBON_MANAGE_EMISSION_FACTORS.key)
        request = self._make_request(data_owner_user, "POST")
        assert perm.has_permission(request, view) is False

    def test_write_superuser_passes(self, superuser):
        from accounts.permissions import ReadAnyWriteAdmin
        perm = ReadAnyWriteAdmin()
        view = self._make_view(required_write_capability=CARBON_MANAGE_EMISSION_FACTORS.key)
        request = self._make_request(superuser, "POST")
        assert perm.has_permission(request, view) is True

    def test_write_global_admin_passes(self, admin_user):
        from accounts.permissions import ReadAnyWriteAdmin
        perm = ReadAnyWriteAdmin()
        view = self._make_view(required_write_capability=CARBON_MANAGE_EMISSION_FACTORS.key)
        request = self._make_request(admin_user, "POST")
        assert perm.has_permission(request, view) is True

    def test_all_http_methods_delegated_correctly(self, carbon_lead_user, viewer_user):
        """GET/HEAD/OPTIONS always pass; POST/PUT/PATCH/DELETE check capability."""
        from accounts.permissions import ReadAnyWriteAdmin
        perm = ReadAnyWriteAdmin()
        view = self._make_view(required_write_capability=CARBON_MANAGE_EMISSION_FACTORS.key)

        # Safe methods — viewer passes
        for method in ["GET", "HEAD", "OPTIONS"]:
            request = self._make_request(viewer_user, method)
            assert perm.has_permission(request, view) is True, f"Failed on {method}"

        # Unsafe methods — viewer denied, carbon_lead passes
        for method in ["POST", "PUT", "PATCH", "DELETE"]:
            req_v = self._make_request(viewer_user, method)
            assert perm.has_permission(req_v, view) is False, f"Viewer should fail on {method}"

            req_l = self._make_request(carbon_lead_user, method)
            assert perm.has_permission(req_l, view) is True, f"Lead should pass on {method}"

    def test_unauthenticated_denied_read(self):
        from accounts.permissions import ReadAnyWriteAdmin
        from django.contrib.auth.models import AnonymousUser
        perm = ReadAnyWriteAdmin()
        view = self._make_view(required_write_capability=CARBON_MANAGE_EMISSION_FACTORS.key)
        request = self._make_request(AnonymousUser(), "GET")
        assert perm.has_permission(request, view) is False


# ═══════════════════════════════════════════════════════════════════════
# SECTION 6: API INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMeContextCapabilities:
    """Verify me_context returns correct capabilities."""

    def _auth(self, api_client, user, get_token_for_user):
        token = get_token_for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_me_context_includes_capabilities_field(self, api_client, create_user, create_scoped_role, get_token_for_user):
        u = create_user("mectx")
        create_scoped_role(u, "carbon_lead")
        self._auth(api_client, u, get_token_for_user)
        resp = api_client.get(reverse("me-context"))
        assert resp.status_code == 200
        data = resp.json()
        assert "capabilities" in data
        assert isinstance(data["capabilities"], list)

    def test_me_context_carbon_lead_has_manage_factors(self, api_client, create_user, create_scoped_role, get_token_for_user):
        u = create_user("mectx2")
        create_scoped_role(u, "carbon_lead")
        self._auth(api_client, u, get_token_for_user)
        resp = api_client.get(reverse("me-context"))
        caps = resp.json()["capabilities"]
        keys = {c["key"] for c in caps}
        assert CARBON_MANAGE_EMISSION_FACTORS.key in keys
        assert CARBON_VIEW_CONSOLE.key in keys  # inherited

    def test_me_context_viewer_has_no_admin_caps(self, api_client, create_user, create_scoped_role, get_token_for_user):
        u = create_user("mectx3")
        create_scoped_role(u, "viewers_group")
        self._auth(api_client, u, get_token_for_user)
        resp = api_client.get(reverse("me-context"))
        caps = resp.json()["capabilities"]
        keys = {c["key"] for c in caps}
        assert CARBON_VIEW_CONSOLE.key in keys
        assert CARBON_MANAGE_EMISSION_FACTORS.key not in keys
        assert CARBON_ENTER_DATA.key not in keys

    def test_me_context_superuser_has_all_caps(self, api_client, create_user, get_token_for_user):
        u = create_user("su", is_superuser=True)
        self._auth(api_client, u, get_token_for_user)
        resp = api_client.get(reverse("me-context"))
        caps = resp.json()["capabilities"]
        assert len(caps) == len(ALL_CAPABILITIES)


@pytest.mark.django_db
class TestCapabilityMatrixEndpoint:
    """Verify the capability-matrix API endpoint."""

    def _auth(self, api_client, user, get_token_for_user):
        token = get_token_for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_matrix_endpoint_accessible_by_admin(self, api_client, create_user, create_scoped_role, get_token_for_user):
        u = create_user("matrixadmin")
        create_scoped_role(u, "admin")
        self._auth(api_client, u, get_token_for_user)
        resp = api_client.get(reverse("capability-matrix"))
        assert resp.status_code == 200
        data = resp.json()
        assert "matrix" in data
        assert "inheritance" in data
        assert "domains" in data

    def test_matrix_endpoint_denied_for_viewer(self, api_client, create_user, create_scoped_role, get_token_for_user):
        u = create_user("matrixviewer")
        create_scoped_role(u, "viewers_group")
        self._auth(api_client, u, get_token_for_user)
        resp = api_client.get(reverse("capability-matrix"))
        assert resp.status_code == 403

    def test_matrix_endpoint_denied_for_data_owner(self, api_client, create_user, create_scoped_role, get_token_for_user):
        u = create_user("matrixowner")
        create_scoped_role(u, "dataowners_group")
        self._auth(api_client, u, get_token_for_user)
        resp = api_client.get(reverse("capability-matrix"))
        assert resp.status_code == 403

    def test_matrix_endpoint_unauthenticated(self, api_client):
        resp = api_client.get(reverse("capability-matrix"))
        assert resp.status_code == 401

    def test_matrix_has_inheritance_edges(self, api_client, create_user, create_scoped_role, get_token_for_user):
        u = create_user("matrixadmin2")
        create_scoped_role(u, "admin")
        self._auth(api_client, u, get_token_for_user)
        resp = api_client.get(reverse("capability-matrix"))
        data = resp.json()
        # Verify at least one inheritance edge exists
        edges = data["inheritance"]
        assert len(edges) > 0
        # Check that edges have from/to structure
        edge = edges[0]
        assert "from" in edge
        assert "to" in edge

    def test_matrix_domains_are_complete(self, api_client, create_user, create_scoped_role, get_token_for_user):
        u = create_user("matrixadmin3")
        create_scoped_role(u, "admin")
        self._auth(api_client, u, get_token_for_user)
        resp = api_client.get(reverse("capability-matrix"))
        data = resp.json()
        domain_names = {d["domain"] for d in data["domains"]}
        assert "carbon" in domain_names
        assert "platform" in domain_names
        assert "catalog" in domain_names
        assert "dq" in domain_names
        assert "mdm" in domain_names


# ═══════════════════════════════════════════════════════════════════════
# SECTION 7: EDGE CASES & BOUNDARIES
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_duplicate_scoped_role(self, carbon_lead_user):
        """User with two identical carbon_lead ScopedRoles should get same caps."""
        group = Group.objects.get(name="carbon_lead")
        # Create a second identical role
        ScopedRole.objects.create(user=carbon_lead_user, group=group, is_active=True)
        caps = get_user_capabilities(carbon_lead_user)
        assert CARBON_MANAGE_EMISSION_FACTORS.key in caps

    def test_one_active_one_deactivated_same_role(self):
        """One active + one deactivated role → caps from active only."""
        u = User.objects.create_user(username="mixed", password="test")
        u.save()
        group, _ = Group.objects.get_or_create(name="carbon_lead")
        ScopedRole.objects.create(user=u, group=group, is_active=True)
        ScopedRole.objects.create(user=u, group=Group.objects.get_or_create(name="dataowners_group")[0], is_active=False)
        caps = get_user_capabilities(u)
        # Should get carbon_lead caps (active) but dataowners_group deactivated adds nothing
        assert CARBON_MANAGE_EMISSION_FACTORS.key in caps
        assert CARBON_ENTER_DATA.key in caps  # carbon_lead has this

    def test_org_scoped_role_still_gives_caps(self):
        """ScopedRole with org_unit set should still grant capabilities."""
        from mdm.models import OrgUnit
        u = User.objects.create_user(username="scoped", password="test")
        u.save()
        org = OrgUnit.objects.create(name="Test Org", slug="test-org")
        group, _ = Group.objects.get_or_create(name="carbon_lead")
        ScopedRole.objects.create(user=u, group=group, org_unit=org, is_active=True)
        caps = get_user_capabilities(u)
        assert CARBON_MANAGE_EMISSION_FACTORS.key in caps

    # ── DD-1 (TASK-CBAC-TRUST-CORE-SWAP): org-scoped wildcard → read-only ──
    def test_org_scoped_admins_group_is_read_only(self):
        """Org-scoped admins_group resolves to view-only caps — never a global writer."""
        from mdm.models import OrgUnit
        u = User.objects.create_user(username="orgadmin", password="test")
        u.save()
        org = OrgUnit.objects.create(name="Scoped Org", slug="scoped-org")
        group, _ = Group.objects.get_or_create(name="admins_group")
        ScopedRole.objects.create(user=u, group=group, org_unit=org, is_active=True)
        caps = get_user_capabilities(u)
        # Read-only view caps present
        assert CATALOG_VIEW.key in caps
        assert DQ_VIEW.key in caps
        assert MDM_VIEW.key in caps
        assert EVIDENCE_VIEW.key in caps
        # NO write/manage/admin capabilities
        assert "*" not in caps
        assert PLATFORM_MANAGE_USERS.key not in caps
        assert PLATFORM_MANAGE_ACCESS.key not in caps
        assert CARBON_ENTER_DATA.key not in caps
        assert CARBON_MANAGE_EMISSION_FACTORS.key not in caps
        assert DQ_MANAGE_RULES.key not in caps
        assert MDM_MANAGE.key not in caps
        assert EVIDENCE_MANAGE.key not in caps

    def test_org_scoped_admins_group_keeps_view_caps(self):
        """Org-scoped admins_group still resolves view_* caps for scoped reads."""
        from mdm.models import OrgUnit
        u = User.objects.create_user(username="orgadmin2", password="test")
        u.save()
        org = OrgUnit.objects.create(name="Scoped Org 2", slug="scoped-org-2")
        group, _ = Group.objects.get_or_create(name="admins_group")
        ScopedRole.objects.create(user=u, group=group, org_unit=org, is_active=True)
        caps = get_user_capabilities(u)
        assert CARBON_VIEW_CONSOLE.key in caps
        assert PLATFORM_VIEW_AUDIT.key in caps
        assert CATALOG_VIEW_GOVERNANCE.key in caps

    def test_global_admins_group_is_full_wildcard(self):
        """Global (org=None) admins_group still resolves to ALL capabilities."""
        u = User.objects.create_user(username="globaladmin", password="test")
        u.save()
        group, _ = Group.objects.get_or_create(name="admins_group")
        ScopedRole.objects.create(user=u, group=group, is_active=True)  # org_unit=None
        caps = get_user_capabilities(u)
        assert "*" in caps or len(caps) == len(ALL_CAPABILITIES), \
            "Global admin must resolve to full capability set"
        assert PLATFORM_MANAGE_USERS.key in caps
        assert EVIDENCE_MANAGE.key in caps
        assert has_capability(u, PLATFORM_MANAGE_USERS.key)
        assert has_capability(u, EVIDENCE_MANAGE.key)

    def test_org_scoped_data_owner_keeps_data_caps(self):
        """Org-scoped dataowners_group keeps its declared data caps (DD-2 unaffected by DD-1)."""
        from mdm.models import OrgUnit
        u = User.objects.create_user(username="orgdowner", password="test")
        u.save()
        org = OrgUnit.objects.create(name="Scoped Org 3", slug="scoped-org-3")
        group, _ = Group.objects.get_or_create(name="dataowners_group")
        ScopedRole.objects.create(user=u, group=group, org_unit=org, is_active=True)
        caps = get_user_capabilities(u)
        assert CARBON_ENTER_DATA.key in caps
        assert CATALOG_VIEW.key in caps
        assert DQ_VIEW.key in caps

    def test_module_scoped_role_still_gives_caps(self):
        """ScopedRole with module set should still grant capabilities."""
        from core.models import Module
        from mdm.models import OrgUnit
        u = User.objects.create_user(username="modscoped", password="test")
        u.save()
        org = OrgUnit.objects.create(name="Mod Org", slug="mod-org")
        mod = Module.objects.create(name="Test Mod", scope=1, org_unit=org)
        group, _ = Group.objects.get_or_create(name="carbon_lead")
        ScopedRole.objects.create(user=u, group=group, module=mod, is_active=True)
        caps = get_user_capabilities(u)
        assert CARBON_MANAGE_EMISSION_FACTORS.key in caps

    def test_user_with_only_unknown_group(self):
        """User in a group NOT in GROUP_CAPABILITIES should get empty caps."""
        u = User.objects.create_user(username="unknown", password="test")
        u.save()
        group, _ = Group.objects.get_or_create(name="some_custom_group")
        ScopedRole.objects.create(user=u, group=group, is_active=True)
        caps = get_user_capabilities(u)
        assert caps == frozenset()

    def test_wildcard_group_does_not_break_function(self):
        """Wildcard '*' should be handled gracefully in expand."""
        # Expanding a set with "*" should not crash
        result = _expand_capabilities({"*"})
        assert "*" in result

    def test_has_capability_with_empty_string(self, carbon_lead_user):
        """Empty capability string should return False."""
        assert has_capability(carbon_lead_user, "") is False

    def test_has_capability_with_none_string(self, carbon_lead_user):
        """None capability should return False gracefully."""
        # None can be in a frozenset, but has_capability handles it
        result = has_capability(carbon_lead_user, None)
        assert result is False

    def test_very_long_username(self):
        """User with long username should still work."""
        long_name = "u" * 150
        u = User.objects.create_user(username=long_name, password="test")
        u.save()
        group, _ = Group.objects.get_or_create(name="dataowners_group")
        ScopedRole.objects.create(user=u, group=group, is_active=True)
        caps = get_user_capabilities(u)
        assert CARBON_VIEW_CONSOLE.key in caps

    def test_group_name_case_sensitivity(self):
        """Group names are case-sensitive. 'Carbon_Lead' ≠ 'carbon_lead'."""
        u = User.objects.create_user(username="casesens", password="test")
        u.save()
        group, _ = Group.objects.get_or_create(name="Carbon_Lead")  # Capitalized
        ScopedRole.objects.create(user=u, group=group, is_active=True)
        caps = get_user_capabilities(u)
        # 'Carbon_Lead' is NOT in GROUP_CAPABILITIES, so no caps
        assert caps == frozenset()

    def test_cache_isolation(self, carbon_lead_user, data_owner_user):
        """Cache on one user should not affect another user."""
        caps1 = get_user_capabilities(carbon_lead_user)
        caps2 = get_user_capabilities(data_owner_user)
        assert CARBON_MANAGE_EMISSION_FACTORS.key in caps1
        assert CARBON_MANAGE_EMISSION_FACTORS.key not in caps2

    def test_adding_role_after_caching(self, no_role_user):
        """After caching, adding a role should NOT change cached caps within same request."""
        caps1 = get_user_capabilities(no_role_user)
        assert caps1 == frozenset()
        # Simulate adding a role (cache already set)
        group, _ = Group.objects.get_or_create(name="carbon_lead")
        ScopedRole.objects.create(user=no_role_user, group=group, is_active=True)
        caps2 = get_user_capabilities(no_role_user)
        # Should still be cached empty
        assert caps2 == frozenset()
        # Clear cache manually and re-check
        delattr(no_role_user, "_cached_capabilities")
        caps3 = get_user_capabilities(no_role_user)
        assert CARBON_MANAGE_EMISSION_FACTORS.key in caps3


# ═══════════════════════════════════════════════════════════════════════
# SECTION 8: PARAMETRIZED CROSS-ROLE ACCESS MATRIX
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestScopedRoleViewSetOptionA:
    """A2 (TASK-CBAC-A2, Option A — centralize): role-assignment management
    is GLOBAL-ADMIN ONLY.

    Org-scoped stewards (admins_group scoped to an org unit) get 403 on the
    access-control endpoints: DD-1 resolves their scoped wildcard role to
    view-only capabilities, so platform:manage_access is absent. Global
    admins and superusers are unaffected.
    """

    def _auth(self, api_client, user, get_token_for_user):
        token = get_token_for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_org_scoped_steward_denied_list(self, api_client, create_user, create_scoped_role, get_token_for_user):
        """Org-scoped admins_group steward → 403 on GET /access-control/."""
        from mdm.models import OrgUnit
        org = OrgUnit.objects.create(name="Steward Org", slug="steward-org")
        u = create_user("steward-list")
        create_scoped_role(u, "admins_group", org_unit=org)
        self._auth(api_client, u, get_token_for_user)
        resp = api_client.get(reverse("access-control-list"))
        assert resp.status_code == 403

    def test_org_scoped_steward_denied_create(self, api_client, create_user, create_scoped_role, get_token_for_user):
        """Org-scoped admins_group steward → 403 on POST /access-control/."""
        from mdm.models import OrgUnit
        org = OrgUnit.objects.create(name="Steward Org 2", slug="steward-org-2")
        u = create_user("steward-create")
        create_scoped_role(u, "admins_group", org_unit=org)
        self._auth(api_client, u, get_token_for_user)
        target = create_user("target-user")
        group = Group.objects.get_or_create(name="dataowners_group")[0]
        resp = api_client.post(reverse("access-control-list"), {
            "user": target.id,
            "group": group.id,
            "org_unit": org.id,
            "is_active": True,
        }, format="json")
        assert resp.status_code == 403

    def test_global_admin_allowed_list(self, api_client, create_user, create_scoped_role, get_token_for_user):
        """Global admins_group → 200 on GET /access-control/."""
        u = create_user("global-admin-list")
        create_scoped_role(u, "admins_group")  # org_unit=None → global
        self._auth(api_client, u, get_token_for_user)
        resp = api_client.get(reverse("access-control-list"))
        assert resp.status_code == 200

    def test_global_admin_allowed_create(self, api_client, create_user, create_scoped_role, get_token_for_user):
        """Global admins_group → 201 on POST /access-control/."""
        u = create_user("global-admin-create")
        create_scoped_role(u, "admins_group")  # org_unit=None → global
        self._auth(api_client, u, get_token_for_user)
        target = create_user("target-user-2")
        group = Group.objects.get_or_create(name="dataowners_group")[0]
        resp = api_client.post(reverse("access-control-list"), {
            "user": target.id,
            "group": group.id,
            "is_active": True,
        }, format="json")
        assert resp.status_code == 201

    def test_superuser_allowed_list(self, api_client, create_user, get_token_for_user):
        """Superuser → 200 on GET /access-control/."""
        u = create_user("a2-super", is_superuser=True)
        self._auth(api_client, u, get_token_for_user)
        resp = api_client.get(reverse("access-control-list"))
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════
# SECTION 8: PARAMETRIZED CROSS-ROLE ACCESS MATRIX
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCrossRoleAccessMatrix:
    """Parametrized tests covering every role × every key capability."""

    @pytest.mark.parametrize("role_name,cap_key,expected", [
        # ── carbon:view_console ──
        ("superuser",       CARBON_VIEW_CONSOLE.key, True),
        ("admin",           CARBON_VIEW_CONSOLE.key, True),
        ("carbon_lead",     CARBON_VIEW_CONSOLE.key, True),   # inherited
        ("catalog_lead",    CARBON_VIEW_CONSOLE.key, False),
        ("mdm_lead",        CARBON_VIEW_CONSOLE.key, False),
        ("dq_lead",         CARBON_VIEW_CONSOLE.key, False),
        ("dataowners_group", CARBON_VIEW_CONSOLE.key, True),
        ("analysts_group",  CARBON_VIEW_CONSOLE.key, True),
        ("viewers_group",   CARBON_VIEW_CONSOLE.key, True),
        ("auditors_group",  CARBON_VIEW_CONSOLE.key, True),

        # ── carbon:enter_data ──
        ("superuser",       CARBON_ENTER_DATA.key, True),
        ("admin",           CARBON_ENTER_DATA.key, True),
        ("carbon_lead",     CARBON_ENTER_DATA.key, True),
        ("catalog_lead",    CARBON_ENTER_DATA.key, False),
        ("mdm_lead",        CARBON_ENTER_DATA.key, False),
        ("dq_lead",         CARBON_ENTER_DATA.key, False),
        ("dataowners_group", CARBON_ENTER_DATA.key, True),
        ("analysts_group",  CARBON_ENTER_DATA.key, False),
        ("viewers_group",   CARBON_ENTER_DATA.key, False),
        ("auditors_group",  CARBON_ENTER_DATA.key, False),

        # ── carbon:manage_emission_factors ──
        ("superuser",       CARBON_MANAGE_EMISSION_FACTORS.key, True),
        ("admin",           CARBON_MANAGE_EMISSION_FACTORS.key, True),
        ("carbon_lead",     CARBON_MANAGE_EMISSION_FACTORS.key, True),
        ("catalog_lead",    CARBON_MANAGE_EMISSION_FACTORS.key, False),
        ("mdm_lead",        CARBON_MANAGE_EMISSION_FACTORS.key, False),
        ("dq_lead",         CARBON_MANAGE_EMISSION_FACTORS.key, False),
        ("dataowners_group", CARBON_MANAGE_EMISSION_FACTORS.key, False),
        ("analysts_group",  CARBON_MANAGE_EMISSION_FACTORS.key, False),
        ("viewers_group",   CARBON_MANAGE_EMISSION_FACTORS.key, False),
        ("auditors_group",  CARBON_MANAGE_EMISSION_FACTORS.key, False),

        # ── carbon:verify_data ──
        ("superuser",       CARBON_VERIFY_DATA.key, True),
        ("admin",           CARBON_VERIFY_DATA.key, True),
        ("carbon_lead",     CARBON_VERIFY_DATA.key, True),
        ("catalog_lead",    CARBON_VERIFY_DATA.key, False),
        ("dataowners_group", CARBON_VERIFY_DATA.key, False),
        ("analysts_group",  CARBON_VERIFY_DATA.key, False),
        ("viewers_group",   CARBON_VERIFY_DATA.key, False),
        ("auditors_group",  CARBON_VERIFY_DATA.key, False),

        # ── carbon:generate_reports ──
        ("superuser",       CARBON_GENERATE_REPORTS.key, True),
        ("admin",           CARBON_GENERATE_REPORTS.key, True),
        ("carbon_lead",     CARBON_GENERATE_REPORTS.key, True),
        ("dataowners_group", CARBON_GENERATE_REPORTS.key, False),
        ("analysts_group",  CARBON_GENERATE_REPORTS.key, True),
        ("viewers_group",   CARBON_GENERATE_REPORTS.key, False),
        ("auditors_group",  CARBON_GENERATE_REPORTS.key, False),

        # ── carbon:view_analytics ──
        ("superuser",       CARBON_VIEW_ANALYTICS.key, True),
        ("admin",           CARBON_VIEW_ANALYTICS.key, True),
        ("carbon_lead",     CARBON_VIEW_ANALYTICS.key, True),
        ("dataowners_group", CARBON_VIEW_ANALYTICS.key, False),
        ("analysts_group",  CARBON_VIEW_ANALYTICS.key, True),
        ("viewers_group",   CARBON_VIEW_ANALYTICS.key, False),

        # ── catalog:manage_products ──
        ("superuser",       CATALOG_MANAGE_PRODUCTS.key, True),
        ("admin",           CATALOG_MANAGE_PRODUCTS.key, True),
        ("carbon_lead",     CATALOG_MANAGE_PRODUCTS.key, False),
        ("catalog_lead",    CATALOG_MANAGE_PRODUCTS.key, True),
        ("dataowners_group", CATALOG_MANAGE_PRODUCTS.key, False),

        # ── dq:manage_rules ──
        ("superuser",       DQ_MANAGE_RULES.key, True),
        ("admin",           DQ_MANAGE_RULES.key, True),
        ("carbon_lead",     DQ_MANAGE_RULES.key, False),
        ("dq_lead",         DQ_MANAGE_RULES.key, True),
        ("dataowners_group", DQ_MANAGE_RULES.key, False),

        # ── mdm:manage ──
        ("superuser",       MDM_MANAGE.key, True),
        ("admin",           MDM_MANAGE.key, True),
        ("carbon_lead",     MDM_MANAGE.key, False),
        ("mdm_lead",        MDM_MANAGE.key, True),
        ("viewers_group",   MDM_MANAGE.key, False),

        # ── platform:manage_users (only wildcard groups) ──
        ("superuser",       PLATFORM_MANAGE_USERS.key, True),
        ("admin",           PLATFORM_MANAGE_USERS.key, True),
        ("carbon_lead",     PLATFORM_MANAGE_USERS.key, False),
        ("catalog_lead",    PLATFORM_MANAGE_USERS.key, False),
        ("dataowners_group", PLATFORM_MANAGE_USERS.key, False),
        ("analysts_group",  PLATFORM_MANAGE_USERS.key, False),
        ("viewers_group",   PLATFORM_MANAGE_USERS.key, False),
        ("auditors_group",  PLATFORM_MANAGE_USERS.key, False),
    ])
    def test_role_capability_matrix(self, role_name, cap_key, expected):
        """Parametrized access matrix covering every role × key capability."""
        # Resolve user based on role_name
        if role_name == "superuser":
            user = User.objects.create_superuser(username=f"u_{role_name}_{cap_key}", password="test")
        else:
            user = User.objects.create_user(username=f"u_{role_name}_{cap_key}", password="test")
            user.save()
            if role_name:
                group, _ = Group.objects.get_or_create(name=role_name)
                ScopedRole.objects.create(user=user, group=group, is_active=True)

        result = has_capability(user, cap_key)
        assert result is expected, \
            f"{role_name} → {cap_key}: expected {expected}, got {result}"


# ═══════════════════════════════════════════════════════════════════════
# SECTION 9: INHERITANCE DEPTH & TRANSITIVE TESTS
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestInheritanceDepth:
    """Verify that implied capabilities are fully resolved at any depth."""

    def test_platform_admin_transitive(self):
        """platform:admin should expand to all sub-platform caps."""
        expanded = _expand_capabilities({PLATFORM_ADMIN.key})
        assert PLATFORM_MANAGE_USERS.key in expanded
        assert PLATFORM_MANAGE_GROUPS.key in expanded
        assert PLATFORM_MANAGE_ORG_UNITS.key in expanded
        assert PLATFORM_MANAGE_ACCESS.key in expanded
        assert PLATFORM_VIEW_AUDIT.key in expanded
        assert PLATFORM_MANAGE_APPS.key in expanded

    def test_enter_data_expands_to_view_my_data_and_view_console(self):
        expanded = _expand_capabilities({CARBON_ENTER_DATA.key})
        assert CARBON_VIEW_MY_DATA.key in expanded
        assert CARBON_VIEW_CONSOLE.key in expanded

    def test_verify_data_expands_view_verification(self):
        expanded = _expand_capabilities({CARBON_VERIFY_DATA.key})
        assert CARBON_VIEW_VERIFICATION.key in expanded
        assert CARBON_VIEW_CONSOLE.key in expanded

    def test_trigger_calculations_expands_view_calculations(self):
        expanded = _expand_capabilities({CARBON_TRIGGER_CALCULATIONS.key})
        assert CARBON_VIEW_CALCULATIONS.key in expanded
        assert CARBON_VIEW_CONSOLE.key in expanded

    def test_generate_reports_expands_view_console_and_dashboard(self):
        expanded = _expand_capabilities({CARBON_GENERATE_REPORTS.key})
        assert CARBON_VIEW_CONSOLE.key in expanded
        assert CARBON_VIEW_DASHBOARD.key in expanded

    def test_view_analytics_expands_view_console_and_dashboard(self):
        expanded = _expand_capabilities({CARBON_VIEW_ANALYTICS.key})
        assert CARBON_VIEW_CONSOLE.key in expanded
        assert CARBON_VIEW_DASHBOARD.key in expanded

    def test_catalog_manage_policies_expands_view_and_governance(self):
        expanded = _expand_capabilities({CATALOG_MANAGE_POLICIES.key})
        assert CATALOG_VIEW.key in expanded
        assert CATALOG_VIEW_GOVERNANCE.key in expanded

    @pytest.mark.parametrize("manage_cap,view_cap", [
        (CARBON_MANAGE_EMISSION_FACTORS.key, CARBON_VIEW_CONSOLE.key),
        (CARBON_MANAGE_CALCULATION_RULES.key, CARBON_VIEW_CONSOLE.key),
        (CARBON_MANAGE_GWP.key, CARBON_VIEW_CONSOLE.key),
        (CARBON_MANAGE_SBTI_TARGETS.key, CARBON_VIEW_CONSOLE.key),
        (CARBON_TRIGGER_CALCULATIONS.key, CARBON_VIEW_CALCULATIONS.key),
        (CARBON_VERIFY_DATA.key, CARBON_VIEW_VERIFICATION.key),
        (CARBON_ENTER_DATA.key, CARBON_VIEW_MY_DATA.key),
        (DQ_MANAGE_RULES.key, DQ_VIEW.key),
        (MDM_MANAGE.key, MDM_VIEW.key),
        (CATALOG_MANAGE_PRODUCTS.key, CATALOG_VIEW.key),
        (CATALOG_MANAGE_METADATA.key, CATALOG_VIEW.key),
        (CONNECTIONS_MANAGE.key, CONNECTIONS_VIEW.key),
        (IMPORTEXPORT_MANAGE.key, IMPORTEXPORT_VIEW.key),
        (DATASCHEMA_MANAGE.key, DATASCHEMA_VIEW.key),
        (AI_MANAGE_CONSOLE.key, AI_VIEW_CONSOLE.key),
    ])
    def test_every_manage_implies_view(self, manage_cap, view_cap):
        """Every manage capability should imply at least one view capability."""
        expanded = _expand_capabilities({manage_cap})
        assert view_cap in expanded, \
            f"{manage_cap} should imply {view_cap}"
