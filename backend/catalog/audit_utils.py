import logging
from typing import Any, Dict, Optional

from django.db import transaction

logger = logging.getLogger(__name__)


def emit_governance_event(
    entity_type: str,
    entity_id: int,
    action: str,
    before: Optional[Dict[str, Any]],
    after: Optional[Dict[str, Any]],
    user,
    asset_profile=None,
    *,
    strict: bool = False,
):
    """Create a GovernanceEvent record with before/after state.

    Default is best-effort: a governance-event failure must not roll back the
    caller's business write. The insert runs in its own savepoint so that if
    it raises, only this event insert is rolled back.

    ``strict=True`` writes in the caller's transaction and lets the exception
    propagate. Policy publish uses this so a failed event insert undoes the
    state change.
    """
    from catalog.models import GovernanceEvent

    payload = dict(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before=before or {},
        after=after or {},
        user=user,
        asset=asset_profile,
    )
    if strict:
        GovernanceEvent.objects.create(**payload)
        return
    try:
        with transaction.atomic():
            GovernanceEvent.objects.create(**payload)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to emit governance event for %s#%s: %s", entity_type, entity_id, exc)
