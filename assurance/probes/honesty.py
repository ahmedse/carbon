"""Declared process vs declared host plane.

A YAML SoD line is a Pulse dial. This probe refuses to treat it as host ACL.
It checks coverage, forbids leftover dial_only rows, and checks that the
process file still declares the roles the plane requires.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from assurance.probes.types import ProbeFinding


def run(root: Path, pack_id: str, rule_id: str) -> list[ProbeFinding]:
    honesty_path = root / "domain_packs" / pack_id / "assurance" / "honesty.yaml"
    process_dir = root / "domain_packs" / pack_id / "processes"
    if not honesty_path.is_file():
        return [
            ProbeFinding(rule_id, pack_id, "unknown", str(honesty_path), "honesty.yaml missing")
        ]
    planes = (yaml.safe_load(honesty_path.read_text(encoding="utf-8")) or {}).get("planes") or {}
    docs: dict[str, dict] = {}
    for path in sorted(process_dir.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if doc.get("id"):
            docs[str(doc["id"])] = doc

    findings: list[ProbeFinding] = []
    if set(docs) != set(planes):
        findings.append(
            ProbeFinding(
                rule_id,
                pack_id,
                "failed",
                "honesty.yaml",
                f"process set {sorted(docs)} != plane set {sorted(planes)}",
            )
        )
        return findings

    dial = [pid for pid, plane in planes.items() if plane == "dial_only"]
    if dial:
        findings.append(
            ProbeFinding(rule_id, pack_id, "failed", "honesty.yaml", f"dial_only remains: {dial}")
        )

    for process_id, plane in planes.items():
        doc = docs[process_id]
        human = [step for step in doc.get("steps") or [] if step.get("autonomy") == "human_only"]
        if not human:
            findings.append(
                ProbeFinding(rule_id, pack_id, "failed", process_id, "no human_only step")
            )
            continue
        if not any(step.get("separation_of_duties") for step in human):
            findings.append(
                ProbeFinding(rule_id, pack_id, "failed", process_id, "human_only without SoD roles")
            )
            continue
        refuse = [str(item) for item in (doc.get("policies") or {}).get("refuse_if") or []]
        if plane == "host_gate" and not any("preparer" in item for item in refuse):
            findings.append(
                ProbeFinding(
                    rule_id,
                    pack_id,
                    "failed",
                    process_id,
                    "host_gate process has no preparer refuse_if",
                )
            )
        if plane == "correspondence":
            review = next((step for step in doc.get("steps") or [] if step.get("id") == "review"), None)
            roles = (review or {}).get("separation_of_duties") or []
            if roles != ["requester", "approver"]:
                findings.append(
                    ProbeFinding(
                        rule_id,
                        pack_id,
                        "failed",
                        process_id,
                        f"correspondence review SoD is {roles}",
                    )
                )

    if not findings:
        findings.append(
            ProbeFinding(
                rule_id,
                pack_id,
                "passed",
                "honesty.yaml",
                "every process has a host plane; YAML SoD still declared; no dial_only",
            )
        )
    return findings
