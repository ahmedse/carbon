"""Carbon guide pack over HTTP: scope, brand gate, writes, completion signals."""
from __future__ import annotations

import yaml
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import ScopedRole
from core.models import Module
from dataschema.models import DataRow, DataTable
from emissions.models import Calculation, InventorySource, InventorySourceStatus, ReportingPeriod
from guide import engine, packs
from guide.models import GuideProgress
from mdm.models import OrgUnit

User = get_user_model()
FORBIDDEN_KEYS = ("kg", "tonne", "factor_value", "co2e")


def _keys(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from _keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _keys(item)


@override_settings(DJANGO_BRAND="aastmt")
class CarbonGuideAPITests(APITestCase):
    def setUp(self):
        root = OrgUnit.objects.create(name="Guide University", slug="guide-univ")
        self.org = OrgUnit.objects.create(name="Guide Campus A", slug="guide-a", parent=root)
        self.other = OrgUnit.objects.create(name="Guide Campus B", slug="guide-b", parent=root)
        module = Module.objects.create(name="Guide Diesel", scope=1, org_unit=self.org)
        self.table = DataTable.objects.create(module=module, name="guide_diesel")
        self.period = ReportingPeriod.objects.create(
            name="FY26", start_date="2026-01-01", end_date="2026-12-31", status="open",
        )
        self.mine = InventorySource.objects.create(org_unit=self.org, scope=1, source_name="Guide generators")
        InventorySource.objects.create(org_unit=self.other, scope=2, source_name="Other electricity")
        InventorySourceStatus.objects.create(source=self.mine, reporting_period=self.period).linked_tables.add(self.table)
        self.owner = User.objects.create_user(username="guide_owner", password="unused")
        ScopedRole.objects.create(
            user=self.owner, org_unit=self.org,
            group=Group.objects.get_or_create(name="dataowners_group")[0], is_active=True,
        )
        self.plain = User.objects.create_user(username="guide_plain", password="unused")
        self.list_url = reverse("guide:list", args=["carbon"])

    def detail(self, lesson_id, **params):
        return self.client.get(reverse("guide:detail", args=["carbon", lesson_id]), params)

    def progress(self, lesson_id, **body):
        return self.client.post(reverse("guide:progress", args=["carbon", lesson_id]), body, format="json")

    # ── gate ────────────────────────────────────────────────────────────
    def test_unauthenticated(self):
        self.assertIn(self.client.get(self.list_url).status_code, (401, 403))

    @override_settings(DJANGO_BRAND="nibras")
    def test_app_not_enabled_for_brand_is_forbidden(self):
        # GUIDE-SEC-BRAND
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        self.assertEqual(self.progress("D1", event="started").status_code, 403)

    def test_app_without_a_pack_is_404(self):
        self.client.force_authenticate(self.owner)
        with override_settings(BRAND_APP_PRESETS={"aastmt": {"carbon": True, "healthy": True}}):
            self.assertEqual(self.client.get(reverse("guide:list", args=["healthy"])).status_code, 404)

    # ── who sees what ───────────────────────────────────────────────────
    def test_owner_gets_data_track_first(self):
        # GUIDE-COR-TRACKS
        self.client.force_authenticate(self.owner)
        data = self.client.get(self.list_url).json()
        ids = [r["id"] for r in data["lessons"]]
        self.assertEqual(ids[:3], ["D1", "D2", "D3"])
        self.assertNotIn("L2", ids)
        self.assertEqual(data["recommended_track"], "D")
        self.assertEqual(data["next_id"], "D1")
        stages = {r["id"]: r["stage"] for r in data["lessons"]}
        self.assertEqual(stages["D1"], "entry")
        self.assertEqual(stages["D2"], "entry")
        self.assertEqual(stages["D7"], "entry")
        self.assertEqual(stages["D3"], "")
        self.assertEqual(stages["D4"], "")
        self.assertNotIn("L2", stages)
        d = next(t for t in data["tracks"] if t["id"] == "D")
        self.assertTrue(d["title"])

    def test_plain_user_has_only_common_process_lessons(self):
        self.client.force_authenticate(self.plain)
        ids = {r["id"] for r in self.client.get(self.list_url).json()["lessons"]}
        self.assertEqual(ids, {"C2", "C3"})
        self.assertEqual(self.detail("D2").status_code, 404)
        self.assertEqual(self.progress("D2", event="started").status_code, 404)
        self.assertEqual(GuideProgress.objects.count(), 0)

    def test_superuser_sees_every_lesson_and_every_track(self):
        # GUIDE-COR-SUPERUSER: a wildcard caller reads all tracks and stations.
        su = User.objects.create_superuser(username="guide_su", password="unused")
        self.client.force_authenticate(su)
        data = self.client.get(self.list_url).json()
        self.assertTrue(data["all_tracks"])
        ids = {r["id"] for r in data["lessons"]}
        self.assertEqual(
            ids,
            {"D1", "D2", "D3", "D4", "D5", "D6", "D7", "C2", "C3",
             "L1", "L2", "L3", "L4", "L5", "L6", "L7"},
        )
        self.assertEqual({t["id"] for t in data["tracks"]}, {"C", "D", "L"})
        self.assertEqual(len(data["journey"]["stages"]), 7)
        # Reading every track does not fake completion: nothing is done yet.
        self.assertEqual({r["state"] for r in data["lessons"]}, {"offered"})

    # ── scope ───────────────────────────────────────────────────────────
    def test_scope_shows_only_my_sources(self):
        # GUIDE-COR-SCOPE
        self.client.force_authenticate(self.owner)
        live = self.detail("D1").json()["live"]
        self.assertEqual([r["name"] for r in live["items"]], ["Guide Diesel"])
        self.assertEqual(live["items"][0]["row_count"], 0)
        self.assertEqual(live["items"][0]["status"], "no_data")

    # ── payload hygiene ─────────────────────────────────────────────────
    def test_no_kilograms_in_payloads(self):
        # GUIDE-COR-NOKG
        self.client.force_authenticate(self.owner)
        payloads = [self.client.get(self.list_url).json()]
        for lid in ("D1", "D2", "D3", "C2"):
            payloads.append(self.detail(lid).json())
        for payload in payloads:
            for key in _keys(payload):
                self.assertFalse(any(w in key.lower() for w in FORBIDDEN_KEYS), key)

    def test_detail_hides_the_answer_and_checks_the_row(self):
        self.client.force_authenticate(self.owner)
        body = self.detail("D2").json()
        self.assertEqual(body["question"], {"kind": "host", "options": 0, "params": {}})
        self.assertIn("row you saved", body["copy"]["question"])
        self.assertNotIn("scope", body["copy"]["question"].lower())
        self.assertEqual(body["copy"].get("options") or [], [])
        self.assertNotIn("correct", body)

    def test_arabic_copy_and_english_fallback(self):
        self.client.force_authenticate(self.owner)
        ar = self.detail("D1", lang="ar").json()["copy"]
        en = self.detail("D1", lang="en").json()["copy"]
        self.assertNotEqual(ar["title"], en["title"])
        self.assertEqual(self.detail("D1", lang="fr").json()["copy"]["title"], en["title"])

    # ── journey contract ────────────────────────────────────────────────
    def test_listing_carries_the_journey_contract(self):
        self.client.force_authenticate(self.owner)
        data = self.client.get(self.list_url).json()
        journey = data["journey"]
        self.assertEqual(journey["title"], "Your carbon onboarding journey")
        self.assertTrue(journey["glossary"])
        keys = [row["key"] for row in journey["stages"]]
        self.assertEqual(
            keys,
            ["setup", "coverage", "data_products", "data_entry", "calculation", "lock", "report"],
        )
        by_id = {row["id"]: row for row in data["lessons"]}
        self.assertEqual(by_id["D2"]["completion"], "host")
        self.assertEqual(len(by_id["D2"]["steps"]), 3)
        self.assertEqual(by_id["D2"]["steps"][0]["route"], "/carbon/my-data")
        comps = {row["key"]: row for row in journey["competencies"]}
        self.assertEqual(comps["one_row"]["kind"], "host")
        self.assertEqual(comps["one_row"]["title"], "Save one activity row for your source")

    def test_arabic_journey_copy_is_mixed_language(self):
        self.client.force_authenticate(self.owner)
        ar = self.client.get(self.list_url, {"lang": "ar"}).json()["journey"]
        en = self.client.get(self.list_url).json()["journey"]
        self.assertNotEqual(ar["intro"], en["intro"])
        # Allowlisted domain terms stay English inside the Arabic copy by design.
        self.assertIn("reporting period", ar["intro"])

    def test_blocker_carries_copy_and_no_path_for_an_owner(self):
        self.client.force_authenticate(self.owner)
        self.period.status = "draft"
        self.period.save()
        row = next(r for r in self.client.get(self.list_url).json()["lessons"] if r["id"] == "D2")
        self.assertEqual(row["blocker"]["code"], "no_open_period")
        self.assertIsNone(row["blocker"]["path"])
        self.assertTrue(row["blocker"]["title"])

    # ── writes ──────────────────────────────────────────────────────────
    def test_get_writes_nothing(self):
        # GUIDE-SEC-WRITE (read side)
        self.client.force_authenticate(self.owner)
        self.client.get(self.list_url)
        self.detail("D2")
        self.assertEqual(GuideProgress.objects.count(), 0)

    def test_post_writes_only_guide_progress(self):
        # GUIDE-SEC-WRITE (write side)
        self.client.force_authenticate(self.owner)
        before = (DataRow.objects.count(), Calculation.objects.count(), InventorySourceStatus.objects.count())
        self.assertEqual(self.progress("D2", event="started").status_code, 200)
        self.assertEqual(self.progress("D2", event="check").status_code, 200)
        after = (DataRow.objects.count(), Calculation.objects.count(), InventorySourceStatus.objects.count())
        self.assertEqual(before, after)

    def test_bad_events_are_rejected(self):
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.progress("D2", event="finish").status_code, 400)
        self.assertEqual(self.progress("D2", event="answered", choice=0).status_code, 400)
        for bad in (9, -1, "a", True):
            self.assertEqual(self.progress("D1", event="answered", choice=bad).status_code, 400)
        self.assertEqual(GuideProgress.objects.count(), 0)

    # ── completion ──────────────────────────────────────────────────────
    def test_wrong_answer_does_not_complete(self):
        self.client.force_authenticate(self.owner)
        out = self.progress("D1", event="answered", choice=2).json()
        self.assertEqual((out["correct"], out["state"]), (False, "started"))
        again = self.progress("D1", event="answered", choice=2)
        self.assertEqual(again.status_code, 200)
        self.assertEqual((again.json()["correct"], again.json()["state"]), (False, "started"))

    def test_a_second_host_check_is_allowed_until_the_row_exists(self):
        self.client.force_authenticate(self.owner)
        self.progress("D2", event="started")
        first = self.progress("D2", event="check")
        second = self.progress("D2", event="check")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual((second.json()["correct"], second.json()["state"], second.json()["waiting"]), (None, "started", "host"))
        self.assertEqual(GuideProgress.objects.get(lesson_id="D2").state, "started")

    def test_answer_only_lesson_completes(self):
        # GUIDE-COR-DONE (answer)
        self.client.force_authenticate(self.owner)
        out = self.progress("D1", event="answered", choice=0).json()
        self.assertEqual((out["correct"], out["state"]), (True, "done"))
        self.assertEqual(GuideProgress.objects.get(lesson_id="D1").signal, "answer")
        self.assertEqual(self.progress("D1", event="answered", choice=2).json()["state"], "done")

    def test_d2_needs_a_real_row_after_start(self):
        # GUIDE-COR-DONE (host row): the check is the saved row, not a quiz
        self.client.force_authenticate(self.owner)
        DataRow.objects.create(data_table=self.table, values={"litres": 1}, created_by=self.owner)
        self.progress("D2", event="started")
        waiting = self.progress("D2", event="check").json()
        self.assertEqual((waiting["correct"], waiting["state"], waiting["waiting"]), (None, "started", "host"))
        DataRow.objects.create(data_table=self.table, values={"litres": 2}, created_by=self.owner)
        done = self.progress("D2", event="check").json()
        self.assertEqual((done["correct"], done["state"], done["waiting"]), (None, "done", None))
        self.assertEqual(GuideProgress.objects.get(lesson_id="D2").signal, "host_row")

    def test_someone_elses_row_does_not_count(self):
        self.client.force_authenticate(self.owner)
        self.progress("D2", event="started")
        DataRow.objects.create(data_table=self.table, values={"litres": 2}, created_by=self.plain)
        self.assertEqual(self.progress("D2", event="check").json()["state"], "started")

    def test_wrong_answer_does_not_also_wait(self):
        from django.utils import timezone

        from guide import engine

        self.client.force_authenticate(self.owner)
        lesson = {
            "id": "ZX", "pack": "carbon", "version": 1,
            "question": {"kind": "static", "options": 3, "correct": 0},
            "host": "row_created",
        }
        ctx = engine.Ctx(self.owner, "carbon", frozenset(["carbon:enter_data"]))
        now = timezone.now()
        first = engine.apply_event(ctx, lesson, "answered", 0, now)
        self.assertEqual((first["correct"], first["waiting"], first["state"]), (True, "host", "started"))
        second = engine.apply_event(ctx, lesson, "answered", 1, now)
        self.assertEqual(second["correct"], False)
        self.assertIsNone(second["waiting"])

    def test_progress_is_per_user(self):
        self.client.force_authenticate(self.owner)
        self.progress("D1", event="answered", choice=0)
        self.client.force_authenticate(self.plain)
        self.progress("C2", event="started")
        self.assertEqual(GuideProgress.objects.filter(user=self.owner).count(), 1)
        self.client.force_authenticate(self.owner)
        states = {r["id"]: r["state"] for r in self.client.get(self.list_url).json()["lessons"]}
        self.assertEqual((states["D1"], states["C2"]), ("done", "offered"))

    def test_snooze_moves_next_on(self):
        self.client.force_authenticate(self.owner)
        self.progress("D1", event="snooze")
        listing = self.client.get(self.list_url).json()
        self.assertEqual(next(r for r in listing["lessons"] if r["id"] == "D1")["state"], "snoozed")
        self.assertEqual(listing["next_id"], "D2")


class CarbonGuidePackDisplayTests(SimpleTestCase):
    """The pack journey blocks (stages, competencies, steps) are engine-read."""

    def _raw(self):
        path = packs.pack_dir("carbon") / "guide.yaml"
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def test_stage_map_is_a_seven_stage_spine_over_known_lessons(self):
        raw = self._raw()
        stages = raw["stages"]
        self.assertEqual([row["n"] for row in stages], [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(len({row["key"] for row in stages}), 7)
        known = {row["id"] for row in raw["lessons"]}
        placed: list[str] = []
        for row in stages:
            members = list(row.get("lessons") or [])
            for lesson_id in members:
                self.assertIn(lesson_id, known)
            if row.get("pending"):
                self.assertEqual(members, [])
                self.assertEqual(row["key"], "data_products")
            placed.extend(sorted(members))
        # Every pack lesson sits in exactly one journey stage.
        self.assertEqual(sorted(placed), sorted(known))
        self.assertEqual(len(placed), len(set(placed)))

    def test_journey_blocks_load_and_choose_next_staging_is_unchanged(self):
        loaded = packs.load_pack("carbon")
        # The journey blocks are now part of the engine pack shape.
        self.assertEqual(len(loaded["stages"]), 7)
        self.assertTrue(loaded["competencies"])
        self.assertTrue(loaded["journey"]["glossary"])
        by_id = {row["id"]: row for row in loaded["lessons"]}
        # The per-lesson `stage:` key that _choose_next reads is unchanged.
        self.assertEqual([by_id[i].get("stage") for i in ("D1", "D2", "D7")], ["entry"] * 3)
        self.assertFalse(by_id["D3"].get("stage"))
        self.assertFalse(by_id["D4"].get("stage"))
        # D2 is not renamed; its completion is declared by the pack.
        self.assertEqual(by_id["D2"]["completion"], "host")
        self.assertTrue(by_id["D2"]["steps"])
        rows = [
            {"id": "D1", "stage": "entry", "state": "offered", "blocker": None},
            {"id": "D3", "stage": "", "state": "offered", "blocker": None},
        ]
        self.assertEqual(engine._choose_next(rows), "D1")
