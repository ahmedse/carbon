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
