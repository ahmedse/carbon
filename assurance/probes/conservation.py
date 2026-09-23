"""Signed leave identity versus the host floor."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import yaml

from assurance.oracles.conservation import display_remaining, signed_remaining
from assurance.probes.types import ProbeFinding


def run(root: Path, pack_id: str, rule_id: str) -> list[ProbeFinding]:
    path = root / "domain_packs" / pack_id / "assurance" / "oracles" / "conservation.yaml"
    if not path.is_file():
        return [ProbeFinding(rule_id, pack_id, "unknown", str(path), "no conservation fixtures")]
    cases = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("cases") or []
    findings: list[ProbeFinding] = []
    overdraw_seen = False
    for case in cases:
        signed = signed_remaining(case["entitled"], case["carried"], case["used"], case["pending"])
        display = display_remaining(case["entitled"], case["carried"], case["used"], case["pending"])
        if signed != Decimal(str(case["signed"])):
            findings.append(
                ProbeFinding(rule_id, pack_id, "failed", case["id"], f"signed {signed} != {case['signed']}")
            )
        if display != Decimal(str(case["display"])):
            findings.append(
                ProbeFinding(rule_id, pack_id, "failed", case["id"], f"display {display} != {case['display']}")
            )
        if signed < 0:
            overdraw_seen = True
            if display != Decimal("0"):
                findings.append(
                    ProbeFinding(
                        rule_id,
                        pack_id,
                        "failed",
                        case["id"],
                        "overdraw must display as 0; the signed value is the real over-allocation",
                    )
                )
    if overdraw_seen is False:
        findings.append(
            ProbeFinding(
                rule_id,
                pack_id,
                "failed",
                str(path),
                "fixtures never include a negative signed remaining — cannot detect hidden overdraw",
            )
        )
    if not findings:
        findings.append(
            ProbeFinding(
                rule_id,
                pack_id,
                "passed",
                str(path),
                "signed identity and display floor both checked, including an overdraw case",
            )
        )
    return findings
