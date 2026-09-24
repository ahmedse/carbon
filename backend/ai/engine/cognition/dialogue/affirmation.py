"""Canonical short-affirmation detection (English + Arabic).

One source of truth for "the user just said yes". The deixis gate, the
pending-action store and the consent-resume path all consult this module so a
bare affirmative can never be re-read as a fresh — or off-limits — request.

Arabic is normalized before matching (tashkeel stripped, alef/ya/teh-marbuta
unified), so ``ايوة`` and ``ايوه`` are the same token. The teh-marbuta spelling
is what users actually type, and missing it made Nibras hard-refuse a leave
confirmation with the out-of-scope copy.
"""
from __future__ import annotations

from ai.engine.cognition.dialogue.affirmation_helpers import (
    strip_edge_punct,
    strip_tashkeel,
    tokenize,
)
from ai.engine.cognition.dialogue.affirmation_i18n import (
    AFFIRM_PHRASES,
    AFFIRM_WORDS,
    ARABIC_FOLD,
)

#: A confirmation is a SHORT utterance. A long message that happens to contain
#: "yes" is a fresh query and must flow through the normal pipeline.
MAX_AFFIRMATION_WORDS = 4

def normalize(text: str) -> str:
    """Lowercase, strip edge punctuation, and fold Arabic orthography."""
    s = (text or "").strip()
    if not s:
        return ""
    s = strip_tashkeel(s)
    s = s.translate(ARABIC_FOLD)
    s = strip_edge_punct(s)
    s = " ".join(s.split())
    return s.casefold()


def is_affirmation(text: str) -> bool:
    """True when ``text`` is a short, unambiguous yes.

    Rejects negations, questions, and anything longer than
    ``MAX_AFFIRMATION_WORDS`` words.
    """
    s = normalize(text)
    if not s or "?" in s or "؟" in s:
        return False
    words = tokenize(s)
    if not words or len(words) > MAX_AFFIRMATION_WORDS:
        return False
    if s in AFFIRM_PHRASES or " ".join(words) in AFFIRM_PHRASES:
        return True
    # Every word must itself be affirmative ("yes ok", "نعم اكمل"). A single
    # non-affirmative word ("yes but", "no") disqualifies the whole message.
    return all(w in AFFIRM_WORDS for w in words)


def starts_with_affirmation(text: str) -> bool:
    """True when ``text`` opens with a yes ("yes, the annual one").

    Looser than :func:`is_affirmation` — for gates that only need to know the
    user is agreeing with the previous turn, not that the whole message is a
    bare yes.
    """
    s = normalize(text)
    if not s:
        return False
    if is_affirmation(s):
        return True
    words = tokenize(s)
    return bool(words) and words[0] in AFFIRM_WORDS
