"""Governed-process briefing — Chat concept answers, never navigation.

When the operator asks about a Nibras process id / lifecycle (EN or AR),
Pulse must explain ordered steps + human gates. That is a *concept* brief,
not a navigate short-circuit to People & Payroll.

Deterministic (stdlib + optional Django ORM / pack YAML). No LLM.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Canonical Nibras process ids (domain_packs/nibras/processes).
KNOWN_PROCESS_IDS: tuple[str, ...] = (
    "leave.request.lifecycle",
    "loan.request.lifecycle",
    "payroll.run.lifecycle",
    "gosi_wps.sif.lifecycle",
    "employee.onboarding.lifecycle",
    "attendance.permission.lifecycle",
)

# Explicit process id token (backticks optional).
_PROCESS_ID_RE = re.compile(
    r"(?i)\b("
    + "|".join(re.escape(p) for p in KNOWN_PROCESS_IDS)
    + r")\b"
)

# Explain / list-steps asks about a governed process or lifecycle (EN + AR).
_BRIEFING_ASK_RE = re.compile(
    r"(?is)("
    r"\b(explain|describe|walk\s*me\s*through|how\s+does|what\s+(is|are)\s+the\s+steps|"
    r"list\s+(every\s+)?step|end[- ]to[- ]end|human\s+approval|human[- ]only|"
    r"governed\s+process|process\s+lifecycle|lifecycle)\b"
    r"|اشرح|شرح|خطوة\s*بخطوة|موافقة\s*بشرية|عملية|دورة\s*الحياة|lifecycle"
    r")",
)

_AR_SCRIPT_RE = re.compile(r"[\u0600-\u06FF]")

_PACK_DIR = (
    Path(__file__).resolve().parents[5] / "domain_packs" / "nibras" / "processes"
)

# Short human labels for step ids (EN / AR).
_STEP_LABELS: dict[str, tuple[str, str]] = {
    "submit": ("Submit", "تقديم"),
    "review": ("Review (human approval)", "مراجعة (موافقة بشرية)"),
    "record": ("Record", "تسجيل"),
    "verify": ("Verify", "تحقق"),
    "compute": ("Compute", "احتساب"),
    "validate": ("Validate", "تدقيق"),
    "commit": ("Commit", "اعتماد / ترحيل"),
    "generate": ("Generate", "توليد"),
    "activate": ("Activate", "تفعيل"),
    "approve": ("Approve", "موافقة"),
}


# Mentions of place nouns inside a *deliverable* ask (report / Word / tables)
# must NOT short-circuit to open-app propose. "تقرير عن المرتبات … word file"
# mentions payroll but wants a document, not /people.
_DELIVERABLE_ASK_RE = re.compile(
    r"(?is)("
    r"\b(report|reports|document|documents|word|docx|xlsx|excel|pdf|csv|"
    r"export|generate|produce|create|draft|write|summar(y|ise|ize)|"
    r"breakdown|comprehensive|analysis|analyse|analyze)\b"
    r"|تقرير|تقارير|ملف|مستند|وورد|اكسل|إكسل|رسوم|جداول|جدول|صدّر|صدر|"
    r"أنشئ|انشئ|ولّد|ولد|اكتب|تحليل|ملخص"
    r")",
)


def is_deliverable_request(text: str) -> bool:
    """True when the utterance asks for a produced artifact, not navigation."""
    raw = (text or "").strip()
    if not raw:
        return False
    return bool(_DELIVERABLE_ASK_RE.search(raw))


def is_process_briefing(text: str) -> bool:
    """True when the utterance asks to *explain* a governed process/lifecycle.

    Mentions of a process id alone count (sim prompts always embed the id).
    Bare "open leave" / "take me to payroll" do NOT match.
    """
    raw = (text or "").strip()
    if not raw:
        return False
    if _PROCESS_ID_RE.search(raw):
        return True
    # Lifecycle + explain verbs without an exact id (still concept, not nav).
    if _BRIEFING_ASK_RE.search(raw) and re.search(
        r"(?i)\b(leave|loan|payroll|gosi|wps|sif|onboarding|onboard|"
        r"إجازة|اجازة|قرض|رواتب|تأمينات|توظيف|تعيين)\b",
        raw,
    ):
        return True
    return False


def extract_process_id(text: str) -> str | None:
    """Return the first known process id mentioned, or a best-effort alias."""
    raw = text or ""
    m = _PROCESS_ID_RE.search(raw)
    if m:
        return m.group(1).lower()
    low = raw.casefold()
    aliases = (
        ("leave.request.lifecycle", ("leave.request", "leave lifecycle", "leave process", "إجازة", "اجازة")),
        ("loan.request.lifecycle", ("loan.request", "loan lifecycle", "loan process", "قرض")),
        ("payroll.run.lifecycle", ("payroll.run", "payroll lifecycle", "payroll process", "رواتب")),
        ("gosi_wps.sif.lifecycle", ("gosi", "wps", "sif", "تأمينات")),
        ("employee.onboarding.lifecycle", ("onboarding", "onboard", "توظيف", "تعيين")),
        ("attendance.permission.lifecycle", (
            "attendance.permission", "attendance permission", "attendance lifecycle",
            "short hours", "إذن حضور", "اذن حضور", "صلاحية حضور",
        )),
    )
    if not _BRIEFING_ASK_RE.search(raw):
        return None
    for pid, needles in aliases:
        if any(n.casefold() in low or n in raw for n in needles):
            return pid
    return None


def detect_brief_lang(text: str) -> str:
    return "ar" if _AR_SCRIPT_RE.search(text or "") else "en"


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
    path = _PACK_DIR / f"{process_id}.yaml"
    if not path.is_file():
        return None
    try:
        import yaml

        with path.open(encoding="utf-8") as fh:
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
        lines.append(f"عملية نبراس المحكومة `{process_id}` تسير بالترتيب التالي:")
    else:
        lines.append(
            f"The Nibras governed process `{process_id}` runs in this order:"
        )

    for i, step in enumerate(steps, start=1):
        sid = str(step.get("id") or f"step_{i}")
        en_lbl, ar_lbl = _STEP_LABELS.get(sid, (sid, sid))
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
            "هذا شرح مفاهيمي للعملية — وليس طلبًا لفتح شاشة People & Payroll."
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
            "People & Payroll."
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
