#!/usr/bin/env python3
"""Fail-open lint (P1-13).

Detects two fail-open anti-patterns that violate Principle 1 (fail-closed):

  1. **Fail-open exception handler** — an ``except`` clause whose body
     reports SUCCESS after swallowing an error::

         except Exception:
             return True            # or: passed = True / passed=True

  2. **No-op tenancy filter** — a ``_apply_*filter`` method that returns the
     queryset *unchanged* (the P1-11 ``_apply_tenancy_filter`` bug)::

         def _apply_tenancy_filter(self, qs):
             return qs               # ← filter applies nothing (fail-open)

Outputs one ``relpath:lineno: message`` line per offender and exits 1 when any
offender is not present in the allowlist.

Allowlist format (one entry per line, ``#`` starts the justification)::

    backend/ai/some_module.py:42  # justified: retry helper returns True on retryable error

Blank lines and ``#`` comment lines are ignored.  Line numbers are pinned; when
code shifts, update the entry — or better, fix the code.

Usage::

    .ai-toolkit/scripts/failopen-lint.py [--root ROOT] [--allowlist FILE]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Directories skipped while walking the tree (vendored / generated / scratch).
_SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", "migrations",
    "dist", "build", "static", "staticfiles", "media", "archive",
    "archived_apps", "chroma_db", "logs", "raw", "tests", "test",
    ".ai-toolkit",
}

# ── Pattern 1: fail-open exception handler ─────────────────────────────────────
_EXCEPT_RE = re.compile(r"^\s*except\b")
# Bare success statements: `return True` or `passed = True` (whole statement).
_SUCCESS_RE = re.compile(r"^\s*(return\s+True|passed\s*=\s*True)\s*(#.*)?$")

# ── Pattern 2: no-op tenancy filter ────────────────────────────────────────────
_FILTER_DEF_RE = re.compile(r"^\s*def\s+(_apply_\w*filter)\s*\(")
# A bare `return qs` / `return queryset` with nothing applied (no .filter()).
_RETURN_QS_RE = re.compile(r"^\s*return\s+(qs|queryset|query_set)\s*(#.*)?$")
# A real filter narrows the queryset; a no-op filter never calls these.
_NARROW_RE = re.compile(r"\.(filter|exclude)\(")

# How many lines ahead of an ``except`` we search for a success statement.
_EXCEPT_LOOKAHEAD = 15


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def find_offenders(path: Path) -> list[tuple[int, str]]:
    """Return [(lineno, message)] fail-open offenders in ``path``."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = text.splitlines()
    offenders: list[tuple[int, str]] = []

    # Pattern 1 — except clause whose block reports success.
    for i, line in enumerate(lines):
        if not _EXCEPT_RE.match(line):
            continue
        base_indent = _indent(line)
        for j in range(i + 1, min(len(lines), i + 1 + _EXCEPT_LOOKAHEAD)):
            nxt = lines[j]
            if not nxt.strip():
                continue
            if _indent(nxt) <= base_indent:
                break  # left the except block
            if _SUCCESS_RE.match(nxt):
                offenders.append(
                    (
                        j + 1,
                        f"fail-open handler: `{nxt.strip()}` swallows "
                        f"`{line.strip()}`",
                    )
                )
                break

    # Pattern 2 — `_apply_*filter` that returns the queryset unchanged
    # WITHOUT ever narrowing it (a true no-op filter).
    for i, line in enumerate(lines):
        m = _FILTER_DEF_RE.match(line)
        if not m:
            continue
        fname = m.group(1)
        base_indent = _indent(line)
        j = i + 1
        body: list[tuple[int, str]] = []
        while j < len(lines):
            nxt = lines[j]
            if nxt.strip():
                if _indent(nxt) <= base_indent:
                    break
                body.append((j + 1, nxt))
            j += 1
        bare_returns = [(ln, b) for ln, b in body if _RETURN_QS_RE.match(b)]
        if not bare_returns:
            continue
        if any(_NARROW_RE.search(b) for _, b in body):
            continue  # applies a real filter — not a no-op
        ln, _ = bare_returns[0]
        offenders.append(
            (ln, f"no-op filter `{fname}` returns queryset unchanged")
        )

    return offenders


def load_allowlist(allowlist_path: Path) -> set[str]:
    """Return the set of allowlisted ``relpath:lineno`` keys."""
    if not allowlist_path.exists():
        return set()
    entries: set[str] = set()
    for line in allowlist_path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()  # drop justification
        if line:
            entries.add(line)
    return entries


def iter_py_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for p in sorted(root.rglob("*.py")):
        rel = p.relative_to(root)
        if any(part in _SKIP_DIRS for part in rel.parts):
            continue
        files.append(p)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-open lint (P1-13)")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[2] / "backend"),
        help="Directory to scan (default: repo's backend/).",
    )
    parser.add_argument(
        "--allowlist",
        default=str(Path(__file__).resolve().parent / "failopen-allowlist.txt"),
        help="Allowlist file path.",
    )
    args = parser.parse_args(argv)

    root = Path(args.root)
    allowlist_path = Path(args.allowlist)
    allowed = load_allowlist(allowlist_path)

    # Report paths relative to the repo root (stable across --root values).
    repo_root = Path(__file__).resolve().parents[2]

    failures = 0
    for path in iter_py_files(root):
        try:
            rel = str(path.relative_to(repo_root))
        except ValueError:
            rel = str(path)
        for lineno, message in find_offenders(path):
            key = f"{rel}:{lineno}"
            if key in allowed:
                continue
            print(f"{key}: {message}")
            failures += 1

    if failures:
        print(
            f"\nFail-open lint: {failures} offender(s). "
            f"Fix them or add a JUSTIFIED entry to {allowlist_path}.",
            file=sys.stderr,
        )
        return 1
    print("Fail-open lint: clean (no un-allowlisted offenders).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
