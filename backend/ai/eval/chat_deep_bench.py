"""Pulse Chat deep benchmark — C1–C10 + expert metrics, three columns.

Stub CI can be green while live Chat is not. Honest status is the worst of
the last live snapshot and this week's operator log. Stub never upgrades a miss.

Closing rule: an operator finding stays in the log forever. It stops counting
against the week only when the three latest full runs of the live retest bank
(``chat_retest.py``) all pass every thread that names it. A later failing run
reopens it. The same runs are the live source for C6, C8, and C9.

L6 / L7 are v21 rungs. This module does not score them and must not be used
to claim them.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from ai.eval.intelligence_ladder import (
    G5_FILE,
    LIVE_A9_FILE,
    LIVE_C1_FILE,
    LIVE_C2_FILE,
    _load,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = REPO_ROOT / "docs" / "pulse" / "evidence"
OPERATOR_FILE = "PV2-chat-operator-2026-09-26.json"
RETEST_GLOB = "PV2-chat-retest-*.json"
INTENTION_GLOB = "PV2-intention-IB*.json"
INTENTION_BLOCKED_GLOB = "PV2-intention-blocked-*.json"

# ── Intention bank registry (PULSE-INTENTION-CONTRACT §5) ──────────────────
# One registry: a new bank is a YAML in this directory. The runner
# (``chat_intention_retest``) and this scorer both read the discovery below, so
# adding a bank never means editing a hardcoded tuple in two places.
INTENTION_BANK_GLOB = "chat_intention_bank_ib*.yaml"
INTENTION_BANKS_DIR = Path(__file__).resolve().parent
_BANK_FILE_RE = re.compile(r"^chat_intention_bank_(ib\d{2})\.yaml$")
_ARABIC = re.compile(r"[\u0600-\u06FF]")

#: Bank YAML ``gate.kind`` that scores by aggregate thresholds (the IR5
#: paraphrase/adversarial bank) instead of all-threads-pass. The id is read
#: from the YAML, never hardcoded here.
_GATE_KIND_PARAPHRASE = "paraphrase"

#: IB-09 is a unit bank (pytest); it has no live YAML and is reported apart.
INTENTION_UNIT_BANKS: tuple[str, ...] = ("IB-09",)

#: IF-* failure class -> owning banks (contract §3). This is the taxonomy
#: mapping, not the bank registry: new banks are still auto-discovered.
INTENTION_IF_OWNERS: dict[str, tuple[str, ...]] = {
    "if_01": ("IB-04", "IB-05"),
    "if_02": ("IB-04",),
    "if_03": ("IB-06",),
    "if_04": ("IB-03",),
    "if_05": ("IB-03",),
    "if_06": ("IB-07", "IB-06"),
    "if_07": ("IB-08",),
    "if_08": ("IB-10",),
    "if_09": ("IB-11",),
}


def discover_intention_banks(directory: Path | None = None) -> dict[str, Path]:
    """Map ``IB-nn`` -> bank YAML by globbing ``chat_intention_bank_ib*.yaml``.

    The single registration point for a new intention bank: drop the file in
    this directory and the runner, the bench, and the tests all see it. IB-04
    and IB-05 are discovered exactly like every other bank (their YAML is
    unchanged).
    """
    directory = Path(directory) if directory else INTENTION_BANKS_DIR
    banks: dict[str, Path] = {}
    for path in sorted(directory.glob(INTENTION_BANK_GLOB)):
        match = _BANK_FILE_RE.match(path.name)
        if not match:
            continue
        # "ib04" -> "IB-04"
        banks[f"IB-{match.group(1)[2:]}"] = path
    return banks


def intention_gate_banks(directory: Path | None = None) -> dict[str, dict[str, Any]]:
    """Banks scored by the YAML ``gate:`` block, keyed by bank id.

    The IR5 paraphrase bank declares ``gate.kind: paraphrase`` in its YAML
    (accuracy / parity / fallthrough / ungrounded thresholds). Reading the id
    from the bank file means the scorer and the tests never hardcode it, and a
    new threshold bank needs no code edit.
    """
    gates: dict[str, dict[str, Any]] = {}
    for bank_id, path in discover_intention_banks(directory).items():
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            continue
        gate = doc.get("gate") if isinstance(doc, dict) else None
        if isinstance(gate, dict) and str(gate.get("kind") or "") == _GATE_KIND_PARAPHRASE:
            gates[bank_id] = dict(gate)
    return gates


#: Live/defined banks, discovered (not hardcoded).
INTENTION_BANKS: tuple[str, ...] = tuple(discover_intention_banks())
CLOSE_RUNS = 3

#: A turn whose v21 understand recorded one of these reasons did not finish
#: inside the Decision and is counted as a fallthrough (V21-1 fallthrough /
#: unrepairable, V21-2 committed route whose v21 exit is superseded). This is a
#: counter, not a pass bar: it never moves a thread, an objective, or ``honest``.
FALLTHROUGH_REASONS: tuple[str, ...] = (
    "fallthrough",
    "unrepairable",
    "committed_route_skipped",
)


def _turn_fell_through(turn: dict[str, Any]) -> bool | None:
    """(fell) for one recorded turn, or None when that turn did not measure it."""
    if not isinstance(turn, dict):
        return None
    if "fell_through" in turn:
        return bool(turn.get("fell_through"))
    if "v21_miss" in turn:
        return str(turn.get("v21_miss") or "") in FALLTHROUGH_REASONS
    return None


def _turn_expected_lang(turn: dict[str, Any]) -> str:
    """The language of the *asking* turn, from its own text (not the reply)."""
    return "ar" if _ARABIC.search(str(turn.get("say") or "")) else "en"


def _turn_ungrounded(turn: dict[str, Any]) -> int:
    """How many figure-grounding misses this turn recorded (IRP-5)."""
    return sum(
        1
        for miss in turn.get("misses") or []
        if str(miss).startswith(("numbers_grounded", "numbers_from"))
    )


def paraphrase_run_score(run: dict[str, Any]) -> dict[str, Any]:
    """IR5 score for one live run of the paraphrase bank.

    * ``accuracy`` — share of turns whose declared checks pass (entity, figure,
      refusal, no-fallthrough, not-degraded). A turn is the scored unit.
    * ``parity`` — ``1 - |accuracy_ar - accuracy_en|`` (the difference form; the
      contract states the ≥ 0.98 bar, this module defines the formula). The raw
      ``parity_gap`` is reported alongside it.
    * ``fallthrough`` — turns whose v21 marker is a fallthrough reason.
    * ``ungrounded`` — figure-grounding misses.

    A run with no recorded turns is ``missing``, never zero-fail.
    """
    turns = [
        turn
        for thread in run.get("threads") or []
        if isinstance(thread, dict)
        for turn in thread.get("turns") or []
        if isinstance(turn, dict)
    ]
    if not turns:
        return {
            "status": "missing", "turns": 0, "correct": 0, "accuracy": None,
            "accuracy_en": None, "accuracy_ar": None, "parity": None,
            "parity_gap": None, "fallthrough": 0, "ungrounded": 0,
        }

    def _acc(rows: list[dict[str, Any]]) -> float | None:
        if not rows:
            return None
        return sum(1 for t in rows if t.get("pass")) / len(rows)

    en = [t for t in turns if _turn_expected_lang(t) == "en"]
    ar = [t for t in turns if _turn_expected_lang(t) == "ar"]
    acc_en, acc_ar = _acc(en), _acc(ar)
    parity = None
    gap = None
    if acc_en is not None and acc_ar is not None:
        gap = abs(acc_ar - acc_en)
        parity = 1.0 - gap
    correct = sum(1 for t in turns if t.get("pass"))
    return {
        "status": "scored",
        "turns": len(turns),
        "correct": correct,
        "accuracy": round(correct / len(turns), 4),
        "accuracy_en": round(acc_en, 4) if acc_en is not None else None,
        "accuracy_ar": round(acc_ar, 4) if acc_ar is not None else None,
        "parity": round(parity, 4) if parity is not None else None,
        "parity_gap": round(gap, 4) if gap is not None else None,
        "fallthrough": sum(1 for t in turns if _turn_fell_through(t) is True),
        "ungrounded": sum(_turn_ungrounded(t) for t in turns),
    }


def paraphrase_run_pass(score: dict[str, Any], gate: dict[str, Any]) -> bool:
    """Does one run clear the IR5 thresholds? A missing score never passes."""
    if score.get("status") != "scored":
        return False
    accuracy = score.get("accuracy")
    parity = score.get("parity")
    return bool(
        accuracy is not None
        and accuracy >= float(gate.get("accuracy", 0.95))
        and parity is not None
        and parity >= float(gate.get("parity", 0.98))
        and int(score.get("fallthrough") or 0) <= int(gate.get("fallthrough", 0))
        and int(score.get("ungrounded") or 0) <= int(gate.get("ungrounded", 0))
    )


def fallthrough_count(retests: list[dict[str, Any]]) -> dict[str, Any]:
    """How many recorded turns fell through (V21-1 + V21-2).

    Reads the per-turn marker a run records (``fell_through`` / ``v21_miss``).
    A run that never recorded the marker is not counted as zero: the honest
    status stays ``missing`` until a live bank measures it. Reported on its
    own; it never changes a pass bar or the honest verdict (RULE_36).
    """
    measured = fell = 0
    runs = 0
    for run in retests:
        run_measured = False
        for thread in run.get("threads") or []:
            for turn in thread.get("turns") or []:
                got = _turn_fell_through(turn)
                if got is None:
                    continue
                measured += 1
                run_measured = True
                fell += 1 if got else 0
        if run_measured:
            runs += 1
    if not measured:
        return {"status": "missing", "count": None, "turns": 0, "runs": 0}
    return {
        "status": "fail" if fell else "reached",
        "count": fell,
        "turns": measured,
        "runs": runs,
    }


def load_intention_runs(root: Path = EVIDENCE) -> list[dict[str, Any]]:
    """IB-04/IB-05 live runs, oldest first. A partial run never counts."""
    runs = []
    for path in sorted(root.glob(INTENTION_GLOB)):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(row, dict) and row.get("tier") == "live_intention" and row.get("bank"):
            row["_file"] = path.name
            runs.append(row)
    return sorted(runs, key=lambda r: str(r.get("run_at") or ""))


def _intention_run_pass(row: dict[str, Any]) -> bool:
    threads = row.get("threads") or []
    return bool(threads) and all(t.get("pass") for t in threads if isinstance(t, dict))


def intention_bank_status(
    runs: list[dict[str, Any]],
    bank_id: str,
    gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Honest bank status: missing / partial / fail / reached over CLOSE_RUNS.

    A bank with no live run is ``missing``, never zero-fail. ``reached`` needs
    the last ``CLOSE_RUNS`` full runs to pass every thread.

    ``gate`` selects the aggregate-threshold path (IR5 paraphrase bank): a run
    passes when accuracy/parity/fallthrough/ungrounded clear the ``gate:``
    block, not when every thread passes. The last run's score is attached so
    the number is reported, never inferred.
    """
    mine = [r for r in runs if r.get("bank") == bank_id]
    if not mine:
        return {"status": "missing", "runs": 0, "passed": 0, "of": 0, "last": None}
    window = mine[-CLOSE_RUNS:]
    if gate:
        scores = [paraphrase_run_score(r) for r in window]
        passed = sum(1 for s in scores if paraphrase_run_pass(s, gate))
        last_ok = paraphrase_run_pass(scores[-1], gate)
        last_extra = {"gate": dict(gate), "score": scores[-1]}
    else:
        passed = sum(1 for r in window if _intention_run_pass(r))
        last_ok = _intention_run_pass(mine[-1])
        last_extra = {}
    if not last_ok:
        status = "fail"
    elif len(window) == CLOSE_RUNS and passed == CLOSE_RUNS:
        status = "reached"
    else:
        status = "partial"
    return {
        "status": status,
        "runs": len(mine),
        "passed": passed,
        "of": len(window),
        "last": mine[-1].get("_file"),
        **last_extra,
    }


def _intention_class_status(*banks: dict[str, Any]) -> str:
    """IF-* status from its owning banks. ``fixed`` needs every bank reached.

    ``seen`` needs a dated live run that failed a turn; ``missing`` is no live
    run at all; anything else is ``pending``.
    """
    statuses = [b.get("status") for b in banks]
    if all(s == "reached" for s in statuses):
        return "fixed"
    if all(s == "missing" for s in statuses):
        return "missing"
    if any(s == "fail" for s in statuses):
        return "seen"
    return "pending"


def _intention_ladder(
    banks: dict[str, dict[str, Any]],
    paraphrase_banks: tuple[str, ...] = (),
) -> dict[str, str]:
    """``IR0``–``IR5`` each scored by its own exit gate (contract §6).

    Reported per level, as the contract's Phase 4 does (``IR2`` reached while
    ``IR1`` is not). Entry is cumulative on paper; the report never hides a
    lower level's miss behind a higher pass, so no level is inferred. ``IR5``
    needs ``IB-10`` + ``IB-11`` + every discovered locked paraphrase bank
    (``gate.kind: paraphrase``) reached. The ``g6_runner`` gate is a separate
    command and is not inferred here.
    """
    def reached(*ids: str) -> bool:
        return all((banks.get(i) or {}).get("status") == "reached" for i in ids)

    ir5 = reached("IB-10", "IB-11") and bool(paraphrase_banks) and reached(*paraphrase_banks)
    return {
        "ir0": "reached",  # contract committed + unit bank green (this file)
        "ir1": "reached" if reached("IB-10") else "not reached",
        "ir2": "reached" if reached("IB-04", "IB-05") else "not reached",
        "ir3": "reached" if reached("IB-03", "IB-01") else "not reached",
        "ir4": "reached" if reached("IB-07", "IB-08") else "not reached",
        "ir5": "reached" if ir5 else "not reached",
    }


def intention_banks(root: Path = EVIDENCE) -> dict[str, Any]:
    """Every discovered intention bank + IF-* classes + IR0–IR5. Never merged.

    Reads the live intention evidence only. A bank with no live run is
    ``missing``, never zero-fail; ``reached`` needs ``CLOSE_RUNS`` consecutive
    full runs. IB-09 is a unit bank (pytest) and is reported apart. This block
    never changes a Chat objective, the honest verdict, or the Ask 10/10 score
    (RULE_36).
    """
    runs = load_intention_runs(root)
    gates = intention_gate_banks()
    banks = {
        bank_id: intention_bank_status(runs, bank_id, gates.get(bank_id))
        for bank_id in INTENTION_BANKS
    }
    paraphrase = {
        bank_id: banks[bank_id] for bank_id in gates if bank_id in banks
    }
    unit_banks = {
        bank_id: {
            "status": "unit",
            "runs": 0,
            "passed": 0,
            "of": 0,
            "last": None,
            "evidence": "backend/ai/tests/test_intention_banks.py",
        }
        for bank_id in INTENTION_UNIT_BANKS
    }
    classes = {
        name: _intention_class_status(*(banks.get(b, {}) for b in owners))
        for name, owners in INTENTION_IF_OWNERS.items()
    }
    blocked = None
    files = sorted(root.glob(INTENTION_BLOCKED_GLOB))
    if files:
        try:
            row = json.loads(files[-1].read_text(encoding="utf-8"))
        except (OSError, ValueError):
            row = {}
        if isinstance(row, dict):
            blocked = {
                "file": files[-1].name,
                "run_at": row.get("run_at"),
                "reason": row.get("reason"),
                "release": row.get("release"),
            }
    return {
        "banks": banks,
        "paraphrase": paraphrase,
        "unit_banks": unit_banks,
        **classes,
        **_intention_ladder(banks, tuple(gates)),
        "blocked": blocked,
        "rule": (
            "A bank with no live run is missing, never zero-fail. A bank reaches "
            f"only after {CLOSE_RUNS} consecutive full live runs; a later fail "
            "reopens it. IB-06 (write) needs STACK-HOLD and stays missing here. "
            "IB-09 is unit. The paraphrase bank gates on accuracy/parity/"
            "fallthrough/grounding, never all-threads-pass. Reported, not merged "
            "into Ask 10/10 (RULE_36)."
        ),
    }


def load_retests(root: Path = EVIDENCE) -> list[dict[str, Any]]:
    """Full retest runs, oldest first. A partial (``--only``) run never counts."""
    runs = []
    for path in sorted(root.glob(RETEST_GLOB)):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(row, dict) and row.get("tier") == "live_retest" and not row.get("partial"):
            row["_file"] = path.name
            runs.append(row)
    return sorted(runs, key=lambda r: str(r.get("run_at") or ""))


def _last_runs(retests: list[dict[str, Any]], key: str, name: str) -> list[tuple[str, bool]]:
    out = [
        (str(r.get("_file") or r.get("run_at")), bool((r.get(key) or {})[name]))
        for r in retests
        if name in (r.get(key) or {})
    ]
    return out[-CLOSE_RUNS:]


def finding_closure(finding_id: str, retests: list[dict[str, Any]]) -> tuple[bool, str]:
    """(closed, note). Closed = the last three full runs naming it all passed."""
    runs = _last_runs(retests, "findings", finding_id)
    passed = sum(1 for _, ok in runs if ok)
    if len(runs) == CLOSE_RUNS and passed == CLOSE_RUNS:
        return True, f"closed by retest {passed}/{CLOSE_RUNS} ({runs[0][0]} … {runs[-1][0]})"
    if not runs:
        return False, "no retest yet"
    return False, f"retest {passed}/{len(runs)} of {CLOSE_RUNS}"


def _retest_live(retests: list[dict[str, Any]], objective: str) -> tuple[str, str] | None:
    """Live status from the retest bank, or None when no run measured it."""
    runs = _last_runs(retests, "objectives", objective)
    if not runs:
        return None
    passed = sum(1 for _, ok in runs if ok)
    note = f"retest {passed}/{len(runs)} of {CLOSE_RUNS}"
    if not runs[-1][1]:
        return "fail", note
    return ("reached" if len(runs) == CLOSE_RUNS and passed == CLOSE_RUNS else "partial"), note


def _retest_latency(retests: list[dict[str, Any]]) -> tuple[str, str] | None:
    runs = [r for r in retests if isinstance(r.get("latency"), dict)][-CLOSE_RUNS:]
    if not runs:
        return None
    verdicts = []
    for run in runs:
        lat = run["latency"]
        turns = int(lat.get("turns") or 0)
        p50 = float(lat.get("p50_ms") or 0)
        share = (int(lat.get("over_4s") or 0) / turns) if turns else 1.0
        calls = float(lat.get("llm_calls_p50") or 0)
        if p50 <= 4000 and share <= 0.15 and calls <= 2:
            verdicts.append("reached")
        elif p50 <= 4000:
            verdicts.append("partial")
        else:
            verdicts.append("fail")
    last = runs[-1]["latency"]
    note = (
        f"retest p50 {last.get('p50_ms')} ms · {last.get('over_4s')}/{last.get('turns')} turns >4s · "
        f"llm p50 {last.get('llm_calls_p50')} · {len(runs)}/{CLOSE_RUNS} runs"
    )
    if len(runs) < CLOSE_RUNS and verdicts[-1] == "reached":
        return "partial", note
    return _worst(*verdicts), note


def _worst(*statuses: str) -> str:
    order = {"fail": 0, "missing": 1, "partial": 2, "reached": 3}
    return min(statuses, key=lambda s: order.get(s, 1))


def _obj(row: dict[str, Any], key: str) -> float | None:
    raw = (row.get("per_objective_pass") or {}).get(key)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _frac_ok(value: float | None, *, bar: float = 1.0) -> str:
    if value is None:
        return "missing"
    if value >= bar:
        return "reached"
    if value >= 0.5:
        return "partial"
    return "fail"


@dataclass(frozen=True)
class Column:
    stub: str
    live: str
    week: str
    honest: str
    note: str
    sources: tuple[str, ...]


@dataclass(frozen=True)
class Row:
    id: str
    name: str
    must: str
    goal: str
    column: Column


def _operator_hits(
    obs: dict[str, Any],
    *,
    objective: str | None = None,
    metric: str | None = None,
    retests: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    hits = []
    for finding in obs.get("findings") or []:
        if not isinstance(finding, dict):
            continue
        objs = list(finding.get("objectives") or [])
        mets = list(finding.get("metrics") or [])
        if objective and objective not in objs:
            continue
        if metric and metric not in mets:
            continue
        closed, why = finding_closure(str(finding.get("id") or ""), retests or [])
        if closed:
            finding = {**finding, "status": "closed", "closure": why}
        elif retests:
            finding = {**finding, "closure": why}
        hits.append(finding)
    return hits


def _week_status(
    obs: dict[str, Any],
    *,
    objective: str | None = None,
    metric: str | None = None,
    retests: list[dict[str, Any]] | None = None,
) -> str:
    hits = _operator_hits(obs, objective=objective, metric=metric, retests=retests)
    if not hits:
        return "missing"
    if any(h.get("status") == "fail" for h in hits):
        return "fail"
    if any(h.get("status") == "partial" for h in hits):
        return "partial"
    return "reached"


def _week_note(
    obs: dict[str, Any],
    *,
    objective: str | None = None,
    metric: str | None = None,
    retests: list[dict[str, Any]] | None = None,
) -> str:
    hits = _operator_hits(obs, objective=objective, metric=metric, retests=retests)
    if not hits:
        return "no operator miss this week"
    return "; ".join(
        f"{h.get('id')}: {h.get('what')}" + (f" [{h['closure']}]" if h.get("closure") else "")
        for h in hits
    )


def _c8_live(c1: dict[str, Any]) -> tuple[str, str]:
    hist = c1.get("latency_histogram") or {}
    samples = int(c1.get("latency_samples") or 0)
    over = int(hist.get("4000ms+") or 0)
    try:
        p50 = float(c1.get("latency_p50_ms") or 0)
    except (TypeError, ValueError):
        p50 = 0.0
    share = (over / samples) if samples else 1.0
    note = f"p50 {p50:.0f} ms · {over}/{samples} turns >4s"
    if p50 <= 4000 and share <= 0.15:
        return "reached", note
    if p50 <= 4000:
        return "partial", note
    return "fail", note


def score_chat_objectives(
    *,
    stub: dict[str, Any] | None = None,
    live_c1: dict[str, Any] | None = None,
    live_c2: dict[str, Any] | None = None,
    live_a9: dict[str, Any] | None = None,
    operator: dict[str, Any] | None = None,
    retests: list[dict[str, Any]] | None = None,
) -> list[Row]:
    runs = load_retests() if retests is None else list(retests)
    g5 = stub if stub is not None else _load(G5_FILE)
    c1 = live_c1 if live_c1 is not None else _load(LIVE_C1_FILE)
    c2 = live_c2 if live_c2 is not None else _load(LIVE_C2_FILE)
    a9 = live_a9 if live_a9 is not None else _load(LIVE_A9_FILE)
    obs = operator if operator is not None else _load(OPERATOR_FILE)

    journeys = list(a9.get("journeys") or [])
    chat_clean = bool(journeys) and all(not j.get("chat_mutated") for j in journeys)

    specs = [
        ("C1", "Continuity", "Resolve any entity/number/decision from turns 1..N-1 at turn N.", "Focus ≥ 0.95 on 10-turn scripts"),
        ("C2", "Grounded recall", "Facts from tools stay available; numbers in the answer are in the payload.", "Recall 100% · facts ⊆ tool payload"),
        ("C3", "Slot memory", "Never re-ask a slot the user already gave.", "Slot carry-over = 1.0"),
        ("C4", "One decision", "Routers are signals; one Arbiter picks one TurnDecision.", "Decision log 100% · router ≥ 0.98"),
        ("C5", "Truthful surface", "Chat advises and hands off. No host mutation. No post-hoc rewrite.", "0 Chat host writes"),
        ("C6", "Identity constancy", "Same persona, date, user. Never invent a name or title.", "0 invented-identity failures"),
        ("C7", "Language fidelity", "Reply language = user language, including follow-ups.", "Language golden 100%"),
        ("C8", "Latency", "Simple turn ≤ 2 LLM calls; wall clock p50 ≤ 4 s.", "p50 ≤ 4s · few turns over budget"),
        ("C9", "Plan awareness", "Status of my request comes from active_plans, 0 LLM.", "100% from state"),
        ("C10", "Memory use", "A confirmed learn_fact applies later in the same thread.", "learn_fact turn-1 → applied turn-3"),
    ]

    rows: list[Row] = []
    for oid, name, must, goal in specs:
        stub_s = _frac_ok(_obj(g5, oid))
        week_s = _week_status(obs, objective=oid, retests=runs)
        week_note = _week_note(obs, objective=oid, retests=runs)
        sources = [G5_FILE, OPERATOR_FILE]
        if runs:
            sources.append(RETEST_GLOB)

        if oid == "C1":
            live_s = "reached" if float(c1.get("focus_retention") or 0) >= 0.95 and int(c1.get("turns_passed") or 0) == 24 else "fail"
            live_note = f"23o focus {c1.get('focus_retention')} on {c1.get('turns_passed')}/{c1.get('total_turns')}"
            sources.append(LIVE_C1_FILE)
        elif oid == "C2":
            live_s = "reached" if _obj(c2, "C2") == 1.0 and int(c2.get("turns_passed") or 0) == 24 else "fail"
            live_note = f"23p C2 {_obj(c2, 'C2')} on {c2.get('turns_passed')}/{c2.get('total_turns')}"
            sources.append(LIVE_C2_FILE)
        elif oid == "C3":
            live_s = _frac_ok(float(c1.get("slot_carry_over")) if c1.get("slot_carry_over") is not None else None)
            live_note = f"23o slot_carry {c1.get('slot_carry_over')}"
            sources.append(LIVE_C1_FILE)
        elif oid == "C4":
            live_s = _frac_ok(float(c1.get("router_agreement") or 0), bar=0.90)
            live_note = f"23o router {c1.get('router_agreement')}"
            sources.append(LIVE_C1_FILE)
        elif oid == "C5":
            live_s = "reached" if chat_clean else "fail"
            live_note = "6B verify: chat_mutated=false on 3 ESS"
            sources.append(LIVE_A9_FILE)
        elif oid == "C6":
            live_s, live_note = _retest_live(runs, "C6") or ("missing", "no live identity-honesty bank")
        elif oid == "C7":
            live_s = _frac_ok(float(c1.get("language_fidelity") or 0))
            live_note = f"23o language {c1.get('language_fidelity')}"
            sources.append(LIVE_C1_FILE)
        elif oid == "C8":
            live_s, live_note = _retest_latency(runs) or _c8_live(c1)
            sources.append(LIVE_C1_FILE)
        elif oid == "C9":
            live_s, live_note = _retest_live(runs, "C9") or ("missing", "live plan-status bank not re-run this week")
        else:
            live_s = _frac_ok(_obj(c2, "C10"))
            live_note = f"23p C10 {_obj(c2, 'C10')}"
            sources.append(LIVE_C2_FILE)

        if oid not in ("C6", "C8", "C9"):
            retest = _retest_live(runs, oid)
            if retest is not None:
                live_s = retest[0] if live_s == "missing" else _worst(live_s, retest[0])
                live_note = f"{live_note} · {retest[1]}"

        honest = _worst(live_s if live_s != "missing" else "partial", week_s if week_s != "missing" else live_s)
        if live_s == "missing" and week_s == "missing":
            honest = "missing"
        note = f"{live_note}. week: {week_note}"
        rows.append(
            Row(
                oid,
                name,
                must,
                goal,
                Column(stub_s, live_s, week_s, honest, note, tuple(sources)),
            )
        )
    return rows


def score_expert_metrics(
    objectives: list[Row],
    operator: dict[str, Any] | None = None,
    retests: list[dict[str, Any]] | None = None,
) -> list[Row]:
    runs = load_retests() if retests is None else list(retests)
    obs = operator if operator is not None else _load(OPERATOR_FILE)
    by_c = {r.id: r.column.honest for r in objectives}

    specs = [
        ("M01", "Grounding", "Facts = host only.", "C2 honest", by_c.get("C2", "missing")),
        ("M02", "Fabrication", "0 invented people, titles, or amounts.", "C6 honest", by_c.get("C6", "missing")),
        ("M03", "Determinism pass^3", "Same entity/metric three times.", "not in CI", "missing"),
        ("M04", "Entity resolution", "employee_no / name match host.", "C6 honest", by_c.get("C6", "missing")),
        ("M05", "Metric stability", "Repeat ask → same integer.", "C1 honest", by_c.get("C1", "missing")),
        ("M06", "Mode contract", "Chat never writes the host.", "C5 honest", by_c.get("C5", "reached")),
        ("M07", "Authz", "403-honest deny. No soft empty.", "TASKS B5 still PARTIAL", "partial"),
        ("M08", "Calibration", "Say unknown. Do not speak ungrounded.", "C2 honest", by_c.get("C2", "missing")),
        ("M09", "Session memory", "Focus and slots survive the next turn.", "C1+C3", _worst(by_c.get("C1", "missing"), by_c.get("C3", "missing"))),
        ("M10", "LTM hygiene", "No other-user leak on cold start.", "QA PARTIAL", "partial"),
        ("M11", "Learning loop", "Thumbs-down becomes a fixture, not silent drift.", "QA PARTIAL", "partial"),
        ("M13", "Domain expertise", "Leave / pay / ESS explain without invention.", "C2+C6", _worst(by_c.get("C2", "missing"), by_c.get("C6", "missing"))),
        ("M14", "Adversarial", "Injection treated as data. Writes refused.", "QA C1–C3 PARTIAL", "partial"),
        ("M17", "UX honesty", "Chart/export matches prose. No hollow table.", "week hollow-export", _week_status(obs, metric="M17", retests=runs) if _week_status(obs, metric="M17", retests=runs) != "missing" else "partial"),
    ]

    rows: list[Row] = []
    for mid, name, must, goal, honest in specs:
        week = _week_status(obs, metric=mid, retests=runs)
        rows.append(
            Row(
                mid,
                name,
                must,
                goal,
                Column("missing", "missing", week, honest, _week_note(obs, metric=mid, retests=runs), (OPERATOR_FILE,)),
            )
        )
    return rows


def score_chat_bench(
    *,
    stub: dict[str, Any] | None = None,
    live_c1: dict[str, Any] | None = None,
    live_c2: dict[str, Any] | None = None,
    live_a9: dict[str, Any] | None = None,
    operator: dict[str, Any] | None = None,
    retests: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    runs = load_retests() if retests is None else list(retests)
    objectives = score_chat_objectives(
        stub=stub, live_c1=live_c1, live_c2=live_c2, live_a9=live_a9, operator=operator,
        retests=runs,
    )
    metrics = score_expert_metrics(objectives, operator=operator, retests=runs)
    honest = [r.column.honest for r in objectives]
    reached = sum(1 for s in honest if s == "reached")
    failed = sum(1 for s in honest if s == "fail")
    if failed >= 3 or reached <= 3:
        verdict = "fragile"
    elif failed:
        verdict = "inconsistent"
    elif reached == 10:
        verdict = "reliable"
    else:
        verdict = "partial"

    def _dump(rows: list[Row]) -> list[dict[str, Any]]:
        out = []
        for row in rows:
            payload = asdict(row)
            payload["column"]["sources"] = list(row.column.sources)
            out.append(payload)
        return out

    obs = operator if operator is not None else _load(OPERATOR_FILE)
    return {
        "date": "2026-09-26",
        "surface": "chat",
        "verdict": verdict,
        "reached": reached,
        "failed": failed,
        "partial": sum(1 for s in honest if s == "partial"),
        "missing": sum(1 for s in honest if s == "missing"),
        "n_objectives": 10,
        "rule": (
            "Honest = worst of last live snapshot and this week. Stub never upgrades a miss. "
            f"A week finding closes only after the last {CLOSE_RUNS} full live retest runs pass it."
        ),
        "l6_l7": "not scored — v21 rungs, not a Chat reliability claim",
        "fallthrough": fallthrough_count(runs),
        "intention": intention_banks(),
        "objectives": _dump(objectives),
        "metrics": _dump(metrics),
        "findings": [
            {**f, "closure": finding_closure(str(f.get("id") or ""), runs)[1]}
            for f in (obs or {}).get("findings") or []
            if isinstance(f, dict)
        ],
        "retest_runs": [r.get("_file") for r in runs],
        "sources": {
            "stub": G5_FILE,
            "live_c1": LIVE_C1_FILE,
            "live_c2": LIVE_C2_FILE,
            "live_a9": LIVE_A9_FILE,
            "operator": OPERATOR_FILE,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pulse Chat deep benchmark (offline evidence)")
    parser.add_argument("--write", nargs="?", const="__default__", metavar="PATH")
    args = parser.parse_args(argv)
    report = score_chat_bench()
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.write:
        path = (
            EVIDENCE / "PV2-chat-deep-2026-09-26.json"
            if args.write == "__default__"
            else Path(args.write)
        )
        path.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
