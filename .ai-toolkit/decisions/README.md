# Architecture Decision Records (ADRs)

**Purpose:** record every non-trivial architectural decision ONCE so it is never
re-debated, re-investigated, or accidentally reversed by a worker who lacks context.

This is how we stop "why did we do it this way?" from costing tokens every session.

## When to write an ADR
- A choice with trade-offs that a future worker might question or undo.
- A breaking change (API shape, DB field, config key).
- A "we tried X, it failed, we chose Y" learning (so nobody re-tries X).
- A cross-cutting convention (auth scheme, error format, deploy method).

## When NOT to
- Obvious, low-stakes, or fully-reversible local choices.

## How
```bash
cp .ai-toolkit/decisions/0000-template.md .ai-toolkit/decisions/00NN-short-title.md
# fill it in, keep it short (half a page)
```

## Rules
- Number sequentially. NEVER delete an ADR — supersede it (set Status: Superseded by 00NN).
- Master Architect owns ADRs. Workers READ them before touching the relevant area.
- Link the ADR from the relevant TASKS.md phase when it constrains the work.

## Index
| # | Title | Status |
|---|-------|--------|
| [0001](0001-pattern-architecture.md) | Pattern architecture (Strategy/Command) | Accepted |
| [0010](0010-data-product-domain-neutral.md) | Data Product must not carry GHG `scope` (domain vocabulary stays out of the generic core) | Proposed |

<!-- Add a row per ADR. Keep newest at the bottom. -->
