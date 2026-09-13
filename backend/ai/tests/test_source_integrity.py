"""Regression guard for NB-BP-006 (loan workflow reload storm).

Root cause: the dev server ran ``runserver`` with Django's StatReloader
auto-reload enabled. Rapid ``.py`` edits during active development triggered a
full restart every few seconds; each restart queued in-flight HTTP requests
~13s, spiking loan POST latency from ~4.3s to ~17.6s.

Two invariants are guarded here so the defect cannot silently return:

1. ``manage.sh start_backend`` must run ``runserver --noreload`` by default
   (auto-reload only re-enabled via an explicit ``DJANGO_AUTORELOAD=1`` opt-in).
2. No production code path under ``backend/ai/`` may write to ``.py`` source
   files (the "self-modification" premise must never become real code).

These are pure-Python tests: no DB, no Django setup, no LLM.
"""
from __future__ import annotations

import re
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]  # .../backend
AI_DIR = Path(__file__).resolve().parents[1]       # .../backend/ai
REPO_ROOT = BACKEND_DIR.parent                      # .../carbon
MANAGE_SH = REPO_ROOT / "manage.sh"


def _start_backend_body() -> str:
    """Return the text of the ``start_backend()`` function in manage.sh."""
    src = MANAGE_SH.read_text(encoding="utf-8")
    m = re.search(r"^start_backend\(\)\s*\{(.*?)^\}", src, flags=re.M | re.S)
    assert m, "start_backend() not found in manage.sh"
    return m.group(1)


def test_start_backend_disables_autoreload_by_default():
    """NB-BP-006 — the dev server must NOT auto-reload on .py edits."""
    body = _start_backend_body()
    # The flag is set to --noreload unconditionally first...
    assert 'reload_flag="--noreload"' in body, (
        "start_backend() must default to --noreload to avoid the reload storm"
    )
    # ...and only cleared by an explicit opt-in.
    assert 'DJANGO_AUTORELOAD' in body, (
        "start_backend() must gate auto-reload behind DJANGO_AUTORELOAD=1"
    )
    # The runserver invocation must pass the flag through.
    assert re.search(
        r"runserver\s+\$reload_flag\s+0\.0\.0\.0:\$BACKEND_PORT", body
    ), "runserver must forward $reload_flag"


def test_start_backend_opt_in_still_possible():
    """Auto-reload must remain available for manual dev (DJANGO_AUTORELOAD=1)."""
    body = _start_backend_body()
    assert '[[ "${DJANGO_AUTORELOAD:-0}" == "1" ]]' in body, (
        "opting back into auto-reload must be an explicit DJANGO_AUTORELOAD=1"
    )
    assert 'reload_flag=""' in body, (
        "the opt-in branch must clear the --noreload flag"
    )


# ── No .py self-modification guard ────────────────────────────────────────

# A line is suspicious if it performs a *write* AND references a .py/.pyc path
# in the same statement. Reads (open 'r') and imports are intentionally ignored.
_WRITE_OPEN = re.compile(r"open\([^)]*?['\"](?:w|a|x)[b+]?['\"]")
_WRITE_TEXT = re.compile(r"\.(?:write_text|write_bytes)\(")
_PY_LITERAL = re.compile(r"['\"][^'\"]*\.pyc?['\"]")

_SKIP_DIRS = {"tests", "fixtures", "__pycache__", "migrations"}


def _source_files() -> list[Path]:
    return [
        p
        for p in AI_DIR.rglob("*.py")
        if not any(part in _SKIP_DIRS for part in p.relative_to(AI_DIR).parts[:-1])
    ]


def test_ai_engine_never_writes_py_source():
    """No production ``backend/ai/`` path may write a ``.py`` source file."""
    offenders: list[str] = []
    for path in _source_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if (_WRITE_OPEN.search(line) or _WRITE_TEXT.search(line)) and _PY_LITERAL.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
    assert not offenders, (
        "Forbidden .py-source write operations detected in backend/ai:\n"
        + "\n".join(offenders)
    )
