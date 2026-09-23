"""Dispatch pack probes and write a JSONL ledger."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from assurance.probes import binding, conservation, formula, honesty
from assurance.probes.types import ProbeFinding

_TYPES = {
    "honesty": honesty.run,
    "formula": formula.run,
    "conservation": conservation.run,
    "binding": binding.run,
}


def load_probe_specs(root: Path, pack_id: str) -> list[dict]:
    path = root / "domain_packs" / pack_id / "assurance" / "probes.yaml"
    if pack_id == "platform":
        path = root / "assurance" / "platform" / "probes.yaml"
    if not path.is_file():
        return []
    return list((yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("probes") or [])


def run_pack(root: Path, pack_id: str) -> list[ProbeFinding]:
    findings: list[ProbeFinding] = []
    for spec in load_probe_specs(root, pack_id):
        runner = _TYPES[str(spec["type"])]
        findings.extend(runner(root, pack_id, str(spec["rule_id"])))
    return findings


def write_ledger(path: Path, findings: list[ProbeFinding], commit: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for finding in findings:
        lines.append(
            json.dumps(
                {
                    "rule_id": finding.rule_id,
                    "pack_id": finding.pack_id,
                    "commit": commit,
                    "result": finding.result,
                    "source": finding.source,
                    "evidence_class": "executed",
                    "detail": finding.detail,
                },
                sort_keys=True,
            )
        )
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
