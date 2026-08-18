# DESIGN — Adaptive, Learning Data Quality Core

- **Status:** Proposal (for owner review — not yet ratified)
- **Author:** Master Architect
- **Area:** `backend/dq/` + `backend/ai/` (knowledge/memory/feedback seams)
- **Grounded in:** `.ai-toolkit/shared/ai-contract.md`, ADR-0006/0007/0008/0009,
  Anthropic "Building Effective Agents" + "Effective Context Engineering".

---

## 1. The question, answered directly

**Q: What makes a system scale, adapt, and learn — and isn't hardcoding workflows
unsustainable?**

A: Hardcoding is exactly the anti-pattern. Anthropic names it explicitly: at one end of
the "right altitude" spectrum sits *"brittle if-else hardcoded prompts"* that "create
fragility and increase maintenance complexity over time." The fix is **not** to make
everything an autonomous agent, and **not** to bolt on a knowledge graph and call it done.

The fix is to **separate four concerns and make three of them data, not code**:

| Layer | Role | Editable by | "Learns" how |
|-------|------|-------------|--------------|
| **Interpreter** (fixed code) | evaluate declarative specs | code change only | it doesn't — it's the substrate |
| **Knowledge** (data: rules, templates, profiles, schema) | the WHAT | humans + feedback loop | adding/reusing data, not code |
| **Memory** (data: semantic/episodic/procedural + graph + vectors) | the KNOW | feedback loop | retrieving the right context |
| **Reasoning** (stateless engine + declarative workflows) | the HOW | workflow specs/plugins | new spec = new capability |

> **The core principle:** a system *learns by editing data, not code*; it *adapts by
> having a small deterministic interpreter over declarative specs*; it *scales by
> decoupling durable state (Carbon-owned) from stateless reasoning (Pulse engine)*.

This is precisely what ADR-0007 already mandates for the whole platform: **Carbon is the
System of Intelligence; Pulse is a stateless in-hand reasoning engine; feedback is
first-class.** The DQ core is the first domain to fully exploit it.

---

## 2. "Knowledge graph or what?"

A knowledge graph answers **"what relates to what."** It is one memory structure — good
for relationship traversal and global sensemaking, weak for fuzzy "what's similar to this
request" retrieval. A KG alone does **not** make a system learn; the *feedback loop that
writes to it* does.

**The honest answer: not "KG or what" — it's "KG + hybrid retrieval + feedback loop."**

| Primitive | Best for | DQ example |
|-----------|----------|------------|
| Knowledge graph | lineage, reachability, dedup | `field → rule → dimension → domain`; "which rules already touch this field?" |
| Vector store | fuzzy semantic similarity | "which existing rule resembles this new NL intent?" |
| BM25 / keyword | exact/identifier match | field named `emp_no`, rule type `regex` |
| Structured profiles | statistics, facts | column cardinality, null %, min/max, top values |
| Episodic memory | what happened | past `DQResult`s, accept/reject outcomes |

Microsoft **GraphRAG** is the canonical example: KG + community summaries for global
questions; hybrid BM25+dense for local retrieval. The lesson to copy is *layered memory*,
not "buy a graph DB."

---

## 3. Research summary — wisdom to adopt, flaws to avoid

### Wisdom to adopt

1. **Context engineering > prompt engineering** (Anthropic). Treat the context window as a
   finite "attention budget." Find the *smallest set of high-signal tokens* per call.
2. **Context rot is real** (Chroma, Anthropic): more tokens → worse recall. Don't stuff;
   retrieve just-in-time.
3. **Workflows vs agents** (Anthropic): use deterministic workflows for well-defined
   tasks, agents only for open-ended ones. *"Start simple, add complexity only when it
   demonstrably improves outcomes."*
4. **The learning-lever hierarchy** (cheapest first): deterministic code → retrieval →
   in-context examples → structured memory → spec/example optimization (DSPy) → fine-tune
   (last resort).
5. **Declarative over imperative** (DSPy, Great Expectations, Soda): encode the task as a
   *signature/spec* and let an optimizer tune prompts/examples against a metric — instead
   of hand-editing brittle prompt strings.
6. **Memory hierarchy** (MemGPT/Letta): main context (working set) vs external store;
   self-editing memory via tools, persisted outside the window.
7. **Feedback = language, not gradients** (Reflexion / ADR-0007): learning is an async,
   idempotent, revertible memory update, not a fine-tune.
8. **Hybrid retrieval + rerank** for precision (every mature RAG system).
9. **Declarative expectations + profiles → auto-suggest** (Great Expectations, Soda,
   Ataccama): profile a table, propose rules from statistics — exactly `dq.suggest`.

### Flaws to avoid

| Flaw | Consequence | Carbon guard |
|------|-------------|--------------|
| Hardcoded if/else prompt chains | breaks on model swap, unversioned | declarative workflow specs (ADR-0008) |
| No eval harness | can't tell if "learning" helps | golden-set gate (Phase A) |
| RAG without hybrid + rerank | precision loss, wrong context | graph + BM25 + dense + rerank (Phase C) |
| Memory without idempotency/revertibility | poisoning, no rollback | async idempotent pipeline (ADR-0007) |
| Over-fine-tuning | cost, catastrophic forgetting, drift | fine-tune = last resort only |
| Stuff-everything-in-context | context rot | just-in-time retrieval |
| Tool bloat | ambiguous tool selection | minimal toolset, clear boundaries |
| Learning inside the engine | violates RULE_6/§0.4 | Carbon owns all durable state |
| Non-declarative rule logic | every rule = code change | rule `definition` JSON is data (ADR-0006) |
| Auto-mutation | AI writes prod data | §4 / RULE_21: AI suggests, Carbon executes |

---

## 4. The unified architecture (applied to DQ)

Five layers, already aligned to the existing Carbon AI contract:

```
                 ┌─────────────────────────────────────────────────┐
  request        │  CarbonIntelligence  (single entry point)       │
  (scope,        │  GuardChain: Scope→Access→Isolation→Mutation→Rate│
   op)           └───────────────┬─────────────────────────────────┘
                                 │
        ┌────────────────────────┼───────────────────────────────┐
        │                        ▼                                │
        │   L1 INTERPRETER (deterministic, pure, tested)          │
        │   dq/rule_schema.py · dq/engine.py                      │
        │   — never calls AI; always available (graceful)         │
        │                                                         │
        │   L2 KNOWLEDGE (declarative data)                       │
        │   rule definitions · rule templates · type/dimension     │
        │   catalog · field profiles · canonical examples          │
        │                                                         │
        │   L3 MEMORY (retrieval substrate)                       │
        │   graph (lineage) + vector (similarity) + BM25 (exact)   │
        │   + episodic (run/feedback history)                     │
        │                                                         │
        │   L4 REASONING (stateless engine)                       │
        │   declarative workflow specs + tool/plugin registry     │
        │   (six-witness turn pipeline)                           │
        │                                                         │
        │   L5 LEARNING (closed feedback loop)                    │
        │   accept/reject/correct → async idempotent update → eval │
        └─────────────────────────────────────────────────────────┘
```

**The single rule that makes it all work:** L5 (learning) only ever writes to L2/L3
(data). It never touches L1 (code) and never mutates production rules without a
confirmation gate. "New rule type" = a catalog row (data); "better suggestions" = better
memory (data); "new capability" = a workflow spec or plugin (data), not an app (ADR-0008).

### Adaptation happens at three speeds

1. **Fast (runtime, no learning):** retrieval assembles the right context per request.
2. **Medium (feedback):** accept/reject + DQ outcomes edit memory/examples → suggestions
   improve. Auditable + revertible.
3. **Slow (governed):** humans add rule types/dimensions/templates/plugins as data —
   the system grows without rewriting the interpreter.

---

## 5. Piece-by-piece application plan (DQ core)

Each phase is independently shippable, each ends with a verification gate.

### Phase A — Deterministic substrate + eval harness (no AI, foundation)

The interpreter must be provably correct before anything "learns" on top of it.

- Externalize `RULE_TYPES`, `RULE_LEVELS`, `DIMENSIONS` from hardcoded tuples in
  `dq/models.py` into a seedable catalog (data, not code). New rule type = catalog row.
- Build a **golden-set eval harness**: a fixed corpus of rule definitions → expected
  `EvalResult`, run by `pytest`. This becomes the regression gate for every later phase.
- Files: `backend/dq/catalog.py` (new), `backend/dq/tests/test_eval_harness.py` (new).
- Gate: harness green; `pytest backend/dq` shows zero regressions.

### Phase B — Knowledge graph + memory substrate (the KNOW)

Make DQ's relationships a first-class queryable graph, reusing the already-vendored
`engine/knowledge/schema_graph.py` + `knowledge_graph/` machinery.

- Model: `DataTable ↔ DataField ↔ DQRule ↔ RuleFieldAssignment ↔ dimension ↔ domain ↔
  org_unit` as a graph view (not a new DB — a read projection over existing FKs).
- Semantic memory: field profiles (extend `dq/services.py:profile_table`), canonical
  examples per rule type.
- Enables: rule reuse ("what rules touch `emp_no`?"), gap analysis, dedup, similarity
  ("find fields like this one").
- Files: `backend/ai/knowledge/dq_graph.py` (new), extend `dq/services.py`.
- Gate: graph queries return correct lineage for the seeded golden tables.

### Phase C — Retrieval + context assembly (adaptive `suggest`/`nl_check`, no hardcoding)

Replace any hardcoded NL prompt with a declarative, retrieval-augmented context assembler
(the vendored `proactive/context_assembler.py` is the seam).

- `dq.suggest` retrieves: schema, field profile, canonical examples, N most-similar
  existing rules (hybrid graph + vector + BM25, reranked) → feeds a *data-driven* prompt.
- `nl_check` retrieves: the rule's field profile + past results + similar rules.
- All retrieval partitioned by `scope.app_identifier` + `org_unit_ids` (contract §3).
- Files: `backend/ai/providers/pulse.py` (context assembly), new retriever module.
- Gate: eval harness shows retrieval-augmented suggest ≥ baseline on golden set.

### Phase D — Feedback loop / learning (the LEARN)

This is the actual "learn." Persist outcomes and feed an async, idempotent, revertible
pipeline (already mandated by ADR-0007).

- **Feedback sources:** rule accept/reject/correct (UI already discards these — fix
  `AIConversationView.jsx`); `DQResult` outcomes (true-positive vs always-pass vs
  false-positive); drift events.
- **Pipeline effects (all data edits, none auto-mutating prod rules):**
  1. Accepted rule → promoted to canonical example for its type.
  2. Corrected rule → correction recorded; future suggestions bias toward it.
  3. False-positive / always-pass rule → flagged for retirement (human confirms).
  4. Field profile refreshed → future `suggest` reflects new data.
- Files: `backend/ai/feedback/` (new), `backend/ai/learning/` (new), reuse
  `engine/knowledge_graph/feedback.py`.
- Gate: feedback loop is idempotent + revertible (rollback test); no prod rule mutates
  without `requires_confirmation`.

### Phase E — Declarative workflows + rule catalog (the HOW, scalable)

De-hardcode `dq/jobs.py` (currently an if/elif dispatch) into declarative workflow specs;
add a reusable, parameterizable rule template catalog.

- Model `rule_run / profile / freshness / schema / nl_check / suggest / anomaly` as
  workflow specs (ADR-0008: "a new workflow = a spec, not an app").
- Rule templates: `{"employee_no": {"type": "regex", "params": {"pattern": "^\\d{4,5}$"}}}` —
  the emp-no case becomes a template, instantiated with a confirmation gate.
- Files: `backend/dq/workflows.py` (new), `backend/dq/templates.py` (new), refactor
  `dq/jobs.py`.
- Gate: adding a job type no longer requires touching the dispatcher.

### Phase F — Eval-driven optimization (DSPy-style, only if C's harness shows a gap)

Only after Phase A's harness exists, tune `suggest`/`nl_check` examples/prompts against
the metric automatically. Fine-tuning remains explicitly out of scope (last resort).

- Gate: optimizer must beat baseline on golden set, with a revertible checkpoint.

---

## 5B. Admin & ops coworker surfaces (substrate + surface)

**Correction to earlier framing:** CBAC, users, lineage, governance, MDM, and data product
are **not** merely substrate. Admins are users too — the coworker must help them govern.
These domains are therefore **both substrate and surface**: they remain the
correctness-critical rails (scope enforcement, lineage truth), *and* Pulse assists admins
on top of them.

Each admin surface is **suggest/draft only** — never auto-mutates grants, users, policies,
or master records (§4, RULE_21). Every write carries `requires_confirmation`.

### Phase G — Admin domain registration (the pattern)

Register an admin/ops domain alongside `emissions` using the same `ai/domain/{app}.py`
ABC. Establishes `app_identifier="admin"` (or per-app identifiers) + manifest of
entry points. No new Django app (ADR-0008).

- Files: `backend/ai/domain/admin.py` (new), thin adapters in `accounts/`, `mdm/`,
  `dataschema/`.
- Gate: manifest loads; `listDomainManifests` returns the admin surfaces; zero regressions.

### Phase H — Access & CBAC assistance

Pulse assists admins with *explanation and proposal*, never mutation:
- "what is this user's effective capability set across their org subtree?"
- "which users can reach X?" (trace `capabilities.py` registry + group maps).
- propose least-privilege grants; flag over-granted users and dormant grants (anomaly).

- Capability-gated (`platform:manage_access`, `platform:view_audit`); results filtered by
  `scope.org_unit_ids`.
- Gate: proposals are read-only; a golden set of "grant this user X" intents yields
  correct capability + confirmation payload, and never executes.

### Phase I — Lineage & impact (feeds the graph, memory layer)

- Trace "where does this field/table flow from/to?" and "if I change X, what breaks?"
  — read projection over `dataschema` lineage + FKs, surfaced via the knowledge graph
  (extends Phase B).
- Gate: lineage trace of a seeded golden table returns correct upstream/downstream edges;
  impact analysis lists affected rules/tables.

### Phase J — Governance & policy

- Explain policy; draft policy changes (draft only); map rules → policies → dimensions;
  flag drift (unbound rules, stale policies, dimension gaps).
- Gate: policy explanation is grounded in the existing rule catalog; drafts require
  confirmation; drift flags match seeded anomalies.

### Phase K — MDM & data product

- Entity resolution assistance, dedup suggestions, "explain this entity's master record",
  gold-record confidence.
- Gate: dedup suggestions against a seeded golden set; no record mutates without
  confirmation.

---

## 6. Explicit non-goals (reaffirmed)

- **No fine-tuning** until every cheaper lever is exhausted (Anthropic hierarchy).
- **No auto-mutation** — AI suggests, Carbon executes (§4, RULE_21). Admin surfaces
  included: no self-grant, no auto user/group/policy/master-record mutation.
- **No learning inside Pulse** — Carbon owns all durable state (RULE_6, ADR-0007).
- **No new Django apps** — knowledge/memory/feedback/admin are internal packages under
  `backend/ai/` (ADR-0008).
- **No SQLite, no docker in dev** (user hard rules).
- **CBAC remains a correctness rail** — making it a coworker surface never weakens the
  three enforcement boundaries (request/context/write) in ADR-0007.

---

## 7. Decision needed

Recommended order: **A + B first** (deterministic harness + graph — zero AI risk), then
**emissions** (first Category B domain op), then the **admin/ops cluster (G–K)** as a
distinct phase group, then the remaining domains (mdm, data product) via the same ABC.

**Ratify / reorder / reject — then I execute phase-by-phase.**
