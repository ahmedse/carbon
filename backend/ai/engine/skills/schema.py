"""
Schema validation for procedural skills (BE-02-4).

Pydantic models that validate the `body` JSON column when kind='procedure'.
The body describes an executable multi-step sequence the agent can invoke.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, field_validator

VALID_STEP_TYPES = frozenset({
    "tool_call",
    "llm_call",
    "conditional",
    "parallel",
    "wait_for_approval",
})

VALID_ON_FAILURE = frozenset({"abort", "continue", "retry", "skip"})


# ── Executable skill schema (P4-04) ──────────────────────────────────────
# An executable skill body references a governed process by
# ``process_id`` or ``process_id@version``, and MAY declare the tool names the
# referenced process is allowed to use.  ``process_ref`` is validated strictly
# here; ``allowed_tools`` is normalized to a sorted, de-duplicated list.


@dataclass(frozen=True)
class ProcessRef:
    """A reference to a governed process: ``process_id`` plus optional version."""

    process_id: str
    version: str | None = None


def parse_process_ref(ref: str) -> ProcessRef:
    """Parse a ``process_ref`` string into a :class:`ProcessRef`.

    Accepts exactly ``id`` or ``id@version``.  Fail-closed on any malformed
    input: non-strings, empty strings, more than one ``@``, empty process id
    or version, and any leading/trailing or embedded whitespace.
    """
    if not isinstance(ref, str):
        raise ValueError(
            f"process_ref must be a string, got {type(ref).__name__}: {ref!r}"
        )
    if not ref:
        raise ValueError("process_ref must be a non-empty string, got ''")
    if ref != ref.strip():
        raise ValueError(
            f"process_ref must not have leading or trailing whitespace, got {ref!r}"
        )

    parts = ref.split("@")
    if len(parts) > 2:
        raise ValueError(
            f"process_ref must be 'id' or 'id@version' (at most one '@'), got {ref!r}"
        )

    process_id = parts[0]
    version = parts[1] if len(parts) == 2 else None

    if not process_id:
        raise ValueError(f"process_ref has an empty process_id, got {ref!r}")
    if version is not None and not version:
        raise ValueError(f"process_ref has an empty version, got {ref!r}")

    for label, part in (("process_id", process_id), ("version", version)):
        if part is None:
            continue
        if any(c.isspace() for c in part):
            raise ValueError(
                f"process_ref {label} must not contain whitespace, got {ref!r}"
            )
        if "@" in part:
            raise ValueError(
                f"process_ref {label} must not contain '@', got {ref!r}"
            )

    return ProcessRef(process_id=process_id, version=version)


def format_process_ref(ref: ProcessRef) -> str:
    """Return the canonical ``id`` or ``id@version`` string for ``ref``."""
    if ref.version:
        return f"{ref.process_id}@{ref.version}"
    return ref.process_id


class ExecutableSkillBody(BaseModel):
    """The validated schema for a skill body that references a governed process.

    Stored as JSON text in ``Skill.body`` when the skill is executable.  The
    declared ``allowed_tools`` are enforced by the PDP (stage 6) at invoke
    time against the invoking principal's capabilities.
    """

    process_ref: str
    allowed_tools: list[str] = []

    @field_validator("process_ref")
    @classmethod
    def _validate_process_ref(cls, v: str) -> str:
        parse_process_ref(v)
        return v

    @field_validator("allowed_tools")
    @classmethod
    def _normalize_allowed_tools(cls, v: list[str]) -> list[str]:
        if v is None:
            return []
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in v:
            if not isinstance(item, str):
                raise ValueError(
                    f"allowed_tools entries must be strings, got {item!r}"
                )
            item = item.strip()
            if not item:
                raise ValueError("allowed_tools must not contain empty-string entries")
            if item not in seen:
                seen.add(item)
                cleaned.append(item)
        return sorted(cleaned)


class ProcedureStep(BaseModel):
    """A single step in a procedure's execution sequence."""

    id: str
    type: Literal["tool_call", "llm_call", "conditional", "parallel", "wait_for_approval"]
    tool_name: str | None = None
    task: str | None = None  # for llm_call: cognition, retrieval, etc.
    params: dict = {}
    prompt_template: str | None = None
    output_key: str | None = None
    condition: str | None = None
    then: str | None = None  # step id or "done"
    else_: str | None = None  # step id or "done"
    on_failure: str = "abort"

    @field_validator("on_failure")
    @classmethod
    def _check_on_failure(cls, v: str) -> str:
        if v not in VALID_ON_FAILURE:
            raise ValueError(f"on_failure must be one of {sorted(VALID_ON_FAILURE)}, got {v!r}")
        return v

    @field_validator("type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in VALID_STEP_TYPES:
            raise ValueError(f"step type must be one of {sorted(VALID_STEP_TYPES)}, got {v!r}")
        return v


class ProcedureBody(BaseModel):
    """The validated schema for a skill row with kind='procedure'.

    Stored as JSON text in Skill.body. All steps are validated at write time.
    """

    version: int = 1
    steps: list[ProcedureStep]
    output_schema: dict = {}
    # GAP-6: coverage and prerequisite declarations (domain-set, core-read)
    covers: list[str] = []
    requires: list[str] = []
    produces: list[str] = []
    # GAP-5: canonical terminology map — human phrase → platform term
    terminology: dict[str, str] = {}

    @field_validator("steps")
    @classmethod
    def _steps_not_empty(cls, v: list[ProcedureStep]) -> list[ProcedureStep]:
        if len(v) == 0:
            raise ValueError("procedure must have at least one step")
        return v
