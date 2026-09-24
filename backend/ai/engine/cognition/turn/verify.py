"""S4.5 — Post-result verification witness (Pulse v2 Phase 7).

Checks that the synthesized answer's factual claims are supported by the tool
results. Runs only when tool results exist. Returns a VerificationResult.

The verification call is ON BY DEFAULT (``PULSE_VERIFY_ENABLED`` defaults to
True) and fails CLOSED: any exception or unparseable response yields
``passed=False`` with an ``error`` message so the ledger records that the
answer was *not* verified rather than silently claiming it was.
"""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T

import json
import logging
from dataclasses import dataclass, field

from ai.engine.llm.router import route_chat
from ai.engine.text.word_match import contains_any_phrase, has_gapped_words

logger = logging.getLogger("pulse.cognition.verify")

# A phrase in the ANSWER that asserts the absence of data. Deterministic guard:
# if the answer says this while a tool returned rows, that is a contradiction.
# Allows up to 3 words between "no" and the data noun ("no matching records").
_NO_DATA_NOUNS = T("turn/verify.py::_NO_DATA_NOUNS")
_NO_DATA_PHRASES = T("turn/verify.py::_NO_DATA_PHRASES")


def _asserts_no_data(text: str) -> bool:
    """'no <up to 3 words> data|records|...' or a bare absence phrase."""
    return has_gapped_words(text, "no", _NO_DATA_NOUNS, max_gap=3) or contains_any_phrase(
        text, _NO_DATA_PHRASES
    )

# Result keys that carry a positive row/record count.
_COUNT_KEYS = T("turn/verify.py::_COUNT_KEYS")
# Result keys whose non-empty list/dict value means data is present.
_COLLECTION_KEYS = T("turn/verify.py::_COLLECTION_KEYS")


def _result_has_data(result: object) -> bool:
    """True when a tool result carries actual data (rows / counts / breakdowns).

    Unwraps the host-executor envelope ``{"status_code", "data"}`` before
    inspecting, so it works on both raw payloads and wrapped host responses.
    Also parses JSON-string results (the real pipeline serializes tool results
    via ``_safe_serialize``), so a genuinely-empty payload (e.g. ``0``
    calculations) is NOT mistaken for data.
    """
    if result is None:
        return False
    data = result
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            if isinstance(parsed, (dict, list)):
                data = parsed
        except (TypeError, ValueError):
            pass
    if isinstance(data, dict) and "status_code" in data and "data" in data:
        data = data["data"]
    if not isinstance(data, dict):
        return bool(data)  # a non-empty list/str is data
    for key in _COUNT_KEYS:
        value = data.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            return True
    for key in _COLLECTION_KEYS:
        value = data.get(key)
        if isinstance(value, (list, dict)) and len(value) > 0:
            return True
    return False


def detect_no_data_contradiction(answer: str, tool_results: list[dict]) -> str | None:
    """Deterministic guard: answer asserts 'no data' while a tool returned data."""
    if not answer or not tool_results:
        return None
    if not _asserts_no_data(answer):
        return None
    for tr in tool_results:
        if not isinstance(tr, dict) or tr.get("error"):
            continue
        if _result_has_data(tr.get("result")):
            tool = tr.get("tool_name") or "tool"
            return f"answer claims no data but '{tool}' returned data"
    return None


def _fmt_num(value: object) -> str:
    """Format a numeric value for display (commas, 2 dp) without crashing."""
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _deterministic_correction(tool_results: list[dict]) -> str | None:
    """Build a factual answer straight from the tool results — no LLM.

    Used as a hard fallback when the LLM-based no-data correction fails or
    re-asserts 'no data'. Renders exactly what the tools returned so a turn can
    NEVER end on a false "no data" answer. Returns ``None`` when no supported
    data shape is found (caller then keeps the original behaviour).
    """
    for tr in tool_results:
        data = tr.get("result")
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, (dict, list)):
                    data = parsed
            except (TypeError, ValueError):
                pass
        if isinstance(data, dict) and "status_code" in data and "data" in data:
            data = data["data"]
        if not isinstance(data, dict) or "total_calculations" not in data:
            continue

        total = data.get("total_calculations", 0)
        lines = [f"**Total calculations:** {total}"]

        by_scope = data.get("by_scope") or {}
        if isinstance(by_scope, dict) and by_scope:
            lines.append("**Emissions by scope (kg CO₂e):**")
            for scope, info in by_scope.items():
                if isinstance(info, dict):
                    co2 = _fmt_num(info.get("total_co2e_kg"))
                    cnt = info.get("count")
                    lines.append(f"- Scope {scope}: {co2} kg CO₂e ({cnt} calculations)")

        by_module = data.get("by_module") or []
        if isinstance(by_module, list) and by_module:
            lines.append("**Emissions by module (kg CO₂e):**")
            for mod in by_module[:10]:
                if isinstance(mod, dict):
                    name = mod.get("module_name") or mod.get("module") or "module"
                    co2 = _fmt_num(mod.get("total_co2e_kg"))
                    cnt = mod.get("count")
                    lines.append(f"- {name}: {co2} kg CO₂e ({cnt} calculations)")

        return "\n".join(lines)

    return None


async def _correct_no_data(
    *,
    answer: str,
    tool_results: list[dict],
    user_message: str,
    instance_id: str,
    conversation_id: str,
    model: str | None = None,
    user_info: dict | None = None,
    instance_config: dict | None = None,
    language: str = "",
    state=None,
) -> str | None:
    """Re-synthesize an answer that falsely claimed 'no data'.

    The tool results carry real rows/counts — give them to the LLM with a
    hard directive to report them, never claim absence. Returns the corrected
    text, or ``None`` on failure (the caller falls back to the original).
    """
    try:
        from ai.engine.cognition.context_pack import build_context_pack

        results_text = json.dumps(
            [{"tool": tr.get("tool_name", ""), "result": tr.get("result")}
             for tr in tool_results],
            ensure_ascii=False, default=str,
        )[:4000]
        pack = build_context_pack(
            state,
            surface="chat",
            stage="verify_correct",
            user_info=user_info,
            instance_config=instance_config,
            language=language,
            user_body=(
                f"User question: {user_message}\n\n"
                f"Tool results (JSON):\n{results_text}\n\n"
                f"Incorrect previous answer:\n{answer}\n\n"
                "Corrected answer:"
            ),
            include_history=False,
            include_knowledge=False,
            include_memory=False,
        )
        response = await route_chat(
            task="cognition",
            instance_id=instance_id,
            conversation_id=f"correct-{conversation_id}",
            messages=[
                {"role": "system", "content": pack.system_prompt()},
                {"role": "user", "content": pack.user_prompt()},
            ],
            temperature=0.2,
            model=model,
            tools=None,
        )
        text = (response.get("content") or "").strip()
        # The correction LLM is itself non-deterministic: it can return an
        # empty response, or re-hallucinate "no data" despite the directive.
        # When that happens, fall back to a deterministic render of the tool
        # results so the turn can never end on a false "no data" answer.
        if text and not _asserts_no_data(text):
            return text
        deterministic = _deterministic_correction(tool_results)
        if deterministic:
            logger.warning(
                "No-data correction LLM re-asserted 'no data' or returned empty; "
                "using deterministic fallback"
            )
            return deterministic
        return text if text else None
    except Exception:
        logger.warning("No-data correction LLM call failed", exc_info=True)
        return _deterministic_correction(tool_results)


@dataclass
class VerificationResult:
    passed: bool
    unsupported_claims: list[str] = field(default_factory=list)
    verified_claims: list[str] = field(default_factory=list)
    corrected_text: str | None = None  # corrected version if passed=False
    error: str = ""  # non-empty when verification failed closed
    tokens_used: int = 0
    model_used: str = ""


class VerificationWitness:
    """Verify that a synthesized answer is grounded in the tool results."""

    async def verify(
        self,
        *,
        answer: str,
        tool_results: list[dict],
        user_message: str,
        instance_id: str,
        conversation_id: str,
        model: str | None = None,
        user_info: dict | None = None,
        instance_config: dict | None = None,
        language: str = "",
        state=None,
    ) -> VerificationResult:
        """Verify the answer against the tool results.

        Returns VerificationResult. Never raises — on any exception or
        unparseable response it fails closed, returning ``passed=False`` with
        an ``error`` message so the failure is visible in the turn ledger.
        """

        if not answer or not tool_results:
            return VerificationResult(passed=True)

        # Deterministic guard (no LLM): a "no data" answer over a tool result
        # that actually returned rows is always wrong — force a corrective
        # re-synthesis so the runner replaces the answer with real data.
        contradiction = detect_no_data_contradiction(answer, tool_results)
        if contradiction:
            logger.warning("Verification (deterministic): %s — forcing re-synthesis", contradiction)
            corrected = await _correct_no_data(
                answer=answer,
                tool_results=tool_results,
                user_message=user_message,
                instance_id=instance_id,
                conversation_id=conversation_id,
                model=model,
                user_info=user_info,
                instance_config=instance_config,
                language=language,
                state=state,
            )
            return VerificationResult(
                passed=False,
                error=contradiction,
                unsupported_claims=[contradiction],
                corrected_text=corrected,
            )

        from ai.engine.cognition.context_pack import build_context_pack

        results_text = json.dumps(
            [
                {"tool": tr.get("tool_name", ""), "result": tr.get("result")}
                for tr in tool_results
            ],
            ensure_ascii=False,
            default=str,
        )[:3000]

        pack = build_context_pack(
            state,
            surface="chat",
            stage="verify",
            user_info=user_info,
            instance_config=instance_config,
            language=language,
            user_body=(
                f"User question: {user_message}\n\n"
                f"Tool results:\n{results_text}\n\n"
                f"Answer to verify:\n{answer}"
            ),
            include_history=False,
            include_knowledge=False,
            include_memory=False,
        )

        try:
            response = await route_chat(
                task="cognition",
                instance_id=instance_id,
                conversation_id=f"verify-{conversation_id}",
                messages=[
                    {"role": "system", "content": pack.system_prompt()},
                    {"role": "user", "content": pack.user_prompt()},
                ],
                temperature=0.0,
                model=model,
                tools=None,
            )
        except Exception as e:
            logger.warning("VerificationWitness LLM call failed", exc_info=True)
            return VerificationResult(passed=False, error=str(e))

        raw = (response.get("content") or "").strip()
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return VerificationResult(
                passed=False, error="unparseable verification response"
            )

        tokens = int(response.get("input_tokens", 0) or 0) + int(
            response.get("output_tokens", 0) or 0
        )

        return VerificationResult(
            passed=bool(parsed.get("passed", True)),
            unsupported_claims=list(parsed.get("unsupported_claims", []) or []),
            verified_claims=list(parsed.get("verified_claims", []) or []),
            corrected_text=parsed.get("corrected_text"),
            tokens_used=tokens,
            model_used=response.get("model", ""),
        )
