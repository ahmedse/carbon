"""Domain pack contract gate (ADR-0050).

Pulse core is domain-free; every domain lives in a self-contained, versioned
pack under ``domain_packs/<id>/``. This gate checks the shape the engine
relies on so a pack can be swapped, versioned or added without touching core:

* ``pack.yaml`` exists with ``id`` (== directory name), integer ``version`` ≥ 1,
  ``domain``, ``instance`` (a path that exists) and ``compat.engine``;
* every path under ``owns:`` exists inside the pack (self-contained: a pack
  may not point outside itself, except ``banks`` which name eval evidence);
* no two packs share an ``id``.

CLI::

    python -m ai.eval.pack_contract          # print a table
    python -m ai.eval.pack_contract --gate   # exit 1 on any violation
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
DOMAIN_PACKS_ROOT = REPO_ROOT / "domain_packs"

_REQUIRED = ("id", "version", "domain", "instance", "compat")
#: ``owns`` keys allowed to reference files outside the pack directory.
_EXTERNAL_OK = frozenset({"banks"})


def _load_manifest(pack_dir: Path) -> dict[str, Any] | None:
    path = pack_dir / "pack.yaml"
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _check_owned_paths(pack_dir: Path, owns: Any, violations: list[str], pack: str) -> None:
    if owns is None:
        return
    if not isinstance(owns, dict):
        violations.append(f"{pack}: owns must be a mapping")
        return
    for key, value in owns.items():
        targets = value.values() if isinstance(value, dict) else [value]
        for raw in targets:
            if not isinstance(raw, str) or not raw.strip():
                violations.append(f"{pack}: owns.{key} has an empty path")
                continue
            rel = raw.strip()
            if key in _EXTERNAL_OK:
                target = REPO_ROOT / rel
            else:
                if rel.startswith(("/", "..")) or "/../" in rel:
                    violations.append(f"{pack}: owns.{key} points outside the pack ({rel})")
                    continue
                target = pack_dir / rel
            if not target.exists():
                violations.append(f"{pack}: owns.{key} missing ({rel})")


def check_pack(pack_dir: Path) -> tuple[dict[str, Any], list[str]]:
    pack = pack_dir.name
    violations: list[str] = []
    manifest = _load_manifest(pack_dir)
    if manifest is None:
        return {}, [f"{pack}: pack.yaml missing"]
    if not manifest:
        return {}, [f"{pack}: pack.yaml unreadable or empty"]
    for key in _REQUIRED:
        if key not in manifest:
            violations.append(f"{pack}: pack.yaml missing `{key}`")
    if str(manifest.get("id") or "").strip().lower() != pack.lower():
        violations.append(f"{pack}: id `{manifest.get('id')}` must equal directory name")
    version = manifest.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        violations.append(f"{pack}: version must be an integer ≥ 1 (got {version!r})")
    instance = manifest.get("instance")
    if isinstance(instance, str) and instance.strip():
        if not (REPO_ROOT / instance.strip()).is_file():
            violations.append(f"{pack}: instance file missing ({instance})")
    compat = manifest.get("compat")
    if not isinstance(compat, dict) or not str(compat.get("engine") or "").strip():
        violations.append(f"{pack}: compat.engine required")
    _check_owned_paths(pack_dir, manifest.get("owns"), violations, pack)
    if isinstance(instance, str) and (REPO_ROOT / instance.strip()).is_file():
        violations.extend(
            f"{pack}: {msg}" for msg in tool_reference_violations(REPO_ROOT / instance.strip())
        )
    return manifest, violations


def _registry_tool_names() -> set[str]:
    """Engine tools the pack does not own (static + flag-gated capabilities)."""
    try:
        from ai.engine.agent import tools as registry
    except Exception:  # noqa: BLE001 — the catalog check still runs
        return set()
    defs = list(getattr(registry, "STATIC_TOOL_DEFINITIONS", []) or [])
    for attr in ("_ECF_RESOLVE_ENTITY_DEFINITION", "_ECF_AGGREGATE_ENTITY_DEFINITION"):
        if isinstance(getattr(registry, attr, None), dict):
            defs.append(getattr(registry, attr))
    return {
        str(((d or {}).get("function") or {}).get("name") or "")
        for d in defs
    } - {""}


def _tokens(text: str) -> set[str]:
    out: set[str] = set()
    buf: list[str] = []
    for ch in f"{text} ":
        if ch.isalnum() or ch == "_":
            buf.append(ch)
        elif buf:
            out.add("".join(buf))
            buf = []
    return out


def _entry_text(entry: dict) -> str:
    parts = [str(entry.get(k) or "") for k in ("description", "not_for")]
    for ex in entry.get("examples") or []:
        parts.append(" ".join(str(v) for v in ex.values()) if isinstance(ex, dict) else str(ex))
    return " ".join(parts)


def tool_reference_violations(instance_path: Path) -> list[str]:
    """Prompt text may only name tools its reader can call (ADR-0049 §9).

    * Identity prose (``persona``, ``guidance_by_audience``) names no tool:
      it is shown to every audience, and routing belongs on the tool.
    * Catalog text names only catalog entries every one of its readers can
      see. Engine tools describe themselves; a pack cannot know whether a
      flag-gated engine tool is on, so it never points at one.
    """
    from ai.engine.cognition.context_pack import entry_audience

    try:
        doc = yaml.safe_load(instance_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return [f"{instance_path.name} unreadable"]
    catalog = [e for e in doc.get("api_catalog") or [] if isinstance(e, dict) and e.get("name")]
    audience_of = {str(e["name"]): set(entry_audience(e)) for e in catalog}
    registry = _registry_tool_names() - set(audience_of)
    known = set(audience_of) | registry
    out: list[str] = []

    identity = {"persona": doc.get("persona")}
    guidance = doc.get("guidance_by_audience")
    if isinstance(guidance, dict):
        identity.update({f"guidance_by_audience.{k}": v for k, v in guidance.items()})
    for where, text in identity.items():
        named = sorted(_tokens(str(text or "")) & known)
        if named:
            out.append(f"{where} names tools {named}; put routing on the tool entry")

    for entry in catalog:
        name = str(entry["name"])
        readers = audience_of[name]
        for other in sorted(_tokens(_entry_text(entry)) & known - {name}):
            if other in registry:
                out.append(f"api_catalog.{name} names engine tool {other}")
            elif not readers <= audience_of[other]:
                missing = sorted(readers - audience_of[other])
                out.append(f"api_catalog.{name} names {other}, hidden from {missing}")
    return out


def check_all(root: Path = DOMAIN_PACKS_ROOT) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    violations: list[str] = []
    seen: dict[str, str] = {}
    if not root.is_dir():
        return rows, [f"domain_packs root missing: {root}"]
    for pack_dir in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        manifest, errs = check_pack(pack_dir)
        violations.extend(errs)
        pid = str(manifest.get("id") or pack_dir.name)
        if pid in seen:
            violations.append(f"duplicate pack id `{pid}` ({seen[pid]}, {pack_dir.name})")
        seen[pid] = pack_dir.name
        rows.append({
            "id": pid,
            "version": manifest.get("version"),
            "domain": manifest.get("domain"),
            "instance_ok": bool(manifest.get("instance")) and (REPO_ROOT / str(manifest.get("instance"))).is_file(),
            "violations": len(errs),
        })
    return rows, violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Domain pack contract gate (ADR-0050)")
    parser.add_argument("--gate", action="store_true", help="exit 1 on any violation")
    args = parser.parse_args(argv)
    rows, violations = check_all()
    for row in rows:
        print(f"{row['id']:10s} v{row['version']!s:<4} {str(row['domain']):12s} instance={'ok' if row['instance_ok'] else 'MISSING'} violations={row['violations']}")
    for msg in violations:
        print(f"PACK: {msg}", file=sys.stderr)
    if args.gate and violations:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
