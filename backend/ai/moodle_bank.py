"""Passage bank for one listed course. Not imported by engine/.

C3 passages are page, label, and book text. The id is
``shortname:kind:activity``. File and video rows are not C3.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import yaml

MISS = "This is not in this lecture."
_C3_KINDS = ("page", "label", "book")
_PACK = Path(__file__).resolve().parents[2] / "domain_packs" / "aast-med" / "bank"
_ROOT = _PACK / "course-meat-13"
_KEYS = _PACK / "course-keys-13"
_EXT = _PACK / "course-ext-13"


def passage_id(shortname: str, kind: str, activity_id: int) -> str:
    return f"{shortname}:{kind}:{int(activity_id)}"


def load_c3(shortname: str, root: Path | None = None) -> dict[str, dict]:
    """Passages for one course. A row without an activity id is skipped."""
    path = (root or _ROOT) / f"{shortname}.jsonl"
    out: dict[str, dict] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if str(row.get("course") or "") != shortname:
            continue
        kind = str(row.get("kind") or "")
        if kind not in _C3_KINDS:
            continue
        activity = _activity_id(row)
        text = str(row.get("text") or "").strip()
        if activity is None or not text:
            continue
        pid = passage_id(shortname, kind, activity)
        out[pid] = {
            "id": pid,
            "course": shortname,
            "kind": kind,
            "activity_id": activity,
            "name": str(row.get("name") or ""),
            "text": text,
            "visible": bool(row.get("visible", True)),
            "world": listed_world(shortname),
        }
    return out


def passages_for(shortname: str, activity_id: int, bank: dict[str, dict] | None = None) -> list[dict]:
    rows = bank if bank is not None else load_c3(shortname)
    return [row for row in rows.values() if row["activity_id"] == int(activity_id) and row["course"] == shortname]


def load_c4_files(shortname: str, meat_root: Path | None = None, keys_root: Path | None = None) -> dict[str, dict]:
    """Local resource files for one course.

    A row with no activity id is skipped. URL and Google rows are skipped:
    their text is the Moodle intro, not a Drive body.
    """
    meat_path = (meat_root or _ROOT) / f"{shortname}.jsonl"
    keys_path = (keys_root or _KEYS) / f"{shortname}.jsonl"
    if not meat_path.is_file() or not keys_path.is_file():
        return {}
    keys: dict[tuple, dict] = {}
    for row in _rows(keys_path):
        if row.get("kind") != "file" or not row.get("cmid"):
            continue
        keys.setdefault(_join_key(row), row)
    out: dict[str, dict] = {}
    for row in _rows(meat_path):
        if str(row.get("course") or "") != shortname or row.get("kind") != "file":
            continue
        key = keys.get(_join_key(row))
        if key is None:
            continue
        ref = str(row.get("ref") or "")
        filename = ref.removeprefix("file:")
        text = str(row.get("text") or "").strip()
        if not filename or len(text) <= len(filename):
            continue
        activity = int(key["cmid"])
        pid = f"{shortname}:file:{activity}:{filename}"
        out[pid] = {
            "id": pid,
            "course": shortname,
            "kind": "file",
            "activity_id": activity,
            "source": ref,
            "name": str(row.get("name") or ""),
            "text": text,
            "world": listed_world(shortname),
        }
    return out


def load_c4_drive(shortname: str, ext_root: Path | None = None) -> dict[str, dict]:
    """Drive bodies already stored for one course.

    Empty and unavailable rows stay out. Moodle intro is never the body.
    A Chat turn does not call Google.
    """
    return _load_ext(shortname, family="google", kind="google", ext_root=ext_root)


def load_c5_youtube(shortname: str, ext_root: Path | None = None) -> dict[str, dict]:
    """YouTube captions already stored for one course.

    An explicit empty caption is not a passage. The video file is not stored.
    A Chat turn does not call YouTube.
    """
    return _load_ext(shortname, family="youtube", kind="youtube", ext_root=ext_root)


def load_external(shortname: str, ext_root: Path | None = None) -> dict[str, dict]:
    """Drive bodies and captions for one course. Not file meat."""
    return {**load_c4_drive(shortname, ext_root), **load_c5_youtube(shortname, ext_root)}


def _load_ext(shortname: str, *, family: str, kind: str, ext_root: Path | None) -> dict[str, dict]:
    path = (ext_root or _EXT) / f"{shortname}.jsonl"
    out: dict[str, dict] = {}
    if not path.is_file():
        return out
    for row in _rows(path):
        if str(row.get("course") or "") != shortname:
            continue
        if row.get("family") != family or row.get("status") != "ok":
            continue
        if str(row.get("source_kind") or "").startswith("link:"):
            continue
        source_id = str(row.get("source_id") or "")
        text = str(row.get("text") or "").strip()
        if not source_id or not text or not row.get("cmid"):
            continue
        activity = int(row["cmid"])
        pid = f"{shortname}:{kind}:{activity}:{source_id}"
        out[pid] = {
            "id": pid,
            "course": shortname,
            "kind": kind,
            "activity_id": activity,
            "source": f"{row.get('source_kind')}:{source_id}",
            "name": str(row.get("name") or ""),
            "text": text,
            "world": listed_world(shortname),
        }
    return out


def retrieve(shortname: str, activity_id: int, bank: dict[str, dict] | None = None) -> list[str]:
    """Passage ids for one activity, or an empty list."""
    return [row["id"] for row in passages_for(shortname, activity_id, bank)]


def select_for_turn(bank: dict[str, dict], *, course: str, activity_id: int, world: str) -> list[dict]:
    """Passages for this course, activity, and world. Other worlds are dropped."""
    return [
        row
        for row in bank.values()
        if row.get("course") == course
        and int(row.get("activity_id") or 0) == int(activity_id)
        and row.get("world") == world
    ]


def cite_open_activity(
    message: str,
    bank: dict[str, dict],
    *,
    course: str,
    activity_id: int,
    world: str,
    min_span: int = 24,
) -> str:
    """Passage id and the matching quote, or the lecture miss.

    Only passages for this course, activity, and world are searched.
    """
    rows = select_for_turn(bank, course=course, activity_id=activity_id, world=world)
    found: list[tuple[dict, str]] = []
    for row in rows:
        span = _longest_span(message, row.get("text") or "", min_span)
        if span:
            found.append((row, span))
    if len(found) != 1:
        return MISS
    row, span = found[0]
    return f"{row['id']}\n{span}"


def cite_for_turn(bank: dict[str, dict], *, course: str, activity_id: int, world: str) -> str:
    rows = select_for_turn(bank, course=course, activity_id=activity_id, world=world)
    if not rows:
        return MISS
    return "\n".join(row["text"] for row in rows)


def passages_if_listed(bank: dict[str, dict], shortname: str, allowed: set[str]) -> list[dict]:
    if shortname not in allowed:
        return []
    return [row for row in bank.values() if row.get("course") == shortname]


def cite(shortname: str, activity_id: int, bank: dict[str, dict] | None = None) -> str:
    rows = passages_for(shortname, activity_id, bank)
    if not rows:
        return MISS
    return rows[0]["text"]


def listed_world(shortname: str) -> str:
    return _course_index().get(shortname, "")


def listed_shortnames() -> set[str]:
    return set(_course_index())


_ROSTER_URL_KINDS = {
    "google-presentation": "google-presentation",
    "google-file": "google-file",
    "google-document": "google-document",
    "youtube": "youtube",
}


def course_roster(shortname: str) -> dict:
    """Ask-read of loaders for one listed course. No passage text.

    Off-list names are refused. A row is in_pack when a keys/ext/meat
    record exists; status is ok only when a loader already stored text.
    """
    name = str(shortname or "").strip()
    if name not in listed_shortnames():
        return {"ok": False, "error": "off_list", "shortname": name, "activities": []}

    loaded = _roster_loaded(name)
    ext = _roster_ext(name)
    activities: list[dict] = []
    seen: set[int] = set()
    keys_path = _KEYS / f"{name}.jsonl"
    if keys_path.is_file():
        for row in _rows(keys_path):
            item = _roster_from_key(name, row, loaded, ext)
            if item is None:
                continue
            activities.append(item)
            seen.add(int(item["cmid"]))
    for cmid, rows in loaded.items():
        if cmid in seen:
            continue
        for row in rows:
            if row.get("kind") not in _C3_KINDS:
                continue
            activities.append(
                {
                    "cmid": cmid,
                    "name": str(row.get("name") or ""),
                    "kind": str(row.get("kind") or ""),
                    "sectionnum": 0,
                    "status": "ok",
                    "source": "",
                    "in_pack": True,
                }
            )
            seen.add(cmid)
            break
    return {"ok": True, "shortname": name, "activities": activities}


def _roster_loaded(shortname: str) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for bank in (
        load_c3(shortname),
        load_c4_files(shortname),
        load_c4_drive(shortname),
        load_c5_youtube(shortname),
    ):
        for row in bank.values():
            activity = int(row["activity_id"])
            out.setdefault(activity, []).append(row)
    return out


def _roster_ext(shortname: str) -> dict[tuple[int, str], dict]:
    path = _EXT / f"{shortname}.jsonl"
    out: dict[tuple[int, str], dict] = {}
    if not path.is_file():
        return out
    for row in _rows(path):
        if str(row.get("course") or "") != shortname or not row.get("cmid"):
            continue
        source_id = str(row.get("source_id") or "")
        if not source_id:
            continue
        out[(int(row["cmid"]), source_id)] = row
    return out


def _roster_from_key(
    shortname: str,
    row: dict,
    loaded: dict[int, list[dict]],
    ext: dict[tuple[int, str], dict],
) -> dict | None:
    if str(row.get("course") or "") != shortname or not row.get("cmid"):
        return None
    cmid = int(row["cmid"])
    kind, source = _roster_kind_source(row)
    item = {
        "cmid": cmid,
        "name": str(row.get("name") or ""),
        "kind": kind or "link",
        "sectionnum": int(row.get("sectionnum") or 0),
        "status": "not_in_pack",
        "source": source,
        "in_pack": False,
    }
    if kind is None:
        return item
    passages = loaded.get(cmid) or []
    if any(_roster_passage_matches(kind, source, passage) for passage in passages):
        item["status"] = "ok"
        item["in_pack"] = True
        return item
    recorded = ext.get((cmid, source))
    if recorded is not None:
        status = str(recorded.get("status") or "empty")
        item["status"] = status if status in {"ok", "empty", "unavailable"} else "empty"
        item["in_pack"] = True
        if item["status"] == "ok" and not str(recorded.get("text") or "").strip():
            item["status"] = "empty"
        return item
    item["status"] = "empty"
    item["in_pack"] = True
    return item


def _roster_kind_source(row: dict) -> tuple[str | None, str]:
    ref = str(row.get("ref") or "")
    prefix, _, rest = ref.partition(":")
    kind = str(row.get("kind") or "")
    if kind == "file" and prefix == "file":
        return "file", rest
    mapped = _ROSTER_URL_KINDS.get(prefix)
    if kind == "url" and mapped:
        return mapped, rest
    return None, rest


def _roster_passage_matches(kind: str, source: str, passage: dict) -> bool:
    row_kind = str(passage.get("kind") or "")
    if kind == "file":
        return row_kind == "file" and (
            not source or str(passage.get("source") or "").endswith(source)
        )
    if kind == "youtube":
        return row_kind == "youtube" and source in str(passage.get("source") or passage.get("id") or "")
    if kind.startswith("google"):
        return row_kind == "google" and source in str(passage.get("source") or passage.get("id") or "")
    return row_kind == kind


@lru_cache(maxsize=1)
def _course_index() -> dict[str, str]:
    path = _PACK.parent / "courses.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    world = str(data.get("world") or "")
    out: dict[str, str] = {}
    for row in data.get("enabled_courses") or []:
        shortname = str(row.get("shortname") or "")
        if shortname:
            out[shortname] = world
    return out


def _longest_span(message: str, text: str, min_span: int) -> str:
    if len(message) < min_span or len(text) < min_span:
        return ""
    limit = min(len(message), 160)
    for size in range(limit, min_span - 1, -1):
        for start in range(0, len(message) - size + 1):
            span = message[start : start + size]
            if span in text:
                return span
    return ""


def _rows(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("{"):
            continue
        rows.append(json.loads(line))
    return rows


def _join_key(row: dict) -> tuple:
    return (row.get("sectionnum"), str(row.get("name") or ""), str(row.get("ref") or ""))


def _activity_id(row: dict) -> int | None:
    if row.get("cmid"):
        return int(row["cmid"])
    ref = str(row.get("ref") or "")
    kind, _, tail = ref.partition(":")
    if kind in _C3_KINDS and tail.isdigit():
        return int(tail)
    return None
