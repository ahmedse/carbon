"""Guide engine: pure rules with fake probes. No domain, no HTTP."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone

from django.test import SimpleTestCase

from guide import engine, registry

NOW = datetime(2026, 9, 30, 9, 0, tzinfo=dt_timezone.utc)
PACK = "t"


def _lesson(lid, priority, track="D", phase="gather", **over):
    row = {
        "id": lid, "pack": PACK, "track": track, "phase": phase, "priority": priority,
        "minutes": 1, "version": 1, "question": {"kind": "static", "options": 3, "correct": 1},
    }
    row.update(over)
    return row


CATALOG = [
    _lesson("A1", 10, track="C"),
    _lesson("B1", 20, any=["t:write"]),
    _lesson("B2", 30, any=["t:write"], needs=["gate"]),
    _lesson("B3", 40, any=["t:write"]),
    _lesson("M1", 50, track="L", any=["t:manage"]),
    _lesson("R1", 60, track="U", all=["t:view", "t:audit"]),
]
STATE = {"gate_open": True}


@registry.probe(PACK, "need", "gate")
def _gate(ctx, lesson):
    return None if STATE["gate_open"] else {"code": "gate_closed", "path": None}


def _ctx(*caps):
    return engine.Ctx(user=None, app_id=PACK, caps=frozenset(caps))


def _done(*ids):
    return {(PACK, i): {"state": "done", "lesson_version": 1} for i in ids}


class EngineTests(SimpleTestCase):
    def setUp(self):
        STATE["gate_open"] = True

    def ids(self, out):
        return [r["id"] for r in out["lessons"]]

    def test_capabilities_pick_the_lessons(self):
        out = engine.evaluate_lessons(_ctx("t:write"), CATALOG, {}, NOW)
        self.assertEqual(self.ids(out), ["A1", "B1", "B2", "B3"])

    def test_all_needs_every_key(self):
        self.assertNotIn("R1", self.ids(engine.evaluate_lessons(_ctx("t:view"), CATALOG, {}, NOW)))
        self.assertIn("R1", self.ids(engine.evaluate_lessons(_ctx("t:view", "t:audit"), CATALOG, {}, NOW)))

    def test_superuser_gets_all(self):
        out = engine.evaluate_lessons(_ctx("*"), CATALOG, {}, NOW)
        self.assertEqual(len(out["lessons"]), len(CATALOG))

    def test_next_follows_priority_and_skips_done(self):
        out = engine.evaluate_lessons(_ctx("t:write"), CATALOG, _done("A1"), NOW)
        self.assertEqual(out["next_id"], "B1")
        self.assertEqual(out["recommended_track"], "D")

    def test_blocked_lesson_is_shown_but_not_next(self):
        STATE["gate_open"] = False
        out = engine.evaluate_lessons(_ctx("t:write"), CATALOG, _done("A1", "B1"), NOW)
        b2 = next(r for r in out["lessons"] if r["id"] == "B2")
        self.assertEqual(b2["blocker"], {"code": "gate_closed", "path": None})
        self.assertEqual(out["next_id"], "B3")

    def test_snooze_hides_until_expiry(self):
        snoozed = {(PACK, "A1"): {"state": "snoozed", "lesson_version": 1, "snoozed_until": NOW + timedelta(hours=3)}}
        out = engine.evaluate_lessons(_ctx("t:write"), CATALOG, snoozed, NOW)
        self.assertEqual(out["next_id"], "B1")
        later = engine.evaluate_lessons(_ctx("t:write"), CATALOG, snoozed, NOW + timedelta(days=2))
        self.assertEqual(later["next_id"], "A1")

    def test_new_version_reoffers_a_done_lesson(self):
        old = {(PACK, "A1"): {"state": "done", "lesson_version": 0}}
        row = next(r for r in engine.evaluate_lessons(_ctx("t:write"), CATALOG, old, NOW)["lessons"] if r["id"] == "A1")
        self.assertEqual((row["state"], row["stale"]), ("offered", True))

    def test_tracks_count_done(self):
        out = engine.evaluate_lessons(_ctx("t:write"), CATALOG, _done("B1"), NOW)
        d = next(t for t in out["tracks"] if t["id"] == "D")
        self.assertEqual((d["done"], d["total"]), (1, 3))

    def test_missing_probe_blocks_instead_of_crashing(self):
        lesson = _lesson("X", 5, needs=["nope"])
        self.assertEqual(engine.blocker_for(lesson, _ctx())["code"], "probe_missing")

    def test_question_never_carries_the_answer(self):
        q = engine.question_for(CATALOG[0], _ctx())
        self.assertEqual(set(q), {"options", "params"})
        self.assertTrue(engine.check_choice(CATALOG[0], _ctx(), 1))
        self.assertFalse(engine.check_choice(CATALOG[0], _ctx(), 0))

    def test_host_check_carries_no_options(self):
        lesson = _lesson("H1", 1, question={"kind": "host"}, host="row_created")
        self.assertEqual(engine.question_for(lesson, _ctx()), {"kind": "host", "options": 0, "params": {}})

    def test_resume_is_the_last_touched_lesson_and_step(self):
        earlier = NOW - timedelta(hours=2)
        later = NOW - timedelta(minutes=5)
        progress = {
            (PACK, "A1"): {"state": "done", "lesson_version": 1, "started_at": earlier, "updated_at": earlier, "step": 3},
            (PACK, "B1"): {"state": "started", "lesson_version": 1, "started_at": later, "updated_at": later, "step": 2},
        }
        out = engine.evaluate_lessons(_ctx("t:write"), CATALOG, progress, NOW)
        self.assertEqual(out["resume"], {"id": "B1", "step": 2})
        self.assertEqual(out["next_id"], "B1")

    def test_resume_is_empty_when_nothing_has_been_opened(self):
        out = engine.evaluate_lessons(_ctx("t:write"), CATALOG, {}, NOW)
        self.assertIsNone(out["resume"])

    def test_stage_owns_next_until_its_lessons_are_done(self):
        catalog = [
            _lesson("D1", 20),
            _lesson("D2", 30, stage="entry"),
            _lesson("D3", 40),
            _lesson("D7", 80, stage="entry"),
        ]
        out = engine.evaluate_lessons(_ctx("t:write"), catalog, {}, NOW)
        self.assertEqual(out["next_id"], "D2")
        self.assertEqual(out["recommended_track"], "D")
        self.assertFalse(next(r for r in out["lessons"] if r["id"] == "D3")["is_next"])

        done_row = engine.evaluate_lessons(_ctx("t:write"), catalog, _done("D2"), NOW)
        self.assertEqual(done_row["next_id"], "D7")

        both = engine.evaluate_lessons(_ctx("t:write"), catalog, _done("D2", "D7"), NOW)
        self.assertIsNone(both["next_id"])
        self.assertIsNone(both["recommended_track"])
        self.assertEqual(len(both["lessons"]), 4)

    def test_blocked_stage_lesson_does_not_hand_next_to_a_later_one(self):
        catalog = [
            _lesson("D2", 30, stage="entry", needs=["gate"]),
            _lesson("D7", 80, stage="entry"),
        ]
        STATE["gate_open"] = False
        out = engine.evaluate_lessons(_ctx("t:write"), catalog, {}, NOW)
        self.assertIsNone(out["next_id"])
        self.assertEqual(next(r for r in out["lessons"] if r["id"] == "D2")["blocker"]["code"], "gate_closed")
