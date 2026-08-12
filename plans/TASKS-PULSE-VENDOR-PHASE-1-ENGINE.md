# TASKS.md — Pulse Vendoring Phase 1: In-Hand Stateless Engine

**Role:** Backend Worker
**Model:** DeepSeek-V3
**Domain:** backend
**Primary context:** `.ai-toolkit/decisions/0007-pulse-inhand-stateless-engine.md`, `docs/AI_INTELLIGENCE_ARCHITECTURE.md`, `.ai-toolkit/shared/ai-contract.md`

Vendor Pulse's stateless reasoning engine into Carbon as an in-hand package.
Source: `/home/ahmed/clearturn/pulse`. Destination: `backend/ai/engine/`.

FILES TO READ FIRST:
- `backend/ai/providers/pulse.py` — current HTTP adapter (the seam that changes)
- `backend/ai/providers/_http.py` — current HTTP transport (to be retired)
- `backend/ai/protocol.py` — AIProvider ABC (contract the engine must satisfy)
- `backend/ai/intelligence.py` — CarbonIntelligence single entry point
- `.ai-toolkit/decisions/0007-pulse-inhand-stateless-engine.md` — binding ADR
- `/home/ahmed/clearturn/pulse/core/config.py` — engine config (vendored)
- `/home/ahmed/clearturn/pulse/agent/reasoning.py` — engine agent loop (vendored)

TASKS:

1. VENDOR THE STATELESS ENGINE CORE
   - CREATE `backend/ai/engine/` package with subpackages: `agent/`, `llm/`, `cognition/turn/`, `core/`
   - COPY from `/home/ahmed/clearturn/pulse` ONLY the stateless reasoning meat:
     - `agent/` — reasoning.py, guardrails.py, tools.py, executor.py, workers.py, budget.py, registry.py, api_discipline.py, mcp_client.py
     - `llm/` — provider.py, embeddings.py, router.py, prompts.py, playbook.py, prompt_optimizer.py, prompt_synthesizer.py, eval.py
     - `cognition/turn/` — six-witness pipeline: runner.py, witnesses.py, retrieve.py, draft.py, critic.py, execute.py, salience.py, ledger.py
     - `cognition/` — state.py, trajectory.py, synthesis.py
     - `core/` — config.py, models.py, security.py, encryption.py, exceptions.py, clock.py
   - Rewrite ALL intra-package imports to the new package root (`from core.config` → `engine.core.config`; `llm.prompts` → `engine.llm.prompts`; etc.)
   - Verify: `cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -c "import ai.engine"` → no ImportError

2. EXCLUDE PERSISTENCE + SYSTEM-OF-INTELLIGENCE (do NOT vendor)
   - DO NOT copy: `core/database.py`, `main.py`, `api/`, `memory/`, `knowledge/`, `knowledge_graph/`, `ingestion/`, `proactive/`, `archetypes/`, `skills/`, `studio/`, `widget/`, `evals/`, `cognition/loop.py`, `cognition/consolidation.py`, `cognition/distillation.py`, `cognition/monitors.py`, `cognition/learned_triggers.py`
   - These are Phase 2 (migrated as Carbon Django apps, CBAC-partitioned). The engine stays stateless.

3. ADD ENGINE DEPENDENCIES
   - MODIFY `backend/requirements.txt`: add `openai`, `tenacity` (and `apscheduler` ONLY if a vendored module imports it — check first)
   - Verify: `/home/ahmed/aast/carbon/.venv/bin/python -m pip install -r requirements.txt` → no error (report if new pins conflict)

4. REPLACE HTTP ADAPTER WITH IN-PROCESS ENGINE SEAM
   - MODIFY `backend/ai/providers/pulse.py`: call the vendored engine in-process (no HTTP, no requests to :9100)
   - MODIFY `backend/ai/providers/_http.py`: retire the live HTTP path (inert shim or remove references)
   - MODIFY `backend/config/settings.py`: remove `AI_PROVIDER_CLASS` runtime swapping (single hardcoded engine seam)
   - Do NOT change `backend/ai/protocol.py` ABC signatures (contract is stable)

DO NOT TOUCH:
- `carbon-frontend/**`
- `backend/ai/memory|knowledge|knowledge_graph|ingestion|proactive|archetypes` (do not create — Phase 2)
- `docs/AI_INTELLIGENCE_ARCHITECTURE.md`
- `.ai-toolkit/decisions/0007-pulse-inhand-stateless-engine.md`
- `backend/core/`, `backend/catalog/`, `backend/mdm/`, `backend/dq/`, `backend/emissions/` (engine vendor only)

GATES (run ALL in order before reporting done):
  cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -c "import ai.engine" → clean
  cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check → system checks pass
  cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests -q → backend AI test suite passes
  cd /home/ahmed/aast/carbon && bash ./.ai-toolkit/scripts/verify.sh backend → backend gate passes

HARD RULES (project-specific):
- Pulse engine is STATELESS — no memory, no learning, no graphs, no DB of its own.
- No separate AI database. Durable state = Carbon Postgres; transient = Redis.
- Do not add pgvector or an LLM gateway as a separate service (RULE_6).
- Backend-only phase: do not touch frontend files.
- Follow `.ai-toolkit/shared/ai-contract.md` (scope is MANDATORY).

REPORT BACK:
List each task with ✅ pass / ❌ fail, test count, terminal proof, and any deviations from spec.
