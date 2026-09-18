"""LTI 1.3 Advantage scaffold (P3) — not wired to production LMS yet.

When enabled, mount under ``/api/v1/gradevance/lti/`` and configure
platform JWKS / client_id via instance settings. Score passback only after
``AnalysisRun.released`` for summative assignments.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LtiLaunchContext:
    iss: str
    sub: str
    deployment_id: str
    roles: tuple[str, ...]
    resource_link_id: str | None = None
    context_id: str | None = None


def map_lti_roles_to_capabilities(roles: tuple[str, ...]) -> set[str]:
    """Map IMS roles to GradeVance capability keys (scaffold)."""
    caps: set[str] = set()
    joined = " ".join(r.lower() for r in roles)
    if "instructor" in joined or "faculty" in joined or "teachingassistant" in joined:
        caps.update({"gradevance:view", "gradevance:manage", "gradevance:mark"})
    if "learner" in joined or "student" in joined:
        caps.update({"gradevance:view", "gradevance:submit"})
    if "administrator" in joined:
        caps.update({"gradevance:view", "gradevance:manage", "gradevance:qa"})
    return caps


def ags_passback_allowed(*, released: bool, mode: str) -> bool:
    if mode == "summative":
        return bool(released)
    return True  # formative advisory may sync as draft/comment only in future
