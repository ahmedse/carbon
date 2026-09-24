"""Arabic affirmation tokens for ``affirmation.py`` (ADR-0049 L7). No ``compiled regex``."""
from __future__ import annotations

# Single-token affirmatives (already normalized — no hamza, no teh-marbuta).
AFFIRM_WORDS: frozenset[str] = frozenset({
    # English
    "yes", "yeah", "yep", "yup", "ok", "okay", "sure", "correct", "right",
    "confirm", "confirmed", "confirming", "approve", "approved", "proceed",
    "continue", "go", "affirmative", "absolutely", "definitely", "please",
    "agreed", "agree",
    # Arabic
    "نعم", "ايوه", "ايوا", "اه", "اي", "اكيد", "تمام", "صح", "صحيح",
    "موافق", "موافقه", "ماشي", "اوك", "اوكي", "حسنا", "طيب", "يلا",
    "تفضل", "كمل", "اكمل", "نفذ", "قدمها", "ابدا",
    "اعملها", "ارسلها", "وافق", "اوافق", "بالتاكيد",
})

#: "Commit what you proposed" tokens. Only consulted when a typed
#: ``open_question`` is pending (``is_commit_affirmation``) — never as a
#: free-standing router signal, so "apply for leave" cannot match here.
COMMIT_WORDS: frozenset[str] = frozenset({
    "apply", "applied", "accept", "accepted", "commit", "adopt",
    "اعتمد", "اعتمدها", "طبق", "طبقها", "اقبل", "موافقه",
})

AFFIRM_PHRASES: frozenset[str] = frozenset({
    "go ahead", "go for it", "do it", "do that", "do so", "submit it",
    "send it", "please do", "yes please", "sounds good", "that works",
    "of course", "why not", "make it so", "lets do it", "let's do it",
    "i confirm", "i approve", "i agree",
    "نعم من فضلك", "اه صح", "تمام كده", "ماشي تمام", "قدم الطلب",
    "ابعت الطلب", "نفذ الطلب", "اكمل الطلب", "موافق تماما",
})

ARABIC_FOLD = str.maketrans({
    "\u0623": "\u0627", "\u0625": "\u0627", "\u0622": "\u0627", "\u0671": "\u0627",
    "\u0629": "\u0647",
    "\u0649": "\u064a", "\u0626": "\u064a",
    "\u0624": "\u0648",
})
