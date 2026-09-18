#!/usr/bin/env python3
"""Validate EduOS GradeVance engine packs against JSON Schema + pack invariants.

Usage (from repo root):
  .venv/bin/python domain_packs/eduos/scripts/validate_packs.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
ERRORS: list[str] = []


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected mapping")
    return data


def schema(name: str) -> Draft202012Validator:
    raw = json.loads((SCHEMAS / name).read_text())
    return Draft202012Validator(raw)


def err(msg: str) -> None:
    ERRORS.append(msg)


def check_weights(path: Path, criteria: list) -> None:
    total = sum(float(c.get("weight", 0)) for c in criteria)
    if abs(total - 1.0) > 1e-6:
        err(f"{path}: criteria weights sum to {total}, expected 1.0")


def check_device_pack(pack_dir: Path) -> None:
    device_path = pack_dir / "device.yaml"
    if not device_path.exists():
        err(f"missing {device_path}")
        return
    data = load_yaml(device_path)
    for e in schema("translation_device.schema.json").iter_errors(data):
        err(f"{device_path}: {e.message}")
    for key in ("anchors_file", "boundary_pairs_file", "segmentation_file", "held_out_file"):
        rel = data.get(key)
        if rel and not (pack_dir / rel).exists():
            err(f"{device_path}: missing {key} → {rel}")
    if data.get("status") == "published":
        anchors = load_yaml(pack_dir / data["anchors_file"])
        if not anchors.get("anchors"):
            err(f"{pack_dir}: published device requires ≥1 anchor")

    # Summative-bound devices need enough held-out segments for κ gates.
    gate = data.get("reliability_gate") or {}
    if gate.get("required_for_summative") and data.get("held_out_file"):
        held_path = pack_dir / data["held_out_file"]
        if held_path.exists():
            seg_n = 0
            for line in held_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    err(f"{held_path}: invalid JSONL line")
                    continue
                seg_n += len(row.get("segments") or [])
            if seg_n < 5:
                err(
                    f"{pack_dir}: reliability_gate.required_for_summative "
                    f"but held_out has {seg_n} segments (need ≥5)"
                )
        else:
            err(f"{pack_dir}: reliability_gate set but held_out missing")


def check_rubric_pack(pack_dir: Path) -> None:
    rubric_path = pack_dir / "rubric.yaml"
    if not rubric_path.exists():
        err(f"missing {rubric_path}")
        return
    data = load_yaml(rubric_path)
    for e in schema("rubric_pack.schema.json").iter_errors(data):
        err(f"{rubric_path}: {e.message}")
    check_weights(rubric_path, data.get("criteria") or [])
    for key in ("band_descriptors_file", "action_templates_file"):
        rel = data.get(key)
        if rel and not (pack_dir / rel).exists():
            err(f"{rubric_path}: missing {key} → {rel}")


def check_profile(path: Path) -> None:
    data = load_yaml(path)
    for e in schema("assignment_profile.schema.json").iter_errors(data):
        err(f"{path}: {e.message}")
    for key in ("lct_device", "rubric_pack"):
        ref = data.get(key)
        if not ref:
            if key == "lct_device" and not data.get("pipeline", {}).get("lct_enabled", True):
                continue
            if key == "lct_device" and data.get("lct_device") is None:
                continue
            if key == "rubric_pack":
                err(f"{path}: rubric_pack required")
            continue
        pack_path = ROOT / ref["pack_path"]
        if not pack_path.is_dir():
            err(f"{path}: pack_path not found: {ref['pack_path']}")


def check_gold_wave(path: Path) -> None:
    data = json.loads(path.read_text())
    points = data.get("wave_points") or []
    codes = [p["sg_numeric"] for p in points]
    if len(set(codes)) < 2:
        err(f"{path}: wave is flat (no oscillation) — invalid LCT gold")
    words = data["text"].split()
    if len(words) != data.get("word_count"):
        err(f"{path}: word_count {data.get('word_count')} != actual {len(words)}")
    for seg in data.get("segments") or []:
        chunk = " ".join(words[seg["word_start"] : seg["word_end"]])
        if chunk != seg["text"]:
            err(f"{path}: segment {seg['segment_index']} text mismatch offsets")


def main() -> int:
    for d in sorted((ROOT / "engines/lct_semantics").glob("*/")):
        if d.is_dir():
            check_device_pack(d)
    for d in sorted((ROOT / "engines/rubric").glob("*/")):
        if d.is_dir():
            check_rubric_pack(d)
    for p in sorted((ROOT / "profiles").glob("*.yaml")):
        check_profile(p)
    gold = ROOT / "gold/naa/AR-CYCLE1-18-week1.json"
    if gold.exists():
        check_gold_wave(gold)
    else:
        err(f"missing gold {gold}")

    if ERRORS:
        print(f"FAIL — {len(ERRORS)} issue(s):")
        for e in ERRORS:
            print(f"  - {e}")
        return 1
    print("OK — EduOS GradeVance packs valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
