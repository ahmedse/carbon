"""Tests for PV2-0B multi-turn coherence bank.

Structural tests (scripts load, ≥8 turns each, objective IDs valid, slot table covers
all referenced slots) PASS for real. Per-script coherence expectations run as xfail
(strict=False) so baseline red is expected.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from ai.eval.multiturn.bank import (
    SLOT_PATTERNS,
    Script,
    detect_language,
    load_scripts_from_glob,
    reasks_slot,
)


pytestmark = pytest.mark.eval_multiturn


@pytest.fixture(autouse=True)
def _committed_understand_default(monkeypatch):
    """The G5 bank scores the committed default path. A local ``.env`` trial
    of ``PULSE_UNDERSTAND`` must not change what these goldens measure."""
    monkeypatch.setenv("PULSE_UNDERSTAND", "legacy")
    monkeypatch.setenv("PULSE_TOOL_CHOICE", "on")


# ── Structural tests (PASS for real) ─────────────────────────────────────


class TestScriptsLoad:
    """Verify all 14 scripts load and are structurally valid."""
    
    def test_all_scripts_load(self):
        """All 14 scripts must load without error."""
        base_dir = Path(__file__).parent / "multiturn"
        scripts = load_scripts_from_glob("scripts/*.yaml", base_dir)
        assert len(scripts) == 14, f"Expected 14 scripts, got {len(scripts)}"
    
    def test_v21_tier_scripts_load_outside_the_g5_bank(self):
        """ADR-0049 goldens live in scripts_v21/ so scripts/*.yaml (G5, 96/96)
        is unchanged. They must still be schema-valid scripts."""
        base_dir = Path(__file__).parent / "multiturn"
        scripts = {s.id: s for s in load_scripts_from_glob("scripts_v21/*.yaml", base_dir)}
        assert set(scripts) == {"payslip-loan-followup-en-01", "leave-charts-subject-en-01"}
        for s in scripts.values():
            ok, err = s.validate()
            assert ok, err
        charts = scripts["leave-charts-subject-en-01"]
        where = next(t for t in charts.turns if t.user.startswith("where are the charts"))
        assert "Gross Pay" in where.expect.mentions_none
        script = scripts["payslip-loan-followup-en-01"]
        assert "list_my_loans" in script.stub_host
        loan_turn = next(t for t in script.turns if t.user.startswith("I noticed I have a loan"))
        assert "loan_type" in loan_turn.expect.must_not_reask_slots
        assert "handoff_agent" not in loan_turn.expect.decision_in

    def test_each_script_has_minimum_turns(self):
        """Each script must have ≥7 turns."""
        base_dir = Path(__file__).parent / "multiturn"
        scripts = load_scripts_from_glob("scripts/*.yaml", base_dir)
        for script in scripts:
            assert len(script.turns) >= 7, (
                f"Script {script.id}: has {len(script.turns)} turns, "
                f"need ≥7"
            )
    
    def test_each_script_has_objective_ids(self):
        """Each script must have ≥1 objective_id."""
        base_dir = Path(__file__).parent / "multiturn"
        scripts = load_scripts_from_glob("scripts/*.yaml", base_dir)
        for script in scripts:
            assert len(script.objective_ids) >= 1, (
                f"Script {script.id}: has no objective_ids"
            )
    
    def test_all_objective_ids_valid(self):
        """All objective_ids must be C1–C10 or A1–A10."""
        base_dir = Path(__file__).parent / "multiturn"
        scripts = load_scripts_from_glob("scripts/*.yaml", base_dir)
        valid_ids = {f"C{i}" for i in range(1, 11)} | {f"A{i}" for i in range(1, 11)}
        for script in scripts:
            for oid in script.objective_ids:
                assert oid in valid_ids, (
                    f"Script {script.id}: invalid objective_id {oid}"
                )
    
    def test_slot_table_covers_referenced_slots(self):
        """Every slot referenced in scripts must be in SLOT_PATTERNS."""
        base_dir = Path(__file__).parent / "multiturn"
        scripts = load_scripts_from_glob("scripts/*.yaml", base_dir)
        referenced = set()
        for script in scripts:
            for turn in script.turns:
                if turn.expect and turn.expect.must_not_reask_slots:
                    referenced.update(turn.expect.must_not_reask_slots)
        
        for slot in referenced:
            assert slot in SLOT_PATTERNS, (
                f"Slot {slot} referenced but not in SLOT_PATTERNS"
            )


# ── Detector unit tests (PASS for real) ──────────────────────────────────


class TestLanguageDetector:
    """Unit tests for detect_language()."""
    
    def test_detect_english(self):
        """English text should detect as 'en'."""
        assert detect_language("Hello world") == "en"
        assert detect_language("This is a test") == "en"
    
    def test_detect_arabic(self):
        """Arabic text should detect as 'ar'."""
        assert detect_language("مرحبا بالعالم") == "ar"
        assert detect_language("أريد قرض") == "ar"
    
    def test_detect_mixed(self):
        """Mixed text should detect as 'mixed'."""
        assert detect_language("Hello مرحبا world") == "mixed"
        assert detect_language("The مرحبا test") == "mixed"
    
    def test_empty_string(self):
        """Empty string should default to 'en'."""
        assert detect_language("") == "en"
    
    def test_numbers_only(self):
        """Numbers without alpha should default to 'en'."""
        assert detect_language("12345") == "en"


class TestReasksSlotDetector:
    """Unit tests for reasks_slot()."""
    
    def test_detects_amount_reask_en(self):
        """Should detect re-asking for amount in English."""
        assert reasks_slot("What is the amount?", "amount") is True
        assert reasks_slot("How much do you need?", "amount") is True
    
    def test_detects_amount_reask_ar(self):
        """Should detect re-asking for amount in Arabic."""
        assert reasks_slot("ما المبلغ؟", "amount") is True
    
    def test_detects_leave_type_reask(self):
        """Should detect re-asking for leave_type."""
        assert reasks_slot("What type of leave?", "leave_type") is True
    
    def test_detects_start_date_reask(self):
        """Should detect re-asking for start_date."""
        assert reasks_slot("When do you want to start?", "start_date") is True
        assert reasks_slot("What is the start date?", "start_date") is True
    
    def test_no_reask_when_not_present(self):
        """Should return False when slot is not being re-asked."""
        assert reasks_slot("Your request has been processed", "amount") is False
        assert reasks_slot("The emergency loan has been noted", "loan_type") is False
    
    def test_unknown_slot(self):
        """Should return False for unknown slots."""
        assert reasks_slot("Some text", "unknown_slot") is False
    
    def test_case_insensitive(self):
        """Should be case-insensitive."""
        assert reasks_slot("WHAT IS THE AMOUNT?", "amount") is True
        assert reasks_slot("What Is The Amount?", "amount") is True
    
    def test_negative_case_not_reask(self):
        """Should NOT detect re-asking when it is not present."""
        assert reasks_slot("What else can I help with?", "amount") is False
        assert reasks_slot("What do you think?", "loan_type") is False


# ── Smoke test (must PASS for real) ──────────────────────────────────────


class TestSmokeTest:
    """Verify engine produces a reply on every turn (structural, not coherence)."""
    
    @pytest.mark.django_db(transaction=True)
    def test_smoke_script_01_engine_produces_replies(self):
        """Script 01 must produce a reply on every turn (engine integrity check)."""
        from ai.eval.multiturn.runner import run_script
        from ai.eval.multiturn.bank import load_scripts_from_glob
        
        base_dir = Path(__file__).parent / "multiturn"
        scripts = load_scripts_from_glob("scripts/01-*.yaml", base_dir)
        if not scripts:
            pytest.skip("Script 01 not found")
        
        script = scripts[0]
        result = run_script(script)
        
        # Engine must not error on any turn
        assert not result.error, f"Script error: {result.error}"
        assert all(
            t.error is None for t in result.turns
        ), f"Some turns had engine errors: {[t.error for t in result.turns if t.error]}"
        
        # Engine must produce reply on every turn
        assert all(
            t.stub_reply for t in result.turns
        ), "Some turns have no reply (engine integrity issue)"


# ── CLI exit codes (PASS for real) ───────────────────────────────────────


class TestCliExitCodes:
    """main() must surface engine errors (3) and malformed scripts (2)."""

    @pytest.fixture
    def no_isolated_db(self, monkeypatch):
        import contextlib
        from ai.eval.multiturn import runner

        @contextlib.contextmanager
        def _fake_db(*, keepdb=False):
            yield "fake_test_db"

        monkeypatch.setattr(runner, "isolated_test_db", _fake_db)
        return runner

    def test_engine_error_exits_3(self, no_isolated_db, monkeypatch, tmp_path):
        runner = no_isolated_db

        def _boom(script, **kwargs):
            raise ValueError("dispatch_task failed: Connection refused")

        monkeypatch.setattr(runner, "run_script", _boom)
        report_path = tmp_path / "report.json"
        code = runner.main(["--report", str(report_path), "--scripts", "scripts/12-*.yaml"])
        assert code == 3

        import json
        data = json.loads(report_path.read_text())
        assert data["errors"] == [
            {"script_id": "nav-zero-llm-01",
             "error": "ValueError: dispatch_task failed: Connection refused"}
        ]
        assert data["tier"] == "offline_stub"
        assert data["caveats"]

    def test_engine_error_exits_3_via_system_exit(self, no_isolated_db, monkeypatch, tmp_path):
        runner = no_isolated_db

        def _boom(script, **kwargs):
            raise RuntimeError("engine exploded")

        monkeypatch.setattr(runner, "run_script", _boom)
        with pytest.raises(SystemExit) as exc:
            import sys
            sys.exit(runner.main(["--report", str(tmp_path / "r.json"),
                                  "--scripts", "scripts/0[12]-*.yaml"]))
        assert exc.value.code == 3

    def test_clean_run_exits_0(self, no_isolated_db, monkeypatch, tmp_path):
        from ai.eval.multiturn.runner import ScriptResult, TurnResult
        runner = no_isolated_db

        def _ok(script, **kwargs):
            return ScriptResult(
                script_id=script.id,
                turns=[TurnResult(user_input=t.user, stub_reply="ok", passed=True)
                       for t in script.turns],
                passed=True,
            )

        monkeypatch.setattr(runner, "run_script", _ok)
        code = runner.main(["--report", str(tmp_path / "r.json"), "--scripts", "scripts/12-*.yaml"])
        assert code == 0

    def test_malformed_yaml_exits_2(self, no_isolated_db, monkeypatch, tmp_path):
        runner = no_isolated_db
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "bad.yaml").write_text("id: bad\nturns: [\n")
        monkeypatch.setattr(runner, "__file__", str(tmp_path / "runner.py"))
        code = runner.main(["--report", str(tmp_path / "r.json"), "--scripts", "scripts/*.yaml"])
        assert code == 2


# ── Coherence expectations (xfail) ───────────────────────────────────────


class TestCoherenceExpectations:
    """Per-script coherence expectations (expected to fail in P0 baseline).
    
    All 13 scripts run with dispatch_task; xfail because Pulse v2 features
    are not yet implemented. Failures are on expectation assertions
    (decision, language, reask, mentions), not on engine/DB errors.
    """
    
    @pytest.mark.django_db(transaction=True)
    @pytest.mark.xfail(strict=False, reason="PV2-0B baseline — Pulse v2 not yet implemented")
    @pytest.mark.parametrize("script_pattern,script_id", [
        ("scripts/01-*.yaml", "ess-loan-ar-01"),
        ("scripts/02-*.yaml", "ess-leave-en-01"),
        ("scripts/03-*.yaml", "ess-attendance-mixed-01"),
        ("scripts/05-*.yaml", "entity-focus-switch-01"),
        ("scripts/06-*.yaml", "grounded-recall-01"),
        ("scripts/07-*.yaml", "plan-status-01"),
        ("scripts/08-*.yaml", "chat-handoff-write-01"),
        ("scripts/11-*.yaml", "memory-learn-fact-01"),
        ("scripts/13-*.yaml", "composite-brief-ar-01"),
    ])
    def test_script_coherence_expectations(self, script_pattern, script_id):
        """Run script and validate all turns pass expectations."""
        from ai.eval.multiturn.runner import run_script
        from ai.eval.multiturn.bank import load_scripts_from_glob
        
        base_dir = Path(__file__).parent / "multiturn"
        scripts = load_scripts_from_glob(script_pattern, base_dir)
        if not scripts:
            pytest.skip(f"{script_id} not found")
        
        script = scripts[0]
        result = run_script(script)
        
        # No engine errors
        assert not result.error, f"Script {script_id} error: {result.error}"
        
        # All turns must pass their expectations
        passed = sum(1 for t in result.turns if t.passed)
        assert passed == len(result.turns), (
            f"Script {script_id}: {passed}/{len(result.turns)} turns passed; "
            f"failures: "
            f"{[(i, t.decision, t.language_ok, t.reask_violations) for i, t in enumerate(result.turns) if not t.passed]}"
        )


@pytest.mark.django_db(transaction=True)
def test_v21_leave_charts_script_renders_only_the_decided_read(monkeypatch):
    """ADR-0049 execute+render contract under PULSE_UNDERSTAND=v21. The
    understand output is stubbed; G6 g6-068..070 score the model."""
    from ai.eval.multiturn.runner import run_script

    monkeypatch.setenv("PULSE_UNDERSTAND", "v21")
    base_dir = Path(__file__).parent / "multiturn"
    script = load_scripts_from_glob("scripts_v21/15-*.yaml", base_dir)[0]
    result = run_script(script)
    assert not result.error, result.error
    failures = [
        (i, t.user_input, t.fail_reasons)
        for i, t in enumerate(result.turns)
        if not t.passed
    ]
    assert not failures, failures


class TestBoundReadGoldens:
    """Blocking. Stub host rows let bound 0-LLM reads restate committed figures."""

    @pytest.mark.django_db(transaction=True)
    @pytest.mark.parametrize("script_pattern,script_id", [
        ("scripts/04-*.yaml", "payroll-followup-en-01"),
        ("scripts/09-*.yaml", "language-fidelity-ar-01"),
        ("scripts/10-*.yaml", "date-awareness-01"),
        ("scripts/12-*.yaml", "nav-zero-llm-01"),
        ("scripts/ess_leave_followup*.yaml", "ess-leave-followup-subject"),
    ])
    def test_script_is_blocking(self, script_pattern, script_id):
        TestCoherenceExpectations().test_script_coherence_expectations(script_pattern, script_id)
