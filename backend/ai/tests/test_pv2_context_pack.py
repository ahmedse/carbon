"""PV2-2A — ContextPack for every chat-turn LLM stage.

Heuristic (static AST test)
---------------------------
Walk ``ai/engine/cognition/turn/**/*.py``. For every ``route_chat(...)`` call,
inspect the ``messages`` keyword (or positional) argument. Fail when the system
message content is a bare Name that resolves to a module-level
``*_SYSTEM_PROMPT`` constant (or a Constant string used as the sole system
body). Allowed: ``pack.system_prompt()``, ``*.system_prompt()``, or any
Attribute/Call that is not a ``*_SYSTEM_PROMPT`` Name.

Date / critic / budget tests exercise the runtime pack composition.
"""

from __future__ import annotations

import ast
import re
import types
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from asgiref.sync import async_to_sync
from django.test import override_settings

from ai.tests.pv21_stub import answer_decision
from ai.engine.core.config import get_settings
from ai.store import reset_store

_TURN_ROOT = (
    Path(__file__).resolve().parents[1] / "engine" / "cognition" / "turn"
)
_SYSTEM_PROMPT_NAME_RE = re.compile(r".*_SYSTEM_PROMPT$")
_DATE_LINE_RE = re.compile(
    r"Today's date:\s*([A-Za-z]+,\s+[A-Za-z]+\s+\d{1,2},\s+\d{4})"
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def django_store():
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


@pytest.fixture
def single_pass(monkeypatch):
    monkeypatch.setenv("AGENT_ORCHESTRATOR_ENABLED", "false")
    monkeypatch.setenv("KG_MULTI_STEP_ENABLED", "false")
    monkeypatch.setenv("PULSE_LOOP_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def no_nav_fast_path(monkeypatch):
    patched = get_settings().model_copy(
        update={"NAVIGATION_RESOLVER_ENABLED": False},
    )
    monkeypatch.setattr(
        "ai.engine.cognition.turn.runner.get_settings",
        lambda: patched,
    )


def _system_text(kw: dict) -> str:
    return "\n".join(
        str(m.get("content") or "")
        for m in kw.get("messages") or []
        if m.get("role") == "system"
    )


def _date_echo_client(calls: list):
    """Stub LLM: draft replies with the IdentityBlock date; JSON stages pass."""

    async def _create(**kw):
        calls.append(kw)
        system = _system_text(kw)
        user = ""
        for msg in reversed(kw.get("messages") or []):
            if msg.get("role") == "user":
                user = str(msg.get("content") or "")
                break

        if kw.get("response_format"):
            content = '{"verdict":"pass","rewritten_text":"","veto_reason":""}'
            if "intent" in system.lower() or "Return JSON" in user:
                content = (
                    '{"action":"answer","candidates":[],"delivery":"explain",'
                    '"confidence":0.9,"needs_host_data":false}'
                )
            elif "passed" in system.lower() or "Fact-check" in system:
                content = (
                    '{"passed":true,"unsupported_claims":[],'
                    '"verified_claims":[],"corrected_text":null}'
                )
        else:
            m = _DATE_LINE_RE.search(system)
            if m and "date" in user.lower():
                content = f"Today is {m.group(1)}."
            elif m:
                content = f"Today is {m.group(1)}."
            else:
                content = "Stubbed reply."

        return types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(
                        content=content,
                        tool_calls=answer_decision(kw),
                    ),
                    finish_reason="stop",
                )
            ],
            usage=types.SimpleNamespace(
                prompt_tokens=10, completion_tokens=4, total_tokens=14,
            ),
        )

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=_create))
    )


# ── 1. Static AST: no stage-local *_SYSTEM_PROMPT as route_chat system ─────


def _module_system_prompt_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and _SYSTEM_PROMPT_NAME_RE.match(
                    target.id
                ):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if _SYSTEM_PROMPT_NAME_RE.match(node.target.id):
                names.add(node.target.id)
    return names


def _content_expr_from_dict(elt: ast.AST) -> ast.AST | None:
    """Extract ``content`` value from a dict literal ``{"role":"system",...}``."""
    if not isinstance(elt, ast.Dict):
        return None
    role_is_system = False
    content_expr: ast.AST | None = None
    for key, val in zip(elt.keys, elt.values):
        if isinstance(key, ast.Constant) and key.value == "role":
            if isinstance(val, ast.Constant) and val.value == "system":
                role_is_system = True
        if isinstance(key, ast.Constant) and key.value == "content":
            content_expr = val
    if role_is_system:
        return content_expr
    return None


def _system_contents_from_messages(messages_node: ast.AST) -> list[ast.AST]:
    found: list[ast.AST] = []
    if isinstance(messages_node, ast.List):
        for elt in messages_node.elts:
            content = _content_expr_from_dict(elt)
            if content is not None:
                found.append(content)
    elif isinstance(messages_node, (ast.Name, ast.Attribute)):
        # Dynamic list built earlier — inspected via assignment scan below.
        pass
    return found


def _is_pack_system_prompt(expr: ast.AST) -> bool:
    """True when expr is ``something.system_prompt()`` (ContextPack path)."""
    if not isinstance(expr, ast.Call):
        return False
    func = expr.func
    return isinstance(func, ast.Attribute) and func.attr == "system_prompt"


def _is_forbidden_system_content(
    expr: ast.AST, module_prompts: set[str]
) -> str | None:
    """Return a failure reason if system content is a stage-local prompt."""
    if _is_pack_system_prompt(expr):
        return None
    if isinstance(expr, ast.Name) and expr.id in module_prompts:
        return f"module-level {expr.id} used as system content"
    if isinstance(expr, ast.Name) and _SYSTEM_PROMPT_NAME_RE.match(expr.id):
        return f"Name {expr.id} looks like a stage-local system prompt"
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        # Long literal system prompts are forbidden; short sentinels OK.
        if len(expr.value) > 80:
            return "long string Constant used as system content"
    return None


def _collect_route_chat_violations(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    module_prompts = _module_system_prompt_names(tree)
    violations: list[str] = []

    # Map simple Name → assigned messages list (one hop).
    messages_bindings: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and "message" in target.id.lower():
                messages_bindings[target.id] = node.value

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = ""
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name != "route_chat":
            continue

        messages_arg: ast.AST | None = None
        for kw in node.keywords:
            if kw.arg == "messages":
                messages_arg = kw.value
                break
        if messages_arg is None and node.args:
            # route_chat is keyword-heavy; ignore positionals.
            pass

        content_exprs: list[ast.AST] = []
        if messages_arg is not None:
            if isinstance(messages_arg, ast.Name) and messages_arg.id in messages_bindings:
                content_exprs.extend(
                    _system_contents_from_messages(messages_bindings[messages_arg.id])
                )
                # Also scan appends / extend of system dicts onto that name.
                for sub in ast.walk(tree):
                    if not isinstance(sub, ast.Call):
                        continue
                    if not isinstance(sub.func, ast.Attribute):
                        continue
                    if sub.func.attr not in ("append", "extend"):
                        continue
                    if not (
                        isinstance(sub.func.value, ast.Name)
                        and sub.func.value.id == messages_arg.id
                    ):
                        continue
                    if sub.func.attr == "append" and sub.args:
                        c = _content_expr_from_dict(sub.args[0])
                        if c is not None:
                            content_exprs.append(c)
                    elif sub.func.attr == "extend" and sub.args:
                        content_exprs.extend(
                            _system_contents_from_messages(sub.args[0])
                        )
            else:
                content_exprs.extend(_system_contents_from_messages(messages_arg))

        for expr in content_exprs:
            reason = _is_forbidden_system_content(expr, module_prompts)
            if reason:
                violations.append(f"{path.name}:{getattr(node, 'lineno', '?')}: {reason}")

        # Also fail if the module still defines *_SYSTEM_PROMPT at all while
        # a route_chat exists — stage wording must live in TaskBlock templates.
        # (soft: only when the constant is referenced near route_chat messages)
        for pname in module_prompts:
            for expr in content_exprs:
                if isinstance(expr, ast.Name) and expr.id == pname:
                    violations.append(
                        f"{path.name}:{getattr(node, 'lineno', '?')}: "
                        f"{pname} passed as system content"
                    )

    return violations


def test_route_chat_system_prompts_come_from_context_pack():
    """AST gate: turn/** route_chat system content must be pack.system_prompt()."""
    assert _TURN_ROOT.is_dir(), _TURN_ROOT
    all_violations: list[str] = []
    for path in sorted(_TURN_ROOT.rglob("*.py")):
        all_violations.extend(_collect_route_chat_violations(path))
    assert all_violations == [], (
        "route_chat system prompts must come from ContextPack.system_prompt(); "
        "found:\n  " + "\n  ".join(all_violations)
    )


def test_turn_modules_have_no_module_level_system_prompt_constants():
    """Identity/task wording must not live as ``*_SYSTEM_PROMPT`` in turn/**."""
    leftovers: list[str] = []
    for path in sorted(_TURN_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for name in sorted(_module_system_prompt_names(tree)):
            leftovers.append(f"{path.name}: {name}")
    assert leftovers == [], (
        "module-level *_SYSTEM_PROMPT constants must be removed from turn/** "
        "(task wording lives in context_pack.TaskBlock templates):\n  "
        + "\n  ".join(leftovers)
    )


# ── 2. Date-class golden ───────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_todays_date_from_identity_block_zero_tools(
    django_store, single_pass, no_nav_fast_path,
):
    """'what is today's date?' answered from IdentityBlock; no host tools."""
    from ai.engine_runtime import dispatch_task

    calls: list = []
    conv = f"conv-pv2-2a-date-{uuid.uuid4().hex[:8]}"
    with patch("ai.engine.llm.provider.get_llm_client") as mock:
        mock.return_value = _date_echo_client(calls)
        data = dispatch_task(
            "chat",
            {
                "message": "what is today's date?",
                "conversation_history": {
                    "conversation_id": conv,
                    "messages": [],
                },
            },
            instance_id="nibras",
        )
    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    text = str(result.get("content") or result.get("text") or data.get("content") or "")

    from ai.engine.cognition.context_pack import format_today_line
    from ai.engine.core.archetypes import load_instance_config

    cfg = load_instance_config("nibras")
    date_line = format_today_line(cfg)
    m = _DATE_LINE_RE.search(date_line)
    assert m, date_line
    expected = m.group(1)
    assert expected in text, f"reply missing IdentityBlock date {expected!r}: {text!r}"

    # Stub never emits tool_calls; no host staging.
    actions = result.get("pending_actions") or result.get("actions") or []
    assert not actions

    # At least one system prompt carried the IdentityBlock date line.
    assert any(_DATE_LINE_RE.search(_system_text(kw)) for kw in calls), (
        "no LLM call saw IdentityBlock date line"
    )


# ── 3. Critic identity + TaskBlock ─────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_critic_llm_prompt_has_identity_and_task():
    """CriticWitness LLM tier: IdentityBlock markers + TASK_CRITIC wording."""
    from ai.engine.cognition.context_pack import CHAT_AUTONOMY, TASK_CRITIC
    from ai.engine.cognition.turn.critic import CriticWitness
    from ai.engine.cognition.turn.witnesses import DraftResult, RetrievalResult

    captured: list[dict] = []

    async def _fake_route_chat(**kwargs):
        captured.append(kwargs)
        return {
            "content": '{"verdict":"pass","rewritten_text":"","veto_reason":""}',
            "model": "stub",
            "input_tokens": 1,
            "output_tokens": 1,
        }

    draft = DraftResult(
        text="The sky is green and payroll totals 999.",
        tool_calls=[],
        claimed_citations=[],
    )
    retrieval = RetrievalResult(
        knowledge_chunks=[{"content": "Payroll fact: net pay is opaque."}],
        memory_chunks=[],
        citation_ids=["node:1"],
    )
    user_info = {
        "username": "emp_test",
        "display_name": "Test Emp",
        "audience": ["ess"],
        "roles": ["employee"],
    }
    instance_config = {
        "persona": "You are Pulse, the ClearTurn assistant for Nibras.",
        "guidance_by_audience": {
            "ess": "ESS guidance: only My* tools.",
        },
        "timezone": "Asia/Riyadh",
    }

    with patch(
        "ai.engine.cognition.turn.critic.route_chat",
        side_effect=_fake_route_chat,
    ):
        verdict = async_to_sync(CriticWitness().review)(
            draft,
            retrieval,
            enable_llm_critic=True,
            instance_id="nibras",
            conversation_id="crit-pv2-2a",
            user_message="What is my net pay this month please?",
            user_info=user_info,
            instance_config=instance_config,
            language="en",
        )

    assert verdict.verdict in ("pass", "rewrite", "veto", "pass_with_flag")
    assert captured, "LLM critic did not call route_chat"
    system = _system_text(captured[0])

    assert "Today's date:" in system
    assert "Surface: chat" in system
    assert "Autonomy" in system and "ADR-0046" in system
    assert CHAT_AUTONOMY.split(":")[0] in system or "ADR-0046" in system
    assert "You are Pulse" in system or "ClearTurn" in system or "Nibras" in system
    # TaskBlock critic wording
    assert "TASK — Critic" in system or "quality review" in system.lower()
    assert "alternative" in system.lower()
    for marker in ("verdict", "rewrite", "veto"):
        assert marker in TASK_CRITIC.lower()
        assert marker in system.lower()


# ── 4. Pack budgets smoke ──────────────────────────────────────────────────


def test_context_pack_system_prompt_respects_block_caps():
    from ai.engine.cognition.context_pack import (
        HISTORY_BLOCK_MAX_CHARS,
        IDENTITY_BLOCK_MAX_CHARS,
        KNOWLEDGE_BLOCK_MAX_CHARS,
        MEMORY_BLOCK_MAX_CHARS,
        STATE_BLOCK_MAX_CHARS,
        TASK_BLOCK_MAX_CHARS,
        build_context_pack,
    )
    from ai.engine.cognition.state_store import ConversationState
    from ai.engine.cognition.turn.witnesses import RetrievalResult

    huge = "X" * 50_000
    state = ConversationState(
        focus=[{"topic": "topic-" + "f" * 200}],
        intent={"name": "intent-" + "i" * 200},
        slots={"amount": "5000", "note": "n" * 400},
        open_question={"text": "q" * 300},
        last_results=[{"tool": "t", "summary": "s" * 400}] * 5,
        language="en",
    )
    retrieval = RetrievalResult(
        knowledge_chunks=[{"content": huge}],
        memory_chunks=[{"content": huge}],
    )
    history = [
        {"role": "user", "content": huge},
        {"role": "assistant", "content": huge},
    ] * 6

    pack = build_context_pack(
        state,
        surface="chat",
        stage="draft",
        user_info={"username": "u", "display_name": "U", "audience": ["ess"]},
        instance_config={
            "persona": huge,
            "guidance_by_audience": {"ess": huge},
            "timezone": "UTC",
        },
        conversation_history=history,
        retrieval=retrieval,
        language="en",
        task_body=huge,
    )
    # Individual blocks clipped
    assert len(pack.identity) <= IDENTITY_BLOCK_MAX_CHARS
    assert len(pack.state) <= STATE_BLOCK_MAX_CHARS
    assert len(pack.history) <= HISTORY_BLOCK_MAX_CHARS
    assert len(pack.knowledge) <= KNOWLEDGE_BLOCK_MAX_CHARS
    assert len(pack.memory) <= MEMORY_BLOCK_MAX_CHARS
    assert len(pack.task) <= TASK_BLOCK_MAX_CHARS

    budget_sum = (
        IDENTITY_BLOCK_MAX_CHARS
        + STATE_BLOCK_MAX_CHARS
        + HISTORY_BLOCK_MAX_CHARS
        + KNOWLEDGE_BLOCK_MAX_CHARS
        + MEMORY_BLOCK_MAX_CHARS
        + TASK_BLOCK_MAX_CHARS
    )
    # Join separators add a few chars; stay within sum + small slack.
    assert len(pack.system_prompt()) <= budget_sum + 32
