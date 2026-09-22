"""Normalize profile-change payload on sent_back edit (no Employee mutation)."""

from __future__ import annotations

from .profile_change_service import PROFILE_CHANGE_ALLOWLIST


class ProfileChangeReviseError(Exception):
    def __init__(self, detail, *, error_kind=None, status_code=400, **extra):
        super().__init__(detail)
        self.detail = detail
        self.error_kind = error_kind
        self.status_code = status_code
        self.extra = extra


def apply_profile_change_payload_edit(corr, payload: dict) -> tuple[dict, str]:
    """Validate ``changes`` allowlist shape; return payload for fsm.edit_payload.

    Does not write Employee — approve signal applies later.
    """
    if not isinstance(payload, dict):
        raise ProfileChangeReviseError(
            'payload must be an object',
            error_kind='invalid_payload',
        )

    changes = payload.get('changes')
    if not isinstance(changes, dict) or not changes:
        raise ProfileChangeReviseError(
            'changes must be a non-empty object of {field: {from, to}}',
            error_kind='invalid_changes',
        )

    normalized_changes = {}
    for field, change in changes.items():
        if field not in PROFILE_CHANGE_ALLOWLIST:
            raise ProfileChangeReviseError(
                f'Field {field!r} is not allowed on profile change',
                error_kind='field_not_allowed',
            )
        if not isinstance(change, dict) or 'to' not in change:
            raise ProfileChangeReviseError(
                f'change for {field!r} must be an object with a "to" value',
                error_kind='invalid_change',
            )
        entry = {'to': change['to']}
        if 'from' in change:
            entry['from'] = change['from']
        normalized_changes[field] = entry

    title = 'Profile change request'
    if corr.title:
        title = corr.title
    return {'changes': normalized_changes}, title
