---
name: ops-canvas-job-map
description: Emit Ops Canvas Job Map / Chat Job Brief boards (ADR-0041) for multi-hop ops work
allowed_tools: []
when_to_use: [job map, ops canvas, task map, what this requires, plan review, multi-hop briefing]
---

# Skill: Ops Canvas / Job Map (ADR-0041)

## Trigger
Use when the user asks for a **job map**, **task map**, **ops canvas**, what a
task requires, multi-hop synthesis, Agent plan review, or ops briefing on a
record. Do **not** open a canvas for short single-tool lookups.

## Layout (closed kit — never free HTML)
Emit / upsert `artifact_type=job_map` with five layers:

1. **Intent** — ask, success criteria, Chat advisory vs Agent contract
2. **Job map** — steps, deps, tools, CBAC capabilities, entities
3. **Live run** — progress, FlightDirector QoS, blockers, consent (Agent only)
4. **Evidence** — envelope headline/tables/sources/caveats
5. **Outcome** — summary, SoR links, canvas id

## API
- `POST /carbon-api/ai/workspace/artifacts/job-maps/`
- Shelf: Pulse workspace → Artifacts panel (Ops Canvas)
- Share: `POST …/artifacts/{id}/share/` (owner or `ai:manage_console`)
- Record attach: filter `?artifact_type=job_map&related_type=&related_id=`

## Modes
- Chat → Job Brief (read-only)
- Agent → Job Map (runnable under RULE_21)
