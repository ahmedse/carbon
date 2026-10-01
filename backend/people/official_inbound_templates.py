"""Official People InboundTemplate rows (ADR-0060 · DMS templates slice).

Identity maps (every cartridge field → itself) so the blank header CSV and the
Map SearchSelect apply path share one layout. Seed is create-only: an existing
row with the official name is never overwritten (operator customizations stick).

inbound never imports this module (RULE_3). People owns the seed.
"""

from __future__ import annotations

from inbound.models import InboundTemplate

from .inbound_cartridges import BALANCE_FIELDS, EMPLOYEE_FIELDS, HISTORY_FIELDS

KIND_TYPED = 'typed_object'

# Stable names — match live nibras rows and SearchSelect labels.
OFFICIAL_TEMPLATES = (
    {
        'name': 'People · Employee snapshot',
        'target_key': 'people.employee_snapshot',
        'fields': EMPLOYEE_FIELDS,
    },
    {
        'name': 'People · Leave opening balance',
        'target_key': 'people.leave_opening_balance',
        'fields': BALANCE_FIELDS,
    },
    {
        'name': 'People · Leave history',
        'target_key': 'people.leave_history',
        'fields': HISTORY_FIELDS,
    },
)


def identity_columns(fields) -> dict:
    """mapping.columns = every declared field name → itself."""
    return {f['name']: f['name'] for f in fields}


def official_mapping(fields) -> dict:
    return {'columns': identity_columns(fields), 'crosswalks': {}}


def ensure_official_inbound_templates() -> dict:
    """Idempotent create-only seed. Returns counts: created, existing, keys."""
    created = 0
    existing = 0
    keys = []
    for spec in OFFICIAL_TEMPLATES:
        keys.append(spec['target_key'])
        _obj, was_created = InboundTemplate.objects.get_or_create(
            name=spec['name'],
            target_key=spec['target_key'],
            defaults={
                'kind': KIND_TYPED,
                'mapping': official_mapping(spec['fields']),
                'owner': None,
            },
        )
        if was_created:
            created += 1
        else:
            existing += 1
    return {
        'created': created,
        'existing': existing,
        'keys': keys,
        'expected': len(OFFICIAL_TEMPLATES),
    }
