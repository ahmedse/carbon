"""The camp drama: pure beat rules, the one write, the contract and the payload.

The drama is a teaching device. These tests pin the boundary that makes it safe:
a beat answer advances a drama, and it can NEVER mark a lesson or a station done.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from guide import contract, engine, views

User = get_user_model()
PACK = "t"
STAGE = {
    "n": 1,
    "key": "setup",
    "scenario": {
        "beats": [
            {"id": "keep_one_open", "correct": 0},
            {"id": "name_the_move", "correct": 1},
        ],
    },
}
BEATS = engine.beats_of(STAGE)


class BeatRuleTests(SimpleTestCase):
    def test_beats_of_reads_the_declared_beats(self):
        self.assertEqual([beat["id"] for beat in BEATS], ["keep_one_open", "name_the_move"])
        self.assertEqual(engine.beats_of({}), [])
        self.assertEqual(engine.beats_of({"scenario": {}}), [])

    def test_clamp_beat_is_bounded(self):
        self.assertEqual(engine.clamp_beat(None, 2), 0)
        self.assertEqual(engine.clamp_beat("x", 2), 0)
        self.assertEqual(engine.clamp_beat(9, 2), 2)
        self.assertEqual(engine.clamp_beat(1, 2), 1)

    def test_check_beat_grades_only_the_declared_choice(self):
        self.assertTrue(engine.check_beat(BEATS[0], 0))
        self.assertFalse(engine.check_beat(BEATS[0], 1))
        self.assertFalse(engine.check_beat({}, 0))


class ScenarioWriteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="scenario.user", password="x")
        self.ctx = engine.Ctx(user=self.user, app_id=PACK, caps=frozenset())

    def test_a_wrong_choice_does_not_advance(self):
        out = engine.apply_scenario(self.ctx, STAGE, 0, 1)
        self.assertEqual((out["correct"], out["beat"], out["total"], out["done"]), (False, 0, 2, False))
        self.assertEqual(engine.load_scenarios(self.user, [PACK]), {(PACK, "setup"): 0})

    def test_a_right_choice_advances_one_beat(self):
        out = engine.apply_scenario(self.ctx, STAGE, 0, 0)
        self.assertEqual((out["correct"], out["beat"], out["done"]), (True, 1, False))
        self.assertEqual(engine.load_scenarios(self.user, [PACK])[(PACK, "setup")], 1)

    def test_walking_every_beat_finishes_the_drama(self):
        engine.apply_scenario(self.ctx, STAGE, 0, 0)
        out = engine.apply_scenario(self.ctx, STAGE, 1, 1)
        self.assertTrue(out["done"])
        self.assertEqual(out["beat"], 2)

    def test_a_replayed_earlier_beat_is_ignored(self):
        engine.apply_scenario(self.ctx, STAGE, 0, 0)
        out = engine.apply_scenario(self.ctx, STAGE, 0, 0)
        self.assertIsNone(out["correct"])
        self.assertEqual(out["beat"], 1)

    def test_a_beat_beyond_the_declared_range_is_ignored(self):
        out = engine.apply_scenario(self.ctx, STAGE, 2, 0)
        self.assertIsNone(out["correct"])
        self.assertEqual(out["beat"], 0)

    def test_the_drama_never_touches_lesson_progress(self):
        from guide.models import GuideProgress

        engine.apply_scenario(self.ctx, STAGE, 0, 0)
        self.assertEqual(GuideProgress.objects.count(), 0)


class ScenarioContractTests(SimpleTestCase):
    WHERE = "t.stage[1]"
    GOOD_BEAT = {
        "id": "b1",
        "cast": "Cast",
        "line": "A line.",
        "question": "Which?",
        "choices": ["One", "Two"],
        "explain": "Because.",
    }

    def copy(self, lang="en", beat=None):
        return {lang: {"stages": {"setup": {"scenario": {"beats": [beat or self.GOOD_BEAT]}}}}}

    def both_langs(self, beat=None):
        copy = {}
        copy.update(self.copy("en", beat))
        copy.update(self.copy("ar", beat))
        return copy

    def test_a_good_scenario_passes(self):
        stage = {"key": "setup", "scenario": {"beats": [{"id": "b1", "correct": 0}]}}
        self.assertEqual(contract._scenario_problems(stage, self.both_langs(), self.WHERE), [])

    def test_correct_out_of_range_fails(self):
        stage = {"key": "setup", "scenario": {"beats": [{"id": "b1", "correct": 5}]}}
        problems = contract._scenario_problems(stage, self.both_langs(), self.WHERE)
        self.assertTrue(any("out of range" in problem for problem in problems))

    def test_a_missing_language_beat_fails(self):
        stage = {"key": "setup", "scenario": {"beats": [{"id": "b1", "correct": 0}]}}
        copy = self.copy("en")
        copy["ar"] = {"stages": {}}
        problems = contract._scenario_problems(stage, copy, self.WHERE)
        self.assertTrue(any("ar copy is missing the beat" in problem for problem in problems))

    def test_a_duplicate_beat_id_fails(self):
        stage = {"key": "setup", "scenario": {"beats": [
            {"id": "b1", "correct": 0}, {"id": "b1", "correct": 0},
        ]}}
        problems = contract._scenario_problems(stage, self.both_langs(), self.WHERE)
        self.assertTrue(any("unique" in problem for problem in problems))

    def test_more_than_the_maximum_beats_fails(self):
        stage = {"key": "setup", "scenario": {"beats": [
            {"id": f"b{i}", "correct": 0} for i in range(engine.SCENARIO_MAX_BEATS + 1)
        ]}}
        problems = contract._scenario_problems(stage, self.both_langs(), self.WHERE)
        self.assertTrue(any("at most" in problem for problem in problems))

    def test_too_few_choices_fails(self):
        beat = dict(self.GOOD_BEAT, choices=["Only one"])
        stage = {"key": "setup", "scenario": {"beats": [{"id": "b1", "correct": 0}]}}
        problems = contract._scenario_problems(stage, self.both_langs(beat), self.WHERE)
        self.assertTrue(any("at least two choices" in problem for problem in problems))


class ScenarioPayloadTests(SimpleTestCase):
    def test_beats_ship_text_but_never_the_answer(self):
        spec = {"scenario": {"beats": [{"id": "b1", "correct": 1}]}}
        text = {"scenario": {"beats": [{
            "id": "b1", "cast": "Cast", "line": "A line.", "question": "Which?",
            "choices": ["One", "Two"], "explain": "Because.",
        }]}}
        beats = views._scenario_payload(spec, text)["beats"]
        self.assertEqual(beats[0]["id"], "b1")
        self.assertEqual(beats[0]["choices"], ["One", "Two"])
        self.assertEqual(beats[0]["explain"], "Because.")
        self.assertNotIn("correct", beats[0])

    def test_a_stage_without_a_drama_ships_no_beats(self):
        self.assertEqual(views._scenario_payload({}, {}), {"beats": []})
