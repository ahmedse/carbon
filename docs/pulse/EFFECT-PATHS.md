# PULSE P0-06 — Effect-Path Inventory

**Status:** research deliverable (read-only audit — no code was modified)
**Scope:** every code path in the Pulse AI subsystem (`backend/ai/`) that produces a **host effect** or a **durable write**, and the guard coverage present **today**.
**Method:** static trace of the specified entry points to their sink. Every row cites `file:line`. Nothing was executed.

---

## 0. Definitions used in this document

**Effect** = a path that leaves a mark outside the process's own ephemeral state:

| Effect type | Meaning |
|---|---|
| **Host API call** | HTTP call to the Carbon host platform (`call_host_api`, host executor, host DB) |
| **External system** | Any non-Carbon I/O: MCP server, LLM provider, outbound HTTP, Redis/WebSocket, vector store |
| **Subprocess** | Shell/process spawn, code execution sandbox |
| **DB write** | Row insert/update/delete in the Pulse or host database |
| **Durable write** | Append-only or accounting row that survives the turn: ledger, evidence, usage accounting, audit log, provenance, cache |
| **Filesystem** | File created/overwritten on disk |

**Fail-closed** (the only acceptable state for a mutation guard):

> **Fail-closed = NO.** A guard is *fail-closed* only when **every** one of the following holds:
> 1. The guard is **on the code path** that reaches the sink (not merely defined elsewhere in the module).
> 2. The guard's **default / absent-input** branch **denies** the effect (deny-by-default), not allows it.
> 3. A **crash, exception, timeout, or missing dependency inside the guard** results in **denial**, not pass-through.
> 4. An **unregistered / unknown** target (unknown endpoint, unknown tool, unknown domain) is **denied**.
> 5. The denial is **observable** (returned error, veto verdict, or audit row) — a silent `return None` / `logger.warning` is **not** a denial.
>
> `PARTIAL` = at least one of 1–5 fails. `NO` = no guard on the path at all.

---

## PART 1 — Host-effect paths (host API / external system / subprocess / filesystem)

| # | Path (file:function/class) | Effect type | Guard coverage TODAY | Fail-closed? | Notes |
|---|---|---|---|---|---|
| 1 | `ai/engine/agent/tools.py:662` `execute_call_host_api` (non-GET branch) | Host API call | `HostAPIExecutor.requires_confirmation` (`agent/executor.py:96`) + `create_pending_execution` (`executor.py:108`) + `consent_hook` (`agent/guardrails.py:156`) + `CriticWitness` mutation gate (`cognition/turn/critic.py:104`) | PARTIAL | Staged, never sent. But `requires_confirmation` consults an API catalog; a catalog entry explicitly marked `requires_confirmation: False` sends immediately. `consent_hook` only exists if a `hook_pipeline` was injected (see #7). |
| 2 | `ai/engine/agent/tools.py:662` `execute_call_host_api` (GET branch → `call_api_direct`) | Host API call | **NONE** | **NO** | The GET branch is a **live, unconfirmed host read**. No scope guard, no tenancy filter, no rate limit on this branch. |
| 3 | `ai/engine/agent/executor.py` `_call_api` | Host API call | `HostJWT` only — `_build_headers` (`executor.py:83`) attaches the per-user token; `_call_api` raises when no `user_token` | PARTIAL | No service-account fallback (good). But there is **no per-endpoint authorization check** beyond "did the caller bring a token". |
| 4 | `ai/engine/agent/executor.py` `confirm_execution` | Host API call (staged release) | `ConfirmOwnership` (P0-2 ownership check) + `PendingExec` | **YES** | Confirmation is ownership-scoped and only releases a row that already passed staging. |
| 5 | `ai/engine/agent/mcp_client.py:202` `MCPClient.execute_tool` → `session.call_tool(...)` | External system | **NONE** | **NO** | Arbitrary third-party tool invocation. No allowlist, no confirmation, no hook, no argument inspection. The only failure handling is `except Exception → {"error": ...}` at `mcp_client.py:259`. |
| 6 | `ai/engine/agent/tools.py:1483` `init_mcp_tools` → `_exec` closures → `registry.execute_tool` | External system | **NONE** | **NO** | The closures are registered as ordinary tool executors, so they inherit whatever (lack of) guard the dispatching path has. |
| 7 | `ai/engine_runtime.py:3756` `_run_action_stream` → `executor_fn` dispatch at `3962`/`3964` | Host API / External / DB (all tools incl. `MCP_EXECUTORS`) | **NONE** | **NO** | **The single riskiest path.** This is the workspace "Run tool / Run agent" path. It builds **no** `HookPipeline`, runs **no** `CriticWitness`, performs **no** pre-execution consent check. The only gate is the tool's *own* returned `requires_confirmation` (`engine_runtime.py:3988`), i.e. the tool guards itself or nothing does. It is also the path through which #5, #6 and #17 are reachable. |
| 8 | `ai/plugins/create_dq_rule.py:363` `CreateDQRule.execute` → `:400` `create_pending_execution` | Host API call (staged) | `HostAPI.requires_confirmation = True` (`:359`) + `PendingExec` | PARTIAL | Correctly staged. Depends on `ctx.host_api` being present — if absent it returns `{"error": ...}` at `:366` (fail-visible, good). |
| 9 | `ai/engine/ingestion/ops_workflow.py` `ingest_csv` | Host API call (write) | `OpsConfirm` — refuses `is_managed`; host dry-run first; real write requires `confirm` else returns a pending execution | PARTIAL | Strong layering, but the confirm flag is a caller-supplied boolean, not an ownership-verified consent record. |
| 10 | `ai/engine/ingestion/ops_workflow.py` `validate` | Host API call | `OpsConfirm` hard gate | **YES** | Pure validation; refuses to proceed without confirm. |
| 11 | `ai/engine/ingestion/ops_workflow.py` `run_inference` | Host API call | `OpsConfirm` (requires confirm, else pending execution) | PARTIAL | Same caller-supplied-confirm caveat as #9. |
| 12 | `ai/engine/proactive/trigger_evaluator.py` (host SQL via `psycopg2`) | Host DB (external) | `ReadOnlyPG` — `conn.set_session(readonly=True)` + `SET statement_timeout` + `_qi()` identifier quoting | PARTIAL | Read-only session is a real control. Mitigating caveat: identifiers are quoted via `_qi` but the **threshold/window values are interpolated into the SQL text** (e.g. `INTERVAL '{days_ago_start} days'`), and any raw `where_clause` fragment is not re-parsed. Failures return `None` (fail-silent) — a broken probe looks like "no anomaly". |
| 13 | `ai/engine/proactive/context_assembler.py` `_execute_context_queries` | Host DB (external) | `ReadOnlyPG` + weak `startswith("SELECT")` allowlist + 5-query cap + `fetchmany(50)` | PARTIAL | `startswith("SELECT")` is a string-prefix check, not a SQL parser — `WITH ... SELECT` or a leading comment bypasses it. Read-only session still bounds the blast radius. |
| 14 | `ai/plugins/web_research.py:185` `WebResearch.execute` (`httpx` client at `:199`) | External system | **NONE** | **NO** | Outbound HTTP to arbitrary URLs. No domain allowlist, no egress guard, no SSRF check. Reachable from #7 with no pipeline. |
| 15 | `ai/plugins/code_execute.py:60` `CodeExecuteTool.execute` → `ai/code_sandbox.CodeSandbox` | Subprocess | `Sandbox` (subprocess with network / file-write / subprocess blocked) | PARTIAL | Genuine sandbox, but `requires_confirmation = False` (`:52`), so it runs unattended on every path including #7. |
| 16 | `ai/engine/skills/sandbox.py` `SafeExecutor.execute` (RestrictedPython eval→exec) | Subprocess / exec | `SafeExecutor` — whitelisted builtins/modules + thread timeout + forced termination | PARTIAL | In-process `exec` of generated code. RestrictedPython is a well-known escape-surface; the timeout is the second line of defence. |
| 17 | `ai/plugins/export_document.py:106` `ExportDocument.execute` (`:117` `mkdir`, `_write_docx`, `_write_xlsx`) | Filesystem | Planner mutation classification only — `_MUTATION_TOOL_NAMES = {"export_document"}` (`cognition/plan/planner.py:222`) | **NO** | `requires_confirmation = False` (`:102`). The *only* thing that gates it is a **plan-path-only** classification; from #7 there is no gate at all. Writes into `MEDIA_ROOT/ai_exports` under a timestamped name — unbounded growth, no size cap. |
| 18 | `ai/engine/llm/router.py` `route_chat` → provider HTTP | External system | `budget_hook` pre-check + provider config | PARTIAL | Budget is advisory and fail-open (see §3). No content egress guard beyond `_redact_secrets` on specific frames. |
| 19 | `ai/engine/proactive/delivery.py` `_push_websocket` (Redis publish + WS send + `delivered_at` commit) | External system + DB write | **NONE** | **NO** | Pushes insight content to a channel keyed only by `instance_id`. No per-user authorization on the push itself. |
| 20 | `ai/engine/knowledge/vector_store.py:110`/`:183` `upsert`, `:337` `delete`, `:349` `update` | External system (pgvector / Chroma) | **NONE** | **NO** | Vector rows are written with an `instance_id` metadata filter but no tenancy filter is applied *to the write*, and callers treat vector failures as best-effort (see #41, #56 notes). |

---

## PART 2 — Durable-write paths (DB rows, ledger, memory, accounting, audit, provenance)

| # | Path (file:function/class) | Effect type | Guard coverage TODAY | Fail-closed? | Notes |
|---|---|---|---|---|---|
| 21 | `ai/engine/agent/executor.py:108` `create_pending_execution` | DB write (`ToolExecution` pending) | `PendingExec` (the staging gate itself) | **YES** | Writes only a *proposal* row. The actual host call is released by #4. |
| 22 | `ai/engine/agent/tools.py:998` `execute_learn_fact` | DB write (`ToolExecution` pending) | `PendingExec` — pending execution only, no direct write | **YES** | Correct pattern: stages, never writes. |
| 23 | `ai/engine/agent/tools.py:1055` `execute_forget_fact` | DB write (`ToolExecution` pending) | `PendingExec` — pending execution only | **YES** | Same pattern as #22. |
| 24 | `ai/engine/agent/tools.py:1154` `execute_run_ops_workflow` | DB write (`ToolExecution` pending) | `PendingExec` + `dry_run` defaults to `True` + requires `user_token` | **YES** | Triple-layered: dry-run default, token requirement, pending staging. |
| 25 | `ai/engine/agent/tools.py:1247` `execute_draft_skill` | DB write (`Skill` insert — **direct**) | **NONE** | **NO** | **The code says so explicitly: "no confirmation gate."** A planner/hallucinated tool call creates a durable, user-authored skill row in one step. There is no staging, no critic, no ownership check. |
| 26 | `ai/engine/agent/tools.py:1342` `execute_invoke_skill` → `SkillsStore.update_stats` | DB write (`Skill` usage stats) | **NONE** | **NO** | Mutable accounting write with no guard. If the skill body is `code_snippet` it also reaches #16. |
| 27 | `ai/engine/skills/registry.py:29` `SkillRegistry.add` | DB write (`Skill` insert) | **NONE** | **NO** | Raw storage layer, commits immediately. Any caller that forgets to gate it writes a skill. |
| 28 | `ai/engine/skills/registry.py:91` `SkillRegistry.update_status` | DB write (`Skill` status, incl. promotion) | **NONE** | **NO** | Can set `instance_promoted` **without running the four critics** — the promotion gate lives in `gate.py`, not here. This is a promotion bypass. |
| 29 | `ai/engine/skills/crud.py:31` `SkillsStore.create_procedure` | DB write (`Skill` insert) | **NONE** | **NO** | Validates the body shape (`ProcedureBody`) then commits. No actor/permission check. |
| 30 | `ai/engine/skills/crud.py:131` `SkillsStore.update_stats` | DB write (`Skill` stats) | **NONE** | **NO** | In-place mutation + commit. |
| 31 | `ai/engine/skills/crud.py:163` `SkillsStore.promote_to_instance` | DB write (`Skill` promote) | **NONE** | **NO** | **Second promotion bypass** — sets `status="instance_promoted"` with no critics, in contrast to #32. |
| 32 | `ai/engine/skills/gate.py:475` `promote_skill` | DB write (`Skill` promote) | `Critics4` — but only `if skill.gate_status == "pending"`; raises `ValueError` if rejected | PARTIAL | When `gate_status != "pending"` the critics are **skipped entirely** and the skill is promoted. Combined with #28/#31 this is the weakest link in the promotion story. |
| 33 | `ai/engine/skills/gate.py:409` `admit_skill` → `~:660` `_write_log` | Durable write (`SkillAdmissionLog`) | `Critics4` (structural / harmlessness / consistency / marginal_gain) | PARTIAL | Three of the four critics **fail open on LLM/exam error** — see §3. Structural critic is the only deterministic one. |
| 34 | `ai/engine/skills/gate.py:508` `rollback_skill` | DB write (`Skill` deprecate) | **NONE** | **NO** | No reason validation, no actor check; a `reason` argument is accepted and only logged. |
| 35 | `ai/engine/skills/gate.py:528` `run_skill_admission` | DB write (`Skill` promote, batch) | `Critics4` + `SKILL_ADMISSION_ENABLED` flag | PARTIAL | Batch promotion to **instance-global** visibility. Per-skill exceptions are swallowed (`except Exception: logger.exception`), so a failing skill is merely skipped — it stays `pending`, it is not denied. |
| 36 | `ai/engine/memory/long_term.py` `store_fact` | DB write (`MemoryFact`) | **NONE** (noise reject + dedup only) | **NO** | Writes durable, retrievable facts. Dedup is a quality filter, not an authorization control. |
| 37 | `ai/engine/memory/long_term.py` `supersede_fact` / `update_fact` / `archive_fact` / `decay_unused` | DB write (+ vector delete for archive) | **NONE** | **NO** | Mutates and archives memory rows; `archive_fact` also issues a vector delete (#20). |
| 38 | `ai/engine/memory/episodic.py:64` `record_event` | DB write (`MemoryEpisodic`) + vector | **NONE** | **NO** | Also auto-links a causal predecessor by searching prior events — a write that reaches across episodes. |
| 39 | `ai/engine/memory/manager.py:172` `learn_from_correction` | DB write (`MemoryFact` + `MemoryEpisodic`) | **NONE** | **NO** | The chat-correction loop. Writes with `visibility="private"` when a `host_user_id` is known, `"shared"` otherwise — **defaults to shared visibility when identity is missing** (`memory/manager.py:~207`). |
| 40 | `ai/engine/knowledge/store.py:65` `store_entities` | DB write (`KnowledgeEntity`) | **NONE** | **NO** | Commits rows first, then best-effort vector upsert (`except Exception → logger.warning`). Durable write succeeds even when the index did not → silent divergence between DB and vector store. |
| 41 | `ai/engine/knowledge/store.py:243` `update_entity_description` | DB write (`KnowledgeEntity`) + vector | **NONE** | **NO** | Identical DB-first / vector-best-effort divergence. |
| 42 | `ai/engine/knowledge_graph/store.py:174` `add_node` | DB write (`KnowledgeNode`) | `allowlist` — `node_type`/`source` must be in `NODE_TYPES`/`SOURCE_TYPES`, else `ValueError` | PARTIAL | Good deny-by-default on the enum, but `instance_id`/`name` are taken from caller input with no authorization check, and the in-memory adjacency cache (#44–49) is updated unconditionally. |
| 43 | `ai/engine/knowledge_graph/store.py:233` `upsert_node` | DB write (`KnowledgeNode`) | `allowlist` | PARTIAL | Merges `properties` from caller input; same caveat as #42. |
| 44 | `ai/engine/knowledge_graph/store.py:330` `update_node` | DB write (`KnowledgeNode`) | **NONE** | **NO** | Arbitrary `updates` dict merged into the row and committed. |
| 45 | `ai/engine/knowledge_graph/store.py:404` `delete_node` | DB write (delete node + edges + vector) | **NONE** | **NO** | Cascading delete across node, edges and the vector collection; no ownership or reference check. |
| 46 | `ai/engine/knowledge_graph/store.py:449` `add_edge` | DB write (`KnowledgeEdge`) | `allowlist` (`RELATIONSHIP_TYPES`) | PARTIAL | Same caveat as #42. |
| 47 | `ai/engine/knowledge_graph/store.py:526` `update_edge` | DB write (`KnowledgeEdge` — supersede + insert) | **NONE** | **NO** | Writes a new edge and commits; history is preserved, authority is not checked. |
| 48 | `ai/engine/knowledge_graph/store.py:580` `delete_edge` | DB write (delete) | **NONE** | **NO** | — |
| 49 | `ai/engine/knowledge_graph/store.py:849` `store_table_profile` | DB write (node `properties`) | **NONE** | **NO** | Profile data merged and committed. |
| 50 | `ai/engine/knowledge_graph/cache_store.py:366` `QueryCacheStore._set` | Durable write (`KgCacheEntry`) | **NONE** — and the failure branch is `except Exception: logger.warning(...)` at `:417` | **NO** | Cache write is silently swallowed. Gate is only `KG_CACHE_ENABLED` for the read path. |
| 51 | `ai/engine/proactive/delivery.py` `deliver_insight` | DB write (`KgProactiveInsight`, `visibility="shared"`) + commit | **NONE** | **NO** | **Hardcoded `visibility="shared"`** — proactive insights generated from one user's data become instance-visible. |
| 52 | `ai/engine/proactive/delivery.py` `deliver_batch` | DB write + #19 | **NONE** | **NO** | Loop over #51/#53/#54 with no aggregate guard. |
| 53 | `ai/engine/proactive/delivery.py` `expire_stale_insights` | DB write (bulk update + commit) | **NONE** | **NO** | Bulk mutation with no dry-run. |
| 54 | `ai/engine/proactive/delivery.py` `_create_notification` | DB write (`Notification`) | **NONE** | **NO** | — |
| 55 | `ai/engine/ingestion/ops_workflow.py:464` `OpsRun(...)` | Durable write (provenance row) | `OpsConfirm` (the workflow's own gate) | PARTIAL | Provenance is good practice; the row is written by the same code path it describes, so a bypass of the gate also bypasses the provenance. |
| 56 | `ai/engine/cognition/turn/ledger.py` `record_stage` | Durable write (`TurnLedgerRow`, `begin_nested()`) | **NONE** — exception → `logger.warning` + `return None` | **NO** | **The turn ledger is fail-silent.** A DB error produces a turn with no ledger row and no signal. |
| 57 | `ai/engine/cognition/turn/execute.py:197` `_register_evidence` (`EvidenceRecord.objects.create` at `:251`) | Durable write (`EvidenceRecord`) | **NONE** — `except Exception: logger.warning(...)` at `:262` | **NO** | Evidence for a tool call is lost silently. Downstream grounding/citation then has nothing to cite while the turn reports success. |
| 58 | `ai/engine/llm/router.py` `_log_call` | Durable write (`LLMCallLog`, `begin_nested()`) | **NONE** — exception → `logger.debug` | **NO** | **Usage accounting is fail-silent.** Cost/budget reporting can silently under-count; `budget_hook` (#§3) then reads a `Run` row built on incomplete data. |
| 59 | `ai/engine/cognition/loop.py:126` `_persist_sweep_run` (`:149` `CognitionSweepRun`) | Durable write | **NONE** | **NO** | Background sweep bookkeeping. |
| 60 | `ai/engine/cognition/synthesis.py` `synthesize_insights` | DB write (`Insight`) | **NONE** | **NO** | Produces the rows that `deliver_insight` (#51) later publishes instance-wide. |
| 61 | `ai/engine/cognition/synthesis.py` `reflect_on_insights` / `learn_user_preferences` / `detect_recurring_queries` / `decay_stale_memories` | DB write (Insight / Memory / preference rows) | **NONE** | **NO** | `learn_user_preferences` writes inferred preferences derived from one user into memory — see #39 visibility caveat. |
| 62 | `ai/plans_service.py:775` `PlansService.create_plan` → `:804` `run.save()`, `:807` `RunStep.objects.create` | DB write (`Run` + `RunStep`) | owner-scoped (`user` argument) / CBAC | PARTIAL | Scoping is by the passed `user`; there is no re-authentication inside the service, so a caller that supplies the wrong `user` object bypasses it. |
| 63 | `ai/plans_service.py:372` `PlansService.store_artifact` → `:384` `RunArtifact.objects.create` + `artifact.file.save` | DB write + **filesystem** | `run_id` scoping | PARTIAL | Two effects (row + file). No size cap, no MIME assertion on write. |
| 64 | `ai/plans_service.py:1108` `approve_plan` → `:1119`/`:1131` `run.save` | DB write (`Run` status → runnable) | status precondition + ownership | PARTIAL | Converts a plan into a runnable task. |
| 65 | `ai/plans_service.py:2512` `confirm_step` / `:2648` `_finalize_run` | DB write (`RunStep` status, `Run` status) | `confirmation_token` match (`:2512`) | PARTIAL | This is the consent *release* — but it matches a token on the step row rather than a per-user consent record. |
| 66 | `ai/durable_service.py:378` `resume_run` | DB write (`RunStep`, `Run` status) | ownership (`_get_owned_run`) | PARTIAL | — |
| 67 | `ai/durable_service.py:452` `replay_run` | DB write (resets every `RunStep`, sets `Run` → `replaying`) + audit | `confirm is not True` → raises `PlanConsentError` (`durable_service.py:~466`) | **YES** | Explicit mandatory `confirm=True` with a hard raise — a model fail-closed gate. Good template for the rest of the platform. |
| 68 | `ai/engine_runtime.py:3736` `_create_execution_row` / `:3747` `_save_execution_row` | Durable write (`ToolExecution`) | **NONE** | **NO** | The workspace action path writes mutable execution rows (#7) with no guard. |
| 69 | `ai/plugins/save_work_objective.py:32` `SaveWorkObjective.execute` → `WorkObjective.objects.create` | DB write | **NONE** (`requires_confirmation = False` at `:29`) | **NO** | A durable, resumable investigation objective written straight to the DB. Reachable from #7 with no pipeline. It checks only that `host_user_id`/`instance_id` **exist**, not that the caller may write. |
| 70 | `ai/plugins/plan_task.py:63` `PlanTask.execute` → `PlansService.create_plan` | DB write (`Run` + `RunStep`) | owner resolution via `ctx.host_user_id` + CBAC in the service | PARTIAL | Returns `{"error": ...}` when the session user cannot be resolved (fail-visible, good). |
| 71 | `ai/plugins/plan_lifecycle.py:134` `EditPlan.execute` → `PlansService.edit_plan` | DB write (`Run`/`RunStep` rewritten) | ownership via `_resolve_owner` + service-level ownership | PARTIAL | `requires_confirmation = False` — plan mutation without consent. |
| 72 | `ai/plugins/plan_lifecycle.py:206` `ApprovePlan.execute` → `PlansService.approve_plan` | DB write (`Run` → runnable) | status guard (`PlanNotRunnableError`) + ownership | PARTIAL | `requires_confirmation = False` — approval is a state transition with no consent step, justified as "approval does not execute steps". |

---

## §3 Fail-open / fail-silent register

Every occurrence of `except ... : return True` / `passed = True` / silent durable-write failure found in the audited scope. **Each one converts a guard failure into an allowed effect.**

| File:line | Pattern | Effect of the fail-open |
|---|---|---|
| `ai/engine/agent/guardrails.py:412-496` `budget_hook` | `except Exception: logger.exception("budget_hook: failed to read Run row — passing")` then `return HookResult(action="pass")` | A DB error reading the `Run` row **permits** the tool call even when the budget may be exhausted. Fail-open by construction. |
| `ai/engine/agent/guardrails.py:106-120` `HookPipeline.run_before` | `except Exception: logger.exception(...); continue` | Any before-hook that crashes is **skipped**, and the remaining hooks decide. A crashing `consent_hook` does not block the mutation. |
| `ai/engine/agent/guardrails.py:122-152` `HookPipeline.run_after` | `except Exception: logger.exception(...); continue` | A crashing `redaction_hook` silently lets the raw result through to the client. |
| `ai/engine/cognition/turn/execute.py:376` (`_execute_single_tool`) | `except Exception: logger.exception("Before-hook pipeline error ...")` — **no return**, execution proceeds | The entire before-hook pipeline can fail and the tool still executes. Fail-open at the outermost layer of the primary chat path. |
| `ai/engine/cognition/turn/execute.py:470` | `except Exception: logger.exception("After-hook pipeline error ...")` | Redaction loss; raw tool output retained. |
| `ai/engine/cognition/plan/loop.py:34-44` `_tool_requires_confirmation` | `except Exception: return False` (docstring: *"a lookup failure is treated as read-only (fail-open for the guard)"*) | If the plugin registry cannot be imported, **every** confirmation tool is treated as read-only. Also: this function only knows about **registered plugins**, so static tools (`call_host_api`, `learn_fact`, `forget_fact`, `run_ops_workflow`) are never matched here. |
| `ai/engine/cognition/turn/verify.py` `VerificationWitness.verify` | ALL errors and parse failures → `passed=True`; opt-in via `PULSE_VERIFY_ENABLED` (default `False`) | Verification reports "passed" when it did not run, could not parse, or crashed. The `ledger.verification_passed` value is therefore not evidence of verification. |
| `ai/engine/skills/gate.py` `harmlessness_critic` | LLM error → `passed=True` (+ flag `harmlessness_llm_error`) | The safety critic of the skill gate defaults to **admit** on any LLM failure. |
| `ai/engine/skills/gate.py` `consistency_critic` | Eval error → `passed=True` | Consistency is asserted when it was never checked. |
| `ai/engine/skills/gate.py` `marginal_gain_check` | Error → `passed=True` | A useless skill is admitted. |
| `ai/engine/skills/gate.py` `structural_critic` | Disabled flag → pass; regex `_DANGEROUS_PATTERNS` is the only deterministic check | When the structural critic is disabled, the gate has **no** deterministic deny path at all. |
| `ai/engine/cognition/turn/ledger.py` `record_stage` | `except Exception: logger.warning(...); return None` | Turn ledger row silently absent. |
| `ai/engine/cognition/turn/execute.py:262` | `except Exception: logger.warning("EvidenceRecord write failed ...")` | Evidence silently absent. |
| `ai/engine/llm/router.py` `_log_call` | `except Exception: logger.debug(...)` | Usage accounting silently incomplete. |
| `ai/engine/knowledge_graph/cache_store.py:417` | `except Exception: logger.warning("cache_store._set error: %s", exc)` | Cache divergence; callers cannot tell a cache miss from a cache write failure. |
| `ai/engine/knowledge/store.py:~120`, `:~175` | `except Exception: logger.warning("Vector upsert/search failed ...")` | Vector store silently diverges from PostgreSQL. |
| `ai/engine/memory/manager.py` `retrieve_relevant_context` | three `except Exception: logger.warning/debug(...)` blocks | Retrieval silently returns fewer memory types; the turn proceeds with degraded grounding. |
| `ai/engine/proactive/trigger_evaluator.py` `_run` | `except Exception as e: logger.debug(...); return None` | A failed host probe is indistinguishable from "measured nothing / no anomaly" — **fail-silent in the direction of not firing**, which is safe for alerting but unsafe for assertions of correctness. |
| `ai/engine_runtime.py:3969` `_run_action_stream` | `except Exception as exc: logger.exception(...); result = {"error": str(exc)}` | Fail-**visible** (correct) — included for contrast: this is the pattern the guard paths should use. |
| `ai/engine/agent/mcp_client.py:259` | `except Exception as exc: logger.exception(...); return {"error": ...}` | Fail-**visible** but the effect may already have happened externally and cannot be rolled back. |
| `ai/engine/proactive/delivery.py` (`_push_websocket`) | Disposition/`delivered_at` commit wrapped in a best-effort handler | An insight can be published but never marked delivered, or vice versa. |

**Structural gap (highest-severity single finding):**

> `ai/engine/cognition/plan/loop.py:201` constructs
> `ExecuteWitness(executor=_host_executor, knowledge_store=self.knowledge_store)`
> — **without `hook_pipeline`**.
> `ai/engine/cognition/turn/runner.py:1874-1886` constructs the *same* witness with
> `hook_pipeline = build_default_pipeline()` and passes it in.
>
> Consequence: `_execute_single_tool` (`cognition/turn/execute.py:336`) guards with `if hook_pipeline is not None:` — so on the **plan / ReAct-loop path** (`call_host_api`, `export_document`, `code_execute`, MCP, plugins) **every guardrail hook is skipped**: `consent_hook`, `readonly_worker_hook`, `tool_safety_hook`, `rate_limit_hook`, `budget_hook`, `redaction_hook`. The plan path is the *more* privileged path (it executes multi-step plans with mutations), and it is the *less* guarded one.

---

## §4 Guard mechanisms that exist today

Distinct mechanisms actually present in the codebase (26):

**Consent / staging**
1. `HostAPIExecutor.requires_confirmation` — `agent/executor.py:96`; unknown endpoint ⇒ `True` (deny-by-default).
2. `create_pending_execution` — `agent/executor.py:108`; stages instead of sending.
3. `confirm_execution` + `ConfirmOwnership` (P0-2) — `agent/executor.py`; ownership-checked release.
4. `consent_hook` — `agent/guardrails.py:156`; blocks non-GET `call_host_api` without a matching `ToolExecution`.
5. `PlanConsentGate` — `cognition/plan/loop.py:~806`; sets `paused` + issues a `confirmation_token`.
6. `confirm is not True → PlanConsentError` — `durable_service.py:~466`; the clearest model fail-closed gate.
7. `OpsConfirm` — `ingestion/ops_workflow.py`; dry-run-first, `confirm`-required writes, `is_managed` refusal.

**Hook pipeline**
8. `HookPipeline.run_before` / `run_after` — `agent/guardrails.py:106`/`:122`.
9. `build_default_pipeline()` — `agent/guardrails.py:499`; wires consent → readonly_worker → tool_safety → rate_limit → budget, then redaction.
10. `readonly_worker_hook` — `agent/guardrails.py:213`; restricts worker agents.
11. `tool_safety_hook` + `_search_dangerous_patterns` — `agent/guardrails.py:387`/`:359`; regex denylist on arguments.
12. `rate_limit_hook` — `agent/guardrails.py:303`; warns (does not block).
13. `budget_hook` — `agent/guardrails.py:412`; cancels on `Run.budget_exceeded`.
14. `redaction_hook` — `agent/guardrails.py:253`; after-stage output redaction.

**Critic / verifier tier**
15. `CriticWitness.review` mutation veto — `cognition/turn/critic.py:104` (non-GET, unconfirmed ⇒ hard veto) and `:157` (`is_mutation` without token ⇒ hard veto).
16. `PlannerMutationClass` — `cognition/plan/planner.py:222`; deterministic `is_mutation` override because the LLM marks mutation steps `False`.
17. `_plugin_input_schemas` + `_schema_field_violations` — `cognition/plan/planner.py:238+`; JSON-schema check on tool args.
18. `VerificationWitness` — `cognition/turn/verify.py`; opt-in, **fail-open** (see §3).
19. `Critics4` skill gate — `skills/gate.py` (structural deterministic; three fail-open).
20. `NullOutputGuard` — `cognition/turn/execute.py:~485`; refuses to mark a confirmation tool with null output as "completed" (phantom-success fix).

**Structural / platform guards**
21. `GuardChain` + `ScopeGuard` / `AccessGuard` / `DataIsolationGuard` / `MutationGuard` / `AuditTrail` — `ai/guards.py:320`/`:29`/`:55`/`:96`/`:199`/`:269`.
22. `scope_q` tenancy triplet (`global`/`shared`/`private`) — `ai/store.py:76`.
23. `_apply_tenancy_filter` — **real** implementation at `ai/engine/core/models.py:19`; the `DjangoStore` method at `ai/store.py:1356` is a **NO-OP that returns `qs` unchanged** (all 6 call sites at `store.py:1027, 1097, 1148, 1152, 1187, 1197, 1271` therefore filter nothing).
24. `StoreFailClosed` — `ai/store.py:1382`; refuses to start when `AI_STORE_BACKEND` is unset (PULSE P1-01).
25. `HostJWT` per-user token, no service-account fallback — `agent/executor.py:83`.
26. `SafeExecutor` (RestrictedPython + timeout) and `CodeSandbox` (no net/fs-write/subprocess) — `skills/sandbox.py`, `ai/code_sandbox.py`.

Additional bounded-context controls: `ReadOnlyPG` (readonly session + `statement_timeout`) in `trigger_evaluator.py` / `context_assembler.py`; `GENERATIONS.is_cancelled` cancel check in `_run_action_stream`; `_redact_secrets` on emitted frames.

---

## Summary

**(a) Total paths counted: 72**
- Part 1 — host effects: **20** (#1–#20)
- Part 2 — durable writes: **52** (#21–#72)

**(b) Paths with NO guard at all: 40 of 72 (56%)**
Rows: `#2, #5, #6, #7, #14, #17, #19, #20, #25, #26, #27, #28, #29, #30, #31, #34, #36, #37, #38, #39, #40, #41, #44, #45, #47, #48, #49, #50, #51, #52, #53, #54, #56, #57, #58, #59, #60, #61, #68, #69`.

Breakdown of the remaining 32:
- **Fail-closed (YES): 7** — `#4, #10, #21, #22, #23, #24, #67`
- **Partial: 25**

Notably, **all 7 fail-closed paths are in the "stage a proposal" or "hard-refuse without a boolean" families.** Not one *execution* path for a non-staged effect (MCP, external HTTP, filesystem, subprocess, direct DB write) is fail-closed.

**(c) Distinct guard mechanisms that exist today: 26** (enumerated in §4).

**(d) Top 5 riskiest paths**

1. **`ai/engine_runtime.py:3756` `_run_action_stream`** — the workspace "Run tool/agent" dispatcher executes *any* registered executor (MCP, `export_document`, `code_execute`, plugins) with **no `HookPipeline`, no `CriticWitness`, no pre-execution consent**; it is also the entry point through which #5, #6 and #17 are reached.
2. **`ai/engine/agent/mcp_client.py:202` `MCPClient.execute_tool`** — arbitrary third-party tool invocation with `session.call_tool(...)` and **zero** allowlist, argument inspection, confirmation or hook; effect is external and irreversible.
3. **`ai/engine/agent/tools.py:1247` `execute_draft_skill`** — a **direct, ungated durable write** of a `Skill` row; the code comment states it has "no confirmation gate", so a single hallucinated tool call persists an executable artifact.
4. **`ai/engine/cognition/plan/loop.py:201` `ExecuteWitness` constructed without `hook_pipeline`** — the plan/ReAct path (the path that actually performs multi-step mutations) silently bypasses **all six** guardrail hooks, while the chat path adds them (`runner.py:1884`).
5. **`ai/engine/proactive/delivery.py` `deliver_insight`** — writes proactive insights with **hardcoded `visibility="shared"`**, promoting data derived from one user's activity to instance-wide visibility, with no guard and no per-user authorization.

**Runner-up (must-fix, not ranked above because it degrades confidence rather than permitting a new effect):** the fail-open cluster in §3 — `budget_hook` → pass, `HookPipeline` hook crash → continue, `_execute_single_tool` before-hook crash → execute anyway, `verify.py` → `passed=True` on every error, three of four `skills/gate.py` critics → `passed=True` on error, plus the fail-silent ledger / evidence / usage-accounting writes (`ledger.py`, `execute.py:262`, `llm/router.py:_log_call`) and the `DjangoStore._apply_tenancy_filter` NO-OP (`ai/store.py:1356`) that makes six tenancy call sites inert.

---

## Appendix — Files traced

`ai/engine/agent/{tools,executor,guardrails,plugins,workers,mcp_client}.py` · `ai/engine/cognition/turn/{runner,critic,execute,ledger,verify}.py` · `ai/engine/cognition/plan/{loop,planner}.py` · `ai/engine/cognition/{loop,synthesis}.py` · `ai/engine/skills/{gate,sandbox,crud,registry,router}.py` · `ai/engine/memory/{manager,long_term,episodic}.py` · `ai/engine/knowledge/{store,vector_store}.py` · `ai/engine/knowledge_graph/{store,cache_store}.py` · `ai/engine/proactive/{delivery,trigger_evaluator,context_assembler,loop}.py` · `ai/engine/ingestion/ops_workflow.py` · `ai/engine/llm/router.py` · `ai/engine/core/models.py` · `ai/engine_runtime.py` · `ai/guards.py` · `ai/store.py` · `ai/plans_service.py` · `ai/durable_service.py` · `ai/plugins/{code_execute,create_dq_rule,export_document,save_work_objective,plan_task,plan_lifecycle,web_research}.py`
