# P2-05 — Dual-ORM Inventory (SQLAlchemy → Django)

Status: research-only. No code changed.

Goal: enumerate the remaining SQLAlchemy usage so the team can retire it and run
`pip uninstall sqlalchemy` (remediation plan P2-05).

**Headline numbers**

| Metric | Count |
|---|---|
| Engine SQLAlchemy models | **49** (34 core + 15 knowledge-graph) |
| Engine tables | **49** |
| Django mirror models | **49** (all 49 engine classes have a 1:1 Django mirror) |
| Engine models **missing** a Django mirror | **0** |
| Django-native models (no engine counterpart) | **19** |
| Files importing `sqlalchemy` at runtime | **17** (14 engine + `store.py` + `catalog_service.py` + 1 test file) |

---

## Section 1 — Engine SQLAlchemy model inventory

Both files use SQLAlchemy 2.0 style: `DeclarativeBase` + `Mapped` /
`mapped_column`. `knowledge_graph/models.py` imports `Base` from
`core/models.py`, so all 49 tables share one registry.

Type shorthand: `Text`, `Int`, `Float`, `Bool`, `DT` (DateTime). `?` = nullable,
`(PK)` = primary key.

### 1.1 `backend/ai/engine/core/models.py` (34 models)

| # | Class | `__tablename__` | Columns |
|---|---|---|---|
| 1 | `Instance` | `instances` | id Text(PK), name Text(unique), display_name Text, host_db_url Text, host_api_url Text, host_api_token Text?, status Text, config Text?, created_at DT, updated_at DT |
| 2 | `Conversation` | `conversations` | id(PK), instance_id, user_identifier?, host_user_id?, visibility, page_context?, title?, mode, archived Bool, compaction_summary?, started_at DT, ended_at DT? |
| 3 | `Message` | `messages` | id(PK), conversation_id, role, content, metadata_json?, host_user_id?, visibility, timestamp DT |
| 4 | `MemoryLongTerm` | `memory_long_term` | id(PK), instance_id, category, content, source?, confidence Float, decay_at DT?, archived Bool, host_user_id?, visibility, valid_from DT?, valid_to DT?, superseded_by?, created_at DT, last_used DT, use_count Int |
| 5 | `MemoryEpisodic` | `memory_episodic` | id(PK), instance_id, event_type, summary, details?, causal_chain?, caused_by_episode_id?, relevance_score Float, last_accessed_at DT?, archived Bool, host_user_id?, visibility, occurred_at DT, learned_at DT |
| 6 | `KnowledgeEntity` | `knowledge_entities` | id(PK), instance_id, entity_type, name, schema_json?, semantic_description?, relationships?, last_introspected DT |
| 7 | `SystemSnapshot` | `system_snapshots` | id(PK), instance_id, snapshot_data?, diff_from_previous?, summary?, taken_at DT |
| 8 | `Notification` | `notifications` | id(PK), instance_id, severity, title, body?, host_user_id?, visibility, acknowledged Bool, created_at DT |
| 9 | `Feedback` | `feedback` | id(PK), message_id, rating Int, correction_text?, host_user_id?, visibility, created_at DT |
| 10 | `UserKey` | `user_keys` | id(PK), instance_id, username, display_name?, email?, roles_json?, key_prefix, key_hash(unique), host_token?, is_active Bool, created_at DT, last_used_at DT? |
| 11 | `Insight` | `insights` | id(PK), instance_id, insight_type, title, content, evidence?, confidence Float, archived Bool, host_user_id?, visibility, created_at DT, superseded_by? |
| 12 | `ToolExecution` | `tool_executions` | id(PK), conversation_id, tool_name, input_params?, output?, status, confirmed_by_user Bool, host_user_id?, visibility, executed_at DT? |
| 13 | `LLMCallLog` | `llm_call_logs` | id(PK), instance_id, conversation_id, model, llm_calls Int, total_tokens Int, cost_usd Float, duration_ms Int, created_at DT |
| 14 | `ConversationContextRecord` | `conversation_context_records` | conversation_id(PK), instance_id, session_json, updated_at DT |
| 15 | `AuditLog` | `audit_log` | id(PK), instance_id?, actor, actor_type, action, target?, detail?, created_at DT |
| 16 | `OpsRun` | `ops_runs` | id(PK), instance_id, workflow, status, dry_run Bool, csv_filename?, input_hash?, dataset_ref?, engine_ref?, rows_ingested Int, rows_skipped Int, date_start?, date_end?, model_version?, output_location?, steps_json?, provenance_json?, error?, host_user_id?, visibility, created_at DT, completed_at DT? |
| 17 | `CsvUpload` | `csv_uploads` | id(PK), instance_id, conversation_id?, host_user_id?, filename?, content, row_count Int, created_at DT |
| 18 | `VectorEmbedding` | `vector_embeddings` | id(PK), collection, instance_id, document, metadata_json?, embedding_json?, created_at DT |
| 19 | `TurnLedgerRow` | `turn_ledger` | id(PK), turn_id, instance_id, host_user_id?, conversation_id, stage, stage_index Int, payload_json?, latency_ms Float?, tokens_used Int?, model_used?, verdict?, flags_json?, created_at DT |
| 20 | `Run` | `runs` | id(PK), instance_id, conversation_id, host_user_id?, user_message, status, plan_json?, final_response?, total_tokens Int, total_llm_calls Int, total_latency_ms Float?, working_notes?, token_budget Int?, tokens_consumed Int, fan_out_justification?, worker_budgets_json?, budget_exceeded Bool, created_at DT, updated_at DT, completed_at DT? |
| 21 | `RunStep` | `run_steps` | id(PK), run_id, step_index Int, intent, tool_name?, tool_args_json?, depends_on_json?, status, draft_text?, critic_verdict?, critic_flags_json?, tool_output_json?, error?, latency_ms Float?, confirmation_token?, created_at DT, updated_at DT |
| 22 | `Trajectory` | `trajectory` | id(PK), run_id, instance_id, host_user_id?, conversation_id, user_message, task_intent?, plan_json?, tool_calls_json?, stages_json?, status, final_response?, user_feedback?, total_tokens Int, total_latency_ms Float?, skill_candidates_json?, consolidation_round Int, extracted_at DT?, created_at DT |
| 23 | `Agent` | `agents` | id(PK), instance_id, name, role, tool_set_json?, playbook_blocks_json?, model_override?, max_turns Int, is_active Bool, created_at DT, updated_at DT |
| 24 | `AgentHandoff` | `agent_handoffs` | id(PK), from_agent_id, to_agent_id, description?, max_parallel Int, created_at DT |
| 25 | `KgNode` | `kg_node` | id(PK), instance_id, type, name, canonical_ref?, properties, embedding?, source, confidence Float, created_at DT, updated_at DT |
| 26 | `KgEdge` | `kg_edge` | id(PK), instance_id, source_node_id, target_node_id, edge_type, properties, confidence Float, source, created_at DT |
| 27 | `KgProvenance` | `kg_provenance` | id(PK), node_id(unique), source_type, source_ref, extracted_at DT, extraction_batch? |
| 28 | `Skill` | `skill` | id(PK), instance_id, name, description, signature, body, kind, status, author_user_id, promoted_at DT?, promoted_by?, usage_count Int, success_rate Float, avg_latency_ms Float, last_executed_at DT?, preconditions?, provenance_run_ids?, gate_status?, created_at DT, updated_at DT |
| 29 | `SkillAdmissionLog` | `skill_admission_log` | id(PK), skill_id, instance_id, structural_passed Bool, harmlessness_passed Bool, consistency_passed Bool, marginal_gain_passed Bool, structural_flags_json?, harmlessness_flags_json?, consistency_flags_json?, marginal_gain_details_json?, verdict, rejected_by?, admitted_by?, created_at DT |
| 30 | `PromptVersion` | `prompt_versions` | id(PK), instance_id, prompt_text, content_hash Text(16), synthesized_at DT, is_active Bool, score Float?, improvement_round Int, parent_version_id?, created_at DT |
| 31 | `PromptEval` | `prompt_evals` | id(PK), prompt_version_id, instance_id, conversation_id?, query_text, response_text?, tool_calls_made, tool_calls_expected?, task_completion Bool?, relevance_score Float?, user_feedback Int?, eval_source, created_at DT |
| 32 | `PlaybookBlock` | `playbook_blocks` | id(PK), instance_id, block_type, title, content, version Int, is_active Bool, priority Int, provenance?, created_at DT, updated_at DT |
| 33 | `TaskExecution` | `task_executions` | id(PK), instance_id, task_type, external_task_id, status, request_payload, response_payload, error_message?, execution_ms Int, created_at DT |
| 34 | `PulseUser` | `pulse_users` | id(PK), instance_id, username, password_hash, display_name?, created_at DT, last_login_at DT? |

### 1.2 `backend/ai/engine/knowledge_graph/models.py` (15 models)

| # | Class | `__tablename__` | Columns |
|---|---|---|---|
| 1 | `KnowledgeNode` | `knowledge_nodes` | id(PK), instance_id, node_type, name, description, properties, source, confidence Float, verified Bool, verification_date DT?, module_id?, valid_from DT?, valid_to DT?, created_at DT, updated_at DT, last_accessed DT?, access_count Int |
| 2 | `KnowledgeEdge` | `knowledge_edges` | id(PK), instance_id, source_node_id, target_node_id, relationship, properties, confidence Float, source, weight Float, valid_from DT?, valid_to DT?, created_at DT, updated_at DT |
| 3 | `KgQueryFeedback` | `kg_query_feedback` | id(PK), instance_id, question, sql_final, succeeded Bool, retry_count Int, error_category, duration_ms Int, row_count Int, shape, created_at DT |
| 4 | `KgCacheEntry` | `kg_cache_entries` | id(PK), instance_id, cache_layer, cache_key, utterance, sql_executed, result_json, table_tags, hit_count Int, ttl_seconds Int, expires_at DT, created_at DT |
| 5 | `KgRecoveryLog` | `kg_recovery_log` | id(PK), instance_id, question, error_type, recovery_type, original_sql, repaired_sql, succeeded Bool, correction_description, retry_count Int, created_at DT |
| 6 | `KgFeedbackRecord` | `kg_feedback_records` | id(PK), instance_id, conversation_id, message_id, signal_type, user_id, original_utterance, resolved_utterance, generated_sql, corrected_sql?, user_comment?, quality_score Float, created_at DT |
| 7 | `KgGoldenPair` | `kg_golden_pairs` | id(PK), instance_id, question, sql, source_feedback_id?, review_status, reviewed_by?, reviewed_at DT?, tags, created_at DT |
| 8 | `KgReviewItem` | `kg_review_items` | id(PK), instance_id, category, title, description, evidence_json, frequency Int, status, resolution?, reviewed_by?, created_at DT, updated_at DT |
| 9 | `KgQualityScore` | `kg_quality_scores` | id(PK), instance_id, dimension, dimension_value, date, score Float, sample_count Int, created_at DT |
| 10 | `KgQueryPlan` | `kg_query_plans` | id(PK), instance_id, conversation_id, original_utterance, pattern, step_count Int, status, synthesis_instruction, result_summary?, total_duration_ms Int, total_llm_calls Int, created_at DT, completed_at DT? |
| 11 | `KgPlanStep` | `kg_plan_steps` | id(PK), plan_id, step_order Int, intent, depends_on, generated_sql?, result_json?, branch_condition?, status, error_message?, duration_ms Int, created_at DT |
| 12 | `KgDomainPack` | `kg_domain_packs` | id(PK), instance_id, version Int, status, trigger, pack_json, changelog_json, created_at DT |
| 13 | `KgBootstrapRun` | `kg_bootstrap_runs` | id(PK), instance_id, trigger, crawlers_run, domain_pack_id?, previous_pack_id?, status, error_message?, duration_ms Int, created_at DT |
| 14 | `KgProactiveTrigger` | `kg_proactive_triggers` | id(PK), instance_id, name, category, description, severity, enabled Bool, condition_json, data_sources_json, context_queries_json, recommended_actions_json, recipients_json, cooldown_seconds Int, last_fired_at DT?, fire_count Int, source, created_at DT |
| 15 | `KgProactiveInsight` | `kg_proactive_insights` | id(PK), instance_id, visibility, trigger_id?, insight_type, severity, title, narrative, context_json, recommended_actions_json, disposition, dismissed_reason?, group_id?, delivery_channel, delivered_at DT?, expires_at DT?, created_at DT |

---

## Section 2 — Django mirror inventory

Mirrors live in `backend/ai/models/` under `app_label="ai"`. No `db_table` is
set anywhere, so **every** Django table uses the default
`ai_<classname_lowercase>` (confirmed by `store.py::_run_django_text`, which
maps `skill`→`ai_skill`, `vector_embeddings`→`ai_vectorembedding`, etc.).

All 49 mirror models inherit `AppScopeMixin` (see `models/base.py`) which adds
4 CBAC columns: `app_identifier` (CharField 64, default `"carbon"`),
`org_unit_id` (BigInt, null), `host_user_id` (CharField 255, null),
`visibility` (CharField 16, default `"private"`).

### 2.1 `backend/ai/models/core.py` — 34 mirrors (engine core) + 10 Django-native

Mirror classes (1:1 by name): `Instance`, `Conversation`, `Message`,
`MemoryLongTerm`, `MemoryEpisodic`, `KnowledgeEntity`, `SystemSnapshot`,
`Notification`, `Feedback`, `UserKey`, `Insight`, `ToolExecution`,
`LLMCallLog`, `ConversationContextRecord`, `AuditLog`, `OpsRun`, `CsvUpload`,
`VectorEmbedding`, `TurnLedgerRow`, `Run`, `RunStep`, `Trajectory`, `Agent`,
`AgentHandoff`, `KgNode`, `KgEdge`, `KgProvenance`, `Skill`,
`SkillAdmissionLog`, `PromptVersion`, `PromptEval`, `PlaybookBlock`,
`TaskExecution`, `PulseUser`.

Django-native (no engine SQLAlchemy counterpart): `AIAnomalyWatch`,
`RunArtifact`, `PlanTemplate`, `RunSchedule`, `WorkObjective`,
`EvidenceRecord`, `CognitionSweepRun`, `AcceptanceReport`, `LearningOutcome`,
`AISubagent`. These use real Django `ForeignKey`/`ManyToManyField`/`FileField`
and are out of scope for the SQLAlchemy migration.

### 2.2 `backend/ai/models/knowledge_graph.py` — 15 mirrors

`KnowledgeNode`, `KnowledgeEdge`, `KgQueryFeedback`, `KgCacheEntry`,
`KgRecoveryLog`, `KgFeedbackRecord`, `KgGoldenPair`, `KgReviewItem`,
`KgQualityScore`, `KgQueryPlan`, `KgPlanStep`, `KgDomainPack`,
`KgBootstrapRun`, `KgProactiveTrigger`, `KgProactiveInsight` — all 1:1 mirrors.

### 2.3 Django-native models elsewhere (no engine counterpart)

| File | Classes |
|---|---|
| `models/workspace.py` | `AIConversation`, `AIMessage`, `AIArtifact`, `AIGeneration`, `ConversationCheckpoint`, `AIUserProfile` |
| `models/catalog.py` | `ModelCatalog` |
| `models/feedback.py` | `DqFeedbackEvent` |
| `models/pdp.py` | `PolicyDecisionRow` |

> Note: the task mentioned `models/kg.py` and `models/knowledge.py` — those
> files do not exist. The KG mirrors are in `models/knowledge_graph.py`.

---

## Section 3 — Schema diff (per model)

### Legend of systematic differences (apply broadly)

- **S1 `id`**: engine `Text` (UUID string) ↔ Django `CharField(max_length=36)`. (real type change: `TEXT` vs `VARCHAR(36)`)
- **S2 CBAC extras**: Django adds `app_identifier` + `org_unit_id` (+ `host_user_id`/`visibility` where the engine model lacks them) via `AppScopeMixin`.
- **S3 `host_user_id`**: engine `Text` ↔ Django `CharField(max_length=255)` (where the engine has it).
- **S4 `visibility`**: engine `Text` ↔ Django `CharField(max_length=16)` (where the engine has it).
- **S5 JSON**: engine stores JSON as `Text` ↔ Django `JSONField` (deliberate; values are still JSON).
- **S6 timestamps**: engine `DateTime(server_default=func.now())` or `default=utcnow` ↔ Django `DateTimeField(auto_now_add=True)` / `auto_now=True` (equivalent semantics).

### 3.1 Core models

| Model | Engine-only | Django-only | Type mismatches |
|---|---|---|---|
| `Instance` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), config (S5), created/updated (S6) |
| `Conversation` | — | app_identifier, org_unit_id (S2) | id (S1), host_user_id (S3), visibility (S4), timestamps (S6) |
| `Message` | — | app_identifier, org_unit_id (S2) | id (S1), metadata_json (S5), host_user_id (S3), visibility (S4) |
| `MemoryLongTerm` | — | app_identifier, org_unit_id (S2), **`memory_type`** CharField(20) | id (S1), host_user_id (S3), visibility (S4) |
| `MemoryEpisodic` | — | app_identifier, org_unit_id (S2) | id (S1), details (S5), host_user_id (S3), visibility (S4) |
| `KnowledgeEntity` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), schema_json + relationships (S5) |
| `SystemSnapshot` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), snapshot_data + diff_from_previous (S5) |
| `Notification` | — | app_identifier, org_unit_id (S2) | id (S1), host_user_id (S3), visibility (S4; Django redeclares default `"shared"`) |
| `Feedback` | — | app_identifier, org_unit_id (S2) | id (S1), host_user_id (S3), visibility (S4) |
| `UserKey` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), roles_json (S5) |
| `Insight` | — | app_identifier, org_unit_id (S2) | id (S1), evidence (S5), host_user_id (S3), visibility (S4; Django redeclares default `"shared"`) |
| `ToolExecution` | — | app_identifier, org_unit_id (S2) | id (S1), input_params + output (S5), host_user_id (S3), visibility (S4) |
| `LLMCallLog` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1) |
| `ConversationContextRecord` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | conversation_id (S1), session_json (S5) |
| `AuditLog` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), detail (S5) |
| `OpsRun` | — | app_identifier, org_unit_id (S2) | id (S1), steps_json + provenance_json (S5), host_user_id (S3), visibility (S4) |
| `CsvUpload` | — | app_identifier, org_unit_id, **visibility** (S2) | id (S1), host_user_id (S3) |
| `VectorEmbedding` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), metadata_json + embedding_json (S5) |
| `TurnLedgerRow` | — | app_identifier, org_unit_id, **visibility** (S2) | id (S1), payload_json + flags_json (S5), host_user_id (S3) |
| `Run` | — | app_identifier, org_unit_id, **visibility** (S2) | id (S1), plan_json + working_notes + worker_budgets_json (S5), host_user_id (S3) |
| `RunStep` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), tool_args_json + depends_on_json + critic_flags_json + tool_output_json (S5) |
| `Trajectory` | — | app_identifier, org_unit_id, **visibility** (S2) | id (S1), plan_json + tool_calls_json + stages_json + skill_candidates_json (S5), host_user_id (S3) |
| `Agent` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), tool_set_json + playbook_blocks_json (S5) |
| `AgentHandoff` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1) |
| `KgNode` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), properties + embedding (S5) |
| `KgEdge` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), properties (S5) |
| `KgProvenance` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1) |
| `Skill` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), signature + body (S5), **gate_status** nullable-Text vs `TextField(default="pending", blank=True)` (null-vs-not-null) |
| `SkillAdmissionLog` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), 4× `*_flags_json` + `marginal_gain_details_json` (S5) |
| `PromptVersion` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), content_hash `Text(16)` vs `CharField(16)` (equivalent) |
| `PromptEval` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), tool_calls_made + tool_calls_expected (S5) |
| `PlaybookBlock` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1) |
| `TaskExecution` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), request_payload + response_payload (S5) |
| `PulseUser` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1) |

### 3.2 Knowledge-graph models

| Model | Engine-only | Django-only | Type mismatches |
|---|---|---|---|
| `KnowledgeNode` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), properties (S5) |
| `KnowledgeEdge` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), properties (S5) |
| `KgQueryFeedback` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1) |
| `KgCacheEntry` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), result_json + table_tags (S5) |
| `KgRecoveryLog` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1) |
| `KgFeedbackRecord` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1) |
| `KgGoldenPair` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), tags (S5) |
| `KgReviewItem` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), evidence_json (S5) |
| `KgQualityScore` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1) |
| `KgQueryPlan` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), result_summary (S5) |
| `KgPlanStep` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), depends_on + result_json (S5) |
| `KgDomainPack` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), pack_json + changelog_json (S5) |
| `KgBootstrapRun` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), crawlers_run (S5) |
| `KgProactiveTrigger` | — | app_identifier, org_unit_id, host_user_id, visibility (S2) | id (S1), condition_json + data_sources_json + context_queries_json + recommended_actions_json + recipients_json (S5) |
| `KgProactiveInsight` | `visibility` default `"shared"` | app_identifier, org_unit_id, **host_user_id** (S2) | id (S1), context_json + recommended_actions_json (S5); **visibility default mismatch** — engine `"shared"` vs Django mixin `"private"` (Django does NOT redeclare it, unlike `Notification`/`Insight`) |

### Notable diff highlights

1. **CBAC columns are Django-only.** `AppScopeMixin` injects `app_identifier`,
   `org_unit_id` (+ `host_user_id`/`visibility`) onto *every* table. The engine
   layer only carries `host_user_id`/`visibility` on 13 of 49 models
   (tenancy-aware ones); the rest get them purely on the Django side.
2. **JSON as `Text` → `JSONField`** is the most pervasive type change (~50 columns).
3. **`MemoryLongTerm.memory_type`** is a Django-only column (no engine
   counterpart) — likely a Django-side extension not yet back-ported to the engine.
4. **`KgProactiveInsight.visibility`** default drifts: engine `"shared"` vs
   Django `"private"`. Runtime is currently saved by the store copying the
   engine's attribute, but a direct Django insert would default to `"private"`.
5. **`Skill.gate_status`** nullability differs (engine nullable vs Django
   `default="pending"`, not null).

---

## Section 4 — `sqlalchemy` import classification

Classification: **(a)** real query construction, **(b)** type-hint only
(`AsyncSession` in annotations), **(c)** docstring/comment only.

### (a) Real query construction (block `pip uninstall sqlalchemy`)

| File:line | Import / usage |
|---|---|
| `engine/core/models.py:11-12` | `from sqlalchemy import Boolean, CheckConstraint, …, and_, func, or_`; `from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column` — 34 model classes |
| `engine/knowledge_graph/models.py:11-12` | `from sqlalchemy import …`; `from sqlalchemy.orm import Mapped, mapped_column` — 15 model classes |
| `engine/agent/executor.py:12-13` | `select, update` — writes `ToolExecution` rows + updates (DML via `db.execute`) |
| `engine/agent/guardrails.py:431` | `from sqlalchemy import select` (local) — budget hook reads `Run.tokens_consumed/token_budget` |
| `engine/agent/reasoning.py:1139` | `from sqlalchemy import select` (local) — `_fetch_golden_pairs` reads `KgGoldenPair` |
| `engine/agent/registry.py:21` | `select` — `AgentRegistry` fan-out (`select(Agent)`, `select(AgentHandoff)`) |
| `engine/agent/tools.py:1180` | `from sqlalchemy import select` (local) — reads staged `CsvUpload` by id |
| `engine/llm/prompt_eval.py:12-13` | `select, func` — eval queries (`select(PromptVersion)`, `func.count` etc.) |
| `engine/llm/prompt_optimizer.py:13-14,242` | `select`, `update` — deactivate/activate prompt versions |
| `engine/skills/crud.py:14-15` | `select` — `SkillsStore` procedure CRUD |
| `engine/skills/gate.py:31-32` | `select` — admission-gate critics read/write `SkillAdmissionLog` |
| `engine/skills/registry.py:9-10` | `and_, or_, select` — `SkillRegistry` filtered skill search |
| `engine/knowledge/vector_store.py:19-20` | `text` — pgvector backend runs raw SQL (`<=>`, `<->`) via `db.execute(text(...))` |
| `catalog_service.py:30` | `select` — `CatalogService` reads `Agent`/`AgentHandoff`/`Skill`/`SkillAdmissionLog` (outside `engine/`) |
| `store.py:220,235,290,309,329,904,1147,1149` | `Table`, `sqlalchemy.sql.elements`, `sqlalchemy as sa`, `TextClause` — the Django Store's statement translator |

### (b) Type-hint only (`AsyncSession` in annotations)

| File:line | Usage |
|---|---|
| `engine/llm/prompt_synthesizer.py:24` | only `from sqlalchemy.ext.asyncio import AsyncSession`; used as `db: AsyncSession` in signatures (no `select`/`text`/`func`) |

The following files also *annotate* `AsyncSession` but are already classed as
(a) above (their real-query imports dominate): `executor.py:13`,
`prompt_eval.py:13`, `prompt_optimizer.py:14`, `skills/crud.py:15`,
`skills/gate.py:32`, `skills/registry.py:10`, `vector_store.py:20`.

### (c) Docstring / comment only (safe to `pip uninstall` today)

| File:line | Note |
|---|---|
| `engine/agent/budget.py:56` | `db_session: Async SQLAlchemy session.` |
| `engine/core/database.py:4` | "The SQLAlchemy-backed engine database is retired." — module is now a Store facade, no SQLAlchemy import |
| `engine/ingestion/ops_workflow.py:77` | `Pulse SQLAlchemy async session …` docstring |
| `engine/knowledge/store.py:236` | docstring mention |
| `engine/knowledge/vector_migration.py:57` | docstring mention (`Async SQLAlchemy session`) |
| `engine/ports/skills.py:3` | docstring mention |
| `engine/ports/store.py:18` | docstring "mirrors the SQLAlchemy AsyncSession surface" |

**Verification vs. the known list in the task:** the 15 "known import files" were
confirmed, plus **6 additional docstring-only** files (`budget.py`,
`core/database.py`, `ingestion/ops_workflow.py`, `knowledge/store.py`,
`ports/skills.py`, `ports/store.py`) and **2 additional real-import files
outside `engine/`** (`catalog_service.py`, `store.py`). `knowledge/vector_migration.py`
turned out to be docstring-only (no import), not a real-query file.

---

## Section 5 — `store.py` translation helpers

`backend/ai/store.py` is the persistence seam (Pulse Vendoring Phase 2). The
Django backend receives real SQLAlchemy 2.0 statements and must translate them
into Django ORM. Five helpers do the entity/expression mapping.

| Helper (def line) | What it does |
|---|---|
| `resolve_model(model)` (55) | Maps an engine SQLAlchemy model class → Django model class **by class name** (looks up `ai.models.<Name>`). Returns Django models unchanged (detects `_meta` + `objects`); returns unknown classes unchanged so the in-memory backend / test stubs keep working. |
| `_engine_table_map()` (204) | Lazy, cached dict of `__tablename__` → engine SQLAlchemy class, built by scanning `ai.engine.core.models` for classes with `__tablename__`. Used to reverse-map a `Table`/`TextClause` table name back to a model, and by `_run_django_text` to rewrite raw-SQL table names. |
| `_stmt_model(entity)` (218) | Maps a SQLAlchemy entity (model class **or** `Table`) → Django model. If given a `Table`, looks its `.name` up in `_engine_table_map()` then `resolve_model()`. |
| `_column_field(col)` (228) | Extracts a column's field name from a SQLAlchemy column/attribute: prefers `.key`, falls back to `.name`. |
| `_literal(value)` (233) | Coerces SQLAlchemy literal/expression wrappers to plain Python: `True_`/`False_`/`Null`, and any `BindParameter`/`_LiteralClause`/`_OffsetLimitParam` (via `.value`). |

**Call sites**

- `resolve_model` → `_to_django_instance` (145), `_stmt_model` (224/225),
  `_select_spec` (388, 396), `_InMemorySession.select/get` (853/882),
  `_DjangoSession.select/get/aggregate` (1038/1055/1124),
  `_run_django_text` table loop (1323).
- `_engine_table_map` → `_stmt_model` (223), `_run_django_text` (1322).
- `_stmt_model` → `_select_spec` join handling (410), `_update_spec` (468).
- `_column_field` → `_binary_to_q` (257, 262), `_criteria_to_q` (332, 349, 351),
  `_select_spec` join normalization (416, 418, 423, 425), `_update_spec` (478).
- `_literal` → `_binary_to_q` (262), `_criteria_to_q` (332), `_update_spec` (479).

These feed `_select_spec` (379) / `_update_spec` (462), which normalize
`Select`/`Update` statements into dicts consumed by `_run_django_select` (1170) /
`_run_django_update` (1301) / `_run_django_text` (1309). Dispatch happens in
`_DjangoSession.execute` (1130): `Select`→select spec, `Update`→update spec,
`TextClause`→raw SQL. **`store.py` itself imports `sqlalchemy` at runtime** and
must be converted last.

---

## Section 6 — Recommended conversion order + risks

### Order (each step keeps the suite green)

1. **(c) docstring-only files** — trivial comment cleanup (no functional change).
2. **(b) `prompt_synthesizer.py`** — drop `AsyncSession` import; use the
   `ai.engine.ports.store.Store` protocol type (or `Any`) in annotations.
3. **(a) query-construction leaves** — convert one file at a time from
   `select()/update()/text()` to the Store's native session API
   (`db.select(model, *filters)`, `db.get`, `db.aggregate`, and a new
   `db.update(...)`/`db.execute(...)` helper). Suggested order (by dependency
   risk): `skills/registry.py` → `skills/crud.py` → `skills/gate.py` →
   `agent/registry.py` → `agent/tools.py` → `agent/guardrails.py` →
   `agent/reasoning.py` → `agent/executor.py` → `llm/prompt_eval.py` →
   `llm/prompt_optimizer.py` → `knowledge/vector_store.py` →
   `catalog_service.py`.
4. **(a) model definitions** — `engine/core/models.py` +
   `engine/knowledge_graph/models.py`: replace the 49 SQLAlchemy classes with
   lightweight typed entities (dataclasses / pydantic) that the engine
   instantiates (`Skill(**data)`, `Agent(...)`) while the Django mirror remains
   the only ORM. This is the bulk of the work.
5. **(a) `store.py` last** — once no caller emits SQLAlchemy statements, delete
   the statement translator (`_select_spec`/`_update_spec`/`_literal`/`_stmt_model`
   and the `execute()` dispatch) and remove every `import sqlalchemy`.

### Files that block `pip uninstall sqlalchemy`

- **Runtime (must convert):** the 14 engine (a) files + `store.py` +
  `catalog_service.py` (16 total).
- **Type-hint (must clean):** `prompt_synthesizer.py`.
- **Test-only:** `backend/ai/tests/test_store_execute.py` (constructs real
  `select/update/or_/text` statements to exercise the translator — becomes
  obsolete once step 5 lands).
- **Not blocking:** the 7 docstring-only (c) files.

### Risks

1. **`store.py` is the highest-risk file.** It inspects SQLAlchemy's *private*
   statement internals — `column_descriptions`, `_setup_joins`,
   `_where_criteria`, `_order_by_clauses`, `_limit_clause`, `_offset_clause`,
   `entity_description`, `_values`, plus `sqlalchemy.sql.elements` (`True_`,
   `False_`, `Null`, `BindParameter`, `TextClause`). These are not public API
   and are version-sensitive; any SQLAlchemy upgrade can silently break the
   Django backend. It is the *last* file to convert and the reason SQLAlchemy
   cannot be uninstalled until every engine caller stops building statements.
2. **Engine model instantiation surface** — ~15 files construct model instances
   (`Skill(**kwargs)`, `Agent(...)`) and pass them to `db.add()`; replacing the
   ORM classes with plain entities must preserve the `db.commit()` →
   attribute-backfill contract (`_backfill_engine_attrs`) that sets `id` /
   `created_at` after commit.
3. **Raw SQL in `vector_store.py`** (`text(...)` with pgvector `<=>`/`<->`) has
   no Django-ORM equivalent; the translator rewrites table names + binds but the
   pgvector operators stay raw SQL. Needs a Django `RawSQL`/cursor path.
4. **Schema drift** (Section 3): `KgProactiveInsight.visibility` default and
   `MemoryLongTerm.memory_type` are latent divergences to reconcile during the
   cutover (they currently survive only because the store copies engine
   attributes onto Django rows).
5. **`Text` vs `CharField(36)`/`CharField(16)`** primary/visibility keys: engine
   treats them as unbounded `TEXT`; Django constrains length. Any value > 36
   chars in `id` (or > 16 in `visibility`) would insert fine in SQLAlchemy but
   fail in Django.
