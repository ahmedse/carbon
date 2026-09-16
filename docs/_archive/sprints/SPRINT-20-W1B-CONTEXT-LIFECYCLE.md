# Sprint 20 — W1-B: Conversation checkpoint / restore / fork / clear-context (backend)

**Owner:** Master Architect · **Worker Role:** backend-worker · **Model:** DeepSeek V4-Flash
**Status:** 🚀 READY for dispatch (after W1-A)
**Design:** `docs/DESIGN_AI_WORKSTATION.md` §2.3
**Master index:** `TASKS.md` Phase W1-B (lines 1818–1871)
**Depends on:** W1-A (fork reuses the abort/stop seam).

## Goal
Give the workstation **context lifecycle**: snapshot a conversation's working context to a
named **checkpoint**, **restore** it, **fork** a conversation from a checkpoint at a chosen
message boundary, and **clear** the working context — none of which delete the durable
message log or learned facts.

## Current state (verified facts — do NOT re-discover)
- `backend/ai/models/workspace.py` — `AIConversation` already has `context_snapshot_json`,
  `summary`, `last_summarized_message_id`, `scope_json`, `task_payload_json`. `AIMessage`
  has `parent_message_id`, `status`, `outcome`, `learned_at`. `AIGeneration` at line 318.
- `backend/ai/context_assembler.py` — `assemble_context` (line 456) is the snapshot bundle.
- `backend/ai/intelligence.py` — `send_message_stream` (line 434) builds/injects context;
  `stop_generation` (line 1472) is the abort seam (reused by fork).
- `backend/ai/workspace_api.py` — `WorkspaceConversationViewSet` (line 54) is where actions mount.
- No `ConversationCheckpoint` model exists yet.

## Files to Change
- `backend/ai/models/workspace.py` — ADD `ConversationCheckpoint` model + migration
  (fields: `id`, `conversation` FK, `owner` FK, `name`, `note`, `snapshot_json`,
  `message_boundary_id`, `created_at`). Unique-together `(conversation, name)`.
- `backend/ai/intelligence.py` — MODIFY: `checkpoint_conversation`, `restore_conversation`,
  `fork_conversation`, `clear_context`.
- `backend/ai/workspace_api.py` — MODIFY: `checkpoint/`, `restore/`, `fork/`, `clear-context/` actions.
- `backend/ai/serializers.py` — MODIFY: checkpoint serializer.
- `backend/ai/tests/test_context_lifecycle.py` — ADD.

## Tasks

### 1. Checkpoint
`intelligence.checkpoint_conversation(user, conversation_id, name, note=None)`:
- Build the current bundle via `context_assembler.assemble_context` (messages + budget +
  `kg_entities` + memory) and persist it as `snapshot_json`.
- Idempotent: same `name` overwrites the existing checkpoint (update `snapshot_json`, `note`).
- Return the serialized checkpoint. Mutating → `ai:manage_console`.

### 2. Restore
`intelligence.restore_conversation(user, conversation_id, checkpoint_id)`:
- Re-seed the conversation's **working** context (history/summary/KG/memory injection) from
  the checkpoint. It does NOT overwrite the durable `AIMessage` log.

### 3. Fork
`intelligence.fork_conversation(user, conversation_id, checkpoint_id)`:
- Clone the conversation into a NEW `AIConversation` row (title `"{old} — fork"`) seeded from
  the checkpoint at the chosen `message_boundary_id`.
- **Return a NEW conversation id** — never alias the old row.

### 4. Clear context
`intelligence.clear_context(user, conversation_id)`:
- Reset the *working* context (history/summary/KG/memory injection) without deleting the
  conversation row, the message log, or learned facts. Do not call the learning forget path.
- Leave `context_snapshot_json` on existing messages untouched.

### 5. Endpoints + CBAC
`workspace_api.py` actions (all under the conversation router):
- `POST .../checkpoint/` (body: name, note)
- `POST .../restore/` (body: checkpoint_id)
- `POST .../fork/` (body: checkpoint_id)
- `POST .../clear-context/`
- `GET .../checkpoints/` (list for the picker)
Mutating actions require `ai:manage_console`; reads require `ai:view_console`.

## DO NOT TOUCH
- Frontend files.
- `learning.py` / durable memory writes (clearing context must NOT trigger forgetting).

## Verification Gate
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q
```

## Hard rules
- `python -m pytest`, **never** `manage.py test`. Venv is `/home/ahmed/aast/carbon/.venv`.
- Generate the migration with `manage.py makemigrations ai` (do not hand-write it).
- Timezone-aware datetimes only.

## Output contract
Append to `TASK-RESULTS.md`.

## Notes for the Master
- Fork must produce a NEW conversation id (no aliasing). Clear must leave
  `context_snapshot_json` on existing messages untouched. Both are explicit test cases.
