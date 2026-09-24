from __future__ import annotations
from ai.engine.cognition.phrase_tables import T
from ai.engine.pack_vocab import V
V("t_governed_process_briefing_chat_concept_answers")


from pathlib import Path
from typing import Any

from ai.engine.text.word_match import contains_any_phrase, has_any_word

from ai.engine.cognition.turn.process_brief_i18n import (
    BRIEFING_ASK_AR,
    DELIVERABLE_ASK_AR,
    STEP_LABELS,
    any_needle,
    has_arabic_script,
)

def process_ids() -> tuple[str, ...]:
    """Process ids shipped by any pack, read from ``domain_packs/*/processes``."""
    root = Path(__file__).resolve().parents[5] / "domain_packs"
    if not root.is_dir():
        return ()
    return tuple(sorted(path.stem for path in root.glob("*/processes/*.yaml")))


_BRIEFING_WORDS = T("turn/process_brief.py::_BRIEFING_WORDS")
_BRIEFING_PHRASES = T("turn/process_brief.py::_BRIEFING_PHRASES")


def _find_process_id(text: str) -> str | None:
    cf = (text or "").casefold()
    for pid in process_ids():
        if pid.casefold() in cf:
            return pid
    return None


def _is_briefing_ask_en(text: str) -> bool:
    return has_any_word(text, _BRIEFING_WORDS) or contains_any_phrase(text, _BRIEFING_PHRASES)

# Mentions of place nouns inside a *deliverable* ask (report / Word / tables)
# must NOT short-circuit to open-app propose when the user wants a document.
_DELIVERABLE_WORDS = T("turn/process_brief.py::_DELIVERABLE_WORDS")


def is_deliverable_request(text: str) -> bool:
    """True when the utterance asks for a produced artifact, not navigation."""
    raw = (text or "").strip()
    if not raw:
        return False
    return bool(has_any_word(raw, _DELIVERABLE_WORDS) or any_needle(raw, DELIVERABLE_ASK_AR))


def is_process_briefing(text: str) -> bool:
    V("t_true_when_the_utterance_asks_to")
    raw = (text or "").strip()
    if not raw:
        return False
    if _find_process_id(raw):
        return True
    # Lifecycle + explain verbs without an exact id (still concept, not nav).
    if (_is_briefing_ask_en(raw) or any_needle(raw, BRIEFING_ASK_AR)) and (
        has_any_word(raw, (V("t_leave"), V("t_loan_2"), V("t_payroll"), V("t_gosi"), "wps", "sif", "onboarding", "onboard"))
        or any_needle(raw, (V("t_إجازة"), V("t_اجازة"), V("t_قرض"), V("t_رواتب"), "تأمينات", "توظيف", "تعيين"))
    ):
        return True
    return False


def extract_process_id(text: str) -> str | None:
    """Return the first known process id mentioned, or a best-effort alias."""
    raw = text or ""
    found = _find_process_id(raw)
    if found:
        return found
    low = raw.casefold()
    aliases = (
        (V("t_leave_request_lifecycle"), (V("t_leave_request"), V("t_leave_lifecycle"), V("t_leave_process"), V("t_إجازة"), V("t_اجازة"))),
        (V("t_loan_request_lifecycle"), (V("t_loan_request"), V("t_loan_lifecycle"), V("t_loan_process"), V("t_قرض"))),
        (V("t_payroll_run_lifecycle"), (V("t_payroll_run"), V("t_payroll_lifecycle"), V("t_payroll_process"), V("t_رواتب"))),
        ("gosi_wps.sif.lifecycle", (V("t_gosi"), "wps", "sif", "تأمينات")),
        (V("t_employee_onboarding_lifecycle"), ("onboarding", "onboard", "توظيف", "تعيين")),
        (V("t_attendance_permission_lifecycle"), (
            V("t_attendance_permission_2"), V("t_attendance_permission"), V("t_attendance_lifecycle"),
            "short hours", V("t_إذن_حضور"), V("t_اذن_حضور"), V("t_صلاحية_حضور"),
        )),
    )
    if not (_is_briefing_ask_en(raw) or any_needle(raw, BRIEFING_ASK_AR)):
        return None
    for pid, needles in aliases:
        if any(n.casefold() in low or n in raw for n in needles):
            return pid
    return None


def detect_brief_lang(text: str) -> str:
    return "ar" if has_arabic_script(text) else "en"


def _load_definition(process_id: str) -> dict[str, Any] | None:
    """Load process document from DB (active) else pack YAML."""
    try:
        from ai.models.process import ProcessDefinition, STATUS_ACTIVE

        obj = (
            ProcessDefinition.objects.filter(
                process_id=process_id, status=STATUS_ACTIVE,
            )
            .order_by("-created_at")
            .first()
        )
        if obj and isinstance(obj.definition, dict):
            return obj.definition
    except Exception:  # noqa: BLE001 — briefing must not depend on ORM health
        pass
    root = Path(__file__).resolve().parents[5] / "domain_packs"
    matches = sorted(root.glob(f"*/processes/{process_id}.yaml")) if root.is_dir() else []
    if not matches:
        return None
    try:
        import yaml

        with matches[0].open(encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        return doc if isinstance(doc, dict) else None
    except Exception:  # noqa: BLE001
        return None


def _step_is_human(step: dict[str, Any]) -> bool:
    autonomy = str(step.get("autonomy") or "").lower()
    kind = str(step.get("kind") or "").lower()
    return autonomy == "human_only" or kind == "human_task"


def format_process_briefing(process_id: str, *, lang: str = "en") -> str | None:
    """Render ordered steps + SoD/human_only callouts for *process_id*."""
    doc = _load_definition(process_id)
    if not doc:
        return None
    steps = [s for s in (doc.get("steps") or []) if isinstance(s, dict)]
    if not steps:
        return None
    objective = (doc.get("objective") or {}).get("predicate") or ""
    ar = lang == "ar"

    lines: list[str] = []
    if ar:
        lines.append(f"العملية المحكومة `{process_id}` تسير بالترتيب التالي:")
    else:
        lines.append(
            f"The governed process `{process_id}` runs in this order:"
        )

    for i, step in enumerate(steps, start=1):
        sid = str(step.get("id") or f"step_{i}")
        en_lbl, ar_lbl = STEP_LABELS.get(sid, (sid, sid))
        label = ar_lbl if ar else en_lbl
        human = _step_is_human(step)
        sod = step.get("separation_of_duties") or []
        if ar:
            gate = " — **موافقة بشرية فقط** (human_only)" if human else ""
            if sod:
                gate += f" · فصل واجبات: {', '.join(str(x) for x in sod)}"
            lines.append(f"{i}. **{sid}** — {label}{gate}")
        else:
            gate = " — **human_only** (human approval required)" if human else ""
            if sod:
                gate += f" · separation of duties: {', '.join(str(x) for x in sod)}"
            lines.append(f"{i}. **{sid}** — {label}{gate}")

    human_ids = [str(s.get("id")) for s in steps if _step_is_human(s)]
    if ar:
        if human_ids:
            lines.append(
                "الخطوات التي تحتاج موافقة بشرية: "
                + ", ".join(f"`{h}`" for h in human_ids)
                + "."
            )
        if objective:
            lines.append(f"الهدف (objective): `{objective}`.")
        lines.append(
            V("t_هذا_شرح_مفاهيمي_للعملية_وليس_طلب")
        )
    else:
        if human_ids:
            lines.append(
                "Steps that need human approval: "
                + ", ".join(f"`{h}`" for h in human_ids)
                + "."
            )
        if objective:
            lines.append(f"Objective predicate: `{objective}`.")
        lines.append(
            "This is a process briefing (concept), not a request to open "
            + V("t_people_payroll")
        )
    return "\n".join(lines)


def try_process_briefing(text: str) -> tuple[str, str] | None:
    """If *text* is a process briefing ask, return ``(process_id, reply)``.

    Returns ``None`` when not a briefing ask or the process cannot be loaded.
    """
    if not is_process_briefing(text):
        return None
    pid = extract_process_id(text)
    if not pid:
        return None
    lang = detect_brief_lang(text)
    reply = format_process_briefing(pid, lang=lang)
    if not reply:
        return None
    return pid, reply

