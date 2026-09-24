"""Arabic needles for ``process_brief`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations

BRIEFING_ASK_AR = ('اشرح', 'شرح', 'خطوة بخطوة', 'موافقة بشرية', 'عملية', 'دورة الحياة')
DELIVERABLE_ASK_AR = ('تقرير', 'تقارير', 'ملف', 'مستند', 'وورد', 'اكسل', 'إكسل', 'رسوم', 'جداول', 'جدول', 'صدّر', 'صدر', 'أنشئ', 'انشئ', 'ولّد', 'ولد', 'اكتب', 'تحليل', 'ملخص')


STEP_LABELS: dict[str, tuple[str, str]] = {
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


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)


def has_arabic_script(text: str) -> bool:
    return any(0x0600 <= ord(c) <= 0x06FF for c in (text or ""))
