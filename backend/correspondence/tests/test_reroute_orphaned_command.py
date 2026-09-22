# correspondence/tests/test_reroute_orphaned_command.py
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee, LeaveEntitlement, LeaveRecord

from correspondence import fsm
from correspondence.models import Correspondence, WorkflowPolicy, WorkflowPolicyStep


@pytest.fixture
def orphan_leave(db, create_user, create_scoped_role):
    root = OrgUnit.objects.create(name='R', slug='reroute-root', org_type='company')
    ou = OrgUnit.objects.create(name='Unit', slug='reroute-ou', parent=root, org_type='department')
    mgr_user = create_user('emp_mgr_rr', password='x', is_staff=True)
    create_scoped_role(mgr_user, 'manager_group', org_unit=ou)
    req_user = create_user('emp_req_rr', password='x')
    create_scoped_role(req_user, 'employee_group')
    mgr = Employee.objects.create(
        org_unit=ou, employee_no='M9', full_name='Mgr', user=mgr_user,
        basic_salary=Decimal('0'), is_active=True,
    )
    req = Employee.objects.create(
        org_unit=ou, employee_no='E9', full_name='Emp', user=req_user,
        basic_salary=Decimal('0'), is_active=True,
        # no manager yet
    )
    rs, _ = ReferenceSet.objects.get_or_create(name='leave_type', defaults={'slug': 'leave-type'})
    annual, _ = ReferenceValue.objects.get_or_create(
        reference_set=rs, code='annual', defaults={'label': 'Annual', 'is_active': True},
    )
    crs, _ = ReferenceSet.objects.get_or_create(
        name='correspondence_type', defaults={'slug': 'correspondence-type'},
    )
    leave_ct, _ = ReferenceValue.objects.get_or_create(
        reference_set=crs, code='leave_request',
        defaults={'label': 'Leave Request', 'is_active': True},
    )
    policy = WorkflowPolicy.objects.create(
        corr_type=leave_ct, name='Leave RR', version='1.0.0', is_active=True,
    )
    WorkflowPolicyStep.objects.create(
        policy=policy, order=1, role='manager', intent='approve',
        skip_if_self=True, is_active=True,
    )
    LeaveEntitlement.objects.create(
        employee=req, year=date.today().year, leave_type=annual, entitled_days=Decimal('20'),
    )
    start = date.today() + timedelta(days=10)
    record = LeaveRecord.objects.create(
        employee=req, leave_type=annual, start_date=start, end_date=start,
        days=Decimal('1'), status='draft',
    )
    corr = Correspondence.objects.create(
        corr_type=leave_ct, subject_type='people.LeaveRecord', subject_id=record.pk,
        org_unit=ou, requester=req_user,
        title='Leave orphan test', payload={'leave_type': 'annual', 'days': '1'},
        status='draft', reference_no='DRAFT-RR',
    )
    corr = fsm.submit_correspondence(corr=corr, by=req_user, subject=record, subject_label='people.LeaveRecord')
    assert corr.current_approver_ids == []
    return {'corr': corr, 'req': req, 'mgr': mgr, 'mgr_user': mgr_user}


@pytest.mark.django_db
def test_reroute_after_manager_assigned(orphan_leave):
    orphan_leave['req'].manager = orphan_leave['mgr']
    orphan_leave['req'].save(update_fields=['manager'])
    call_command('reroute_orphaned_correspondence')
    orphan_leave['corr'].refresh_from_db()
    assert orphan_leave['mgr_user'].id in (orphan_leave['corr'].current_approver_ids or [])
