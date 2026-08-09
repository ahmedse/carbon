# File: config/log_viewer.py
# Phase 1 — Pure Python helper to read JSON-lines log files for the log viewer API.
# No Django ORM dependency — works with raw file I/O.

import json
import os
from typing import Optional


def read_logs(
    log_file: str,
    lines: int = 200,
    level: Optional[str] = None,
    search: Optional[str] = None,
    correlation_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Read log entries from a JSON-lines file with optional filters.

    Args:
        log_file: Absolute path to the log file.
        lines: Max number of raw lines to read from the end of the file.
        level: Filter by log level (INFO, WARNING, ERROR, CRITICAL, DEBUG).
        search: Case-insensitive substring search across message, name, pathname.
        correlation_id: Exact match on correlation_id field.
        page: 1-based page number for paged results.
        page_size: Number of entries per page.

    Returns:
        {
            entries: list[dict],
            total_matched: int,
            file_size_bytes: int,
            total_lines_in_file: int,
            page: int,
            page_size: int,
            total_pages: int,
        }
    """
    if not os.path.isfile(log_file):
        return {
            'entries': [],
            'total_matched': 0,
            'file_size_bytes': 0,
            'total_lines_in_file': 0,
            'page': 1,
            'page_size': page_size,
            'total_pages': 0,
            'error': f'Log file not found: {log_file}',
        }

    file_size = os.path.getsize(log_file)

    # Read last N lines efficiently by seeking backwards
    raw_lines = _tail_file(log_file, lines)
    total_lines = _count_lines(log_file)

    # Parse JSON and filter
    entries = []
    for raw in raw_lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue

        # Apply filters
        if level and entry.get('levelname', '').upper() != level.upper():
            continue
        if correlation_id and entry.get('correlation_id', '') != correlation_id:
            continue
        if search:
            search_lower = search.lower()
            searchable = ' '.join(str(v) for v in entry.values()).lower()
            if search_lower not in searchable:
                continue

        entries.append(entry)

    # Paginate
    total_matched = len(entries)
    total_pages = max(1, (total_matched + page_size - 1) // page_size)
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start = (page - 1) * page_size
    end = start + page_size
    paged_entries = entries[start:end]

    return {
        'entries': paged_entries,
        'total_matched': total_matched,
        'file_size_bytes': file_size,
        'total_lines_in_file': total_lines,
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
    }


def list_log_files(log_dir: str) -> list[dict]:
    """List available log files in a directory.

    Returns list of {name, path, size_bytes, modified} dicts sorted by name.
    """
    if not os.path.isdir(log_dir):
        return []

    files = []
    for fname in sorted(os.listdir(log_dir)):
        fpath = os.path.join(log_dir, fname)
        if not os.path.isfile(fpath):
            continue
        # Only include .log and .log.N rotated files
        if not (fname.endswith('.log') or '.log.' in fname):
            continue
        stat = os.stat(fpath)
        files.append({
            'name': fname,
            'path': fpath,
            'size_bytes': stat.st_size,
            'modified': stat.st_mtime,
        })

    # Sort: main log first, then rotated logs
    files.sort(key=lambda f: (not f['name'].endswith('.log'), f['name']))
    return files


def _tail_file(filepath: str, n: int) -> list[str]:
    """Read approximately the last N lines from a file efficiently.

    Seeks backwards from EOF and reads chunks until we have enough lines.
    Falls back to reading the whole file for small files.
    """
    try:
        with open(filepath, 'rb') as f:
            file_size = f.seek(0, 2)  # EOF

            if file_size == 0:
                return []

            # For small files or large N, read the whole thing
            if file_size < 1024 * 1024:  # < 1 MB
                f.seek(0)
                return f.read().decode('utf-8', errors='replace').splitlines()[-n:]

            # Read backwards in 8KB chunks
            chunk_size = 8192
            chunks = []
            remaining = file_size
            lines_found = 0

            while remaining > 0 and lines_found < n:
                read_size = min(chunk_size, remaining)
                remaining -= read_size
                f.seek(remaining)
                chunk = f.read(read_size).decode('utf-8', errors='replace')
                chunks.insert(0, chunk)
                lines_found += chunk.count('\n')

            return ''.join(chunks).splitlines()[-n:]
    except (OSError, IOError):
        return []


def _count_lines(filepath: str) -> int:
    """Count total lines in a file (approximate for large files)."""
    try:
        count = 0
        with open(filepath, 'rb') as f:
            for _ in f:
                count += 1
        return count
    except (OSError, IOError):
        return 0
