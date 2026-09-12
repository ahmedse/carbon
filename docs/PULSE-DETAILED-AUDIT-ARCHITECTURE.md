# Pulse — Detailed Audit & Architecture

> **Purpose.** This document is a self-contained, evidence-backed audit of **Pulse** — the AI "brain" of the Carbon Data Trust Platform. It is written to be pasted into a higher-capability LLM so that a stronger "coworker" can reason about Pulse's cognitive architecture, its agentic workflow, its integration with host systems, its learning loops, and its ability to *discover and encode* the business processes of the host platform — and then prescribe concrete fixes.
>
> **Method.** Every claim below was verified against the **actual code** (not the design docs), by six independent sub-audits of the engine and host layers. Design documents (`PULSE-MASTER.md`, `PULSE-0.3-ROADMAP.md`, ADRs) are treated as *aspirational*; code is treated as *truth*. Where code contradicts docs, the contradiction is flagged explicitly.
>
> **Key file map** (all paths relative to repo root `/home/ahmed/ws/carbon`):
> - Engine (vendored, host-agnostic): `backend/ai/engine/**`
> - Host (Carbon-owned durable state): `backend/ai/**` (everything *except* `engine/`)
> - Frontend: `carbon-frontend/src/**`

---

## 0. TL;DR — the honest verdict

Pulse is **not a demo**. It is a genuinely large (~55k+ LOC of engine + ~14k LOC of host glue + a full React workspace) in-process reasoning engine with real wiring: a six-witness turn pipeline, a multi-tier memory system, a knowledge graph, a scheduled proactive loop, a skill admission + promotion gate, tool/guardrail enforcement, and a chat↔agent UI split — all executed on the live hot path.

But it is **asymmetric**. For every genuinely-wired subsystem there is a roughly equal mass of **dead or inert scaffolding** that only exists to be faithful to the design docs. The most important structural flaws are:

1. **The engine is not actually stateless.** The design contract says "Pulse holds NO memory, stores NO graphs" and "engine imports nothing from Carbon." In reality the engine calls `db.add()/commit()` everywhere and imports Carbon-owned `ai.models.*` Django ORM models directly in 14+ files.
2. **The engine is not domain-agnostic.** Carbon/DQ/GHG/emissions vocabulary is hardcoded into generic cognition prompts and routing heuristics (36+ hits in `cognition/`, plus `llm/`, `agent/`, `proactive/`).
3. **The "strong reasoning" lane is inert.** The escalation/reason model config is empty by default, so "deep" turns silently fall back to the same cheap model as everything else.
4. **The MCP tool pipeline is dead.** `init_mcp_tools()` has zero callers; MCP tools never reach the registry.
5. **A large fraction of the knowledge-graph package is dead code** (multi-step planner, recovery, conversational memory, cache warmer, migration) — including a `NameError` that would crash if it ever ran.
6. **Default persistence is volatile.** `AI_STORE_BACKEND` defaults to `inmemory`, so any deployment missing the right env var silently drops every durable write.
7. **The "learning" subsystem is a misnomer.** Skill promotion *does* close its loop, but "learning" (`learning/preferences.py`) is an in-process, volatile prompt-tweak, and learned skill *reuse* is shallow (mostly terminology injection, not procedure execution).
8. **Guardrails and persistence are leaky** — worker fan-out bypasses the hook pipeline, the mutation guard is dead code, skill-gate bypass paths exist, and LLM cost logging is silently lost for owned sessions.

The rest of this document maps every subsystem, then decomposes these flaws into the user's five focus areas (cognition, agentic workflow, host integration/learning, business-process discovery/encoding, and cross-cutting).

---

## 1. What Pulse is — concept & boundary contract

### 1.1 Conceptual model

Pulse is described (and largely implemented) as a **host-agnostic, in-process reasoning engine**. The intended split is:

| Layer | Owns | Location |
|---|---|---|
| **Engine (Pulse proper)** | Inference only: perception, memory, reasoning, drafting, critique, action *planning* | `backend/ai/engine/**` |
| **Host (Carbon)** | Durable state, identity/RBAC, budgets, audit, persistence, and *execution of effects* | `backend/ai/**` (non-engine) |

The boundary contract is codified in rules:
- **RULE_6 / RULE_20 / RULE_21** — engine owns inference; host owns effects/state; mutations are consent-gated.
- Allowed integration surfaces (the only places the engine may touch the host): `ai/intelligence.py`, `ai/providers/pulse.py`, `ai/engine_runtime.py`, `ai/serializers.py`, `ai/workspace_api.py`.
- **Invariants I1–I8** and **anti-drift laws L1–L7** are binding for any change (see §9).

### 1.2 The eight faculties (PULSE-MASTER §1)

1. **Perception / salience** — what deserves attention.
2. **Memory** — working / short-term / long-term / episodic.
3. **Reasoning** — planning, decomposition, multi-step.
4. **Action** — tool use, execution, confirmation.
5. **Grounding / truthfulness** — citations, anti-hallucination, confidence.
6. **Learning / growth** — skill extraction, admission, promotion, reuse.
7. **Metacognition / awareness** — self-critique, verification, reflection.
8. **Proactivity / collaboration** — scheduled triggers, briefings, delivery.

### 1.3 The six-witness spine (single hot path)

Every chat turn flows through one deterministic pipeline in `engine/cognition/turn/`:

```
S1  salience   — deterministic regex classifier (zero LLM)
S1.5 intent    — LLM-as-classifier over api_catalog (gated by mutation-verb regex)
S2  retrieve   — hybrid pgvector→BM25→fuse→rerank (zero LLM)
S3  draft      — single route_chat planning call
S4  critic     — rules tier (always) + optional LLM tier
S5  execute    — asyncio.gather parallel tool dispatch
S6  ledger     — TurnLedgerRow write
```

---

## 2. System topology

| Concern | Technology | Detail |
|---|---|---|
| Backend | Django 5.2 + DRF | port **8009**, API prefix `/carbon-api/` |
| Frontend | React 19 + Vite 6 + MUI v7 | port **5179**, path `/carbon/` |
| DB | PostgreSQL 16 | durable state (under `AI_STORE_BACKEND=django`) |
| Cache/streams | Redis 6379 | short-term/working memory, event bus, SSE fan-out |
| Vector | pgvector / ChromaDB | semantic retrieval, embeddings |
| Scheduler | APScheduler `AsyncIOScheduler` | cognition loop, ~20 cron jobs |
| Transport | in-process (no HTTP between host→engine) | `engine_runtime.py` + `pulse.py` headers |

### 2.1 Engine subsystem line-mass (measured)

| Subsystem | LOC |
|---|---|
| `engine/cognition/` | ~11,216 |
| `engine/knowledge_graph/` | ~9,086 |
| `engine/agent/` | ~5,143 |
| `engine/core/` | ~2,735 |
| `engine/llm/` | ~2,567 |
| `engine/proactive/` | ~2,217 |
| `engine/memory/` | ~1,884 |
| `engine/skills/` | ~1,487 |
| `engine/knowledge/` | ~1,464 |
| `engine/ingestion/` | ~1,120 |

Host-side (`backend/ai/`, non-engine): `intelligence.py` 4,268; `engine_runtime.py` 4,089; `plans_service.py` 2,829; `host_executor.py` 1,408; `store.py` 1,414; `flight_director.py` 1,350; `workspace_api.py` 1,363; `providers/pulse.py` 597; `protocol.py` 567; `guards.py` 384.

---

## 3. Component-by-component architecture

### 3.1 Cognition (`engine/cognition/`)

**Turn pipeline** (`turn/`): `runner.py` (~2,600 LOC) is the *only* chat codepath (`PulseAgent.think()` has been deleted). It handles: pre-S1 pending-confirmation short-circuit, S1 salience, S1.5 intent, S2 retrieval, ReAct-loop gate, multi-step gate, single-pass fallback, S6 ledger.

| Module | Behavior | Status |
|---|---|---|
| `salience.py` | Pure regex classifier, zero LLM | ✅ clean |
| `intent.py` | LLM classifier over `api_catalog`; mutation/new-thing regex gates | ⚠️ hardcoded Carbon/DQ vocabulary |
| `retrieve.py` | Hybrid retrieval (pgvector→BM25→fuse→rerank), `_NO_KNOWLEDGE_PLACEHOLDER` | ✅ clean |
| `draft.py` | Single `route_chat` planning call; citation regex | ✅ clean |
| `critic.py` | Rules tier always; LLM tier optional | ⚠️ `_rules_only_verdict` always passes, never vetoes |
| `execute.py` | `asyncio.gather` parallel dispatch; dependency splitting; `EvidenceRecord` write | ⚠️ hardcoded `"carbon_api"` source |
| `verify.py` | Opt-in (`PULSE_VERIFY_ENABLED`, default **False**), fail-open | ⚠️ effectively dead |
| `ledger.py` | `TurnLedgerRow` write | ⚠️ engine DB write |

**Plan / ReAct** (`plan/`): `loop.py` (~1,400 LOC) `ReActLoop.run()` — draft→critic→execute→observe per step, `MAX_REPLANS=2`, consent gate, multi-hop injection, persists `Run`/`RunStep`. `planner.py` is `SkillAwarePlanner.decompose()` (skill-first, LLM fallback). ⚠️ `_allow = {"create_dq_rule", …}` and `_MULTI_SIGNALS` hardcode DQ/supplier vocabulary.

**Top-level cognition** (`loop.py`, `synthesis.py`, `consolidation.py`, `trajectory.py`, `distill/*`, `dialogue/*`, `auto_memory.py`, `kg_seeding.py`, `monitors.py`, `notifier.py`, `state.py`): a real APScheduler with ~20 jobs (consolidation 3:00 AM, skill admission 3:30 AM, kg_seeding 4:30 AM, prompt refine 6h, proactive eval 300s, daily briefing cron, etc.).

### 3.2 Memory (`engine/memory/`)

The **cleanest** part of the engine (zero domain terms, consistent `Store` seam, consistent tenancy filtering).

| Tier | Backing | Notes |
|---|---|---|
| `short_term.py` | Redis (source of truth) + in-process dict fallback | ✅ |
| `working.py` | Redis + dict fallback; `WorkingFocus` | ✅ |
| `long_term.py` | Store/Postgres + Chroma | ⚠️ stale docstring claims "SQLite"; semantic dedup (>0.92), contradiction (0.5–0.92 → conf 0.5), noise regex |
| `episodic.py` | Store | ✅ causal auto-link (7d), causal-chain walk, per-type decay |
| `manager.py` | orchestrates ST+LT+episodic+insights+prefs | ✅ domain-agnostic |
| `compactor.py` | LLM rolling summary (thresholds 20/50) | ✅ |
| `_redis.py` | lazy/lenient Redis client | ✅ |

### 3.3 Knowledge graph (`engine/knowledge_graph/` + `engine/knowledge/`)

**Storage is three-layer**, not one backend:
1. **PostgreSQL** via `ai.store.Session` — but binds to **Django ORM models** (`ai.models.knowledge_graph.KnowledgeNode/Edge`), *not* the engine's SQLAlchemy models.
2. **Optional vector store** (pgvector/ChromaDB) — degrades to `None`.
3. **Module-level in-memory adjacency list + node cache** — keyed per-instance.

**Live paths:**
- Schema-bootstrap + analysis pipeline (`_run_schema_analyze` → `run_schema_analysis` → `enrich_column_semantics` → `analyze_implicit_relationships` → `score_entity_importance`), idempotent.
- `DataProfiler.profile_table()` (live profiling of host-DB tables, FK-overlap validation).
- Single-step NL/SQL query path: `ExecutionEngine` → `QueryRetryLoop` → `ResponseSynthesizer` → `QueryCacheStore` (read-only psycopg2, `readonly=True`).

**Dead/inert paths:**
- `migrate_knowledge_entities` (referenced only in its own file).
- `MultiStepPlanner`, `PlanExecutor`, `PlanSynthesizer`, `JoinPathFinder` (never imported outside package; their config flags `KG_MULTI_STEP_ENABLED` / `KG_RECOVERY_ENABLED` toggle nothing).
- `RecoveryPipeline`, `TimeoutRecovery`, `ContextMerger`, `CoreferenceResolver`, `TurnClassifier`, `ConversationSessionStore`.
- `bm25.py` (retired no-op stub), `cache_warmer.py`, `cache_invalidator.py`.
- **Latent `NameError`** in dead `plan_executor.py:299` (`step` undefined in `_generate_step_sql`).

### 3.4 Agent / tools / skills / LLM (`engine/agent/`, `engine/skills/`, `engine/llm/`)

**Tools (`agent/tools.py`)**: 11 static tools + plugin + MCP merge. Merge order `{**plugin, **static, **mcp}` — static/MCP override plugins. `call_host_api` has a real confirmation gate (non-GET or `requires_confirmation` → pending `ToolExecution`).

**Guardrails (`agent/guardrails.py`)**: `HookPipeline` with 6 hooks (consent/readonly/tool-safety/rate-limit/budget/redaction), wired in `execute.py`. ⚠️ **bypassed in worker fan-out** (`workers.py` builds the pipeline but never runs it).

**Skills (`engine/skills/`)**: `registry.py`, `gate.py` (4 critics: structural/harmlessness/consistency/marginal_gain), `router.py`, `sandbox.py` (RestrictedPython), `crud.py`, `schema.py`.

**LLM router (`engine/llm/router.py`)**: lanes `chat`, `deep`, `reason`, `cognition`, `introspect`, `eval`, `embed`. Default config:
```
LLM_MODEL = LLM_NORMAL_MODEL = LLM_COGNITION_MODEL = "anthropic/claude-haiku-4.5"
LLM_REASON_MODEL = LLM_ESCALATION_MODEL = LLM_INTROSPECT_MODEL = ""
LLM_DAILY_BUDGET_USD = 5.0
```

### 3.5 Proactive (`engine/proactive/`)

`loop.py` orchestrates eval→dedupe→assemble→deliver→expire; `trigger_evaluator.py` runs raw SQL against `host_db_url`; `delivery.py` persists `KgProactiveInsight` and routes by severity; `suppression.py` handles cooldown/dedup/dismissal-learning; `user_watches.py` evaluates `AIAnomalyWatch` rows; `context_assembler.py` runs context queries + LLM narrative.

### 3.6 Host layer (`backend/ai/` non-engine)

**Entry chain (single, coherent):**
```
POST .../conversations/{id}/messages/stream/
  → WorkspaceConversationViewSet.send_message_stream (SSE)
  → CarbonIntelligence.send_message_stream
  → build_scope → assemble_context → _guard_workspace_operation
  → PulseProvider.chat_stream → dispatch_task_stream("chat")
  → _run_chat → TurnPipelineRunner(...).run()
  → deterministic post-processing (anti-hallucination gate, access table, confidence)
```

**GuardChain (`ai/guards.py`)**: docstring claims "Five mandatory guards" but there is **no `RateLimiter`**. `GuardChain.run` = Scope → Access → Isolation → Mutation. Reality: Scope+Access are the workhorses; `DataIsolationGuard` only fires when `table_names` is non-None; **`MutationGuard.validate` is dead** (no workspace op name matches any mutation operation); `AuditTrail` is not in `run()` (log-only, `logger.info`).

**Domain seam (`ai/domain_protocol.py`)**: 9 registered `DomainAIOperations` subclasses. `get_tools()` exists on the ABC **and** every subclass — but only `emissions` (5 read tools) and `data_product` (3 tools incl. `create_table` mutation) return real tools; the other **7 return `[]`** (manifest-only).

**Adapter seam (`ai/adapter/`)**: `HostAdapterContract(ABC)` with 4 abstract methods. `CarbonHostAdapter` is the *only* place (besides `intelligence.py`) that reaches Carbon ORM. `context_assembler.py` is **ORM-free** (only imports `ai.protocol.WorkspaceContext`); the adapter is injected. ✅ Genuine abstraction.

**Audit**: `AuditLog(AppScopeMixin)` + `AuditService.log()` (append-only, PII-redacts) + `AuditListView` (GET-only, capability-gated). ✅ Working (not "planned only"). Note: two parallel trails (structured-log `AI_AUDIT` vs durable `AuditLog`).

### 3.7 Frontend (`carbon-frontend/src/`)

- **`AIWorkspace.jsx`** master container; Chat↔Agent `ToggleButtonGroup` (ADR-0014) fully wired.
- Three real SSE streams (message POST-SSE, insight GET-SSE, operation GET-SSE); polling only for suggestions (60s) + live plan DAG.
- All **26** admin panels routed under `/admin/ai/*` behind `AdminRoute requiredCapability={AI_VIEW_CONSOLE}`.
- Confidence/provenance are **real backend data** (`confidence_label`, `honest_uncertainty`, provenance `lines/sources/toolTrace`), not UI-invented.
- `PulseConsolePage` / `/ai/console` is **still planned, not built** (docs explicitly say not to build a new route — the console is `/admin/ai/*`).

---

## 4. Every feature / intelligence — capability inventory

### 4.1 Perception & salience
- Deterministic regex salience classifier (zero LLM cost). ✅
- Intent classifier over `api_catalog`. ✅ (but polluted with hardcoded domain terms — §5.1)

### 4.2 Memory
- Working / short-term / long-term / episodic, all wired. ✅
- Semantic dedup, contradiction detection, noise filtering, causal auto-linking, decay, distillation (episodic→semantic), promotion (learned→confirmed). ✅
- Conversation compaction (rolling LLM summary). ✅

### 4.3 Reasoning & planning
- ReAct loop with replans, consent gates, multi-hop injection. ✅
- Skill-aware planner (`SkillAwarePlanner`). ✅ (weak reuse — §5.1)
- Multi-step KG query planning. ❌ **dead code**.
- "Strong reasoning" escalation lane. ⚠️ **inert by default** (empty model config).

### 4.4 Action & tool use
- 11 static tools, plugin registry, confirmation-gated mutations. ✅
- Worker parallel fan-out. ⚠️ guardrails bypassed in fan-out.
- MCP tools. ❌ **dead** (never initialized).
- Host API discipline (validate→execute→retry). ⚠️ default-off.

### 4.5 Grounding & truthfulness
- Hybrid retrieval + citations + anti-hallucination post-processing + confidence labels. ✅
- Verification witness. ⚠️ opt-in + fail-open (effectively dead).
- Critic veto. ⚠️ rules tier never vetoes.

### 4.6 Learning & growth
- Trajectory → consolidation (LLM reflect) → skill admission (4 critics) → promotion → reuse. ✅ **loop closes** (refutes the "learning is cold" claim).
- But reuse is shallow: mostly terminology injection; `invoke_skill` returns body "as data only" (no execution for `sql_macro`/`api_call`; only `code_snippet` runs in sandbox).
- `learning/preferences.py` — in-process, volatile preference classifier (misnamed "learning").

### 4.7 Metacognition
- Self-critique (critic), verification (opt-in), reflection (consolidation reflect), prompt optimizer (LLM-as-judge → rewrite). ✅/⚠️ mixed.

### 4.8 Proactivity
- Trigger evaluation (threshold/trend/correlation), daily briefing, suppression/cooldown, dismissal-learning. ✅ real and scheduled; **delivery reaches the React UI via Redis→SSE** (refutes the G2 "never reaches the human" doc claim).
- User watches. ✅ wired (but leaks Django ORM into engine).

### 4.9 Ingestion
- CSV loading (`csv_loader.py`, pure) → `ops_workflow.py` (validate→inference→ops output via host REST) → `run_ops_workflow` tool. ✅ wired.

---

## 5. Flaw register — by the user's focus areas

### 5.1 Cognition flaws

1. **Domain vocabulary hardcoded into generic cognition.** `cognition/turn/intent.py` — supposed to be a closed-label classifier over `api_catalog` — hardcodes `list_emission_factors`, four campus branch names (`"South Valley", "Smart Village", "Abu Qir", "Alamein"`), and GHG/Scope vocabulary in system prompts (36 grep hits). `plan/loop.py` hardcodes `_allow = {"create_dq_rule", …}` and DQ grounding rules. `planner.py` hardcodes `"by supplier"/"by module"/"across suppliers"`. **This is the single biggest "cognition is not general" flaw** — the engine cannot be reused by a new host without editing engine files.
2. **Critic never vetoes.** `turn/critic.py` `_rules_only_verdict` returns `pass_with_flag` unconditionally — even for `unconfirmed_mutation`. The safety net for "unconfirmed mutation" is dead.
3. **Verification is opt-in + fail-open.** `verify.py` returns `passed=True` on any error, and is off by default.
4. **Strong reasoning is a no-op.** `LLM_REASON_MODEL`/`LLM_ESCALATION_MODEL` empty ⇒ "deep" salience routes to the same cheap model, and knowledge-gap escalation is disabled.
5. **Hardcoded source map.** `execute.py` hardcodes `"carbon_api"` as the default source.
6. **Cognition ↔ Carbon coupling.** `runner.py:1435` imports `CarbonContextAssembler` on the hot path; `loop.py`/`monitors.py` import Carbon Django models (`CognitionSweepRun`, `KnowledgeEntity`).

### 5.2 Agentic workflow flaws

1. **MCP tool pipeline is dead.** `init_mcp_tools()` has zero callers; `MCP_TOOLS`/`MCP_EXECUTORS` stay empty. Any MCP surface in config/UI has no runtime effect.
2. **Guardrails bypassed in worker fan-out.** `workers.py:_run_worker` builds `_pipeline = self._get_hook_pipeline()` but never runs it and never passes `is_worker=True`.
3. **Skill-gate bypass paths.** `promote_skill` skips admission for any non-`pending` `gate_status`; `SkillsStore.promote_to_instance` and `SkillRegistry.update_status` mutate promotion state without the gate; `Skill.gate_status` defaults to `NULL`, so un-gated skills are invisible to the sweep.
4. **Skill reuse is shallow.** `invoke_skill` returns the body as data only; `sql_macro`/`api_call` skills are not executed; the hot path injects only `terminology` and discards the matched skill procedure.
5. **Admission critics fail open.** `harmlessness`/`consistency`/`marginal_gain` critics return `passed=True` on exception.
6. **`get_task()` is a hard stub.** `engine_runtime.py:3690` always returns `{"status":"pulse_unavailable",...}` — the async "poll status" contract is dead; "async" submit methods actually return completed results synchronously.
7. **`_builtin_plugins()` returns `[]`** (placeholder); real registration happens elsewhere (`ai/plugins/__init__.py`), leaving a misleading empty hook.

### 5.3 Host integration & learning flaws

1. **`AI_STORE_BACKEND` defaults to `inmemory`** (`config/settings.py:674`). Any deployment missing `.env` silently drops every engine write. Production only works because `backend/.env:38` sets `=django`.
2. **`DjangoStore._apply_tenancy_filter` is a no-op** — returns `qs` unchanged; real CBAC partitioning is `scope_q()` at query boundaries, contradicting the store docstring.
3. **Dual persistence stack.** `core/database.py` declares SQLAlchemy "retired" in favor of Django `ai.store`, but the engine still imports `sqlalchemy.select/update` and type-hints `AsyncSession` (e.g. `tools.py:1184`, `skills/registry.py`, `executor.py`, `gate.py`). Two ORM stacks coexist.
4. **Django ORM leakage into the engine layer.** 14+ engine files import `ai.models.*` directly (`knowledge_graph/store.py`, `knowledge/store.py`, `cache_store.py`, `feedback.py`, `proactive/user_watches.py` does direct `.save()` on `AIAnomalyWatch`, `cognition/turn/execute.py` does `EvidenceRecord.objects.create`).
5. **LLM cost/usage logging lost for owned sessions.** `router.py:_log_call` writes inside `begin_nested()` + `flush()` but never commits; when `route_chat` owns its session, the `finally` closes it → log rolled back. `provider.chat_completion*` bypass router budget/log entirely.
6. **GuardChain thinner than advertised.** No `RateLimiter` (rate limiting is view-throttle + quota instead); `MutationGuard.validate` dead; `DataIsolationGuard` conditional.
7. **Duplicated model families.** `KnowledgeEntity` vs `KnowledgeNode/Edge`; engine-mirror `Conversation/Message` (`core.py`) vs host `AIConversation/AIMessage` (`workspace.py`) — kept in sync by class-name lookup.
8. **Raw SQL injection surface.** `trigger_evaluator.py` interpolates `where_clause` verbatim (`f"WHERE {where_clause}"`); `context_assembler.py` only checks `.startswith("SELECT")`; both bypass `sql_validator.py`.
9. **`learning/preferences.py` is volatile** — thread-local in-process dict, never persisted, so learned preferences vanish on restart.
10. **`storage_migration.py` imports a nonexistent `_ensure_pg_schema`** → guaranteed `ImportError` (but it's dead, zero callers).

### 5.4 Business-process discovery & encoding flaws

This is the weakest area — the user's explicit interest. Honest assessment:

1. **No real "process discovery" exists.** There is `kg_seeding.py` (noun-phrase → `KgNode`, conf 0.3) and schema analysis (entity/attribute/relationship extraction from DB schema), but **nothing** that observes multi-step business workflows (e.g., "a DQ rule is created, then approved, then published") and encodes them as reusable procedures. Process discovery is, at best, *schema discovery*.
2. **Domain tools are 2-of-9 real.** Only `emissions` and `data_product` expose actual `call_host_api`-backed tools; the other 7 domains (`water`, `mdm`, `admin`, `customer`, `finance`, `hr`, `people`) return `[]` — so the engine cannot *act on* most host business processes even if it knew about them.
3. **`seed_from_domain_pack` is dead** — returns 0 after logging "Skipping…"; there is no live mechanism to ingest a host's domain pack of business processes/triggers.
4. **Skills are generic, not business-process-encoded.** The skill admission pipeline extracts "skills" from *trajectory* (conversational behavior), not from observed host business flows. `invoke_skill` doesn't execute `sql_macro`/`api_call`, so even a discovered multi-step procedure can't be replayed against the host.
5. **`learned_triggers.py` is dead** — `analyze_snapshots` has no caller, is not scheduled; the `seed_learned_triggers` + `trigger_learning` wiring was explicitly removed. So there is no loop that turns repeated anomalies/trends into new proactive triggers.
6. **`ops_workflow.py` is the closest thing** — CSV ingest → validate → inference → ops output — but it's a fixed, hand-coded pipeline, not a *discovered* one.

### 5.5 Cross-cutting architectural flaws

1. **"Stateless engine" contract is not honored literally.** The engine writes durable state everywhere (`turn/ledger.py`, `cognition/*`, `memory/*`, `skills/*`, `agent/*`, `proactive/*`) — via the `ai.store` seam, but still *inside* the engine.
2. **`core/models.py` is still SQLAlchemy `DeclarativeBase`** (34 tables + 15 in `knowledge_graph/models.py` = 49 engine tables) — *not* Django models. The Django mirror lives in `ai/models/`, mapped 1:1 by class-name lookup in `store.resolve_model`.
3. **Default persistence is volatile** (repeated: `inmemory` default).
4. **Dead/inert code is a large fraction of the surface** (§6).
5. **Hardcoded host-app routes/brand** in `proactive/delivery.py` (`"/engines","/models","/predictions","/datasets"`, `app_identifier` fallback `"carbon"`), power-domain defaults in `insight_generator.py` (`"demand_forecasts"`, `"value_mw"`), and Carbon/DQ config constants in `core/config.py`.

---

## 6. Dead / inert / stub code register (consolidated)

| Item | Location | Nature |
|---|---|---|
| `analyze_snapshots()` | `cognition/learned_triggers.py:37` | Dead (no caller, not scheduled; wiring removed) |
| `_get_llm()` | `cognition/distill/episodic_to_semantic.py:55` | Self-marked DEPRECATED, still live branch |
| `CriticWitness._rules_only_verdict` | `cognition/turn/critic.py` | Inert safety gate (never vetoes) |
| `VerificationWitness` | `cognition/turn/verify.py` | Opt-in + fail-open |
| `bm25.py` | `knowledge_graph/` | Retired no-op stub |
| `MultiStepPlanner` / `PlanExecutor` / `PlanSynthesizer` / `JoinPathFinder` | `knowledge_graph/` | Dead (unimported; `NameError` in `plan_executor.py:299`) |
| `RecoveryPipeline` / `TimeoutRecovery` | `knowledge_graph/` | Dead |
| `ContextMerger` / `CoreferenceResolver` / `TurnClassifier` / `ConversationSessionStore` | `knowledge_graph/` | Dead |
| `cache_warmer` / `cache_invalidator` | `knowledge_graph/` | Dead |
| `migrate_knowledge_entities` | `knowledge_graph/migration.py:79` | Dead (self-referenced only) |
| `init_mcp_tools()` | `agent/tools.py` | Dead (zero callers) |
| `_builtin_plugins()` | `agent/plugins.py` | Placeholder → `[]` |
| `PulseAgent` (legacy) | `agent/reasoning.py` | Mostly dead (only `AgentResponse` + 2 regex helpers live) |
| `detect_performance_drift` | `proactive/insight_generator.py:111` | DEPRECATED, dead |
| `seed_from_domain_pack` | `proactive/trigger_registry.py:267` | Dead (returns 0, logs "Skipping") |
| `storage_migration.copy_sqlite_to_postgres` | `core/storage_migration.py:26` | **Broken** (imports nonexistent `_ensure_pg_schema`), dead |
| `instance_export.export/import_instance` | `core/instance_export.py` | Dead (pre-Django SQLite/Chroma bundle) |
| `encryption.encrypt/decrypt_value` | `core/encryption.py` | No callers found |
| `get_task()` | `engine_runtime.py:3690` | Hard stub (always `pulse_unavailable`) |
| `MutationGuard.validate` | `guards.py:222` | Dead (no op matches) |
| `except NotImplementedError` (anomaly) | `intelligence.py:3510` | Unreachable (provider is implemented) |
| Frontend `PulsePane.jsx` / `AIAgentPanel.jsx` / `AIActionRunner.jsx` | `src/shell/` | Orphaned (no production import) |
| Frontend `useDomainManifests.js` / `useOptimisticItem.js` | `src/hooks/` | Dead hooks |

---

## 7. Documented-vs-implemented gap table

| Claim (docs) | Actual (code) | Verdict |
|---|---|---|
| "Pulse holds NO memory, stores NO graphs" | Engine writes durable state everywhere via `ai.store` | ❌ contradicted |
| "Engine imports nothing from Carbon" | 14+ engine files import `ai.models.*` Django models | ❌ contradicted (spirit) |
| "Cognition is domain-agnostic" | 36+ hardcoded Carbon/DQ/GHG terms in cognition | ❌ contradicted |
| "Learning loop is cold" (G1) | Trajectory→consolidation→admission→reuse **closes** | ✅ refuted (but reuse shallow) |
| "Proactivity never reaches the human" (G2) | Redis→SSE→React path is real | ✅ refuted |
| "`get_tools()` is missing" (0.3 roadmap) | Exists on ABC + all 9 domains | ✅ refuted (but 7/9 return `[]`) |
| "Strong reasoning lane" | Inert (empty model config → haiku fallback) | ⚠️ latent |
| "MCP integration" | `init_mcp_tools` never called | ❌ dead |
| "Five mandatory guards" | 4 run; no RateLimiter; MutationGuard dead | ⚠️ thinner |
| "CBAC-partitioned Django store" | `_apply_tenancy_filter` is a no-op; CBAC at query boundary | ⚠️ misnomer |
| "Durable audit log" | `AuditLog` + `AuditService` + admin API working | ✅ confirmed |
| "Pulse Console `/ai/console`" | Not built; console = `/admin/ai/*` | ⚠️ planned-only |
| "SQLAlchemy engine retired" | Schema still SQLAlchemy; raw SQLAlchemy still used in engine | ⚠️ dual stack |

---

## 8. What is genuinely excellent (preserve)

1. **Memory subsystem** — domain-clean, consistent `Store` seam, real tenancy filtering, semantic dedup/contradiction/noise handling.
2. **Six-witness spine** — a single, deterministic, observable hot path (`TurnPipelineRunner.run()`), not a tangle of codepaths.
3. **Skill admission loop** — 4 critics + cron + promotion + terminology reuse actually runs end-to-end.
4. **Confirmation/mutation gating** — RULE_21 staging (`ToolExecution` pending → confirm/decline) is real, with a null-output guard preventing silent success.
5. **Host adapter seam** — `context_assembler.py` is genuinely ORM-free; ORM access is consolidated in `CarbonHostAdapter`.
6. **Frontend chat↔agent split** — fully wired, with real SSE streams (not polling) and backend-authored confidence/provenance.
7. **Proactive delivery** — a real Redis→SSE→React path with CBAC frame filtering.

---

## 9. Invariants & anti-drift laws (binding for any remediation)

- **I1** — engine imports nothing from Carbon domain apps.
- **I2** — engine writes no durable state (host owns all persistence).
- **I3** — RULE_21 consent-gated mutations.
- **I5** — outcome copy, no engine internals leaked to UI.
- **I6** — new capability = tool/plugin/skill, never spine edits.
- **L1–L7** — anti-drift laws (no schema divergence, no second ORM path, no dead scaffolding shipped, etc.).
- Pulse 0.2 is **closed** (ADR-0026); 0.3 = Waves E–H; 0.4 = Wave I (MCP per app, code sandbox, web search, subagent UI, PII gate).

---

## 10. Recommended remediation (prioritized, for the higher LLM to elaborate)

### A. Restore generality of cognition (highest leverage)
- Move all hardcoded domain vocabulary out of `cognition/turn/intent.py`, `plan/loop.py`, `planner.py`, `llm/prompts.py`, `agent/tools.py` into instance config / domain packs (`ai/domain/*`, `instance.yaml`).
- Make the critic actually veto (`unconfirmed_mutation` must stop execution), and make verification fail-closed or at least default-on.

### B. Make the agentic loop honest
- Wire `init_mcp_tools()` (or delete the MCP surface if it can't be shipped).
- Configure `LLM_REASON_MODEL` / `LLM_ESCALATION_MODEL` (or remove the "deep reasoning" claim).
- Run the guardrail hook pipeline in worker fan-out.
- Close skill-gate bypass paths (`gate_status` default → `"pending"`; route all promotion through the gate).
- Give `invoke_skill` real execution for `sql_macro`/`api_call` (consent-gated), or stop advertising multi-step skill execution.

### C. Fix host integration & learning
- Change `AI_STORE_BACKEND` default to `django` (or fail loudly, never silently drop writes).
- Implement `_apply_tenancy_filter` (or rename/remove the "CBAC store" claim).
- Commit LLM cost logs; route all completion through the budget path.
- Persist `learning/preferences.py` (durable user profile already exists as `AIUserProfile`).
- Reuse `sql_validator.py` in `trigger_evaluator.py` and `context_assembler.py`; parameterize `where_clause`.

### D. Business-process discovery & encoding (the user's core ambition)
This is the **largest greenfield gap**. A credible path:
1. **Instrument host mutations** (via the existing `AuditLog` / `ToolExecution` staging) to capture real business-process traces ("created DQ rule → approved → published").
2. **Add a process-mining layer** that clusters event traces into candidate multi-step procedures (the existing `trajectory.py`/`consolidation.py` machinery is a template, but currently operates on *conversation*, not *host events*).
3. **Encode discovered procedures as `ProcedureBody` skills** with `sql_macro`/`api_call` steps, then make `invoke_skill` actually execute them behind the RULE_21 consent gate.
4. **Implement `seed_from_domain_pack`** (currently a no-op) to bootstrap each host's business vocabulary/triggers.
5. **Re-wire `learned_triggers`** so repeated anomalies/trends become new proactive triggers (the wiring was removed).
6. **Expand `get_tools()` coverage** from 2/9 domains to all domains, so the engine can *act* on every host business process it learns.

### E. Hygiene
- Delete or finish the ~20 dead/inert modules (or gate them behind real, honored flags).
- Resolve the dual ORM stack (SQLAlchemy schema vs Django mirror) — pick one source of truth for models.
- Remove/repair `storage_migration.py` (nonexistent `_ensure_pg_schema`).
- Prune orphaned frontend components (`PulsePane`, `AIAgentPanel`, `AIActionRunner`).

---

## 11. Suggested prompts for the higher LLM

1. "Given §5.4, design a process-discovery + encoding architecture that observes host business events (from `AuditLog` and `ToolExecution`) and encodes them as executable, consent-gated `ProcedureBody` skills — without violating invariants I1/I2/I3."
2. "Given §5.1, propose a clean domain-agnostic cognition layer where all Carbon/DQ/GHG vocabulary is injected from instance config/domain packs, not hardcoded."
3. "Given §5.2, redesign the agentic execution loop so guardrails are never bypassed, MCP tools are actually loaded, and skill admission has no bypass path."
4. "Given §3.3, either complete or remove the dead knowledge-graph multi-step planner / recovery / conversational-memory paths, and fix the latent `NameError`."
5. "Given §6, produce a prioritized deletion/completion plan for the dead-code register."
