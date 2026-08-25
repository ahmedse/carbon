# ADR-0017 — Pulse Instance Config: YAML Seam Pattern

**Date:** 2026-08-24  
**Status:** Accepted  
**Author:** QA Validator (validated by execution + audit)  
**Supersedes:** Inline fallback in `_carbon_instance_config()` (engine_runtime.py)  
**Extends:** ADR-0008 (Pulse portability), ADR-0016 (domain app AI contract)

---

## Context

During QA deep-simulation (22 live API scenarios), an audit of the engine layer found
that `engine_runtime.py::_carbon_instance_config()` contained ~80 lines of hardcoded
domain knowledge in Python:

- Carbon-specific API routes (`/carbon-api/dq/rules/`, `/carbon-api/dataschema/tables/`)
- DQ rule schema fields (`rule_level`, `dimension`, `severity`)
- Navigation routes (`/dq/rules/{id}`)
- Domain topics list (`["data quality", "data catalog", "governance"]`)
- Persona and description strings

The intelligence kernel (`engine/cognition/`, `engine/memory/`, `engine/learning/`)
contained zero domain terms — correctly. But this one Python function was the last
coupling point between the brain and the domain.

**The question:** Can you copy `engine/` to a Moodle (or healthcare, or logistics) project
and bootstrap Pulse as a true coworker?

**Before this ADR:** No. You would also need to rewrite `_carbon_instance_config()`.  
**After this ADR:** Yes. Copy `engine/`, write `instances/<project>/instance.yaml`,
write `host_executor.py`. Done.

---

## Decision

**All domain-specific instance configuration is declared in `instances/<name>/instance.yaml`.**  
`_carbon_instance_config()` becomes a thin loader (≤10 lines) with no domain strings.

### The Seam Contract

```
engine_runtime.py              ← thin loader; no domain terms
  └─ load_instance_config("carbon")
       └─ instances/carbon/instance.yaml   ← ALL Carbon domain knowledge here
```

### instance.yaml Structure

```yaml
display_name: str           # shown in UI / system prompt
description: str            # what the platform does (one paragraph)
persona: str                # how the assistant behaves (one paragraph)
domain_topics: list[str]    # topic routing hints for skill router
api_catalog:                # tool definitions (routes, bodies, auth, confirmation)
  - name, method, path, description, requires_auth, requires_confirmation
navigation_routes:          # frontend navigation the assistant can trigger
  - name, path, description
```

### Bootstrap Recipe for a New Project

```bash
# 1. Copy the intelligence kernel
cp -r backend/ai/engine/  /path/to/new-project/ai/engine/

# 2. Create the instance config (no Python changes needed)
mkdir -p ai/engine/instances/<project>
# Write ai/engine/instances/<project>/instance.yaml

# 3. Write a host executor
# Copy backend/ai/host_executor.py, replace Carbon API paths with project paths

# 4. Point the runtime loader
# In your engine_runtime.py equivalent: load_instance_config("<project>")
```

### What Stays In Python (Not Movable to YAML)

| Item | Location | Reason |
|------|----------|--------|
| `host_user_id` | runtime | resolved at request time |
| `user_access` | runtime | resolved from ORM at request time |
| `display_name` fallback | runtime | reads Django `PLATFORM_TITLE` setting |
| Task handlers (dq.validate, etc.) | engine_runtime.py | executable Python logic, not config |

---

## Consequences

### Positive
- `engine/` is now copy-pasteable to any project with zero Python changes
- A new domain can be bootstrapped by writing YAML + host_executor, not modifying intelligence code
- instance.yaml is reviewable by non-engineers (product owners, domain experts)
- The coupling boundary is explicit and auditable: grep `instances/` to see all domain knowledge

### Negative / Tradeoffs
- If `instance.yaml` is missing, `load_instance_config()` returns `{}` and the engine gets no persona/tools — **must fail loudly in production** (add startup check)
- YAML does not validate against a schema by default — add a Pydantic validator in `archetypes.py` for CI

### Mitigation
- Add `validate_instance_config(name)` to `archetypes.py` (raises on missing required fields)
- Add startup assertion in `engine_runtime.py`: `assert load_instance_config("carbon").get("persona"), "instance.yaml missing or invalid"`

---

## Files Changed

| File | Change |
|------|--------|
| `backend/ai/engine/instances/carbon/instance.yaml` | Created — all Carbon domain config |
| `backend/ai/engine_runtime.py::_carbon_instance_config()` | Replaced 80-line dict with 10-line loader |
