"""Regression tests for DT-BP-014: alamein.* data-owner provisioning.

Verifies that the idempotent ``provision_alamein_rbac`` management command
creates the department org units and provisions the five alamein.* users with
the correct group membership and ScopedRole(s), and that RBAC visibility is
scoped correctly (a transport data owner sees only Transportation).
"""

import pytest
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from accounts.constants import CARBON_LEAD_GROUP, DATAOWNERS_GROUP
from accounts.models import ScopedRole
from accounts.rbac_utils import get_visible_org_units
from mdm.models import OrgUnit

User = get_user_model()

USERNAMES = [
    "alamein.admin",
    "alamein.medical",
    "alamein.finance",
    "alamein.transport",
    "alamein.hotels",
]

EXPECTED_GROUPS = {
    "alamein.admin": CARBON_LEAD_GROUP,
    "alamein.medical": DATAOWNERS_GROUP,
    "alamein.finance": DATAOWNERS_GROUP,
    "alamein.transport": DATAOWNERS_GROUP,
    "alamein.hotels": DATAOWNERS_GROUP,
}

EXPECTED_ORG_UNITS = {
    "alamein.medical": [
        "College of Medicine / كلية الطب",
        "Educational Hospital / المستشفى التعليمي",
    ],
    "alamein.finance": ["Financial Affairs / الشؤون المادية"],
    "alamein.transport": ["Transportation / النقل"],
    "alamein.hotels": ["Student Hotels — Sakan Masr / فنادق الطلبة في عمارات سكن مصر"],
}

ALL_DEPARTMENT_NAMES = [
    "College of Medicine / كلية الطب",
    "Financial Affairs / الشؤون المادية",
    "Transportation / النقل",
    "Student Hotels — Sakan Masr / فنادق الطلبة في عمارات سكن مصر",
    "Educational Hospital / المستشفى التعليمي",
]


@pytest.mark.django_db
def test_provision_alamein_rbac_idempotent_and_scoped(monkeypatch):
    monkeypatch.setenv("ALAMEIN_USER_PASSWORD", "Alamein_2026")
    call_command("provision_alamein_rbac")
    # Run a second time to prove idempotency (no duplicates, no errors).
    call_command("provision_alamein_rbac")

    # 1. All five users exist, are active, and have the correct password/group.
    for username in USERNAMES:
        user = User.objects.get(username=username)
        assert user.is_active is True
        assert user.check_password("Alamein_2026") is True
        group_names = set(user.groups.values_list("name", flat=True))
        assert EXPECTED_GROUPS[username] in group_names

    # 2. alamein.admin holds a GLOBAL carbon_lead ScopedRole.
    admin = User.objects.get(username="alamein.admin")
    carbon_lead = Group.objects.get(name=CARBON_LEAD_GROUP)
    assert ScopedRole.objects.filter(
        user=admin, group=carbon_lead, org_unit=None, module=None, is_active=True
    ).exists()

    # 3. Each data-owner holds a ScopedRole pointing to the expected org unit(s).
    dataowners = Group.objects.get(name=DATAOWNERS_GROUP)
    for username, ou_names in EXPECTED_ORG_UNITS.items():
        user = User.objects.get(username=username)
        for ou_name in ou_names:
            org_unit = OrgUnit.objects.get(name=ou_name)
            assert ScopedRole.objects.filter(
                user=user, group=dataowners, org_unit=org_unit, module=None, is_active=True
            ).exists(), f"{username} missing ScopedRole for {ou_name}"

    # 4. alamein.transport sees ONLY Transportation (not Medicine/Hotels/...).
    transport = User.objects.get(username="alamein.transport")
    visible_names = {ou.name for ou in get_visible_org_units(transport)}
    assert "Transportation / النقل" in visible_names
    for other in ALL_DEPARTMENT_NAMES:
        if other != "Transportation / النقل":
            assert other not in visible_names
