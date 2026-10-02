"""Draft medicine-L5 scorer — "Grounded lecture" (default-OFF, draft).

This is the *medicine* L5 (C6 + 100-question curriculum bar + R11 + R12), not
``ai.eval.intelligence_ladder.score_l5``. It computes the medicine-L5 status
from two DRAFT golds:

* ``gold/l5-curriculum.draft.yaml`` — 100 body-only curriculum items per listed
  shortname, each citing a real passage and a verbatim span;
* ``gold/l5-r11.draft.yaml`` — four frozen draft-labelling cases.

It **never** flips the frozen ``gold/l5.yaml`` ``status`` and is not imported by
the Ask turn path. ``student_cohorts`` stays empty; R12 needs two real students.
The frozen status in ``gold/l5.yaml`` remains ``not_passable``.

Spec: ``docs/pulse/aast-med/L5-PASSABILITY.md``.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PACK = REPO_ROOT / "domain_packs" / "aast-med"
CURRICULUM_GOLD = PACK / "gold" / "l5-curriculum.draft.yaml"
R11_GOLD = PACK / "gold" / "l5-r11.draft.yaml"

SAMPLE_SIZE = 100
MIN_PASSAGE_CITE = 95
MAX_EXTRA_FACT = 2
R11_REQUIRED_N = 4
R12_REQUIRED_N = 2

_STOP = frozenset(
    """the a an and or of to in for on with by is are was were be been being this
that these those it its as at from into not no if then than there their they them we you
your our can may must should would could will shall does do did has have had which who whom
whose what when where why how all any both each few more most other some such only own same
so too very s t don now also using used use one two three first second between within without
across after before during under over about more less least study guide lecture session week
course page book unit chapter""".split()
)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+|•")
_TOKEN = re.compile(r"[A-Za-z](?:[A-Za-z\-']{3,})[A-Za-z]")
_MIN_SPAN = 40

__all__ = [
    "CURRICULUM_GOLD",
    "R11_GOLD",
    "L5DraftStatus",
    "ShortnameScore",
    "derive_curriculum_items",
    "load_curriculum_gold",
    "load_r11_gold",
    "medicine_l5_status",
    "score_curriculum",
    "score_r11",
    "verify_cites",
]


# ── bank helpers (imported lazily; the module stays light) ───────────────────


def _bank(shortname: str) -> dict[str, dict]:
    from ai.moodle_bank import load_c3, load_c4_drive, load_c4_files, load_c5_youtube, load_extra

    return {
        **load_c3(shortname),
        **load_c4_files(shortname),
        **load_c4_drive(shortname),
        **load_c5_youtube(shortname),
        **load_extra(shortname),
    }


def _listed_shortnames() -> list[str]:
    doc = yaml.safe_load((PACK / "courses.yaml").read_text(encoding="utf-8")) or {}
    return [str(row["shortname"]) for row in doc.get("enabled_courses") or []]


def _title_tokens(shortname: str) -> set[str]:
    toks: set[str] = set()
    path = PACK / "bank" / "course-meat-13" / f"{shortname}.jsonl"
    if not path.is_file():
        return toks
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("{"):
            continue
        row = json.loads(line)
        for field in ("name", "section"):
            for token in _TOKEN.findall(str(row.get(field) or "")):
                toks.add(token.lower())
    return toks


# ── derivation (the exact authoring rule behind the frozen draft gold) ───────


def derive_curriculum_items(shortname: str, cap: int = SAMPLE_SIZE) -> list[dict]:
    """Deterministically derive draft curriculum items from the real bank.

    Each item cites the passage it came from and a verbatim span that contains
    a body-only term (present in the passage body, absent from every
    section/activity title). No question is emitted whose span is not a
    contiguous substring of the cited passage.
    """
    bank = _bank(shortname)
    titles = _title_tokens(shortname)
    items: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for pid in sorted(bank):
        row = bank[pid]
        text = str(row.get("text") or "")
        for span in _SENT_SPLIT.split(text):
            span = span.strip()
            if len(span) < _MIN_SPAN or not re.search(r"[A-Za-z]", span):
                continue
            terms: list[str] = []
            low: set[str] = set()
            for token in _TOKEN.findall(span):
                lt = token.lower()
                if lt in titles or lt in _STOP or lt in low:
                    continue
                low.add(lt)
                terms.append(token)
            terms.sort(key=lambda t: (-len(t), t.lower()))
            for term in terms:
                key = (pid, term.lower())
                if key in seen:
                    continue
                seen.add(key)
                items.append(
                    {
                        "id": f"{shortname}-{len(items) + 1:03d}",
                        "passage_id": pid,
                        "sectionnum": int(row.get("sectionnum") or -1),
                        "term": term,
                        "question": f"What does this lecture say about {term}?",
                        "quote": span,
                    }
                )
                if len(items) >= cap:
                    return items
    return items


# ── gold loading ─────────────────────────────────────────────────────────────


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return doc if isinstance(doc, dict) else {}


def load_curriculum_gold() -> dict[str, Any]:
    return _load_yaml(CURRICULUM_GOLD)


def load_r11_gold() -> dict[str, Any]:
    return _load_yaml(R11_GOLD)


# ── scoring ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ShortnameScore:
    shortname: str
    items: int
    cited: int
    extra_facts: int
    sample_size: int = SAMPLE_SIZE
    min_passage_cite: int = MIN_PASSAGE_CITE
    max_extra_fact: int = MAX_EXTRA_FACT

    @property
    def sample_met(self) -> bool:
        return self.items >= self.sample_size

    @property
    def cite_met(self) -> bool:
        return self.cited >= self.min_passage_cite

    @property
    def at_bar(self) -> bool:
        return self.sample_met and self.cite_met and self.extra_facts <= self.max_extra_fact

    def line(self) -> str:
        return f"{self.shortname}: {self.cited}/{self.items} cited, {self.extra_facts} extra facts"


@dataclass(frozen=True)
class L5DraftStatus:
    status: str  # "passable" | "not_passable"
    per_shortname: tuple[ShortnameScore, ...]
    r11_frozen_n: int
    r11_required_n: int
    r12_frozen_n: int
    r12_required_n: int
    student_cohorts_non_empty: bool
    consent_records_present: bool
    audit_present: bool
    blocked_by: tuple[str, ...]

    @property
    def passable(self) -> bool:
        return self.status == "passable"


def verify_cites(gold: dict[str, Any] | None = None) -> list[str]:
    """Every gold quote must be a verbatim substring of its cited passage.

    Returns a list of typed violations (empty means the gold is honest).
    """
    doc = gold if isinstance(gold, dict) else load_curriculum_gold()
    out: list[str] = []
    for shortname, items in (doc.get("short") or {}).items():
        bank = _bank(shortname)
        for item in items or []:
            pid = str(item.get("passage_id") or "")
            quote = str(item.get("quote") or "")
            term = str(item.get("term") or "")
            row = bank.get(pid)
            if row is None:
                out.append(f"{shortname}:{item.get('id')}:cited_passage_not_in_bank:{pid}")
                continue
            if not quote or quote not in str(row.get("text") or ""):
                out.append(f"{shortname}:{item.get('id')}:quote_not_in_passage:{pid}")
                continue
            if term and term.casefold() not in quote.casefold():
                out.append(f"{shortname}:{item.get('id')}:term_not_in_quote:{term}")
    return out


def _page(shortname: str) -> dict:
    """Signed staff page snapshot for one listed course (offline)."""
    from ai.moodle_host import page_context_from_snapshot, snapshot_from_page_context

    courses = yaml.safe_load((PACK / "courses.yaml").read_text(encoding="utf-8")) or {}
    info = {str(r["shortname"]): r for r in courses.get("enabled_courses") or []}[shortname]
    seen: dict[int, str] = {}
    path = PACK / "bank" / "course-meat-13" / f"{shortname}.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("{"):
            continue
        row = json.loads(line)
        number = row.get("sectionnum")
        if number is not None:
            seen.setdefault(int(number), str(row.get("section") or ""))
    snapshot = {
        "audience": "staff",
        "enrolled": True,
        "course": {
            "id": 1,
            "shortname": shortname,
            "fullname": info["fullname"],
            "visible_to_user": True,
        },
        "sections": [{"number": k, "name": v, "visible": True} for k, v in sorted(seen.items())],
    }
    return snapshot_from_page_context(page_context_from_snapshot({"audience": "staff"}, snapshot))


def _door_cites(shortname: str, items: list[dict], bank: dict[str, dict]) -> tuple[int, int]:
    """(cited, extra_facts) by running the real Ask door offline.

    A door cite counts only when the reply names a real passage id from the
    course and the body-only term appears in the reply. ``extra_facts`` counts
    items whose quote is not a substring of the cited passage (must be 0).
    """
    from ai.moodle_host import door_answer

    page = _page(shortname)
    cited = 0
    extra = 0
    for item in items:
        quote = str(item.get("quote") or "")
        pid = str(item.get("passage_id") or "")
        row = bank.get(pid)
        if row is None or quote not in str(row.get("text") or ""):
            extra += 1
            continue
        reply = door_answer(f"what is {item['term']}", page)
        if not reply or "not in this course" in reply or "not in this lecture" in reply:
            continue
        lines = reply.splitlines()
        if len(lines) > 1 and lines[1] in bank:
            cited += 1
    return cited, extra


def score_curriculum(*, run_door: bool = False, gold: dict[str, Any] | None = None) -> tuple[ShortnameScore, ...]:
    """Per-shortname curriculum score. ``cited`` is door-verified when run_door."""
    doc = gold if isinstance(gold, dict) else load_curriculum_gold()
    scores: list[ShortnameScore] = []
    for shortname in _listed_shortnames():
        items = list((doc.get("short") or {}).get(shortname) or [])
        bank = _bank(shortname)
        if run_door:
            cited, extra = _door_cites(shortname, items, bank)
        else:
            extra = sum(
                1
                for item in items
                if str(item.get("passage_id") or "") not in bank
                or str(item.get("quote") or "") not in str(bank[str(item.get("passage_id") or "")].get("text") or "")
            )
            cited = len(items) - extra
        scores.append(ShortnameScore(shortname=str(shortname), items=len(items), cited=cited, extra_facts=extra))
    return tuple(scores)


def score_r11(gold: dict[str, Any] | None = None) -> dict[str, Any]:
    doc = gold if isinstance(gold, dict) else load_r11_gold()
    return {
        "frozen_n": int(doc.get("frozen_n") or 0),
        "required_n": int(doc.get("required_n") or R11_REQUIRED_N),
        "cases": tuple(doc.get("cases") or ()),
    }


def medicine_l5_status(
    *,
    run_door: bool = False,
    r11_frozen_n: int | None = None,
    r12_frozen_n: int = 0,
    r12_required_n: int = R12_REQUIRED_N,
    student_cohorts_non_empty: bool = False,
    consent_records_present: bool = False,
    audit_present: bool = False,
) -> L5DraftStatus:
    """Compute the draft medicine-L5 status from the golds + real-world inputs.

    The status is ``passable`` only when every code gate (curriculum per
    shortname, R11) and every real-world gate (R12 two real students, a
    non-empty student cohort, consent and audit records) holds. Nothing is
    hardcoded and no cohort is invented.
    """
    scores = score_curriculum(run_door=run_door)
    r11 = score_r11()
    r11_n = r11["frozen_n"] if r11_frozen_n is None else int(r11_frozen_n)

    gaps: list[str] = []
    for score in scores:
        if not score.at_bar:
            gaps.append(
                f"curriculum_below_bar:{score.shortname}({score.cited}/{score.items})"
            )
    if r11_n < R11_REQUIRED_N:
        gaps.append(f"r11_draft_cases_missing({r11_n}/{R11_REQUIRED_N})")
    if int(r12_frozen_n) < int(r12_required_n):
        gaps.append(f"r12_two_real_students_missing({int(r12_frozen_n)}/{int(r12_required_n)})")
    if not student_cohorts_non_empty:
        gaps.append("student_cohorts_empty")
    if not consent_records_present:
        gaps.append("consent_records_missing")
    if not audit_present:
        gaps.append("audit_records_missing")

    return L5DraftStatus(
        status="passable" if not gaps else "not_passable",
        per_shortname=scores,
        r11_frozen_n=r11_n,
        r11_required_n=R11_REQUIRED_N,
        r12_frozen_n=int(r12_frozen_n),
        r12_required_n=int(r12_required_n),
        student_cohorts_non_empty=bool(student_cohorts_non_empty),
        consent_records_present=bool(consent_records_present),
        audit_present=bool(audit_present),
        blocked_by=tuple(gaps),
    )
