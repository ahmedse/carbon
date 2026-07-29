"""Runtime governance policy enforcement engine."""

from catalog.models import GovernancePolicy


def check_policy(action, *, org_unit_id=None, module=None, data_table=None):
    """Evaluate enabled governance policies for an action.
    Returns (allowed: bool, blocked_by: list[str])."""
    policies = GovernancePolicy.objects.filter(enabled=True, policy_type=action)
    if not policies.exists():
        return True, []

    blocked_by = []
    for policy in policies:
        if _policy_matches(policy, org_unit_id=org_unit_id, module=module, data_table=data_table):
            blocked_by.append(policy.name)
    return len(blocked_by) == 0, blocked_by


def _policy_matches(policy, *, org_unit_id=None, module=None, data_table=None):
    scope_type = policy.scope_type
    if scope_type == 'global':
        return True
    if scope_type == 'org_unit' and org_unit_id:
        return str(policy.org_unit_id) == str(org_unit_id)
    if scope_type == 'scope' and module:
        return policy.emission_scope and str(policy.emission_scope) == str(getattr(module, 'scope', None))
    if scope_type == 'domain' and data_table:
        from catalog.models import AssetProfile
        try:
            asset = AssetProfile.objects.filter(data_table=data_table).first()
            if asset and asset.domain:
                return policy.domain_id == asset.domain_id
        except Exception:
            pass
    return False
