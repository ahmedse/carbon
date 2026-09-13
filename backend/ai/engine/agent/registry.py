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

from ai.engine.core.models import AGENT_ROLES, Agent, AgentHandoff
from ai.engine.core.query import first

logger = logging.getLogger("pulse.agent.registry")


def _dt_key(value):
    """Sort key for datetimes (None-safe)."""
    if value is None:
        return 0
    try:
        return value.timestamp()
    except AttributeError:
        return 0


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

        agent = first(
            await self.db.select(
                Agent,
                ("instance_id", instance_id),
                ("name", name),
            )
        )

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
        agent = first(
            await self.db.select(
                Agent,
                ("instance_id", instance_id),
                ("name", name_or_role),
                ("is_active", True),
            )
        )
        if agent is not None:
            return agent

        rows = await self.db.select(
            Agent,
            ("instance_id", instance_id),
            ("role", name_or_role),
            ("is_active", True),
        )
        rows.sort(key=lambda a: _dt_key(a.created_at))
        return rows[0] if rows else None

    async def list_agents(self, instance_id: str, role: Optional[str] = None) -> list[Agent]:
        """All agents for an instance, optionally filtered by role."""
        filters: list = [("instance_id", instance_id)]
        if role is not None:
            filters.append(("role", role))
        rows = await self.db.select(Agent, *filters)
        rows.sort(key=lambda a: _dt_key(a.created_at))
        return rows

    async def remove_agent(self, agent_id: str) -> None:
        """Soft-delete an agent (is_active=False); the row stays in the DB."""
        agent = first(await self.db.select(Agent, ("id", agent_id)))
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
        existing = first(
            await self.db.select(
                AgentHandoff,
                ("from_agent_id", from_agent_id),
                ("to_agent_id", to_agent_id),
            )
        )
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
            agent = first(await self.db.select(Agent, ("id", from_agent_id)))
            return agent is not None and agent.role == "orchestrator"

        handoff = first(
            await self.db.select(
                AgentHandoff,
                ("from_agent_id", from_agent_id),
                ("to_agent_id", to_agent_id),
            )
        )
        return handoff is not None

    async def get_workers_for(self, agent_id: str) -> list[tuple[Agent, AgentHandoff]]:
        """All active agents this agent can delegate to, with handoff metadata."""
        handoffs = await self.db.select(
            AgentHandoff,
            ("from_agent_id", agent_id),
        )
        if not handoffs:
            return []

        agents = await self.db.select(
            Agent,
            ("id__in", [h.to_agent_id for h in handoffs]),
            ("is_active", True),
        )
        agents.sort(key=lambda a: _dt_key(a.created_at))
        handoff_by_to = {h.to_agent_id: h for h in handoffs}
        return [
            (agent, handoff_by_to[agent.id])
            for agent in agents
            if agent.id in handoff_by_to
        ]

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
