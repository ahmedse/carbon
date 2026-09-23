# Each domain read uses live duties that grant that domain's verb.

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from accounts.models import ScopedRole
from accounts.rbac_utils import org_scope_for_capability
from mdm.models import OrgUnit

User = get_user_model()


def _role(user, group_name, org):
    group, _ = Group.objects.get_or_create(name=group_name)
    return ScopedRole.objects.create(
        user=user, group=group, org_unit=org, module=None, is_active=True,
    )


@pytest.mark.django_db
def test_carbon_scope_follows_carbon_duty_not_people_duty():
    root = OrgUnit.objects.create(name="Root", slug="cap-root", org_type="company")
    parent = OrgUnit.objects.create(
        name="Ops", slug="cap-ops", parent=root, org_type="division",
    )
    child = OrgUnit.objects.create(
        name="Plant", slug="cap-plant", parent=parent, org_type="department",
    )
    sibling = OrgUnit.objects.create(
        name="HR", slug="cap-hr", parent=root, org_type="department",
    )
    carbon_user = User.objects.create_user("carbon_reader", password="x")
    people_user = User.objects.create_user("people_reader", password="x")
    _role(carbon_user, "carbon_lead", parent)
    _role(people_user, "people_lead", parent)

    carbon = org_scope_for_capability(carbon_user, "carbon:view_console")
    assert carbon.unrestricted is False
    assert carbon.ids == {parent.id, child.id}

    people_on_carbon = org_scope_for_capability(people_user, "carbon:view_console")
    assert people_on_carbon.ids == set()

    catalog = org_scope_for_capability(carbon_user, "catalog:view")
    assert catalog.ids == set()

    people = org_scope_for_capability(people_user, "people:view")
    assert child.id in people.ids
    assert sibling.id not in people.ids


@pytest.mark.django_db
def test_expired_duty_drops_out_of_scope():
    org = OrgUnit.objects.create(name="Only", slug="cap-only", org_type="company")
    user = User.objects.create_user("expired_carbon", password="x")
    role = _role(user, "viewers_group", org)
    role.valid_to = date(2020, 1, 1)
    role.save(update_fields=["valid_to"])

    scope = org_scope_for_capability(user, "carbon:view_console")
    assert scope.unrestricted is False
    assert scope.ids == set()
