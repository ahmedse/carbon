"""DMS-COR-BOUND: inbound does not import people, emissions, or gradevance."""
from pathlib import Path

BANNED = ('people', 'emissions', 'gradevance')


def test_inbound_never_imports_people():
    """DMS-COR-BOUND"""
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for path in root.rglob('*.py'):
        if 'tests' in path.parts:
            continue
        text = path.read_text(encoding='utf-8')
        for i, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            for name in BANNED:
                if f'import {name}' in stripped or stripped.startswith(f'from {name}'):
                    offenders.append(f'{path.name}:{i}:{stripped}')
    assert not offenders, 'inbound must not import ' + ', '.join(BANNED) + ': ' + '; '.join(offenders)
