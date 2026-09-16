# Sprint 15 — Context Engineering + Enterprise Governance (backend)

**Owner:** Master Architect · **Status:** 🚀 Ready for Backend Worker dispatch (after Sprint 13)
**Design:** `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` §6 + §8 (Phase 3 + Phase 4 backend)
**Contract:** `.ai-toolkit/shared/ai-contract.md` §11 (WorkspaceContext) + §3 (isolation)

## Goal
Tiered, budgeted context assembly (compaction + RAG/KG retrieval feed) and enterprise
surface: transcript export + per-turn usage attribution + provenance.

## Current state (verified facts — do not re-discover)
- `backend/ai/intelligence.py` `send_message`/`send_message_stream` build
  `ConversationContext` from ALL history every turn (no budget). `_prepend_workspace_context`
  and `_prepend_domain_context` already exist and mutate the outgoing message.
- `AIConversation.summary` field now exists (Sprint 13).
- `backend/ai/engine/` has a knowledge graph + memory (`LongTermMemory`, `KnowledgeGraph`)
  but the workspace does not query them. Inspect `backend/ai/store.py` and `backend/ai/engine/`
  for the retrieval entry points before wiring (READ FIRST, do not guess names).
- `backend/ai/models/workspace.py` `AIMessage.token_usage_json` exists (Sprint 13).

## Tasks

### 1. Context assembler (tiered + budgeted)
CREATE `backend/ai/context_assembler.py`:
- `def assemble_context(conversation, messages, scope, *, recent_turns=8, summary_budget=1500, retrieval_budget=2000, memory_budget=1000) -> dict`
  returning `{"messages": [...tiered history...], "budget": {tier: token_estimate}}`.
- Tier rules (approximate tokens by `len(text)//4`):
  - T2 history: most recent `recent_turns` messages verbatim; anything older is NOT sent.
  - T2b summary: prepend `conversation.summary` if non-empty.
  - T3 retrieval + T4 memory: **stub only** — return empty lists with a `TODO` comment
    noting the engine KG/memory seam (do not fabricate engine calls this sprint). The
    budget dict still reserves those token counts.
- MODIFY `backend/ai/intelligence.py` `send_message` + `send_message_stream`: replace the
  current "all history" `ConversationContext` build with `assemble_context(...)` output
  (use `assemble_context(...)["messages"]`). Store the returned `budget` into
  `conversation.context_snapshot_json` (save `update_fields=["context_snapshot_json"]`).
- Keep `ConversationContext` dataclass shape the same — only the `messages` list changes.

### 2. Compaction + summary endpoint
MODIFY `backend/ai/intelligence.py`:
- `summarize_conversation(self, user, conversation_id, force=False)` — if `conversation.summary`
  is empty OR `force`, build a cheap summary. **Deterministic fallback**: concatenate the
  first 3 user messages truncated to 120 chars each into a summary line (no LLM call —
  avoids hidden cost and keeps tests deterministic). Store to `conversation.summary`.
  Return `_serialize_conversation`.
- The LLM-based summarizer is a `TODO` comment; the deterministic fallback is the shipped behavior.
MODIFY `backend/ai/workspace_api.py`:
- `@action(detail=True, methods=["post"], url_path="summary")` `summarize` → `intelligence.summarize_conversation`
  (accept optional `force` boolean in body).

### 3. Export endpoint
MODIFY `backend/ai/intelligence.py`:
- `export_conversation(self, user, conversation_id, fmt="json")` — returns the full
  conversation. `fmt="json"` → `{"conversation": {...}, "messages": [...]}` (already have
  `_serialize_*`). `fmt="markdown"` → a markdown string: `# {title}\n\n` then per message
  `**{Role}** ({timestamp})\n\n{content}\n\n`, with `metadata_json` rendered as a fenced
  ```json block when non-empty. Returns `{"format": fmt, "content": <str>}`.
MODIFY `backend/ai/workspace_api.py`:
- `@action(detail=True, methods=["get"], url_path="export")` `export` → query param `?format=json|markdown`.

### 4. Usage attribution
MODIFY `backend/ai/intelligence.py`:
- In `_save_assistant_message` / `_build_ai_message`, accept optional `usage=None` and persist
  to `AIMessage.token_usage_json` (`{model, prompt_tokens, completion_tokens, total_tokens, cost_usd, latency_ms}`).
- In chat streaming `done`, if the result dict carries `execution_ms`, set `usage={"latency_ms": execution_ms}`.
- MODIFY `backend/ai/models/workspace.py` `_serialize_message` already exposes `token_usage_json`
  (done in Sprint 13) — confirm it is returned.

### 5. Tests (REQUIRED)
CREATE `backend/ai/tests/test_context_assembler.py`:
- assemble_context returns at most `recent_turns` messages + summary
- budget dict has expected keys and non-negative values
- conversation.context_snapshot_json is set after send_message
- summarize_conversation (deterministic) produces a non-empty summary and persists it
- export json returns conversation + messages; export markdown contains the title and content
- usage kwarg persists to token_usage_json and survives serialize

## DO NOT TOUCH
- `backend/ai/engine/**`
- `carbon-frontend/**`
- Do NOT call the LLM in this sprint (deterministic fallbacks only — keeps tests fast and offline-safe).

## GATES (run ALL, paste output)
```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check
./.ai-toolkit/scripts/verify.sh backend
./.ai-toolkit/scripts/verify.sh antipatterns
```

## HARD RULES
- No cross-app leak: `assemble_context` only reads the current conversation's own messages.
- No hidden LLM cost in tests (deterministic fallbacks).
- `timezone.now()` only.

## REPORT BACK
Task-by-task ✅/❌, test count, terminal output, deviations.
