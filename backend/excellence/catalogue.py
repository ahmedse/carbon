"""Ladder catalogue: tiers, tracks, subjects, checks — loaded from YAML.

Git is the SSOT (ADR-0051 §3). Platform and Pulse tiers live in
``assurance/<tier>/ladder.yaml`` + ``assurance/<tier>/tracks/<track>.yaml``;
domain apps in ``domain_packs/<id>/assurance/``. Platform checks are inherited
by every tier and cannot be lowered — a tier may only add checks.

Subjects are declared, never derived from the tree (ADR-0020 denominator rule).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSURANCE_ROOT = REPO_ROOT / "assurance"
DOMAIN_PACKS_ROOT = REPO_ROOT / "domain_packs"

PLATFORM_TIER = "platform"

SUBJECT_KINDS: frozenset[str] = frozenset(
    {"module", "process", "journey", "dataset", "artifact", "ai_pack"}
)
DIMENSIONS: tuple[str, ...] = (
    "specified", "correct", "secure", "reliable", "performant",
    "usable", "maintainable", "observed", "governed",
)
LEVEL_NAMES: tuple[str, ...] = (
    "Unmanaged", "Declared", "Specified", "Built", "Proven", "Operated", "Excellent",
)
MAX_LEVEL = len(LEVEL_NAMES) - 1  # L6


@dataclass(frozen=True)
class Check:
    id: str
    title: str
    dimension: str
    rank: int
    collector: str
    probe: dict[str, Any] = field(default_factory=dict)
    applies_to: frozenset[str] = frozenset(SUBJECT_KINDS)
    solution: str = ""
    source: str = ""
    tier: str = PLATFORM_TIER
    track: str = ""

    def applies(self, subject: "Subject") -> bool:
        if subject.kind not in self.applies_to:
            return False
        only = self.probe.get("subjects")
        if isinstance(only, list) and only:
            return subject.id in only
        return True


@dataclass(frozen=True)
class Subject:
    id: str
    kind: str
    title: str
    tier: str
    track: str = ""
    owner: str = ""
    paths: tuple[str, ...] = ()
    tests: tuple[str, ...] = ()
    spec: tuple[str, ...] = ()
    adr: tuple[str, ...] = ()
    runbook: tuple[str, ...] = ()
    ci: tuple[str, ...] = ()
    process: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Track:
    id: str
    tier: str
    title: str
    owner: str = ""


@dataclass(frozen=True)
class Tier:
    id: str
    title: str
    owner: str = ""
    level_names: tuple[str, ...] = LEVEL_NAMES


@dataclass
class Catalogue:
    tiers: dict[str, Tier] = field(default_factory=dict)
    tracks: dict[tuple[str, str], Track] = field(default_factory=dict)
    subjects: dict[str, Subject] = field(default_factory=dict)
    checks: dict[str, Check] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    def checks_for(self, subject: Subject) -> list[Check]:
        """Platform checks + the subject's tier checks + its track checks."""
        out: list[Check] = []
        for c in self.checks.values():
            in_scope = (
                c.tier == PLATFORM_TIER and c.track == ""
                or (c.tier == subject.tier and c.track in ("", subject.track))
            )
            if in_scope and c.applies(subject):
                out.append(c)
        return sorted(out, key=lambda c: (c.rank, c.dimension, c.id))

    def subjects_in(self, tier: str | None = None, track: str | None = None) -> list[Subject]:
        rows = list(self.subjects.values())
        if tier:
            rows = [s for s in rows if s.tier == tier]
        if track:
            rows = [s for s in rows if s.track == track]
        return sorted(rows, key=lambda s: (s.tier, s.track, s.id))


# ── Loading ────────────────────────────────────────────────────────────────


def _where(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:  # noqa: PERF203 - one file
        raise ValueError(f"{path}: {exc}") from exc
    return data if isinstance(data, dict) else {}


def _tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        return tuple(str(v) for v in value if v is not None)
    return ()


def _parse_check(raw: dict[str, Any], *, tier: str, track: str, problems: list[str], where: str) -> Check | None:
    cid = str(raw.get("id") or "").strip()
    if not cid:
        problems.append(f"{where}: check without id")
        return None
    dim = str(raw.get("dimension") or "").strip()
    if dim not in DIMENSIONS:
        problems.append(f"{where}: check {cid} dimension {dim!r} not in {DIMENSIONS}")
        return None
    try:
        rank = int(raw.get("rank"))
    except (TypeError, ValueError):
        problems.append(f"{where}: check {cid} rank must be an integer")
        return None
    if not 1 <= rank <= MAX_LEVEL:
        problems.append(f"{where}: check {cid} rank {rank} outside 1..{MAX_LEVEL}")
        return None
    applies = raw.get("applies_to")
    kinds = frozenset(_tuple(applies)) if applies else frozenset(SUBJECT_KINDS)
    bad = kinds - SUBJECT_KINDS
    if bad:
        problems.append(f"{where}: check {cid} applies_to unknown kinds {sorted(bad)}")
        return None
    probe = raw.get("probe") if isinstance(raw.get("probe"), dict) else {}
    return Check(
        id=cid,
        title=str(raw.get("title") or cid),
        dimension=dim,
        rank=rank,
        collector=str(raw.get("collector") or "repo"),
        probe=dict(probe),
        applies_to=kinds,
        solution=str(raw.get("solution") or ""),
        source=str(raw.get("source") or ""),
        tier=tier,
        track=track,
    )


def _parse_subject(raw: dict[str, Any], *, tier: str, track: str, problems: list[str], where: str) -> Subject | None:
    sid = str(raw.get("id") or "").strip()
    if not sid:
        problems.append(f"{where}: subject without id")
        return None
    kind = str(raw.get("kind") or "").strip()
    if kind not in SUBJECT_KINDS:
        problems.append(f"{where}: subject {sid} kind {kind!r} not in {sorted(SUBJECT_KINDS)}")
        return None
    known = {"id", "kind", "title", "owner", "paths", "tests", "spec", "adr", "runbook", "ci", "process"}
    return Subject(
        id=sid,
        kind=kind,
        title=str(raw.get("title") or sid),
        tier=tier,
        track=track,
        owner=str(raw.get("owner") or ""),
        paths=_tuple(raw.get("paths")),
        tests=_tuple(raw.get("tests")),
        spec=_tuple(raw.get("spec")),
        adr=_tuple(raw.get("adr")),
        runbook=_tuple(raw.get("runbook")),
        ci=_tuple(raw.get("ci")),
        process=str(raw.get("process") or ""),
        extra={k: v for k, v in raw.items() if k not in known},
    )


def _ingest(cat: Catalogue, data: dict[str, Any], *, tier: str, track: str, where: str) -> None:
    for raw in data.get("subjects") or []:
        if not isinstance(raw, dict):
            continue
        s = _parse_subject(raw, tier=tier, track=track, problems=cat.problems, where=where)
        if s is None:
            continue
        if s.id in cat.subjects:
            cat.problems.append(f"{where}: duplicate subject id {s.id}")
            continue
        cat.subjects[s.id] = s
    for raw in data.get("checks") or []:
        if not isinstance(raw, dict):
            continue
        c = _parse_check(raw, tier=tier, track=track, problems=cat.problems, where=where)
        if c is None:
            continue
        if c.id in cat.checks:
            cat.problems.append(f"{where}: duplicate check id {c.id}")
            continue
        cat.checks[c.id] = c


def _load_tier_dir(cat: Catalogue, tier_dir: Path, *, tier_id_hint: str) -> None:
    ladder = tier_dir / "ladder.yaml"
    if not ladder.is_file():
        return
    data = _read_yaml(ladder)
    tier_id = str(data.get("tier") or tier_id_hint).strip()
    if tier_id != tier_id_hint:
        cat.problems.append(f"{ladder}: tier {tier_id!r} does not match directory {tier_id_hint!r}")
    if tier_id in cat.tiers:
        cat.problems.append(f"{ladder}: duplicate tier {tier_id}")
        return
    names = _tuple(data.get("level_names"))
    if names and len(names) != len(LEVEL_NAMES):
        cat.problems.append(f"{ladder}: level_names must have {len(LEVEL_NAMES)} entries (rename, not reorder)")
        names = ()
    cat.tiers[tier_id] = Tier(
        id=tier_id,
        title=str(data.get("title") or tier_id),
        owner=str(data.get("owner") or ""),
        level_names=names or LEVEL_NAMES,
    )
    _ingest(cat, data, tier=tier_id, track="", where=_where(ladder))
    tracks_dir = tier_dir / "tracks"
    if tracks_dir.is_dir():
        for path in sorted(tracks_dir.glob("*.yaml")):
            tdata = _read_yaml(path)
            track_id = str(tdata.get("track") or path.stem).strip()
            if track_id != path.stem:
                cat.problems.append(f"{path}: track {track_id!r} does not match file name {path.stem!r}")
            cat.tracks[(tier_id, track_id)] = Track(
                id=track_id,
                tier=tier_id,
                title=str(tdata.get("title") or track_id),
                owner=str(tdata.get("owner") or ""),
            )
            _ingest(cat, tdata, tier=tier_id, track=track_id, where=_where(path))


def load_catalogue(
    assurance_root: Path = ASSURANCE_ROOT,
    domain_packs_root: Path = DOMAIN_PACKS_ROOT,
) -> Catalogue:
    cat = Catalogue()
    if assurance_root.is_dir():
        for tier_dir in sorted(p for p in assurance_root.iterdir() if p.is_dir()):
            _load_tier_dir(cat, tier_dir, tier_id_hint=tier_dir.name)
    if domain_packs_root.is_dir():
        for pack_dir in sorted(p for p in domain_packs_root.iterdir() if p.is_dir()):
            _load_tier_dir(cat, pack_dir / "assurance", tier_id_hint=pack_dir.name)
    if PLATFORM_TIER not in cat.tiers:
        cat.problems.append("no platform tier: assurance/platform/ladder.yaml is required")
    _validate_paths(cat)
    return cat


def _validate_paths(cat: Catalogue) -> None:
    """Declared paths must exist. A manifest that points at nothing is a claim."""
    for s in cat.subjects.values():
        for p in (*s.paths, *s.tests, *s.spec, *s.adr, *s.runbook, *s.ci):
            if not (REPO_ROOT / p).exists():
                cat.problems.append(f"subject {s.id}: declared path {p} does not exist")


def check_ids(checks: Iterable[Check]) -> list[str]:
    return [c.id for c in checks]
