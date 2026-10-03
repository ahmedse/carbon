"""IB-01 … IB-11 — intention banks are discovered, live, bilingual, honestly scored.

Phase 3 (PULSE-INTENTION-CONTRACT §5). These tests pin four things:

* **Discovery.** A new bank is a YAML, never an edit to a hardcoded tuple in
  two places: the runner, the bench, and these tests read one registry
  (``chat_deep_bench.discover_intention_banks``). IB-04/IB-05 load exactly as
  before.
* **Shape.** Each bank declares the contract's sample size, language mix, and
  threshold, and the YAML actually carries that many bilingual threads/turns.
* **Honest status (RULE_36).** No live run is ``missing`` (never zero-fail);
  fewer than ``CLOSE_RUNS`` full runs is ``partial``; only three consecutive
  full runs make a bank ``reached``; a later fail reopens it. IB-06 (write)
  stays ``missing`` without STACK-HOLD; IB-09 is unit and reported apart.
* **Not merged.** The intention block is its own key; it never moves a Chat
  objective or the Ask 10/10 score.
"""
from __future__ import annotations

import json
import re

from ai.eval import chat_deep_bench as cdb
from ai.eval.chat_intention_retest import BANKS, bank_is_write, main as retest_main, pack_problem
from ai.eval.chat_retest import load_bank, load_bank_doc

_ARABIC = re.compile(r"[\u0600-\u06FF]")

#: The live banks the contract defines, with its exact §5 sample size and mix.
#: ``axis`` says whether the EN/AR split is counted per thread or per turn;
#: ``None`` means mixed (both languages present, no fixed split).
CONTRACT_BANKS: dict[str, dict] = {
    "IB-01": {"threads": 8, "turns": 16, "en": 4, "ar": 4, "axis": "threads"},
    "IB-02": {"threads": 8, "turns": 12, "en": 6, "ar": 6, "axis": "turns"},
    "IB-03": {"threads": 12, "turns": 12, "en": 6, "ar": 6, "axis": "threads"},
    "IB-04": {"threads": 10, "turns": 10, "en": 5, "ar": 5, "axis": "threads"},
    "IB-05": {"threads": 10, "turns": 10, "en": 5, "ar": 5, "axis": "threads"},
    "IB-06": {"threads": 4, "turns": 4, "en": 2, "ar": 2, "axis": "threads"},
    "IB-07": {"threads": 8, "turns": 16, "en": 4, "ar": 4, "axis": "threads"},
    "IB-08": {"threads": 16, "turns": 16, "en": 8, "ar": 8, "axis": "threads"},
    "IB-10": {"threads": 11, "turns": 34, "en": None, "ar": None, "axis": None},
    "IB-11": {"threads": 8, "turns": 24, "en": 4, "ar": 4, "axis": "threads"},
    # IB-12 is the IR5 locked paraphrase bank: 6 intents x (5 EN + 5 AR).
    "IB-12": {"threads": 12, "turns": 60, "en": 6, "ar": 6, "axis": "threads"},
}

#: IB-01 … IB-05, IB-07, IB-08, IB-10, IB-11, IB-12 are read-only; only IB-06 writes.
READ_ONLY_BANKS = frozenset(CONTRACT_BANKS) - {"IB-06"}


# ── helpers ────────────────────────────────────────────────────────────────


def _threads(bank_id: str) -> list[dict]:
    return load_bank(BANKS[bank_id])


def _turns(bank_id: str) -> list[dict]:
    return [turn for thread in _threads(bank_id) for turn in thread["turns"]]


def _rows(bank_id: str) -> int:
    """Scored rows: a thread mirrored across ``modes`` runs once per dial."""
    return sum(len(t["turns"]) * len(t.get("modes") or [1]) for t in _threads(bank_id))


def _is_ar(text: str) -> bool:
    return bool(_ARABIC.search(text))


def _split(bank_id: str, axis: str) -> tuple[int, int]:
    if axis == "turns":
        items = [t["say"] for t in _turns(bank_id)]
    else:
        items = [t["turns"][0]["say"] for t in _threads(bank_id)]
    ar = sum(1 for s in items if _is_ar(s))
    return len(items) - ar, ar


def _write_run(root, bank_id: str, run_at: str, thread_passes: list[bool], tier: str = "live_intention") -> None:
    payload = {
        "tier": tier,
        "bank": bank_id,
        "run_at": run_at,
        "threads": [{"pass": ok, "turns": []} for ok in thread_passes],
    }
    stamp = run_at.replace(":", "").replace("-", "")
    (root / f"PV2-intention-{bank_id.replace('-', '')}-{stamp}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _paraphrase_run(
    *,
    en_total: int = 30,
    en_pass: int = 30,
    ar_total: int = 30,
    ar_pass: int = 30,
    fallthrough: int = 0,
    ungrounded: int = 0,
) -> dict:
    """A synthetic live run of the IB-12 shape, with real per-turn rows."""

    def _turns(total: int, passed: int, lang: str) -> list[dict]:
        rows = []
        for i in range(total):
            misses: list[str] = []
            if fallthrough and i == 0:
                misses.append("no_fallthrough got=fallthrough")
            if ungrounded and i == 0:
                misses.append("numbers_grounded ['999']")
            if i >= passed and not misses:
                misses.append("contains entity")
            say = f"سؤال {lang} {i}" if lang == "ar" else f"paraphrase {lang} {i}"
            rows.append({
                "say": say,
                "pass": not misses,
                "misses": misses,
                "fell_through": bool(fallthrough and i == 0),
            })
        return rows

    return {
        "threads": [
            {"id": "IB-12-en", "pass": en_pass == en_total, "turns": _turns(en_total, en_pass, "en")},
            {"id": "IB-12-ar", "pass": ar_pass == ar_total, "turns": _turns(ar_total, ar_pass, "ar")},
        ],
    }


def _write_paraphrase_run(root, run_at: str, bank_id: str = "IB-12", **kwargs) -> None:
    payload = {"tier": "live_intention", "bank": bank_id, "run_at": run_at, **_paraphrase_run(**kwargs)}
    stamp = run_at.replace(":", "").replace("-", "")
    (root / f"PV2-intention-{bank_id.replace('-', '')}-{stamp}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


# ── registry / discovery ───────────────────────────────────────────────────


def test_registry_is_discovered_from_the_bank_glob():
    """One registry: the runner and the bench read the same discovered glob."""
    globbed = cdb.INTENTION_BANKS_DIR.glob(cdb.INTENTION_BANK_GLOB)
    discovered = cdb.discover_intention_banks()
    expected = {}
    for path in globbed:
        match = re.match(r"chat_intention_bank_(ib\d{2})\.yaml$", path.name)
        if match:
            expected[f"IB-{match.group(1)[2:]}"] = path
    assert set(discovered) == set(expected)
    assert set(BANKS) == set(discovered)
    assert tuple(BANKS) == cdb.INTENTION_BANKS
    # IB-04/IB-05 keep loading exactly as before, now via discovery.
    assert {"IB-04", "IB-05"} <= set(BANKS)
    # IB-09 is a unit bank (pytest); it has no live YAML.
    assert "IB-09" not in BANKS
    assert cdb.INTENTION_UNIT_BANKS == ("IB-09",)


def test_discovery_picks_up_a_new_bank_without_code_edits(tmp_path):
    (tmp_path / "chat_intention_bank_ib42.yaml").write_text("threads: []\n", encoding="utf-8")
    (tmp_path / "chat_intention_bank_ib99.yaml").write_text("threads: []\n", encoding="utf-8")
    # Non-conforming names are ignored: not a bank.
    (tmp_path / "chat_intention_bank_ib1.yaml").write_text("threads: []\n", encoding="utf-8")
    (tmp_path / "chat_intention_bank_foo.yaml").write_text("threads: []\n", encoding="utf-8")
    found = cdb.discover_intention_banks(tmp_path)
    assert set(found) == {"IB-42", "IB-99"}
    assert found["IB-42"].name == "chat_intention_bank_ib42.yaml"


# ── shape + language mix (contract §5) ─────────────────────────────────────


def test_contract_banks_exist_with_the_exact_sample_size_and_mix():
    assert set(CONTRACT_BANKS) == set(BANKS)
    for bank_id, spec in CONTRACT_BANKS.items():
        threads = _threads(bank_id)
        assert len(threads) == spec["threads"], f"{bank_id} threads"
        assert _rows(bank_id) == spec["turns"], f"{bank_id} scored rows"
        if spec["axis"] is None:
            en, ar = _split(bank_id, "turns")
            assert en > 0 and ar > 0, f"{bank_id} must be bilingual"
            assert _rows(bank_id) >= 30, f"{bank_id} needs M >= 30 recorded turns"
        else:
            en, ar = _split(bank_id, spec["axis"])
            assert (en, ar) == (spec["en"], spec["ar"]), f"{bank_id} {spec['axis']} mix"


def test_declared_metadata_matches_the_content():
    """Where a bank declares its size, the declaration is true (no placeholder)."""
    for bank_id, path in BANKS.items():
        doc = load_bank_doc(path)
        if "sample_threads" in doc:
            assert doc["sample_threads"] == len(_threads(bank_id)), bank_id
        if "sample_turns" in doc:
            assert doc["sample_turns"] == _rows(bank_id), bank_id
        if "tier" in doc:
            assert doc["tier"] in {"live_intention", "live_intention_write"}, bank_id
        if "bank" in doc:  # IB-04/IB-05 are bare thread docs (kept as-is)
            assert doc.get("threshold"), f"{bank_id} must state its pass threshold"


def test_every_bank_is_bilingual():
    for bank_id in BANKS:
        says = [t["say"] for t in _turns(bank_id)]
        assert any(_is_ar(s) for s in says), f"{bank_id} has no Arabic turn"
        assert any(not _is_ar(s) for s in says), f"{bank_id} has no English turn"


# ── per-bank checks (contract §5 axes) ─────────────────────────────────────


def test_ib01_grounds_every_figure():
    """IRP-5: every figure in the reply is in the tool/host payload."""
    for turn in _turns("IB-01"):
        assert turn.get("numbers_grounded") is True
        assert turn.get("ground_objects"), "grounding needs the host oracle(s)"
        assert turn.get("not_degraded") is True


def test_ib02_language_follows_the_message_incl_refusal_and_clarify():
    """IRP-7: reply language = message language, on reads, refusals, clarify."""
    turns = _turns("IB-02")
    assert all(t.get("language") in {"en", "ar"} for t in turns)
    refused = [t for t in turns if t.get("decision_is") == "refuse"]
    clarify = [t for t in turns if t.get("decision_is") == "clarify"]
    assert len(refused) == 2 and len(clarify) == 2, "EN+AR refusal and clamp each"
    for want in ("en", "ar"):
        assert any(t.get("language") == want for t in refused)
        assert any(t.get("language") == want for t in clarify)


def test_ib03_answers_the_field_or_says_unknown_without_a_raw_dump():
    """IF-04/IF-05: field present or explicit unknown; no raw-record dump."""
    turns = _turns("IB-03")
    for turn in turns:
        assert turn.get("no_raw_dump") is True, turn.get("say")
        assert turn.get("field_or_unknown") or turn.get("unknown_required"), turn.get("say")
    absent = [t for t in turns if t.get("unknown_required")]
    assert len(absent) >= 2, "IB-03 must include the absent-field case (EN + AR)"
    says = [t["say"] for t in absent]
    assert any(_is_ar(s) for s in says) and any(not _is_ar(s) for s in says)


def test_ib07_read_never_gets_a_plan_card_and_goals_get_a_plan():
    """IF-06: mirrored in both dials; read -> no plan card; goal -> one plan/handoff."""
    threads = _threads("IB-07")
    reads = [t for t in threads if t["turns"][0].get("no_plan_card")]
    goals = [t for t in threads if t["turns"][0].get("plan_or_handoff")]
    assert len(reads) == 4 and len(goals) == 4, "IB-07 is 4 reads + 4 goals"
    for thread in threads:
        assert thread.get("modes") == ["ask", "plan"], thread["id"]
        assert len(thread["turns"]) == 1
        for turn in thread["turns"]:
            assert turn.get("not_degraded") is True, thread["id"]
    assert _rows("IB-07") == 16
    # A read is never a plan card; a goal is a plan or a handoff, never a write.
    for thread in reads:
        assert all(t.get("no_plan_card") for t in thread["turns"])
        assert all(not t.get("plan_or_handoff") for t in thread["turns"])
    for thread in goals:
        assert all(t.get("plan_or_handoff") for t in thread["turns"])


def test_ib08_declares_two_bilingual_surfaces():
    """IF-07: 8 threads per surface, 4 EN / 4 AR each, in-scope + register."""
    threads = _threads("IB-08")
    surfaces = {t.get("surface") for t in threads}
    assert surfaces == {"coworker", "tutor"}
    for surface in surfaces:
        rows = [t for t in threads if t.get("surface") == surface]
        assert len(rows) == 8, surface
        says = [t["turns"][0]["say"] for t in rows]
        assert sum(1 for s in says if _is_ar(s)) == 4
        assert sum(1 for s in says if not _is_ar(s)) == 4
    for turn in _turns("IB-08"):
        assert "refuse" in (turn.get("decision_not") or []), turn.get("say")
        assert turn.get("not_degraded") is True, turn.get("say")


def test_ib10_ledger_flags_every_turn_and_clears_the_size_bar():
    """IRP-8/IF-08: M >= 30 recorded turns, every one marked no_fallthrough."""
    turns = _turns("IB-10")
    assert len(turns) >= 30
    assert all(t.get("no_fallthrough") is True for t in turns)
    says = [t["say"] for t in turns]
    assert any(_is_ar(s) for s in says) and any(not _is_ar(s) for s in says)


def test_ib11_is_three_paraphrases_per_thread_bilingual():
    """IF-09: same question x 3 phrasings; one figure all three times."""
    threads = _threads("IB-11")
    assert len(threads) == 8
    for thread in threads:
        assert thread.get("stable") is True, thread["id"]
        assert len(thread["turns"]) == 3, thread["id"]
        for turn in thread["turns"]:
            assert turn.get("numbers_grounded") is True
            assert turn.get("ground_objects"), thread["id"]
    says = [t["turns"][0]["say"] for t in threads]
    assert sum(1 for s in says if _is_ar(s)) == 4
    assert sum(1 for s in says if not _is_ar(s)) == 4


# ── IB-12: the IR5 locked, held-out paraphrase bank ────────────────────────


def test_ib12_is_locked_bilingual_and_paired_five_paraphrases_per_intent():
    """Six intents, one EN + one AR thread each, five unseen paraphrases a side."""
    doc = load_bank_doc(BANKS["IB-12"])
    assert doc.get("locked") is True, "the IR5 bank is held out"
    threads = _threads("IB-12")
    by_intent: dict[str, dict[str, dict]] = {}
    for thread in threads:
        side = "ar" if _is_ar(thread["turns"][0]["say"]) else "en"
        by_intent.setdefault(thread["intent"], {})[side] = thread
    assert set(by_intent) == {"name", "no", "title", "salary", "leave", "oos"}
    for intent, pair in by_intent.items():
        assert set(pair) == {"en", "ar"}, intent
        for side, thread in pair.items():
            assert len(thread["turns"]) == 5, (intent, side)
    # Entity + figure grounding where a figure is expected.
    for thread in threads:
        for turn in thread["turns"]:
            assert turn.get("no_fallthrough") is True, thread["id"]
            assert turn.get("not_degraded") is True, thread["id"]
            if thread["intent"] == "oos":
                assert turn.get("decision_is") == "refuse", thread["id"]
                continue
            assert turn.get("contains"), thread["id"]
            if thread["intent"] in {"salary", "leave", "no"}:
                assert turn.get("numbers_grounded") is True, thread["id"]
                assert turn.get("ground_objects"), thread["id"]


def test_ib12_declares_the_ir5_gate_in_its_yaml():
    doc = load_bank_doc(BANKS["IB-12"])
    gate = doc.get("gate") or {}
    assert gate.get("kind") == "paraphrase"
    assert float(gate.get("accuracy")) == 0.95
    assert float(gate.get("parity")) == 0.98
    assert int(gate.get("fallthrough")) == 0
    assert int(gate.get("ungrounded")) == 0


def test_ib12_gate_is_discovered_not_hardcoded():
    """The scorer reads the id from the YAML; tests read the same registry."""
    gates = cdb.intention_gate_banks()
    assert "IB-12" in gates
    assert gates["IB-12"]["kind"] == "paraphrase"
    # Discovery is by ``gate.kind``, not a fixed tuple.
    assert all(g.get("kind") == "paraphrase" for g in gates.values())


def test_ib12_is_held_out_from_the_engine():
    """The locked bank's phrasing never appears in ``engine/**`` (ADR-0050)."""
    engine = cdb.INTENTION_BANKS_DIR.parent / "engine"
    blobs = [
        p.read_text(encoding="utf-8", errors="ignore")
        for p in engine.rglob("*")
        if p.is_file() and p.suffix in {".py", ".yaml"}
    ]
    corpus = "\n".join(blobs)
    for thread in _threads("IB-12"):
        for turn in thread["turns"]:
            assert turn["say"] not in corpus, turn["say"]


def test_ib12_paraphrase_score_formula():
    """accuracy = correct/turns; parity = 1 - |accuracy_ar - accuracy_en|."""
    score = cdb.paraphrase_run_score(_paraphrase_run(en_pass=28, ar_pass=30))
    assert score["turns"] == 60
    assert score["correct"] == 58
    assert score["accuracy"] == 0.9667
    assert score["accuracy_en"] == 0.9333
    assert score["accuracy_ar"] == 1.0
    assert score["parity"] == 0.9333
    assert score["parity_gap"] == 0.0667
    assert score["fallthrough"] == 0
    assert score["ungrounded"] == 0
    # A run with no recorded turns is missing, never zero-fail.
    assert cdb.paraphrase_run_score({"threads": []})["status"] == "missing"


def test_ib12_threshold_wiring_accuracy_parity_fallthrough_grounding():
    gate = cdb.intention_gate_banks()["IB-12"]
    assert cdb.paraphrase_run_pass(cdb.paraphrase_run_score(_paraphrase_run()), gate)
    # Accuracy clears the bar but the language gap breaks parity (2 EN misses).
    skewed = cdb.paraphrase_run_score(_paraphrase_run(en_pass=28, ar_pass=30))
    assert skewed["accuracy"] >= 0.95 and skewed["parity"] < 0.98
    assert not cdb.paraphrase_run_pass(skewed, gate)
    # Balanced misses keep parity but drop accuracy below the bar.
    low = cdb.paraphrase_run_score(_paraphrase_run(en_pass=25, ar_pass=25))
    assert low["accuracy"] < 0.95 and low["parity"] == 1.0
    assert not cdb.paraphrase_run_pass(low, gate)
    # One fallthrough or one ungrounded figure fails even at full accuracy.
    assert not cdb.paraphrase_run_pass(
        cdb.paraphrase_run_score(_paraphrase_run(fallthrough=1)), gate
    )
    assert not cdb.paraphrase_run_pass(
        cdb.paraphrase_run_score(_paraphrase_run(ungrounded=1)), gate
    )


def test_ib12_honest_status_missing_partial_reached_and_reopen(tmp_path):
    report = cdb.intention_banks(tmp_path)
    assert report["banks"]["IB-12"]["status"] == "missing"
    assert report["banks"]["IB-12"]["passed"] == 0
    assert "IB-12" in report["paraphrase"]
    assert report["paraphrase"]["IB-12"]["status"] == "missing"
    assert report["ir5"] == "not reached"

    _write_paraphrase_run(tmp_path, "2026-10-01T10:00:00+00:00")
    assert cdb.intention_banks(tmp_path)["banks"]["IB-12"]["status"] == "partial"

    _write_paraphrase_run(tmp_path, "2026-10-02T10:00:00+00:00")
    _write_paraphrase_run(tmp_path, "2026-10-03T10:00:00+00:00")
    reached = cdb.intention_banks(tmp_path)
    assert reached["banks"]["IB-12"]["status"] == "reached"
    assert reached["banks"]["IB-12"]["score"]["accuracy"] == 1.0
    assert reached["banks"]["IB-12"]["gate"]["kind"] == "paraphrase"

    # A later threshold miss reopens the bank.
    _write_paraphrase_run(tmp_path, "2026-10-04T10:00:00+00:00", en_pass=25, ar_pass=25)
    reopened = cdb.intention_banks(tmp_path)
    assert reopened["banks"]["IB-12"]["status"] == "fail"
    assert reopened["ir5"] == "not reached"


# ── IB-06 stays missing (write bank) ───────────────────────────────────────


def test_ib06_is_a_declared_write_bank():
    doc = load_bank_doc(BANKS["IB-06"])
    assert doc.get("write") is True
    assert doc.get("tier") == "live_intention_write"
    assert bank_is_write("IB-06") is True
    assert all(bank_is_write(b) is False for b in READ_ONLY_BANKS)


def test_ib06_never_runs_without_a_stack_hold(capsys):
    """Chat never host-mutates (ADR-0046): no STACK-HOLD -> the bank is skipped."""
    code = retest_main(["--bank", "IB-06", "--no-write"])
    out = capsys.readouterr().out
    assert code == 0
    assert "SKIP IB-06" in out
    # No release/health probe ran: a skipped write bank never touches the network.
    assert "wrote" not in out


def test_ib06_stays_missing_even_with_write_tier_evidence(tmp_path):
    """A write-tier run is not a ``live_intention`` run: it never reaches IB-06."""
    _write_run(tmp_path, "IB-06", "2026-10-03T10:00:00+00:00", [True], tier="live_intention_write")
    report = cdb.intention_banks(tmp_path)
    assert report["banks"]["IB-06"]["status"] == "missing"
    assert report["if_03"] == "missing"


# ── honest status (RULE_36) ────────────────────────────────────────────────


def test_pack_problem_refuses_any_non_nibras_process():
    assert pack_problem({"pack": "carbon", "pulse_enabled": True}) is not None
    assert pack_problem({"pack": "nibras", "pulse_enabled": False}) is not None
    assert pack_problem({"pack": "nibras", "pulse_enabled": True}) is None


def test_no_live_run_is_missing_not_zero_fail(tmp_path):
    report = cdb.intention_banks(tmp_path)
    for bank_id in READ_ONLY_BANKS:
        assert report["banks"][bank_id]["status"] == "missing", bank_id
        assert report["banks"][bank_id]["passed"] == 0
    assert report["if_01"] == "missing"
    assert report["if_02"] == "missing"
    assert report["if_03"] == "missing"
    assert report["ir2"] == "not reached"
    assert report["ir3"] == "not reached"
    assert report["ir4"] == "not reached"
    assert report["ir5"] == "not reached"


def test_three_consecutive_full_runs_reach_a_bank(tmp_path):
    for day in ("01", "02", "03"):
        stamp = f"2026-10-{day}T10:00:00+00:00"
        _write_run(tmp_path, "IB-01", stamp, [True, True])
        _write_run(tmp_path, "IB-02", stamp, [True, True])
        _write_run(tmp_path, "IB-03", stamp, [True, True])
        _write_run(tmp_path, "IB-04", stamp, [True, True])
        _write_run(tmp_path, "IB-05", stamp, [True, True])
        _write_run(tmp_path, "IB-07", stamp, [True, True])
        _write_run(tmp_path, "IB-08", stamp, [True, True])
        _write_run(tmp_path, "IB-10", stamp, [True])
        _write_run(tmp_path, "IB-11", stamp, [True, True])
        _write_paraphrase_run(tmp_path, stamp)
    report = cdb.intention_banks(tmp_path)
    for bank_id in READ_ONLY_BANKS:
        assert report["banks"][bank_id]["status"] == "reached", bank_id
    assert report["if_01"] == "fixed"
    assert report["if_02"] == "fixed"
    assert report["if_04"] == "fixed"
    assert report["if_06"] == "pending"  # IB-06 has no run
    assert report["if_08"] == "fixed"
    assert report["if_09"] == "fixed"
    assert report["ir1"] == "reached"
    assert report["ir2"] == "reached"
    assert report["ir3"] == "reached"
    assert report["ir4"] == "reached"
    # IR5 = IB-10 + IB-11 + the locked paraphrase bank (IB-12), all reached.
    assert report["ir5"] == "reached"


def test_ir5_is_not_reached_without_the_paraphrase_bank(tmp_path):
    """IR5 needs the locked bank: IB-10 + IB-11 alone never reach it."""
    for day in ("01", "02", "03"):
        stamp = f"2026-10-{day}T10:00:00+00:00"
        _write_run(tmp_path, "IB-10", stamp, [True])
        _write_run(tmp_path, "IB-11", stamp, [True, True])
    report = cdb.intention_banks(tmp_path)
    assert report["banks"]["IB-10"]["status"] == "reached"
    assert report["banks"]["IB-11"]["status"] == "reached"
    assert report["banks"]["IB-12"]["status"] == "missing"
    assert report["ir5"] == "not reached"


def test_fewer_than_three_runs_stays_partial(tmp_path):
    _write_run(tmp_path, "IB-04", "2026-10-01T10:00:00+00:00", [True])
    report = cdb.intention_banks(tmp_path)
    assert report["banks"]["IB-04"]["status"] == "partial"
    assert report["if_02"] == "pending"
    assert report["ir2"] == "not reached"


def test_a_later_failing_run_reopens_the_class(tmp_path):
    for day in ("01", "02"):
        _write_run(tmp_path, "IB-04", f"2026-10-{day}T10:00:00+00:00", [True])
    _write_run(tmp_path, "IB-04", "2026-10-03T10:00:00+00:00", [False])
    report = cdb.intention_banks(tmp_path)
    assert report["banks"]["IB-04"]["status"] == "fail"
    assert report["if_02"] == "seen"


def test_a_failure_below_a_passing_level_does_not_hide_it(tmp_path):
    """No level is inferred: IR1 reached while IR2/IR3 stay not reached."""
    for day in ("01", "02", "03"):
        _write_run(tmp_path, "IB-10", f"2026-10-{day}T10:00:00+00:00", [True])
    report = cdb.intention_banks(tmp_path)
    assert report["banks"]["IB-10"]["status"] == "reached"
    assert report["ir1"] == "reached"
    assert report["ir2"] == "not reached"
    assert report["banks"]["IB-04"]["status"] == "missing"


def test_if_taxonomy_covers_the_nine_failure_classes():
    assert set(cdb.INTENTION_IF_OWNERS) == {f"if_0{i}" for i in range(1, 10)}
    for name, owners in cdb.INTENTION_IF_OWNERS.items():
        assert owners, name
        for owner in owners:
            assert owner in cdb.INTENTION_BANKS or owner in cdb.INTENTION_UNIT_BANKS, name


def test_intention_is_reported_not_merged_into_the_ask_score():
    """RULE_36: the intention block is its own key; it never moves the ask rows."""
    report = cdb.score_chat_bench()
    assert "intention" in report
    assert report["n_objectives"] == 10
    assert all(row["id"] not in cdb.INTENTION_BANKS for row in report["objectives"])


# ── IB-02 language: the copy decides, not a host proper noun ────────────────


class _HostStub:
    """The bits of ``Host`` the language check reads (no network)."""

    def me(self) -> dict:
        return {"department": "Coiled Tubing", "job_title": "Heavy Duty Driver"}

    def resolve(self, ref: str):
        return ""

    def obj(self, ref: str):
        return {}


def _check_language(value: str, reply: str, meta: dict) -> list[str]:
    from ai.eval.chat_retest import check_turn

    return check_turn({"language": value}, reply, meta, _HostStub())


def test_ib02_language_reads_the_copy_not_the_host_proper_noun():
    """IRP-7: an Arabic table whose cell is an English host value is Arabic."""
    meta = {"tool_digest": (
        "call_host_api get_my_profile: employee_no=1067, "
        "department=Coiled Tubing, job_title=Heavy Duty Driver"
    )}
    reply = "| الإدارة |\n| --- |\n| Coiled Tubing |"
    assert _check_language("ar", reply, meta) == []


def test_ib02_language_still_fails_a_genuinely_wrong_language_reply():
    """The fix must not launder a reply that is really in the other language."""
    meta = {"tool_digest": (
        "call_host_api get_my_profile: department=Coiled Tubing"
    )}
    # An Arabic question answered in English prose (host value aside) still fails.
    assert any(
        m.startswith("language")
        for m in _check_language("ar", "Your department is Coiled Tubing.", meta)
    )
    # No host payload at all: nothing to set aside, the English reply fails.
    assert any(
        m.startswith("language")
        for m in _check_language("ar", "Your leave balance is 18 days.", {})
    )


def test_ib02_language_ignores_numeric_payloads_only():
    """Numbers never carry a language; Latin words always do."""
    meta = {"tool_digest": "call_host_api get_my_leave_balance: annual remaining=18"}
    assert _check_language("ar", "رصيد إجازاتك السنوية 18", meta) == []
    assert any(
        m.startswith("language")
        for m in _check_language("ar", "Your annual balance is 18", meta)
    )

