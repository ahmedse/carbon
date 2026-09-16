# mdm/tests/test_org_unit_root.py
# ADR-0028 / NSR-8A: single active OrgUnit root + instance-gated org seeds.

from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from mdm.models import OrgUnit
from mdm.services import get_deployment_root


@pytest.mark.django_db
def test_cannot_create_second_active_root():
    OrgUnit.objects.create(name='Root A', slug='root-a', org_type='company', code='A')
    with pytest.raises(ValidationError) as exc:
        OrgUnit.objects.create(name='Root B', slug='root-b', org_type='company', code='B')
    assert 'parent' in exc.value.message_dict


@pytest.mark.django_db
def test_can_update_existing_root():
    root = OrgUnit.objects.create(name='Root', slug='root', org_type='company', code='R')
    root.name = 'Root Renamed'
    root.description = 'still the only root'
    root.save()
    root.refresh_from_db()
    assert root.name == 'Root Renamed'
    assert root.parent_id is None
    assert get_deployment_root().id == root.id


@pytest.mark.django_db
def test_get_deployment_root_returns_the_root():
    assert get_deployment_root() is None
    root = OrgUnit.objects.create(name='Deploy', slug='deploy', org_type='company')
    child = OrgUnit.objects.create(
        name='Child', slug='deploy-child', org_type='division', parent=root,
    )
    found = get_deployment_root()
    assert found is not None
    assert found.id == root.id
    assert child.id in found.get_descendant_ids(include_self=True)


@pytest.mark.django_db
def test_get_deployment_root_raises_on_multiple_roots():
    # Bypass model.clean via QuerySet.update after creating one inactive root
    # then force a second active root through bulk update (corrupt state).
    a = OrgUnit.objects.create(name='A', slug='a-root', org_type='company')
    b = OrgUnit(
        name='B', slug='b-root', org_type='company', parent=a, is_active=True,
    )
    # Save child under a, then detach with queryset update (skips full_clean).
    b.save()
    OrgUnit.objects.filter(pk=b.pk).update(parent_id=None)
    with pytest.raises(RuntimeError, match='Multiple active OrgUnit roots'):
        get_deployment_root()


@pytest.mark.django_db
@override_settings(DJANGO_BRAND='aastmt', INSTANCE_NAME='AASTMT')
def test_seed_gofsco_org_rejects_wrong_brand():
    with pytest.raises(CommandError, match='instance-gated'):
        call_command('seed_gofsco_org', '--dry-run', stdout=StringIO())


@pytest.mark.django_db
@override_settings(DJANGO_BRAND='nibras', INSTANCE_NAME='gofsco')
def test_seed_gofsco_org_allows_nibras_brand_dry_run():
    out = StringIO()
    call_command('seed_gofsco_org', '--dry-run', stdout=out)
    assert 'dry-run' in out.getvalue()
    assert 'GOFSCO' in out.getvalue()


@pytest.mark.django_db
@override_settings(DJANGO_BRAND='nibras', INSTANCE_NAME='nibras')
def test_seed_gofsco_org_allows_correct_brand_and_is_idempotent():
    call_command('seed_gofsco_org', stdout=StringIO())
    root = get_deployment_root()
    assert root is not None
    assert root.slug == 'gofsco'
    assert root.parent_id is None
    call_command('seed_gofsco_org', stdout=StringIO())
    assert OrgUnit.objects.filter(parent__isnull=True, is_active=True).count() == 1


@pytest.mark.django_db
@override_settings(DJANGO_BRAND='nibras', INSTANCE_NAME='gofsco')
def test_seed_aastmt_org_rejects_wrong_brand():
    with pytest.raises(CommandError, match='instance-gated'):
        call_command('seed_aastmt_org', stdout=StringIO())


@pytest.mark.django_db
@override_settings(DJANGO_BRAND='aastmt', INSTANCE_NAME='AASTMT')
def test_seed_aastmt_org_allows_correct_brand():
    call_command('seed_aastmt_org', stdout=StringIO())
    root = get_deployment_root()
    assert root is not None
    assert root.slug == 'aast'
    assert root.parent_id is None
    call_command('seed_aastmt_org', stdout=StringIO())
    assert OrgUnit.objects.filter(parent__isnull=True, is_active=True).count() == 1


@pytest.mark.django_db
def test_inactive_second_root_allowed():
    OrgUnit.objects.create(name='Active Root', slug='active-root', org_type='company')
    inactive = OrgUnit(
        name='Inactive Root',
        slug='inactive-root',
        org_type='company',
        parent=None,
        is_active=False,
    )
    inactive.save()
    assert get_deployment_root().slug == 'active-root'
