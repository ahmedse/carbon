"""Held-out reliability gate for summative profile / assignment publish."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gradevance.services.canary import evaluate_canary
from gradevance.services.lct_scale import canonicalize_sd, canonicalize_sg
from gradevance.services.packs import LoadedProfile, eduos_pack_root, load_device, load_profile
from gradevance.services.pipeline import _SegDraft, code_segment
from gradevance.services.reliability import passes_reliability_gate


class PublishGateError(Exception):
    pass


def load_held_out_rows(device_pack_rel: str, held_out_file: str = "held_out.jsonl") -> list[dict]:
    path = eduos_pack_root() / device_pack_rel / held_out_file
    if not path.is_file() or path.stat().st_size == 0:
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def engine_sg_labels_for_held_out(device_pack_rel: str) -> tuple[list[str], list[str]]:
    """Return (expert_sg_labels, engine_sg_labels) from held-out gold segments."""
    return _engine_dim_labels_for_held_out(device_pack_rel, "semantic_gravity")


def engine_sd_labels_for_held_out(device_pack_rel: str) -> tuple[list[str], list[str]]:
    """Return (expert_sd_labels, engine_sd_labels) where expert sd_label is present."""
    return _engine_dim_labels_for_held_out(device_pack_rel, "semantic_density")


def _engine_dim_labels_for_held_out(
    device_pack_rel: str, dimension: str
) -> tuple[list[str], list[str]]:
    device = load_device(device_pack_rel)
    held_out_file = device.device.get("held_out_file") or "held_out.jsonl"
    rows = load_held_out_rows(device_pack_rel, held_out_file)
    expert: list[str] = []
    engine: list[str] = []
    for row in rows:
        for seg in row.get("segments") or []:
            if dimension == "semantic_gravity":
                expert_lab = canonicalize_sg(
                    seg.get("sg_label") or f"N{seg.get('sg_numeric')}"
                ) or "SG-"
            else:
                expert_lab = canonicalize_sd(seg.get("sd_label"))
                if not expert_lab:
                    continue
            draft = _SegDraft(
                ordinal=int(seg.get("segment_index") or 0),
                start_word=int(seg.get("word_start") or 0),
                end_word=int(seg.get("word_end") or 0),
                text=seg.get("text") or "",
                stage_guess="what",
            )
            codes = code_segment(draft, device.anchors, True)
            hit = next((c for c in codes if c["dimension"] == dimension), None)
            default = "SG-" if dimension == "semantic_gravity" else "SD-"
            eng_val = (hit or {}).get("value") or default
            if dimension == "semantic_gravity":
                eng_val = canonicalize_sg(eng_val) or default
            else:
                eng_val = canonicalize_sd(eng_val) or default
            expert.append(expert_lab)
            engine.append(eng_val)
    return expert, engine


def held_out_anchor_overlap(device_pack_rel: str) -> list[str]:
    """Return held_out segment texts that duplicate (or contain) an anchor span — must be empty for NAA gate."""
    device = load_device(device_pack_rel)
    anchors = device.anchors or []
    anchor_spans = [
        (a.get("span_text") or "").strip().lower()
        for a in anchors
        if (a.get("span_text") or "").strip()
    ]
    held_out_file = device.device.get("held_out_file") or "held_out.jsonl"
    overlaps: list[str] = []
    for row in load_held_out_rows(device_pack_rel, held_out_file):
        for seg in row.get("segments") or []:
            t = (seg.get("text") or "").strip().lower()
            if not t:
                continue
            for a in anchor_spans:
                if t in a or a in t:
                    # Require substantial overlap (≥40 chars) to ignore short cue collisions
                    if min(len(t), len(a)) >= 40:
                        overlaps.append(t[:80])
                        break
    return overlaps


def evaluate_publish_gate(
    profile: dict[str, Any] | LoadedProfile,
    *,
    minimum_kappa: float | None = None,
    min_held_out: int = 5,
    as_mode: str | None = None,
) -> dict[str, Any]:
    """Gate summative publish when LCT is enabled and reliability_gate is set.

    ``as_mode`` overrides the profile's default mode — use ``summative`` when the
    *assignment* is summative even if the pack file defaults to formative.
    """
    doc = profile.profile if isinstance(profile, LoadedProfile) else profile
    mode = as_mode or doc.get("mode") or "formative"
    pipeline = doc.get("pipeline") or {}
    lct_ref = doc.get("lct_device") or {}

    if mode != "summative" or not pipeline.get("lct_enabled") or not lct_ref.get("pack_path"):
        return {
            "required": False,
            "passed": True,
            "reason": "Gate not required (formative or LCT off).",
            "mode": mode,
        }

    pack_rel = lct_ref["pack_path"]
    loaded_dev = load_device(pack_rel)
    gate = loaded_dev.device.get("reliability_gate") or {}
    if not gate.get("required_for_summative", True):
        return {
            "required": False,
            "passed": True,
            "reason": "Device does not require summative κ.",
            "mode": mode,
        }

    min_k = float(minimum_kappa if minimum_kappa is not None else gate.get("minimum") or 0.6)
    expert, engine = engine_sg_labels_for_held_out(pack_rel)
    expert_sd, engine_sd = engine_sd_labels_for_held_out(pack_rel)
    held_out_status = (gate.get("held_out_status") or "").strip() or _held_out_status_from_rows(
        load_held_out_rows(pack_rel, loaded_dev.device.get("held_out_file") or "held_out.jsonl")
    )
    overlaps = held_out_anchor_overlap(pack_rel)
    canary = evaluate_canary(
        expert_labels=expert,
        engine_labels=engine,
        minimum_kappa=min_k,
        held_out_n=len(expert),
        min_held_out=min_held_out,
    )
    rel_sg = (
        passes_reliability_gate(expert, engine, minimum=min_k, dimension="semantic_gravity")
        if expert
        else canary.reliability
    )
    rel_sd = (
        passes_reliability_gate(
            expert_sd, engine_sd, minimum=float(gate.get("minimum_sd") or 0.4), dimension="semantic_density"
        )
        if len(expert_sd) >= 3
        else None
    )

    # Instrument Trust B4: seeded / circular held_out must not unlock summative as "expert-proven"
    seeded = held_out_status in {"seeded_draft", "seeded", "draft"}
    circular = bool(overlaps)
    # expert_disjoint / expert / faculty_coded_disjoint / unspecified-without-overlap → trusted if not seeded/circular
    expert_trusted = (not seeded) and (not circular)
    passed = bool(canary.allowed) and expert_trusted
    reason = canary.reason
    if seeded:
        reason = (
            gate.get("soft_floor_note")
            or "Held-out is seeded_draft (not faculty expert gold). Summative blocked."
        )
        passed = False
    elif circular:
        reason = (
            f"Held-out overlaps anchors ({len(overlaps)} spans) — circular κ risk. Summative blocked."
        )
        passed = False

    return {
        "required": True,
        "passed": passed,
        "reason": reason,
        "reliability": rel_sg,
        "reliability_sd": rel_sd,
        "kappa": (rel_sg or {}).get("value") if isinstance(rel_sg, dict) else None,
        "kappa_sd": (rel_sd or {}).get("value") if isinstance(rel_sd, dict) else None,
        "held_out_n": len(expert),
        "held_out_sd_n": len(expert_sd),
        "minimum_kappa": min_k,
        "mode": mode,
        "gold_status": held_out_status or ("circular_overlap" if circular else "unknown"),
        "expert_trusted": expert_trusted,
        "held_out_anchor_overlaps": len(overlaps),
    }


def _held_out_status_from_rows(rows: list[dict]) -> str:
    if not rows:
        return "empty"
    statuses = {(r.get("gold_status") or "").strip() for r in rows}
    statuses.discard("")
    if "seeded_draft" in statuses or "seeded" in statuses:
        return "seeded_draft"
    if "expert" in statuses or "tutor_letter_bands" in statuses:
        return "expert"
    # Infer from source strings
    sources = " ".join((r.get("source") or "") for r in rows).lower()
    if "seeded" in sources:
        return "seeded_draft"
    if "faculty_coded" in sources or "gradevance2" in sources:
        return "expert"
    return "unspecified"


def assert_summative_publish_allowed(profile_pack_id: str, profile_version: int = 1) -> dict:
    from gradevance.services.packs import find_profile_file_for_id

    loaded = load_profile(find_profile_file_for_id(profile_pack_id, profile_version))
    # Assignment mode is summative — evaluate as such even if pack defaults formative.
    result = evaluate_publish_gate(loaded, as_mode="summative")
    if result["required"] and not result["passed"]:
        raise PublishGateError(result.get("reason") or "Publish gate failed")
    return result
