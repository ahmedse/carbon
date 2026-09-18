import pytest
from django.core.management import call_command

from gradevance.models import AssignmentProfileRecord
from gradevance.services.packs import list_profiles


@pytest.mark.django_db
def test_sync_eduos_packs_idempotent():
    call_command("sync_eduos_packs")
    n1 = AssignmentProfileRecord.objects.count()
    assert n1 >= 6
    assert n1 == len(list_profiles())
    call_command("sync_eduos_packs")
    assert AssignmentProfileRecord.objects.count() == n1
    naa = AssignmentProfileRecord.objects.get(pack_id="naa_cycle1_exam_prep", version=1)
    assert naa.content_hash
    assert naa.discipline


@pytest.mark.django_db
def test_sync_eduos_packs_prune():
    call_command("sync_eduos_packs")
    AssignmentProfileRecord.objects.create(
        pack_id="stale_orphan_profile",
        version=99,
        name="orphan",
        status="draft",
        discipline="x",
        genre="y",
        mode="formative",
    )
    call_command("sync_eduos_packs", prune=True)
    assert not AssignmentProfileRecord.objects.filter(pack_id="stale_orphan_profile").exists()
