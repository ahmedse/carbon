# ADR-0007: Pulse as In-Hand Stateless Engine, Carbon as System of Intelligence

## Status
Proposed (accepted direction, pending final ratification)

## Context

ADR-0004 established a three-layer AI architecture (platform AI, domain AI, security
guards) and framed the provider (Pulse) as **external and swappable** via an
`AI_PROVIDER_CLASS` strategy seam. `docs/AI_WORKSPACE_ARCHITECTURE.md` §2/§4.2 encodes
the same "Pulse is external, swappable, stateless from Carbon's perspective" framing.

Two gaps emerged from that framing:

1. **Missing institutional learning.** Only episodic conversation history and Pulse's
   opaque internals existed. There was no semantic (what we know), procedural (how we
   do it), or feedback (what users accepted/rejected) memory. The UI already signals the
   gap: `AIConversationView.jsx` discards accept/reject outcomes.
2. **Swappability is a liability, not a feature.** A swappable provider forces the
   domain-facing contract to be lowest-common-denominator, pushes memory/learning
   decisions into an opaque external system, and gives us no place to enforce CBAC on
   the context the model sees.

## Decision

We adopt the following direction, documented in depth in
`docs/AI_INTELLIGENCE_ARCHITECTURE.md`:

- **Carbon is the System of Intelligence.** All durable AI state — memory, learning,
  feedback, knowledge graph — is Carbon-owned.
- **Pulse is an in-hand, stateless reasoning engine.** It is co-deployed, not external;
  it holds no memory, does no learning, stores no graphs. Per-task working memory only,
  discarded on completion.
- **No provider swappability.** Remove `AI_PROVIDER_CLASS` runtime swapping. The engine
  adapter (`backend/ai/providers/pulse.py`) is the single contained seam — an
  implementation detail, not a strategy guarantee.
- **Knowledge is partitioned by `app_identifier`.** Cross-app reads are structurally
  impossible.
- **CBAC is enforced at three boundaries** — request (capability + org subtree + task
  class), context (scoped cache keyed by scope hash), and write (mutation guard + human
  approval).
- **Performance is designed**: orchestration (AI Heart) decoupled from inference (Pulse
  engine); bounded inference queue; model tiering; async agent jobs on Redis; scoped
  context cache.
- **Feedback is first-class**: accept/reject/correct outcomes are persisted and feed an
  async, idempotent, revertible learning pipeline.

## Consequences

### Positive
- A single governed place to enforce multi-user isolation on AI context and knowledge.
- Learning becomes auditable and revertible (a feedback loop, not a fine-tune).
- The engine stays simple, testable, and replaceable at the adapter seam if ever needed.

### Negative
- We must build and operate the knowledge store and learning pipeline (real new scope,
  proposed as Phase 2.5 in the phased plan).
- The context cache becomes a correctness-critical component and must carry dedicated
  cross-scope isolation tests (issues I1/I2 in the deep document).

## Supersedes
- ADR-0004 §Decision (provider-swappability clause only).
- `docs/AI_WORKSPACE_ARCHITECTURE.md` §2 and §4.2 (the "external, swappable" wording).

## Follow-ups
- Amend `project.config.md` RULE_6 (no Pulse SDK — reinterpret to "no vendor SDK in
  domain/core code") and RULE_13 (task envelope) to reflect the in-hand engine and the
  feedback obligation.
- Insert a knowledge/learning phase (Phase 2.5) into the phased plan.
