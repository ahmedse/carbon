# TASK — AI Workspace Phase 6B: Surface Knowledge-Graph Context + Align Budget Telemetry

- **Role:** Master Architect (backend seam + frontend surface; small, coupled change)
- **Task ID:** AI-WORKSPACE-PHASE-6B-FRONTEND-KG
- **Parent:** `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` §16, Phase 6 (post-T3)
- **Goal:** Make the `[Knowledge Graph]` (T3) context that `assemble_context` injects into every AI turn visible in the conversation detail view, with transparency parity to the existing budget telemetry — and fix the budget bar that was silently broken by a key mismatch.

## Background

Phase 6 (T3) implemented `_retrieve_knowledge_graph` in `backend/ai/context_assembler.py`. It builds `kg_entries` (a list of `{name, node_type, confidence, attributes}`) and injects them as a `[Knowledge Graph]` system note into the provider payload. **But nothing persists the actual entries** — `intelligence.send_message` / `send_message_stream` only store `assembled["budget"]` (token counts) into `conversation.context_snapshot_json`. The frontend therefore has no data to surface.

Two coupled defects were found while tracing the surface:

1. **KG entries are dropped.** `assemble_context` returns `{messages, budget}` but discards `kg_entries` at the boundary. The frontend cannot show *what* was retrieved.
2. **The budget bar is broken.** The backend budget dict uses keys `T2_history`, `T2b_summary`, `T3_retrieval`, `T4_memory` (see `test_assemble_context_budget_keys_non_negative`), but `AIContextPanel.parseBudget` reads `T0…T4`. Every tier resolves to `0`, `total === 0`, and the panel permanently shows "Available after first message".

This task exposes the KG entries and aligns the budget bar to the real contract, on the existing `AIContextPanel` surface.

## Scope

### 1. Backend — return the KG entries (`backend/ai/context_assembler.py`)

In `assemble_context`, add the already-computed entries to the return dict:

```python
return {
    "messages": tiered,
    "budget": budget,
    "kg_entities": kg_entries,   # NEW — [{name, node_type, confidence, attributes}]
}
```

Do **not** change `kg_entries` construction or budget accounting.

### 2. Backend — persist the entries (`backend/ai/intelligence.py`)

Both `send_message` and `send_message_stream` currently do:

```python
conversation.context_snapshot_json = assembled["budget"]
conversation.save(update_fields=["context_snapshot_json"])
```

Change to a flat merge (keeps `T2_history` etc. as top-level keys, so the existing telemetry test still passes):

```python
conversation.context_snapshot_json = {
    **assembled["budget"],
    "kg_entities": assembled["kg_entities"],
}
conversation.save(update_fields=["context_snapshot_json"])
```

### 3. Backend — tests (`backend/ai/tests/test_context_assembler.py`)

- The existing `test_context_snapshot_json_set_after_send_message` (asserts `"T2_history" in snapshot`) stays valid under the flat merge — leave it.
- Add `test_context_snapshot_json_persists_kg_entities_after_send_message`: seed one ENTITY `KnowledgeNode` (instance_id="carbon") + one ATTRIBUTE + `HAS_ATTRIBUTE` edge, run `send_message` (mirror the existing `test_context_snapshot_json_set_after_send_message` wiring), then assert `conv.context_snapshot_json["kg_entities"]` contains the entity name and its stripped attribute. The existing autouse `_clear_carbon_kg` fixture already isolates this from committed leaks.

### 4. Frontend — surface KG + fix budget keys (`carbon-frontend/src/shell/AIContextPanel.jsx`)

- Fix `parseBudget` to read the real backend keys, using a `BUDGET_TIERS` list:

  ```js
  const BUDGET_TIERS = [
    { key: 'T2_history', label: 'History' },
    { key: 'T2b_summary', label: 'Summary' },
    { key: 'T3_retrieval', label: 'KG Retrieval' },
    { key: 'T4_memory', label: 'Memory' },
  ];
  ```

  `parseBudget` maps each `BUDGET_TIERS` entry to `{ tier, label, tokens, pct }`; render uses `e.label` (drop the stale `TIER_LABELS` map). Keep `TIER_COLORS` length aligned (4 tiers).

- Add a **Knowledge Graph** section to the panel (between "Mentions" and "Context budget"), reading `snapshot.kg_entities`:

  - Header "Knowledge Graph".
  - Empty/missing → muted "None retrieved".
  - Otherwise, one row per entity: name (bold, word-break-safe) + confidence as a percentage on the right; a muted attribute list line (`attributes.join(', ')`) when non-empty.
  - Read from `const kgEntities = Array.isArray(snapshot?.kg_entities) ? snapshot.kg_entities : [];`.

- Keep the existing scope/mentions/summarize behavior and accessibility labels untouched.

### 5. Frontend — tests (`carbon-frontend/src/__tests__/AIContextPanel.test.jsx`)

- Update `baseConversation.context_snapshot_json` to the real shape (e.g. `{ T2_history: 420, T2b_summary: 120, T3_retrieval: 340, T4_memory: 0 }`).
- Update `"renders token budget bars for non-zero tiers"` to assert `History`, `Summary`, `KG Retrieval` (not `System`/`Workspace`).
- Add a test: with `kg_entities: [{ name: 'monthly_electricity', confidence: 1.0, attributes: ['month', 'total_kwh'] }]`, assert the entity name and the attribute list render after expanding.

## Do not touch

- `backend/ai/context_assembler.py` KG retrieval/budget logic beyond the return-dict addition.
- DQ backend routes, routing surface, or any non-AI-workspace frontend views.
- The `send_message_stream` frame/SSE contract.

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

Report: files changed, the `context_snapshot_json` contract change, the budget-bar fix, the KG section behavior, and test/build proof.
