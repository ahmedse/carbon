"""Notice registry for the aast-med rollout (default unpublished).

Two notices exist: a staff notice (K10, frozen R18 sentence) and a student
notice (K11, a separate decision per R16). Both default **unpublished**. The
registry is the single place a future canvas/report reads notice state from.

This module has no side effects on import. Construct a :class:`NoticeRegistry`
explicitly (tests do) to publish. Publishing requires the cohort idnumbers, the
shortnames that hold C6 gold, and the five R18 "does not" clauses.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

__all__ = [
    "Notice",
    "NoticeDraftError",
    "NoticeRegistry",
    "REQUIRED_DOES_NOT",
    "STAFF_NOTICE_TEXT",
    "STUDENT_NOTICE_TEXT",
]

NOTICE_KEYS = ("staff", "student")

#: R18 sentence, frozen. The one sentence that may be sent, and only after S3.
STAFF_NOTICE_TEXT = (
    "Pulse is on for staff in the named cohort, on the named course "
    "shortnames. It answers from the lecture you have open. It does not "
    "grade, enrol, or see another student. If the fact is not in that "
    "lecture, it says so."
)

#: Student notice. Spec-frozen wording; NOT publishable until K11 preconditions
#: hold (L5 passable, cohort non-empty, consent + RBAC + audit present).
STUDENT_NOTICE_TEXT = (
    "Pulse is available to students in the named student cohort, on the "
    "named course shortnames. It answers from the lecture you have open. "
    "It does not grade or enrol you. It never shows another student's "
    "answers or work. It does not give clinical doses or diagnose patients. "
    "If the fact is not in that lecture, it says so. You may withdraw "
    "consent at any time; withdrawing stops Pulse for you."
)

#: The five R18 clauses every notice must carry, as stable tokens.
REQUIRED_DOES_NOT = (
    "no_grade",
    "no_enrol",
    "no_other_student",
    "no_clinical_dose",
    "lecture_miss",
)

_DEFAULT_TEXT = {"staff": STAFF_NOTICE_TEXT, "student": STUDENT_NOTICE_TEXT}
_DEFAULT_AUDIENCE = {"staff": "staff", "student": "student"}


class NoticeDraftError(ValueError):
    """A notice publish was refused because a required field was missing."""


@dataclass(frozen=True)
class Notice:
    key: str
    audience: str
    text: str
    cohort_idnumbers: tuple[str, ...] = ()
    shortnames: tuple[str, ...] = ()
    does_not: tuple[str, ...] = ()
    published: bool = False
    published_at: str | None = None


def _default_notice(key: str) -> Notice:
    return Notice(
        key=key,
        audience=_DEFAULT_AUDIENCE[key],
        text=_DEFAULT_TEXT[key],
        published=False,
        published_at=None,
    )


@dataclass
class NoticeRegistry:
    """A staff notice and a student notice. Both unpublished until published."""

    staff: Notice = field(default_factory=lambda: _default_notice("staff"))
    student: Notice = field(default_factory=lambda: _default_notice("student"))

    def get(self, key: str) -> Notice:
        if key == "staff":
            return self.staff
        if key == "student":
            return self.student
        raise KeyError(key)

    def is_published(self, key: str) -> bool:
        return self.get(key).published

    def _replace(self, key: str, notice: Notice) -> None:
        if key == "staff":
            self.staff = notice
        elif key == "student":
            self.student = notice
        else:
            raise KeyError(key)

    def publish(
        self,
        key: str,
        *,
        cohort_idnumbers: tuple[str, ...] | list[str],
        shortnames: tuple[str, ...] | list[str],
        does_not: tuple[str, ...] | list[str],
        published_at: str | None,
    ) -> Notice:
        """Publish one notice, or raise ``NoticeDraftError``.

        Requirements (spec R15/R16/R18):
        * at least one cohort idnumber (the notice names the cohort);
        * at least one course shortname (the exact shortnames with C6 gold);
        * every :data:`REQUIRED_DOES_NOT` clause present;
        * a publish timestamp.
        """
        if key not in NOTICE_KEYS:
            raise NoticeDraftError(f"unknown notice key {key!r}")
        cohorts = tuple(str(c).strip() for c in cohort_idnumbers if str(c).strip())
        courses = tuple(str(c).strip() for c in shortnames if str(c).strip())
        clauses = tuple(str(c).strip() for c in does_not if str(c).strip())
        if not cohorts:
            raise NoticeDraftError("notice must name at least one cohort idnumber")
        if not courses:
            raise NoticeDraftError("notice must name at least one course shortname")
        missing = [token for token in REQUIRED_DOES_NOT if token not in clauses]
        if missing:
            raise NoticeDraftError(f"notice is missing R18 clauses: {missing}")
        if not published_at:
            raise NoticeDraftError("notice must carry a published_at timestamp")
        notice = replace(
            self.get(key),
            cohort_idnumbers=cohorts,
            shortnames=courses,
            does_not=clauses,
            published=True,
            published_at=str(published_at),
        )
        self._replace(key, notice)
        return notice

    def unpublish(self, key: str) -> Notice:
        notice = replace(
            self.get(key),
            cohort_idnumbers=(),
            shortnames=(),
            does_not=(),
            published=False,
            published_at=None,
        )
        self._replace(key, notice)
        return notice
