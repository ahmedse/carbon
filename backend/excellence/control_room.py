"""Readiness answers for Pulse and Nibras.

This reads existing scorers and evidence files. It does not create a second score,
and a partial production recheck cannot replace the latest full production run.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EVIDENCE = REPO / "docs" / "pulse" / "evidence"


READINESS_COLUMNS = ["contract", "correct", "safe", "continuous", "fast", "proven"]
ACTUAL_COLUMNS = ["built", "configured", "data", "access", "adopted", "operated", "live"]
PULSE_ROWS = [
    {"id": "ask", "owner": "pulse-master"},
    {"id": "plan-lab", "owner": "pulse-master"},
    {"id": "plan-prod", "owner": "pulse-master"},
    {"id": "memory", "owner": "pulse-master"},
    {"id": "expertise", "owner": "pulse-master"},
    {"id": "operations", "owner": "pulse-master"},
]
NIBRAS_ROWS = [
    {"id": "people", "owner": "nibras-master"},
    {"id": "payroll", "owner": "nibras-master"},
    {"id": "stores", "owner": "nibras-master"},
    {"id": "finance-a", "owner": "nibras-master"},
    {"id": "finance-b", "owner": "nibras-master"},
    {"id": "documents", "owner": "nibras-master"},
]
DEFINITIONS = [
    {"id": "target", "group": "targets"},
    {"id": "leaf", "group": "targets"},
    {"id": "readiness", "group": "boards"},
    {"id": "actualization", "group": "boards"},
    {"id": "weakest", "group": "rules"},
    {"id": "unknown", "group": "rules"},
    {"id": "partial-run", "group": "rules"},
    {"id": "evidence", "group": "evidence"},
    {"id": "owners", "group": "evidence"},
    {"id": "sources", "group": "sources"},
]
_STATES = {"reached", "partial", "fail", "missing", "absent", "unmeasured"}


def build_control_room() -> dict:
    return {
        "domains": [
            {"id": "pulse", "instance": "nibras"},
            {"id": "nibras", "instance": "gofsco"},
        ],
        "boards": {
            "readiness": {"columns": READINESS_COLUMNS},
            "actualization": {"columns": ACTUAL_COLUMNS},
        },
        "rows": {"pulse": PULSE_ROWS, "nibras": NIBRAS_ROWS},
        "cells": {
            "pulse": {"readiness": _pulse_readiness(), "actualization": _pulse_actualization()},
            "nibras": {"readiness": _nibras_readiness(), "actualization": _nibras_actualization()},
        },
        "definitions": DEFINITIONS,
    }


def _matrix(rows: list[dict], columns: list[str]) -> dict:
    return {row["id"]: {column: _cell("unmeasured") for column in columns} for row in rows}


def _cell(state: str, reading: str = "", proof: str = "", limit: str = "", action: str = "", observed_at: str = "") -> dict:
    if state not in _STATES:
        state = "unmeasured"
    return {
        "state": state,
        "reading": reading,
        "proof": proof,
        "limit": limit or "Silence is not a pass.",
        "action": action or "Bind a probe and an owner.",
        "observed_at": observed_at,
    }


def _status(value: str) -> str:
    return value if value in _STATES else "unmeasured"


def _worse(left: str, right: str) -> str:
    rank = {"fail": 0, "absent": 1, "missing": 2, "partial": 3, "unmeasured": 4, "reached": 5}
    return left if rank.get(left, 4) <= rank.get(right, 4) else right


def _objective_status(report: dict, objective_id: str) -> tuple[str, str]:
    for row in report.get("objectives") or []:
        if row.get("id") == objective_id or row.get("tid") == objective_id:
            column = row.get("column") if isinstance(row.get("column"), dict) else {}
            status = column.get("honest") or row.get("honest") or "unmeasured"
            note = column.get("note") or row.get("note") or ""
            return _status(str(status)), str(note)
    return "unmeasured", ""


def _kpi_status(report: dict, kpi_id: str) -> tuple[str, str]:
    for row in report.get("kpis") or []:
        if row.get("id") == kpi_id:
            return _status(str(row.get("honest") or "unmeasured")), str(row.get("note") or "")
    return "unmeasured", ""


def _pulse_readiness() -> dict:
    board = _matrix(PULSE_ROWS, READINESS_COLUMNS)
    try:
        from ai.eval.chat_deep_bench import score_chat_bench

        ask = score_chat_bench()
    except Exception as exc:
        ask = None
        board["ask"]["proven"] = _cell("unmeasured", type(exc).__name__, "ai.eval.chat_deep_bench")
    if ask:
        observed = str(ask.get("date") or "")
        correct, correct_note = _objective_status(ask, "C2")
        safe, safe_note = _objective_status(ask, "C5")
        continuity, continuity_note = _objective_status(ask, "C1")
        slots, slots_note = _objective_status(ask, "C3")
        fast, fast_note = _objective_status(ask, "C8")
        proven = "reached"
        for row in ask.get("objectives") or []:
            column = row.get("column") if isinstance(row.get("column"), dict) else {}
            proven = _worse(proven, _status(str(column.get("honest") or "unmeasured")))
        board["ask"]["contract"] = _cell(
            "reached", "Ask is advisory. Host writes are forbidden.", "ADR-0046",
            "A written contract is not proof that every live run obeys it.", "Keep the live Safe cell separate.", observed,
        )
        board["ask"]["correct"] = _cell(correct, correct_note, "chat_deep_bench C2", "Grounding does not cover every scenario family.", "Extend the scenario denominator before calling expertise reached.", observed)
        board["ask"]["safe"] = _cell(safe, safe_note, "chat_deep_bench C5", "A closed finding is not a permanent pass.", "Close the remaining retest misses.", observed)
        board["ask"]["continuous"] = _cell(
            _worse(continuity, slots), continuity_note or slots_note, "chat_deep_bench C1, C3",
            "One good thread cannot upgrade the cell.", "Require the last three full runs.", observed,
        )
        board["ask"]["fast"] = _cell(fast, fast_note, "chat_deep_bench C8", "A median does not pass when too many turns exceed the bar.", "Hold the declared latency rule.", observed)
        board["ask"]["proven"] = _cell(proven, f"{ask.get('reached', 0)}/{ask.get('n_objectives', 10)} reached. Verdict {ask.get('verdict')}.", "ai.eval.chat_deep_bench", "The dated 9/10 canvas is not this cell.", "Regenerate this cell from the scorer.", observed)
    try:
        from ai.eval.agent_deep_bench import score_agent_bench

        lab = score_agent_bench()
        observed = str(lab.get("date") or "")
        lab_state = "reached" if lab.get("verdict") == "reliable" and lab.get("failed", 1) == 0 and lab.get("missing", 1) == 0 else "partial"
        for column in ("contract", "correct", "safe", "continuous", "fast", "proven"):
            board["plan-lab"][column] = _cell(
                lab_state, f"Lab {lab.get('reached', 0)}/{lab.get('n_objectives', 10)}. Verdict {lab.get('verdict')}.",
                "ai.eval.agent_deep_bench", "Lab evidence does not close the production row.", "Keep this row labeled lab.", observed,
            )
    except Exception as exc:
        board["plan-lab"]["proven"] = _cell("unmeasured", type(exc).__name__, "ai.eval.agent_deep_bench")
    full = _latest_json("production_readiness")
    partial = _latest_json("persona_recheck")
    if full:
        path, report = full
        note = f"Latest full run {path.name}: {report.get('reached')}/{report.get('n')}."
        if partial and partial[0].name > path.name:
            note += f" Later partial run {partial[0].name} covers only {partial[1].get('scope') or partial[1].get('tier')}."
        observed = str(report.get("run_at") or "")
        mapping = {"correct": "R1", "safe": "R7", "continuous": "R8", "fast": "R10", "proven": "R12"}
        board["plan-prod"]["contract"] = _cell("reached", "Production readiness is R1–R12. Lab T1–T10 cannot close it.", "tasks_prod_bench", note, "Run a new full production bench.", observed)
        for column, kpi in mapping.items():
            status, kpi_note = _kpi_status(report, kpi)
            board["plan-prod"][column] = _cell(status, kpi_note or note, f"{path.relative_to(REPO)} {kpi}", note + " Night 2026-09-23 FAIL stays.", "Reach R1–R11 on a full run.", observed)
    return board


def _pulse_actualization() -> dict:
    board = _matrix(PULSE_ROWS, ACTUAL_COLUMNS)
    board["ask"]["built"] = _cell("reached", "Ask runs on the Nibras instance used by the benches.", "Nibras Pulse instance", "A running dev instance is not a production service.", "Keep Live separate from Built.")
    board["plan-prod"]["live"] = _cell("fail", "Enterprise go-live is not reached, and the retained night failure stays.", "tasks production bench; PV2-6B-nights.json", "Lab green does not make this deployment live.", "Clear the production gates on a full run.")
    return board


def _nibras_readiness() -> dict:
    board = _matrix(NIBRAS_ROWS, READINESS_COLUMNS)
    staff = _staff_go_live()
    payroll = _deployment_certificate()
    if staff["verdict"] == "ready":
        board["people"]["contract"] = _cell("reached", staff["actual"], staff["proof"], staff["limits"], "Keep the staff target separate from full People.", staff["observed_at"])
        board["people"]["proven"] = _cell("partial", "The staff gate passed. The full People lifecycle is a different target.", staff["proof"], staff["limits"], "Do not reuse this cell for payroll.", staff["observed_at"])
    if payroll["verdict"] == "limited":
        board["payroll"]["proven"] = _cell("fail", payroll["actual"], payroll["proof"], payroll["limits"], "Name the legal-month evidence that is missing.", payroll["observed_at"])
    for row_id, relative in (("stores", "backend/stores"), ("finance-a", "backend/fintrust"), ("finance-b", "backend/fintrust")):
        if not (REPO / relative).exists():
            board[row_id]["contract"] = _cell("missing", "No product contract with checks is declared.", relative, "A roadmap heading is not a contract.", "Write the target before measuring it.")
            board[row_id]["correct"] = _cell("absent", "No backend app exists.", relative, "A roadmap entry is not an implemented domain app.", "Build only after the target is accepted.")
    return board


def _nibras_actualization() -> dict:
    board = _matrix(NIBRAS_ROWS, ACTUAL_COLUMNS)
    staff = _staff_go_live()
    payroll = _deployment_certificate()
    if (REPO / "backend/people").exists():
        board["people"]["built"] = _cell("reached", "People, My, and Team are built for the Nibras brand.", "backend/people", "A built app is not a populated customer.", "Judge data and live use in their own columns.")
    if staff["verdict"] == "ready":
        board["people"]["live"] = _cell("reached", "Named staff journeys passed.", staff["proof"], staff["limits"], "Do not reuse this live cell for payroll.", staff["observed_at"])
    board["payroll"]["data"] = _cell("partial", "Imported salary can be estimated. Verified compensation is the authority.", "GOFSCO onboarding runbook; ADR-0029", "Seeded history is not customer completion.", "Show the data owner and the missing fields.")
    if payroll["verdict"] == "limited":
        board["payroll"]["live"] = _cell("fail", payroll["actual"], payroll["proof"], payroll["limits"], "Record the business signer and the missing reconciliation.", payroll["observed_at"])
    for row_id, relative in (("stores", "backend/stores"), ("finance-a", "backend/fintrust"), ("finance-b", "backend/fintrust")):
        if (REPO / relative).exists():
            continue
        board[row_id]["built"] = _cell("absent", "There is no application to configure or populate.", relative, "A source document is not a deployment.", "Leave the later gates blocked.")
        for column in ACTUAL_COLUMNS:
            if column == "built":
                continue
            board[row_id][column] = _cell("missing", "This gate cannot be met before the application exists.", relative, "Built is absent, so this gate is blocked.", "Accept the target before building.")
    return board


def _claim(**fields) -> dict:
    return fields


def _ask() -> dict:
    try:
        from ai.eval.chat_deep_bench import score_chat_bench

        report = score_chat_bench()
    except Exception as exc:
        return _unknown("pulse.ask", "Pulse Ask", "pulse", "Ask dependable", exc)
    failed = [
        row["name"]
        for row in report.get("objectives") or []
        if (row.get("column") or {}).get("honest") == "fail"
    ]
    return _claim(
        id="pulse.ask",
        domain="pulse",
        scope="product",
        title="Pulse Ask",
        target="Ask dependable",
        verdict=report.get("verdict") or "unknown",
        actual=f"{report.get('reached', 0)}/{report.get('n_objectives', 10)} reached",
        limits=("Failed: " + ", ".join(failed)) if failed else "No failed Ask objectives.",
        proof="ai.eval.chat_deep_bench",
        observed_at=str(report.get("date") or ""),
    )


def _plan_lab() -> dict:
    try:
        from ai.eval.agent_deep_bench import score_agent_bench

        report = score_agent_bench()
    except Exception as exc:
        return _unknown("pulse.plan_lab", "Pulse Plan lab", "pulse", "Plan lab", exc)
    return _claim(
        id="pulse.plan_lab",
        domain="pulse",
        scope="product",
        title="Pulse Plan · lab",
        target="Tasks lab T1–T10",
        verdict=report.get("verdict") or "unknown",
        actual=f"{report.get('reached', 0)}/{report.get('n_objectives', 10)} reached",
        limits="Lab evidence does not make Plan enterprise-ready.",
        proof="ai.eval.agent_deep_bench",
        observed_at=str(report.get("date") or ""),
    )


def _plan_production() -> dict:
    full = _latest_json("production_readiness")
    partial = _latest_json("persona_recheck")
    if full is None:
        return _claim(
            id="pulse.plan_production",
            domain="pulse",
            scope="product",
            title="Pulse Plan · production",
            target="Plan enterprise",
            verdict="unknown",
            actual="No full production run",
            limits="Lab results are not substituted.",
            proof="docs/pulse/evidence/PV2-tasks-prod-*.json",
            observed_at="",
        )
    path, report = full
    note = f"Latest full run {path.name}: {report.get('reached')}/{report.get('n')}."
    if partial and partial[0].name > path.name:
        scoped = partial[1].get("scope") or partial[1].get("tier")
        note += f" Later partial run {partial[0].name} covers only {scoped}."
    return _claim(
        id="pulse.plan_production",
        domain="pulse",
        scope="product",
        title="Pulse Plan · production",
        target="Plan enterprise",
        verdict=report.get("verdict") or "unknown",
        actual=f"{report.get('reached', 0)}/{report.get('n', 12)} full run",
        limits=note + " Night 2026-09-23 FAIL stays.",
        proof=str(path.relative_to(REPO)),
        observed_at=str(report.get("run_at") or ""),
    )


def _latest_json(tier: str) -> tuple[Path, dict] | None:
    found: list[tuple[Path, dict]] = []
    if not EVIDENCE.is_dir():
        return None
    for path in sorted(EVIDENCE.glob("PV2-tasks-prod-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("tier") == tier:
            found.append((path, payload))
    return found[-1] if found else None


def _staff_go_live() -> dict:
    path = REPO / "docs/nibras/evidence/NSR-9-go-live-gate.md"
    text = _read(path)
    ready = "**READY** for staff go-live" in text
    return _claim(
        id="nibras.staff",
        domain="nibras",
        scope="deployment",
        title="Staff People / My / Team",
        target="Staff go-live",
        verdict="ready" if ready else "unknown",
        actual="Named staff journeys" if ready else "Gate text not found",
        limits="This does not prove legal payroll, Stores, or Finance.",
        proof=str(path.relative_to(REPO)) if path.exists() else "",
        observed_at="2026-09-21" if ready else "",
    )


def _deployment_certificate() -> dict:
    path = REPO / "docs/assurance/NIBRAS-DEPLOYMENT-CERTIFICATE.md"
    text = _read(path)
    limited = "limited internal deployment" in text
    return _claim(
        id="nibras.payroll",
        domain="nibras",
        scope="deployment",
        title="Payroll deployment",
        target="Legal payroll month",
        verdict="limited" if limited else "unknown",
        actual="Internal demo of named journeys" if limited else "Certificate not found",
        limits="Not a lawyer-signable payroll month. Local WPS is not a PAM receipt.",
        proof=str(path.relative_to(REPO)) if path.exists() else "",
        observed_at="2026-09-23" if limited else "",
    )


def _missing_app(claim_id: str, title: str, relative_dir: str) -> dict:
    exists = (REPO / relative_dir).exists()
    return _claim(
        id=claim_id,
        domain="nibras",
        scope="product",
        title=title,
        target=f"{title} enterprise",
        verdict="present" if exists else "not_built",
        actual="Backend app present" if exists else "No backend app",
        limits="A roadmap entry is not an implemented domain app.",
        proof=relative_dir,
        observed_at="",
    )


def _unknown(claim_id: str, title: str, domain: str, target: str, exc: Exception) -> dict:
    return _claim(
        id=claim_id,
        domain=domain,
        scope="product",
        title=title,
        target=target,
        verdict="unknown",
        actual="Scorer unavailable",
        limits=type(exc).__name__,
        proof="",
        observed_at="",
    )


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""
