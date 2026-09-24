"""Harness budget meter for Pulse engine complexity ceilings.

Walks ``backend/ai/engine`` and counts static complexity signals used to
gate regressions (PV2.1 budget evidence).

Counters
--------
staged_exits
    Substring occurrences of ``stage_exit(`` and ``StagedExit(`` in
    ``runner.py`` and extracted spine stage modules (refuse / handoff / bound ESS).
    Soft legacy gates use ``stage_soft_exit(`` and are not counted here.
re_compile
    Substring occurrences of ``re.compile`` in all ``**/*.py`` under engine.
arabic_regex
    Among ``re.compile`` call sites, how many have Arabic script (U+0600–U+06FF)
    on the **same source line** as the call or on any of the **next 8 lines**
    (inclusive window of 9 lines). Each ``re.compile`` occurrence on a line
    counts once; multiline compile expressions are not merged across windows.
    Implemented with a line scanner, not nested regex.
runner_lines
    Line count of ``runner.py`` (including blank lines).
tool_choice_uses
    Raw substring count of ``tool_choice`` in ``llm/**/*.py`` (comments included).

Gate (``--gate PATH``)
----------------------
Loads a ceiling JSON. Exits 1 when any measured counter **except**
``tool_choice_uses`` exceeds its ceiling value. Missing ceiling keys are ignored;
``tool_choice_uses`` is never gated (may grow freely).

CLI::

    python -m ai.eval.harness_budget
    python -m ai.eval.harness_budget --write
    python -m ai.eval.harness_budget --write PATH
    python -m ai.eval.harness_budget --gate ceiling.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
ENGINE_ROOT = REPO_ROOT / "backend" / "ai" / "engine"
RUNNER_PATH = ENGINE_ROOT / "cognition" / "turn" / "runner.py"
TURN_ROOT = RUNNER_PATH.parent
# Spine stage modules split from ``runner.py`` — ``stage_exit(`` calls live here now.
SPINE_RUNNER_PATHS = (
    RUNNER_PATH,
    TURN_ROOT / "runner_pre_s1.py",
    TURN_ROOT / "runner_s1.py",
    TURN_ROOT / "runner_s2_plan.py",
    TURN_ROOT / "runner_s3_s5.py",
    TURN_ROOT / "runner_s6.py",
)
LLM_ROOT = ENGINE_ROOT / "llm"
DEFAULT_EVIDENCE = REPO_ROOT / "docs" / "pulse" / "evidence" / "PV2.1-budget-2026-09-23.json"

_COUNT_KEYS = (
    "staged_exits",
    "re_compile",
    "arabic_regex",
    "runner_lines",
    "tool_choice_uses",
)

_ARABIC_RANGE = range(0x0600, 0x06FF + 1)


def _repo_paths() -> tuple[Path, Path, Path, Path]:
    return REPO_ROOT, ENGINE_ROOT, RUNNER_PATH, LLM_ROOT


def _contains_arabic(text: str) -> bool:
    return any(ord(ch) in _ARABIC_RANGE for ch in text)


def _count_substring(text: str, needle: str) -> int:
    if not needle:
        return 0
    count = start = 0
    while True:
        idx = text.find(needle, start)
        if idx < 0:
            return count
        count += 1
        start = idx + len(needle)


def _iter_engine_py_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _count_re_compile_and_arabic(files: list[Path]) -> tuple[int, int]:
    re_total = 0
    arabic_sites = 0
    needle = "re.compile"
    for path in files:
        lines = path.read_text(encoding="utf-8").splitlines()
        for line_no, line in enumerate(lines):
            hits = _count_substring(line, needle)
            if hits == 0:
                continue
            re_total += hits
            window = lines[line_no : line_no + 9]
            if _contains_arabic("\n".join(window)):
                arabic_sites += hits
    return re_total, arabic_sites


def _count_tool_choice(root: Path) -> int:
    if not root.is_dir():
        return 0
    total = 0
    for path in sorted(root.rglob("*.py")):
        total += _count_substring(path.read_text(encoding="utf-8"), "tool_choice")
    return total


def measure() -> dict[str, Any]:
    """Return budget counters plus ``measured_at`` (ISO date)."""
    _, engine_root, runner_path, llm_root = _repo_paths()
    engine_files = _iter_engine_py_files(engine_root)
    runner_text = runner_path.read_text(encoding="utf-8")
    re_compile, arabic_regex = _count_re_compile_and_arabic(engine_files)
    runner_lines = runner_text.count("\n") + (1 if runner_text and not runner_text.endswith("\n") else 0)
    if not runner_text:
        runner_lines = 0
    staged_exits = 0
    for spine_path in SPINE_RUNNER_PATHS:
        if not spine_path.is_file():
            continue
        spine_text = spine_path.read_text(encoding="utf-8")
        staged_exits += _count_substring(spine_text, "StagedExit(")
        staged_exits += _count_substring(spine_text, "stage_exit(")
    # Do not count stage_soft_exit — those are legacy soft gates (Q4).
    return {
        "staged_exits": staged_exits,
        "re_compile": re_compile,
        "arabic_regex": arabic_regex,
        "runner_lines": runner_lines,
        "tool_choice_uses": _count_tool_choice(llm_root),
        "measured_at": date.today().isoformat(),
    }


def gate_violations(measured: dict[str, Any], ceiling: dict[str, Any]) -> list[str]:
    """Return human-readable violations; empty list means within budget."""
    violations: list[str] = []
    for key in _COUNT_KEYS:
        if key == "tool_choice_uses":
            continue
        if key not in ceiling:
            continue
        try:
            limit = int(ceiling[key])
            value = int(measured[key])
        except (KeyError, TypeError, ValueError):
            continue
        if value > limit:
            violations.append(f"{key}: measured {value} > ceiling {limit}")
    return violations


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pulse harness budget meter")
    parser.add_argument(
        "--write",
        nargs="?",
        const=str(DEFAULT_EVIDENCE),
        default=None,
        metavar="PATH",
        help=f"Write JSON evidence (default: {DEFAULT_EVIDENCE.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--gate",
        metavar="PATH",
        help="Ceiling JSON; exit 1 if any counter except tool_choice_uses exceeds ceiling",
    )
    args = parser.parse_args(argv)

    payload = measure()
    text = json.dumps(payload, indent=2) + "\n"

    if args.write is not None:
        out_path = Path(args.write)
        if not out_path.is_absolute():
            out_path = REPO_ROOT / out_path
        _write_json(out_path, payload)

    if args.gate:
        gate_path = Path(args.gate)
        if not gate_path.is_absolute():
            gate_path = REPO_ROOT / gate_path
        ceiling = _load_json(gate_path)
        violations = gate_violations(payload, ceiling)
        if violations:
            for msg in violations:
                print(msg, file=sys.stderr)
            return 1

    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
