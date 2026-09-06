"""Workflow policy resolution and snapshotting."""

from .models import WorkflowPolicy


class PolicyNotFound(Exception):
    """No active WorkflowPolicy matches the request."""


def resolve_policy(*, corr_type, org_unit=None) -> WorkflowPolicy:
    """Most-specific active policy: (corr_type, org_unit) first, then
    (corr_type, org_unit=None) global default. Raise PolicyNotFound if none.
    Return the policy with steps prefetched (ordered by 'order', is_active=True)."""
    # Prefer org-specific.
    policy = (
        WorkflowPolicy.objects
        .filter(corr_type=corr_type, org_unit=org_unit, is_active=True)
        .prefetch_related('steps')
        .first()
    )
    if policy is not None:
        return policy

    # Fall back to global (org_unit__isnull=True).
    policy = (
        WorkflowPolicy.objects
        .filter(corr_type=corr_type, org_unit__isnull=True, is_active=True)
        .prefetch_related('steps')
        .first()
    )
    if policy is None:
        raise PolicyNotFound(
            f'No active workflow policy for corr_type={corr_type} '
            f'org_unit={org_unit or "global"}'
        )
    return policy


def freeze_policy(policy) -> dict:
    """Snapshot dict for Correspondence.policy_snapshot."""
    return {
        'policy_id': policy.id,
        'policy_version': policy.version,
        'policy_snapshot': {
            'name': policy.name,
            'numbering_format': policy.numbering_format,
            'steps': [
                {
                    'order': s.order, 'role': s.role, 'intent': s.intent,
                    'specific_user_id': s.specific_user_id,
                    'skip_if_self': s.skip_if_self, 'auto_approve': s.auto_approve,
                    'can_skip': s.can_skip, 'condition': s.condition,
                }
                for s in policy.steps.all().order_by('order').filter(is_active=True)
            ],
        },
    }
