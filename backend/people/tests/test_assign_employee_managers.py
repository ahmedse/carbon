# people/tests/test_assign_employee_managers.py
from decimal import Decimal

import pytest
from django.core.management import call_command
from mdm.models import OrgUnit
from people.models import Employee, Position


@pytest.fixture
def org_world(db, create_user):
    root = OrgUnit.objects.create(name='Ops Root', slug='ops-root-mgr', org_type='company')
    ou = OrgUnit.objects.create(
        name='Coiled Tubing', slug='ct-mgr-test', org_type='department', parent=root,
    )
    lead_pos = Position.objects.create(org_unit=ou, code='SUP', title='Supervisor')
    lead_user = create_user('emp_lead', password='x')
    lead = Employee.objects.create(
        org_unit=ou, employee_no='L1', full_name='Lead One', user=lead_user,
        position=lead_pos, basic_salary=Decimal('0'), is_active=True,
    )
    report_user = create_user('emp_rep', password='x')
    report = Employee.objects.create(
        org_unit=ou, employee_no='R1', full_name='Report One', user=report_user,
        basic_salary=Decimal('0'), is_active=True,
    )
    return {'ou': ou, 'lead': lead, 'report': report}


@pytest.mark.django_db
def test_org_leads_assigns_manager(org_world):
    call_command('assign_employee_managers', '--org-leads')
    org_world['report'].refresh_from_db()
    assert org_world['report'].manager_id == org_world['lead'].id


@pytest.mark.django_db
def test_org_leads_skips_existing_unless_force(org_world, create_user):
    other_user = create_user('emp_other', password='x')
    other = Employee.objects.create(
        org_unit=org_world['ou'], employee_no='O1', full_name='Other',
        user=other_user, basic_salary=Decimal('0'), is_active=True,
    )
    org_world['report'].manager = other
    org_world['report'].save(update_fields=['manager'])
    call_command('assign_employee_managers', '--org-leads')
    org_world['report'].refresh_from_db()
    assert org_world['report'].manager_id == other.id
    call_command('assign_employee_managers', '--org-leads', '--force')
    org_world['report'].refresh_from_db()
    assert org_world['report'].manager_id == org_world['lead'].id
