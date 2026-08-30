# Carbon Data Trust Platform — Documentation Index

Enterprise carbon emissions management platform. Django 5.2 + DRF 3.16 backend (port 8009), React 19 + Vite + MUI 7.1 frontend (port 5179).

> Single source of truth for task/phase status lives in the repo-root [`TASKS.md`](../TASKS.md). Architecture decisions live in [`.ai-toolkit/decisions/`](../.ai-toolkit/decisions/).

---

## Architecture & Design

- [Design — Platform](./DESIGN-PLATFORM.md) — platform architecture (canonical)
- [Design — AI Workspace V4](./DESIGN_AI_WORKSPACE_V4.md) — AI workspace (current implementation target)
- [Design — AI Workspace NextGen](./DESIGN_AI_WORKSPACE_NEXTGEN.md) — AI shell target architecture (reference)
- [Design — AI Workstation](./DESIGN_AI_WORKSTATION.md)
- [Design — Agent Catalog](./DESIGN-AGENT-CATALOG.md)
- [Design — Agent Execution Control & Scheduling](./DESIGN-AGENT-EXECUTION-CONTROL.md) — W6 findings F-26/F-28/F-29 (multi-agent, mid-execution edits, scheduling)
- [Design — Domain Apps Expansion](./DESIGN-DOMAIN-APPS-EXPANSION.md)
- [Storage Pattern — Hosted Apps](./STORAGE-PATTERN-HOSTED-APPS.md) — typed tables for owned data, `dataschema` for governed measurements (ADR 0025)
- [Design — Export (Rich)](./DESIGN-EXPORT-RICH.md)
- [Design — Adaptive Learning DQ Core](./DESIGN-ADAPTIVE-LEARNING-DQ-CORE.md) (proposal)

## Operations & Deployment

- [Deployment](./deployment.md)
- [Security & Deployment](./SECURITY_DEPLOYMENT.md)
- [Quickstart Deployment](./QUICKSTART_DEPLOYMENT.md)
- [Deployment Plan — AASTMT](./DEPLOYMENT_PLAN_AASTMT_CARBON.md)
- [Environment Variables](./env.md)

## Developer Reference

- [API Reference](./api.md)
- [Data Model](./data-model.md)
- [Testing & QA Guide](./TESTING_QA_GUIDE.md)
- [Admin User Guide](./ADMIN_USER_GUIDE.md)

## Task Specs (phase work orders)

- [AI Workspace Phase 3A — Backend](./TASK-AI-WORKSPACE-PHASE-3A-BACKEND.md)
- [AI Workspace Phase 3B — Frontend](./TASK-AI-WORKSPACE-PHASE-3B-FRONTEND.md)
- [AI Workspace Phase 4A — Backend](./TASK-AI-WORKSPACE-PHASE-4A-BACKEND.md)
- [AI Workspace Phase 4B — Frontend](./TASK-AI-WORKSPACE-PHASE-4B-FRONTEND.md)
- [AI Workspace Phase 5 — Backend](./TASK-AI-WORKSPACE-PHASE-5-BACKEND.md)
- [AI Workspace Phase 5B — Frontend](./TASK-AI-WORKSPACE-PHASE-5B-FRONTEND.md)
- [AI Workspace Phase 6 — T3 Knowledge Graph](./TASK-AI-WORKSPACE-PHASE-6-T3-KG.md)
- [AI Workspace Phase 6B — Frontend KG](./TASK-AI-WORKSPACE-PHASE-6B-FRONTEND-KG.md)
- [AI Workspace Phase 6C — Provenance KG](./TASK-AI-WORKSPACE-PHASE-6C-PROVENANCE-KG.md)
- [AI Workspace Phase 7C — Entity Entry Points](./TASK-AI-WORKSPACE-PHASE-7C-ENTITY-ENTRY-POINTS.md)
- [DQ Rules Audit & Fix](./TASK-DQ-RULES-AUDIT-FIX.md)
- [W6 Remediation — All Findings](./TASK-W6-REMEDIATION-ALL-FINDINGS.md)
- [QA — Agentic Workflow Simulation](./TASK-QA-AGENTIC-WORKFLOW-SIMULATION.md)
- [QA — AI Pulse Simulation](./TASK-QA-AI-PULSE-SIMULATION.md)
- [QA — AI Workspace Simulation](./TASK-QA-AI-WORKSPACE-SIMULATION.md)

## Task Results (handoff reports)

- [Results — W6 Remediation](./TASK-RESULTS-W6-REMEDIATION.md)
- [Results — QA W5 Chat Agent Mode](./TASK-RESULTS-QA-W5-CHAT-AGENT-MODE.md)
- [Result — DQ Rules Audit & Fix](./TASK-RESULT-DQ-RULES-AUDIT-FIX.md)
- [Result — DQ Rules Audit & Fix Phase B2](./TASK-RESULT-DQ-RULES-AUDIT-FIX-PHASE-B2.md)
- [Result — QA Create DQ Rule](./TASK-RESULT-QA-CREATE-DQ-RULE.md)
- [Result — QA AI Pulse Simulation](./TASK-RESULT-QA-AI-PULSE-SIMULATION.md)
- [Result — QA AI Workspace Simulation](./TASK-RESULT-QA-AI-WORKSPACE-SIMULATION.md)

## Data & Fixtures

- [SIMULATION-GOLDEN.json](./SIMULATION-GOLDEN.json) — golden regression baseline consumed by `manage.py simulate_agent_workflows` (do not delete)
- Simulation reports (`TASK-RESULTS-SIMULATION-YYYY-MM-DD.{md,json}`) are **generated** by that command and are not kept in the repo.

## Diagrams

All architecture, data model, and workflow diagrams: [diagrams/](./diagrams/)

---

*Platform root: [README.md](../README.md) | AI toolkit: [.ai-toolkit/](../.ai-toolkit/) | Decisions: [.ai-toolkit/decisions/](../.ai-toolkit/decisions/)*