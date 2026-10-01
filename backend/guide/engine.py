"""Guide engine: domain-free microlearning.

It knows lessons, capabilities, progress and probes. It does not know what the
host's objects are: a pack names probes and the domain app answers them
(``guide.registry``). Lesson text is never here.

Everything except ``apply_event`` and ``load_progress`` is a read. The only
write is ``GuideProgress``.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable, Iterable, Mapping

from django.db import transaction

from guide import registry

TRACKS = ("C", "D", "L", "A", "U", "H")
RECOMMEND_ORDER = ("D", "L", "A", "U", "H")
SNOOZE_DAYS = 1
STEP_MAX = 3
LIVE_FALLBACK = {"kind": "none"}


def clamp_step(value) -> int:
    try:
        step = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(STEP_MAX, step))


class Ctx:
    """One request's view of the caller. ``memo`` lets probes share a read."""

    def __init__(self, user, app_id: str, caps: frozenset[str]):
        self.user = user
        self.app_id = app_id
        self.caps = caps
        self.memo: dict[Any, Any] = {}
        self.started_at: datetime | None = None

    def has(self, key: str) -> bool:
        return "*" in self.caps or key in self.caps

    def once(self, key: Any, fn: Callable[[], Any]) -> Any:
        if key not in self.memo:
            self.memo[key] = fn()
        return self.memo[key]


# ── Catalog rules ──────────────────────────────────────────────────────────

def is_available(lesson: Mapping[str, Any], ctx: Ctx) -> bool:
    any_of = lesson.get("any") or []
    all_of = lesson.get("all") or []
    if any_of and not any(ctx.has(key) for key in any_of):
        return False
    return all(ctx.has(key) for key in all_of)


def _probe(lesson: Mapping[str, Any], kind: str, name: str):
    return registry.find(lesson["pack"], kind, name)


def blocker_for(lesson: Mapping[str, Any], ctx: Ctx) -> dict | None:
    """First unmet precondition as ``{code, path}``. A missing probe blocks; the contract gate catches it."""
    for name in lesson.get("needs") or []:
        fn = _probe(lesson, "need", name)
        if fn is None:
            return {"code": "probe_missing", "path": None}
        found = fn(ctx, lesson)
        if found:
            return found
    return None


def host_met(lesson: Mapping[str, Any], ctx: Ctx) -> bool:
    name = lesson.get("host")
    if not name:
        return True
    fn = _probe(lesson, "host", name)
    return bool(fn and fn(ctx, lesson))


def live_object(lesson: Mapping[str, Any], ctx: Ctx) -> dict:
    name = lesson.get("live")
    fn = _probe(lesson, "live", name) if name else None
    return fn(ctx, lesson) if fn else dict(LIVE_FALLBACK)


def _question_probe(lesson: Mapping[str, Any], ctx: Ctx) -> dict:
    spec = lesson.get("question") or {}
    fn = _probe(lesson, "question", spec.get("name") or "")
    return fn(ctx, lesson) if fn else {"params": {}, "correct": -1}


def question_for(lesson: Mapping[str, Any], ctx: Ctx) -> dict:
    """Question shape for the coach. The correct option is never in this payload."""
    spec = lesson.get("question") or {}
    if spec.get("kind") == "host":
        return {"kind": "host", "options": 0, "params": {}}
    options = int(spec.get("options") or 3)
    if spec.get("kind") == "probe":
        return {"options": options, "params": dict(_question_probe(lesson, ctx).get("params") or {})}
    return {"options": options, "params": {}}


def check_choice(lesson: Mapping[str, Any], ctx: Ctx, choice: int) -> bool:
    spec = lesson.get("question") or {}
    if spec.get("kind") == "probe":
        return int(_question_probe(lesson, ctx).get("correct", -1)) == choice
    return int(spec.get("correct", -1)) == choice


def signal_for(lesson: Mapping[str, Any]) -> str:
    host = lesson.get("host")
    if not host:
        return "answer"
    return "host_row" if str(host).startswith("row_") else "host_state"


# ── Evaluation ─────────────────────────────────────────────────────────────

def _effective_state(row: Mapping[str, Any] | None, lesson: Mapping[str, Any], now: datetime) -> tuple[str, bool]:
    if row is None:
        return "offered", False
    state = row.get("state") or "offered"
    stored = row.get("lesson_version")
    stale = (1 if stored is None else int(stored)) < int(lesson.get("version") or 1)
    if state == "done":
        return ("offered", True) if stale else ("done", False)
    if state == "snoozed":
        until = row.get("snoozed_until")
        if until is not None and until > now:
            return "snoozed", stale
        return ("started" if row.get("started_at") else "offered"), stale
    return state, stale


def progress_key(lesson: Mapping[str, Any]) -> tuple[str, str]:
    return lesson["pack"], lesson["id"]


def evaluate_lessons(
    ctx: Ctx,
    catalog: Iterable[Mapping[str, Any]],
    progress: Mapping[tuple[str, str], Mapping[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    """Lessons this user may take, their state and blockers, and the one to do next."""
    rows: list[dict] = []
    for lesson in catalog:
        if not is_available(lesson, ctx):
            continue
        stored = progress.get(progress_key(lesson))
        state, stale = _effective_state(stored, lesson, now)
        rows.append({
            "id": lesson["id"],
            "pack": lesson["pack"],
            "track": lesson["track"],
            "phase": lesson["phase"],
            "priority": lesson["priority"],
            "minutes": lesson["minutes"],
            "version": lesson["version"],
            "state": state,
            "stale": stale,
            "step": clamp_step((stored or {}).get("step")),
            "blocker": blocker_for(lesson, ctx),
            "route": lesson.get("route") or "",
            "target": lesson.get("target") or "",
            "stage": str(lesson.get("stage") or ""),
            "is_next": False,
        })
    rows.sort(key=lambda row: row["priority"])
    next_id = _choose_next(rows)
    tracks = []
    for track in TRACKS:
        members = [row for row in rows if row["track"] == track]
        if members:
            tracks.append({
                "id": track,
                "total": len(members),
                "done": sum(1 for row in members if row["state"] == "done"),
            })
    if any(row.get("stage") for row in rows):
        # A stage owns the recommendation until its lessons are finished.
        recommended = next((row["track"] for row in rows if row["id"] == next_id), None)
    else:
        recommended = next(
            (
                track for track in RECOMMEND_ORDER
                if any(r["track"] == track and r["state"] != "done" and r["blocker"] is None for r in rows)
            ),
            None,
        )
    return {
        "tracks": tracks,
        "recommended_track": recommended,
        "lessons": rows,
        "next_id": next_id,
        "resume": resume_of(rows, progress),
    }


def _choose_next(rows: list[dict]) -> str | None:
    """One lesson to offer.

    A pack stage (for example data entry) owns "next" until those lessons are
    finished or the first unfinished one is blocked. Quiet lessons stay listed.
    Without a stage, the first unfinished unblocked lesson wins, as before.
    """
    staged = [row for row in rows if row.get("stage")]
    pool = staged if staged else rows
    for row in pool:
        if row["state"] in ("done", "snoozed"):
            continue
        if staged and row.get("blocker"):
            return None
        if row["state"] in ("offered", "started") and row.get("blocker") is None:
            row["is_next"] = True
            return row["id"]
        if staged:
            return None
    return None


def resume_of(rows: Iterable[Mapping[str, Any]], progress: Mapping[tuple[str, str], Mapping[str, Any]]) -> dict | None:
    """The lesson the caller last touched, and the coach card they were on."""
    best: tuple | None = None
    for row in rows:
        stored = progress.get((row["pack"], row["id"]))
        if not stored:
            continue
        stamp = stored.get("updated_at") or stored.get("started_at") or stored.get("done_at")
        if stamp is None:
            continue
        if not stored.get("started_at") and stored.get("state") not in ("started", "done", "snoozed"):
            continue
        cand = (stamp, row["id"], clamp_step(stored.get("step")))
        if best is None or cand[0] > best[0]:
            best = cand
    if best is None:
        return None
    return {"id": best[1], "step": best[2]}


# ── Progress (the only write) ──────────────────────────────────────────────

def load_progress(user, pack_ids: Iterable[str]) -> dict[tuple[str, str], dict]:
    from guide.models import GuideProgress

    return {
        (row.pack_id, row.lesson_id): {
            "state": row.state,
            "lesson_version": row.lesson_version,
            "started_at": row.started_at,
            "done_at": row.done_at,
            "snoozed_until": row.snoozed_until,
            "signal": row.signal,
            "step": row.step,
            "updated_at": row.updated_at,
        }
        for row in GuideProgress.objects.filter(user=user, pack_id__in=list(pack_ids))
    }


def apply_event(ctx: Ctx, lesson: Mapping[str, Any], event: str, choice: int | None,
                now: datetime, step: int | None = None) -> dict[str, Any]:
    from guide.models import GuideProgress

    with transaction.atomic():
        row, _ = GuideProgress.objects.select_for_update().get_or_create(
            user=ctx.user, pack_id=lesson["pack"], lesson_id=lesson["id"],
            defaults={"lesson_version": lesson["version"]},
        )
        if row.state == "done" and row.lesson_version < lesson["version"]:
            row.state, row.started_at, row.done_at, row.signal, row.step = "offered", None, None, "", 0
            row.lesson_version = lesson["version"]
        out: dict[str, Any] = {"correct": None, "waiting": None}
        if step is not None:
            row.step = clamp_step(step)
        if row.state == "done":
            row.save()
            out["state"] = "done"
            out["step"] = row.step
            return out
        if event == "snooze":
            row.state = "snoozed"
            row.snoozed_until = now + timedelta(days=SNOOZE_DAYS)
        else:
            if row.started_at is None:
                row.started_at = now
            if row.state in ("offered", "snoozed"):
                row.state = "started"
            row.snoozed_until = None
            host_check = (lesson.get("question") or {}).get("kind") == "host"
            if event == "answered" and not host_check:
                ok = choice is not None and check_choice(lesson, ctx, choice)
                out["correct"] = ok
                # A failed answer is the whole outcome. Drop an earlier pass so
                # the host wait cannot ride along on the same check.
                row.signal = "answer" if ok else ""
            if host_check and event == "check":
                ctx.started_at = row.started_at
                if host_met(lesson, ctx):
                    row.state, row.done_at, row.signal = "done", now, signal_for(lesson)
                else:
                    out["waiting"] = "host"
            elif out["correct"] is not False and row.signal == "answer":
                ctx.started_at = row.started_at
                if host_met(lesson, ctx):
                    row.state, row.done_at, row.signal = "done", now, signal_for(lesson)
                else:
                    out["waiting"] = "host"
        row.save()
        out["state"] = row.state
        out["step"] = row.step
        return out
