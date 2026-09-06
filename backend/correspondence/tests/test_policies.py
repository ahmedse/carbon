import pytest

from correspondence.models import WorkflowPolicy, WorkflowPolicyStep
from correspondence.policies import PolicyNotFound, freeze_policy, resolve_policy
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue


@pytest.fixture
def reference_value(db):
    ref_set = ReferenceSet.objects.create(
        name='Correspondence Type', slug='correspondence-type',
    )
    return ReferenceValue.objects.create(
        reference_set=ref_set, code='leave_request', label='Leave Request',
    )


@pytest.fixture
def org_unit(db):
    return OrgUnit.objects.create(
        name='Engineering', slug='engineering', code='ENG', org_type='department',
    )


def _make_policy(corr_type, org_unit, name, version='1.0.0', is_active=True):
    return WorkflowPolicy.objects.create(
        name=name, corr_type=corr_type, org_unit=org_unit,
        version=version, is_active=is_active,
    )


@pytest.mark.django_db
def test_resolve_prefers_org_specific(reference_value, org_unit):
    OrgUnit.objects.create(name='HR', slug='hr', code='HR', org_type='division')
    _make_policy(reference_value, None, 'Global Leave')
    org_policy = _make_policy(reference_value, org_unit, 'Org Leave')

    assert resolve_policy(corr_type=reference_value, org_unit=org_unit) == org_policy


@pytest.mark.django_db
def test_resolve_falls_back_to_global(reference_value, org_unit):
    other_ou = OrgUnit.objects.create(
        name='HR', slug='hr', code='HR', org_type='division',
    )
    global_policy = _make_policy(reference_value, None, 'Global Leave')

    assert resolve_policy(corr_type=reference_value, org_unit=other_ou) == global_policy


@pytest.mark.django_db
def test_resolve_raises_when_no_active_policy(reference_value, org_unit):
    with pytest.raises(PolicyNotFound):
        resolve_policy(corr_type=reference_value, org_unit=org_unit)


@pytest.mark.django_db
def test_freeze_policy_snapshot(reference_value):
    policy = WorkflowPolicy.objects.create(
        name='Leave Default', corr_type=reference_value, org_unit=None,
        version='1.0.0', is_active=True,
        numbering_format='{PREFIX}-{YEAR}-{SEQ:04d}',
    )
    WorkflowPolicyStep.objects.create(
        policy=policy, order=2, role='hr', intent='review', is_active=True,
    )
    WorkflowPolicyStep.objects.create(
        policy=policy, order=1, role='manager', intent='approve',
        skip_if_self=True, is_active=True,
    )
    WorkflowPolicyStep.objects.create(
        policy=policy, order=3, role='manager', intent='approve', is_active=False,
    )

    snap = freeze_policy(policy)

    assert snap['policy_id'] == policy.id
    assert snap['policy_version'] == '1.0.0'
    assert snap['policy_snapshot']['name'] == 'Leave Default'
    assert snap['policy_snapshot']['numbering_format'] == '{PREFIX}-{YEAR}-{SEQ:04d}'
    steps = snap['policy_snapshot']['steps']
    assert [s['order'] for s in steps] == [1, 2]
    assert steps[0]['role'] == 'manager'
    assert steps[0]['skip_if_self'] is True
    assert steps[0]['auto_approve'] is False
