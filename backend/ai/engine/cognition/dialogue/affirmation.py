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

import re

#: A confirmation is a SHORT utterance. A long message that happens to contain
#: "yes" is a fresh query and must flow through the normal pipeline.
MAX_AFFIRMATION_WORDS = 4

_TASHKEEL = re.compile(r"[\u0610-\u061A\u064B-\u0652\u0640\u0670\u06D6-\u06ED]")
_TOKEN = re.compile(r"[^\s,;.!?،؛…\"'«»]+")
_EDGE_PUNCT = re.compile(r"^[\s.!?,،؛…\"'«»]+|[\s.!?,،؛…\"'«»]+$")
_WHITESPACE = re.compile(r"\s+")

_ARABIC_FOLD = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ة": "ه",
    "ى": "ي", "ئ": "ي",
    "ؤ": "و",
})

#: Single-token affirmatives (already normalized — no hamza, no teh-marbuta).
_AFFIRM_WORDS: frozenset[str] = frozenset({
    # English
    "yes", "yeah", "yep", "yup", "ok", "okay", "sure", "correct", "right",
    "confirm", "confirmed", "confirming", "approve", "approved", "proceed",
    "continue", "go", "affirmative", "absolutely", "definitely", "please",
    "agreed", "agree",
    # Arabic ("ايه" is deliberately absent — in Egyptian it means "what?")
    "نعم", "ايوه", "ايوا", "اه", "اي", "اكيد", "تمام", "صح", "صحيح",
    "موافق", "موافقه", "ماشي", "اوك", "اوكي", "حسنا", "طيب", "يلا",
    "تفضل", "كمل", "اكمل", "نفذ", "قدمها", "ابدا",
    "اعملها", "ارسلها", "وافق", "اوافق", "بالتاكيد",
})

#: Multi-word phrases that are affirmations as a whole ("go ahead" is yes,
#: but "ahead" alone is not).
_AFFIRM_PHRASES: frozenset[str] = frozenset({
    "go ahead", "go for it", "do it", "do that", "do so", "submit it",
    "send it", "please do", "yes please", "sounds good", "that works",
    "of course", "why not", "make it so", "lets do it", "let's do it",
    "i confirm", "i approve", "i agree",
    "نعم من فضلك", "اه صح", "تمام كده", "ماشي تمام", "قدم الطلب",
    "ابعت الطلب", "نفذ الطلب", "اكمل الطلب", "موافق تماما",
})


def normalize(text: str) -> str:
    """Lowercase, strip edge punctuation, and fold Arabic orthography."""
    s = (text or "").strip()
    if not s:
        return ""
    s = _TASHKEEL.sub("", s)
    s = s.translate(_ARABIC_FOLD)
    s = _EDGE_PUNCT.sub("", s)
    s = _WHITESPACE.sub(" ", s)
    return s.casefold()


def is_affirmation(text: str) -> bool:
    """True when ``text`` is a short, unambiguous yes.

    Rejects negations, questions, and anything longer than
    ``MAX_AFFIRMATION_WORDS`` words.
    """
    s = normalize(text)
    if not s or "?" in s or "؟" in s:
        return False
    words = _TOKEN.findall(s)
    if not words or len(words) > MAX_AFFIRMATION_WORDS:
        return False
    if s in _AFFIRM_PHRASES or " ".join(words) in _AFFIRM_PHRASES:
        return True
    # Every word must itself be affirmative ("yes ok", "نعم اكمل"). A single
    # non-affirmative word ("yes but", "no") disqualifies the whole message.
    return all(w in _AFFIRM_WORDS for w in words)


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
    words = _TOKEN.findall(s)
    return bool(words) and words[0] in _AFFIRM_WORDS
