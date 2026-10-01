"""Pack contract for guide packs. ``python manage.py guide_check`` exits non-zero on any problem.

Checks, per pack that has ``guide/guide.yaml``:
  - lesson ids and priorities are unique across the platform pack and the pack
  - track, phase, version are well formed; gathering lessons sort before closing lessons
  - every probe a lesson names is registered
  - every capability key exists in the host's capability table
  - English and Arabic copy exist for each lesson, with the option count a quiz needs
  - no kilogram-like key in a live payload is checked in tests, where probes run on data
"""
from __future__ import annotations

from guide import engine, packs, registry

COPY_KEYS = ("title", "know", "do", "dont", "question", "explain")


def _known_capabilities() -> set[str]:
    from accounts.capabilities import GROUP_CAPABILITIES

    known: set[str] = set()
    for caps in GROUP_CAPABILITIES.values():
        known |= {str(c) for c in caps}
    return known


def pack_ids() -> list[str]:
    if not packs.PACKS_ROOT.is_dir():
        return []
    return sorted(p.name for p in packs.PACKS_ROOT.iterdir() if (p / "guide" / "guide.yaml").is_file())


def check_pack(pack_id: str, known_caps: set[str]) -> list[str]:
    problems: list[str] = []
    loaded = packs.load_pack(pack_id)
    lessons = loaded["lessons"]
    platform = packs.load_pack(registry.PLATFORM)["lessons"] if pack_id != registry.PLATFORM else []
    ids = [row["id"] for row in platform + lessons]
    if len(ids) != len(set(ids)):
        problems.append(f"{pack_id}: duplicate lesson ids")
    priorities = [row["priority"] for row in platform + lessons]
    if len(priorities) != len(set(priorities)):
        problems.append(f"{pack_id}: duplicate priorities")
    gather = [r["priority"] for r in lessons if r.get("phase") == "gather"]
    close = [r["priority"] for r in lessons if r.get("phase") == "close"]
    if gather and close and max(gather) > min(close):
        problems.append(f"{pack_id}: a closing lesson sorts before a gathering lesson")
    copies = {lang: packs.copy_for(pack_id, lang) for lang in packs.LANGUAGES}
    for row in lessons:
        lid = row["id"]
        where = f"{pack_id}.{lid}"
        if row.get("track") not in engine.TRACKS:
            problems.append(f"{where}: unknown track {row.get('track')!r}")
        if row.get("phase") not in ("gather", "close"):
            problems.append(f"{where}: phase must be gather or close")
        if not isinstance(row.get("version"), int):
            problems.append(f"{where}: version must be an integer")
        for key in (row.get("any") or []) + (row.get("all") or []) + ([row["scope_cap"]] if row.get("scope_cap") else []):
            if key not in known_caps:
                problems.append(f"{where}: unknown capability {key}")
        wanted = [("need", n) for n in row.get("needs") or []]
        if row.get("host"):
            wanted.append(("host", row["host"]))
        if row.get("live"):
            wanted.append(("live", row["live"]))
        spec = row.get("question") or {}
        qkind = spec.get("kind")
        if qkind == "probe":
            wanted.append(("question", spec.get("name")))
        elif qkind == "host":
            if not row.get("host"):
                problems.append(f"{where}: a host check needs a host probe")
        elif qkind != "static":
            problems.append(f"{where}: question kind must be static, probe, or host")
        for kind, name in wanted:
            if registry.find(pack_id, kind, name) is None:
                problems.append(f"{where}: probe {kind}.{name} is not registered")
        options = int(spec.get("options") or (0 if qkind == "host" else 3))
        copy_keys = ("title", "know", "do", "dont", "question") if qkind == "host" else COPY_KEYS
        for lang, copy in copies.items():
            text = (copy.get("lessons") or {}).get(lid)
            if not text:
                problems.append(f"{where}: no {lang} copy")
                continue
            for key in copy_keys:
                if not str(text.get(key) or "").strip():
                    problems.append(f"{where}: {lang} copy is missing {key}")
            if qkind != "host" and len(text.get("options") or []) != options:
                problems.append(f"{where}: {lang} copy needs {options} options")
        if qkind == "static" and not 0 <= int(spec.get("correct", -1)) < options:
            problems.append(f"{where}: correct index out of range")
    return problems


def check_all() -> list[str]:
    known = _known_capabilities()
    problems: list[str] = []
    for pack_id in pack_ids():
        problems += check_pack(pack_id, known)
    return problems
