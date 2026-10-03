"""Live intention-retest banks (PULSE-INTENTION-CONTRACT §5).

Read-only Chat signals for the intention ladder, one bank per class:

* **IB-01** grounding — every figure is in the tool payload (IRP-5).
* **IB-02** language fidelity, incl. refusals/clarify (IRP-7).
* **IB-03** a read answers the asked field or says unknown (IF-04/IF-05).
* **IB-04** greeting + scope, bilingual (IF-01/IF-02).
* **IB-05** an in-scope ask is never scope-refused (IRP-9).
* **IB-07** Ask/Plan boundary — read never gets a plan card (IF-06).
* **IB-08** voice / register / persona-scope per surface (IF-07).
* **IB-10** live no-fallthrough ledger (IRP-8 / IF-08).
* **IB-11** determinism ``pass^3`` across paraphrases (IF-09).

The registry is **discovered** from ``chat_intention_bank_ib*.yaml``
(:func:`ai.eval.chat_deep_bench.discover_intention_banks`); adding a bank is a
new YAML, never an edit to a hardcoded tuple. This reuses the ``chat_retest``
machinery (``Host``, ``run_thread``, ``summarize``) — one retest system, not a
second one. It writes one dated evidence file per bank per run:
``docs/pulse/evidence/PV2-intention-<IB-ID>-<YYYY-MM-DD>-<HHMM>.json`` with
``tier="live_intention"`` (write bank ``IB-06``: ``live_intention_write``).
``chat_deep_bench`` reports those banks separately; they never move a Chat
objective or the Ask 10/10 score (RULE_36).

**Pack boundary.** These banks only mean anything on the nibras pack. The
runner verifies ``/health/`` ``release.pack == "nibras"`` and ``pulse_enabled``
is true *before* it logs in or scores. A different brand is left running: the
runner writes a ``tier="intention_blocked"`` note and exits 2 — the bank stays
``missing``, never zero-fail. It never starts or stops the stack.

**Write bank.** ``IB-06`` is the only write bank (ADR-0046). It needs a COMMS
STACK-HOLD + ``PULSE_NIGHTLY_LIVE=1``; without an explicit
``--allow-write`` and that window the runner refuses to run it and the bank
stays ``missing``. This runner never posts a host mutation.
"""
from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from ai.eval.chat_deep_bench import (
    discover_intention_banks,
    intention_gate_banks,
    paraphrase_run_pass,
    paraphrase_run_score,
)
from ai.eval.chat_live_probe import BASE, USER, _req, login
from ai.eval.chat_retest import EVIDENCE, Host, load_bank, load_bank_doc, run_thread, summarize

#: Single discovered registry — IB-04/IB-05 load exactly as before.
BANKS: dict[str, Path] = discover_intention_banks()
REQUIRED_PACK = "nibras"


def bank_doc(bank_id: str) -> dict:
    """The bank YAML document (``bank:`` meta + ``threads:``)."""
    return load_bank_doc(BANKS[bank_id])


def bank_is_write(bank_id: str) -> bool:
    """True for a bank that would mutate the host (IB-06). Never run silently."""
    return bool(bank_doc(bank_id).get("write"))


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
    """A dated note that a run was attempted against the wrong pack. Not a run."""
    path = EVIDENCE / f"PV2-intention-blocked-{started.strftime('%Y-%m-%d-%H%M')}.json"
    payload = {
        "tier": "intention_blocked",
        "run_at": started.isoformat(),
        "surface": "chat",
        "user": USER,
        "base": BASE,
        "banks": banks,
        "release": rel,
        "reason": reason,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _expand_modes(thread: dict) -> list[dict]:
    """Expand a thread's ``modes: [ask, plan]`` into one run per dial.

    IB-07 mirrors the same 8 threads in both dials; each dial gets its own
    conversation (a fresh ``run_thread``), so the messages do not cross dials.
    """
    modes = thread.get("modes")
    if not modes:
        return [thread]
    return [
        {**thread, "mode": mode, "id": f"{thread['id']}[{mode}]"}
        for mode in modes
    ]


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

    tier = str(doc.get("tier") or ("live_intention_write" if doc.get("write") else "live_intention"))
    report = {
        "tier": tier,
        "bank": bank_id,
        "bank_file": BANKS[bank_id].name,
        "bank_purpose": doc.get("purpose"),
        "run_at": started.isoformat(),
        "surface": "chat",
        "user": USER,
        "base": BASE,
        "release": release_payload(),
        "threads": rows,
        **summarize(rows),
    }
    report["total"] = len(rows)
    report["passed"] = sum(1 for r in rows if r["pass"])
    gate = intention_gate_banks().get(bank_id)
    if gate:
        # IR5 paraphrase bank: pass is the aggregate threshold, not 100% threads.
        report["gate"] = dict(gate)
        report["paraphrase"] = paraphrase_run_score(report)
        report["pass"] = paraphrase_run_pass(report["paraphrase"], gate)
    else:
        report["pass"] = report["passed"] == report["total"]
    return report


def _bank_filename(bank_id: str, started: datetime) -> str:
    return f"PV2-intention-{bank_id.replace('-', '')}-{started.strftime('%Y-%m-%d-%H%M')}.json"


def _write_allowed() -> bool:
    """IB-06 may run only inside an approved write window (never in CI/local)."""
    return os.environ.get("PULSE_NIGHTLY_LIVE") == "1" and bool(os.environ.get("STACK_HOLD"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live intention-retest banks")
    parser.add_argument("--bank", nargs="*", choices=sorted(BANKS), default=sorted(BANKS))
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--no-write", action="store_true", help="print only")
    parser.add_argument("--list", action="store_true", help="print the turn sets; no network, no run")
    parser.add_argument(
        "--allow-write",
        action="store_true",
        help="run a write bank (IB-06); also needs STACK_HOLD + PULSE_NIGHTLY_LIVE=1",
    )
    args = parser.parse_args(argv)

    started = datetime.now(timezone.utc)

    if args.list:
        for bank_id in args.bank:
            specs = load_bank(BANKS[bank_id])
            turns = sum(len(t.get("turns") or []) for t in specs)
            doc = bank_doc(bank_id)
            flags = "write" if doc.get("write") else "read-only"
            modes = len({m for t in specs for m in (t.get("modes") or ["—"])})
            print(f"{bank_id} · {BANKS[bank_id].name} · {len(specs)} threads / {turns} turns "
                  f"· modes={modes} · {flags}")
            for thread in specs:
                for turn in thread.get("turns") or []:
                    print(f"  {thread['id']}: {turn['say']}")
        return 0

    # A write bank never runs without an explicit window.
    requested = list(args.bank)
    runnable: list[str] = []
    for bank_id in requested:
        if bank_is_write(bank_id) and not (args.allow_write and _write_allowed()):
            print(
                f"SKIP {bank_id}: write bank needs STACK-HOLD + PULSE_NIGHTLY_LIVE=1 and "
                "--allow-write. The bank stays missing; Chat never host-mutates (ADR-0046).",
                flush=True,
            )
            continue
        runnable.append(bank_id)

    if not runnable:
        return 0

    rel = release_payload()
    problem = pack_problem(rel)
    if problem:
        message = (
            f"{problem}. Refusing to score intention banks off the wrong pack; "
            "the bank stays missing until a nibras cell is up. Not switching the brand."
        )
        print(f"BLOCKED: {message}", flush=True)
        if not args.no_write:
            path = write_blocked(message, rel, runnable, started)
            print(f"wrote {path}", flush=True)
        return 2

    token = login()
    host = Host(token)
    exit_code = 0
    for bank_id in runnable:
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
