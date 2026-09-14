#!/usr/bin/env python3
"""Forbidden-domain-term lint (P2-08 acceptance gate).

The engine (``backend/ai/engine/``) must be DOMAIN-AGNOSTIC. Carbon/DQ/GHG
vocabulary belongs in ``domain_packs/carbon/*``, loaded via the ``DomainPack``
port. This script scans engine sources for the literal terms listed in
``forbidden-terms.txt`` and fails on any non-allowlisted hit.

Matching is word-boundary based and case-sensitive: a term matches a line only
when it is NOT immediately preceded or followed by a word character
(``[A-Za-z0-9_]``). This avoids false positives such as ``carbon`` inside
``PULSE_CARBON_CONTEXT_ENABLED`` (``_`` is a word char) — which is why that
constant is listed as its own term.

Outputs one ``relpath:lineno: term '<term>'`` line per offender and exits 1 when
any offender is not present in the allowlist.

Allowlist format (one entry per line, ``#`` starts the justification)::

    backend/ai/engine/foo.py:12  # justified: generic fallback value

Blank lines and ``#`` comment lines are ignored. Line numbers are pinned; when
code shifts, update the entry — or better, fix the code.

Usage::

    .ai-toolkit/scripts/forbidden-term-lint.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Directories skipped while walking the engine tree.
_SKIP_DIRS = {"__pycache__"}

_ENGINE_DIR = Path(__file__).resolve().parents[2] / "backend" / "ai" / "engine"
_TERMS_PATH = Path(__file__).resolve().parent / "forbidden-terms.txt"
_ALLOWLIST = Path(__file__).resolve().parent / "forbidden-terms-allowlist.txt"

_WORD_CHAR = re.compile(r"\w")


def load_terms(terms_path: Path) -> list[str]:
    """Return the list of forbidden terms (comments + blanks stripped)."""
    if not terms_path.exists():
        return []
    terms: list[str] = []
    for line in terms_path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            terms.append(line)
    return terms


def _pattern(term: str) -> re.Pattern[str]:
    """Build a word-boundary regex for ``term``.

    Only apply ``\\b``-style boundaries on edges that are word characters, so
    terms with leading/trailing punctuation match literally.
    """
    prefix = r"(?<!\w)" if term and _WORD_CHAR.match(term[0]) else ""
    suffix = r"(?!\w)" if term and _WORD_CHAR.match(term[-1]) else ""
    return re.compile(prefix + re.escape(term) + suffix)


def find_hits(path: Path, terms: list[str], patterns: list[re.Pattern[str]]) -> list[tuple[int, str]]:
    """Return [(lineno, term)] forbidden-term hits in ``path``."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hits: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for term, pat in zip(terms, patterns):
            if pat.search(line):
                hits.append((lineno, term))
    return hits


def load_allowlist(allowlist_path: Path) -> set[str]:
    """Return the set of allowlisted ``relpath:lineno`` keys."""
    if not allowlist_path.exists():
        return set()
    entries: set[str] = set()
    for line in allowlist_path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            entries.add(line)
    return entries


def iter_engine_files() -> list[Path]:
    """Return the ``*.py`` files under ``backend/ai/engine/``."""
    files: list[Path] = []
    for p in sorted(_ENGINE_DIR.rglob("*.py")):
        rel = p.relative_to(_ENGINE_DIR)
        if any(part in _SKIP_DIRS for part in rel.parts):
            continue
        files.append(p)
    return files


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    terms = load_terms(_TERMS_PATH)
    patterns = [_pattern(t) for t in terms]
    allowed = load_allowlist(_ALLOWLIST)

    failures = 0
    for path in iter_engine_files():
        rel = str(path.relative_to(repo_root))
        for lineno, term in find_hits(path, terms, patterns):
            key = f"{rel}:{lineno}"
            if key in allowed:
                continue
            print(f"{key}: term '{term}'")
            failures += 1

    if failures:
        print(
            f"\nForbidden domain term: {failures} hit(s) — engine must be "
            f"domain-agnostic. Move the vocabulary into domain_packs/ and load "
            f"via the DomainPack port, or add a JUSTIFIED entry to {_ALLOWLIST}.",
            file=sys.stderr,
        )
        return 1
    print("Forbidden domain term: clean (engine is domain-agnostic)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
