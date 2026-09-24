"""Q0 G6 understanding bank — offline baseline scorer + v21 understand scorer.

``--mode baseline`` (default): no LLM, no network. Compares a deterministic
decision ladder (refuse → handoff → nav → empty-host → coworker →
multi-domain clarify → ESS bind → aspect follow-up) to bank expectations.
Follow-up cases score against a synthetic leave-thread history unless the
case carries its own ``history``. Only ``tier: baseline`` cases gate; ``tier:
v21`` cases are reported under ``v21_pending`` (the ladder is not expected to
pass them — ADR-0049 §8: fixes are goldens + descriptions, not regexes).

``--mode understand``: one ``emit_decision`` call per utterance through the
same ``understand_turn`` / ``catalog_prompt_lines`` the runtime uses
(PULSE_UNDERSTAND=v21). Needs the LLM provider and the engine DB (cost log).
This is the ADR-0049 §5 gate: flip only after decision_accuracy ≥ 0.95.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from ai.engine.cognition.turn.ess_read import (
    bound_ess_self_api,
    is_bare_place_noun,
    is_named_employee_ask,
    matching_self_domains,
    preferred_self_api,
)

BANK_PATH = Path(__file__).resolve().parent / "g6_bank.yaml"
REPO_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = REPO_ROOT / "docs" / "pulse" / "evidence"

G6_TIERS = frozenset({"baseline", "v21"})
G6_UNDERSTAND_MIN = 0.95  # ADR-0049 §5 flip gate

G6_CATEGORIES = frozenset({
    "leave_balance",
    "leave_history",
    "loan",
    "payslip",
    "attendance",
    "followup",
    "typo",
    "multi_intent",
    "nav_bare",
    "coworker",
    "empty_host",
    "process",
    "off_limits",
})

# Synthetic prior turn so aspect follow-ups bind the leave twin (Q0 offline).
_FOLLOWUP_HISTORY = (
    {"role": "user", "content": "What is my leave balance?"},
)

_REFUSE_RE = re.compile(
    r"(?i)("
    r"system\s+prompt|hidden\s+instructions?|developer\s+mode|"
    r"ignore\s+your\s+rules|jailbreak|"
    r"admin\s+password|passwords?|credentials?|"
    r"internal\s+JSON\s+schema|dump\s+your\s+internal|"
    r"اكشف\s*لي\s*system\s*prompt|"
    r"تعليمات(?:ك)?\s*السرية|"
    r"تجاهل\s*قواعد|"
    r"كلمة\s*مرور|"
    r"JSON\s*schema\s*الداخلي|اطبع\s*JSON"
    r")"
)

_EMPTY_HOST_RE = re.compile(
    r"(?i)("
    r"why\s+is\s+my\s+balance\s+zero|"
    r"no\s+(?:leave\s+requests?|loans?|payslips?)\b|"
    r"no\s+payslip\s+for|"
    r"لماذا\s*رصيدي\s*صفر|"
    r"لا\s*توجد\s*(?:طلبات?\s*)?(?:إجازة|اجازة|قروض|قسيمة)"
    r")"
)

_NAV_BARE_ONLY = frozenset({
    "attendance", "payroll", "حضور", "رواتب",
})

# Chat write → Agent handoff. Keep tight: bare ESS nouns stay reads.
_WRITE_HANDOFF_RE = re.compile(
    r"(?i)("
    r"\bi\s+want\s+to\s+request\s+leave\b|"
    r"\bi\s+need\s+an?\s+emergency\s+loan\b|"
    r"\bsubmit\b.{0,48}\bleave\b|"
    r"\bclock\s+me\s+in\b|"
    r"أريد\s*طلب\s*[اأإ]?جاز|"
    r"أريد\s*قرض\s*طارئ|"
    r"قدم\s*طلب\s*[اأإ]?جاز|"
    r"سجل\s*حضوري\s*الآن|سجل\s*حضورى\s*الان"
    r")"
)


def load_bank(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or BANK_PATH
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected YAML list in {p}")
    return data


def _coworker_leave_api(text: str) -> str | None:
    """Named / third-person leave → org entitlements API."""
    raw = text or ""
    try:
        from ai.engine.agent.tools import named_leave_balance_ask

        if named_leave_balance_ask(raw):
            return "list_leave_entitlements"
    except Exception:  # noqa: BLE001
        pass
    # First-person never routes to coworker entitlements.
    if re.search(r"(?i)\b(?:my|mine)\b|[اأإ]?جاز\w{0,4}ي|رصيد(?:ي)?\s", raw):
        if not re.search(
            r"(?i)\bemp[_\s-]?\d+\b|'s\s+leave|لـ\s*|does\s+[A-Z]",
            raw,
        ):
            return None
    if is_named_employee_ask(raw) and any(
        d.id == "leave" for d in matching_self_domains(raw)
    ):
        return "list_leave_entitlements"
    return None


def baseline_decision(
    text: str,
    *,
    history: list | None = None,
) -> dict[str, str]:
    """Deterministic offline decision for one utterance."""
    raw = (text or "").strip()
    if not raw:
        return {"op": "answer", "api": ""}

    if _REFUSE_RE.search(raw):
        return {"op": "refuse", "api": ""}

    if _EMPTY_HOST_RE.search(raw):
        return {"op": "answer", "api": ""}

    if _WRITE_HANDOFF_RE.search(raw):
        return {"op": "handoff_agent", "api": ""}

    coworker = _coworker_leave_api(raw)
    if coworker:
        return {"op": "call_tool", "api": coworker}

    if is_bare_place_noun(raw):
        token = re.sub(r"[?؟!]+$", "", raw).strip().casefold()
        if token in {t.casefold() for t in _NAV_BARE_ONLY}:
            return {"op": "navigate", "api": ""}

    domains = matching_self_domains(raw)
    if len(domains) > 1:
        return {"op": "clarify", "api": ""}

    api = preferred_self_api(raw)
    if api:
        return {"op": "call_tool", "api": api}

    bound = bound_ess_self_api(raw, history=history)
    if bound:
        return {"op": "call_tool", "api": bound}

    return {"op": "answer", "api": ""}


def _matches_expect(decision: dict[str, str], case: dict[str, Any]) -> bool:
    expect_api = str(case.get("expect_api") or "")
    expect_render = str(case.get("expect_render") or "")
    if expect_render and decision.get("render", "text") != expect_render:
        return False
    expect_process = str(case.get("expect_process") or "")
    if expect_process and decision.get("process", "") != expect_process:
        return False
    return decision["op"] == case["expect_op"] and decision["api"] == expect_api


def case_tier(case: dict[str, Any]) -> str:
    tier = str(case.get("tier") or "baseline").strip().lower()
    return tier if tier in G6_TIERS else "baseline"


def _history_for(case: dict[str, Any]) -> list | None:
    own = case.get("history")
    if isinstance(own, list) and own:
        return [dict(m) for m in own if isinstance(m, dict)]
    if case.get("category") == "followup":
        return list(_FOLLOWUP_HISTORY)
    return None


def _pair_result(
    case: dict[str, Any], ar_dec: dict[str, str], en_dec: dict[str, str]
) -> dict[str, Any]:
    return {
        "id": case["id"],
        "tier": case_tier(case),
        "ar": ar_dec,
        "en": en_dec,
        "ar_ok": _matches_expect(ar_dec, case),
        "en_ok": _matches_expect(en_dec, case),
        "parity": ar_dec["op"] == en_dec["op"] and ar_dec["api"] == en_dec["api"],
        "_expect": {
            "op": case.get("expect_op"),
            "api": str(case.get("expect_api") or ""),
        },
    }


def score_pair(case: dict[str, Any]) -> dict[str, Any]:
    hist = _history_for(case)
    ar_dec = baseline_decision(str(case.get("ar") or ""), history=hist)
    en_dec = baseline_decision(str(case.get("en") or ""), history=hist)
    return _pair_result(case, ar_dec, en_dec)


def _aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(results)
    utterance_hits = 0
    parity_hits = 0
    misses: list[str] = []
    for result in results:
        if result["ar_ok"]:
            utterance_hits += 1
        if result["en_ok"]:
            utterance_hits += 1
        if not result["ar_ok"] or not result["en_ok"]:
            misses.append(result["id"])
        if result["parity"]:
            parity_hits += 1
    total_utterances = 2 * n
    forced = 0
    for result in results:
        case_expect = result.get("_expect") or {}
        if case_expect.get("op") != "call_tool":
            continue
        for side in ("ar", "en"):
            dec = result.get(side) or {}
            if dec.get("op") != "call_tool" or dec.get("api") != case_expect.get("api"):
                forced += 1
    return {
        "n": n,
        "decision_accuracy": (
            utterance_hits / total_utterances if total_utterances else 0.0
        ),
        "parity": parity_hits / n if n else 0.0,
        "misses": misses,
        "forced_call_misses": forced,
    }


def score_bank(
    cases: list[dict[str, Any]] | None = None,
    *,
    tier: str | None = "baseline",
) -> dict[str, Any]:
    """Offline ladder score. ``tier="baseline"`` (default) is the gate set;
    ``tier=None`` scores every case. ``v21_pending`` always lists the tier-v21
    cases with the ladder's (expected-miss) decisions for the record."""
    bank = cases if cases is not None else load_bank()
    gated = [c for c in bank if tier is None or case_tier(c) == tier]
    report = _aggregate([score_pair(c) for c in gated])
    report["tier"] = tier or "all"
    report["v21_pending"] = [
        {
            "id": r["id"],
            "expect": f"{c.get('expect_op')}:{c.get('expect_api') or ''}",
            "baseline_ar": f"{r['ar']['op']}:{r['ar']['api']}",
            "baseline_en": f"{r['en']['op']}:{r['en']['api']}",
            "baseline_passes": r["ar_ok"] and r["en_ok"],
        }
        for c in bank
        if case_tier(c) == "v21"
        for r in (score_pair(c),)
    ]
    return report


# ── v21 understand scorer (ADR-0049 §5 gate) ────────────────────────────────


def _case_state(case: dict[str, Any]) -> Any:
    """ConversationState for a case: ``state_last_api`` is the prior read."""
    api = str(case.get("state_last_api") or "").strip()
    if not api:
        return None
    from ai.engine.cognition.state_store import ConversationState

    digest = str(case.get("state_digest") or f"call_host_api {api}")
    return ConversationState(
        last_results=[{"turn": 1, "tool": "call_host_api", "api": api, "digest": digest}],
    )


def _decision_to_dict(decision: Any, state: Any = None) -> dict[str, str]:
    """Normalise to the api the runtime would execute (``act_on_decision``)."""
    from ai.engine.cognition.turn.pipeline_v21 import _continue_api

    if decision is None:
        # Runtime falls through to legacy; the understand call still missed.
        return {"op": "malformed", "api": "", "render": "text"}
    cmds = list(getattr(decision, "commands", None) or [])
    if not cmds:
        return {"op": "answer", "api": "", "render": "text"}
    first = cmds[0]
    op = str(getattr(first, "op", "") or "answer")
    name = str(getattr(first, "name", "") or "")
    api = name if op == "call_tool" else ""
    if op == "confirm":
        # A confirm on an offered read is that read.
        op, api = "call_tool", name
    elif op == "continue":
        resolved = _continue_api(state) or name
        if resolved:
            op, api = "call_tool", resolved
    return {
        "op": op,
        "api": api,
        "render": str(getattr(first, "render", "") or "text"),
        "process": str(getattr(first, "process_id", "") or "") if op == "handoff_agent" else "",
    }


async def understand_decision(
    text: str,
    *,
    history: list | None,
    instance_config: dict[str, Any],
    instance_id: str = "nibras",
    user_info: dict[str, Any] | None = None,
    state: Any = None,
) -> dict[str, str]:
    """One understand call, same prompt/catalog/validation as the runtime."""
    from ai.engine.cognition.turn.understand import (
        build_understand_system_prompt,
        catalog_context,
        catalog_prompt_lines,
        navigation_prompt_lines,
        understand_turn,
    )
    from ai.engine.cognition.turn.runner_helpers import (
        _scoped_api_catalog,
        _scoped_navigation_routes,
    )
    from ai.engine.llm.router import route_chat

    scoped_catalog = _scoped_api_catalog(instance_config, user_info)
    lines, allowed, writes = catalog_prompt_lines(
        text,
        scoped_catalog,
        k=12,
        context=catalog_context(history),
    )
    system = build_understand_system_prompt(
        catalog_lines=lines,
        navigation_lines=navigation_prompt_lines(
            _scoped_navigation_routes(instance_config, user_info)
        ),
        state=state,
        user_info=user_info,
        instance_config=instance_config,
    )
    messages: list[dict] = [{"role": "system", "content": system}]
    messages.extend(list(history or [])[-8:])
    messages.append({"role": "user", "content": text})

    async def complete(*, messages, tools, tool_choice, strict_tools):
        return await route_chat(
            task="cognition",
            instance_id=instance_id,
            conversation_id="g6-understand",
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            strict_tools=strict_tools,
            temperature=0.0,
        )

    decision = await understand_turn(
        complete=complete,
        messages=messages,
        catalog_tools=scoped_catalog,
        surface="chat",
        allowed_tools=allowed or None,
        write_tools=writes or None,
        state=state,
    )
    return _decision_to_dict(decision, state)


_G6_USER_INFO = {"username": "emp_1067", "is_staff": False, "is_superuser": False}


def _user_info_for(case: dict[str, Any]) -> dict[str, Any]:
    """Default persona is emp_1067 (ESS). ``audience`` scopes the catalog."""
    aud = case.get("audience")
    if isinstance(aud, list) and aud:
        return {**_G6_USER_INFO, "username": str(case.get("persona") or "emp_2378"), "audience": [str(a) for a in aud]}
    return dict(_G6_USER_INFO)


async def score_bank_understand(
    cases: list[dict[str, Any]] | None = None,
    *,
    instance_id: str = "nibras",
    tier: str | None = None,
) -> dict[str, Any]:
    """Score the bank through the understand call. ``tier=None`` = all cases."""
    from ai.engine.core.archetypes import load_instance_config

    bank = cases if cases is not None else load_bank()
    picked = [c for c in bank if tier is None or case_tier(c) == tier]
    cfg = load_instance_config(instance_id)
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for case in picked:
        hist = _history_for(case)
        state = _case_state(case)
        user_info = _user_info_for(case)
        try:
            ar_dec = await understand_decision(
                str(case.get("ar") or ""), history=hist,
                instance_config=cfg, instance_id=instance_id, user_info=user_info,
                state=state,
            )
            en_dec = await understand_decision(
                str(case.get("en") or ""), history=hist,
                instance_config=cfg, instance_id=instance_id, user_info=user_info,
                state=state,
            )
        except Exception as exc:  # noqa: BLE001 — record, keep scoring
            errors.append({"id": case["id"], "error": f"{type(exc).__name__}: {exc}"[:200]})
            ar_dec = en_dec = {"op": "error", "api": ""}
        results.append(_pair_result(case, ar_dec, en_dec))
    report = _aggregate(results)
    report.update({
        "mode": "understand",
        "tier": tier or "all",
        "measured_at": date.today().isoformat(),
        "gate_min": G6_UNDERSTAND_MIN,
        "gate_pass": report["decision_accuracy"] >= G6_UNDERSTAND_MIN and not errors,
        "by_tier": {
            t: _aggregate([r for r in results if r["tier"] == t])
            for t in sorted({r["tier"] for r in results})
        },
        "errors": errors,
        "cases": results,
    })
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="G6 scorer (baseline | understand)")
    parser.add_argument(
        "--mode",
        choices=("baseline", "understand"),
        default="baseline",
        help="baseline: offline ladder (no LLM). understand: one emit_decision call per utterance",
    )
    parser.add_argument(
        "--tier",
        choices=("baseline", "v21", "all"),
        default=None,
        help="Case subset. baseline mode defaults to `baseline`; understand mode to `all`",
    )
    parser.add_argument(
        "--write",
        nargs="?",
        const="__default__",
        metavar="PATH",
        help="Write full evidence JSON (understand default: docs/pulse/evidence/PV2.1-g6-understand-<date>.json)",
    )
    parser.add_argument(
        "--bank",
        default=str(BANK_PATH),
        help="Path to g6_bank.yaml",
    )
    args = parser.parse_args(argv)
    bank = load_bank(Path(args.bank))
    tier = None if args.tier == "all" else args.tier

    if args.mode == "understand":
        import os

        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        import django

        django.setup()
        report = asyncio.run(score_bank_understand(bank, tier=tier))
        summary = {
            k: report[k]
            for k in ("n", "decision_accuracy", "parity", "misses", "gate_pass", "by_tier", "errors")
        }
        default_out = EVIDENCE_DIR / f"PV2.1-g6-understand-{report['measured_at']}.json"
    else:
        report = score_bank(bank, tier="baseline" if tier is None else tier)
        summary = {k: report[k] for k in ("n", "tier", "decision_accuracy", "parity", "misses", "v21_pending")}
        default_out = None
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.write:
        out_path = default_out if args.write == "__default__" else Path(args.write)
        if out_path is None:
            parser.error("--write needs a PATH in baseline mode")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"evidence → {out_path}")
    if args.mode == "understand":
        return 0 if report["gate_pass"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
