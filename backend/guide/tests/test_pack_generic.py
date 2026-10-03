"""A fake, non-carbon pack proves the journey engine is generic and domain-free.

The engine loads any pack that passes the contract and builds a journey payload
with stage titles, competency outcomes and step scripts read from copy. No
engine edit is needed to add this pack.
"""
from __future__ import annotations

import textwrap
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase

from guide import contract, engine, packs, views

FAKE_GUIDE = textwrap.dedent(
    """
    pack: fake
    version: 1
    journey:
      title_key: journey.title
      intro_key: journey.intro
      glossary: [flux capacitor]
    stages:
      - n: 1
        key: begin
        title_key: stage.begin.title
        what_key: stage.begin.what
        lessons: [F1]
        competencies: [first_step]
    competencies:
      - {key: first_step, kind: answer, lesson: F1}
    lessons:
      - id: F1
        track: C
        phase: gather
        priority: 10
        minutes: 1
        version: 1
        route: /fake/one
        target: fake.one
        completion: answer
        competency: first_step
        steps:
          - {route: /fake/one, target: fake.one}
        question: {kind: static, options: 2, correct: 0}
    """
).strip()

FAKE_COPY_EN = textwrap.dedent(
    """
    journey: {title: "Fake journey", intro: "A pack with no domain words."}
    stages:
      begin: {title: "Begin", what: "The first station.", voice: "One route, one record."}
    competencies:
      first_step: {title: "Take the first step", good: "One route, one do line."}
    lessons:
      F1:
        title: "The first lesson"
        know: "Know text."
        do: "Do text."
        dont: "Dont text."
        steps:
          - {title: "Open the page", do: "Open /fake/one."}
        question: "Which page?"
        options: ["The fake page", "Another page"]
        explain: "Explain text."
    """
).strip()

FAKE_COPY_AR = textwrap.dedent(
    """
    journey: {title: "رحلة تجريبية", intro: "رحلة بلا كلمات نطاق."}
    stages:
      begin: {title: "البداية", what: "أول محطة.", voice: "مسار واحد وسجل واحد."}
    competencies:
      first_step: {title: "اتخذ الخطوة الأولى", good: "مسار واحد وسطر واحد."}
    lessons:
      F1:
        title: "الدرس الأول"
        know: "نص المعرفة."
        do: "نص التنفيذ."
        dont: "نص التحذير."
        steps:
          - {title: "افتح الصفحة", do: "افتح /fake/one."}
        question: "أي صفحة؟"
        options: ["الصفحة التجريبية", "صفحة أخرى"]
        explain: "نص الشرح."
    """
).strip()


class FakePackJourneyTests(SimpleTestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "fake" / "guide").mkdir(parents=True)
        (root / "fake" / "guide" / "guide.yaml").write_text(FAKE_GUIDE, encoding="utf-8")
        (root / "fake" / "guide" / "copy.en.yaml").write_text(FAKE_COPY_EN, encoding="utf-8")
        (root / "fake" / "guide" / "copy.ar.yaml").write_text(FAKE_COPY_AR, encoding="utf-8")
        # copy_for and check_pack also read the shared platform pack.
        (root / "_platform" / "guide").mkdir(parents=True)
        (root / "_platform" / "guide" / "guide.yaml").write_text(
            "pack: _platform\nversion: 2\nlessons: []\n", encoding="utf-8"
        )
        (root / "_platform" / "guide" / "copy.en.yaml").write_text("{}\n", encoding="utf-8")
        (root / "_platform" / "guide" / "copy.ar.yaml").write_text("{}\n", encoding="utf-8")
        self.patcher = patch.object(packs, "PACKS_ROOT", root)
        self.patcher.start()
        packs.clear_cache()

    def tearDown(self):
        self.patcher.stop()
        packs.clear_cache()
        self.tmp.cleanup()

    def test_fake_pack_passes_the_contract(self):
        self.assertEqual(contract.check_pack("fake", set()), [])

    def test_fake_pack_builds_a_journey_payload_without_carbon(self):
        payload = views._journey_payload("fake", "en")
        self.assertEqual(payload["title"], "Fake journey")
        self.assertEqual(payload["glossary"], ["flux capacitor"])
        self.assertEqual([row["key"] for row in payload["stages"]], ["begin"])
        self.assertEqual(payload["stages"][0]["title"], "Begin")
        self.assertEqual(payload["stages"][0]["voice"], "One route, one record.")
        self.assertEqual(payload["competencies"][0]["title"], "Take the first step")

    def test_fake_lesson_steps_render_from_copy(self):
        rows = [{"id": "F1", "title": "The first lesson"}]
        views._enrich_lessons("fake", "en", rows)
        self.assertEqual(rows[0]["completion"], "answer")
        self.assertEqual(rows[0]["steps"], [
            {"title": "Open the page", "do": "Open /fake/one.", "route": "/fake/one", "target": "fake.one"},
        ])
        # The listing carries display-only learning copy for the trail's hazard
        # cards and field notebook. It is never a figure and never a factor.
        self.assertEqual(rows[0]["know"], "Know text.")
        self.assertEqual(rows[0]["dont"], "Dont text.")

    def test_arabic_stage_voice_is_localized(self):
        ar = views._journey_payload("fake", "ar")
        self.assertEqual(ar["stages"][0]["voice"], "مسار واحد وسجل واحد.")

    def test_arabic_copy_is_mixed_and_keys_match(self):
        ar = views._journey_payload("fake", "ar")
        self.assertEqual(ar["competencies"][0]["title"], "اتخذ الخطوة الأولى")
        self.assertNotEqual(ar["title"], views._journey_payload("fake", "en")["title"])

    def test_engine_lists_the_fake_lesson_with_no_domain_word(self):
        loaded = packs.load_pack("fake")
        ctx = engine.Ctx(user=None, app_id="fake", caps=frozenset())
        out = engine.evaluate_lessons(ctx, loaded["lessons"], {}, __import__("datetime").datetime(2026, 10, 2))
        self.assertEqual([row["id"] for row in out["lessons"]], ["F1"])


FORBIDDEN = (
    "carbon", "emission", "leave", "payslip", "payroll", "loan", "gosi",
    "nibras", "eduos", "aastmt", "tectona", "medos", "إجازة", "قرض", "راتب",
)


class EngineIsDomainFreeTests(SimpleTestCase):
    """ADR-0050: the guide engine core carries no domain or brand vocabulary."""

    def test_engine_core_modules_have_no_domain_or_brand_words(self):
        root = Path(__file__).resolve().parent.parent
        for name in ("engine.py", "packs.py", "contract.py", "registry.py"):
            text = (root / name).read_text(encoding="utf-8").lower()
            for word in FORBIDDEN:
                self.assertNotIn(word, text, f"{name} contains forbidden word {word!r}")
