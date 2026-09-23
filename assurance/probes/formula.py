"""Run pack formula fixtures through the independent oracle."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import yaml

from assurance.oracles.formula import evaluate
from assurance.probes.types import ProbeFinding


def run(root: Path, pack_id: str, rule_id: str) -> list[ProbeFinding]:
    path = root / "domain_packs" / pack_id / "assurance" / "oracles" / "formulas.yaml"
    if not path.is_file():
        return [ProbeFinding(rule_id, pack_id, "unknown", str(path), "no formula fixtures")]
    cases = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("cases") or []
    findings: list[ProbeFinding] = []
    for case in cases:
        got = evaluate(str(case["type"]), case.get("params") or {}, case.get("inputs") or {})
        expected = Decimal(str(case["expected"]))
        if got != expected:
            findings.append(
                ProbeFinding(
                    rule_id,
                    pack_id,
                    "failed",
                    str(case["id"]),
                    f"oracle {got} != hand expected {expected}",
                )
            )
    if not findings:
        findings.append(
            ProbeFinding(
                rule_id,
                pack_id,
                "passed",
                str(path),
                f"{len(cases)} hand-computed fixtures matched the independent oracle",
            )
        )
    return findings
