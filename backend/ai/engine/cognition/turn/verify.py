"""S4.5 — Post-result verification witness (Pulse v2 Phase 7).

Checks that the synthesized answer's factual claims are supported by the tool
results. Runs only when tool results exist. Returns a VerificationResult.

The verification call is OPT-IN (``PULSE_VERIFY_ENABLED`` defaults to False)
because it adds one LLM call per response. When enabled, it always fail-open:
any error yields ``passed=True`` so it can never block the user's answer.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from ai.engine.llm.router import route_chat

logger = logging.getLogger("pulse.cognition.verify")


@dataclass
class VerificationResult:
    passed: bool
    unsupported_claims: list[str] = field(default_factory=list)
    verified_claims: list[str] = field(default_factory=list)
    corrected_text: str | None = None  # corrected version if passed=False
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
    ) -> VerificationResult:
        """Verify the answer against the tool results.

        Returns VerificationResult. Never raises — returns passed=True with
        empty claims on any failure (fail-open to avoid blocking responses).
        """

        if not answer or not tool_results:
            return VerificationResult(passed=True)

        results_text = json.dumps(
            [
                {"tool": tr.get("tool_name", ""), "result": tr.get("result")}
                for tr in tool_results
            ],
            ensure_ascii=False,
            default=str,
        )[:3000]

        system = (
            "You are a fact-checker. You receive: (1) an AI assistant's answer and "
            "(2) the raw tool results the answer was based on. "
            "Your job is to identify any specific numbers, dates, names, or percentages "
            "in the answer that contradict the tool results. "
            "Reply with JSON: "
            '{"passed": true/false, "unsupported_claims": ["claim1", ...], '
            '"verified_claims": ["claim1", ...], '
            '"corrected_text": "corrected answer or null if passed=true"}'
        )

        user_content = (
            f"User question: {user_message}\n\n"
            f"Tool results:\n{results_text}\n\n"
            f"Answer to verify:\n{answer}"
        )

        try:
            response = await route_chat(
                task="cognition",
                instance_id=instance_id,
                conversation_id=f"verify-{conversation_id}",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.0,
                model=model,
                tools=None,
            )
        except Exception:
            logger.warning("VerificationWitness LLM call failed", exc_info=True)
            return VerificationResult(passed=True)

        raw = (response.get("content") or "").strip()
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return VerificationResult(passed=True)

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
