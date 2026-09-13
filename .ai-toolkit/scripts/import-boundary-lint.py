#!/usr/bin/env python3
"""Import-boundary lint (P2-04).

Enforce the engine portability boundary: code under ``backend/ai/engine/`` may
NOT import anything from the Django host layer. The engine must be portable — it
may only import:

  * the engine itself (``ai.engine.*``),
  * the Python standard library, and
  * third-party SDKs (sqlalchemy, openai, anthropic, langchain*, google*,
    pydantic, ...).

For every ``import X`` / ``from X import ...`` in an engine file we extract the
TOP-LEVEL module name (first dot-segment) and flag:

  * top-level ``ai`` whose full module does NOT start with ``ai.engine``
    (host imports such as ``ai.store``, ``ai.models``, ``ai.adapter``,
    ``ai.plugins``, ``ai.envelope_service``, ``ai.instance_registry``,
    ``ai.pdp``, ``ai.command_boundary``, ``ai.workspace``, ``ai.apps``, ...),
  * top-level ``django``.

``from __future__ import ...`` and relative imports (``.module`` / ``..module``)
are ignored. ``sqlalchemy`` is intentionally ALLOWED for now — P2-05 removes it
from the engine in a later task; do NOT flag it (its top-level is neither ``ai``
nor ``django``, so it is classified as an allowed third-party SDK).

Outputs one ``relpath:lineno: imported '<module>'`` line per offender and exits 1
when any offender is not present in the allowlist.

Allowlist format (one entry per line, ``#`` starts the justification)::

    backend/ai/engine/foo.py:12  # justified: ...

Blank lines and ``#`` comment lines are ignored. Line numbers are pinned; when
code shifts, update the entry — or better, fix the code.

Usage::

    .ai-toolkit/scripts/import-boundary-lint.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Directories skipped while walking the engine tree.
_SKIP_DIRS = {"__pycache__"}

_ENGINE_DIR = Path(__file__).resolve().parents[2] / "backend" / "ai" / "engine"
_ALLOWLIST = Path(__file__).resolve().parent / "import-boundary-allowlist.txt"


def _top_level(module: str) -> str:
    """Return the first dot-segment of ``module``."""
    return module.split(".", 1)[0]


def _is_violation(top: str, module: str) -> bool:
    """True when ``module`` (with top-level ``top``) crosses the boundary."""
    if top == "django":
        return True
    if top == "ai" and not module.startswith("ai.engine"):
        return True
    return False


def find_violations(path: Path) -> list[tuple[int, str]]:
    """Return [(lineno, module)] boundary violations in ``path``."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return []
    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                if _is_violation(_top_level(module), module):
                    violations.append((node.lineno, module))
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0 or node.module is None:
                continue  # relative import (`.module` / `..module`) — ignored
            if node.module == "__future__":
                continue
            module = node.module
            if _is_violation(_top_level(module), module):
                violations.append((node.lineno, module))
    return violations


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
    allowed = load_allowlist(_ALLOWLIST)

    failures = 0
    for path in iter_engine_files():
        rel = str(path.relative_to(repo_root))
        for lineno, module in find_violations(path):
            key = f"{rel}:{lineno}"
            if key in allowed:
                continue
            print(f"{key}: imported '{module}'")
            failures += 1

    if failures:
        print(
            f"\nImport boundary: {failures} violation(s) — engine must only "
            f"import engine/stdlib/SDK. Fix them or add a JUSTIFIED entry to "
            f"{_ALLOWLIST}.",
            file=sys.stderr,
        )
        return 1
    print("Import boundary: clean (engine imports only engine/stdlib/SDK)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
