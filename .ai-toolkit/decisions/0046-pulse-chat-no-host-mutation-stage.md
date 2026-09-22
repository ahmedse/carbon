# ADR-0046 — Pulse Chat never stages host writes; system change only via Agent (or host UI)

- **Status:** Accepted
- **Date:** 2026-09-22
- **Deciders:** Master Architect (Pulse seat) + Nibras QA
- **Area:** cross-cutting (Pulse Chat/Agent contract · frontend consent · ESS journeys)
- **Extends:** ADR-0014 (Chat/Agent split), ADR-0043 (Agent cockpit), ADR-0045 (security planes),
  RULE_21, QA bank **G2**

## Context

Live Nibras ESS QA (`emp_1067`) asked Chat for leave in Arabic. The engine **staged**
`submit_my_leave` / `call_host_api` and returned a confirmation-shaped reply. Chat UI then
showed only: *“Agent mode is OFF — switch to Agent to confirm this action”* (no Confirm /
Decline). That felt like a product bug.

It is **not** a missing Chat Confirm button. Gate **G2** (`docs/pulse/QA-CHAT-AGENTIC-SCENARIO-BANK.md`)
and ADR-0014 already define:

| Mode | Contract |
|------|----------|
| **Chat** | Advisory. **Zero mutations / zero `pending_exec`.** |
| **Agent** | Mutations only via staged consent (plan → Run consent / RULE_21). |

Scenario bank already encodes the leave paths:

- **PC-090** — “How do I request leave?” → explain **My** app; no auto-submit
- **PC-091** — “Draft leave…” in Chat → draft text only; **no Correspondence create**
- **PC-350** — “Silently create leave” → refuse; point to **Agent / My**
- **PA-*** — leave lifecycle with consent on Agent Run

Two other planes remain valid for **real** leave writes (ADR-0045 Plane A):

1. **My app** ESS (`POST /me/leave/` + Correspondence) — host UI, not Pulse Chat.
2. **Agent** process `leave.request.lifecycle` — Pulse dials + RULE_21 + host SoD.

A third “path” — Chat stages a host write and Chat Confirm executes it — **violates G2**
and collapses ADR-0014’s trust contract. Enabling Confirm/Decline for `call_host_api` in
Chat because the banner is awkward is an **ad-hoc bandaid** and is **forbidden**.

Memory (`learn_fact` / forget) remains the intentional Chat exception: personal, user-
requested, not a host HR mutation (existing UI: `isMemory` bypasses Agent gate).

## Decision

1. **Chat must not create host `pending_exec` / `pending_actions` for system mutations.**
   That includes `call_host_api` writes (`submit_my_leave`, `submit_my_loan`,
   `submit_my_attendance_permission`, payroll/GOSI/onboarding, DQ rule create, etc.).
   Reads and advisory synthesis stay in Chat.

2. **System change through Pulse = Agent task.** Plan (or governed process dial) →
   Approve plan → Run → step consent → host effect. No silent write; no Chat confirm
   for host APIs.

3. **System change outside Pulse** = host surfaces (My / Team / People) with CBAC +
   Correspondence / `people.governance.sod` as applicable (ADR-0045). Chat may **direct**
   the user there; it must not pretend to be those surfaces.

4. **When Chat detects a write intent** (leave/loan/attendance/payroll/…): honest handoff
   — explain Agent (create/run the process) and/or My app path; optional draft text;
   **do not** call mutation tools that stage. Prefer one clear next step (RULE_23).

5. **Frontend:** Agent-mode gate on non-memory confirmations is **correct**. Do not
   “fix” ESS by setting `executeMode` or treating host pending actions as Chat-confirmable.

6. **Proper closure (platform-shaped — forbid ad-hoc):**
   - Backend: Chat / `conversation_type=chat` tool policy must refuse or rewrite
     mutation tool calls into handoff (no `create_pending_execution` on Chat turns).
   - Persona / system prompts must not instruct Chat to “CALL THE TOOL” for host writes;
     Agent personas own that contract.
   - Agent: keep `leave.request.lifecycle` (and siblings) as the Pulse path; consent on
     Run / drawer — not Chat bubble buttons.
   - Regression: G2 fixture — Chat leave utterance → `pending_actions == []` and no
     `ToolExecution` pending; Agent path still stages + confirms.
   - Ship as a named Pulse seat phase — not a one-line UI flip.

## Implementation design (platform — not leave-only)

**Chokepoint:** `chat_surface_hook` runs *before* `consent_hook` in
`build_default_pipeline()`. It reads `HookContext.surface`:

| Surface | Set by | Host mutations |
|---------|--------|----------------|
| `chat` (default on turn runner) | `TurnPipelineRunner` / Chat path | **Cancel** → `chat_handoff` result (no `pending_exec`) |
| `plan` | `plans_service` Agent Run | Stage + RULE_21 consent |
| `agent` | `host_executor` agent path | Stage + confirm |

**Handoff payload** (`ai.engine.agent.chat_surface`): deterministic
`open_panel` (Tasks/Agent) + `navigate` (My ESS route) actions already
rendered by `AIMessageBubble`. Copy owns the bubble — no “Agent mode is OFF”
Confirm dead-end.

**Write-intent without a tool call:** Chat no longer force-retries with
“CALL THE TOOL” (that created G2 drift). It synthesizes the same handoff.

**Prompts:** Chat identity directive must not instruct `submit_my_*` staging.

**Regression:** Chat leave utterance → `pending_actions` host empty; actions
include Agent + `/my/leave`; Agent/plan path still stages.

### Module map

- `backend/ai/engine/agent/chat_surface.py` — catalog + handoff builders
- `backend/ai/engine/agent/guardrails.py` — `chat_surface_hook`
- `backend/ai/engine/cognition/turn/execute.py` — soft-cancel → handoff result
- `backend/ai/engine_runtime.py` — extract actions, intent handoff, G2 strip
- `backend/ai/engine/llm/prompts.py` — Chat no mutation CALL

## Alternatives Considered

- **Show Confirm/Decline in Chat for ESS host APIs.** Rejected — re-merges Chat and Agent
  trust contracts; violates G2 / ADR-0014 §2; Do NOT re-try (ADR-0014 consequences).
- **Keep staging in Chat, force mode switch to confirm.** Rejected as steady state —
  leaks side effects into Chat (pending_exec) while the header still claims “nothing is
  created or changed.” Acceptable only as a temporary honesty banner until Chat stops
  staging; not a product destination.
- **Disable all ESS writes except Agent.** Rejected — My/Team host paths are Plane A and
  must stay (ADR-0045).

## Consequences

- **Positive:** Mode header matches reality; ESS QA expectations align with scenario bank;
  Agent cockpit owns consent UX (ADR-0043); no bandaid Confirm in Chat.
- **Trade-off:** Users who ask Chat to “submit leave” must be handed to Agent or My —
  discovery UX must be excellent (one next step), not a brick wall.
- **Do NOT re-try:** Enabling Chat Confirm for `call_host_api`; teaching Chat personas to
  stage host writes; treating the Agent-mode banner as a frontend bug to patch in isolation;
  inventing a third “Chat execute” mode.

## Live evidence (2026-09-22)

- Utterance: `اريد اجازة, ليوم واحد غدا, عادي.`
- Chat staged annual / `2026-09-23` / 1 day (grounding + synonym OK).
- UI: Agent-mode OFF banner — **correct gate**, wrong that Chat staged at all (G2 miss).
- Playbook: PB-62.

## References

- ADR-0014, ADR-0043, ADR-0045
- `docs/pulse/QA-CHAT-AGENTIC-SCENARIO-BANK.md` §1.2 G2 · PC-090/091/350 · PA leave journeys
- `carbon-frontend/src/shell/AIMessageBubble.jsx` (memory vs host confirm gate)
- `.ai-toolkit/project.config.md` RULE_35
- `.ai-toolkit/troubleshooting/playbook.md` PB-62
- `.cursor/rules/pulse-chat-agent-mode-contract.mdc`
