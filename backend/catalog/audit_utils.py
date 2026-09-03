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
):
    """Create a GovernanceEvent record with before/after state.

    Best-effort and non-blocking: a governance-event failure MUST NEVER roll
    back the caller's business write. The insert runs in its own
    ``transaction.atomic()`` savepoint so that if it raises (e.g. a PostgreSQL
    DataError from an over-long action/entity_type), ONLY this event insert is
    rolled back — the caller's outer transaction stays intact.
    """
    from catalog.models import GovernanceEvent

    try:
        with transaction.atomic():
            GovernanceEvent.objects.create(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                before=before or {},
                after=after or {},
                user=user,
                asset=asset_profile,
            )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to emit governance event for %s#%s: %s", entity_type, entity_id, exc)
