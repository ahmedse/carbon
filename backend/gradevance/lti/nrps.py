"""LTI Names and Role Provisioning Service (NRPS) scaffold.

Lists membership for a context — used to sync cohort before batch formative.
HTTP fetch is dry-run by default (reuses GRADEVANCE_LTI_AGS_DRY_RUN).
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class NrpsMember:
    user_id: str
    roles: tuple[str, ...]
    name: str = ""
    email: str = ""
    status: str = "Active"


@dataclass
class NrpsFetchResult:
    dry_run: bool
    ok: bool
    url: str
    members: list[dict[str, Any]]
    error: str = ""


def nrps_members_url_from_claim(claims: dict) -> str | None:
    nrps = claims.get("https://purl.imsglobal.org/spec/lti-nrps/claim/namesroleservice") or {}
    if isinstance(nrps, dict):
        return nrps.get("context_memberships_url")
    return None


def parse_nrps_membership_page(payload: dict[str, Any]) -> list[NrpsMember]:
    """Parse an IMS NRPS membership container into opaque members."""
    members = payload.get("members") or []
    out: list[NrpsMember] = []
    for m in members:
        if not isinstance(m, dict):
            continue
        uid = m.get("user_id") or m.get("userId") or ""
        if not uid:
            continue
        roles = m.get("roles") or []
        if not isinstance(roles, list):
            roles = [str(roles)]
        out.append(
            NrpsMember(
                user_id=str(uid),
                roles=tuple(str(r) for r in roles),
                name=str(m.get("name") or ""),
                email=str(m.get("email") or ""),
                status=str(m.get("status") or "Active"),
            )
        )
    return out


def fetch_nrps_membership(
    *,
    memberships_url: str,
    access_token: str | None = None,
    dry_run: bool | None = None,
    timeout: float = 15.0,
) -> NrpsFetchResult:
    """GET NRPS memberships. Dry-run returns empty members without network I/O."""
    from gradevance.lti.ags import AgsPassbackError
    from gradevance.lti.ags_client import fetch_ags_access_token

    if not memberships_url:
        raise AgsPassbackError("memberships_url required")

    use_dry = (
        bool(getattr(settings, "GRADEVANCE_LTI_AGS_DRY_RUN", True))
        if dry_run is None
        else dry_run
    )
    if use_dry:
        logger.info("NRPS dry-run GET %s", memberships_url)
        return NrpsFetchResult(
            dry_run=True,
            ok=True,
            url=memberships_url,
            members=[],
            error="",
        )

    token = access_token or fetch_ags_access_token(
        scopes=(
            "https://purl.imsglobal.org/spec/lti-nrps/scope/contextmembership.readonly"
        ),
    )
    resp = requests.get(
        memberships_url,
        timeout=timeout,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.ims.lti-nrps.v2.membershipcontainer+json",
        },
    )
    if resp.status_code >= 400:
        return NrpsFetchResult(
            dry_run=False,
            ok=False,
            url=memberships_url,
            members=[],
            error=f"HTTP {resp.status_code}: {resp.text[:200]}",
        )
    members = [asdict(m) for m in parse_nrps_membership_page(resp.json())]
    for m in members:
        m["roles"] = list(m.get("roles") or [])
    return NrpsFetchResult(
        dry_run=False,
        ok=True,
        url=memberships_url,
        members=members,
    )
