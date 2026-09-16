# PEC-7A — Convergence: remove inert F1a / F3 paths

**Date:** 2026-09-16  
**Canonical:** `docs/pulse/PULSE-CANONICAL.md` F1a, F3, §12  
**Decision:** `instance.yaml` is the single prompt-config mechanism. REMOVE/DEFER filesystem domain-pack guidance wiring and PlaybookBlock / PromptVersion A/B hot path. Do not seed fake playbooks.

## Deleted / deferred symbols

| Symbol / path | Action | Finding |
|---------------|--------|---------|
| `ai.domain_skills` (`get_guidance_skills`, `pack_skills_dir`, …) | **DELETED** module | F1a |
| `build_chat_prompt(..., guidance_skills=)` | **REMOVED** parameter | F1a |
| `_build_guidance_index` / `_build_guidance_section` | **DELETED** | F1a |
| PromptVersion 20% A/B routing in `build_chat_prompt` | **DELETED** from hot path | F3 |
| `playbook_assembler.assemble(...)` call from `build_chat_prompt` | **REMOVED** (always `_fallback_prompt`) | F3 |
| `PlaybookAssembler` / `playbook.py` | **DEFERRED(F3)** — module kept for ops/CRUD; not on chat hot path | F3 |
| `engine/knowledge/skill_folder.py` | **DEFERRED(F1a)** — parser kept for offline/tests | F1a |
| `domain_packs/carbon/skills/*` | **Deferred on disk** (README marked); not injected live | F1a |

## Untouched (per task DO NOT TOUCH)

- `instance.yaml` persona content  
- ProcessDefinition / Capability seeds  
- Frontend  
- Heartbeat / cognition loop A/B *staging* in `engine/cognition/loop.py` (not hot path)  
- Eval harness  
- Django `PlaybookBlock` model (flight_director upserts still use it; not chat prompt assembly)

## Grep proof (post-change)

```text
# runner: no guidance_skills=
$ rg -n "guidance_skills=" backend/ai/engine/cognition/turn/runner.py || true
(empty)

# hot path: no guidance_skills= / no A/B / no assemble
$ rg -n "guidance_skills\s*[=:]" backend/ai/engine/llm/prompts.py backend/ai/engine/cognition/turn/runner.py || true
NONE
$ rg -n "A/B split|playbook_assembler|improvement_round" backend/ai/engine/llm/prompts.py || true
NONE
$ test ! -f backend/ai/domain_skills.py && echo DELETED
DELETED
```

## Startup / verify notes

- Chat prompt assembly no longer opens a DB session for PlaybookBlocks or PromptVersion candidates — reduces fail-surface on empty tables.
- `verify.sh antipatterns` gate #7 fails if `guidance_skills=` / `guidance_skills:` is reintroduced in `runner.py` or `prompts.py` without an ADR.

## Verification (TASKS.md gate)

See `TASK-RESULTS.md` § PEC-7A for literal terminal output.
