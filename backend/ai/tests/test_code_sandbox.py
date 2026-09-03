"""Phase I2-B — code execution sandbox tests.

Pure-Python (no DB, no Django setup): import :class:`~ai.code_sandbox.CodeSandbox`
directly and exercise the subprocess sandbox security + result contract.
"""
from __future__ import annotations

import asyncio
import base64
import json

import pytest

from ai.code_sandbox import CodeSandbox
from ai.engine_runtime import _build_code_result
from ai.plugins.code_execute import CodeExecuteTool


def test_code_execute_threads_code_into_result():
    """I2-F — the tool returns the executed source as ``code`` alongside the
    sandbox result so the frontend "Code used" disclosure can show what ran."""
    code = "result = 1 + 1"
    result = asyncio.run(CodeExecuteTool().execute({"code": code, "data": {}}, ctx=None))
    assert result["code"] == code
    assert result["error"] is None
    assert result["result"] == 2


def test_pandas_result_becomes_table():
    result = CodeSandbox.execute(
        "import pandas as pd; result = pd.DataFrame({'a': [1, 2]})",
        {},
    )
    assert result["error"] is None
    assert result["table_rows"] == [{"a": 1}, {"a": 2}]
    assert result["result"] is None


def test_timeout(monkeypatch):
    monkeypatch.setattr(CodeSandbox, "TIMEOUT", 1)
    result = CodeSandbox.execute("import time; time.sleep(30)", {})
    assert result["error"] is not None
    assert "timed out" in result["error"].lower()


def test_os_system_blocked():
    result = CodeSandbox.execute("import os; os.system('echo hi')", {})
    assert result["error"] is not None
    lowered = result["error"].lower()
    assert "blocked" in lowered or "permissionerror" in lowered


def test_network_blocked():
    result = CodeSandbox.execute(
        "import urllib.request; urllib.request.urlopen('http://example.com')",
        {},
    )
    assert result["error"] is not None
    lowered = result["error"].lower()
    assert "blocked" in lowered or "permissionerror" in lowered


def test_file_write_blocked():
    result = CodeSandbox.execute(
        "open('/tmp/pulse_should_not_write.txt', 'w').write('x')",
        {},
    )
    assert result["error"] is not None
    lowered = result["error"].lower()
    assert "blocked" in lowered or "permissionerror" in lowered


def test_matplotlib_image():
    result = CodeSandbox.execute(
        "import matplotlib.pyplot as plt; plt.plot([1, 2, 3]); result = None",
        {},
    )
    assert result["error"] is None
    assert result["image_b64"]
    png_bytes = base64.b64decode(result["image_b64"])
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


# ── _build_code_result extraction (Wave I2-F) ───────────────────────────

def test_build_code_result_extracts_code_execute():
    payload = {
        "stdout": "",
        "error": None,
        "image_b64": "abc",
        "table_rows": None,
        "result": None,
    }
    completed = [{"tool_name": "code.execute", "result": json.dumps(payload)}]
    assert _build_code_result(completed) == payload


def test_build_code_result_ignores_non_code_tools():
    completed = [
        {"tool_name": "call_host_api", "result": json.dumps({"ok": True})},
    ]
    assert _build_code_result(completed) is None


def test_build_code_result_surfaces_promoted_error():
    # ExecuteWitness "nested-error promotion": the inner sandbox error is
    # lifted to ``item["error"]`` while the FULL sandbox dict (with its own
    # ``error`` key) is preserved in ``item["result"]``. The frontend needs
    # this dict to render the friendly error state.
    payload = {
        "stdout": "",
        "error": "NameError: name 'x' is not defined",
        "image_b64": None,
        "table_rows": None,
        "result": None,
    }
    completed = [
        {
            "tool_name": "code.execute",
            "error": payload["error"],
            "result": json.dumps(payload),
        },
    ]
    assert _build_code_result(completed) == payload


def test_build_code_result_skips_guardrail_cancel():
    # Guardrail-cancelled code.execute has ``result: None`` — no sandbox dict,
    # so no code_result (nothing to render).
    completed = [
        {
            "tool_name": "code.execute",
            "error": "Tool cancelled by guardrail: policy",
            "result": None,
        },
    ]
    assert _build_code_result(completed) is None


def test_build_code_result_skips_non_sandbox_shape():
    completed = [
        {"tool_name": "code.execute", "result": json.dumps({"requires_confirmation": True})},
    ]
    assert _build_code_result(completed) is None


def test_build_code_result_returns_none_when_absent():
    assert _build_code_result([]) is None
