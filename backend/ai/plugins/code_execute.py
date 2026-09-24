"""``code_execute`` — the ``code_execute`` tool: run code over a result set.

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
    name = "code_execute"
    description = (
        "Run Python/pandas code over a provided result set and return a table, "
        "scalar, or PNG chart. Read-only sandbox: no network, no disk writes, "
        "no subprocess. Prefer this ONLY for multi-step pandas analysis, or to "
        "embed PNG figures into export_document (Word/PDF pack). Do NOT use it "
        "to draw a chart for the screen: host rows shaped as category → measure "
        "already render as interactive charts from the answer envelope. When "
        "you must plot for an export, use plt (auto-captured); do NOT call "
        "savefig to a path. Assign the final answer to `result`."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": (
                    "Python code to run. Use `data` (dict/list), `pd`, and `plt`. "
                    "Do not open files or savefig to a path — figures are "
                    "auto-captured. Assign the final answer to `result` "
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
        "I can run Python/pandas analysis over a result set; PNG charts are "
        "for document export — on-screen charts use the answer envelope."
    )

    async def execute(self, args: dict, *, ctx) -> dict:
        code = args.get("code") or ""
        data = args.get("data") or {}
        try:
            result = CodeSandbox.execute(code, data)
        except Exception as exc:  # fail-visible, never raise into the turn
            logger.warning("code_execute failed: %s", exc)
            return {"error": str(exc), "code": code}
        # I2-F — thread the executed source back so the frontend "Code used"
        # disclosure can show WHAT ran (not just its stdout). Additive to the
        # sandbox shape; the code_result consumer ignores unknown keys.
        return {**result, "code": code}
