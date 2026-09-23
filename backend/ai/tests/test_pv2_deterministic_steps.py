"""PV2-3A — deterministic-first fully bound process_dial steps.

Fully bound ``call_host_api`` steps (complete write_slots, no ``{{…}}``) skip
DraftWitness + observe: bind → consent (RULE_21) → commit with bilingual
``step_templates`` summaries and ``llm_calls == 0``. Partial binding keeps
today's draft path.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai.engine.cognition.plan.export_bind import (
    contains_mustache_placeholders,
    is_fully_bound_host_api,
    render_step_template,
)
from ai.engine.cognition.plan.loop import ReActLoop
from ai.engine.cognition.plan.planner import PlanStep
from ai.engine.cognition.turn.witnesses import RetrievalResult
from ai.engine.core.archetypes import load_instance_config

pytestmark = pytest.mark.asyncio

_CATALOG = [
    {
        "name": "submit_my_leave",
        "write_slots": [
            {"field": "leave_type", "required": True},
            {"field": "start_date", "required": True},
            {"field": "end_date", "required": True},
            {"field": "days", "required": True},
        ],
    },
    {
        "name": "submit_my_loan",
        "write_slots": [
            {"field": "loan_type", "required": True},
            {"field": "principal", "required": True},
            {"field": "term_months", "required": True},
            {"field": "interest_rate", "required": False},
            {"field": "start_date", "required": True},
        ],
    },
    {
        "name": "submit_my_attendance_permission",
        "write_slots": [
            {"field": "permission_type", "required": True},
            {"field": "date", "required": True},
            {"field": "hours", "required": True},
        ],
    },
]


def _nibras_cfg() -> dict:
    cfg = load_instance_config("nibras") or {}
    # Prefer live catalog; fall back to minimal fixture if yaml unloadable.
    if not cfg.get("api_catalog"):
        cfg = {**cfg, "api_catalog": _CATALOG}
    return cfg


def _leave_args(**overrides) -> dict:
    body = {
        "leave_type": "annual",
        "start_date": "2026-10-01",
        "end_date": "2026-10-03",
        "days": 3,
    }
    body.update(overrides)
    return {
        "api_name": "submit_my_leave",
        "body": body,
        "explanation": "Submit leave",
    }


def _loan_args(**overrides) -> dict:
    body = {
        "loan_type": "emergency",
        "principal": 5000,
        "term_months": 12,
        "start_date": "2026-09-23",
        "interest_rate": 0,
    }
    body.update(overrides)
    return {
        "api_name": "submit_my_loan",
        "body": body,
        "explanation": "Submit loan",
    }


def _attendance_args(**overrides) -> dict:
    body = {
        "permission_type": "personal",
        "date": "2026-09-24",
        "hours": 2,
    }
    body.update(overrides)
    return {
        "api_name": "submit_my_attendance_permission",
        "body": body,
        "explanation": "Submit attendance permission",
    }


# ── Pure helpers ───────────────────────────────────────────────────────────


def test_mustache_and_binding_helpers():
    assert contains_mustache_placeholders({"body": {"x": "{{amount}}"}}) is True
    assert contains_mustache_placeholders({"body": {"x": 5000}}) is False
    assert is_fully_bound_host_api("call_host_api", _loan_args(), _CATALOG) is True
    assert is_fully_bound_host_api(
        "call_host_api",
        _loan_args(principal=None),
        _CATALOG,
    ) is False
    assert is_fully_bound_host_api(
        "call_host_api",
        {
            "api_name": "submit_my_loan",
            "body": {"loan_type": "{{type}}", "principal": 1, "term_months": 1, "start_date": "2026-01-01"},
        },
        _CATALOG,
    ) is False
    assert is_fully_bound_host_api("search_knowledge", {}, _CATALOG) is False


def test_step_template_ar_en_snapshots():
    cfg = _nibras_cfg()
    templates = cfg.get("step_templates") or {}
    assert "submit_my_loan" in templates
    assert "submit_my_leave" in templates
    assert "submit_my_attendance_permission" in templates

    loan_en = render_step_template(
        "submit_my_loan", _loan_args()["body"], "en", templates,
    )
    loan_ar = render_step_template(
        "submit_my_loan", _loan_args()["body"], "ar", templates,
    )
    assert loan_en is not None and "emergency" in loan_en and "5000" in loan_en
    assert loan_ar is not None and "قرض" in loan_ar and "5000" in loan_ar
    assert loan_en != loan_ar

    leave_en = render_step_template(
        "submit_my_leave", _leave_args()["body"], "en", templates,
    )
    leave_ar = render_step_template(
        "submit_my_leave", _leave_args()["body"], "ar", templates,
    )
    assert leave_en and "annual" in leave_en and "2026-10-01" in leave_en
    assert leave_ar and "إجازة" in leave_ar

    att_en = render_step_template(
        "submit_my_attendance_permission",
        _attendance_args()["body"],
        "en",
        templates,
    )
    att_ar = render_step_template(
        "submit_my_attendance_permission",
        _attendance_args()["body"],
        "ar",
        templates,
    )
    assert att_en and "personal" in att_en
    assert att_ar and "حضور" in att_ar


# ── ReActLoop deterministic path ───────────────────────────────────────────


async def _run_bound_step(
    *,
    tool_args: dict,
    confirmation_token: str | None,
    language: str = "en",
    expect_draft_called: bool | None = None,
):
    """Drive ``_execute_step`` with mocked witnesses; return (result, dw, observe)."""
    cfg = _nibras_cfg()
    loop = ReActLoop.__new__(ReActLoop)
    loop.db = None
    loop._build_step_prompt = MagicMock(return_value="prompt")  # noqa: SLF001
    observe = AsyncMock(return_value=None)
    loop._observe = observe  # noqa: SLF001

    dw = AsyncMock()
    dw.draft = AsyncMock(
        return_value=SimpleNamespace(
            text="LLM should not run",
            tool_calls=[],
            tokens_used=99,
        )
    )
    cw = AsyncMock()

    async def _review(**kwargs):
        if kwargs.get("is_mutation") and not kwargs.get("confirmation_token"):
            return SimpleNamespace(
                verdict="veto",
                flags=["mutation_not_confirmed"],
                veto_reason="needs confirm",
            )
        return SimpleNamespace(verdict="pass", flags=[], veto_reason=None)

    cw.review = _review

    staged = {
        "tool_name": "call_host_api",
        "result": json.dumps(
            {
                "requires_confirmation": True,
                "execution_id": "exec-det-1",
                "message": "staged",
            }
        ),
        "summary": "host summary ignored when template present",
    }

    class _Host:
        async def confirm_execution(self, execution_id, expected_host_user_id=None):
            return {
                "status_code": 201,
                "data": {"id": 42},
                "summary": "host receipt",
            }

    ex = AsyncMock()
    ex.executor = _Host()
    ex.execute = AsyncMock(
        return_value=SimpleNamespace(completed_tools=[staged])
    )

    step = PlanStep(
        step_id=1,
        intent="Submit ESS request",
        tool_name="call_host_api",
        tool_args=tool_args,
        is_mutation=True,
    )

    result = await loop._execute_step(  # noqa: SLF001
        step=step,
        dw=dw,
        cw=cw,
        ex=ex,
        instance_id="nibras",
        conversation_id="c",
        user_message="submit",
        system_prompt="sp",
        conversation_history=None,
        instance_config=cfg,
        user_info={"language": language},
        retrieval=RetrievalResult(),
        progress_callback=None,
        stream_callback=None,
        dry_run=False,
        confirmation_token=confirmation_token,
        step_contexts={},
        host_user_id="u1",
    )
    if expect_draft_called is True:
        dw.draft.assert_called()
    elif expect_draft_called is False:
        dw.draft.assert_not_called()
    return result, dw, observe


@pytest.mark.parametrize(
    "tool_args_fn,lang,needle",
    [
        (_loan_args, "en", "emergency"),
        (_loan_args, "ar", "قرض"),
        (_leave_args, "en", "annual"),
        (_leave_args, "ar", "إجازة"),
        (_attendance_args, "en", "personal"),
        (_attendance_args, "ar", "حضور"),
    ],
)
async def test_bound_step_zero_llm_and_template_summary(tool_args_fn, lang, needle):
    result, dw, observe = await _run_bound_step(
        tool_args=tool_args_fn(),
        confirmation_token="resume-tok",
        language=lang,
        expect_draft_called=False,
    )
    assert result.llm_calls == 0
    assert result.paused is False
    assert result.executed is True
    assert result.error is None
    assert needle in (result.draft_text or "")
    assert "deterministic_host_step" in result.critic_flags
    dw.draft.assert_not_called()
    observe.assert_not_called()


async def test_bound_step_requires_consent_without_token():
    result, dw, observe = await _run_bound_step(
        tool_args=_loan_args(),
        confirmation_token=None,
        language="en",
        expect_draft_called=False,
    )
    assert result.llm_calls == 0
    assert result.paused is True
    assert result.executed is False
    assert "mutation_not_confirmed" in result.critic_flags
    assert result.confirmation_token
    assert "emergency" in (result.draft_text or "")
    dw.draft.assert_not_called()
    observe.assert_not_called()


async def test_partial_binding_still_drafts():
    """Missing required slot keeps today's draft → observe path."""
    partial = _loan_args()
    del partial["body"]["principal"]

    cfg = _nibras_cfg()
    assert is_fully_bound_host_api("call_host_api", partial, cfg.get("api_catalog")) is False

    result, dw, observe = await _run_bound_step(
        tool_args=partial,
        confirmation_token=None,
        language="en",
        expect_draft_called=True,
    )
    assert result.paused is True
    assert "mutation_not_confirmed" in result.critic_flags
    dw.draft.assert_called_once()
    # Partial path still pauses before execute — observe not reached.
    observe.assert_not_called()


async def test_mustache_placeholder_keeps_draft_path():
    args = _leave_args(leave_type="{{leave_type}}")
    cfg = _nibras_cfg()
    assert is_fully_bound_host_api("call_host_api", args, cfg.get("api_catalog")) is False
    result, dw, _ = await _run_bound_step(
        tool_args=args,
        confirmation_token=None,
        expect_draft_called=True,
    )
    assert result.paused is True
    dw.draft.assert_called_once()


# ── confirm_step template reuse (additive) ─────────────────────────────────


def test_plans_service_reuses_step_templates_for_final_response():
    """confirm_step / inline-commit path renders the same bilingual templates."""
    from ai.plans_service import PlansService

    cfg = _nibras_cfg()
    svc = PlansService()
    en = svc._render_bound_step_summary(  # noqa: SLF001
        "submit_my_loan",
        _loan_args()["body"],
        instance_config=cfg,
        user=SimpleNamespace(language="en"),
    )
    ar = svc._render_bound_step_summary(  # noqa: SLF001
        "submit_my_loan",
        _loan_args()["body"],
        instance_config=cfg,
        user=SimpleNamespace(language="ar"),
    )
    assert "emergency" in en and "5000" in en
    assert "قرض" in ar and "5000" in ar
    assert en != ar
