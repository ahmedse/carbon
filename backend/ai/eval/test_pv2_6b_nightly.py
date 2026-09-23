"""PV2-6B — nightly ESS smoke: consent, catalog, IC assertions, soak ledger."""
from __future__ import annotations

from pathlib import Path

import pytest

from ai.eval.nightly_ess_smoke import (
    HOST_USER,
    JOURNEYS,
    LIVE_ENV,
    REQUIRED_CONSECUTIVE,
    ConsentError,
    NightRecord,
    catalog_issues,
    chat_did_not_mutate,
    chat_utterance,
    consecutive_green_nights,
    ic_failures,
    journey_bindings,
    matching_rows,
    record_night,
    require_live_consent,
    slot_carry_ok,
    soak_complete,
)


pytestmark = pytest.mark.eval_multiturn


def test_catalog_is_three_ess_journeys():
    assert [j.id for j in JOURNEYS] == ["leave", "loan", "attendance"]
    assert catalog_issues() == []
    assert all(j.host_list_path.startswith("/people/me/") for j in JOURNEYS)
    assert {j.api_name for j in JOURNEYS} == {
        "submit_my_leave",
        "submit_my_loan",
        "submit_my_attendance_permission",
    }


def test_utterances_carry_process_dial_tokens_and_slots():
    slots = journey_bindings("2026-09-23")
    leave = chat_utterance(JOURNEYS[0], slots["leave"])
    loan = chat_utterance(JOURNEYS[1], slots["loan"])
    att = chat_utterance(JOURNEYS[2], slots["attendance"])
    assert "I want annual leave" in leave
    assert slots["leave"]["start_date"] in leave
    assert "personal loan" in loan
    assert str(slots["loan"]["principal"]) in loan
    assert "attendance permission" in att
    assert "official" in att
    assert slots["attendance"]["date"] in att
    assert slots["leave"]["start_date"] != slots["loan"]["start_date"]


def test_same_night_bindings_are_stable():
    assert journey_bindings("2026-09-23") == journey_bindings("2026-09-23")
    assert journey_bindings("2026-09-23") != journey_bindings("2026-09-24")


def test_refuse_live_without_hold_or_env_or_wrong_user():
    with pytest.raises(ConsentError, match="stack-hold"):
        require_live_consent(
            live=True, stack_hold=False, host_user=HOST_USER, env={LIVE_ENV: "1"},
        )
    with pytest.raises(ConsentError, match=LIVE_ENV):
        require_live_consent(
            live=True, stack_hold=True, host_user=HOST_USER, env={},
        )
    with pytest.raises(ConsentError, match="emp_1067"):
        require_live_consent(
            live=True, stack_hold=True, host_user="ahmed", env={LIVE_ENV: "1"},
        )
    require_live_consent(
        live=True, stack_hold=True, host_user=HOST_USER, env={LIVE_ENV: "1"},
    )
    require_live_consent(
        live=False, stack_hold=False, host_user="anyone", env={},
    )


def test_cli_live_without_hold_exits_2(capsys):
    from ai.eval.nightly_ess_smoke import main

    assert main(["--live", "--host-user", HOST_USER]) == 2
    err = capsys.readouterr().err
    assert "stack-hold" in err


def test_cli_dry_run_does_not_record_and_exits_0(capsys, tmp_path, monkeypatch):
    from ai.eval import nightly_ess_smoke as mod

    monkeypatch.setattr(mod, "NIGHTS_JSON", tmp_path / "nights.json")
    monkeypatch.setattr(mod, "SOAK_MD", tmp_path / "soak.md")
    assert mod.main(["--dry-run", "--night", "2026-09-23"]) == 0
    out = capsys.readouterr().out
    assert "DRY_RUN" in out
    assert "I want annual leave" in out
    assert not (tmp_path / "nights.json").exists()


def test_chat_must_not_mutate_host_rows():
    before = [{"id": 1, "start_date": "2027-04-10"}]
    assert chat_did_not_mutate(before, [{"id": 1, "start_date": "2027-04-10"}])
    assert not chat_did_not_mutate(before, before + [{"id": 2}])


def test_host_fingerprint_and_slot_carry():
    rows = [
        {"id": 9, "principal": "517", "term_months": "12"},
        {"id": 10, "principal": "100", "term_months": "6"},
    ]
    assert matching_rows(rows, {"principal": 517, "term_months": 12}) == [rows[0]]
    inherited = [{"key": "loan_type", "value": "personal"}, {"key": "amount", "value": "517"}]
    assert slot_carry_ok(inherited, ("loan_type", "amount"))
    assert not slot_carry_ok(inherited, ("loan_type", "amount", "missing"))


def test_ic_failures_cover_contract_axes():
    good = {
        "handoff_ready": True,
        "chat_mutated": False,
        "slot_carry": True,
        "host_row_after_agent": True,
        "approve_http": 200,
    }
    assert ic_failures(good) == []
    bad = {
        "chat_decision": "answer",
        "chat_mutated": True,
        "slot_carry": False,
        "host_row_after_agent": False,
        "approve_http": 403,
    }
    misses = ic_failures(bad)
    assert "chat_handoff" in misses
    assert "chat_host_mutation" in misses
    assert "slot_carry" in misses
    assert "host_row" in misses
    assert "approve_http" in misses


def test_soak_counts_only_trailing_live_pass(tmp_path: Path):
    path = tmp_path / "nights.json"
    nights = [
        {"night_id": "2026-09-20", "status": "PASS"},
        {"night_id": "2026-09-21", "status": "FAIL"},
        {"night_id": "2026-09-22", "status": "PASS"},
        {"night_id": "2026-09-23", "status": "DRY_RUN"},
    ]
    assert consecutive_green_nights(nights) == 0
    assert not soak_complete(nights)
    assert consecutive_green_nights([{"status": "PASS"}] * 5) == 5
    assert soak_complete([{"status": "PASS"}] * REQUIRED_CONSECUTIVE)

    first = NightRecord(
        night_id="2026-09-24",
        status="PASS",
        host_user=HOST_USER,
        journeys=[{"id": "leave", "passed": True}],
        notes="live",
        recorded_at="2026-09-24T02:00:00+00:00",
    )
    payload = record_night(first, path=path)
    assert payload["soak_complete"] is False
    assert payload["nights"][-1]["consecutive_green"] == 1
    dry = NightRecord(
        night_id="2026-09-25",
        status="DRY_RUN",
        host_user=HOST_USER,
        notes="must not count",
        recorded_at="2026-09-25T02:00:00+00:00",
    )
    payload = record_night(dry, path=path)
    assert consecutive_green_nights(payload["nights"]) == 0
