"""S4 — Critic witness (rules-tier safety + LLM-tier reviewer).

Rules-tier (always runs):
1. Citation grounding: if retrieval found entities but the draft cites none → flag
2. Tenancy: tool calls don't carry host_user_id yet → always pass
3. Mutation check: any tool call with non-GET method and no confirmation → flag
4. Mutation confirmation gate: hard veto when is_mutation and no confirmation_token
5. Dry-run hook: skip mutation veto when dry_run=True

LLM-tier (enable_llm_critic=True, triggered when flags are raised):
- Sends draft + flags + knowledge context to LLM via route_chat
- LLM returns JSON: {"verdict": "pass"|"rewrite"|"veto", "rewritten_text": "...", "veto_reason": "..."}
- rewritten_text is populated when verdict is "rewrite"
"""
import json
import logging
import re

from ai.engine.cognition.turn.witnesses import CriticVerdict, DraftResult, RetrievalResult, SalienceResult
from ai.engine.llm.router import route_chat

logger = logging.getLogger("pulse.cognition.turn.critic")

# Phrases that indicate the LLM is admitting it doesn't know — not ambiguity, not safety.
_KNOWLEDGE_GAP_RE = re.compile(
    r"I('m| am) (not sure|not certain|unable to|not confident)|I don't have (specific|detailed|enough|complete|information|knowledge)|I (cannot|can't) (provide|give|confirm|answer)|I need (more|a bit more|additional) (context|information|detail)|I want to give you the most useful|could you clarify which specific",
    re.IGNORECASE,
)

# ── LLM critic prompt ────────────────────────────────────────────────────────

CRITIC_SYSTEM_PROMPT = """You are a safety and accuracy reviewer for an AI copilot. Review this draft response against the provided knowledge context.

RULES:
1. Fix ungrounded claims — anything not supported by the knowledge context.
2. Detect cross-tenant data leaks — data from one user/instance visible to another.
3. Fix incorrect API references — wrong endpoint names, wrong parameters.
4. If the draft is clean, return "pass". If minor fixes needed, return "rewrite" with corrected text. If the draft is dangerous or completely wrong, return "veto".

Return ONLY valid JSON — no markdown, no code fences, no explanation:
{"verdict": "pass"|"rewrite"|"veto", "rewritten_text": "...", "veto_reason": "..."}"""


class CriticWitness:
    """Rules-tier + optional LLM-tier safety review."""

    async def review(
        self,
        draft: DraftResult,
        retrieval: RetrievalResult,
        is_mutation: bool = False,
        dry_run: bool = False,
        confirmation_token: str | None = None,
        enable_llm_critic: bool = True,
        instance_id: str = "",
        conversation_id: str = "",
        user_message: str = "",
        salience: "SalienceResult | None" = None,
    ) -> CriticVerdict:
        """Review a draft against retrieval evidence and safety rules.

        Args:
            draft: S3 draft result with text + tool calls
            retrieval: S2 retrieval result for grounding check
            is_mutation: True if this step mutates host state
            dry_run: True if this is a preview-only run (skip mutation veto)
            confirmation_token: user-supplied confirmation for mutations
            enable_llm_critic: if True and flags raised, run LLM-tier review
            instance_id: Pulse instance ID (for LLM critic routing)
            conversation_id: Conversation UUID (for LLM critic routing)
            user_message: Original user message (for context in LLM review)
        """
        flags: list[str] = []

        # ── 1. Citation grounding check ────────────────────────────────────
        has_retrieval_results = bool(
            retrieval.knowledge_chunks
            and any(c.get("content", "").strip() for c in retrieval.knowledge_chunks)
        )
        has_citations = bool(draft.claimed_citations)
        has_inline_citations = "[node:" in draft.text or "[mem:" in draft.text

        if has_retrieval_results and not has_citations and not has_inline_citations:
            flags.append("ungrounded_claim")

        # ── 2. Tenancy check ───────────────────────────────────────────────
        # Always pass in PR-10 — tool calls don't carry host_user_id yet.

        # ── 3. Mutation check (legacy heuristic from PR-10) ────────────────
        for tc in draft.tool_calls:
            method = tc.get("method", "").upper()
            if method and method != "GET":
                confirmed = tc.get("confirmed", False)
                if not confirmed:
                    flags.append("unconfirmed_mutation")
                    break

        # ── 4. PR-20: Mutation confirmation gate ───────────────────────────
        if is_mutation:
            if dry_run:
                # Dry-run preview — skip mutation veto, add info flag
                flags.append("dry_run_preview")
            elif not confirmation_token:
                # Hard veto: mutation without user confirmation
                return CriticVerdict(
                    verdict="veto",
                    flags=["mutation_not_confirmed"],
                    veto_reason="Mutation step requires user confirmation. "
                               "Please use the confirmation dialog to proceed.",
                )

        # ── Knowledge gap detection (epistemic, not safety) ────────────────
        # Fires when: query is specific + LLM hedges/admits ignorance.
        # Does NOT fire when: query itself was ambiguous (that's the user's job to clarify).
        knowledge_gap = self._detect_knowledge_gap(draft.text, user_message, salience)
        if knowledge_gap and not is_mutation:
            return CriticVerdict(
                verdict="knowledge_gap",
                flags=["knowledge_gap"],
                partial_knowledge=draft.text.strip(),
            )

        # ── Rules-tier verdict (no flags = clean) ──────────────────────────
        if not flags:
            return CriticVerdict(verdict="pass")

        # ── Skip LLM critic for purely informational flags ─────────────────
        # dry_run_preview is a preview marker, not a safety concern —
        # the LLM critic would just confirm "pass" and waste a call.
        if flags == ["dry_run_preview"]:
            return CriticVerdict(verdict="pass_with_flag", flags=flags)

        # ── 5. LLM-tier review ─────────────────────────────────────────────
        if enable_llm_critic:
            return await self._llm_review(draft, retrieval, flags, instance_id, conversation_id, user_message)

        # ── Fallback: rules-only verdict ────────────────────────────────────
        return _rules_only_verdict(flags)

    def _detect_knowledge_gap(
        self,
        draft_text: str,
        user_message: str,
        salience: "SalienceResult | None",
    ) -> bool:
        """True when the LLM explicitly admits it doesn't know (hedging language).

        Short answers alone are NOT a knowledge gap — a one-line confident
        answer is perfectly valid. Only explicit hedging triggers this.
        Domain-agnostic: no domain terms.
        """
        text = draft_text.strip()
        if not text:
            return False  # empty handled separately by FallbackHandler

        # Primary signal: LLM explicitly says it doesn't know.
        is_hedging = bool(_KNOWLEDGE_GAP_RE.search(text))
        if not is_hedging:
            return False

        # Don't flag conversational / trivial queries — they legitimately get short answers.
        if salience is not None:
            if salience.domain == "conversational" or salience.weight < 0.35:
                return False

        # Only fire when the query itself was specific (not a one-liner greeting).
        return len(user_message.strip()) > 30


    async def _llm_review(
        self,
        draft: DraftResult,
        retrieval: RetrievalResult,
        flags: list[str],
        instance_id: str,
        conversation_id: str,
        user_message: str,
    ) -> CriticVerdict:
        """Run LLM-tier review: send draft + flags + knowledge to LLM."""
        # Build knowledge context
        knowledge_text = ""
        for chunk in retrieval.knowledge_chunks[:10]:
            content = chunk.get("content", "").strip()
            if content:
                knowledge_text += f"- {content}\n"

        memory_text = ""
        for chunk in retrieval.memory_chunks[:5]:
            content = chunk.get("content", "").strip()
            if content:
                memory_text += f"- {content}\n"

        review_message = (
            f"**Original user query**: {user_message[:500]}\n\n"
            f"**Draft response** (flagged: {', '.join(flags)}):\n{draft.text[:2000]}\n\n"
            f"**Knowledge context**:\n{knowledge_text[:1000]}\n"
            f"**Memory context**:\n{memory_text[:500]}"
        )

        messages = [
            {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
            {"role": "user", "content": review_message},
        ]

        try:
            result = await route_chat(
                task="cognition",
                instance_id=instance_id,
                conversation_id=f"critic-{conversation_id}",
                messages=messages,
                temperature=0.0,
                response_format={"type": "json_object"},
            )

            content = result.get("content") or "{}"
            # Strip any markdown fences
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[-1]
                if content.endswith("```"):
                    content = content[:-3].strip()

            critic_json = json.loads(content)
            verdict = critic_json.get("verdict", "pass_with_flag")
            rewritten = critic_json.get("rewritten_text", "")
            veto_reason = critic_json.get("veto_reason", "")

            logger.info(
                "LLM critic: conv=%s verdict=%s flags=%s rewritten=%d veto=%s",
                conversation_id[:8], verdict, flags, len(rewritten), veto_reason[:80],
            )

            return CriticVerdict(
                verdict=verdict,
                flags=flags,
                rewritten_text=rewritten,
                veto_reason=veto_reason,
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("LLM critic JSON parse failed: %s — falling back to rules-only", e)
            return _rules_only_verdict(flags)
        except Exception as e:
            logger.warning("LLM critic call failed: %s — falling back to rules-only", e)
            return _rules_only_verdict(flags)


def _rules_only_verdict(flags: list[str]) -> CriticVerdict:
    """Fallback rules-only verdict when LLM critic is disabled or fails."""
    # If ungrounded_claim is the only flag, return pass_with_flag (not a hard veto)
    if flags == ["ungrounded_claim"]:
        return CriticVerdict(verdict="pass_with_flag", flags=flags)

    # dry_run_preview only → pass with flag
    if flags == ["dry_run_preview"]:
        return CriticVerdict(verdict="pass_with_flag", flags=flags)

    # Other flags → pass_with_flag
    return CriticVerdict(verdict="pass_with_flag", flags=flags)
