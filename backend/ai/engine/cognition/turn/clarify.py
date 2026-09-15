"""Deterministic clarification policy (Pulse Phase 4 — P4-06).

Pure, domain-agnostic, and LLM-free. The policy decides — *before* any LLM
call — whether the agent should stop and ask the user a clarifying question
instead of guessing. It recognises three triggers, evaluated in this exact
precedence order:

1. ``ambiguous_identity`` — the object the user refers to matches zero or
   more than one candidate (0 = no match, >1 = multiple matches). We never
   pick one arbitrarily.
2. ``missing_evidence`` — evidence/source data is required for a grounded
   answer but is not available. We ask instead of hallucinating.
3. ``unclear_authority`` — the requested action needs a specific authority
   grant that the caller does not hold.

The "never guess authority" rule: when authority is unconfirmed we *always*
ask. An explicit wildcard grant (``"*"``) counts as a confirmed, unrestricted
grant — it is an explicit statement of permission, not a guess.

The module imports only the standard library so it stays safe to run inside
the engine runtime without pulling in Django models (ADR-0007 / RULE_20).
"""

from dataclasses import dataclass

# The set of recognised clarification triggers, in precedence order.
CLARIFICATION_REASONS = ("ambiguous_identity", "missing_evidence", "unclear_authority")


@dataclass(frozen=True)
class ClarificationDecision:
    """Outcome of the clarification policy for a single turn.

    ``reason`` is one of :data:`CLARIFICATION_REASONS` when a clarification
    is needed, otherwise ``None``. ``question`` is the neutral clarifying
    question to surface to the user (empty when no clarification is needed).
    """

    needs_clarification: bool = False
    reason: str | None = None
    question: str = ""


def evaluate_clarification(
    *,
    object_candidates: int,
    evidence_available: bool,
    evidence_required: bool,
    authority_granted: frozenset[str] | set[str],
    authority_required: str | None,
) -> ClarificationDecision:
    """Evaluate the clarification policy in precedence order.

    Returns the first triggered decision, or a clear decision when none of
    the three triggers fire.
    """
    # 1. Ambiguous identity: zero or more than one candidate.
    if object_candidates < 1 or object_candidates > 1:
        return ClarificationDecision(
            needs_clarification=True,
            reason="ambiguous_identity",
            question=(
                "Which item do you mean? Please give the exact name or id."
            ),
        )

    # 2. Missing evidence: required for a grounded answer, but unavailable.
    if evidence_required and not evidence_available:
        return ClarificationDecision(
            needs_clarification=True,
            reason="missing_evidence",
            question=(
                "I don't have enough evidence for that yet. Could you "
                "provide the source document or the missing data?"
            ),
        )

    # 3. Unclear authority — never guess authority. A ``"*"`` wildcard grant
    #    is an explicit unrestricted grant and therefore counts as clear.
    granted = set(authority_granted)
    if authority_required is not None and authority_required not in granted and "*" not in granted:
        return ClarificationDecision(
            needs_clarification=True,
            reason="unclear_authority",
            question=(
                f"I'm not sure I'm authorised to {authority_required}. "
                "Could you confirm who should perform this?"
            ),
        )

    return ClarificationDecision(
        needs_clarification=False,
        reason=None,
        question="",
    )
