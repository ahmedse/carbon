"""``code_execute`` — ``code.execute`` tool: run code over a result set.

Phase I2-B.  Exposes the subprocess :class:`~ai.code_sandbox.CodeSandbox` to the
agent as a read-only named tool.

Guardrails honored (non-negotiable):

  * **RULE_20** — zero upward imports: only stdlib + the plugin base
    (``ai.engine.agent.plugins``) + ``ai.code_sandbox`` (a sibling, also
    stdlib-only).  Nothing from ``dq``/``catalog``/``mdm``/``emissions``/
    ``accounts``/``core``.
  * **RULE_21** — read-only: ``requires_confirmation=False``.  The code runs in
    a network/file-write/subprocess-blocked subprocess; nothing is staged.
  * **Fail-visible** — ``execute`` never raises; sandbox failures return
    ``{"error": ...}``.
"""
from __future__ import annotations

import logging
from typing import Any

from ai.code_sandbox import CodeSandbox
from ai.engine.agent.plugins import ToolPlugin

logger = logging.getLogger("carbon.ai.plugins.code_execute")


class CodeExecuteTool(ToolPlugin):
    name = "code.execute"
    description = (
        "Run Python/pandas/matplotlib code over a provided result set and "
        "return a chart image, a table, or a scalar. Read-only. Assign the "
        "final answer to `result` (a DataFrame for a table, or a scalar)."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": (
                    "Python code to run. Assign the final answer to `result` "
                    "(a DataFrame for a table, or a scalar)."
                ),
            },
            "data": {
                "type": "object",
                "description": "JSON result set exposed as the `data` variable.",
            },
        },
        "required": ["code"],
    }
    requires_confirmation = False
    capability: str | None = "ai:code_execute"
    app_identifier: str | None = None
    chat_visible = True
    capability_claim = (
        "I can run Python/pandas code over a result set to compute tables and charts."
    )

    async def execute(self, args: dict, *, ctx) -> dict:
        code = args.get("code") or ""
        data = args.get("data") or {}
        try:
            return CodeSandbox.execute(code, data)
        except Exception as exc:  # fail-visible, never raise into the turn
            logger.warning("code.execute failed: %s", exc)
            return {"error": str(exc)}
