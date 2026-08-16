# TASK — AI Workspace Phase 6C: Per-Turn KG Provenance in the "Why?" Tooltip

- **Role:** Master Architect (backend freeze + frontend surface; small, coupled change)
- **Task ID:** AI-WORKSPACE-PHASE-6C-PROVENANCE-KG
- **Parent:** `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` §16, Phase 6 (post-T3/T6B)
- **Goal:** Make the `↩ Why this answer` tooltip on each assistant message show the knowledge-graph entities (and the tiered context budget) that were actually assembled for **that turn**, not just the latest turn's snapshot.

## Background

Two coupled defects block this:

1. **The frontend reads the wrong field.** `AIMessageBubble.normalizeMetadata` returns `message.metadata_json`, then reads `metadata?.provenance`. But `backend/ai/intelligence.py::_serialize_message` emits provenance as a **top-level** `message.provenance` key (built by `_build_message_provenance`); it is **not** stored inside `metadata_json`. So the tooltip's provenance branch is effectively dead in production — it always falls back to the conversation props (`Type`/`App`/`Org units`) and never shows context.
2. **No per-turn freeze.** `_build_message_provenance` falls back to `getattr(conversation, "context_snapshot_json", {})`, which is **overwritten on every send**. Every assistant message in a thread would show the *latest* turn's context, not its own.

This task freezes the per-turn snapshot onto each assistant message and makes the tooltip read + render it.

## Scope

### 1. Backend — freeze per-turn context (`backend/ai/intelligence.py`)

In `_save_assistant_message` (the single choke point for all 27 assistant-message save sites), capture the conversation's current `context_snapshot_json` into the message metadata **unless the caller already provided one**:

```python
snapshot = dict(metadata or {})
snapshot.setdefault(
    "context_snapshot",
    getattr(conversation, "context_snapshot_json", None) or {},
)
```

Pass `metadata_json=snapshot` to `AIMessage.objects.create(...)`. This makes `_build_message_provenance`'s existing `metadata.get("context_snapshot")` branch return the frozen, per-turn dict (which already includes `kg_entities` from Phase 6B). Error/cancel paths (provider unavailable / interrupted / failed) freeze an empty `{}` and are unaffected.

### 2. Backend — test (`backend/ai/tests/test_context_assembler.py`)

Add `test_assistant_message_freezes_per_turn_context_snapshot`: seed a KG entity + attribute (instance_id="carbon"), run `send_message` (mirror `test_context_snapshot_json_persists_kg_entities_after_send_message`), then reload the assistant `AIMessage` and assert:

- `message.metadata_json["context_snapshot"]["kg_entities"]` contains the seeded entity name and its stripped attribute;
- `message.metadata_json["context_snapshot"]["T3_retrieval"] > 0`.

### 3. Frontend — read + render (`carbon-frontend/src/shell/AIMessageBubble.jsx`)

- Change the provenance source to prefer the backend's top-level payload:
  ```js
  const provenancePayload = message.provenance || metadata?.provenance;
  ```
- Replace the naive `Object.entries(ctxSnap)` token loop (which currently renders `kg_entities [object Object] tok`) with a `formatContextLines(ctxSnap)` helper:
  - Map real budget keys to labels: `T2_history`→History, `T2b_summary`→Summary, `T3_retrieval`→KG Retrieval, `T4_memory`→Memory; include only non-zero tiers as `Label N tok`.
  - Emit a `Knowledge Graph: name1, name2, …` line from `ctxSnap.kg_entities` (array of `{name, …}`), truncated to 5 names.
  - Export `formatContextLines` for unit testing.
- Keep the existing `scope_snapshot`/`guard_results`/fallback branches intact.

### 4. Frontend — tests (`carbon-frontend/src/__tests__/AIMessageBubble.transparency.test.jsx`)

- Add a unit test for `formatContextLines`: given `{ T2_history: 12, T3_retrieval: 34, kg_entities: [{ name: 'monthly_electricity' }, { name: 'emission_factors' }] }`, assert it returns a `Context:` line listing `History 12 tok · KG Retrieval 34 tok` and a `Knowledge Graph: monthly_electricity, emission_factors` line; and that `kg_entities` is never rendered as `[object Object]`.
- Update/extend the provenance test to pass a **top-level** `provenance` on the message (matching the real serialization shape) and assert the icon still renders.

## Do not touch

- `_build_message_provenance` logic (it already reads `metadata.get("context_snapshot")` correctly).
- The SSE frame/stream contract.
- `AIContextPanel` (already done in Phase 6B).

## Verification gate

```bash
# backend
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q

# frontend
cd /home/ahmed/aast/carbon/carbon-frontend && npm test -- --run
cd /home/ahmed/aast/carbon/carbon-frontend && npm run lint
cd /home/ahmed/aast/carbon/carbon-frontend && npm run build
```

## Deliverable

Report: files changed, the provenance-source fix, the per-turn freeze behavior, the KG formatting, and test/build proof.
