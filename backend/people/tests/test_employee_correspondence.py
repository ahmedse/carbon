# people/tests/test_employee_correspondence.py
# OF-16 — HR employee-scoped correspondence list
# (GET /people/employees/<pk>/correspondence/).

from datetime import date
from types import SimpleNamespace
import uuid

import pytest
from django.conf import settings

from correspondence.models import Correspondence, CorrespondenceEvent
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee

PREFIX = f'/{settings.API_PREFIX.strip("/")}'


@pytest.fixture
def hr_scene(db, create_user, create_scoped_role):
    """org + corr_type, a requester employee, a second employee, an HR user
    (people:view) and a non-HR user (no capability)."""
    corr_set = ReferenceSet.objects.create(
        name='correspondence_type', slug='correspondence-type',
    )
    corr_type = ReferenceValue.objects.create(
        reference_set=corr_set, code='leave_request', label='Leave Request',
    )
    org = OrgUnit.objects.create(
        name='Engineering', slug='engineering', code='ENG', org_type='department',
    )

    emp_user = create_user('of16_emp')
    other_user = create_user('of16_other')
    emp = Employee.objects.create(
        org_unit=org, employee_no='E-EMP', full_name='Employee',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=emp_user,
    )
    other = Employee.objects.create(
        org_unit=org, employee_no='E-OTHER', full_name='Other',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=other_user,
    )

    hr_user = create_user('of16_hr')
    create_scoped_role(hr_user, 'viewers_group')  # global → people:view
    outsider = create_user('of16_outsider')  # no capability

    def corr(requester, subject_type='', subject_id=None, title='Leave'):
        return Correspondence.objects.create(
            reference_no=f'DRAFT-{uuid.uuid4().hex[:12]}',
            corr_type=corr_type, org_unit=org, requester=requester,
            title=title, payload={}, status='submitted',
            subject_type=subject_type, subject_id=subject_id,
        )

    return SimpleNamespace(
        corr_type=corr_type, org=org, emp=emp, other=other,
        emp_user=emp_user, other_user=other_user,
        hr_user=hr_user, outsider=outsider, corr=corr,
    )


def _url(employee_id):
    return f'{PREFIX}/people/employees/{employee_id}/correspondence/'


@pytest.mark.django_db
def test_hr_lists_employee_correspondence(hr_scene, api_client, get_token_for_user):
    scene = hr_scene
    # emp is the requester of two leaves; other requested one; emp is the
    # subject of a profile-change request raised by other.
    c1 = scene.corr(scene.emp_user, title='Leave A')
    c2 = scene.corr(scene.emp_user, title='Leave B')
    scene.corr(scene.other_user, title='Other Leave')
    c3 = scene.corr(
        scene.other_user, subject_type='people.Employee',
        subject_id=scene.emp.pk, title='Profile change',
    )

    api_client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(scene.hr_user)}',
    )
    resp = api_client.get(_url(scene.emp.pk))
    assert resp.status_code == 200
    data = resp.json()
    assert data['count'] == 3
    assert {c['id'] for c in data['results']} == {c1.id, c2.id, c3.id}


@pytest.mark.django_db
def test_hr_sees_only_that_employee(hr_scene, api_client, get_token_for_user):
    scene = hr_scene
    c_emp = scene.corr(scene.emp_user, title='Employee leave')
    c_other = scene.corr(scene.other_user, title='Other leave')

    api_client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(scene.hr_user)}',
    )
    resp = api_client.get(_url(scene.emp.pk))
    assert resp.status_code == 200
    ids = {c['id'] for c in resp.json()['results']}
    assert ids == {c_emp.id}
    assert c_other.id not in ids


@pytest.mark.django_db
def test_non_hr_blocked(hr_scene, api_client, get_token_for_user):
    scene = hr_scene
    scene.corr(scene.emp_user)

    api_client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(scene.outsider)}',
    )
    resp = api_client.get(_url(scene.emp.pk))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_unauthenticated_401(hr_scene, api_client):
    scene = hr_scene
    resp = api_client.get(_url(scene.emp.pk))
    assert resp.status_code == 401


# --- OF-19 — HR-scoped correspondence detail (with timeline) ---------------

def _detail_url(employee_id, corr_id):
    return f'{PREFIX}/people/employees/{employee_id}/correspondence/{corr_id}/'


@pytest.mark.django_db
def test_hr_retrieves_correspondence_detail_with_timeline(
    hr_scene, api_client, get_token_for_user,
):
    scene = hr_scene
    c1 = scene.corr(scene.emp_user, title='Leave A')
    CorrespondenceEvent.objects.create(
        correspondence=c1, seq=1, event_type='created',
        from_status=None, to_status='submitted', payload={},
    )
    CorrespondenceEvent.objects.create(
        correspondence=c1, seq=2, event_type='acknowledged',
        from_status='submitted', to_status='submitted', payload={},
    )

    api_client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(scene.hr_user)}',
    )
    resp = api_client.get(_detail_url(scene.emp.pk, c1.id))
    assert resp.status_code == 200
    data = resp.json()
    assert data['id'] == c1.id
    assert data['reference_no'] == c1.reference_no
    assert len(data['events']) == 2
    assert [e['event_type'] for e in data['events']] == ['created', 'acknowledged']


@pytest.mark.django_db
def test_hr_cannot_fetch_another_employees_correspondence(
    hr_scene, api_client, get_token_for_user,
):
    scene = hr_scene
    c_other = scene.corr(scene.other_user, title='Other leave')

    api_client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(scene.hr_user)}',
    )
    # Requesting emp's detail URL with other's correspondence id → 404 (not 200).
    resp = api_client.get(_detail_url(scene.emp.pk, c_other.id))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_non_hr_blocked_from_detail(hr_scene, api_client, get_token_for_user):
    scene = hr_scene
    c1 = scene.corr(scene.emp_user, title='Leave A')

    api_client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(scene.outsider)}',
    )
    resp = api_client.get(_detail_url(scene.emp.pk, c1.id))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_subject_scoped_detail_visible_to_hr(
    hr_scene, api_client, get_token_for_user,
):
    scene = hr_scene
    # emp is the SUBJECT of a profile-change request raised by other.
    c3 = scene.corr(
        scene.other_user, subject_type='people.Employee',
        subject_id=scene.emp.pk, title='Profile change',
    )

    api_client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(scene.hr_user)}',
    )
    resp = api_client.get(_detail_url(scene.emp.pk, c3.id))
    assert resp.status_code == 200
    assert resp.json()['id'] == c3.id
