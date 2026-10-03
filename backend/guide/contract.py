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
COMPLETION_KINDS = ("host", "answer", "ack")


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


def _scenario_problems(stage: dict, copies: dict[str, dict], where: str) -> list[str]:
    """Validate one stage's camp drama: beats, ids, choices and both languages."""
    problems: list[str] = []
    beats = (stage.get("scenario") or {}).get("beats") or []
    if len(beats) > engine.SCENARIO_MAX_BEATS:
        problems.append(f"{where}: a scenario has at most {engine.SCENARIO_MAX_BEATS} beats")
    seen_ids: set = set()
    for index, beat in enumerate(beats):
        at = f"{where}.scenario[{index}]"
        bid = beat.get("id")
        if not bid or bid in seen_ids:
            problems.append(f"{at}: beat id must be unique and present")
        seen_ids.add(bid)
        correct = beat.get("correct")
        if isinstance(correct, bool) or not isinstance(correct, int) or correct < 0:
            problems.append(f"{at}: correct must be a non-negative integer")
        for lang, copy in copies.items():
            stage_copy = (copy.get("stages") or {}).get(stage.get("key")) or {}
            beat_copy = next(
                (
                    row
                    for row in ((stage_copy.get("scenario") or {}).get("beats") or [])
                    if isinstance(row, dict) and row.get("id") == bid
                ),
                None,
            )
            if not beat_copy:
                problems.append(f"{at}: {lang} copy is missing the beat")
                continue
            for field in ("cast", "line", "question", "explain"):
                if not str(beat_copy.get(field) or "").strip():
                    problems.append(f"{at}: {lang} copy is missing {field}")
            choices = beat_copy.get("choices") or []
            if len(choices) < 2:
                problems.append(f"{at}: {lang} copy needs at least two choices")
            elif not isinstance(correct, bool) and isinstance(correct, int) and not 0 <= correct < len(choices):
                problems.append(f"{at}: correct is out of range for the {lang} choices")
    return problems


def _journey_problems(pack_id: str, loaded: dict, copies: dict[str, dict]) -> list[str]:
    """Validate the engine-read journey blocks: stages, competencies, steps.

    Domain-free: this reads shape and copy only, never a host object. A pack
    that passes here is usable by the engine with zero engine edits.
    """
    problems: list[str] = []
    lessons = loaded["lessons"]
    known_lessons = {row["id"] for row in lessons}
    stages = loaded.get("stages") or []
    competencies = loaded.get("competencies") or []
    comp_keys = {row.get("key") for row in competencies}

    seen_n: set = set()
    seen_key: set = set()
    for row in stages:
        n = row.get("n")
        key = row.get("key")
        where = f"{pack_id}.stage[{n}]"
        if n in seen_n:
            problems.append(f"{where}: duplicate stage n")
        seen_n.add(n)
        if not key or key in seen_key:
            problems.append(f"{where}: stage key must be unique and present")
        seen_key.add(key)
        members = list(row.get("lessons") or [])
        for lesson_id in members:
            if lesson_id not in known_lessons:
                problems.append(f"{where}: unknown lesson {lesson_id}")
        for comp_key in row.get("competencies") or []:
            if competencies and comp_key not in comp_keys:
                problems.append(f"{where}: unknown competency {comp_key}")
        if row.get("pending") and members:
            problems.append(f"{where}: a pending stage lists lessons")
        problems += _scenario_problems(row, copies, where)

    seen_c: set = set()
    for row in competencies:
        key = row.get("key")
        where = f"{pack_id}.competency[{key}]"
        if not key or key in seen_c:
            problems.append(f"{where}: competency key must be unique and present")
        seen_c.add(key)
        kind = row.get("kind")
        if kind not in COMPLETION_KINDS:
            problems.append(f"{where}: kind must be host, answer or ack")
        if row.get("lesson") and row["lesson"] not in known_lessons:
            problems.append(f"{where}: unknown lesson {row['lesson']}")
        if kind == "host":
            if not row.get("probe"):
                problems.append(f"{where}: a host competency needs a probe")
            elif registry.find(pack_id, "host", row["probe"]) is None:
                problems.append(f"{where}: host probe {row['probe']} is not registered")
        for lang, copy in copies.items():
            text = (copy.get("competencies") or {}).get(key)
            if not text or not str(text.get("title") or "").strip():
                problems.append(f"{where}: {lang} copy is missing title")

    for row in lessons:
        lid = row["id"]
        where = f"{pack_id}.{lid}"
        spec_steps = row.get("steps") or []
        completion = row.get("completion")
        if completion and completion not in COMPLETION_KINDS:
            problems.append(f"{where}: completion must be host, answer or ack")
        for index, step in enumerate(spec_steps):
            if not isinstance(step, dict) or not step.get("route"):
                problems.append(f"{where}.steps[{index}]: needs a route")
        for lang, copy in copies.items():
            text = (copy.get("lessons") or {}).get(lid) or {}
            step_copy = text.get("steps") or []
            if spec_steps and len(step_copy) != len(spec_steps):
                problems.append(f"{where}: {lang} copy needs {len(spec_steps)} step scripts")
            for index, step in enumerate(step_copy):
                if not str((step or {}).get("title") or "").strip():
                    problems.append(f"{where}.steps[{index}]: {lang} copy is missing a title")
                if not str((step or {}).get("do") or "").strip():
                    problems.append(f"{where}.steps[{index}]: {lang} copy is missing a do line")

    glossary = (loaded.get("journey") or {}).get("glossary") or []
    if not isinstance(glossary, list) or any(
        not isinstance(term, str) or not term.strip() for term in glossary
    ):
        problems.append(f"{pack_id}.journey: glossary must be a list of non-empty terms")
    return problems


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
    problems += _journey_problems(pack_id, loaded, copies)
    return problems


def check_all() -> list[str]:
    known = _known_capabilities()
    problems: list[str] = []
    for pack_id in pack_ids():
        problems += check_pack(pack_id, known)
    return problems
