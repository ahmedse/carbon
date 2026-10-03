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
#: Committed keyword-index rows per course (recall-only; see content_engine/index).
_INDEX = _PACK.parent / "index"
_ROOT = _PACK / "course-meat-13"
_KEYS = _PACK / "course-keys-13"
_EXT = _PACK / "course-ext-13"
_EXTRA = _PACK / "course-extra-13"


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
            "sectionnum": int(row.get("sectionnum") or 0),
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


def load_extra(shortname: str, extra_root: Path | None = None) -> dict[str, dict]:
    """Tutor extra files already indexed for one course. Not a Moodle resource."""
    path = (extra_root or _EXTRA) / f"{shortname}.jsonl"
    out: dict[str, dict] = {}
    if not path.is_file():
        return out
    for row in _rows(path):
        if str(row.get("course") or "") != shortname or str(row.get("kind") or "") != "extra":
            continue
        filename = str(row.get("filename") or "")
        text = str(row.get("text") or "").strip()
        if not filename or not text or not row.get("itemid"):
            continue
        itemid = int(row["itemid"])
        pid = f"{shortname}:extra:{itemid}:{filename}"
        out[pid] = {
            "id": pid,
            "course": shortname,
            "kind": "extra",
            "activity_id": -itemid,
            "extra_itemid": itemid,
            "source": f"extra:{filename}",
            "name": str(row.get("name") or filename),
            "text": text,
            "world": listed_world(shortname),
        }
    return out


def write_extra_index(shortname: str, extras: list[dict], extra_root: Path | None = None) -> int:
    """Replace extra JSONL for one listed course. Does not fetch Drive or YouTube."""
    if shortname not in listed_shortnames():
        return 0
    path = (extra_root or _EXTRA) / f"{shortname}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for item in extras:
        if not isinstance(item, dict) or not item.get("itemid"):
            continue
        filename = str(item.get("filename") or "").strip()
        title = str(item.get("title") or filename)
        try:
            itemid = int(item["itemid"])
        except (TypeError, ValueError):
            continue
        if itemid <= 0 or not filename:
            continue
        sectionnum = int(item.get("sectionnum") or -1)
        for passage in item.get("passages") or []:
            if not isinstance(passage, dict):
                continue
            text = str(passage.get("text") or "").strip()
            if not text:
                continue
            lines.append(
                json.dumps(
                    {
                        "course": shortname,
                        "itemid": itemid,
                        "filename": filename,
                        "kind": "extra",
                        "name": title,
                        "sectionnum": sectionnum,
                        "text": text,
                    },
                    ensure_ascii=False,
                )
            )
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)


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


def cite_topic_index(
    topic: str,
    bank: dict[str, dict],
    *,
    course: str,
    activity_id: int,
    world: str,
    index_root: Path | None = None,
    limit: int = 160,
    k: int | None = None,
    allow_window: bool = True,
) -> tuple[str, str] | None:
    """Recall-only keyword-index fallback for a title/whole-file miss (L-R R1).

    The deterministic door in ``cite_open_activity`` misses when no whole-file
    passage holds a unique substring. This consults the committed keyword index
    (``domain_packs/aast-med/index/<course>.jsonl``) over bounded chunk windows,
    but only for **recall**: it returns ``(passage_id, span)`` when

    * exactly one passage in the open activity has the unique top score, and
    * the span is a verbatim slice of that passage's stored text.

    Anything else is ``None``, so the caller keeps the exact miss. No engine
    module is touched and no phrase table is added.
    """
    if not topic or activity_id is None:
        return None
    try:
        activity = int(activity_id)
    except (TypeError, ValueError):
        return None
    try:
        from ai.content_engine.index import DEFAULT_K, load_index, retrieve
    except Exception:  # noqa: BLE001 — the door keeps its miss if the index is absent
        return None
    root = Path(index_root) if index_root is not None else _INDEX
    path = root / f"{course}.jsonl"
    if not path.is_file():
        return None
    try:
        index = load_index(str(path))
    except (OSError, ValueError):
        return None
    results = retrieve(index, topic, k=int(k or DEFAULT_K))
    by_id = index.chunks_by_id
    best_by_passage: dict[str, dict] = {}
    for result in results:
        chunk = by_id.get(str(result.get("chunk_id") or "")) or {}
        pid = str(chunk.get("source_ref") or "")
        row = bank.get(pid)
        if row is None or row.get("world") != world:
            continue
        if int(row.get("activity_id") or 0) != activity:
            continue
        if not str(row.get("text") or "").strip():
            continue
        previous = best_by_passage.get(pid)
        if previous is None or int(result.get("score") or 0) > int(previous.get("score") or 0):
            best_by_passage[pid] = result
    if not best_by_passage:
        return cite_topic_index_windowed(
            topic, bank, course=course, activity_id=activity, world=world,
            index_root=index_root, limit=limit,
        ) if allow_window else None
    top = max(int(result.get("score") or 0) for result in best_by_passage.values())
    winners = [pid for pid, result in best_by_passage.items() if int(result.get("score") or 0) == top]
    if len(winners) != 1:
        # R1 has no unique whole-word winner; the R2 overlap-window pass below
        # may still resolve it deterministically (or return None -> exact miss).
        return cite_topic_index_windowed(
            topic, bank, course=course, activity_id=activity, world=world,
            index_root=index_root, limit=limit,
        ) if allow_window else None
    pid = winners[0]
    text = str(bank[pid].get("text") or "")
    span = _index_window(best_by_passage[pid], limit)
    if not span or span not in text:
        return cite_topic_index_windowed(
            topic, bank, course=course, activity_id=activity, world=world,
            index_root=index_root, limit=limit,
        ) if allow_window else None
    return pid, span


def cite_topic_index_windowed(
    topic: str,
    bank: dict[str, dict],
    *,
    course: str,
    activity_id: int,
    world: str,
    index_root: Path | None = None,
    limit: int = 160,
) -> tuple[str, str] | None:
    """Hybrid recall for a title/whole-file miss (L-R R2).

    Deterministic extension of :func:`cite_topic_index`. It scores every
    committed chunk whose ``source_ref`` resolves to a passage in the open
    activity, then adds the score of that chunk's ``prev_id`` / ``next_id``
    neighbour **only when the neighbour belongs to the same passage** — the
    0.15-ratio overlap windows the chunker already stores. The single passage
    with the unique top *combined* score wins, so a query whose terms fall in
    adjacent windows of one passage is resolved even when no single chunk is a
    unique top whole-word hit.

    Invariants are unchanged: the emitted span is a verbatim slice of the
    selected passage's stored text, only a unique winner is returned, and
    anything ambiguous or absent is ``None`` so the caller keeps the exact
    miss sentence. No engine module, phrase table, or network call is added.
    """
    if not topic or activity_id is None:
        return None
    try:
        activity = int(activity_id)
    except (TypeError, ValueError):
        return None
    try:
        from ai.content_engine.index import load_index, retrieve
    except Exception:  # noqa: BLE001 — the door keeps its miss if the index is absent
        return None
    root = Path(index_root) if index_root is not None else _INDEX
    path = root / f"{course}.jsonl"
    if not path.is_file():
        return None
    try:
        index = load_index(str(path))
    except (OSError, ValueError):
        return None

    # No top-k ceiling: score every chunk the query hits. ``retrieve`` keeps
    # whole-word bounded spans, so nothing partial or fabricated is scored.
    results = retrieve(index, topic, k=max(1, len(index.chunks)))
    if not results:
        return None
    result_by_chunk = {str(r.get("chunk_id") or ""): r for r in results}
    by_id = index.chunks_by_id

    def _in_scope(pid: str) -> bool:
        row = bank.get(pid)
        if row is None or row.get("world") != world:
            return False
        if int(row.get("activity_id") or 0) != activity:
            return False
        return bool(str(row.get("text") or "").strip())

    best: dict[str, tuple[int, dict]] = {}  # passage id -> (combined score, best chunk result)
    for chunk_id, result in result_by_chunk.items():
        chunk = by_id.get(chunk_id)
        if chunk is None:
            continue
        pid = str(chunk.get("source_ref") or "")
        if not _in_scope(pid):
            continue
        combined = int(result.get("score") or 0)
        for neighbour_key in ("prev_id", "next_id"):
            neighbour = by_id.get(str(chunk.get(neighbour_key) or ""))
            if neighbour is None or str(neighbour.get("source_ref") or "") != pid:
                continue
            neighbour_id = str(neighbour.get("chunk_id") or "")
            combined += int((result_by_chunk.get(neighbour_id) or {}).get("score") or 0)
        current = best.get(pid)
        if current is None or combined > current[0]:
            best[pid] = (combined, result)
    if not best:
        return None
    top = max(score for score, _ in best.values())
    winners = [pid for pid, (score, _) in best.items() if score == top]
    if len(winners) != 1:
        return None
    pid = winners[0]
    text = str(bank[pid].get("text") or "")
    span = _index_window(best[pid][1], limit)
    if not span or span not in text:
        return None
    return pid, span


def _index_window(result: dict, limit: int) -> str:
    """A bounded, exact slice of a chunk around its first matched token."""
    chunk_text = str(result.get("text") or "")
    spans = result.get("spans") or []
    if not chunk_text or not spans:
        return ""
    first = min(spans, key=lambda span: int(span.get("char_start") or 0))
    start = max(0, int(first.get("char_start") or 0) - 40)
    end = min(len(chunk_text), start + max(1, int(limit)))
    return chunk_text[start:end].strip()


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

# Stable join vocabulary between the bank and this Docker Moodle. The bank
# keys carry production activity ids (NMD1103) that do not equal local cmids,
# so the roster matches a Moodle module to a bank row by section + family +
# name (the K7 join shape). Family is the only thing the two sides translate.
_FAMILY_FILE = "file"
_FAMILY_URL = "url"
_FAMILY_KINDS = {"page": "page", "label": "label", "book": "book"}
_URL_FAMILY_KINDS = {"url", "link", "youtube"}


def roster_family(kind: str) -> str:
    """Bank kind or Moodle modname → one of file / url / page / label / book / other."""
    name = str(kind or "").strip().lower()
    if name in {"file", "resource"}:
        return _FAMILY_FILE
    if name in _FAMILY_KINDS:
        return _FAMILY_KINDS[name]
    if name in _URL_FAMILY_KINDS or name.startswith("google"):
        return _FAMILY_URL
    return "other"


def roster_key(sectionnum: int, kind: str, name: str) -> str:
    """The section + family + name key a Moodle module and a bank row share."""
    folded = " ".join(str(name or "").split()).lower()
    return f"{int(sectionnum)}:{roster_family(kind)}:{folded}"


def match_roster_activity(module: dict, activities: list[dict]) -> dict | None:
    """A bank roster row for one Moodle module: local cmid first, stable key next.

    Returns None when neither the cmid nor the section+family+name key matches,
    so a caller never reads loaded without a real bank row behind it.
    """
    cmid = int(module.get("cmid") or 0)
    if cmid:
        for row in activities:
            if int(row.get("cmid") or 0) == cmid:
                return row
    key = roster_key(
        int(module.get("sectionnum") or 0),
        str(module.get("modname") or module.get("kind") or ""),
        str(module.get("name") or ""),
    )
    for row in activities:
        if row.get("key") == key:
            return row
    return None


def _roster_key_for_row(sectionnum: int, kind: str, name: str) -> str:
    return roster_key(sectionnum, kind, name)


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
            sectionnum = int(row.get("sectionnum") or 0)
            kind = str(row.get("kind") or "")
            activities.append(
                {
                    "cmid": cmid,
                    "key": roster_key(sectionnum, kind, str(row.get("name") or "")),
                    "name": str(row.get("name") or ""),
                    "kind": kind,
                    "sectionnum": sectionnum,
                    "status": "ok",
                    "source": "",
                    "in_pack": True,
                }
            )
            seen.add(cmid)
            break
    for row in load_extra(name).values():
        activities.append(
            {
                "cmid": 0,
                "itemid": int(row.get("extra_itemid") or 0),
                "name": str(row.get("name") or ""),
                "kind": "extra",
                "sectionnum": -1,
                "status": "ok",
                "source": "extra",
                "in_pack": True,
            }
        )
    return {"ok": True, "shortname": name, "activities": activities}


def _roster_loaded(shortname: str) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for bank in (
        load_c3(shortname),
        load_c4_files(shortname),
        load_c4_drive(shortname),
        load_c5_youtube(shortname),
        load_extra(shortname),
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
    sectionnum = int(row.get("sectionnum") or 0)
    item = {
        "cmid": cmid,
        "key": roster_key(sectionnum, kind or "link", str(row.get("name") or "")),
        "name": str(row.get("name") or ""),
        "kind": kind or "link",
        "sectionnum": sectionnum,
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
