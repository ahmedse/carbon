# Carbon AI Workspace — Phased Plan

**Date:** 2026-08-12  
**Status:** Master Architect draft  
**Owner:** Carbon AI Heart / AI Workspace program  
**Primary references:** [docs/AI_WORKSPACE_ARCHITECTURE.md](../docs/AI_WORKSPACE_ARCHITECTURE.md), [docs/PULSE_CONTRACT_SPEC.md](../docs/PULSE_CONTRACT_SPEC.md)

## 0. Goal

Build AI Workspace as a governed, task-oriented, multi-turn AI operating surface for Carbon.

The workspace is not a chat panel. It is the human interface to AI-assisted work:
- transfer a task from a domain page
- open a persistent AI conversation tab
- auto-start the task with the right context
- render structured AI output
- require human approval where needed
- keep a complete audit trail

## 1. Architecture Contract

### 1.1 Core principle

- Carbon owns identity, scope, policy, conversation state, audit, approvals, and business truth
- Pulse owns reasoning, model execution, and structured AI task results
- the UI is the engagement layer, not the source of truth

### 1.2 Access model

Use Carbon’s capability-driven, org-scoped model in practice.

For AI Workspace this means:
- the user must have the capability to launch the task
- the task must be limited to the user’s current org/module scope
- the provider receives a scope envelope on every AI call
- no task may widen access or cross app boundaries
- all human approval actions remain explicit

### 1.3 Workflow contract

A task transfer is complete only when:
1. the conversation exists
2. the AI task has been started or queued
3. the conversation status is visible
4. the result is normalized into Carbon-owned state
5. the user can review or approve the outcome

## 2. Phases

### Phase 0 — Contract cleanup and workflow clarity

**Intent:** remove ambiguity before adding more surface area.

**Outcomes:**
- define the canonical meaning of task transfer vs conversation creation vs execution start
- standardize the conversation status model across UI and backend
- document which task types auto-start and which remain manual
- ensure suggestion actions require persisted ids

**Key work:**
- align `chat`, `dq_validate`, `dq_suggest`, `nl_query`, and `anomaly` around one state model
- ensure the first AI response for machine workflows is automatic, not user-triggered
- define fallback behavior for provider-down cases

**Exit criteria:**
- the product spec answers: “what happens when the user clicks the button?” without caveats

### Phase 1 — Task transfer foundation

**Intent:** make transfer an executable handoff, not navigation.

**Outcomes:**
- task transfer creates a conversation and starts the first AI operation
- AI Heart records trace id, scope, and source context
- the UI shows immediate progress and a meaningful initial response

**Key work areas:**
- transfer context and kickoff contract
- create-and-start behavior for non-chat tasks
- explicit handling for provider failure and retry
- source-page context injection

**Expected behavior:**
- clicking “Suggest rules with AI” opens AI Workspace and starts suggestion work automatically
- clicking “Analyze with AI” on a rule or anomaly opens a tab and starts the relevant analysis

**Exit criteria:**
- transfer never produces a dead tab
- every task transfer lands in a visible, auditable state

### Phase 2 — AI Heart orchestration

**Intent:** make Carbon’s AI layer a strong governor and normalizer.

**Outcomes:**
- AI Heart owns the conversation lifecycle
- AI Heart routes task type to the correct domain workflow
- AI Heart validates scope and capability before every provider call
- AI Heart normalizes provider responses into Carbon-owned objects

**Key work areas:**
- conversation creation and persistence
- auto-start routing for each task type
- status transitions: `pending` → `working` → `needs_input` / `completed` / `failed`
- structured message serialization and retrieval
- idempotent handoff behavior

**Exit criteria:**
- AI Heart can answer: “what task is this, who is it for, what scope applies, and what should happen next?”

### Phase 3 — Domain task behaviors

**Intent:** make each AI task type feel intentional and useful.

**Outcomes:**
- `dq_suggest` produces reviewable candidate rules
- `dq_validate` produces structured validation output
- `nl_query` produces scoped answers with rows and explanation
- `anomaly` produces anomalies with severity and next steps
- `chat` remains free-form, but still governed

**Key work areas:**
- table/profile context extraction
- suggestion persistence with ids
- structured result rendering in message bubbles
- accept/reject/refine actions on persisted objects
- follow-up prompts when AI needs input

**Exit criteria:**
- every task type has a clear human workflow and a terminal state

### Phase 4 — Governance, security, and trust

**Intent:** prevent AI from becoming a new uncontrolled side channel.

**Outcomes:**
- prompt injection and tool misuse are treated as first-class threats
- scope is mandatory on every AI call
- the provider receives only the minimum data needed
- mutations remain human-approved
- every AI action is auditable and attributable

**Key work areas:**
- tool allowlists and mutation barriers
- response sanitization and scope filtering
- capability and org-scope enforcement
- audit logs and decision trace capture
- typed error taxonomy and safe degradation

**Exit criteria:**
- AI Workspace passes a red-team review for scope leakage, prompt injection, and unauthorized mutation paths

### Phase 5 — Copilot-grade workspace UX

**Intent:** make the experience feel like a serious operating surface.

**Outcomes:**
- persistent tabs for each active conversation
- clear task titles and source context
- structured cards for suggestions, query results, and anomalies
- loading / working / needs-input / failed states are obvious
- the user can continue work without losing context

**Key work areas:**
- tab behavior and persistence
- structured message rendering
- action affordances for accept/reject/refine/view details
- workspace-level empty states and recovery actions
- source-context chips or headers showing where the task came from

**Exit criteria:**
- AI Workspace feels more like a governed Copilot than a chatbot

### Phase 6 — Operational hardening and scale

**Intent:** turn the feature into an enterprise service.

**Outcomes:**
- conversation and task telemetry are observable
- latency, errors, provider availability, and task type usage are measurable
- retries and idempotency are robust
- cost and usage can be governed
- architecture can swap providers without front-end churn

**Key work areas:**
- tracing and metrics
- load-safe polling and refresh behavior
- provider resilience and fallback policies
- replay/debug support for failed tasks
- product analytics for AI usage

**Exit criteria:**
- AI Workspace can be operated, monitored, and evolved like a platform capability

## 3. Recommended order of execution

1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 3
5. Phase 4
6. Phase 5
7. Phase 6

This is deliberately ordered from contract clarity to user experience to hardened operations.

## 4. What not to do

- do not build AI Workspace as a generic chat shell
- do not let the UI be the source of truth for task outcomes
- do not route AI directly from frontend to provider
- do not make suggestions without persisted ids
- do not auto-apply mutations
- do not let provider output bypass Carbon scope
- do not couple the design to one vendor’s semantics
- do not mix navigation with execution state

## 5. Near-term worker decomposition

If this becomes implementation work, split it by layer:

### Backend worker phases
- Phase 1: transfer kickoff and conversation state
- Phase 2: AI Heart orchestration and normalization
- Phase 3: domain behaviors and persisted suggestion ids
- Phase 4: governance, security, and audit hardening

### Frontend worker phases
- Phase 5: workspace UX, structured rendering, task tabs, and action affordances
- Phase 6: telemetry surfaces and operational polish

## 6. Success definition

AI Workspace succeeds when:
- a user can move from a domain page into AI and stay in flow
- the AI does useful work immediately
- the user can see what the AI saw, what it inferred, and what it wants next
- approvals remain explicit
- the system remains auditable, scoped, and swappable

That is the enterprise standard.
