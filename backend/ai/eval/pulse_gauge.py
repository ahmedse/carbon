"""Pulse intelligence gauge — one command, one dated snapshot, one trend.

Pulse is a coworker for many domain apps. Its intelligence is therefore two
numbers moving in opposite directions:

* **engine meters go down** (``ai.eval.harness_budget``: exits, regex, phrase
  tables, domain words in core, runner size) — the harness stops deciding;
* **per-instance behaviour holds** (ladder L0–L7, G5 multi-turn, G6
  understanding, live soak) — the model plus catalog still gets it right.

The ladder, G5, G6 and the budget already exist as separate scorers that each
read one dated file. This module runs them together, from the working tree
and the newest committed evidence, and writes:

* ``docs/pulse/evidence/PV2-gauge-<date>.json`` — the full snapshot;
* ``docs/pulse/evidence/PV2-gauge-series.json`` — one compact row per date
  (the trend the canvas renders).

``--gate`` is the ratchet: exit 1 when any budget meter is above the ceiling
file **or above the previous snapshot**, or when a ladder level regressed.
"Must not rise" becomes a CI fact instead of a canvas sentence.

Snapshots are instance-scoped (``--instance nibras``). Behaviour banks are
Nibras ESS today; a second instance gets its own banks and its own column.

CLI::

    python -m ai.eval.pulse_gauge                 # print dashboard
    python -m ai.eval.pulse_gauge --write         # snapshot + series row
    python -m ai.eval.pulse_gauge --gate          # ratchet (exit 1 on any rise)
    python -m ai.eval.pulse_gauge --seed-history  # import dated budget files into the series
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from ai.eval.harness_budget import (
    _COUNT_KEYS as BUDGET_KEYS,
    DEFAULT_EVIDENCE as _BUDGET_BASELINE,
    gate_violations,
    measure as measure_budget,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = REPO_ROOT / "docs" / "pulse" / "evidence"
SERIES_PATH = EVIDENCE / "PV2-gauge-series.json"
CEILING_PATH = EVIDENCE / "PV2.1-budget-ceiling.json"

#: Budget meters that must never rise. ``tool_choice_uses`` may grow.
RATCHET_KEYS: tuple[str, ...] = tuple(k for k in BUDGET_KEYS if k != "tool_choice_uses")

_LEVEL_RANK = {"missing": 0, "partial": 1, "reached": 2}

#: Dated budget files that predate the series (history for the trend).
_HISTORY_BUDGET_FILES: tuple[tuple[str, str], ...] = (
    ("2026-09-23a", "PV2.1-budget-measured-2026-09-23-late.json"),
    ("2026-09-23b", "PV2.1-budget-2026-09-24.json"),  # measured 03:55 on the 24th, before the gauge existed
)


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _newest(pattern: str) -> tuple[str, dict[str, Any]]:
    files = sorted(EVIDENCE.glob(pattern))
    if not files:
        return "", {}
    return files[-1].name, _load(files[-1])


# ── Collectors ─────────────────────────────────────────────────────────────


def collect_ladder() -> dict[str, Any]:
    from ai.eval.intelligence_ladder import score_ladder

    report = score_ladder(lookup_zero_llm=True, write_zero_llm=True)
    levels = {row["id"]: row["status"] for row in report.get("levels", [])}
    levels.update({row["id"]: row["status"] for row in report.get("v21_levels", [])})
    misses = {
        row["id"]: [g["id"] for g in row.get("gates", []) if not g.get("ok")]
        for row in [*report.get("levels", []), *report.get("v21_levels", [])]
        if any(not g.get("ok") for g in row.get("gates", []))
    }
    return {
        "levels": levels,
        "misses": misses,
        "six_b_streak": report.get("six_b_streak"),
        "soak_complete": report.get("soak_complete"),
        "adr_0047": report.get("adr_0047"),
    }


def collect_g6() -> dict[str, Any]:
    name, row = _newest("PV2.1-g6-understand-*.json")
    if not row:
        return {}
    return {
        "source": name,
        "n": row.get("n"),
        "decision_accuracy": row.get("decision_accuracy"),
        "parity": row.get("parity"),
        "gate_pass": row.get("gate_pass"),
        "misses": len(row.get("misses") or []),
    }


def collect_g5() -> dict[str, Any]:
    name, row = _newest("PV2-g5-*.json")
    if not row:
        return {}
    return {
        "source": name,
        "scripts_passed": row.get("scripts_passed"),
        "scripts_run": row.get("scripts_run"),
        "turns_passed": row.get("turns_passed"),
        "total_turns": row.get("total_turns"),
        "focus_retention": row.get("focus_retention"),
        "slot_carry_over": row.get("slot_carry_over"),
        "router_agreement": row.get("router_agreement"),
        "llm_calls_p50": row.get("llm_calls_p50"),
    }


def collect_soak() -> dict[str, Any]:
    row = _load(EVIDENCE / "PV2-6B-nights.json")
    nights = row.get("nights") if isinstance(row.get("nights"), list) else []
    last = nights[-1] if nights and isinstance(nights[-1], dict) else {}
    return {
        "required_consecutive": row.get("required_consecutive"),
        "soak_complete": row.get("soak_complete"),
        "nights": len(nights),
        "last_night": last.get("date") or last.get("night") or "",
        "last_verdict": last.get("verdict") or last.get("status") or "",
    }


def collect_packs() -> dict[str, Any]:
    """ADR-0050: packs are self-contained and versioned; core is domain-free."""
    from ai.eval.pack_contract import check_all

    rows, violations = check_all()
    return {
        "packs": {r["id"]: {"version": r["version"], "domain": r["domain"]} for r in rows},
        "violations": violations,
        "gate_pass": not violations,
    }


def collect_agent_plan() -> dict[str, Any]:
    """Offline Agent/plan bank (planner seed, Discuss state, ADR-0046 guard)."""
    from ai.eval.agent_plan_runner import score

    return score()


def _coverage(agent: dict[str, Any]) -> dict[str, Any]:
    """What is scored, and what is still silent. Silence is stated."""
    if agent.get("n"):
        mark = "pass" if agent.get("gate_pass") else "FAIL"
        plan = f"bank {agent.get('passed')}/{agent.get('n')} {mark}"
    else:
        plan = "no bank — planner / plans_service / discuss are unmeasured"
    return {
        "chat_turn_path": "ladder L0–L7 · G5 · G6 · budget",
        "agent_plan_path": plan,
        "second_instance": "none — all banks are Nibras ESS",
    }


# ── Snapshot ───────────────────────────────────────────────────────────────


def snapshot(instance: str = "nibras") -> dict[str, Any]:
    budget = measure_budget()
    ladder = collect_ladder()
    agent = collect_agent_plan()
    return {
        "measured_at": budget.get("measured_at") or date.today().isoformat(),
        "instance": instance,
        "budget": {k: budget.get(k) for k in BUDGET_KEYS},
        "ladder": ladder,
        "g6": collect_g6(),
        "g5": collect_g5(),
        "soak": collect_soak(),
        "packs": collect_packs(),
        "agent_plan": agent,
        "coverage": _coverage(agent),
    }


def series_row(snap: dict[str, Any]) -> dict[str, Any]:
    ladder = snap.get("ladder") or {}
    g6 = snap.get("g6") or {}
    g5 = snap.get("g5") or {}
    return {
        "date": snap["measured_at"],
        "instance": snap.get("instance", ""),
        **{k: (snap.get("budget") or {}).get(k) for k in BUDGET_KEYS},
        "levels": ladder.get("levels") or {},
        "g6_accuracy": g6.get("decision_accuracy"),
        "g6_parity": g6.get("parity"),
        "g5_turns": f"{g5.get('turns_passed')}/{g5.get('total_turns')}" if g5 else "",
        "six_b_streak": ladder.get("six_b_streak"),
        "packs_ok": (snap.get("packs") or {}).get("gate_pass"),
        "agent_plan": (
            f"{(snap.get('agent_plan') or {}).get('passed')}/{(snap.get('agent_plan') or {}).get('n')}"
        ),
    }


def load_series() -> list[dict[str, Any]]:
    data = _load(SERIES_PATH)
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    return [r for r in rows if isinstance(r, dict)]


def save_series(rows: list[dict[str, Any]]) -> None:
    rows = sorted(rows, key=lambda r: str(r.get("date") or ""))
    SERIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    SERIES_PATH.write_text(
        json.dumps({"schema": 1, "rows": rows}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def upsert_row(rows: list[dict[str, Any]], row: dict[str, Any]) -> list[dict[str, Any]]:
    key = (row.get("date"), row.get("instance"))
    return [r for r in rows if (r.get("date"), r.get("instance")) != key] + [row]


def seed_history(rows: list[dict[str, Any]], instance: str = "nibras") -> list[dict[str, Any]]:
    """Import dated budget files as budget-only rows so the trend has a past."""
    for label, name in _HISTORY_BUDGET_FILES:
        payload = _load(EVIDENCE / name)
        if not payload:
            continue
        row = {"date": label, "instance": instance, "history_source": name}
        row.update({k: payload.get(k) for k in BUDGET_KEYS if k in payload})
        rows = upsert_row(rows, row)
    return rows


# ── Ratchet ────────────────────────────────────────────────────────────────


def previous_row(rows: list[dict[str, Any]], snap: dict[str, Any]) -> dict[str, Any] | None:
    """Most recent measured row before this snapshot's date (same instance)."""
    candidates = [
        r for r in rows
        if r.get("instance") == snap.get("instance")
        and str(r.get("date") or "") < str(snap["measured_at"])
        and not r.get("history_source")
    ]
    return sorted(candidates, key=lambda r: str(r.get("date")))[-1] if candidates else None


def ratchet_violations(snap: dict[str, Any], prev: dict[str, Any] | None, ceiling: dict[str, Any]) -> list[str]:
    out = list(gate_violations(snap["budget"], ceiling))
    out.extend(f"pack contract: {v}" for v in (snap.get("packs") or {}).get("violations") or [])
    agent = snap.get("agent_plan") or {}
    if agent.get("n") and not agent.get("gate_pass"):
        ids = ", ".join(m.get("id", "") for m in agent.get("misses") or [])
        out.append(f"agent plan bank: {agent.get('passed')}/{agent.get('n')} ({ids})")
    if prev:
        for key in RATCHET_KEYS:
            try:
                now, before = int(snap["budget"][key]), int(prev[key])
            except (KeyError, TypeError, ValueError):
                continue
            if now > before:
                out.append(f"{key}: rose {before} → {now} since {prev.get('date')}")
        prev_levels = prev.get("levels") or {}
        for level, status in (snap["ladder"].get("levels") or {}).items():
            was = prev_levels.get(level)
            if was and _LEVEL_RANK.get(status, 0) < _LEVEL_RANK.get(was, 0):
                out.append(f"ladder {level}: {was} → {status}")
    return out


# ── Dashboard text ─────────────────────────────────────────────────────────


def render_text(snap: dict[str, Any], prev: dict[str, Any] | None = None) -> str:
    b = snap["budget"]
    lines = [f"Pulse gauge · {snap['instance']} · {snap['measured_at']}", ""]
    lines.append("Engine meters (must fall)")
    for key in BUDGET_KEYS:
        delta = ""
        if prev and prev.get(key) is not None and b.get(key) is not None:
            d = int(b[key]) - int(prev[key])
            delta = f"  ({'+' if d > 0 else ''}{d} vs {prev.get('date')})" if d else "  (=)"
        lines.append(f"  {key:22s} {str(b.get(key)):>6}{delta}")
    ladder = snap["ladder"]
    lines += ["", "Ladder"]
    for level, status in (ladder.get("levels") or {}).items():
        miss = ladder.get("misses", {}).get(level)
        lines.append(f"  {level:3s} {status:8s}" + (f"  misses: {', '.join(miss)}" if miss else ""))
    g6, g5, soak = snap.get("g6") or {}, snap.get("g5") or {}, snap.get("soak") or {}
    lines += ["", "Behaviour (per instance)"]
    if g6:
        lines.append(f"  G6 understand  n={g6.get('n')} accuracy={g6.get('decision_accuracy'):.3f} parity={g6.get('parity'):.3f} gate={'pass' if g6.get('gate_pass') else 'FAIL'}")
    if g5:
        lines.append(f"  G5 multi-turn  {g5.get('turns_passed')}/{g5.get('total_turns')} turns · focus={g5.get('focus_retention')} slot={g5.get('slot_carry_over')} router={g5.get('router_agreement')} llm_p50={g5.get('llm_calls_p50')}")
    lines.append(f"  6B soak        streak={ladder.get('six_b_streak')} complete={soak.get('soak_complete')} nights={soak.get('nights')}")
    packs = snap.get("packs") or {}
    lines += ["", "Domain packs (ADR-0050)"]
    for pid, meta in (packs.get("packs") or {}).items():
        lines.append(f"  {pid:10s} v{meta.get('version')} {meta.get('domain')}")
    lines.append(f"  contract gate: {'pass' if packs.get('gate_pass') else 'FAIL'}")
    agent = snap.get("agent_plan") or {}
    if agent.get("n"):
        lines.append(
            f"  Agent/plan bank {agent.get('passed')}/{agent.get('n')} gate={'pass' if agent.get('gate_pass') else 'FAIL'}"
        )
    lines += ["", "Coverage"]
    for k, v in (snap.get("coverage") or {}).items():
        lines.append(f"  {k}: {v}")
    return "\n".join(lines) + "\n"


# ── CLI ────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pulse intelligence gauge")
    parser.add_argument("--instance", default="nibras")
    parser.add_argument("--write", action="store_true", help="write PV2-gauge-<date>.json and a series row")
    parser.add_argument("--gate", action="store_true", help="exit 1 on any meter rise or ladder regression")
    parser.add_argument("--seed-history", action="store_true", help="import dated budget files into the series")
    parser.add_argument("--json", action="store_true", help="print the snapshot as JSON instead of text")
    args = parser.parse_args(argv)

    rows = load_series()
    if args.seed_history:
        rows = seed_history(rows, args.instance)
        save_series(rows)

    snap = snapshot(args.instance)
    prev = previous_row(rows, snap)

    if args.write:
        out = EVIDENCE / f"PV2-gauge-{snap['measured_at']}.json"
        out.write_text(json.dumps(snap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        rows = upsert_row(rows, series_row(snap))
        save_series(rows)

    if args.json:
        sys.stdout.write(json.dumps(snap, indent=2, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(render_text(snap, prev))

    if args.gate:
        violations = ratchet_violations(snap, prev, _load(CEILING_PATH))
        if violations:
            for msg in violations:
                print(f"GATE: {msg}", file=sys.stderr)
            return 1
        print("GATE: pass — no meter rose, no ladder level regressed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
