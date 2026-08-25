"""Pre-S3 anaphora resolver — substitutes targeted pronouns with the active
working memory entity before the message reaches the LLM (GAP-3).

Domain-agnostic: the only domain knowledge is the entity string stored in
WorkingMemory, which was set by EntityExtractor.
"""
from __future__ import annotations

import re

from ai.engine.memory.working import WorkingMemory

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


class AnaphoraResolver:
    """Replaces targeted deictic pronouns with the active working memory entity.

    Substitutes "it" in:
    - object-position after an action verb ("validate it", "profile it")
    - modal + verb forms ("should I check it")
    - adverb-following ("it first", "it next")
    - subject-position property questions ("how many rows should it have?")

    Does NOT replace subject-position "it" in statements ("It is a good idea").
    """

    def __init__(self, working_memory: WorkingMemory) -> None:
        self._wm = working_memory

    def resolve(self, conversation_id: str, user_message: str) -> str:
        """Return user_message with pronoun → entity substitutions applied."""
        focus = self._wm.get_focus(conversation_id)
        if not focus:
            return user_message

        entity = focus.entity
        resolved = _ACTION_IT.sub(rf"\g<1>{entity}", user_message)
        resolved = _SHOULD_IT.sub(rf"\g<1>{entity}", resolved)
        resolved = _IT_ADVERB.sub(rf"{entity} \1", resolved)
        resolved = _SUBJECT_IT_QUESTION.sub(rf"\g<1>{entity}", resolved)
        return resolved
