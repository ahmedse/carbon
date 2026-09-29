"""Cartridge declaration rules. Handlers are not data."""
from __future__ import annotations

import re

from .exceptions import InboundError

_KEY = re.compile(r'[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*')
_NAME = re.compile(r'[a-z][a-z0-9_]*')


def validate_key(key: str) -> str:
    key = (key or '').strip()
    if not _KEY.fullmatch(key):
        raise InboundError('Key must look like app.object', status=400)
    return key


def validate_fields(fields) -> list[dict]:
    if not isinstance(fields, list) or not fields:
        raise InboundError('At least one field is required', status=400)
    seen: set[str] = set()
    clean: list[dict] = []
    for raw in fields:
        if not isinstance(raw, dict):
            raise InboundError('Each field must be an object', status=400)
        name = str(raw.get('name') or '').strip()
        label = str(raw.get('label') or '').strip()
        if not _NAME.fullmatch(name) or not label:
            raise InboundError('Each field needs a lowercase name and a label', status=400)
        if name in seen:
            raise InboundError(f'Duplicate field {name}', status=400)
        seen.add(name)
        item = {'name': name, 'label': label, 'required': bool(raw.get('required'))}
        ref = str(raw.get('ref_set') or '').strip()
        if ref:
            item['ref_set'] = ref
        clean.append(item)
    return clean
