"""Live Chat **Plan** banks (PULSE-PLAN-CONTRACT §5).

Read-only Chat signals for the Plan ladder, one bank per class:

* **PL-01** Ask/Plan boundary — a read never gets a plan card; a goal gets one
  plan/handoff; Chat Plan never host-mutates (ADR-0046).
* **PL-02** plan-revision continuity — the FE discuss seed stays a typed
  revision and "apply" is a 0-LLM handoff to Agent.
* **PL-03** await-user honesty — a goal with a missing fact asks one question
  instead of drafting silently or inventing a value.

The registry is **discovered** from ``chat_plan_bank_pl*.yaml``
(:func:`discover_plan_banks`); adding a bank is a new YAML, never an edit to a
hardcoded tuple. It reuses the ``chat_retest`` machinery (``Host``,
``run_thread``, ``summarize``, ``check_turn``) — one retest system, not a
second one. It writes one dated evidence file per bank per run:
``docs/pulse/evidence/PV2-plan-<PL-ID>-<YYYY-MM-DD>-<HHMM>.json`` with
``tier="live_plan"``. ``plan_bench`` reports those banks separately; they never
move a Chat / Tasks objective score (RULE_36).

**Pack boundary.** These banks only mean anything on the nibras pack. The
runner verifies ``/health/`` ``release.pack == "nibras"`` and ``pulse_enabled``
is true *before* it logs in or scores. A different brand is left running: the
runner writes a ``tier="plan_blocked"`` note and exits 2 — the bank stays
``missing``, never zero-fail. It never starts or stops the stack.

**No write bank.** Plan proposes; Agent applies. Every PL bank is read-only, so
none needs STACK-HOLD.
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from ai.eval.chat_live_probe import BASE, USER, _req, login
from ai.eval.chat_retest import EVIDENCE, Host, load_bank, load_bank_doc, run_thread, summarize

REQUIRED_PACK = "nibras"


def discover_plan_banks(root: Path | None = None) -> dict[str, Path]:
    """Map ``bank:`` id → path for every ``chat_plan_bank_pl*.yaml``."""
    base = root or Path(__file__).resolve().parent
    out: dict[str, Path] = {}
    for path in sorted(base.glob("chat_plan_bank_pl*.yaml")):
        try:
            doc = load_bank_doc(path)
        except (OSError, ValueError):
            continue
        bank_id = str((doc or {}).get("bank") or "").strip()
        if bank_id:
            out[bank_id] = path
    return out


BANKS: dict[str, Path] = discover_plan_banks()


def bank_doc(bank_id: str) -> dict:
    return load_bank_doc(BANKS[bank_id])


def release_payload() -> dict:
    """The live process's ``release`` block, or a status stub when unreachable."""
    status, data = _req("GET", "/health/", timeout=30)
    if status != 200 or not isinstance(data, dict):
        return {"http": status}
    rel = data.get("release")
    return rel if isinstance(rel, dict) else {"http": status, "release": None}


def pack_problem(rel: dict) -> str | None:
    """Why the live process may not serve these banks, or None when it may."""
    if rel.get("http") not in (None, 200) or not rel:
        return f"health unreachable ({rel.get('http')}) — cannot verify the pack"
    pack = str(rel.get("pack") or "")
    if pack != REQUIRED_PACK:
        return f"release.pack={pack!r}, required {REQUIRED_PACK!r}"
    if not rel.get("pulse_enabled"):
        return f"release.pulse_enabled={rel.get('pulse_enabled')!r}, required true"
    return None


def write_blocked(reason: str, rel: dict, banks: list[str], started: datetime) -> Path:
    """A dated note that a run was attempted against the wrong pack / no cell. Not a run."""
    path = EVIDENCE / f"PV2-plan-blocked-{started.strftime('%Y-%m-%d-%H%M')}.json"
    payload = {
        "tier": "plan_blocked",
        "run_at": started.isoformat(),
        "surface": "chat_plan",
        "user": USER,
        "base": BASE,
        "banks": banks,
        "release": rel,
        "reason": reason,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _expand_modes(thread: dict) -> list[dict]:
    """Expand a thread's ``modes: [ask, plan]`` into one run per dial."""
    modes = thread.get("modes")
    if not modes:
        return [thread]
    return [{**thread, "mode": mode, "id": f"{thread['id']}[{mode}]"} for mode in modes]


def run_bank(bank_id: str, token: str, host: Host, workers: int, started: datetime, quiet: bool) -> dict:
    doc = bank_doc(bank_id)
    specs = [t for t in doc.get("threads") or [] if isinstance(t, dict)]
    if not specs:
        raise RuntimeError(f"{bank_id}: bank {BANKS[bank_id].name} has no threads")
    expanded = [t for thread in specs for t in _expand_modes(thread)]

    def _one(thread: dict) -> dict:
        return run_thread(thread, token, host, quiet=quiet, mode=thread.get("mode"))

    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(_one, expanded))
    else:
        rows = [_one(t) for t in expanded]

    report = {
        "tier": "live_plan",
        "bank": bank_id,
        "bank_file": BANKS[bank_id].name,
        "bank_purpose": doc.get("purpose"),
        "run_at": started.isoformat(),
        "surface": "chat_plan",
        "user": USER,
        "base": BASE,
        "release": release_payload(),
        "threads": rows,
        **summarize(rows),
    }
    report["total"] = len(rows)
    report["passed"] = sum(1 for r in rows if r["pass"])
    report["pass"] = report["passed"] == report["total"]
    return report


def _bank_filename(bank_id: str, started: datetime) -> str:
    return f"PV2-plan-{bank_id.replace('-', '')}-{started.strftime('%Y-%m-%d-%H%M')}.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live Chat Plan banks")
    parser.add_argument("--bank", nargs="*", choices=sorted(BANKS), default=sorted(BANKS))
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--no-write", action="store_true", help="print only")
    parser.add_argument("--list", action="store_true", help="print the turn sets; no network, no run")
    args = parser.parse_args(argv)

    started = datetime.now(timezone.utc)

    if args.list:
        for bank_id in args.bank:
            specs = load_bank(BANKS[bank_id])
            turns = sum(len(t.get("turns") or []) for t in specs)
            doc = bank_doc(bank_id)
            modes = len({m for t in specs for m in (t.get("modes") or ["—"])})
            print(f"{bank_id} · {BANKS[bank_id].name} · {len(specs)} threads / {turns} turns "
                  f"· modes={modes} · read-only")
            for thread in specs:
                for turn in thread.get("turns") or []:
                    print(f"  {thread['id']}: {turn['say']}")
        return 0

    requested = list(args.bank)
    rel = release_payload()
    problem = pack_problem(rel)
    if problem:
        message = (
            f"{problem}. Refusing to score Plan banks off the wrong pack; the bank "
            "stays missing until a nibras cell is up. Not switching the brand."
        )
        print(f"BLOCKED: {message}", flush=True)
        if not args.no_write:
            path = write_blocked(message, rel, requested, started)
            print(f"wrote {path}", flush=True)
        return 2

    token = login()
    host = Host(token)
    exit_code = 0
    for bank_id in requested:
        print(f"== {bank_id} ==", flush=True)
        report = run_bank(bank_id, token, host, args.workers, started, quiet=False)
        text = json.dumps(report, indent=2, ensure_ascii=False)
        if args.no_write:
            print(text)
        else:
            path = EVIDENCE / _bank_filename(bank_id, started)
            path.write_text(text + "\n", encoding="utf-8")
            print(f"wrote {path}", flush=True)
        print(
            f"{bank_id}: {report['passed']}/{report['total']} threads pass "
            f"({'PASS' if report['pass'] else 'FAIL'})",
            flush=True,
        )
        if not report["pass"]:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
