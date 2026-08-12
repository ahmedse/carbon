"""
AgentRegistry — manages agent definitions and handoff topology per instance.

An agent is a **role**, not a process.  Handoffs are **declared edges** only
(ADR-001: no LangGraph, no free-form agent chat).  The developer owns the
edges; agents own the routing.

Usage::

    registry = AgentRegistry(db_session)
    orchestrator = await registry.get_agent(instance_id, "orchestrator")
    allowed = await registry.can_handoff(orchestrator.id, researcher.id)
    workers = await registry.get_workers_for(orchestrator.id)
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy import select

from ai.engine.core.models import AGENT_ROLES, Agent, AgentHandoff

logger = logging.getLogger("pulse.agent.registry")


class AgentRegistry:
    """Database-backed catalog of agent roles + declared handoff edges.

    All methods are async.  Writes follow the repo convention (HR-5):
    mutate on the session, then ``await self.db.commit()``.
    """

    def __init__(self, db_session):
        self.db = db_session

    # ── Agents ──────────────────────────────────────────────────────────────

    async def register_agent(
        self,
        instance_id: str,
        name: str,
        role: str,
        tool_set: Optional[list[str]] = None,
        playbook_blocks: Optional[list[str]] = None,
        model_override: Optional[str] = None,
        max_turns: int = 3,
    ) -> Agent:
        """Insert or update an agent (keyed by instance_id + name)."""
        if role not in AGENT_ROLES:
            raise ValueError(
                f"Invalid agent role {role!r}; must be one of {sorted(AGENT_ROLES)}"
            )

        tool_set_json = json.dumps(tool_set) if tool_set is not None else None
        blocks_json = json.dumps(playbook_blocks) if playbook_blocks is not None else None

        stmt = select(Agent).where(
            Agent.instance_id == instance_id,
            Agent.name == name,
        )
        result = await self.db.execute(stmt)
        agent = result.scalar_one_or_none()

        if agent is None:
            agent = Agent(
                instance_id=instance_id,
                name=name,
                role=role,
                tool_set_json=tool_set_json,
                playbook_blocks_json=blocks_json,
                model_override=model_override,
                max_turns=max_turns,
                is_active=True,
            )
            self.db.add(agent)
        else:
            agent.role = role
            agent.tool_set_json = tool_set_json
            agent.playbook_blocks_json = blocks_json
            agent.model_override = model_override
            agent.max_turns = max_turns
            agent.is_active = True

        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def get_agent(self, instance_id: str, name_or_role: str) -> Optional[Agent]:
        """Look up by name first, then by role (returns first active)."""
        stmt = select(Agent).where(
            Agent.instance_id == instance_id,
            Agent.name == name_or_role,
            Agent.is_active.is_(True),
        )
        result = await self.db.execute(stmt)
        agent = result.scalar_one_or_none()
        if agent is not None:
            return agent

        stmt = select(Agent).where(
            Agent.instance_id == instance_id,
            Agent.role == name_or_role,
            Agent.is_active.is_(True),
        ).order_by(Agent.created_at.asc())
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list_agents(self, instance_id: str, role: Optional[str] = None) -> list[Agent]:
        """All agents for an instance, optionally filtered by role."""
        stmt = select(Agent).where(Agent.instance_id == instance_id)
        if role is not None:
            stmt = stmt.where(Agent.role == role)
        stmt = stmt.order_by(Agent.created_at.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def remove_agent(self, agent_id: str) -> None:
        """Soft-delete an agent (is_active=False); the row stays in the DB."""
        stmt = select(Agent).where(Agent.id == agent_id)
        result = await self.db.execute(stmt)
        agent = result.scalar_one_or_none()
        if agent is not None:
            agent.is_active = False
            await self.db.commit()

    # ── Handoffs ────────────────────────────────────────────────────────────

    async def add_handoff(
        self,
        from_agent_id: str,
        to_agent_id: str,
        description: Optional[str] = None,
        max_parallel: int = 1,
    ) -> Optional[AgentHandoff]:
        """Declare a valid handoff edge.  Idempotent — skips if the pair exists."""
        stmt = select(AgentHandoff).where(
            AgentHandoff.from_agent_id == from_agent_id,
            AgentHandoff.to_agent_id == to_agent_id,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        edge = AgentHandoff(
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            description=description,
            max_parallel=max_parallel,
        )
        self.db.add(edge)
        await self.db.commit()
        return edge

    async def can_handoff(self, from_agent_id: str, to_agent_id: str) -> bool:
        """True iff an explicit edge from_agent_id → to_agent_id exists.

        The orchestrator may always hand off to itself (internal handoff is
        implicit); every other handoff must be declared.
        """
        if from_agent_id == to_agent_id:
            stmt = select(Agent).where(Agent.id == from_agent_id)
            result = await self.db.execute(stmt)
            agent = result.scalar_one_or_none()
            return agent is not None and agent.role == "orchestrator"

        stmt = select(AgentHandoff.id).where(
            AgentHandoff.from_agent_id == from_agent_id,
            AgentHandoff.to_agent_id == to_agent_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_workers_for(self, agent_id: str) -> list[tuple[Agent, AgentHandoff]]:
        """All active agents this agent can delegate to, with handoff metadata."""
        stmt = (
            select(Agent, AgentHandoff)
            .join(AgentHandoff, AgentHandoff.to_agent_id == Agent.id)
            .where(
                AgentHandoff.from_agent_id == agent_id,
                Agent.is_active.is_(True),
            )
            .order_by(Agent.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return [(agent, handoff) for agent, handoff in result.all()]

    # ── Default topology ────────────────────────────────────────────────────

    async def seed_defaults(self, instance_id: str) -> list[Agent]:
        """Create the 5 default agents + 7 declared handoff edges (idempotent)."""
        defaults = [
            # (name, role, tool_set, max_turns)
            ("orchestrator", "orchestrator", ["search_knowledge", "get_entity_details"], 5),
            ("researcher", "researcher", ["search_knowledge", "get_entity_details", "call_host_api"], 3),
            ("planner", "planner", ["search_knowledge", "get_entity_details"], 2),
            ("critic", "critic", [], 1),
            ("domain_expert", "domain_specialist", ["search_knowledge", "get_entity_details", "call_host_api"], 3),
        ]

        agents: dict[str, Agent] = {}
        for name, role, tool_set, max_turns in defaults:
            agent = await self.register_agent(
                instance_id=instance_id,
                name=name,
                role=role,
                tool_set=tool_set,
                max_turns=max_turns,
            )
            agents[name] = agent

        # Declared edges: (from_name, to_name, max_parallel, description)
        edges = [
            ("orchestrator", "researcher", 3, "decompose read-heavy research subtasks"),
            ("orchestrator", "planner", 1, "decompose complex questions into plans"),
            ("orchestrator", "domain_expert", 2, "instance-specific expert queries"),
            ("researcher", "orchestrator", 1, "return findings to the orchestrator"),
            ("planner", "orchestrator", 1, "return plan to the orchestrator"),
            ("critic", "orchestrator", 1, "return review verdict to the orchestrator"),
            ("domain_expert", "orchestrator", 1, "return expert answer to the orchestrator"),
        ]
        for from_name, to_name, max_parallel, desc in edges:
            await self.add_handoff(
                from_agent_id=agents[from_name].id,
                to_agent_id=agents[to_name].id,
                description=desc,
                max_parallel=max_parallel,
            )

        return list(agents.values())
