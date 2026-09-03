"""``code_sandbox`` — subprocess code execution for the Pulse data-analysis tool.

Phase I2-B: a NEW, subprocess-based sandbox for running user/LLM-written
Python/pandas/matplotlib code over a pre-fetched result set.  This is distinct
from the in-process ``RestrictedPython`` sandbox in ``ai.engine.skills.sandbox``
(``SafeExecutor``): RestrictedPython cannot import third-party packages like
pandas/matplotlib/numpy, which is exactly what data analysis requires.

Mechanism (non-negotiables honored):

  * **Never in the Django process.**  Code runs in a fresh ``sys.executable -I``
    subprocess (isolated: no ``PYTHONPATH``, no user site; site-packages still
    load so pandas/matplotlib/numpy import fine).
  * **Never DB credentials.**  The only input is ``data`` passed over stdin;
    the child gets no DB connection, no host API token, no network.
  * **OS-level restrictions** via ``sys.addaudithook``: blocks network
    (``socket.connect``/``socket.getaddrinfo``/``socket.bind``), file-write
    (``open`` with a ``w``/``a``/``x``/``+`` mode), and subprocess spawn
    (``os.system``/``subprocess.Popen``/``os.exec*``/``os.spawn*``).
  * **Fail-visible.**  Timeouts and sandbox crashes return ``{"error": ...}``;
    the exception never propagates into the caller.

The result is emitted as a single sentinel-delimited JSON line on the child's
real stdout (user ``print()`` output is captured into ``stdout`` via
``contextlib.redirect_stdout``, so the sentinel line parses cleanly even if a
C extension writes directly to stdout).
"""
from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

#: Prefix of the single result line the child emits on stdout.
_SENTINEL = "__PULSE_SANDBOX_RESULT__"

# ── WRAPPER (executed in the child) ────────────────────────────────────────

_PRELUDE = r'''
import base64
import contextlib
import io
import json
import sys
import traceback

# Trusted imports happen BEFORE the audit hook so matplotlib's harmless
# font-cache write can complete; the hook then restricts user code only.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

try:
    # Pre-warm the font manager so no cache write is attempted after the
    # audit hook (which blocks all file writes) is installed.
    from matplotlib import font_manager as _font_manager
    _font_manager._load_fontmanager()
except Exception:
    pass


def _json_default(obj):
    try:
        import numpy as np
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except ImportError:
        pass
    if hasattr(obj, "isoformat"):
        try:
            return obj.isoformat()
        except Exception:
            pass
    return str(obj)


def _audit_hook(event, args):
    if event in ("socket.connect", "socket.getaddrinfo", "socket.bind"):
        raise PermissionError("network access blocked in sandbox (%s)" % event)
    if event == "open":
        mode = args[1] if len(args) > 1 else None
        if isinstance(mode, str) and any(c in mode for c in "wax+"):
            raise PermissionError("file write blocked in sandbox (mode=%r)" % mode)
    if event in (
        "os.system",
        "subprocess.Popen",
        "os.exec",
        "os.spawn",
        "os.posix_spawn",
        "os.fork",
        "os.forkpty",
    ):
        raise PermissionError("subprocess spawning blocked in sandbox (%s)" % event)


sys.addaudithook(_audit_hook)

_raw = sys.stdin.read()
try:
    data = json.loads(_raw) if _raw.strip() else {}
except Exception:
    data = {}

_namespace = {"data": data, "pd": pd, "plt": plt}
'''

_POSTAMBLE = r'''
_stdout_buf = io.StringIO()
_error = None
try:
    with contextlib.redirect_stdout(_stdout_buf):
        exec(user_code, _namespace)
except BaseException:
    _error = traceback.format_exc()

_image_b64 = None
try:
    if plt.get_fignums():
        _buf = io.BytesIO()
        plt.savefig(_buf, format="png")
        _image_b64 = base64.b64encode(_buf.getvalue()).decode("ascii")
        _buf.close()
except Exception:
    _image_b64 = None

_table_rows = None
_result = None
if "result" in _namespace:
    _r = _namespace["result"]
    if _r is not None:
        if isinstance(_r, pd.DataFrame):
            _table_rows = _r.to_dict(orient="records")
        elif isinstance(_r, list) and all(isinstance(x, dict) for x in _r):
            _table_rows = _r
        else:
            _result = _r

_payload = {
    "stdout": _stdout_buf.getvalue(),
    "error": _error,
    "image_b64": _image_b64,
    "table_rows": _table_rows,
    "result": _result,
}

sys.stdout.write("@@SENTINEL@@" + json.dumps(_payload, default=_json_default) + "\n")
sys.stdout.flush()
'''


def _build_wrapper(code: str) -> str:
    """Assemble the child program, injecting user code as a safe string literal."""
    postamble = _POSTAMBLE.replace("@@SENTINEL@@", _SENTINEL)
    return _PRELUDE + "\nuser_code = " + repr(code) + "\n" + postamble


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def _parse_result(stdout: str) -> dict | None:
    """Find and decode the sentinel-delimited result line from child stdout."""
    for line in (stdout or "").splitlines():
        if line.startswith(_SENTINEL):
            raw = line[len(_SENTINEL):].strip()
            if not raw:
                return None
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return None
            if not isinstance(parsed, dict):
                return None
            return {
                "stdout": parsed.get("stdout", ""),
                "error": parsed.get("error"),
                "image_b64": parsed.get("image_b64"),
                "table_rows": parsed.get("table_rows"),
                "result": parsed.get("result"),
            }
    return None


class CodeSandbox:
    """Subprocess code sandbox.  Never raises; always returns a result dict."""

    TIMEOUT = 10.0

    @classmethod
    def execute(cls, code: str, data: dict | None = None) -> dict:
        if not isinstance(code, str):
            return {
                "stdout": "",
                "error": "code must be a string",
                "image_b64": None,
                "table_rows": None,
                "result": None,
            }

        data = data or {}
        wrapper = _build_wrapper(code)

        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-c", wrapper],
                input=json.dumps(data, default=str),
                capture_output=True,
                text=True,
                timeout=cls.TIMEOUT,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "stdout": _to_text(getattr(exc, "stdout", None)),
                "error": "Code execution timed out (10s limit).",
                "image_b64": None,
                "table_rows": None,
                "result": None,
            }
        except Exception as exc:  # pragma: no cover - defensive
            return {
                "stdout": "",
                "error": f"Sandbox failed to launch: {exc}",
                "image_b64": None,
                "table_rows": None,
                "result": None,
            }

        stdout = _to_text(proc.stdout)
        payload = _parse_result(stdout)
        if payload is None:
            stderr = _to_text(proc.stderr).strip()
            detail = stderr[-500:] if stderr else f"exit code {proc.returncode}"
            return {
                "stdout": stdout,
                "error": f"Sandbox produced no result ({detail})",
                "image_b64": None,
                "table_rows": None,
                "result": None,
            }
        return payload
