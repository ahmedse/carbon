# correspondence/tests/test_admin_filters_notifications.py
# OF-16 — admin-widened list filters + notification read/read-all API.

from datetime import date
from types import SimpleNamespace
import uuid

import pytest
from django.conf import settings

from correspondence.models import Correspondence, Notification
from correspondence.notifications import notify
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee

PREFIX = f'/{settings.API_PREFIX.strip("/")}'
LIST_URL = f'{PREFIX}/correspondence/'


@pytest.fixture
def filter_scene(db, create_user, create_scoped_role):
    """Two corr_types, two orgs, two requester employees, a
    correspondence:admin (global people_lead) and their correspondence factory."""
    corr_set = ReferenceSet.objects.create(
        name='correspondence_type', slug='correspondence-type',
    )
    leave = ReferenceValue.objects.create(
        reference_set=corr_set, code='leave_request', label='Leave Request',
    )
    memo = ReferenceValue.objects.create(
        reference_set=corr_set, code='internal_memo', label='Internal Memo',
    )
    org1 = OrgUnit.objects.create(
        name='Engineering', slug='engineering', code='ENG', org_type='department',
    )
    org2 = OrgUnit.objects.create(
        name='Finance', slug='finance', code='FIN', org_type='department',
        parent=org1,
    )

    admin = create_user('of16_admin')
    create_scoped_role(admin, 'people_lead')  # global → correspondence:admin

    req1 = create_user('of16_req1')
    req2 = create_user('of16_req2')
    emp1 = Employee.objects.create(
        org_unit=org1, employee_no='E-F1', full_name='One',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=req1,
    )
    emp2 = Employee.objects.create(
        org_unit=org1, employee_no='E-F2', full_name='Two',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=req2,
    )

    def corr(requester, org, ctype, status, subject_type='', subject_id=None):
        return Correspondence.objects.create(
            reference_no=f'DRAFT-{uuid.uuid4().hex[:12]}',
            corr_type=ctype, org_unit=org, requester=requester,
            title='T', payload={}, status=status,
            subject_type=subject_type, subject_id=subject_id,
        )

    return SimpleNamespace(
        leave=leave, memo=memo, org1=org1, org2=org2,
        admin=admin, req1=req1, req2=req2, emp1=emp1, emp2=emp2,
        corr=corr,
    )


def _auth(api_client, user, get_token_for_user):
    api_client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}',
    )
    return api_client


def _ids(resp):
    data = resp.json()
    # Pagination is disabled during pytest → the correspondence list is a
    # plain list; tolerate a dict envelope for future-proofing.
    items = data['results'] if isinstance(data, dict) else data
    return {c['id'] for c in items}


# ── admin filters ───────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_admin_requester_filter(filter_scene, api_client, get_token_for_user):
    scene = filter_scene
    c1 = scene.corr(scene.req1, scene.org1, scene.leave, 'submitted')
    c2 = scene.corr(scene.req2, scene.org1, scene.leave, 'submitted')

    _auth(api_client, scene.admin, get_token_for_user)
    resp = api_client.get(f'{LIST_URL}?requester={scene.req1.id}')
    assert resp.status_code == 200
    assert _ids(resp) == {c1.id}
    assert c2.id not in _ids(resp)


@pytest.mark.django_db
def test_admin_employee_filter(filter_scene, api_client, get_token_for_user):
    scene = filter_scene
    # emp1 as requester, emp1 as subject (raised by req2), and an unrelated corr.
    c1 = scene.corr(scene.req1, scene.org1, scene.leave, 'submitted')
    c2 = scene.corr(
        scene.req2, scene.org1, scene.leave, 'submitted',
        subject_type='people.Employee', subject_id=scene.emp1.pk,
    )
    c3 = scene.corr(scene.req2, scene.org1, scene.leave, 'submitted')

    _auth(api_client, scene.admin, get_token_for_user)
    resp = api_client.get(f'{LIST_URL}?employee={scene.emp1.id}')
    assert resp.status_code == 200
    assert _ids(resp) == {c1.id, c2.id}
    assert c3.id not in _ids(resp)


@pytest.mark.django_db
def test_admin_org_unit_filter(filter_scene, api_client, get_token_for_user):
    scene = filter_scene
    c1 = scene.corr(scene.req1, scene.org1, scene.leave, 'submitted')
    c2 = scene.corr(scene.req1, scene.org2, scene.leave, 'submitted')

    _auth(api_client, scene.admin, get_token_for_user)
    resp = api_client.get(f'{LIST_URL}?org_unit={scene.org1.id}')
    assert resp.status_code == 200
    assert _ids(resp) == {c1.id}
    assert c2.id not in _ids(resp)


@pytest.mark.django_db
def test_admin_corr_type_filter(filter_scene, api_client, get_token_for_user):
    scene = filter_scene
    c1 = scene.corr(scene.req1, scene.org1, scene.leave, 'submitted')
    c2 = scene.corr(scene.req1, scene.org1, scene.memo, 'submitted')

    _auth(api_client, scene.admin, get_token_for_user)
    resp = api_client.get(f'{LIST_URL}?corr_type=leave_request')
    assert resp.status_code == 200
    assert _ids(resp) == {c1.id}
    assert c2.id not in _ids(resp)


@pytest.mark.django_db
def test_admin_status_filter(filter_scene, api_client, get_token_for_user):
    scene = filter_scene
    c1 = scene.corr(scene.req1, scene.org1, scene.leave, 'submitted')
    c2 = scene.corr(scene.req1, scene.org1, scene.leave, 'approved')

    _auth(api_client, scene.admin, get_token_for_user)
    resp = api_client.get(f'{LIST_URL}?status=approved')
    assert resp.status_code == 200
    assert _ids(resp) == {c2.id}
    assert c1.id not in _ids(resp)


@pytest.mark.django_db
def test_admin_search_and_manager_filter(filter_scene, api_client, get_token_for_user):
    scene = filter_scene
    held = scene.corr(scene.req1, scene.org1, scene.leave, 'submitted')
    held.title = 'Annual for One'
    held.current_approver_ids = [scene.req2.id]
    held.approver_chain = [{'order': 1, 'role': 'manager', 'user_ids': [scene.req2.id]}]
    held.current_step = 0
    held.save()
    other = scene.corr(scene.req2, scene.org1, scene.leave, 'submitted')

    _auth(api_client, scene.admin, get_token_for_user)
    by_name = api_client.get(f'{LIST_URL}?q=One')
    assert by_name.status_code == 200
    assert held.id in _ids(by_name)
    assert other.id not in _ids(by_name)

    by_manager = api_client.get(f'{LIST_URL}?manager={scene.emp2.id}')
    assert by_manager.status_code == 200
    assert _ids(by_manager) == {held.id}


@pytest.mark.django_db
def test_admin_cannot_decide_a_step_they_do_not_hold(
    filter_scene, api_client, get_token_for_user,
):
    scene = filter_scene
    held = scene.corr(scene.req1, scene.org1, scene.leave, 'submitted')
    held.current_approver_ids = [scene.req1.id]
    held.save(update_fields=['current_approver_ids'])

    _auth(api_client, scene.admin, get_token_for_user)
    resp = api_client.post(f'{LIST_URL}{held.id}/approve/', {'comment': 'no'}, format='json')
    assert resp.status_code == 403
    held.refresh_from_db()
    assert held.status == 'submitted'


# ── non-admin self-scoping remains ──────────────────────────────────────────

@pytest.mark.django_db
def test_non_admin_stays_self_scoped_ignoring_admin_filters(
    filter_scene, api_client, get_token_for_user,
):
    scene = filter_scene
    c1 = scene.corr(scene.req1, scene.org1, scene.leave, 'submitted')
    c2 = scene.corr(scene.req2, scene.org1, scene.leave, 'submitted')

    # req1 is NOT an admin — passing another requester's id must be ignored.
    _auth(api_client, scene.req1, get_token_for_user)
    resp = api_client.get(f'{LIST_URL}?requester={scene.req2.id}')
    assert resp.status_code == 200
    assert _ids(resp) == {c1.id}
    assert c2.id not in _ids(resp)


# ── notifications ───────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_notifications_roundtrip(filter_scene, api_client, get_token_for_user):
    scene = filter_scene
    corr = scene.corr(scene.req1, scene.org1, scene.leave, 'submitted')

    notify(corr, user_ids=[scene.req1.id], type='action_needed',
           title='Action needed', body='Please approve')
    notify(corr, user_ids=[scene.req1.id], type='status_changed',
           title='Status changed', body='Submitted')
    notify(corr, user_ids=[scene.req2.id], type='action_needed',
           title='Other', body='Not yours')

    _auth(api_client, scene.req1, get_token_for_user)

    # list: only req1's two notifications, both unread, reference_no exposed.
    resp = api_client.get(f'{PREFIX}/correspondence/notifications/')
    assert resp.status_code == 200
    data = resp.json()
    assert data['unread_count'] == 2
    assert len(data['results']) == 2
    assert {n['reference_no'] for n in data['results']} == {corr.reference_no}
    assert all(n['correspondence_id'] == corr.id for n in data['results'])

    # mark one read
    nid = data['results'][0]['id']
    resp = api_client.post(f'{PREFIX}/correspondence/notifications/{nid}/read/')
    assert resp.status_code == 200
    assert resp.json()['id'] == nid
    assert resp.json()['is_read'] is True

    # unread count drops to 1; is_read filter still reports total unread.
    resp = api_client.get(f'{PREFIX}/correspondence/notifications/')
    assert resp.json()['unread_count'] == 1

    resp = api_client.get(f'{PREFIX}/correspondence/notifications/?is_read=true')
    assert resp.json()['unread_count'] == 1
    assert len(resp.json()['results']) == 1
    assert resp.json()['results'][0]['is_read'] is True

    # read-all → count drops to 0
    resp = api_client.post(f'{PREFIX}/correspondence/notifications/read-all/')
    assert resp.status_code == 200
    assert resp.json()['updated'] == 1
    assert resp.json()['unread_count'] == 0

    resp = api_client.get(f'{PREFIX}/correspondence/notifications/')
    assert resp.json()['unread_count'] == 0


@pytest.mark.django_db
def test_notifications_self_scoped_and_cannot_touch_others(
    filter_scene, api_client, get_token_for_user,
):
    scene = filter_scene
    corr = scene.corr(scene.req1, scene.org1, scene.leave, 'submitted')
    notify(corr, user_ids=[scene.req1.id], type='action_needed',
           title='For req1', body='x')
    notify(corr, user_ids=[scene.req2.id], type='action_needed',
           title='For req2', body='y')

    req1_notif = Notification.objects.filter(user=scene.req1).first()

    # req2 sees only their own notification in the list.
    _auth(api_client, scene.req2, get_token_for_user)
    resp = api_client.get(f'{PREFIX}/correspondence/notifications/')
    assert resp.status_code == 200
    assert resp.json()['unread_count'] == 1
    assert len(resp.json()['results']) == 1

    # req2 cannot mark req1's notification read (self-scoped get_object → 404).
    resp = api_client.post(
        f'{PREFIX}/correspondence/notifications/{req1_notif.id}/read/',
    )
    assert resp.status_code == 404
