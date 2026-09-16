#!/usr/bin/env python3
"""FE dangling-route auditor (RULE_22).

Distinct from ``audit-routes.sh`` (registry/api.md drift vs live Django urls).

Checks:
  1. Every top-level namespace that has nested routes also declares a bare-root
     ``<Route path="/ns" …>`` (index / redirect).
  2. Static production nav targets (``navigate()`` / ``to=`` / ``href=`` / ``path:``)
     resolve to a declared ``<Route path>``.

Ignores: ``__tests__``, ``*.test.*``, ``*.spec.*``, ``apps/stub``, dynamic
segments, and external URLs. Exit 0 = clean; exit 1 = violations on stderr.

Usage:
  ./.ai-toolkit/scripts/audit-routes.py [repo-root]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROUTE_PATH_RE = re.compile(
    r"""<Route\s[^>]*\bpath\s*=\s*["']([^"']+)["']""",
    re.MULTILINE,
)
TARGET_RE = re.compile(
    r"""(?:navigate\s*\(\s*|to\s*=\s*|href\s*=\s*|path\s*:\s*)["'](/?[A-Za-z0-9_./-]*)["']""",
)

SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#")


def _normalize(p: str) -> str:
    p = p.strip()
    if not p.startswith("/"):
        p = "/" + p
    p = p.split("?")[0].split("#")[0]
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p or "/"


def _is_dynamic(p: str) -> bool:
    return ":" in p or "*" in p


def _skip_source(path: Path) -> bool:
    parts = set(path.parts)
    if "__tests__" in parts or "node_modules" in parts or "dist" in parts:
        return True
    name = path.name
    if ".test." in name or ".spec." in name or name.endswith(".stories.jsx"):
        return True
    if "stub" in parts:
        return True
    return False


def _route_matches(declared: set[str], target: str) -> bool:
    t = _normalize(target)
    if t in declared:
        return True
    for r in declared:
        if not _is_dynamic(r):
            continue
        r_parts = r.strip("/").split("/")
        t_parts = t.strip("/").split("/")
        if len(r_parts) != len(t_parts):
            continue
        if all(rp.startswith(":") or rp == tp for rp, tp in zip(r_parts, t_parts)):
            return True
    # splat: /schema-admin/* covers /schema-admin/foo
    for r in declared:
        if r.endswith("/*"):
            prefix = r[:-1]  # keep trailing /
            base = r[:-2]
            if t == base or t.startswith(prefix) or t.startswith(base + "/"):
                return True
    return False


def _collect_routes(app_jsx: Path) -> set[str]:
    text = app_jsx.read_text(encoding="utf-8", errors="ignore")
    return {_normalize(m.group(1)) for m in ROUTE_PATH_RE.finditer(text)}


def _collect_targets(src: Path) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in src.rglob("*"):
        if path.suffix not in {".js", ".jsx", ".ts", ".tsx"}:
            continue
        if _skip_source(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            for m in TARGET_RE.finditer(line):
                raw = m.group(1)
                if not raw or any(raw.startswith(p) for p in SKIP_PREFIXES):
                    continue
                if _is_dynamic(raw) or "${" in raw:
                    continue
                # Require absolute-looking app paths (leading / in source OR multi-seg)
                if not raw.startswith("/") and "/" not in raw:
                    continue
                t = _normalize(raw)
                # Single-segment fake paths from demos are rare after test skip;
                # keep real roots like /help, /feedback, /people.
                found.setdefault(t, []).append(f"{path}:{i}")
    return found


def _namespace_roots(routes: set[str]) -> set[str]:
    roots: set[str] = set()
    for r in routes:
        parts = [p for p in r.split("/") if p and not p.startswith(":")]
        if len(parts) >= 2:
            roots.add("/" + parts[0])
    return roots


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    app = root / "carbon-frontend" / "src" / "App.jsx"
    src = root / "carbon-frontend" / "src"
    if not app.is_file():
        print(f"✗ App.jsx not found: {app}", file=sys.stderr)
        return 1

    routes = _collect_routes(app)
    if not routes:
        print("✗ no <Route path=…> found in App.jsx", file=sys.stderr)
        return 1

    errors: list[str] = []

    for ns in sorted(_namespace_roots(routes)):
        if ns not in routes:
            errors.append(f"missing namespace root index route: {ns}")

    targets = _collect_targets(src)
    for t, locs in sorted(targets.items()):
        if not _route_matches(routes, t):
            sample = ", ".join(
                loc.replace(str(root) + "/", "") for loc in locs[:3]
            )
            errors.append(f"dangling nav target {t!r} (e.g. {sample})")

    if errors:
        print("✗ RULE_22 FE route audit failed:", file=sys.stderr)
        for e in errors[:50]:
            print(f"  - {e}", file=sys.stderr)
        if len(errors) > 50:
            print(f"  … and {len(errors) - 50} more", file=sys.stderr)
        print(
            f"\nDeclared routes: {len(routes)}; unique static nav targets: {len(targets)}",
            file=sys.stderr,
        )
        return 1

    print(
        f"✓ RULE_22 FE routes OK ({len(routes)} routes, {len(targets)} static nav targets)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
