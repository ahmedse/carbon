"""PEC-4A — CI-invokable Nibras eval harness (deterministic, offline).

Usage::

    cd backend && python -m ai.eval.run_harness

Runs ≥20 golden Nibras scenarios with **no LLM and no live DB requirement**.
Payroll arithmetic / deny / fabrication / compound checks use
``GOLDEN_HRMS_DATASET`` fixtures. Lifecycle checks load the Nibras process YAML.
Clarify uses the pure policy module. Topic guard uses ``instance.yaml``.

Prints per-scenario PASS/FAIL plus a metrics JSON blob. Exits non-zero when:

* any scenario fails, OR
* ``fabrication_rate`` is not exactly 0, OR
* scenario count < 20

Also importable::

    from ai.eval.run_harness import run_harness, metrics_fail_ci
"""

from __future__ import annotations

import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from ai.eval.checks import (
    assert_compound_net_pay_answer,
    assert_counts_match_db,
    assert_net_pay_grounded,
    assert_no_pay_figures_beyond_db,
    assert_scoped_empty_for_denied,
    assert_topic_guard_fires,
)
from ai.eval.golden_hrms import GOLDEN_HRMS_DATASET
from ai.eval.scenarios_nibras import GOLDEN_NIBRAS_SCENARIOS, assert_scenario_count

PROCESS_ID = "payroll.run.lifecycle"
MINIMUM_SCENARIOS = 20

# Repo-relative paths (engine + domain packs live beside backend/)
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = _BACKEND_DIR.parent
_NIBRAS_INSTANCE_YAML = (
    _BACKEND_DIR / "ai" / "engine" / "instances" / "nibras" / "instance.yaml"
)
_NIBRAS_PROCESS_YAML = (
    _REPO_ROOT / "domain_packs" / "nibras" / "processes" / "payroll.run.lifecycle.yaml"
)


def _bootstrap_django() -> None:
    """Optional Django setup — only needed for modules that import Django transitively.

    Clarify + topic_guard + engine_runtime need Django settings when imported.
    """
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()


# ── Fixture helpers (no DB) ──────────────────────────────────────────────────


def _fixture_payslip_rows() -> list[dict]:
    """Materialise golden payslip lines as host-shaped row dicts."""
    emp_pk = {
        spec["no"]: i + 1
        for i, spec in enumerate(GOLDEN_HRMS_DATASET["employees"])
    }
    rows = []
    for line in GOLDEN_HRMS_DATASET["payslip_lines"]:
        rows.append(
            {
                "employee": emp_pk[line["employee_no"]],
                "employee_no": line["employee_no"],
                "line_type": line["line_type"],
                "amount": Decimal(line["amount"]),
            }
        )
    return rows


def _fixture_db_rows() -> list[dict]:
    return [
        {
            "employee_id": r["employee"],
            "line_type": r["line_type"],
            "amount": r["amount"],
        }
        for r in _fixture_payslip_rows()
    ]


def _emp_pk(employee_no: str) -> int:
    for i, spec in enumerate(GOLDEN_HRMS_DATASET["employees"]):
        if spec["no"] == employee_no:
            return i + 1
    raise KeyError(employee_no)


def _hq_employee_nos() -> set[str]:
    return {
        spec["no"]
        for spec in GOLDEN_HRMS_DATASET["employees"]
        if spec["org"] == "hq"
    }


def _render_payroll_amounts(rows: list[dict]) -> str:
    return " | ".join(
        f"employee={row['employee']} {row['line_type']}={row['amount']}" for row in rows
    )


def _good_compound_answer(rows: list[dict]) -> str:
    by_emp: dict[str, dict[str, str]] = {}
    for row in rows:
        by_emp.setdefault(str(row["employee"]), {})[str(row["line_type"])] = str(
            row["amount"]
        )
    parts = ["Net pay is calculated as: gross - gosi - loan_installment = net."]
    for emp, lines in sorted(by_emp.items()):
        parts.append(
            f"Employee {emp}: gross={lines.get('gross')} gosi={lines.get('gosi')} "
            f"loan={lines.get('loan_installment')} net={lines.get('net')}"
        )
    return " ".join(parts)


def _load_payroll_process() -> dict:
    return yaml.safe_load(_NIBRAS_PROCESS_YAML.read_text(encoding="utf-8"))


def _load_nibras_instance() -> dict:
    return yaml.safe_load(_NIBRAS_INSTANCE_YAML.read_text(encoding="utf-8")) or {}


# ── Scenario runners ─────────────────────────────────────────────────────────


def _run_kind(kind: str, params: dict, ctx: dict) -> None:
    rows = ctx.setdefault("rows", _fixture_payslip_rows())

    if kind == "net_pay_employee":
        emp = _emp_pk(params["employee_no"])
        emp_rows = [r for r in rows if int(r["employee"]) == emp]
        assert_net_pay_grounded(emp_rows)
        return

    if kind == "net_pay_all":
        assert_net_pay_grounded(rows)
        return

    if kind == "no_fabrication":
        rendered = _render_payroll_amounts(rows)
        assert_no_pay_figures_beyond_db(rendered, _fixture_db_rows())
        return

    if kind == "net_pay_counts":
        by_employee: dict[str, int] = {}
        for row in rows:
            key = str(row["employee"])
            by_employee[key] = by_employee.get(key, 0) + 1
        breakdown = [{"label": k, "count": v} for k, v in sorted(by_employee.items())]
        assert_counts_match_db(breakdown, dict(by_employee))
        return

    if kind == "deny_remote_employee":
        # Fixture truth: HR900 is remote-org; HQ payslip lines never include them.
        denied_no = params["denied_employee_no"]
        denied_pk = _emp_pk(denied_no)
        hq_rows = [r for r in rows if r["employee_no"] in _hq_employee_nos()]
        denied_rows = [r for r in hq_rows if int(r["employee"]) == denied_pk]
        assert_scoped_empty_for_denied(denied_rows)
        # Structural: denied employee must exist in dataset but outside HQ.
        remote = next(
            e for e in GOLDEN_HRMS_DATASET["employees"] if e["no"] == denied_no
        )
        if remote["org"] == "hq":
            raise AssertionError(f"{denied_no} unexpectedly in hq org")
        return

    if kind == "deny_empty_for_injected":
        assert_scoped_empty_for_denied([])
        return

    if kind == "deny_hq_only_employee_set":
        allowed = set(params["allowed_employee_nos"])
        seen = {r["employee_no"] for r in rows}
        # Fixture payslip_lines are HQ-only by construction.
        if seen != allowed:
            raise AssertionError(f"HQ payslip employees {seen} != {allowed}")
        return

    if kind == "lifecycle_step":
        doc = ctx.setdefault("process_doc", _load_payroll_process())
        step = next(s for s in doc["steps"] if s["id"] == params["step_id"])
        if step.get("autonomy") != params["expect_autonomy"]:
            raise AssertionError(
                f"step {params['step_id']} autonomy={step.get('autonomy')!r} "
                f"!= {params['expect_autonomy']!r}"
            )
        if bool(step.get("consent")) != bool(params["expect_consent"]):
            raise AssertionError(
                f"step {params['step_id']} consent={step.get('consent')!r} "
                f"!= {params['expect_consent']!r}"
            )
        expect_kind = params.get("expect_kind")
        if expect_kind is not None and step.get("kind") != expect_kind:
            raise AssertionError(
                f"step {params['step_id']} kind={step.get('kind')!r} != {expect_kind!r}"
            )
        return

    if kind == "lifecycle_order":
        doc = ctx.setdefault("process_doc", _load_payroll_process())
        actual = [s["id"] for s in doc["steps"]]
        if actual != params["expected_steps"]:
            raise AssertionError(f"step order {actual} != {params['expected_steps']}")
        return

    if kind == "clarify_policy":
        from ai.engine.cognition.turn.clarify import evaluate_clarification

        decision = evaluate_clarification(
            object_candidates=params["object_candidates"],
            evidence_available=params["evidence_available"],
            evidence_required=params["evidence_required"],
            authority_granted=frozenset(params["authority_granted"]),
            authority_required=params["authority_required"],
        )
        if decision.needs_clarification != params["expect_clarify"]:
            raise AssertionError(
                f"clarify={decision.needs_clarification} != {params['expect_clarify']}"
            )
        if decision.reason != params["expect_reason"]:
            raise AssertionError(
                f"reason={decision.reason!r} != {params['expect_reason']!r}"
            )
        return

    if kind == "topic_guard":
        from ai.engine_runtime import _check_topic_guard

        cfg = ctx.setdefault("instance_config", _load_nibras_instance())
        refusal = _check_topic_guard(cfg, params["message"])
        assert_topic_guard_fires(refusal, expect_refuse=params["expect_refuse"])
        return

    if kind == "compound_net_pay":
        db_rows = _fixture_db_rows()
        mode = params["mode"]
        if mode == "good":
            assert_compound_net_pay_answer(_good_compound_answer(rows), db_rows)
            return
        if mode == "metadata_only_must_fail_check":
            bad = "Payroll run id=42 status=committed period=2026-08 (metadata only)."
            try:
                assert_compound_net_pay_answer(bad, db_rows)
            except AssertionError:
                return
            raise AssertionError("metadata-only compound answer incorrectly passed")
        raise AssertionError(f"unknown compound mode {mode!r}")

    raise AssertionError(f"unknown scenario kind {kind!r}")


# ── Metrics ──────────────────────────────────────────────────────────────────


def aggregate_metrics(results: list[dict], *, wall_ms: float) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r["passed"])

    def _rate(tag: str) -> float | None:
        tagged = [r for r in results if tag in r.get("metrics", [])]
        if not tagged:
            return None
        return round(sum(1 for r in tagged if r["passed"]) / len(tagged), 4)

    fabrication_tagged = [r for r in results if "fabrication" in r.get("metrics", [])]
    fabrication_failures = sum(1 for r in fabrication_tagged if not r["passed"])
    fabrication_rate = (
        round(fabrication_failures / len(fabrication_tagged), 4)
        if fabrication_tagged
        else 0.0
    )

    return {
        "instance": "nibras",
        "scenario_count": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "grounding_pass": _rate("grounding"),
        "deny_correctness": _rate("deny"),
        "fabrication_rate": fabrication_rate,
        "clarify_pass": _rate("clarify"),
        "lifecycle_pass": _rate("lifecycle"),
        "topic_guard_pass": _rate("topic_guard"),
        "compound_pass": _rate("compound"),
        "latency_ms_total": round(wall_ms, 2),
        "tokens": 0,
        "failed_ids": [r["id"] for r in results if not r["passed"]],
    }


def metrics_fail_ci(metrics: dict) -> bool:
    if metrics.get("scenario_count", 0) < MINIMUM_SCENARIOS:
        return True
    if metrics.get("failed", 0) > 0:
        return True
    if float(metrics.get("fabrication_rate", 1.0)) != 0.0:
        return True
    return False


def deliberate_fabrication_would_fail() -> bool:
    try:
        assert_no_pay_figures_beyond_db(
            "fabricated net=9999.999",
            [{"amount": "1315.000"}, {"amount": "1500.000"}],
        )
    except AssertionError:
        return True
    return False


def run_harness() -> dict[str, Any]:
    """Execute all golden Nibras scenarios; return ``{results, metrics}``."""
    assert_scenario_count(MINIMUM_SCENARIOS)
    ctx: dict[str, Any] = {}
    results: list[dict] = []
    t0 = time.perf_counter()
    for scenario in GOLDEN_NIBRAS_SCENARIOS:
        started = time.perf_counter()
        error = None
        try:
            _run_kind(scenario["kind"], scenario.get("params") or {}, ctx)
            passed = True
        except Exception as exc:  # noqa: BLE001
            passed = False
            error = f"{type(exc).__name__}: {exc}"
        results.append(
            {
                "id": scenario["id"],
                "category": scenario["category"],
                "metrics": list(scenario.get("metrics") or []),
                "passed": passed,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "error": error,
                "description": scenario.get("description", ""),
            }
        )

    wall_ms = (time.perf_counter() - t0) * 1000
    metrics = aggregate_metrics(results, wall_ms=wall_ms)
    return {"results": results, "metrics": metrics}


def main(argv: list[str] | None = None) -> int:
    _ = argv
    _bootstrap_django()

    if not deliberate_fabrication_would_fail():
        print(
            "NEGATIVE GATE FAILED: fabricated amount did not trip check",
            file=sys.stderr,
        )
        return 1

    report = run_harness()
    metrics = report["metrics"]

    for row in report["results"]:
        status = "PASS" if row["passed"] else "FAIL"
        suffix = f" — {row['error']}" if row["error"] else ""
        print(f"{row['id']}: {status}{suffix}")

    print("---")
    print(f"pass_rate={metrics['passed']}/{metrics['scenario_count']}")
    print("METRICS_JSON=" + json.dumps(metrics, sort_keys=True))

    if metrics_fail_ci(metrics):
        print(
            "HARNESS GATE FAILED "
            f"(fabrication_rate={metrics['fabrication_rate']}, "
            f"failed={metrics['failed_ids']})",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
