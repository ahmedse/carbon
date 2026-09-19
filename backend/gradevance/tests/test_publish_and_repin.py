"""Publish gate + profile re-pin tests."""
from __future__ import annotations

import pytest

from gradevance.models import Assignment, Proposal
from gradevance.services.pack_bump import PackBumpService
from gradevance.services.packs import eduos_pack_root, find_profile_file_for_id, load_profile
from gradevance.services.publish import PublishGateError, assert_summative_publish_allowed, evaluate_publish_gate
from gradevance.services.repin import ProfileRepinService, RepinError


def test_formative_publish_gate_not_required():
    loaded = load_profile(find_profile_file_for_id("naa_cycle1_exam_prep", 1))
    result = evaluate_publish_gate(loaded)
    assert result["required"] is False
    assert result["passed"] is True


def test_summative_lct_gate_runs_held_out():
    loaded = load_profile(find_profile_file_for_id("naa_cycle1_exam_prep", 1))
    result = evaluate_publish_gate(loaded, as_mode="summative", min_held_out=5)
    assert result["required"] is True
    assert result["held_out_n"] >= 5
    # Heuristic coder may or may not pass κ — just ensure structure.
    assert "passed" in result
    assert "reliability" in result
    assert result.get("expert_trusted") is True
    assert result.get("gold_status") in {"expert_disjoint", "expert", "faculty_coded_disjoint", "unspecified"}


def test_medicine_seeded_held_out_blocks_summative():
    """Clinical reflection OSCE fixture remains seeded — summative blocked."""
    loaded = load_profile(find_profile_file_for_id("medicine_osce_abdominal", 1))
    result = evaluate_publish_gate(loaded, as_mode="summative", min_held_out=1)
    assert result["required"] is True
    assert result["passed"] is False
    assert result.get("expert_trusted") is False
    assert result.get("gold_status") == "seeded_draft"


def test_medicine_cbl_disjoint_held_out_trusted_soft():
    """B4+: CBL disjoint instrument coding — no anchor overlap; soft κ may unlock summative."""
    from gradevance.services.publish import held_out_anchor_overlap

    assert held_out_anchor_overlap("engines/lct_semantics/medicine_cbl_v1") == []
    loaded = load_profile(find_profile_file_for_id("medicine_cbl_appendicitis", 1))
    result = evaluate_publish_gate(loaded, as_mode="summative", min_held_out=5)
    assert result["required"] is True
    assert result.get("expert_trusted") is True
    assert result.get("gold_status") == "instrument_coded_disjoint"
    assert result.get("held_out_anchor_overlaps", 0) == 0
    # Soft floor — κ should pass at device minimum 0.4
    assert result.get("kappa") is not None
    assert result["kappa"] >= 0.4


def test_article_seeded_held_out_blocks_summative():
    loaded = load_profile(find_profile_file_for_id("article_generic_formative", 1))
    result = evaluate_publish_gate(loaded, as_mode="summative", min_held_out=1)
    assert result["required"] is True
    assert result["passed"] is False
    assert result.get("expert_trusted") is False


def test_as_mode_summative_overrides_formative_pack():
    loaded = load_profile(find_profile_file_for_id("naa_cycle1_exam_prep", 1))
    assert (loaded.profile.get("mode") or "formative") != "summative"
    result = evaluate_publish_gate(loaded, as_mode="summative", min_held_out=5)
    assert result["required"] is True
    assert result["mode"] == "summative"


@pytest.mark.django_db
def test_assert_summative_forces_gate():
    """assert_* is used for assignment summative publish — always evaluate as summative."""
    result = assert_summative_publish_allowed("naa_cycle1_exam_prep", 1)
    assert result["required"] is True
    assert "passed" in result


@pytest.mark.django_db
def test_repin_after_bump_updates_draft_only():
    root = eduos_pack_root()
    before_devices = {p.name for p in (root / "engines/lct_semantics").iterdir() if p.is_dir()}
    before_profiles = {p.name for p in (root / "profiles").iterdir() if p.is_file()}

    prop = Proposal.objects.create(
        kind="anchor",
        status=Proposal.STATUS_ACCEPTED,
        payload={
            "sample_after": {
                "dimension": "semantic_gravity",
                "value": "SG+",
                "numeric": 2,
                "span_text": "When I sat the mock exam I spent two hours on one passage.",
            },
            "sample_rationale": "Concrete episode",
        },
    )
    PackBumpService().bump_device_from_proposal(prop, require_canary=False)
    prop.refresh_from_db()

    draft = Assignment.objects.create(
        title="draft",
        mode=Assignment.MODE_FORMATIVE,
        status=Assignment.STATUS_DRAFT,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
    )
    published = Assignment.objects.create(
        title="published",
        mode=Assignment.MODE_FORMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
    )

    result = ProfileRepinService().repin_from_proposal(prop, update_draft_assignments=True)
    draft.refresh_from_db()
    published.refresh_from_db()
    assert draft.profile_pack_id == result["profile_pack_id"]
    assert published.profile_pack_id == "naa_cycle1_exam_prep"
    assert str(draft.id) in result["draft_assignments_updated"]

    # cleanup
    import shutil

    after_devices = {p.name for p in (root / "engines/lct_semantics").iterdir() if p.is_dir()}
    for name in after_devices - before_devices:
        shutil.rmtree(root / "engines/lct_semantics" / name, ignore_errors=True)
    after_profiles = {p.name for p in (root / "profiles").iterdir() if p.is_file()}
    for name in after_profiles - before_profiles:
        (root / "profiles" / name).unlink(missing_ok=True)


@pytest.mark.django_db
def test_repin_requires_bump():
    prop = Proposal.objects.create(kind="anchor", status=Proposal.STATUS_ACCEPTED, payload={})
    with pytest.raises(RepinError):
        ProfileRepinService().repin_from_proposal(prop)
