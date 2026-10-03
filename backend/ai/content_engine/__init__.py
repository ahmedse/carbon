"""Content-engine readers (default-OFF).

File-format readers that turn a local file into citable ``TextUnit`` rows.

This package is **not** on any turn path. It is never imported by
``ai/engine/**``, ``ai/moodle_page.py``, or ``ai/moodle_host.py``. Importing it
has no side effects and opens no network connection.

The public surface is ``readers.registry.dispatch(path, mime)``.
"""

from __future__ import annotations

__all__ = ["readers"]
