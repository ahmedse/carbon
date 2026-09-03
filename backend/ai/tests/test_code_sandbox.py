"""Phase I2-B — code execution sandbox tests.

Pure-Python (no DB, no Django setup): import :class:`~ai.code_sandbox.CodeSandbox`
directly and exercise the subprocess sandbox security + result contract.
"""
from __future__ import annotations

import base64

import pytest

from ai.code_sandbox import CodeSandbox


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
