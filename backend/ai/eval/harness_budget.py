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
routing_phrase_sets
    Module-level phrase tables under ``engine/cognition/**`` — a top-level
    ``UPPER_CASE`` assignment whose annotation starts with ``tuple[str``,
    ``frozenset[str`` or ``set[str``, or whose value opens a ``frozenset(``,
    ``(`` or ``{`` literal that holds string tokens. These are the allowlists
    a ``re.compile`` meter cannot see (the 2026-09-24 Discuss→apply incident
    lived in one). Each is a human guess about user vocabulary and a domain
    assumption baked into the engine, so the count must shrink. ``*_i18n.py``
    files are included: moving a table there is relocation, not deletion.
domain_terms_in_core
    Source lines under ``engine/**`` that carry a host-domain word (HR/ESS
    vocabulary such as leave, payslip, loan, GOSI, إجازة, قرض). Pulse is a
    coworker for many domain apps; domain vocabulary belongs in packs,
    plugins and ``instance.yaml`` catalogs, never in the engine. Word match on
    a token boundary (no regex), comments and docstrings included on purpose:
    a comment that explains leave routing marks code that knows about leave.
brand_literals_in_core
    Source lines under ``engine/**`` naming a domain pack id (the directory
    names under ``domain_packs/``, e.g. nibras / eduos / carbon). Core must
    address packs through the registry, never by name. Target 0.

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

COGNITION_ROOT = ENGINE_ROOT / "cognition"

_COUNT_KEYS = (
    "staged_exits",
    "re_compile",
    "arabic_regex",
    "runner_lines",
    "tool_choice_uses",
    "routing_phrase_sets",
    "domain_terms_in_core",
    "brand_literals_in_core",
)

DOMAIN_PACKS_ROOT = REPO_ROOT / "domain_packs"

#: Host-domain vocabulary that must not appear in the engine. Lives in eval
#: (a meter), not in core. Lowercase; Arabic without diacritics.
DOMAIN_TERMS: frozenset[str] = frozenset({
    "leave", "leaves", "vacation", "vacations", "payslip", "payslips",
    "payroll", "salary", "salaries", "loan", "loans", "gosi", "eosi",
    "attendance", "overtime", "timesheet", "employee", "employees",
    "إجازة", "إجازات", "اجازة", "اجازه", "قرض", "قروض", "راتب", "رواتب",
    "حضور", "موظف", "الموظف", "الموظفين", "مسير",
})

_PHRASE_ANNOTATIONS = ("tuple[str", "frozenset[str", "set[str")
_PHRASE_LITERAL_OPENERS = ("frozenset(", "(", "{")
#: Prose constants (prompts, copy, labels) are not routing vocabulary.
_NOT_PHRASE_SUFFIXES = (
    "_PROMPT", "_TEMPLATE", "_TEXT", "_COPY", "_MSG", "_MESSAGE", "_LABEL",
    "_LABELS", "_HINT", "_URL", "_BLOCK", "_RULES", "_INSTRUCTION", "_INSTRUCTIONS",
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


def _is_phrase_table_line(line: str, following: str = "") -> bool:
    """Top-level ``_NAME[: ann] = <literal>`` whose literal holds string tokens.

    ``following`` is the next few source lines, so a table that opens its
    literal on the assignment line and lists its strings below still counts.
    """
    if not line or line[0] in " \t#":
        return False
    head, sep, rhs = line.partition("=")
    if not sep or head.endswith(("!", "<", ">", ":")) or rhs.startswith("="):
        return False
    name, _, annotation = head.partition(":")
    name = name.strip()
    if len(name) < 2 or not all(ch.isupper() or ch == "_" or ch.isdigit() for ch in name):
        return False
    if name.endswith(_NOT_PHRASE_SUFFIXES):
        return False
    annotation = annotation.strip()
    rhs = rhs.strip()
    if annotation:
        if not annotation.startswith(_PHRASE_ANNOTATIONS):
            return False
    elif not rhs.startswith(_PHRASE_LITERAL_OPENERS):
        return False
    window = rhs + "\n" + following
    return '"' in window or "'" in window


def _count_phrase_tables(root: Path) -> int:
    if not root.is_dir():
        return 0
    total = 0
    for path in sorted(root.rglob("*.py")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines):
            if _is_phrase_table_line(line, "\n".join(lines[idx + 1 : idx + 4])):
                total += 1
    return total


def _line_tokens(line: str) -> list[str]:
    out: list[str] = []
    buf: list[str] = []
    for ch in line.lower():
        if ch.isalnum() or ch == "_" or ("\u0600" <= ch <= "\u06ff"):
            buf.append(ch)
        elif buf:
            out.append("".join(buf))
            buf = []
    if buf:
        out.append("".join(buf))
    return out


def _count_domain_terms(files: list[Path]) -> int:
    total = 0
    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if any(tok in DOMAIN_TERMS for tok in _line_tokens(line)):
                total += 1
    return total


def pack_ids(root: Path = DOMAIN_PACKS_ROOT) -> frozenset[str]:
    """Domain pack ids = directory names under ``domain_packs/``."""
    if not root.is_dir():
        return frozenset()
    return frozenset(p.name.lower() for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))


def _count_brand_literals(files: list[Path], ids: frozenset[str]) -> int:
    if not ids:
        return 0
    total = 0
    for path in files:
        if path.parent.name in ids and path.parent.parent.name == "instances":
            continue  # a pack's own instance folder may name itself
        for line in path.read_text(encoding="utf-8").splitlines():
            if any(tok in ids for tok in _line_tokens(line)):
                total += 1
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
        "routing_phrase_sets": _count_phrase_tables(COGNITION_ROOT),
        "domain_terms_in_core": _count_domain_terms(engine_files),
        "brand_literals_in_core": _count_brand_literals(engine_files, pack_ids()),
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
