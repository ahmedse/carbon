# inbound/parse.py — server-side CSV only. No pandas. No domain words.
from __future__ import annotations

import csv
import hashlib
import io

ALLOWED_ENCODINGS = ('utf-8-sig', 'utf-8', 'windows-1256', 'cp1252')


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_csv(data: bytes, encoding: str | None = None) -> tuple[str, str]:
    """Return (text, encoding_used)."""
    if encoding:
        return data.decode(encoding), encoding
    for enc in ALLOWED_ENCODINGS:
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode('utf-8', errors='replace'), 'utf-8'


def sniff_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample[:4096], delimiters=',;\t|')
        return dialect.delimiter
    except csv.Error:
        return ','


def parse_csv(data: bytes, encoding: str | None = None, delimiter: str | None = None) -> dict:
    text, enc = decode_csv(data, encoding)
    delim = delimiter or sniff_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    headers = [h for h in (reader.fieldnames or []) if h is not None]
    rows = []
    for raw in reader:
        if not raw or all((v or '').strip() == '' for v in raw.values()):
            continue
        rows.append({h: (raw.get(h) or '').strip() for h in headers})
    return {
        'encoding': enc,
        'delimiter': delim,
        'headers': headers,
        'row_count': len(rows),
        'sample': rows[:20],
        'rows': rows,
    }
