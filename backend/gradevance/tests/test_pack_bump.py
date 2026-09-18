import pytest

from gradevance.models import Proposal
from gradevance.services.pack_bump import PackBumpError, PackBumpService
from gradevance.services.packs import eduos_pack_root


@pytest.mark.django_db
def test_pack_bump_writes_draft_device(tmp_path, monkeypatch):
    # Use real eduos root but clean up bump dirs after.
    root = eduos_pack_root()
    before = {p.name for p in (root / "engines/lct_semantics").iterdir() if p.is_dir()}

    prop = Proposal.objects.create(
        kind="anchor",
        status=Proposal.STATUS_ACCEPTED,
        payload={
            "sample_after": {
                "dimension": "semantic_gravity",
                "value": "SG--",
                "numeric": 4,
                "span_text": "The most difficult aspect of preparing for exams is time.",
            },
            "sample_rationale": "More abstract framing",
        },
        source_edit_ids=[],
    )
    result = PackBumpService().bump_device_from_proposal(
        prop,
        require_canary=False,
    )
    dest = root / result["dest_rel"]
    assert dest.is_dir()
    assert (dest / "device.yaml").is_file()
    text = (dest / "anchors.yaml").read_text()
    assert "promoted_" in text
    assert result["new_version"] >= 2

    # cleanup bump dirs created by this test
    after = {p.name for p in (root / "engines/lct_semantics").iterdir() if p.is_dir()}
    for name in after - before:
        import shutil

        shutil.rmtree(root / "engines/lct_semantics" / name, ignore_errors=True)


@pytest.mark.django_db
def test_pack_bump_rejects_non_accepted():
    prop = Proposal.objects.create(
        kind="anchor",
        status=Proposal.STATUS_DRAFT,
        payload={},
    )
    with pytest.raises(PackBumpError):
        PackBumpService().bump_device_from_proposal(prop, require_canary=False)
