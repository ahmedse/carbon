"""Pre-S3 anaphora resolver — substitutes targeted pronouns with the active
working memory entity before the message reaches the LLM (GAP-3).

Also restores a prior focus when the user refers back to a previously
focused named entity ("Back to Abrar", "tell me about Abrar again"),
rewriting the message to include a stable id (e.g. employee_no) when known.
"""
from __future__ import annotations

import re

from ai.engine.memory.working import WorkingFocus, WorkingMemory

# Patterns where "it" acts as the OBJECT of an action verb
_ACTION_IT = re.compile(
    r"""
    (
        \b(?:validate|profile|analyze|analyse|review|check|examine|inspect|
            import|export|clean|process|fix|update|delete|run|query|deploy|
            test|open|close|save|load|verify|audit|sample|describe|
            summarize|summarise|rebuild|refresh|reindex|publish|archive)
        \s+
    )
    it
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# "should I [verb] it"
_SHOULD_IT = re.compile(
    r"(\bshould\s+I\s+\w+\s+)it\b",
    re.IGNORECASE,
)

# "it first/now/next/instead/before/after/as well"
_IT_ADVERB = re.compile(
    r"\bit\s+(first|now|next|instead|before|after|as\s+well)\b",
    re.IGNORECASE,
)


# "it" as subject in a question about a property: "how many X does/should/can/will it [verb]?"
_SUBJECT_IT_QUESTION = re.compile(
    r"(\bhow\s+(?:many|much|long|often|soon)\b.*?\b)it\b",
    re.IGNORECASE,
)

# Explicit restore: "back to Abrar", "back to employee 1021"
_BACK_TO = re.compile(
    r"\bback\s+to\s+(?:the\s+)?(.+?)(?:\s*[.,!?;:]|$)",
    re.IGNORECASE,
)

# Soft restore cues that mention a prior name again
_AGAIN_CUES = re.compile(
    r"\b(?:again|once\s+more|as\s+before|earlier|previously)\b",
    re.IGNORECASE,
)


def _focus_label(focus: WorkingFocus) -> str:
    """Surface label for substitution / rewrite."""
    if focus.entity_id:
        return f"{focus.entity} (employee_no {focus.entity_id})"
    return focus.entity


def _rewrite_with_stable_id(message: str, mention: str, focus: WorkingFocus) -> str:
    """Ensure the restored entity's stable id appears in the user message."""
    if not focus.entity_id:
        return message
    eid = focus.entity_id
    if re.search(rf"\b{re.escape(eid)}\b", message):
        return message
    # Prefer replacing the mention span with "Name (employee_no N)"
    label = _focus_label(focus)
    pattern = re.compile(re.escape(mention), re.IGNORECASE)
    if pattern.search(message):
        return pattern.sub(label, message, count=1)
    return f"{message.rstrip()} — {label}"


class AnaphoraResolver:
    """Replaces targeted deictic pronouns with the active working memory entity.

    Substitutes "it" in:
    - object-position after an action verb ("validate it", "profile it")
    - modal + verb forms ("should I check it")
    - adverb-following ("it first", "it next")
    - subject-position property questions ("how many rows should it have?")

    Restores a prior stacked focus when the user says "back to X" or
    re-mentions a previously focused name (optionally with "again").

    Does NOT replace subject-position "it" in statements ("It is a good idea").
    """

    def __init__(self, working_memory: WorkingMemory) -> None:
        self._wm = working_memory

    def resolve(self, conversation_id: str, user_message: str) -> str:
        """Return user_message with focus restore + pronoun → entity applied."""
        msg = self._restore_prior_focus(conversation_id, user_message)

        focus = self._wm.get_focus(conversation_id)
        if not focus:
            return msg

        entity = focus.entity
        resolved = _ACTION_IT.sub(rf"\g<1>{entity}", msg)
        resolved = _SHOULD_IT.sub(rf"\g<1>{entity}", resolved)
        resolved = _IT_ADVERB.sub(rf"{entity} \1", resolved)
        resolved = _SUBJECT_IT_QUESTION.sub(rf"\g<1>{entity}", resolved)
        return resolved

    def _restore_prior_focus(self, conversation_id: str, user_message: str) -> str:
        """Re-activate a prior focus when the user names it; rewrite with id."""
        stack = self._wm.get_focus_stack(conversation_id)
        if not stack:
            return user_message

        mention: str | None = None
        matched: WorkingFocus | None = None

        back = _BACK_TO.search(user_message)
        if back:
            mention = back.group(1).strip()
            matched = self._wm.find_prior_focus(conversation_id, mention)

        if matched is None and stack:
            # Scan non-current (and current) focuses for a name mentioned in-message.
            # Prefer longer alias hits so "Abrar Alam" beats a short false positive.
            candidates: list[tuple[int, WorkingFocus, str]] = []
            current = stack[0] if stack else None
            for focus in stack:
                for alias in self._searchable_aliases(focus):
                    if len(alias) < 3:
                        continue
                    if not re.search(rf"\b{re.escape(alias)}\b", user_message, re.I):
                        continue
                    # Skip if this is already the active focus and there is no
                    # explicit restore / again cue (avoid noisy rewrites).
                    if (
                        current is not None
                        and focus is current
                        and not back
                        and not _AGAIN_CUES.search(user_message)
                    ):
                        continue
                    candidates.append((len(alias), focus, alias))
            if candidates:
                candidates.sort(key=lambda t: t[0], reverse=True)
                _, matched, mention = candidates[0]

        if matched is None or mention is None:
            return user_message

        # Re-push to head of stack (preserves entity_id / aliases).
        self._wm.set_focus(
            conversation_id,
            matched.entity,
            matched.entity_type,
            entity_id=matched.entity_id,
            aliases=list(matched.aliases or []),
        )
        return _rewrite_with_stable_id(user_message, mention, matched)

    @staticmethod
    def _searchable_aliases(focus: WorkingFocus) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for raw in [focus.entity, *(focus.aliases or [])]:
            a = (raw or "").strip()
            if not a:
                continue
            key = a.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(a)
            # Also index first token of multi-word names ("Abrar").
            parts = a.split()
            if len(parts) > 1 and len(parts[0]) >= 3:
                tok = parts[0]
                if tok.lower() not in seen:
                    seen.add(tok.lower())
                    out.append(tok)
        return out
