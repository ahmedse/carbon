"""Provision opaque student keys from an NRPS membership list."""
from __future__ import annotations

from dataclasses import dataclass

from gradevance.lti.nrps import NrpsMember, parse_nrps_membership_page
from gradevance.lti.provision import provision_user_from_launch
from gradevance.lti import LtiLaunchContext


@dataclass
class RosterSyncResult:
    created: int
    existing: int
    usernames: list[str]


def sync_nrps_members_to_users(
    *,
    iss: str,
    deployment_id: str,
    members: list[NrpsMember] | list[dict],
) -> RosterSyncResult:
    """Idempotent: each NRPS user_id → ``lti:{iss}:{user_id}`` User + groups."""
    created = 0
    existing = 0
    names: list[str] = []
    for raw in members:
        if isinstance(raw, dict):
            m = NrpsMember(
                user_id=str(raw.get("user_id") or ""),
                roles=tuple(raw.get("roles") or ()),
                name=str(raw.get("name") or ""),
                email=str(raw.get("email") or ""),
                status=str(raw.get("status") or "Active"),
            )
        else:
            m = raw
        if not m.user_id or m.status.lower() not in ("active", ""):
            continue
        ctx = LtiLaunchContext(
            iss=iss,
            sub=m.user_id,
            deployment_id=deployment_id,
            roles=m.roles,
        )
        result = provision_user_from_launch(ctx, email=m.email or None, name=m.name or None)
        if result.created:
            created += 1
        else:
            existing += 1
        names.append(result.username)
    return RosterSyncResult(created=created, existing=existing, usernames=names)


def sync_nrps_payload(
    *,
    iss: str,
    deployment_id: str,
    payload: dict,
) -> RosterSyncResult:
    return sync_nrps_members_to_users(
        iss=iss,
        deployment_id=deployment_id,
        members=parse_nrps_membership_page(payload),
    )
