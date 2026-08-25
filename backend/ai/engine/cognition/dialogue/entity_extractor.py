"""Dialogue pre-processor: extracts user-named entities into WorkingMemory (GAP-2).

Domain-agnostic — works for any named thing (table, invoice, patient, dataset, etc.).
The extractor reads surface-form patterns, not domain-specific terminology.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ExtractedEntity:
    name: str
    entity_type: str   # structural type: "table", "column", "field", "dataset", "item", ...
    confidence: float = 1.0


# Ordered most-specific first. Each tuple is (pattern, type_group_or_literal).
# "matched_type" means group(2) holds the structural type word.
_TYPED_PATTERNS: list[tuple[str, str]] = [
    # "the {name} table/column/field/…"
    (
        r"\bthe\s+([A-Za-z][A-Za-z0-9 _\-]+?)\s+"
        r"(table|column|field|dataset|view|schema|pipeline|report|module|"
        r"metric|form|record|document|file|sheet)\b",
        "matched_type",
    ),
    # "validate/profile/analyze the {name} table/…" — imperative
    (
        r"\b(?:validate|profile|analyze|review|check|examine|inspect|import|"
        r"export|clean|process)\s+(?:the\s+)?"
        r"([A-Za-z][A-Za-z0-9 _\-]+?)\s+"
        r"(table|column|field|dataset|view|schema|pipeline|report|module|"
        r"metric|form|record|document|file|sheet)\b",
        "matched_type",
    ),
    # "I want to [verb] [the] {name} table/…" — intent sentences
    (
        r"\bI\s+(?:want|need|would\s+like)\s+to\s+\w+\s+(?:the\s+)?"
        r"([A-Za-z][A-Za-z0-9 _\-]+?)\s+"
        r"(table|column|field|dataset|view|schema|pipeline|report|module|"
        r"metric|form|record|document|file|sheet)\b",
        "matched_type",
    ),
    # "focus on {name}" or "focusing on {name}" — bare focus, no type word
    (
        r"\b(?:focus|focusing)\s+on\s+(?:the\s+)?"
        r"([A-Za-z][A-Za-z0-9 _\-]+?)"
        r"(?:\s+for\s+now|\s+next|\s+first|[.,]|$)",
        "item",
    ),
]

_COMPILED: list[tuple[re.Pattern, str]] = [
    (re.compile(pat, re.IGNORECASE), etype)
    for pat, etype in _TYPED_PATTERNS
]

_MIN_NAME_LEN = 2
_MAX_NAME_LEN = 80


class EntityExtractor:
    """Lightweight surface-form entity extractor. Zero LLM cost.

    Returns the most salient named entity from a user message, or None
    if no recognizable named entity is found.
    """

    def extract(self, user_message: str) -> ExtractedEntity | None:
        for pattern, etype in _COMPILED:
            m = pattern.search(user_message)
            if not m:
                continue
            name = m.group(1).strip()
            if len(name) < _MIN_NAME_LEN or len(name) > _MAX_NAME_LEN:
                continue
            resolved_type = (
                m.group(2).strip().lower() if etype == "matched_type" else etype
            )
            return ExtractedEntity(name=name, entity_type=resolved_type)
        return None
