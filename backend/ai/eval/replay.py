"""P0-07 — L1 deterministic replay runner (offline, no LLM, no DB).

This is the L1 "replay/golden" layer of the QA-FRAMEWORK evidence ladder
(§4): it re-runs the deterministic parts of the Pulse spine against the
committed replay fixtures and compares the *actual* behavior to the *expected*
behavior recorded in the fixtures.

What it replays (all deterministic, all offline):

* **S1 — salience** (``SalienceWitness.assess``): regex intent classification →
  ``(domain, route)``.  No LLM, no DB.
* **S4 — rules-tier critic** (``_rules_only_verdict`` over the flags raised by
  ``CriticWitness.review``): an unconfirmed non-GET tool call is a hard ``veto``
  with the ``unconfirmed_mutation`` flag.  The LLM tier is disabled
  (``enable_llm_critic=False``) so the result is deterministic.

The runner writes ``baseline.json`` next to the fixtures.  Every row stores both
``actual`` (what the code does now) and ``expected`` (what the fixture declares),
so drift shows up as a readable diff rather than being silently overwritten.
``generated_at`` is metadata only and is excluded from match logic.

Run directly::

    cd backend && python -m ai.eval.replay

Exits non-zero if any fixture drifts (actual != expected).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Bootstrap Django so the deterministic engine modules (salience/critic) can be
# imported when this runner is executed standalone (``python -m ai.eval.replay``)
# as well as under pytest. ``django.setup()`` is idempotent and a no-op when the
# test harness has already configured settings.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()

from ai.engine.cognition.turn.critic import CriticWitness, _rules_only_verdict  # noqa: E402
from ai.engine.cognition.turn.salience import SalienceWitness  # noqa: E402
from ai.engine.cognition.turn.witnesses import DraftResult, RetrievalResult  # noqa: E402
from ai.eval.fixtures import load_replay_fixtures  # noqa: E402

REPLAY_DIR: Path = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "replay"
BASELINE_PATH: Path = REPLAY_DIR / "baseline.json"


# ── Per-fixture replay ───────────────────────────────────────────────────────


def replay_conversation(entry: dict) -> dict:
    """Replay one conversation fixture through the S1 salience witness.

    Returns ``{"salience_domain": ..., "salience_route": ...}``.
    """
    salience = asyncio.run(SalienceWitness().assess(entry["user_message"]))
    return {
        "salience_domain": salience.domain,
        "salience_route": salience.route,
    }


def replay_mutation(entry: dict) -> dict:
    """Replay one mutation fixture through the S4 rules-tier critic.

    Builds a ``DraftResult`` from the fixture's ``draft_tool_calls`` and runs
    the rules-tier review (LLM disabled).  The rules-only fallback is applied
    as a fail-closed cross-check, so an unconfirmed non-GET call can never be
    reported as anything but a ``veto``.

    Returns ``{"verdict": ..., "flags": [...]}``.
    """
    draft = DraftResult(
        text="",
        tool_calls=[dict(tc) for tc in entry["draft_tool_calls"]],
    )
    retrieval = RetrievalResult()
    verdict = asyncio.run(
        CriticWitness().review(draft, retrieval, enable_llm_critic=False)
    )
    # `_rules_only_verdict` is the authoritative deterministic verdict source.
    # The rules tier raises ``unconfirmed_mutation`` for the fixture drafts; the
    # rules-only fallback then fails closed with a hard veto.
    rules_only = _rules_only_verdict(list(verdict.flags))
    if rules_only.verdict == "veto":
        verdict = rules_only
    return {"verdict": verdict.verdict, "flags": list(verdict.flags)}


def _conversation_row(entry: dict) -> dict:
    actual = replay_conversation(entry)
    expected = entry["expected"]
    match = (
        actual["salience_domain"] == expected.get("salience_domain")
        and actual["salience_route"] == expected.get("salience_route")
    )
    return {"id": entry["id"], "actual": actual, "expected": expected, "match": match}


def _mutation_row(entry: dict) -> dict:
    actual = replay_mutation(entry)
    expected = entry["expected"]
    match = (
        actual["verdict"] == expected.get("verdict")
        and expected.get("flag") in actual["flags"]
    )
    return {"id": entry["id"], "actual": actual, "expected": expected, "match": match}


# ── Report ───────────────────────────────────────────────────────────────────


def run_replay() -> dict:
    """Run the full deterministic replay and return the baseline report."""
    fixtures = load_replay_fixtures()

    conversations = [_conversation_row(e) for e in fixtures["conversations"]]
    mutations = [_mutation_row(e) for e in fixtures["mutations"]]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "conversations": conversations,
        "mutations": mutations,
        "summary": {
            "conversations_total": len(conversations),
            "conversations_match": sum(1 for r in conversations if r["match"]),
            "mutations_total": len(mutations),
            "mutations_match": sum(1 for r in mutations if r["match"]),
        },
    }


def write_baseline(report: dict, path: Path = BASELINE_PATH) -> None:
    """Write the replay report to disk as the committed baseline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def has_drift(report: dict) -> bool:
    """True if any replay row mismatched its expected behavior."""
    summary = report["summary"]
    return (
        summary["conversations_match"] != summary["conversations_total"]
        or summary["mutations_match"] != summary["mutations_total"]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P0-07 deterministic L1 replay runner")
    parser.add_argument(
        "--out",
        default=str(BASELINE_PATH),
        help="path to write the baseline JSON report",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="run the replay and exit non-zero on drift without writing",
    )
    args = parser.parse_args(argv)

    report = run_replay()

    if not args.check:
        write_baseline(report, Path(args.out))

    summary = report["summary"]
    print(
        "L1 replay: conversations "
        f"{summary['conversations_match']}/{summary['conversations_total']}, "
        f"mutations {summary['mutations_match']}/{summary['mutations_total']}"
    )

    if has_drift(report):
        print("DRIFT detected — actual behavior differs from expected:", file=sys.stderr)
        for section in ("conversations", "mutations"):
            for row in report[section]:
                if not row["match"]:
                    print(
                        f"  [{row['id']}] actual={row['actual']} expected={row['expected']}",
                        file=sys.stderr,
                    )
        return 1

    if not args.check:
        print(f"baseline written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
