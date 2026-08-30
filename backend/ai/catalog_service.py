"""
Unified Agent Catalog — backend CRUD + federated discovery (Phase W3-D).

Read-mostly catalog service over the engine's ``AgentRegistry`` (declared
handoff topology, ADR-001) plus the skill catalog (``Skill`` +
``SkillAdmissionLog``), with request-time federated discovery of registered
``ToolPlugin`` / ``WorkflowPlugin`` capabilities.

Design contracts (TASKS.md W3-D):

  * NO changes under ``backend/ai/engine/**`` — this module only *calls* the
    engine's public seams (``AgentRegistry``, the Store session factory, the
    plugin registry) and reads the engine models directly.
  * The DB is the source of truth; plugins are discovered read-only and
    *enrich* the payload — they can never shadow or replace a DB agent.
  * Reads are authenticated; writes are admin-gated (view layer, RULE_21 —
    registering/removing an agent is an explicit admin act).
  * Async engine seams are bridged with ``_run_async`` (from
    ``ai.plans_service``) so this service stays importable in sync Django
    view contexts; time is engine ``clock.utcnow()`` / ``timezone.now()``
    only (timestamps are read back verbatim, never ``datetime.now()``).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy import select

from ai.engine.core.models import (
    Agent,
    AgentHandoff,
    Skill,
    SkillAdmissionLog,
)
from ai.plans_service import PLAN_INSTANCE_ID, _run_async

logger = logging.getLogger("carbon.ai.catalog_service")


class AgentNotFoundError(Exception):
    """Raised when an agent id is unknown (or belongs to another instance)."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        super().__init__(f"Agent {agent_id} not found.")


class CatalogService:
    """Unified agent catalog: reads, topology, federated index, admin writes.

    Every public method is sync — it bridges one async engine operation via
    ``_run_async`` (module-level helper imported from ``ai.plans_service``).
    """

    def __init__(self, instance_id: str = PLAN_INSTANCE_ID):
        self.instance_id = instance_id

    # ── Public (sync) API ────────────────────────────────────────────────

    def list_agents(self, role: Optional[str] = None) -> list[dict]:
        """All agent roles for the instance with declared edges + skills."""
        return _run_async(self._async_list_agents(role=role))

    def get_agent(self, agent_id: str) -> dict:
        """One agent: metadata, handoffs, admitted skills, last admission log."""
        return _run_async(self._async_get_agent(agent_id))

    def topology(self) -> dict:
        """Declared graph (ADR-001): ``{"nodes": [...], "edges": [...]}``."""
        return _run_async(self._async_topology())

    def list_skills(self) -> list[dict]:
        """Skill catalog with each skill's latest admission-gate verdict."""
        return _run_async(self._async_list_skills())

    def register_agent(
        self,
        *,
        name: str,
        role: str,
        tool_set: Optional[list[str]] = None,
        playbook_blocks: Optional[list[str]] = None,
        model_override: Optional[str] = None,
        max_turns: int = 3,
    ) -> dict:
        """Insert or update an agent (engine ``register_agent``, admin-gated)."""
        return _run_async(
            self._async_register_agent(
                name=name,
                role=role,
                tool_set=tool_set,
                playbook_blocks=playbook_blocks,
                model_override=model_override,
                max_turns=max_turns,
            )
        )

    def update_agent(
        self,
        agent_id: str,
        *,
        role: Optional[str] = None,
        tool_set: Optional[list[str]] = None,
        playbook_blocks: Optional[list[str]] = None,
        model_override: Optional[str] = None,
        max_turns: Optional[int] = None,
    ) -> dict:
        """Update an agent in place (keeps name — the engine upsert key)."""
        return _run_async(
            self._async_update_agent(
                agent_id,
                role=role,
                tool_set=tool_set,
                playbook_blocks=playbook_blocks,
                model_override=model_override,
                max_turns=max_turns,
            )
        )

    def remove_agent(self, agent_id: str) -> dict:
        """Soft-delete an agent (engine ``remove_agent``, admin-gated)."""
        return _run_async(self._async_remove_agent(agent_id))

    def federated_index(self, role: Optional[str] = None) -> dict:
        """Request-time merge: DB agents (source of truth) + plugin discovery.

        Plugins are additive — a plugin name can never shadow a DB agent;
        they are surfaced in a separate ``plugins`` list.
        """
        agents = self.list_agents(role=role)
        return {
            "source": "federated",
            "db_is_source_of_truth": True,
            "agents": agents,
            "plugins": self._discover_plugins(),
        }

    # ── Async internals ──────────────────────────────────────────────────

    async def _async_list_agents(self, role: Optional[str]) -> list[dict]:
        from ai.engine.agent.registry import AgentRegistry
        from ai.engine.core.database import get_session_factory

        async with get_session_factory(self.instance_id)() as db:
            registry = AgentRegistry(db)
            agents = await registry.list_agents(self.instance_id, role=role)
            outgoing, incoming = await self._edge_maps(db, registry, agents)
            admitted = await self._admitted_skills(db)
            return [
                self._agent_to_dict(
                    agent,
                    outgoing.get(agent.id, []),
                    incoming.get(agent.id, []),
                    admitted,
                )
                for agent in agents
            ]

    async def _async_get_agent(self, agent_id: str) -> dict:
        from ai.engine.agent.registry import AgentRegistry
        from ai.engine.core.database import get_session_factory

        async with get_session_factory(self.instance_id)() as db:
            agent = await self._find_agent(db, agent_id)
            registry = AgentRegistry(db)
            outgoing, incoming = await self._handoffs_for(db, registry, agent.id)
            payload = self._agent_to_dict(
                agent, outgoing, incoming, await self._admitted_skills(db)
            )
            payload["last_admission_log"] = await self._last_admission(db)
            return payload

    async def _async_topology(self) -> dict:
        from ai.engine.agent.registry import AgentRegistry
        from ai.engine.core.database import get_session_factory

        async with get_session_factory(self.instance_id)() as db:
            registry = AgentRegistry(db)
            agents = await registry.list_agents(self.instance_id)
            agent_ids = {agent.id for agent in agents}
            nodes = [
                {
                    "id": agent.id,
                    "name": agent.name,
                    "role": agent.role,
                    "status": "active" if agent.is_active else "inactive",
                }
                for agent in agents
            ]
            result = await db.execute(select(AgentHandoff))
            edges = []
            for handoff in result.scalars().all():
                if (
                    handoff.from_agent_id in agent_ids
                    and handoff.to_agent_id in agent_ids
                ):
                    edges.append(
                        {
                            "from": handoff.from_agent_id,
                            "to": handoff.to_agent_id,
                            "description": handoff.description,
                            "max_parallel": handoff.max_parallel,
                        }
                    )
            return {"nodes": nodes, "edges": edges}

    async def _async_list_skills(self) -> list[dict]:
        from ai.engine.core.database import get_session_factory

        async with get_session_factory(self.instance_id)() as db:
            result = await db.execute(
                select(Skill)
                .where(Skill.instance_id == self.instance_id)
                .order_by(Skill.created_at.asc())
            )
            out = []
            for skill in result.scalars().all():
                log = await self._last_admission_for(db, skill.id)
                out.append(self._skill_to_dict(skill, log))
            return out

    async def _async_register_agent(
        self,
        *,
        name: str,
        role: str,
        tool_set: Optional[list[str]],
        playbook_blocks: Optional[list[str]],
        model_override: Optional[str],
        max_turns: int,
    ) -> dict:
        from ai.engine.agent.registry import AgentRegistry
        from ai.engine.core.database import get_session_factory

        async with get_session_factory(self.instance_id)() as db:
            registry = AgentRegistry(db)
            agent = await registry.register_agent(
                self.instance_id,
                name,
                role,
                tool_set=tool_set,
                playbook_blocks=playbook_blocks,
                model_override=model_override,
                max_turns=max_turns,
            )
            admitted = await self._admitted_skills(db)
            return self._agent_to_dict(agent, [], [], admitted)

    async def _async_update_agent(
        self,
        agent_id: str,
        *,
        role: Optional[str],
        tool_set: Optional[list[str]],
        playbook_blocks: Optional[list[str]],
        model_override: Optional[str],
        max_turns: Optional[int],
    ) -> dict:
        from ai.engine.agent.registry import AgentRegistry
        from ai.engine.core.database import get_session_factory

        async with get_session_factory(self.instance_id)() as db:
            agent = await self._find_agent(db, agent_id)
            registry = AgentRegistry(db)
            updated = await registry.register_agent(
                self.instance_id,
                agent.name,  # name is the engine upsert key — immutable on PATCH
                role if role is not None else agent.role,
                tool_set=(
                    tool_set
                    if tool_set is not None
                    else self._parse_json(agent.tool_set_json, None)
                ),
                playbook_blocks=(
                    playbook_blocks
                    if playbook_blocks is not None
                    else self._parse_json(agent.playbook_blocks_json, None)
                ),
                model_override=(
                    model_override
                    if model_override is not None
                    else agent.model_override
                ),
                max_turns=max_turns if max_turns is not None else agent.max_turns,
            )
            outgoing, incoming = await self._handoffs_for(db, registry, updated.id)
            admitted = await self._admitted_skills(db)
            return self._agent_to_dict(updated, outgoing, incoming, admitted)

    async def _async_remove_agent(self, agent_id: str) -> dict:
        from ai.engine.agent.registry import AgentRegistry
        from ai.engine.core.database import get_session_factory

        async with get_session_factory(self.instance_id)() as db:
            agent = await self._find_agent(db, agent_id)
            registry = AgentRegistry(db)
            await registry.remove_agent(agent.id)
            return {"id": agent_id, "deleted": True}

    # ── Query helpers ────────────────────────────────────────────────────

    async def _find_agent(self, db, agent_id: str):
        """Fetch an agent by id, scoped to this instance (or 404)."""
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
        if agent is None or agent.instance_id != self.instance_id:
            raise AgentNotFoundError(agent_id)
        return agent

    async def _edge_maps(self, db, registry, agents):
        """Per-agent incoming/outgoing handoff maps for the list payload."""
        outgoing: dict[str, list[dict]] = {}
        incoming: dict[str, list[dict]] = {}
        for agent in agents:
            out, inn = await self._handoffs_for(db, registry, agent.id)
            outgoing[agent.id] = out
            incoming[agent.id] = inn
        return outgoing, incoming

    async def _handoffs_for(self, db, registry, agent_id: str):
        """Declared edges touching ``agent_id``: outgoing + incoming."""
        workers = await registry.get_workers_for(agent_id)
        outgoing = [
            {
                "to_agent_id": handoff.to_agent_id,
                "description": handoff.description,
                "max_parallel": handoff.max_parallel,
            }
            for _worker, handoff in workers
        ]
        result = await db.execute(
            select(AgentHandoff).where(AgentHandoff.to_agent_id == agent_id)
        )
        incoming = [
            {
                "from_agent_id": handoff.from_agent_id,
                "description": handoff.description,
                "max_parallel": handoff.max_parallel,
            }
            for handoff in result.scalars().all()
        ]
        return outgoing, incoming

    async def _admitted_skills(self, db) -> list[dict]:
        """Instance skills whose latest admission-gate verdict is 'admitted'."""
        result = await db.execute(
            select(Skill).where(Skill.instance_id == self.instance_id)
        )
        out: list[dict] = []
        for skill in result.scalars().all():
            log = await self._last_admission_for(db, skill.id)
            if log is not None and log.verdict == "admitted":
                out.append(self._skill_to_dict(skill, log))
        return out

    async def _last_admission_for(self, db, skill_id: str):
        result = await db.execute(
            select(SkillAdmissionLog)
            .where(SkillAdmissionLog.skill_id == skill_id)
            .order_by(SkillAdmissionLog.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def _last_admission(self, db):
        """Most recent admission-gate evaluation in this instance."""
        result = await db.execute(
            select(SkillAdmissionLog)
            .where(SkillAdmissionLog.instance_id == self.instance_id)
            .order_by(SkillAdmissionLog.created_at.desc())
            .limit(1)
        )
        log = result.scalars().first()
        return self._admission_to_dict(log) if log is not None else None

    # ── Serializers ──────────────────────────────────────────────────────

    def _agent_to_dict(
        self,
        agent: Any,
        outgoing: list[dict],
        incoming: list[dict],
        skills: list[dict],
    ) -> dict:
        return {
            "id": agent.id,
            "instance_id": agent.instance_id,
            "name": agent.name,
            "role": agent.role,
            "tool_set": self._parse_json(agent.tool_set_json, []),
            "playbook_blocks": self._parse_json(agent.playbook_blocks_json, []),
            "model_override": agent.model_override,
            "max_turns": agent.max_turns,
            "is_active": bool(agent.is_active),
            "created_at": self._iso(agent.created_at),
            "updated_at": self._iso(agent.updated_at),
            "outgoing_handoffs": outgoing,
            "incoming_handoffs": incoming,
            "skills": skills,
        }

    def _skill_to_dict(self, skill: Any, last_log: Any) -> dict:
        return {
            "id": skill.id,
            "instance_id": skill.instance_id,
            "name": skill.name,
            "description": skill.description,
            "kind": skill.kind,
            "status": skill.status,
            "author_user_id": skill.author_user_id,
            "usage_count": skill.usage_count,
            "success_rate": skill.success_rate,
            "avg_latency_ms": skill.avg_latency_ms,
            "last_executed_at": self._iso(skill.last_executed_at),
            "signature": self._parse_json(skill.signature, {}),
            "promoted_at": self._iso(skill.promoted_at),
            "promoted_by": skill.promoted_by,
            "created_at": self._iso(skill.created_at),
            "updated_at": self._iso(skill.updated_at),
            "admission": (
                self._admission_to_dict(last_log) if last_log is not None else None
            ),
        }

    def _admission_to_dict(self, log: Any) -> dict:
        return {
            "verdict": log.verdict,
            "structural_passed": bool(log.structural_passed),
            "harmlessness_passed": bool(log.harmlessness_passed),
            "consistency_passed": bool(log.consistency_passed),
            "marginal_gain_passed": bool(log.marginal_gain_passed),
            "rejected_by": log.rejected_by,
            "admitted_by": log.admitted_by,
            "created_at": self._iso(log.created_at),
        }

    # ── Plugin discovery (read-only, additive) ───────────────────────────

    def _discover_plugins(self) -> list[dict]:
        from ai.engine.agent.plugins import WorkflowPlugin, registered_plugins

        plugins: list[dict] = []
        for plugin in registered_plugins():
            plugins.append(
                {
                    "name": plugin.name,
                    "description": plugin.description,
                    "input_schema": plugin.input_schema,
                    "requires_confirmation": plugin.requires_confirmation,
                    "capability": plugin.capability,
                    "app_identifier": plugin.app_identifier,
                    "kind": "workflow" if isinstance(plugin, WorkflowPlugin) else "tool",
                }
            )
        return plugins

    # ── Value helpers ────────────────────────────────────────────────────

    @staticmethod
    def _parse_json(value: Any, default: Any):
        """Tolerate both storage shapes: JSON string (engine seam dumps) and
        already-deserialized list/dict (Django JSONField mirror)."""
        if value is None:
            return default
        if isinstance(value, (list, dict)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (ValueError, TypeError):
                return default
        return default

    @staticmethod
    def _iso(value: Any) -> Optional[str]:
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except (ValueError, TypeError):
                return str(value)
        return value
