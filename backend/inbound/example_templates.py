"""Curated example templates for the inbound template surface.

Each entry is a real ``docs/migration/examples/*.template.csv`` file that ships
with the repo. The endpoint lists them; there is no DB row and no fabricated
header. Reads only — downloads never create or overwrite a template.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from django.conf import settings

from .exceptions import InboundError

SUFFIX = '.template.csv'
EXAMPLES_DIR = Path(settings.BASE_DIR).resolve().parent / 'docs' / 'migration' / 'examples'


def _slug(filename: str) -> str:
    return filename[: -len(SUFFIX)]


def _label(slug: str) -> str:
    return slug.replace('-', ' ').replace('_', ' ').strip()


def _columns(path: Path) -> list[str]:
    try:
        with path.open('r', encoding='utf-8-sig', newline='') as handle:
            header = handle.readline()
    except OSError:
        return []
    first = next(csv.reader(io.StringIO(header)), [])
    return [cell.strip() for cell in first if cell.strip()]


def list_examples() -> list[dict]:
    """Every real example file on disk. Empty list when none ship."""
    if not EXAMPLES_DIR.is_dir():
        return []
    rows = []
    for path in sorted(EXAMPLES_DIR.glob(f'*{SUFFIX}')):
        slug = _slug(path.name)
        rows.append({
            'slug': slug,
            'filename': path.name,
            'name': _label(slug),
            'columns': _columns(path),
        })
    return rows


def read_example(slug: str) -> tuple[str, bytes]:
    """Return ``(filename, bytes)`` for a listed slug, else 404."""
    wanted = (slug or '').strip()
    for row in list_examples():
        if row['slug'] == wanted:
            path = EXAMPLES_DIR / row['filename']
            try:
                return row['filename'], path.read_bytes()
            except OSError as exc:
                raise InboundError('Example template is unreadable', status=404) from exc
    raise InboundError('Unknown example template', status=404)
