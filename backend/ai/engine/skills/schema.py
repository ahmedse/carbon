"""
Schema validation for procedural skills (BE-02-4).

Pydantic models that validate the `body` JSON column when kind='procedure'.
The body describes an executable multi-step sequence the agent can invoke.
"""
from __future__ import annotations

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
