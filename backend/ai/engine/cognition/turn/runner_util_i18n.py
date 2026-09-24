"""Arabic needles for ``runner_util`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T


ESS_TOPIC_AR = T("turn/runner_util_i18n.py::ESS_TOPIC_AR")
FIRST_PERSON_AR = T("turn/runner_util_i18n.py::FIRST_PERSON_AR")
SCOPE_BYPASS_AR = T("turn/runner_util_i18n.py::SCOPE_BYPASS_AR")


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
