"""Assurance CLI.

    python -m assurance probe --pack nibras --commit 3d0c045 --ledger /tmp/nibras.jsonl
    python -m assurance report --pack nibras --commit 3d0c045 --ledger /tmp/nibras.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from assurance.evaluate import evaluate_packs, load_events
from assurance.load import load_brand, repo_root
from assurance.probes.run import run_pack, write_ledger


def _print_rows(pack: str, commit: str, pack_ids: list[str], rows) -> None:
    print(f"pack={pack} commit={commit} packs={pack_ids}")
    blocking_open = 0
    for row in rows:
        flag = "block" if row.blocking and row.label != "passed" else "     "
        if row.blocking and row.label != "passed":
            blocking_open += 1
        print(f"{flag} {row.pack:10} {row.rule_id:14} {row.label:14} {row.reason}")
    print(f"rows={len(rows)} release_blocking_not_passed={blocking_open}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assurance framework")
    parser.add_argument("command", nargs="?", default="report", choices=["report", "probe"])
    parser.add_argument("--pack", default="nibras")
    parser.add_argument("--commit", required=True)
    parser.add_argument("--ledger", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", default="")
    args = parser.parse_args(argv)

    root = repo_root() if not args.root else Path(args.root)
    ledger = Path(args.ledger) if args.ledger else None

    if args.command == "probe":
        if ledger is None:
            parser.error("probe requires --ledger")
        findings = run_pack(root, args.pack)
        if args.pack != "platform":
            findings.extend(run_pack(root, "platform"))
        write_ledger(ledger, findings, args.commit)
        print(f"wrote {len(findings)} findings to {ledger}")
        for finding in findings:
            print(f"  {finding.result:8} {finding.rule_id:14} {finding.detail}")

    packs = load_brand(root, args.pack)
    rows = evaluate_packs(packs, load_events(ledger), args.commit)
    if args.json:
        json.dump(
            [
                {
                    "rule_id": row.rule_id,
                    "pack": row.pack,
                    "label": row.label,
                    "reason": row.reason,
                    "blocks_release": row.blocking,
                }
                for row in rows
            ],
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
        return 0
    _print_rows(args.pack, args.commit, [pack.id for pack in packs], rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
