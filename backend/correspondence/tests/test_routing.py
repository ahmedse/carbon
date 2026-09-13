# File: correspondence/tests/test_routing.py
# OF-4 — approver routing + delegation resolution.

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from correspondence.models import Delegation
from correspondence.routing import apply_delegation, resolve_step_approvers
from mdm.models import OrgUnit
from people.models import Employee


@pytest.fixture
def org(db):
    return OrgUnit.objects.create(
        name='Engineering', slug='engineering', code='ENG', org_type='department',
    )


def _make_employee(org, user=None, employee_no='E-001', **overrides):
    kwargs = dict(
        org_unit=org,
        employee_no=employee_no,
        full_name=f'{employee_no} Employee',
        basic_salary='1000.000',
        join_date=date(2026, 1, 1),
        user=user,
    )
    kwargs.update(overrides)
    return Employee.objects.create(**kwargs)


def _step(role, *, specific_user_id=None, skip_if_self=False):
    """A minimal WorkflowPolicyStep-like object (only routing fields matter)."""
    return SimpleNamespace(
        role=role, specific_user_id=specific_user_id, skip_if_self=skip_if_self,
    )


# ── 'manager' role ─────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_manager_role_resolves_to_managers_user_id(org, create_user):
    manager_user = create_user('of4_mgr')
    requester_user = create_user('of4_req')
    manager_emp = _make_employee(org, user=manager_user, employee_no='E-MGR')
    _make_employee(org, user=requester_user, employee_no='E-REQ', manager=manager_emp)

    ids = resolve_step_approvers(
        step=_step('manager'), requester=requester_user, org_unit=org,
    )

    assert ids == [manager_user.id]


@pytest.mark.django_db
def test_manager_role_empty_when_no_manager(org, create_user):
    requester_user = create_user('of4_req_nomgr')
    _make_employee(org, user=requester_user, employee_no='E-REQ2')

    ids = resolve_step_approvers(
        step=_step('manager'), requester=requester_user, org_unit=org,
    )

    assert ids == []


@pytest.mark.django_db
def test_manager_role_empty_when_no_employee_profile(create_user):
    requester_user = create_user('of4_req_noprofile')

    ids = resolve_step_approvers(
        step=_step('manager'), requester=requester_user, org_unit=None,
    )

    assert ids == []


# ── 'specific_user' role ───────────────────────────────────────────────────

@pytest.mark.django_db
def test_specific_user_role_returns_user_id(create_user):
    target = create_user('of4_target')
    requester = create_user('of4_req_spec')

    ids = resolve_step_approvers(
        step=_step('specific_user', specific_user_id=target.id), requester=requester,
    )

    assert ids == [target.id]


@pytest.mark.django_db
def test_specific_user_role_empty_when_none(create_user):
    requester = create_user('of4_req_specnone')

    ids = resolve_step_approvers(
        step=_step('specific_user', specific_user_id=None), requester=requester,
    )

    assert ids == []


# ── 'any_admin' role ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_any_admin_returns_superusers(create_user):
    super_user = create_user('of4_admin', is_superuser=True)
    normal = create_user('of4_normal')

    ids = resolve_step_approvers(step=_step('any_admin'), requester=normal)

    assert super_user.id in ids
    assert normal.id not in ids


# ── 'hr' role ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_hr_returns_people_manage_users(create_user, create_scoped_role):
    hr_user = create_user('of4_hr')
    create_scoped_role(hr_user, 'people_lead')  # grants people:manage
    other = create_user('of4_other')

    ids = resolve_step_approvers(step=_step('hr'), requester=other)

    assert ids == [hr_user.id]


@pytest.mark.django_db
def test_hr_empty_without_people_manage(create_user):
    requester = create_user('of4_hr_none')

    ids = resolve_step_approvers(step=_step('hr'), requester=requester)

    assert ids == []


# ── 'finance' role ────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_finance_role_empty_without_finance_group(create_user):
    requester = create_user('of4_finance_none')

    ids = resolve_step_approvers(step=_step('finance'), requester=requester)

    assert ids == []


@pytest.mark.django_db
def test_finance_returns_finance_group_users(create_user, create_scoped_role):
    finance_user = create_user('of4_finance')
    create_scoped_role(finance_user, 'finance_group')  # grants correspondence:finance
    other = create_user('of4_other')

    ids = resolve_step_approvers(step=_step('finance'), requester=other)

    assert ids == [finance_user.id]


@pytest.mark.django_db
def test_finance_routing_query_count_is_constant(create_user, create_scoped_role):
    # F16 regression: a loan submission fired 2665 SQL queries because
    # _users_with_capability() called has_capability() once per active user.
    # The query count must not scale with the number of ordinary users.
    requester = create_user('of4_finance_req')
    finance_user = create_user('of4_finance_approver')
    create_scoped_role(finance_user, 'finance_group')

    for i in range(30):
        create_user(f'of4_ordinary_{i}')

    with CaptureQueriesContext(connection) as ctx:
        ids = resolve_step_approvers(step=_step('finance'), requester=requester)

    assert ids == [finance_user.id]
    assert len(ctx.captured_queries) < 10


# ── skip_if_self ───────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_skip_if_self_drops_requester(create_user):
    requester = create_user('of4_selfreq')

    ids = resolve_step_approvers(
        step=_step('specific_user', specific_user_id=requester.id, skip_if_self=True),
        requester=requester,
    )

    assert ids == []


@pytest.mark.django_db
def test_skip_if_self_keeps_other_approvers(org, create_user):
    requester = create_user('of4_selfreq2')
    other = create_user('of4_otherapprover')

    ids = resolve_step_approvers(
        step=_step('specific_user', specific_user_id=other.id, skip_if_self=True),
        requester=requester,
    )

    assert ids == [other.id]


# ── apply_delegation ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_apply_delegation_replaces_delegator(create_user):
    delegator = create_user('of4_del')
    delegate = create_user('of4_del_target')
    Delegation.objects.create(delegator=delegator, delegate=delegate, is_active=True)

    assert apply_delegation([delegator.id]) == [delegate.id]


@pytest.mark.django_db
def test_apply_delegation_inactive_leaves_unchanged(create_user):
    delegator = create_user('of4_del_inactive')
    delegate = create_user('of4_del_inactive_target')
    Delegation.objects.create(
        delegator=delegator, delegate=delegate, is_active=False,
    )

    assert apply_delegation([delegator.id]) == [delegator.id]


@pytest.mark.django_db
def test_apply_delegation_expired_leaves_unchanged(create_user):
    delegator = create_user('of4_del_expired')
    delegate = create_user('of4_del_expired_target')
    Delegation.objects.create(
        delegator=delegator,
        delegate=delegate,
        is_active=True,
        from_date=timezone.now() - timedelta(days=10),
        to_date=timezone.now() - timedelta(days=5),
    )

    assert apply_delegation([delegator.id]) == [delegator.id]


@pytest.mark.django_db
def test_apply_delegation_no_delegation_stays_as_is(create_user):
    user = create_user('of4_nodel')

    assert apply_delegation([user.id]) == [user.id]


@pytest.mark.django_db
def test_apply_delegation_preserves_order(create_user):
    a = create_user('of4_order_a')
    b = create_user('of4_order_b')
    c = create_user('of4_order_c')
    Delegation.objects.create(delegator=b, delegate=c, is_active=True)

    assert apply_delegation([a.id, b.id]) == [a.id, c.id]
