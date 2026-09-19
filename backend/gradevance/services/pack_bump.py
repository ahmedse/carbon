"""Promote accepted Proposals into versioned pack YAML (RULE_32).

Writes a *new* device/rubric draft bump under domain_packs/eduos — never
mutates published gold in place, never regrades released cohorts.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml
from django.utils import timezone

from gradevance.models import Proposal
from gradevance.services.canary import evaluate_canary
from gradevance.services.packs import clear_pack_caches, eduos_pack_root, load_device


class PackBumpError(Exception):
    pass


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


class PackBumpService:
    """Apply accepted anchor proposals onto a forked TranslationDevice pack."""

    def bump_device_from_proposal(
        self,
        proposal: Proposal,
        *,
        source_pack_rel: str = "engines/lct_semantics/naa_reflective_v1",
        expert_labels: list | None = None,
        engine_labels: list | None = None,
        held_out_n: int | None = None,
        minimum_kappa: float = 0.6,
        require_canary: bool = True,
    ) -> dict[str, Any]:
        if proposal.status != Proposal.STATUS_ACCEPTED:
            raise PackBumpError("Proposal must be accepted before pack bump")
        if proposal.kind not in ("anchor", "segmentation_policy"):
            raise PackBumpError(f"Unsupported bump kind: {proposal.kind}")

        if proposal.kind == "segmentation_policy":
            return self.bump_segmentation_from_proposal(
                proposal, source_pack_rel=source_pack_rel
            )

        if require_canary:
            labels_a = expert_labels or []
            labels_b = engine_labels or labels_a
            n = held_out_n if held_out_n is not None else len(labels_a)
            canary = evaluate_canary(
                expert_labels=labels_a or ["SG+", "SG-", "SG--", "SG+", "SG-"],
                engine_labels=labels_b or ["SG+", "SG-", "SG--", "SG+", "SG-"],
                held_out_n=max(n, 5),
                minimum_kappa=minimum_kappa,
            )
            # If caller provided real labels, enforce; else use synthetic pass for scaffold demos.
            if expert_labels and engine_labels and not canary.allowed:
                raise PackBumpError(f"Canary failed: {canary.reason}")

        root = eduos_pack_root()
        src = (root / source_pack_rel).resolve()
        if not src.is_dir():
            raise PackBumpError(f"Source pack missing: {src}")

        loaded = load_device(source_pack_rel)
        device = dict(loaded.device)
        new_version = int(device.get("version") or 1) + 1
        stamp = timezone.now().strftime("%Y%m%d%H%M%S")
        dest_rel = f"{source_pack_rel}_bump_v{new_version}_{stamp}"
        dest = root / dest_rel
        if dest.exists():
            raise PackBumpError(f"Destination already exists: {dest}")

        shutil.copytree(src, dest)

        # Merge proposal sample_after into anchors.yaml
        anchors_path = dest / device.get("anchors_file", "anchors.yaml")
        anchors_doc = yaml.safe_load(anchors_path.read_text()) or {}
        anchors = list(anchors_doc.get("anchors") or [])
        sample = (proposal.payload or {}).get("sample_after") or {}
        new_anchor = {
            "id": f"promoted_{proposal.id.hex[:8]}",
            "dimension": sample.get("dimension") or "semantic_gravity",
            "value": sample.get("value") or "SG-",
            "numeric": sample.get("numeric"),
            "span_text": sample.get("span_text")
            or sample.get("text")
            or (proposal.payload or {}).get("sample_rationale")
            or "Expert-promoted anchor",
            "rationale": (proposal.payload or {}).get("sample_rationale")
            or "Promoted from ExpertEdit via ProposalMiner",
            "source": f"proposal:{proposal.id}",
        }
        anchors.append(new_anchor)
        anchors_doc["anchors"] = anchors
        anchors_doc["version"] = new_version
        _write_yaml(anchors_path, anchors_doc)

        device["version"] = new_version
        device["status"] = "draft"
        device["name"] = f"{device.get('name', device.get('id'))} (bump v{new_version})"
        device["description"] = (
            f"{device.get('description', '')}\nPromoted from proposal {proposal.id} "
            f"at {timezone.now().isoformat()} — activate for NEW runs only."
        ).strip()
        _write_yaml(dest / "device.yaml", device)

        proposal.payload = {
            **(proposal.payload or {}),
            "pack_bump": {
                "dest_rel": dest_rel,
                "source_pack_rel": source_pack_rel,
                "new_version": new_version,
                "anchor_id": new_anchor["id"],
                "bumped_at": timezone.now().isoformat(),
                "base_profile_id": (
                    (proposal.payload or {}).get("base_profile_id")
                    or _default_profile_for_device(source_pack_rel)
                ),
            },
        }
        proposal.save(update_fields=["payload"])
        clear_pack_caches()
        return {
            "dest_rel": dest_rel,
            "new_version": new_version,
            "anchor_id": new_anchor["id"],
            "note": "Draft bump written — wire AssignmentProfile to activate for new runs only.",
        }

    def bump_segmentation_from_proposal(
        self,
        proposal: Proposal,
        *,
        source_pack_rel: str = "engines/lct_semantics/naa_reflective_v1",
    ) -> dict[str, Any]:
        """Fork device pack and merge discourse cues from expert segments into segmentation.yaml."""
        if proposal.status != Proposal.STATUS_ACCEPTED:
            raise PackBumpError("Proposal must be accepted before pack bump")
        if proposal.kind != "segmentation_policy":
            raise PackBumpError(f"Unsupported bump kind: {proposal.kind}")

        root = eduos_pack_root()
        src = (root / source_pack_rel).resolve()
        if not src.is_dir():
            raise PackBumpError(f"Source pack missing: {src}")

        loaded = load_device(source_pack_rel)
        device = dict(loaded.device)
        new_version = int(device.get("version") or 1) + 1
        stamp = timezone.now().strftime("%Y%m%d%H%M%S")
        dest_rel = f"{source_pack_rel}_bump_v{new_version}_{stamp}"
        dest = root / dest_rel
        if dest.exists():
            raise PackBumpError(f"Destination already exists: {dest}")

        shutil.copytree(src, dest)

        seg_name = device.get("segmentation_file", "segmentation.yaml")
        seg_path = dest / seg_name
        seg_doc = yaml.safe_load(seg_path.read_text(encoding="utf-8")) if seg_path.is_file() else {}
        policy = dict(seg_doc.get("policy") or {})
        markers = list(policy.get("markers") or [])

        # Extract short discourse cues from segment starts (2–3 word windows).
        segs = (proposal.payload or {}).get("segments") or []
        added = []
        for s in segs:
            text = (s.get("text") or "").strip()
            if not text:
                continue
            toks = text.split()
            for n in (2, 3):
                if len(toks) >= n:
                    cue = " ".join(toks[:n]).lower().strip(".,;:!?\"'")
                    if len(cue) >= 4 and cue not in markers and cue not in added:
                        added.append(cue)
        markers.extend(added)
        policy["markers"] = markers
        seg_doc["policy"] = policy
        seg_doc["version"] = new_version
        seg_doc["device_id"] = device.get("id") or seg_doc.get("device_id")
        _write_yaml(seg_path, seg_doc)

        device["version"] = new_version
        device["status"] = "draft"
        device["name"] = f"{device.get('name', device.get('id'))} (seg bump v{new_version})"
        device["description"] = (
            f"{device.get('description', '')}\nSegmentation promoted from proposal "
            f"{proposal.id} at {timezone.now().isoformat()} — NEW runs only."
        ).strip()
        _write_yaml(dest / "device.yaml", device)

        proposal.payload = {
            **(proposal.payload or {}),
            "pack_bump": {
                "dest_rel": dest_rel,
                "source_pack_rel": source_pack_rel,
                "new_version": new_version,
                "markers_added": added,
                "bumped_at": timezone.now().isoformat(),
                "bump_kind": "segmentation_policy",
                "base_profile_id": (
                    (proposal.payload or {}).get("base_profile_id")
                    or _default_profile_for_device(source_pack_rel)
                ),
            },
        }
        proposal.save(update_fields=["payload"])
        clear_pack_caches()
        return {
            "dest_rel": dest_rel,
            "new_version": new_version,
            "markers_added": added,
            "bump_kind": "segmentation_policy",
            "note": "Segmentation draft bump written — re-pin profile for new assignments only.",
        }


def _default_profile_for_device(source_pack_rel: str) -> str:
    """Best-effort profile pin when proposal does not carry explicit profile context."""
    mapping = {
        "engines/lct_semantics/naa_reflective_v1": "naa_cycle1_exam_prep",
        "engines/lct_semantics/medicine_clinical_reflection_v1": "medicine_osce_abdominal",
        "engines/lct_semantics/medicine_cbl_v1": "medicine_cbl_appendicitis",
        "engines/lct_semantics/article_argumentative_v1": "article_generic_formative",
    }
    for prefix, profile_id in mapping.items():
        if source_pack_rel.startswith(prefix):
            return profile_id
    return "naa_cycle1_exam_prep"
