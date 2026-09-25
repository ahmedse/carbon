"""Catalog-first plan author (ADR-0052 · ADR-0057).

The brief claims fields. Catalog ``returns`` cover them. One GET family per
cover, one call per named closed-query enum, one ``export_document`` whose
``columns`` ⊆ those ``returns``. The model does not invent the DAG.
"""
from __future__ import annotations

from typing import Any

from ai.engine.cognition.catalog_retrieval import _tokens
from ai.engine.cognition.plan.contract import _entry_returns, _is_closed_aggregate, _is_measure


def _alias_of(name: str) -> str:
    if name == "count":
        return "headcount"
    if name == "headcount":
        return "count"
    return ""
from ai.engine.cognition.plan.planner import (
    Plan,
    PlanPhase,
    PlanStep,
    _infer_export_format,
)


def _is_read(entry: dict) -> bool:
    kind = str(entry.get("kind") or "")
    if kind in ("write", "request"):
        return False
    if entry.get("requires_confirmation"):
        return False
    method = str(entry.get("method") or "GET").upper()
    return method in ("GET", "HEAD", "OPTIONS")


def _returns(entry: dict | None) -> set[str]:
    return _entry_returns(entry)


def _examples_text(entry: dict) -> str:
    parts: list[str] = []
    raw = entry.get("examples") or []
    if not isinstance(raw, list):
        return ""
    for item in raw:
        if isinstance(item, dict):
            parts.append(str(item.get("ar") or ""))
            parts.append(str(item.get("en") or ""))
        else:
            parts.append(str(item))
    return " ".join(parts)


def _desc_tokens(entry: dict) -> set[str]:
    return _tokens(
        " ".join((
            str(entry.get("name") or ""),
            str(entry.get("label") or ""),
            str(entry.get("description") or ""),
            _examples_text(entry),
        ))
    )


def claimed_fields(brief: str, catalog: list | None) -> set[str]:
    """Return names the brief shares with some catalog ``returns``."""
    tokens = _tokens(brief)
    claimed: set[str] = set()
    for entry in catalog or []:
        if not isinstance(entry, dict):
            continue
        for name in _returns(entry):
            key = name.lower()
            if key in tokens:
                claimed.add(name)
                continue
            if len(key) < 3:
                continue
            for tok in tokens:
                if len(tok) < 3:
                    continue
                if tok.startswith(key) or key.startswith(tok):
                    claimed.add(name)
                    break
    return claimed


def _schema(entry: dict) -> dict:
    raw = entry.get("parameters")
    return raw if isinstance(raw, dict) else {}


def _enum_for(entry: dict, key: str) -> list[str]:
    props = _schema(entry).get("properties") or {}
    spec = props.get(key) if isinstance(props.get(key), dict) else {}
    return [str(item) for item in (spec.get("enum") or []) if str(item).strip()]


def _enum_named(item: str, hay: str, tokens: set[str]) -> bool:
    raw = (item or "").lower()
    spaced = raw.replace("_", " ")
    if raw in tokens or (spaced and f" {spaced} " in hay):
        return True
    parts = [p for p in raw.split("_") if len(p) >= 3]
    if raw.startswith("is_") and len(raw) > 3:
        parts.append(raw[3:])
    if not parts:
        return False
    return all(
        any(tok.startswith(part) or part.startswith(tok) for tok in tokens)
        for part in parts
    )


def _param_values(entry: dict, key: str, brief: str) -> list[str | None]:
    """Closed-query values for ``key``. All enums when the brief names the key."""
    enum = _enum_for(entry, key)
    if not enum:
        return [None]
    tokens = _tokens(brief)
    if key in tokens or f"{key}s" in tokens:
        return list(enum)
    hay = f" {(brief or '').lower().replace('_', ' ')} "
    named = [item for item in enum if _enum_named(item, hay, tokens)]
    return named or list(enum)


def _status_on_cover(cover: dict, donor: dict) -> str:
    """A donor ``status`` enum the covering entry's own text names, if any."""
    enum = _enum_for(donor, "status")
    if not enum:
        return ""
    blob = _tokens(
        f"{cover.get('name') or ''} {cover.get('label') or ''} "
        f"{cover.get('description') or ''}"
    )
    hits = [item for item in enum if item.lower() in blob]
    return hits[0] if len(hits) == 1 else ""


def _hits(returns: set[str], claimed: set[str]) -> set[str]:
    hit = returns & claimed
    for name in claimed:
        alt = _alias_of(name)
        if alt and alt in returns and name not in returns:
            hit.add(alt)
    return hit


def _cover_score(entry: dict, claimed: set[str], brief_tokens: set[str]) -> tuple[int, int]:
    return (len(_hits(_returns(entry), claimed)), len(_desc_tokens(entry) & brief_tokens))


def _covering_families(catalog: list, claimed: set[str], brief: str) -> list[dict]:
    brief_tokens = _tokens(brief)
    ranked = []
    for entry in catalog:
        if not isinstance(entry, dict) or not _is_read(entry):
            continue
        if not _is_closed_aggregate(entry):
            continue
        if not any(_is_measure(n) for n in _hits(_returns(entry), claimed)):
            continue
        ranked.append(entry)
    ranked.sort(key=lambda e: _cover_score(e, claimed, brief_tokens), reverse=True)
    chosen: list[dict] = []
    left = set(claimed)
    covered: set[str] = set()
    for entry in ranked:
        hit = _hits(_returns(entry), left)
        if not hit or hit <= covered:
            continue
        chosen.append(entry)
        covered |= _returns(entry)
        left -= hit
        for name in list(hit):
            left.discard(_alias_of(name))
        if not any(_is_measure(n) for n in left):
            break
    return chosen


def _donor_for(field: str, catalog: list, cover: dict) -> dict | None:
    """A listing GET that declares ``field`` so the cover can bind it."""
    cover_name = str(cover.get("name") or "")
    ranked: list[tuple[int, int, dict]] = []
    for index, entry in enumerate(catalog):
        if not isinstance(entry, dict) or not _is_read(entry):
            continue
        if str(entry.get("name") or "") == cover_name:
            continue
        if field not in _returns(entry):
            continue
        if _is_closed_aggregate(entry):
            continue
        bonus = 1 if str(entry.get("latest_by") or "") == field else 0
        ranked.append((bonus, -index, entry))
    ranked.sort(reverse=True)
    return ranked[0][2] if ranked else None


def _required_unfilled(entry: dict, filled: set[str]) -> list[str]:
    required = [str(k) for k in (_schema(entry).get("required") or [])]
    return [k for k in required if k not in filled]


def compile_catalog_plan(brief: str, catalog: list | None) -> Plan | None:
    """A plan the catalog can author. ``None`` when it cannot — caller may LLM."""
    rows = [e for e in (catalog or []) if isinstance(e, dict) and e.get("name")]
    claimed = claimed_fields(brief, rows)
    if not any(_is_measure(n) for n in claimed):
        return None
    families = _covering_families(rows, claimed, brief)
    if not families:
        return None

    steps: list[PlanStep] = []
    donors: dict[str, int] = {}
    export_deps: list[int] = []
    covered: set[str] = set()

    for family in families:
        filled = set()
        dim_key = "dimension" if _enum_for(family, "dimension") else ""
        values = _param_values(family, dim_key, brief) if dim_key else [None]
        if dim_key:
            filled.add(dim_key)

        bind: dict[str, Any] = {}
        donor_ids: list[int] = []
        for field in _required_unfilled(family, filled):
            donor = _donor_for(field, rows, family)
            if donor is None:
                continue
            name = str(donor.get("name") or "")
            if name not in donors:
                args: dict[str, Any] = {"api_name": name}
                status = _status_on_cover(family, donor)
                if status:
                    args["status"] = status
                sid = len(steps)
                steps.append(PlanStep(
                    sid,
                    str(donor.get("label") or name).replace("_", " "),
                    "call_host_api",
                    args,
                ))
                donors[name] = sid
            donor_ids.append(donors[name])
            spec: dict[str, Any] = {
                "step": donors[name],
                "field": field,
            }
            if str(donor.get("latest_by") or "") == field:
                spec["select"] = "latest"
            bind[field] = spec
            filled.add(field)

        for value in values:
            args = {"api_name": str(family.get("name") or "")}
            if dim_key and value is not None:
                args[dim_key] = value
            if bind:
                args["bind"] = dict(bind)
            sid = len(steps)
            label = str(family.get("label") or family.get("name") or "")
            suffix = f" · {value}" if value else ""
            steps.append(PlanStep(
                sid,
                f"{label}{suffix}",
                "call_host_api",
                args,
                depends_on=list(dict.fromkeys(donor_ids)),
            ))
            export_deps.append(sid)
            covered |= _returns(family)

    columns: list[str] = []
    if "label" in covered:
        columns.append("label")
    for name in sorted((claimed & covered) | _hits(covered, claimed)):
        if name not in columns and _is_measure(name):
            columns.append(name)
    if not any(_is_measure(n) for n in columns):
        return None

    fmt = _infer_export_format(brief)
    title = str(families[0].get("label") or "Report")
    export_id = len(steps)
    steps.append(PlanStep(
        export_id,
        title,
        "export_document",
        {"format": fmt, "title": title, "columns": columns},
        depends_on=list(export_deps),
        is_mutation=True,
    ))
    return Plan(
        pattern="custom",
        steps=steps,
        synthesis_instruction="",
        source="catalog_compile",
        needs_confirmation=True,
        phases=[PlanPhase(
            phase_id=0, name="All steps", goal="",
            strategy="sequential",
            step_ids=[s.step_id for s in steps],
        )],
    )
