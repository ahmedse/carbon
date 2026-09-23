"""Static host binding. Reads source as text. Does not import Django apps.

A binding is: the file that is supposed to enforce a rule still contains the
enforcing symbols, and does not contain the forbidden shortcut.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from assurance.probes.types import ProbeFinding


def run(root: Path, pack_id: str, rule_id: str) -> list[ProbeFinding]:
    path = root / "domain_packs" / pack_id / "assurance" / "bindings.yaml"
    if not path.is_file():
        path = root / "assurance" / "platform" / "bindings.yaml"
    if not path.is_file():
        return [ProbeFinding(rule_id, pack_id, "unknown", "bindings.yaml", "no bindings file")]

    items = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("bindings") or []
    findings: list[ProbeFinding] = []
    for item in items:
        if str(item.get("rule_id")) != rule_id:
            continue
        findings.extend(_one(root, pack_id, item))
    if not findings:
        findings.append(
            ProbeFinding(rule_id, pack_id, "unknown", str(path), f"no binding rows for {rule_id}")
        )
    return findings


def _one(root: Path, pack_id: str, item: dict) -> list[ProbeFinding]:
    rule_id = str(item["rule_id"])
    rel = str(item["file"])
    text = (root / rel).read_text(encoding="utf-8") if (root / rel).is_file() else ""
    if not text:
        return [ProbeFinding(rule_id, pack_id, "failed", rel, "file missing")]
    missing = [needle for needle in item.get("must_contain") or [] if needle not in text]
    forbidden = [needle for needle in item.get("must_not_contain") or [] if needle in text]
    if missing or forbidden:
        return [
            ProbeFinding(
                rule_id,
                pack_id,
                "failed",
                rel,
                f"missing={missing} forbidden_present={forbidden}",
            )
        ]
    if item.get("expect") == "conflict":
        return [
            ProbeFinding(
                rule_id,
                pack_id,
                "conflict",
                rel,
                str(item.get("detail") or "declared and implemented representations disagree"),
            )
        ]
    if item.get("expect") == "failed":
        return [
            ProbeFinding(
                rule_id,
                pack_id,
                "failed",
                rel,
                str(item.get("detail") or "invariant does not hold in this file"),
            )
        ]
    return [
        ProbeFinding(
            rule_id,
            pack_id,
            "passed",
            rel,
            str(item.get("detail") or "required symbols still present"),
        )
    ]
