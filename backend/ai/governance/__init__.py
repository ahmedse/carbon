"""Pulse governance helpers that bind Plane B dials to Plane A CBAC keys."""

from ai.governance.review_authority import (  # noqa: F401
    DEFAULT_REQUIRED_AUTHORITY,
    REVIEW_AUTHORITY_BY_CAPABILITY,
    known_hr_review_authorities,
    resolve_required_authority,
)
