"""``list_my_capabilities`` — capability-scoped "what can you do" inventory.

The assistant's self-description listing is grounded here, not in LLM prose:

    User: "What can you do?"
    Agent (list_my_capabilities tool):
      1. build the calling user's access manifest (apps, work areas, modules,
         page links) from their RBAC scope — capability-gated, never global
      2. return it machine-readably so the runtime can surface the page links
         as small ``navigate`` buttons under the reply (the existing
         ``actions`` channel)

Guardrails honored (non-negotiable):

  * **RULE_20** — zero upward imports: this module imports nothing from
    ``dq``/``catalog``/``mdm``/``emissions``/``accounts``/``core``.  The
    inventory is built by ``ai.access_manifest`` (host-side glue, same status
    as ``ai.host_executor``), which is the only module touching the ORM.
  * **RULE_21** — read-only: ``requires_confirmation=False``, nothing staged,
    nothing written.
  * **No-leak (UX audit)** — the returned inventory contains ONLY what the
    user can reach.  Apps, modules or work areas the user cannot access are
    never present, so neither the assistant text nor the rendered links can
    leak their existence.
"""
from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import sync_to_async

from ai.engine.agent.plugins import ToolPlugin

logger = logging.getLogger("carbon.ai.plugins.list_capabilities")


class ListCapabilities(ToolPlugin):
    name = "list_my_capabilities"
    description = (
        "List the work areas, apps and pages the current user can access. "
        "Returns the user's capability-scoped inventory with their page links. "
        "Use it when the user asks what you can do, what they can use, or what "
        "the platform offers them."
    )
    input_schema: dict[str, Any] = {"type": "object", "properties": {}}
    requires_confirmation = False
    # Read-only inventory tool — available to any authenticated chat user; the
    # content is scoped by the host RBAC, never by a blanket gate.
    capability: str | None = None
    app_identifier: str | None = None

    async def execute(self, args: dict, *, ctx) -> dict:
        if not ctx.host_user_id:
            return {
                "error": "No authenticated session — the capability list is unavailable.",
            }
        from ai.access_manifest import build_user_access_manifest

        manifest = await sync_to_async(build_user_access_manifest)(ctx.host_user_id)
        return {
            "requires_confirmation": False,
            "action": "list_capabilities",
            "apps": manifest["apps"],
            "capabilities": manifest["capabilities"],
            "modules": manifest["modules"],
            "routes": manifest["routes"],
        }
