"""Arabic affirmation tokens for ``affirmation.py`` (ADR-0049 L7). No ``compiled regex``."""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T

# Single-token affirmatives (already normalized — no hamza, no teh-marbuta).
AFFIRM_WORDS = T("dialogue/affirmation_i18n.py::AFFIRM_WORDS")

#: "Commit what you proposed" tokens. Only consulted when a typed
#: ``open_question`` is pending (``is_commit_affirmation``) — never as a
#: free-standing router signal, so "apply for " cannot match here.
COMMIT_WORDS = T("dialogue/affirmation_i18n.py::COMMIT_WORDS")

AFFIRM_PHRASES = T("dialogue/affirmation_i18n.py::AFFIRM_PHRASES")

ARABIC_FOLD = str.maketrans({
    "\u0623": "\u0627", "\u0625": "\u0627", "\u0622": "\u0627", "\u0671": "\u0627",
    "\u0629": "\u0647",
    "\u0649": "\u064a", "\u0626": "\u064a",
    "\u0624": "\u0648",
})
