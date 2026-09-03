"""Server-side PII detection + masking (Wave I5-B).

Mirrors the ``logger.js`` client-side redaction (D4) on the server.  Pure,
side-effect-free: imports nothing from Django, the ORM, or the engine so it can
be imported from engine vendored code (``auto_memory.py``) and the Django read
layers alike.

Redaction is replace-not-drop: matches are substituted with ``[REDACTED:{type}]``
and the full text is returned, so the surrounding context survives.  Civil-ID
and passport patterns use digit/alphanumeric boundaries so they can never match
inside a longer run (e.g. an emission figure or a longer identifier).
"""

import re

# Keys whose values are ALWAYS fully redacted when encountered in a nested
# structure (dict).  Normalized (lowercased, ``-``/space → ``_``) before matching.
PII_KEYS = frozenset({
    "civil_id", "civilid", "national_id", "nationalid", "passport",
    "passport_no", "passport_number", "email", "email_address", "phone",
    "phone_number", "mobile", "mobile_number", "nationality",
    "nationality_code", "date_of_birth", "dob", "full_name",
    "name_en_given", "name_en_family", "name_ar_given", "name_ar_family",
    "iban", "bank_account", "account_number", "token", "secret",
    "password", "api_key", "apikey", "authorization",
})

# (type, compiled_regex) — ordered; civil_id (12 digits) is matched BEFORE any
# generic numeric rule so it wins.  Every pattern uses boundaries so it cannot
# match inside a longer alphanumeric/numeric run.
_PATTERNS = [
    ("civil_id", re.compile(r"(?<!\d)\d{12}(?!\d)")),                      # Kuwait civil ID: exactly 12 digits
    ("passport", re.compile(r"(?<![A-Za-z0-9])[A-Za-z]\d{8}(?!\d)")),      # letter + 8 digits
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
]


class PIIGuard:
    """Pure, side-effect-free PII redaction helpers.

    ``redact`` masks free text by pattern; ``redact_dict`` masks structured
    payloads by key (whole-value redaction) and recurses into nested values,
    never mutating the input.
    """

    @classmethod
    def redact(cls, text):
        """Replace each PII pattern in ``text`` with ``[REDACTED:{type}]``.

        Non-``str`` inputs (including ``None``) pass through unchanged.
        Idempotent: the ``[REDACTED:...]`` markers contain no digits or ``@``,
        so a second pass matches nothing.
        """
        if not isinstance(text, str):
            return text
        for pii_type, pattern in _PATTERNS:
            text = pattern.sub("[REDACTED:" + pii_type + "]", text)
        return text

    @classmethod
    def redact_dict(cls, obj):
        """Recursively mask ``obj`` without mutating it.

        * ``str`` → ``redact``
        * ``dict`` → new dict; each key is normalized (lowercased, ``-``/space
          → ``_``) and any normalized key in ``PII_KEYS`` gets its value fully
          replaced by ``[REDACTED:{key}]`` (no recursion into the value); other
          keys recurse.
        * ``list``/``tuple`` → element-wise recursion (tuple type preserved).
        * ``None``/``bool``/``int``/``float``/anything else → returned as-is.
        """
        if isinstance(obj, str):
            return cls.redact(obj)
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                normalized = str(key).strip().lower().replace("-", "_").replace(" ", "_")
                if normalized in PII_KEYS:
                    result[key] = "[REDACTED:" + normalized + "]"
                else:
                    result[key] = cls.redact_dict(value)
            return result
        if isinstance(obj, list):
            return [cls.redact_dict(item) for item in obj]
        if isinstance(obj, tuple):
            return tuple(cls.redact_dict(item) for item in obj)
        return obj
