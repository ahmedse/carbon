"""Process-owner interview kit (P3-04) — host-side functions.

Turns an interview transcript into a filled process definition with durable
provenance, then records the owner's signature.

The question bank is loaded from the domain pack (``prompts/process_interview.yaml``,
surfaced through the engine port ``load_domain_pack(...).prompts()`` keyed by file
stem ``process_interview``). If the pack is absent (NeutralDomainPack) or returns
no questions, a built-in default list is used — mirroring the ``NeutralDomainPack``
degradation pattern.

All public functions are sync and DB-backed; a caller that is async must bridge
with ``asgiref.sync.sync_to_async(..., thread_sensitive=True)`` itself.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from django.core.exceptions import ValidationError
from django.utils import timezone

from ai.models.process import ProcessDefinition, validate_definition
from ai.models.process_interview import STATUS_OPEN, STATUS_SIGNED, ProcessInterview

INTERVIEW_PROMPT_KEY = "process_interview"

# Built-in fallback question bank (mirror of domain_packs/carbon/prompts/
# process_interview.yaml). The pack is the single source of truth; this list is
# used only when the pack cannot be loaded or returns no questions.
DEFAULT_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "emergency_waivers",
        "question": "Under what conditions may an emergency waiver bypass the "
        "normal approval flow for this process?",
        "field": "exceptions",
        "required": False,
        "hint": "Record as a list of waiver conditions; leave empty if no waivers are permitted.",
    },
    {
        "id": "approval_validity_after_edit",
        "question": "Does editing a previously approved definition invalidate its approval?",
        "field": "scope.approval_validity",
        "required": False,
        "hint": "e.g. 're-approval required after any edit' — stored under scope.approval_validity.",
    },
    {
        "id": "reconciliation_owner",
        "question": "Who owns reconciliation when a running instance diverges from this process?",
        "field": "owner",
        "required": False,
        "hint": "Identity string of the accountable owner (overwrites the definition owner field).",
    },
    {
        "id": "sla",
        "question": "What service-level agreement applies to this process?",
        "field": "constraints.sla",
        "required": False,
        "hint": "e.g. 'review within 2 business days' — stored under constraints.sla.",
    },
]


class InterviewNotFoundError(ValueError):
    """Raised when no ``ProcessDefinition`` exists for the given ``process_id``."""

    def __init__(self, process_id: str):
        self.process_id = process_id
        super().__init__(f"No process definition found for {process_id!r}.")


def load_questions() -> list[dict[str, Any]]:
    """Return the question bank from the pack (fall back to defaults)."""
    questions: Any = None
    try:
        from ai.engine.ports.domain import load_domain_pack
        from ai.models.capability import default_pack_dir

        pack = load_domain_pack(default_pack_dir())
        prompts = pack.prompts() or {}
        questions = prompts.get(INTERVIEW_PROMPT_KEY)
    except Exception:  # pragma: no cover - any port failure degrades to defaults
        questions = None

    if isinstance(questions, list):
        cleaned = [q for q in questions if isinstance(q, dict) and q.get("id")]
        if cleaned:
            return cleaned
    return [dict(q) for q in DEFAULT_QUESTIONS]


def _question_index() -> dict[str, dict[str, Any]]:
    return {q["id"]: q for q in load_questions()}


def _latest_definition(process_id: str) -> ProcessDefinition | None:
    return (
        ProcessDefinition.objects.filter(process_id=process_id)
        .order_by("-created_at")
        .first()
    )


def _get_or_create_interview(process_id: str) -> ProcessInterview:
    interview = (
        ProcessInterview.objects.filter(process_id=process_id)
        .order_by("-created_at")
        .first()
    )
    if interview is None:
        interview = ProcessInterview.objects.create(
            process_id=process_id, questions=load_questions(),
        )
    return interview


def _set_dotted_path(document: dict[str, Any], path: str, value: Any) -> None:
    """Set ``path`` (e.g. ``constraints.sla``) in ``document`` in place."""
    parts = path.split(".")
    node: dict[str, Any] = document
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value


def _serialize_interview(interview: ProcessInterview | None) -> dict[str, Any] | None:
    if interview is None:
        return None
    return {
        "id": interview.id,
        "process_id": interview.process_id,
        "questions": interview.questions,
        "answers": interview.answers,
        "status": interview.status,
        "signed_by": interview.signed_by,
        "signed_at": interview.signed_at.isoformat() if interview.signed_at else None,
        "signature_digest": interview.signature_digest,
    }


def build_interview_kit(process_id: str) -> dict[str, Any]:
    """Return the question bank, the current definition snapshot, and any
    durable interview record (provenance) for ``process_id``."""
    definition = _latest_definition(process_id)
    interview = (
        ProcessInterview.objects.filter(process_id=process_id)
        .order_by("-created_at")
        .first()
    )
    return {
        "process_id": process_id,
        "questions": load_questions(),
        "definition": definition.definition if definition else None,
        "interview": _serialize_interview(interview),
    }


def record_answers(
    process_id: str, answers: dict[str, Any], answered_by: str,
) -> dict[str, Any]:
    """Merge answers into the definition fields, record provenance, validate.

    ``answers`` maps question id → answer value. Each answer is written to its
    question's ``field`` (a dotted path into the definition), provenance is
    appended to the durable ``ProcessInterview.answers`` list (who/when), and the
    merged document is validated — invalid merges are rejected (nothing saved).
    """
    if not answered_by:
        raise ValueError("answered_by must not be empty")

    definition_obj = _latest_definition(process_id)
    if definition_obj is None:
        raise InterviewNotFoundError(process_id)

    index = _question_index()
    document: dict[str, Any] = dict(definition_obj.definition or {})
    now = timezone.now()
    provenance: list[dict[str, Any]] = []

    for question_id, answer in answers.items():
        question = index.get(question_id)
        if question is None:
            raise ValueError(f"Unknown question id {question_id!r}.")
        field = question.get("field")
        if field:
            _set_dotted_path(document, field, answer)
        provenance.append(
            {
                "question_id": question_id,
                "answer": answer,
                "answered_by": answered_by,
                "answered_at": now.isoformat(),
            }
        )

    errors = validate_definition(document)
    if errors:
        raise ValidationError({"definition": errors})

    definition_obj.definition = document
    definition_obj.process_id = str(document.get("id") or process_id)
    definition_obj.version = str(document.get("version") or "")
    definition_obj.owner = str(document.get("owner") or "")
    definition_obj.status = str(document.get("status") or "draft")
    definition_obj.save()

    interview = _get_or_create_interview(process_id)
    interview.answers = list(interview.answers or []) + provenance
    interview.save()

    return {
        "process_id": process_id,
        "definition": document,
        "recorded": provenance,
    }


def _signature_digest(document: dict[str, Any], owner: str) -> str:
    payload = json.dumps(document, sort_keys=True, default=str) + "\x00" + owner
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sign_definition(
    process_id: str, owner: str, evidence_digest: str | None = None,
) -> dict[str, Any]:
    """Record the owner's signature over the final definition.

    Refuses to sign when ``owner`` is empty or the definition is invalid.
    """
    if not owner:
        raise ValueError("owner must not be empty")

    definition_obj = _latest_definition(process_id)
    if definition_obj is None:
        raise InterviewNotFoundError(process_id)

    document: dict[str, Any] = dict(definition_obj.definition or {})
    errors = validate_definition(document)
    if errors:
        raise ValidationError({"definition": errors})

    digest = _signature_digest(document, owner)
    interview = _get_or_create_interview(process_id)
    interview.signed_by = owner
    interview.signed_at = timezone.now()
    interview.signature_digest = digest
    interview.status = STATUS_SIGNED
    interview.save()

    return {
        "process_id": process_id,
        "signed_by": owner,
        "signed_at": interview.signed_at.isoformat(),
        "signature_digest": digest,
        "evidence_digest": evidence_digest,
        "status": interview.status,
    }
