# TASK — AI Workspace Phase 6: T3 Knowledge-Graph Retrieval Seam

- **Role:** Backend Worker
- **Task ID:** AI-WORKSPACE-PHASE-6-T3-KG
- **Parent:** `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` §16, Phase 5 → context assembler T3 tier
- **Goal:** Replace the stubbed T3 tier in `backend/ai/context_assembler.py` with a deterministic, budgeted, app-scoped knowledge-graph retrieval that injects durable schema context into every AI turn.

## Background

`assemble_context` in `backend/ai/context_assembler.py` builds tiered context:

- **T2** — verbatim recent history (done)
- **T2b** — rolling summary (done)
- **T3** — knowledge-graph retrieval (**STUBBED** — a comment only; reserves `retrieval_budget` but injects nothing)
- **T4** — long-term memory retrieval (`_retrieve_long_term_memory`, done)

This task implements T3. The KG was already built in Phase 2b-3b: `engine_runtime._bootstrap_schema_graph` upserts `KnowledgeNode` (ENTITY/ATTRIBUTE) + `KnowledgeEdge` (HAS_ATTRIBUTE) rows into the durable Django store. Those rows exist but are never read into context — that is the gap.

## Critical scoping difference vs T4 (read carefully)

T4 memory facts are written by the learning bridge with an explicit `visibility` + `host_user_id` + `org_unit_id`, so `_retrieve_long_term_memory` partitions by visibility + org subtree.

**The schema KG is different.** `_bootstrap_schema_graph` writes `KnowledgeNode` rows with:
- `instance_id = DEFAULT_APP_IDENTIFIER` (`"carbon"`)
- `app_identifier = "carbon"` (AppScopeMixin default)
- `org_unit_id = None`
- `visibility = "private"` (AppScopeMixin default), `host_user_id = None`

So if you copy T4's visibility/org partition verbatim, **every schema node will be filtered out** (`private` requires `host_user_id` match, and `None` matches nobody). The schema KG is **app/instance-scoped reference context** (like emission factors being global — see the "reference data is global" rule in repo memory), NOT user/org-partitioned secret data.

**T3 scoping = pin `instance_id` (and `app_identifier`) to `DEFAULT_APP_IDENTIFIER`, filter `node_type="ENTITY"`, and do NOT apply visibility/org partition.** This is consistent with the existing `_resolve_mention_descriptors`, which already injects table/field/module names without CBAC partition.

## Source models

- `KnowledgeNode` (from `ai.models`): `id`, `instance_id`, `node_type`, `name`, `description`, `properties`, `confidence`, `verified`, `module_id`, `valid_from`, `valid_to`, `created_at`, `access_count`, `last_accessed`.
- `KnowledgeEdge` (from `ai.models`): `source_node_id`, `target_node_id`, `relationship`, `confidence`, `source`.

Use **`KnowledgeNode`/`KnowledgeEdge`** (the 15-table vendored KG cluster), **NOT** `KgNode`/`KgEdge` from `ai/models/core.py` (legacy engine KG with embeddings).

## Scope

### 1. Add `_retrieve_knowledge_graph(scope, retrieval_budget)` in `backend/ai/context_assembler.py`

Mirror the shape of `_retrieve_long_term_memory` (returns `(entries, tokens_used)`, no DB handles leaked), but with app/instance scoping:

- Guard: if `retrieval_budget <= 0`, return `([], 0)`.
- Query `KnowledgeNode.objects.filter(instance_id=DEFAULT_APP_IDENTIFIER, node_type="ENTITY")`.
  - Optionally also `app_identifier=DEFAULT_APP_IDENTIFIER` (harmless; AppScopeMixin defaults to `"carbon"`).
  - Optional hardening (mirror T4): exclude expired rows via `valid_from`/`valid_to` (`Q(valid_from__isnull=True) | Q(valid_from__lte=now)`, `Q(valid_to__isnull=True) | Q(valid_to__gt=now)`). If you include it, gate it behind `django.utils.timezone.now()`.
- Deterministic ordering: `-confidence`, `-created_at` (mirrors T4's `-confidence, -created_at`).
- **No visibility/org partition.** Do not touch `visibility`/`host_user_id`/`org_unit_id`.

For each ENTITY node, resolve its attribute names via `KnowledgeEdge`:
- Fetch edges `KnowledgeEdge.objects.filter(instance_id=DEFAULT_APP_IDENTIFIER, relationship="HAS_ATTRIBUTE", source_node_id=entity.id)`.
- Join each `target_node_id` → `KnowledgeNode` to get the ATTRIBUTE node's `name`.
- Strip the leading `"<entity>."` prefix from attribute names (bootstrap stores attributes as `"table.column"`).
- Deterministic attribute ordering: by node `name` (or `created_at` if names collide).

Build an entry per entity:
```python
{
    "name": entity.name,
    "node_type": entity.node_type,        # "ENTITY"
    "confidence": float(entity.confidence or 1.0),
    "attributes": ["month", "total_kwh", ...],  # short names, prefix stripped, budget-truncated
}
```

Budget accounting (deterministic, testable):
- The entity "base" line = `name` + a fixed label (e.g. `"(ENTITY)"`) + optional `description` if non-empty. Count its tokens with `_estimate_tokens`.
- If `used_tokens + base_tokens > retrieval_budget`, **skip the entity entirely** (mirrors T4's over-budget drop) and `continue` to the next.
- Otherwise add the base, then append attributes one at a time: for each attribute name, if `used_tokens + _estimate_tokens(attr) <= retrieval_budget`, append and count it; else stop appending attributes for this entity (do NOT count the dropped ones).
- Return `(entries, used_tokens)`.

### 2. Wire T3 into `assemble_context`

Replace the T3 stub comment block (the `# T3 — engine knowledge-graph retrieval seam` block) with a real call:

```python
kg_entries, kg_tokens = _retrieve_knowledge_graph(scope, retrieval_budget)
if kg_entries:
    lines = ["[Knowledge Graph]"]
    for e in kg_entries:
        attrs = ", ".join(e["attributes"]) if e["attributes"] else "(no attributes)"
        lines.append(
            f"- {e['name']} (ENTITY, confidence {e['confidence']:.2f}): {attrs}"
        )
    tiered.append({"role": "system", "content": "\n".join(lines), "timestamp": None})
```

Placement: after the T4 memory block, before the T2 verbatim-history block (so ordering is `workspace → summary → memory → graph → history`). T3 is **not** gated on `scope` (it is instance-scoped; T4 is the only scope-gated tier).

### 3. Update budget telemetry

Change `budget["T3_retrieval"]` from the reserved constant `retrieval_budget` to the **actual** tokens injected:

```python
"T3_retrieval": kg_tokens,
```

### 4. Update the docstring

Update the `assemble_context` docstring and module docstring so T3 is no longer described as "stubbed". Note the scoping rule ("T3 is app/instance-scoped reference context, not visibility/org-partitioned").

### 5. Tests — update + add in `backend/ai/tests/test_context_assembler.py`

**Update the one existing assertion that encodes the stub:**

`test_assemble_context_budget_keys_non_negative` currently asserts `budget["T3_retrieval"] == 2000`. Change to `== 0` (fresh test DB has no KG nodes) with a comment, OR drop that line. The `set(budget.keys()) == {...}` assertion stays valid.

**Add new tests** (all `@pytest.mark.django_db`, using the existing `user` fixture and `Scope` from `backend.ai.protocol`):

1. `test_assemble_context_t3_injects_schema_graph` — seed `KnowledgeNode` (ENTITY `"monthly_electricity"`, ATTRIBUTE `"monthly_electricity.total_kwh"`, ATTRIBUTE `"monthly_electricity.month"`) + `KnowledgeEdge` (HAS_ATTRIBUTE: entity→each attr), all `instance_id="carbon"`. Assert the result contains a system message with `"[Knowledge Graph]"`, the entity name, and the stripped attribute names `total_kwh` / `month` (NOT the `"monthly_electricity."` prefix).
2. `test_assemble_context_t3_is_instance_scoped_not_user_partitioned` — seed an ENTITY node with default `visibility="private"`, `org_unit_id=None`, `host_user_id=None` (i.e. exactly what the bootstrap writes). Assert the node STILL appears in context (proves the visibility/org partition was NOT copied from T4). This is the regression guard for the critical scoping difference.
3. `test_assemble_context_t3_truncates_at_budget` — seed one ENTITY with several attributes; set `retrieval_budget` small enough that only some attributes fit. Assert the entity is present, the attributes that fit are present, and the over-budget attribute is absent.
4. `test_assemble_context_t3_drops_over_budget_entity` — seed one ENTITY whose name alone exceeds `retrieval_budget`. Assert no `[Knowledge Graph]` message and `budget["T3_retrieval"] == 0`.
5. `test_assemble_context_t3_empty_when_no_nodes` — no KG rows; assert no `[Knowledge Graph]` message and `budget["T3_retrieval"] == 0`.

Seed via `KnowledgeNode.objects.create(...)` / `KnowledgeEdge.objects.create(...)` (import from `ai.models`). Note `KnowledgeNode` uses a string UUID primary key — pass `id=str(uuid.uuid4())` or let the `generate_uuid` default fill it; `KnowledgeEdge.source_node_id`/`target_node_id` must reference the node `id` strings you set.

## Do not touch

- `_retrieve_long_term_memory` (T4) — leave as-is.
- `_resolve_mention_descriptors` / `_workspace_context_message`.
- Any engine file under `backend/ai/engine/**` (the graph is already populated; this task only READS it).
- `intelligence.py`, `workspace_api.py`, `store.py`, models, migrations.
- Frontend.

## Verification gate

Run from `cd /home/ahmed/aast/carbon/backend` using `/home/ahmed/aast/carbon/.venv/bin/python`:

```bash
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_context_assembler.py -q
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
```

Show FULL output as it streams — do NOT pipe through `tail`/`head`. If output is too large, write to a temp file and read it back.

## Deliverable

Report back with:
- files changed (exact paths)
- the `_retrieve_knowledge_graph` signature + its scoping (instance-scoped, no visibility/org partition) and ordering
- how T3 is injected + where it sits in the tier order
- the budget semantics (entity drop vs attribute truncation)
- test results (pass/fail + counts) and the one updated assertion
- any follow-up issues that should become a separate task
