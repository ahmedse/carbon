# mdm/tests/test_org_unit_manager.py
from datetime import date
from decimal import Decimal

import pytest
from mdm.models import OrgUnit
from mdm.org_unit_manager import resolve_org_unit_manager_user_id
from people.models import Employee


@pytest.mark.django_db
def test_resolve_org_unit_manager_user_id_walks_parent(create_user):
    root = OrgUnit.objects.create(name='Root OU', slug='ou-mgr-root', org_type='company')
    child = OrgUnit.objects.create(
        name='Child OU', slug='ou-mgr-child', org_type='department', parent=root,
    )
    mgr_user = create_user('ou_mgr_u', password='x')
    mgr = Employee.objects.create(
        org_unit=root, employee_no='OU-MGR-1', full_name='Unit Mgr',
        user=mgr_user, basic_salary=Decimal('0'), join_date=date(2026, 1, 1),
        is_active=True,
    )
    root.manager_employee_id = mgr.id
    root.save(update_fields=['manager_employee_id'])

    assert resolve_org_unit_manager_user_id(child) == mgr_user.id
    assert resolve_org_unit_manager_user_id(root) == mgr_user.id


@pytest.mark.django_db
def test_resolve_org_unit_manager_user_id_none_when_empty():
    ou = OrgUnit.objects.create(name='Bare', slug='ou-mgr-bare', org_type='department')
    assert resolve_org_unit_manager_user_id(ou) is None
    assert resolve_org_unit_manager_user_id(None) is None
