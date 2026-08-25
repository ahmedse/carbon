# TASK RESULT — G-C: Registry / Plugin Contract + First Non-Carbon Adapter

**Date:** 2026-08-25
**Gate:** G-C — "freeze the spine, grow the periphery" (plugin registry as the
extension seam; first non-carbon tool added with **zero engine edits**)
**Status:** ✅ GATE MET

---

## 1. Objective

Prove the "separate brain / never tightly couple" principle at the *code* level:
a new capability must be addable purely through the plugin registry, with **no
edit** to the engine spine (`tools.py` static catalog, `runner.py` chat
allow-set, the six-witness pipeline). The registry already existed (Sprint 12,
ARCH_AI_EXTENSIBILITY) but had two coupling gaps that made "grow the periphery"
a lie:

1. **Hardcoded chat allow-set** — `runner.py` listed tool names literally, so a
   new tool required an engine edit to become visible to the chat planner.
2. **No `capability_claim`** — `list_my_capabilities` could not be derived from
   the registry (design §5.2 invariant #2), so "what I can do" was hardcoded
   prose, not truthful-by-construction.

This task closes both gaps and lands the first **non-carbon** plugin as the
exit-gate proof.

---

## 2. Changes

### 2.1 `ai/engine/agent/plugins.py` — the contract

Two new `ToolPlugin` class fields:

| Field | Type | Meaning |
|-------|------|---------|
| `capability_claim` | `str = ""` | Human-readable "I can …" claim. Falls back to `description` when empty. |
| `chat_visible` | `bool = True` | Whether the chat planner may expose this tool. `False` = internal/hidden. |

Two new registry-derived functions:

```python
def chat_tool_names() -> frozenset[str]:
    """Names of registered plugins exposed to the chat planner (chat_visible)."""
    return frozenset(p.name for p in _PLUGINS if p.chat_visible)

def capability_claims() -> list[dict]:
    """Registry-derived capability manifest — truthful by construction (F5)."""
    # returns [{name, claim, requires_confirmation, kind}]
```

### 2.2 `ai/engine/cognition/turn/runner.py` — spine frozen, allow-set derived

The hardcoded `allow = {…}` set was replaced with a registry-derived derivation.
The only remaining spine constant is the *static* (non-plugin) tool allow-set:

```python
_CHAT_STATIC_TOOLS = frozenset({
    "search_knowledge", "get_entity_details", "learn_fact", "forget_fact",
})

allow = _CHAT_STATIC_TOOLS | chat_tool_names()
self._draft_tools = [
    d for d in get_tool_definitions()
    if d.get("function", {}).get("name") in allow
]
```

→ Adding a plugin is now **one line** in `ai/plugins/__init__.py`.

### 2.3 `ai/plugins/list_capabilities.py` — registry-derived capabilities

Added `agent_capabilities: capability_claims()` to the returned dict, alongside
the host-side `access_manifest` (apps/capabilities/modules/routes). Access
(what the *user* may do) stays host-derived; capability (what the *agent* can
do) is now registry-derived — no hardcoded prose.

### 2.4 `ai/plugins/unit_converter.py` — NEW, the first non-carbon plugin

`UnitConverter(ToolPlugin)`: stdlib-only linear + temperature conversion
(length/mass/volume/temperature), aliases + plurals, `requires_confirmation=False`,
`chat_visible=True`, `capability_claim` set. **Zero Carbon imports** (RULE_20),
read-only (RULE_21), fail-visible (`{"error": …}` on unknown/mismatched units).

### 2.5 `ai/plugins/__init__.py` — one-line registration

```python
register_plugin(UnitConverter())
```

No engine file was touched for the tool to become chat-visible — **that is the
exit gate.**

---

## 3. Tests

`ai/tests/test_plugins.py` gained 6 tests (G-C section):

| Test | Proves |
|------|--------|
| `test_chat_tool_names_includes_visible_and_excludes_hidden` | `chat_visible` gates the chat surface |
| `test_capability_claims_derived_from_registry` | claims come from the registry + description fallback |
| `test_runner_draft_allow_derives_plugin_tools` | **zero-edit** chat exposure (spine constant + registry names) |
| `test_unit_converter_plugin_converts_linear_units` | 10 mi → 16.09344 km |
| `test_unit_converter_plugin_converts_temperature` | 32 F → 0 C |
| `test_unit_converter_plugin_fails_visible_on_mismatched_units` | no guessed numbers |

---

## 4. Verification Evidence

```
$ pytest ai/tests/test_plugins.py -q
21 passed in 0.14s

$ pytest ai -q
1080 passed, 1 failed in 109.69s
  └─ failed = test_observability_api.py::test_rollups_totals_and_per_run_shape
     (KNOWN order-dependent flake — passes in isolation: 1 passed in 1.48s)
```

No regression introduced by the 5 contract edits + new plugin.

---

## 5. Verdict

**✅ GATE MET.** The plugin registry is now the single extension seam for
non-carbon capabilities:

- Spine is frozen (only `_CHAT_STATIC_TOOLS` remains, listing 4 core tools).
- Periphery grows by `register_plugin(...)` only.
- `list_my_capabilities` is truthful-by-construction (F5 invariant holds).
- First non-carbon tool (`unit_converter`) landed with **zero engine edits**.

### Residuals

None open. The `test_rollups_totals_and_per_run_shape` order-dependent flake
pre-dates this task (already documented in `carbon-anti-fabrication-qa.md` repo
memory) and is unrelated to G-C.
