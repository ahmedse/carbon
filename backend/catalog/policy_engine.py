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
        matched = True
    elif scope_type == 'org_unit' and org_unit_id:
        matched = str(policy.org_unit_id) == str(org_unit_id)
    elif scope_type == 'scope' and module:
        matched = bool(policy.emission_scope) and str(policy.emission_scope) == str(getattr(module, 'scope', None))
    elif scope_type == 'domain' and data_table:
        matched = _domain_matches(policy, data_table)
    else:
        return False
    if not matched:
        return False
    return _rules_block(policy, module=module, data_table=data_table)


def _domain_matches(policy, data_table):
    from catalog.models import AssetProfile
    try:
        asset = AssetProfile.objects.filter(data_table=data_table).first()
    except Exception:
        return False
    return bool(asset and asset.domain_id and policy.domain_id == asset.domain_id)


def _rules_block(policy, *, module=None, data_table=None):
    """A matched policy blocks unless its config says the data is already gone."""
    config = policy.config if isinstance(policy.config, dict) else {}
    if config.get('check_row_count'):
        return _has_active_rows(module=module, data_table=data_table)
    return True


def _has_active_rows(*, module=None, data_table=None):
    from dataschema.models import DataRow
    rows = DataRow.objects.filter(is_archived=False)
    if data_table is not None:
        return rows.filter(data_table=data_table).exists()
    if module is not None:
        return rows.filter(data_table__module=module).exists()
    return True
