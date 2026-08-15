# TASKS.md — Pulse Vendoring Phase 1: In-Hand Stateless Engine

**Role:** Backend Worker
**Model:** DeepSeek-V3
**Domain:** backend
**Primary context:** `.ai-toolkit/decisions/0007-pulse-inhand-stateless-engine.md`, `docs/AI_INTELLIGENCE_ARCHITECTURE.md`, `.ai-toolkit/shared/ai-contract.md`

Vendor the FULL Pulse engine in-hand as an **INERT** package (no DB wiring, no migrations,
no runtime execution). Source: `/home/ahmed/clearturn/pulse`. Destination: `backend/ai/engine/`.

> **SCOPE CORRECTION (ADR-0009):** Pulse's engine is a **stateful SQLAlchemy monolith** —
> `agent/reasoning.py`, `tools.py`, `guardrails.py`, `llm/router.py`, `llm/prompts.py`,
> `cognition/turn/runner.py` all write to the DB via `get_session_factory()`. There is no
> "clean stateless subset" that is also a usable engine. So this phase vendors the WHOLE
> engine verbatim (inert); Phase 2 swaps the persistence seam to Django. **Do NOT cherry-pick.**

FILES TO READ FIRST:
- `backend/ai/providers/pulse.py` — current HTTP adapter (the seam that changes)
- `backend/ai/providers/_http.py` — current HTTP transport (to be retired)
- `backend/ai/protocol.py` — AIProvider ABC (contract the engine must satisfy)
- `backend/ai/intelligence.py` — CarbonIntelligence single entry point
- `.ai-toolkit/decisions/0007-pulse-inhand-stateless-engine.md` — binding ADR
- `/home/ahmed/clearturn/pulse/core/config.py` — engine config (vendored)
- `/home/ahmed/clearturn/pulse/agent/reasoning.py` — engine agent loop (vendored)

TASKS:

1. VENDOR THE FULL ENGINE IN-HAND (INERT)
   - CREATE `backend/ai/engine/` package with subpackages: `agent/`, `llm/`, `cognition/` (incl. `turn/`, `plan/`), `core/`, `memory/`, `knowledge/`, `knowledge_graph/`, `ingestion/`, `proactive/`, `archetypes/`, `skills/`
   - COPY the FULL source tree from `/home/ahmed/clearturn/pulse` for those directories, VERBATIM. Do NOT cherry-pick by file (see ADR-0009).
   - EXCLUDE ONLY the HTTP/UI/entrypoint layer (NOT the engine): `main.py`, `api/`, `studio/`, `widget/`, `evals/`
   - Rewrite ALL intra-package import roots to the new package root (`from core.config` → `engine.core.config`; `from llm.prompts` → `engine.llm.prompts`; `from core.database` → `engine.core.database`; etc.)
   - DO NOT wire to Django. DO NOT create migrations. DO NOT import from Django. The package is INERT (vendored in-hand, not yet executed).

2. ADD ENGINE DEPENDENCIES (for clean import only — not execution)
   - MODIFY `backend/requirements.txt`: add `sqlalchemy`, `pydantic`, `pydantic-settings`, `openai`, `tenacity`, `cryptography`, `httpx`, `PyYAML`, `Jinja2`, `apscheduler`
   - Note: `sqlalchemy` is TEMPORARY — Phase 2 replaces `core/database.py` with a Django store and removes it.
   - Verify: `/home/ahmed/aast/carbon/.venv/bin/python -m pip install -r requirements.txt` → no error (report if new pins conflict)

3. VERIFY INERT VENDOR (no behavior change)
   - The engine must import cleanly but must NOT be imported by Django or used at runtime yet.
   - Carbon's existing AI path (HTTP via `providers/pulse.py`) is UNCHANGED in this phase.
   - Verify: `cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -c "import ai.engine"` → no ImportError (imports without opening a DB connection)

DO NOT TOUCH:
- `backend/ai/providers/pulse.py` and `backend/ai/providers/_http.py` (HTTP adapter swap = Phase 2)
- `backend/config/settings.py` (no AI_PROVIDER_CLASS removal in this phase)
- `backend/ai/models.py`, `backend/ai/migrations/` (no Django models yet — Phase 2)
- `carbon-frontend/**`
- `docs/AI_INTELLIGENCE_ARCHITECTURE.md`
- `.ai-toolkit/decisions/0007-pulse-inhand-stateless-engine.md`
- `backend/core/`, `backend/catalog/`, `backend/mdm/`, `backend/dq/`, `backend/emissions/` (engine vendor only)

GATES (run ALL in order before reporting done):
  cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -c "import ai.engine" → clean (no DB connection opened)
  cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check → system checks pass
  cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests -q → backend AI test suite passes (existing HTTP path still green)
  cd /home/ahmed/aast/carbon && bash ./.ai-toolkit/scripts/verify.sh backend → backend gate passes

HARD RULES (project-specific):
- Phase 1 vendor is INERT: no Django wiring, no migrations, no runtime execution, no second DB.
- No separate AI database (RULE_6). Durable state → Carbon Postgres (Phase 2); transient → Redis.
- Do not add pgvector or an LLM gateway as a separate service (RULE_6).
- Backend-only phase: do not touch frontend files.
- Follow `.ai-toolkit/shared/ai-contract.md` (scope is MANDATORY).

REPORT BACK:
List each task with ✅ pass / ❌ fail, test count, terminal proof, and any deviations from spec.
