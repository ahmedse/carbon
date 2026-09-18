"""Deep Linking response builder scaffold (LTI 1.3 Advantage)."""
from __future__ import annotations

from typing import Any


def deep_link_assignment_content_item(
    *,
    title: str,
    url: str,
    assignment_id: str,
    profile_pack_id: str,
) -> dict[str, Any]:
    """Return a single LtiResourceLink content item for Deep Linking."""
    return {
        "type": "ltiResourceLink",
        "title": title,
        "url": url,
        "custom": {
            "gradevance_assignment_id": assignment_id,
            "gradevance_profile_pack_id": profile_pack_id,
        },
    }


def deep_link_jwt_claims(
    *,
    iss: str,
    aud: str,
    deployment_id: str,
    data: str | None,
    content_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Unsigned claims payload — sign with tool private key in production."""
    return {
        "iss": iss,
        "aud": aud,
        "https://purl.imsglobal.org/spec/lti/claim/message_type": "LtiDeepLinkingResponse",
        "https://purl.imsglobal.org/spec/lti/claim/version": "1.3.0",
        "https://purl.imsglobal.org/spec/lti/claim/deployment_id": deployment_id,
        "https://purl.imsglobal.org/spec/lti-dl/claim/content_items": content_items,
        "https://purl.imsglobal.org/spec/lti-dl/claim/data": data,
    }
