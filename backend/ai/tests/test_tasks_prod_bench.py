"""Production-readiness host checks stay honest."""
from ai.eval.tasks_prod_bench import check_host_grounded, score_kpis


class Host:
    def me(self):
        return {"full_name": "Ali Mohamed Saad AlAjmi", "basic_salary": "2407.622"}


def test_gosi_empty_september_is_a_miss(monkeypatch):
    from ai.eval import tasks_prod_bench as m

    monkeypatch.setattr(m, "payroll_oracle", lambda token: {
        "ok": True, "count": 13, "latest_period": "2026-08-31", "latest_id": 56,
    })
    monkeypatch.setattr(m, "gosi_oracle", lambda token, period: {
        "ok": True, "totals": ["9863"], "period_end": period, "empty": False,
    })
    plan = {
        "final_response": "No committed GOSI lines for that period.",
        "steps": [{
            "tool_name": "analyze_gosi_committed",
            "tool_args": {"api_name": "analyze_gosi_committed", "query_params": {"period_end": "2026-09-30"}},
            "draft_text": "No committed GOSI lines for that period.",
        }],
    }
    misses = check_host_grounded("gosi", plan, Host(), "tok")
    assert any("2026-08-31" in m for m in misses)
    assert any("9863" in m for m in misses)
    listed = {
        "final_response": "Period End 2026-08-31\nNo committed GOSI lines",
        "steps": [{
            "tool_name": "analyze_gosi_committed",
            "tool_args": {
                "api_name": "analyze_gosi_committed",
                "query_params": {"period_end": "[PLACEHOLDER]"},
            },
            "draft_text": "Period End 2026-08-31 listed above. No GOSI.",
        }],
    }
    listed_misses = check_host_grounded("gosi", listed, Host(), "tok")
    assert any("not bound" in m for m in listed_misses)


def _scored_rows(**extra):
    stub = {"honest": "reached", "note": "ok"}
    rows = {
        key: dict(stub)
        for key in (
            "grounded", "bind", "first_turn", "cockpit", "stability",
            "arabic", "latency", "chat",
        )
    }
    rows.update(extra)
    return rows


def _r6(rows):
    return next(k for k in score_kpis(rows) if k["id"] == "R6")


def test_r6_absent_stays_missing():
    kpi = _r6(_scored_rows())
    assert kpi["honest"] == "missing"


def test_r6_both_personas_grounded_is_reached():
    kpi = _r6(_scored_rows(personas={
        "my": {"pass": True, "host_misses": []},
        "team": {"pass": True, "host_misses": []},
    }))
    assert kpi["honest"] == "reached"


def test_r6_a_persona_miss_is_fail():
    kpi = _r6(_scored_rows(personas={
        "my": {"pass": True, "host_misses": ["missing me.full_name"]},
        "team": {"pass": True, "host_misses": []},
    }))
    assert kpi["honest"] == "fail"
    assert "missing me.full_name" in kpi["note"]


def test_reports_requires_the_host_row(monkeypatch):
    from ai.eval import tasks_prod_bench as m

    monkeypatch.setattr(m, "_req", lambda *a, **k: (200, [{
        "employee_no": "1067",
        "full_name": "Bilagot Panta Suerte",
    }]))

    class TeamHost:
        def me(self):
            return {"full_name": "Mohammad Bolto Ali", "basic_salary": "142.803"}

    found = {"final_response": "Direct report 1067 Bilagot Panta Suerte", "steps": []}
    assert check_host_grounded("reports", found, TeamHost(), "tok") == []
    missing = {"final_response": "No reports.", "steps": []}
    misses = check_host_grounded("reports", missing, TeamHost(), "tok")
    assert any("1067" in item for item in misses)
    assert any("Bilagot Panta Suerte" in item for item in misses)


def test_profile_hides_pay():
    plan = {
        "final_response": "Ali Mohamed Saad AlAjmi, annual 30",
        "steps": [],
    }
    assert check_host_grounded("profile", plan, Host(), "tok") == []
    leaked = {"final_response": "Ali Mohamed Saad AlAjmi 2407.622", "steps": []}
    assert "leaked me.basic_salary" in check_host_grounded("profile", leaked, Host(), "tok")


def test_hidden_pay_fields_cover_basic_and_net():
    from ai.eval import tasks_prod_bench as m

    assert set(m._HIDDEN_PAY_FIELDS) == {"basic_salary", "net_pay"}
    assert m._OBSERVE_STATUS_OK == frozenset({"completed", "completed_with_gaps"})

    class NetHost:
        def me(self):
            return {"full_name": "Bilagot Panta Suerte", "net_pay": "1234.56"}

    leaked = {"final_response": "Bilagot Panta Suerte net 1234.56", "steps": []}
    assert "leaked me.net_pay" in check_host_grounded("profile", leaked, NetHost(), "tok")


def test_non_completed_observe_is_a_miss():
    plan = {
        "status": "awaiting_approval",
        "final_response": "Ali Mohamed Saad AlAjmi",
        "steps": [],
    }
    misses = check_host_grounded("profile", plan, Host(), "tok")
    assert any(m.startswith("status=") for m in misses)


def test_mutation_step_in_observe_is_a_miss():
    plan = {
        "status": "completed",
        "final_response": "Ali Mohamed Saad AlAjmi",
        "steps": [{"tool_name": "submit_my_leave", "tool_args": {}, "is_mutation": True}],
    }
    misses = check_host_grounded("profile", plan, Host(), "tok")
    assert "mutation step in observe" in misses


def test_score_r4_never_reaches_without_a_taskso_file():
    from ai.eval.tasks_prod_bench import score_r4

    honest, note = score_r4(False, None)
    assert honest == "partial"
    assert "Taskso" in note
    assert score_r4(True, None)[0] == "fail"
    reached, note = score_r4(False, "PV2-tasks-taskso-2026-10-01.json")
    assert reached == "reached"
    assert "PV2-tasks-taskso-2026-10-01.json" in note


def test_score_r7_missing_and_r8_fail_are_pinned():
    from ai.eval.tasks_prod_bench import score_r7, score_r8

    assert score_r7()[0] == "missing"
    assert "STACK-HOLD" in score_r7()[1]
    assert score_r8()[0] == "fail"
    assert "2026-09-23" in score_r8()[1]


def test_kpis_carry_falsified_by_and_r12_fails_off_file():
    kpis = {k["id"]: k for k in score_kpis(_scored_rows())}
    assert all(k.get("falsified_by") for k in kpis.values())
    assert kpis["R4"]["tier"] == "live_browser"
    assert kpis["R7"]["honest"] == "missing"
    assert kpis["R8"]["honest"] == "fail"
    assert kpis["R12"]["honest"] == "fail"

