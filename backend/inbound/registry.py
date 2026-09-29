# inbound/registry.py — domain-free cartridge registry (ADR-0060).
# Hosted apps call register() from AppConfig.ready(). This module never
# imports people / emissions / gradevance.

from __future__ import annotations

from typing import Any, Callable

_REGISTRY: dict[str, dict[str, Any]] = {}


def ensure_persisted(item: dict[str, Any]):
    """Create the declaration on first sight. Later edits in the studio win."""
    from django.db.utils import OperationalError, ProgrammingError

    from inbound.models import InboundCartridge

    owner = item['key'].split('.', 1)[0]
    try:
        row, created = InboundCartridge.objects.get_or_create(
            key=item['key'],
            defaults={
                'kind': item['kind'],
                'label': item['label'],
                'label_ar': item.get('label_ar') or '',
                'owner_app': owner,
                'fields': list(item.get('fields') or []),
                'enabled': True,
            },
        )
    except (OperationalError, ProgrammingError):
        item['enabled'] = item.get('enabled', True)
        return None
    if created:
        item['enabled'] = row.enabled
        return row
    item['label'] = row.label
    item['label_ar'] = row.label_ar
    item['fields'] = list(row.fields or [])
    item['enabled'] = row.enabled
    return row


def sync_all() -> None:
    for item in list(_REGISTRY.values()):
        ensure_persisted(item)


def is_bound(key: str) -> bool:
    item = _REGISTRY.get(key)
    return bool(item and callable(item.get('smoke')) and callable(item.get('commit')))


def apply_definition(key: str, *, label: str, label_ar: str, fields: list, enabled: bool) -> None:
    item = _REGISTRY.get(key)
    if not item:
        return
    item['label'] = label
    item['label_ar'] = label_ar
    item['fields'] = list(fields)
    item['enabled'] = enabled


def register(
    *,
    kind: str,
    key: str,
    label: str,
    fields: list[dict],
    smoke: Callable,
    commit: Callable,
    label_ar: str = '',
) -> None:
    if kind not in ('typed_object', 'data_product'):
        raise ValueError(f'unknown kind {kind!r}')
    if not key or '.' not in key:
        raise ValueError('target key must be namespaced (app.object)')
    _REGISTRY[key] = {
        'kind': kind,
        'key': key,
        'label': label,
        'label_ar': label_ar,
        'fields': list(fields),
        'smoke': smoke,
        'commit': commit,
        'enabled': True,
    }
    ensure_persisted(_REGISTRY[key])


def get(key: str) -> dict[str, Any]:
    cartridge = _REGISTRY.get(key)
    if cartridge is not None:
        return cartridge
    from inbound.adapters.dataschema import resolve
    return resolve(key)


def list_targets(kind: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for item in _REGISTRY.values():
        if kind and item['kind'] != kind:
            continue
        ensure_persisted(item)
        if item.get('enabled') is False:
            continue
        rows.append({
            'key': item['key'],
            'kind': item['kind'],
            'label': item['label'],
            'label_ar': item['label_ar'],
            'fields': item['fields'],
        })
    if kind in (None, 'data_product'):
        from inbound.adapters.dataschema import list_product_targets
        existing = {row['key'] for row in rows}
        for row in list_product_targets():
            if row['key'] not in existing:
                rows.append(row)
    return sorted(rows, key=lambda r: r['key'])


def clear() -> None:
    """Tests only."""
    _REGISTRY.clear()
