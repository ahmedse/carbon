# File: people/tests/ref_helpers.py
# NSR-7B — helpers to resolve/create ReferenceValues for people tests.
# Test-only: get_or_create is fine here (RULE_16 applies to app write paths).

from mdm.models import ReferenceSet, ReferenceValue


def ensure_ref(set_name, code, label=None):
    """Return a ReferenceValue for ``(set_name, code)``, creating set/value if needed."""
    slug = set_name.replace('_', '-')
    rs, _ = ReferenceSet.objects.get_or_create(
        name=set_name,
        defaults={
            'slug': slug,
            'description': set_name,
            'is_active': True,
            'lifecycle_state': 'active',
        },
    )
    if rs.lifecycle_state != 'active' or not rs.is_active:
        ReferenceSet.objects.filter(pk=rs.pk).update(
            is_active=True, lifecycle_state='active',
        )
    rv, _ = ReferenceValue.objects.get_or_create(
        reference_set=rs,
        code=code,
        defaults={
            'label': label or code,
            'is_active': True,
        },
    )
    return rv


def compliance_rule_defaults(category='other', jurisdiction='KW'):
    """FK defaults for ComplianceRule.objects.create(...)."""
    return {
        'category': ensure_ref('compliance_category', category),
        'jurisdiction': ensure_ref('jurisdiction', jurisdiction),
    }
