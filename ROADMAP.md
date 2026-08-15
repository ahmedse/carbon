# Carbon — Roadmap to Completion
# Single source of truth for ALL outstanding work.
# Updated: 2026-08-15 | Owner: Master Architect
#
# North star: a fully functioning Carbon where AI knows what the user is doing,
# helps them create DQ rules in natural language, fills forms live, tests them,
# and grows smarter with every interaction.

---

## The DQ+AI target scenario (what "done" looks like)

```
User in DQ workspace → clicks [AI]
→ AI tab opens knowing: "you're looking at table X, I see you want to add a rule"
→ User chats: "validate the email field, here are some examples"
→ AI fills the rule JSON in the editor live, token by token
→ User reviews, edits, or just says "looks good"
→ AI creates the rule, runs a test, reports: "3 rows failed, here's why"
→ AI remembers: next time it knows this user's DQ style
```

Every sprint below is ordered to build toward this. Each sprint is independently
deployable. Later sprints depend on earlier ones.

---

## What's already done (do not re-implement)

- Platform core: accounts, catalog, mdm, dataschema, connections, evidence, importexport ✅
- DQ system (P0–P5): engine, gate, jobs, services, 249 tests ✅
- Carbon Footprint domain app: all models, APIs, frontend pages ✅
- AI system: 10 task types wired in-process, six-witness pipeline, KG, memory, cognition loop ✅
- AI workspace: conversation CRUD, messaging API ✅
- AI workspace frontend: chat + dq_validate tabs ✅
- AI admin console: 19 panels ✅
- QA: 1,191 tests passing ✅

---

## Sprint 1 — Foundation fixes (1 day)
**Goal:** Fix the two things that block clean AI rule creation.

### 1A — DQ Rule Unbind (25 min, backend + frontend)
**Spec:** `tasks/SPRINT-1B-DQ-RULE-UNBIND.md`

A rule must be creatable without specifying a table. Right now `bindings` is required,
which forces the user to bind during authoring — wrong model.

| Task | Worker | Time |
|---|---|---|
| `dq/rule_schema.py`: make `bindings` optional | Backend Worker | 15 min |
| `RuleJsonEditor.jsx`: remove non-empty bindings check from client validation | Frontend Worker | 10 min |

**Verify:**
```bash
cd backend && python -m pytest dq/tests/ -q
cd carbon-frontend && npm run build
```

### 1B — Email + backup ops (30 min, DevOps)
**Spec:** `tasks/SPRINT-1-QUICK-WINS.md §G2, §G4`

| Task | Worker | Time |
|---|---|---|
| Add backup cron: `0 2 * * * .venv/bin/python backend/manage.py run_backup` | DevOps | 5 min |
| Configure real email backend (SendGrid or SMTP) via `EmailConfig` in admin | DevOps | 20 min |

---

## Sprint 2 — Delete safety (2–3 days)
**Goal:** Close the data integrity risk before any production data grows.
**Spec:** `tasks/SPRINT-2-DELETE-SAFETY.md`

17 ViewSets currently do silent hard-delete with no dependency checks.
This is a P0 risk: deleting a ReportingPeriod cascade-destroys all its verifications.

**Pattern for every fix:**
```python
def destroy(self, request, *args, **kwargs):
    obj = self.get_object()
    if obj.has_dependents():
        return AppFeedback.blocked("Cannot delete: X depends on this")
    obj.is_archived = True  # soft-delete
    obj.save()
    emit_governance_event("entity.archived", obj)
    return Response(status=204)
```

| Priority | Entities | Worker |
|---|---|---|
| 🔴 Critical | ReportingPeriod, EmissionFactor, Calculation, CalculationRule, SBTiTarget, ExportProject, ImportJob | Backend Worker |
| 🟠 High | GWP, OrganizationalBoundary, BaseYear, DataSource, ConsumingConnection | Backend Worker |
| 🔵 Frontend | Confirm dialogs on delete buttons in 5 pages | Frontend Worker |

**Verify:**
```bash
cd backend && python -m pytest emissions/tests/ -q
```

---

## Sprint 3 — AI Workspace Phase 2 frontend (1 week)
**Goal:** Complete the AI workspace so dq_suggest, nl_query, and anomaly are usable.
**Spec:** `tasks/SPRINT-3-AI-WORKSPACE-PHASE2.md`

Backend is 100% done (Phase 2-A). This is frontend only.

| Task | What | Worker |
|---|---|---|
| dq_suggest tab | Show AI rule suggestions as accept/reject cards | Frontend Worker |
| nl_query tab | Show SQL + results table inside conversation | Frontend Worker |
| anomaly tab | Show anomaly cards with severity, z-score, investigate button | Frontend Worker |
| Structured message cards | Render `metadata_json.type` as typed cards, not raw JSON | Frontend Worker |

This sprint makes the AI workspace genuinely useful for the first time.

**Verify:**
```bash
cd carbon-frontend && npm run build && npm run lint
# Manual: open DQ workspace → click [Suggest AI] → see suggestion cards
```

---

## Sprint 4 — Log viewer backend (1–2 days)
**Goal:** `LogViewerPage.jsx` exists; the backend API doesn't.
**Spec:** `tasks/SPRINT-1-QUICK-WINS.md §G5`

| Task | Worker | Detail |
|---|---|---|
| `GET /carbon-api/system/logs/?lines=N&search=query&level=ERROR` | Backend Worker | Read-only; tails `logs/carbon.log`; admin-only; sanitize file paths |
| Wire `LogViewerPage.jsx` to live API | Frontend Worker | Replace mock with real apiFetch call |

---

## Sprint 5 — DQ Hub (1 week)
**Goal:** Replace 6 fragmented DQ surfaces with one unified workspace.
**Spec:** `tasks/SPRINT-5-DQ-HUB.md`

Currently: 2 full pages + 2 tabs + 2 dialogs, all doing overlapping DQ things.
Target: single `/catalog/dq-hub` with tabs: Rules | Results | Profiles | Freshness | Jobs.

Frontend only. All backend APIs already exist.

---

## Sprint 6 — WorkspaceContext: AI knows what you're doing (2–3 weeks)
**Goal:** The DQ scenario step 2 — AI opens already knowing your context.
**Spec:** To be written as `tasks/SPRINT-6-WORKSPACE-CONTEXT.md`

**What it is:** The frontend serializes what the user is doing into a structured
`WorkspaceContext` object and sends it when opening the AI tab. No screenshots.

**Phase 6-A: Protocol + backend (Backend Worker, 1 day)**
- Add `WorkspaceContext` dataclass to `ai/protocol.py` (full spec in `ARCHITECTURE.md §AI` and `ai-contract.md §11`)
- `CreateConversationSerializer`: accept optional `workspace_context` field
- `CarbonIntelligence.create_conversation()`: store in `task_payload_json`
- `_send_chat_message()`: inject workspace_context as system prompt prefix

**Phase 6-B: Emit from each workspace (Frontend Worker, 1 day per workspace)**
```js
// When user clicks [AI] in DQ workspace:
const workspaceContext = {
  workspace: "dq",
  current_view: "rule_list",
  entity_type: selectedRule ? "rule" : "table",
  entity_id: selectedRule?.id ?? currentTable?.id,
  entity_name: selectedRule?.name ?? currentTable?.name,
  intent_signal: showNewRuleForm ? "create" : "explore",
  recent_actions: recentActions.slice(-3),
};
openAIWorkspace({ workspaceContext });
```

Workspaces to wire: DQ, Catalog, DataSchema, Emissions.

**Phase 6-C: Intent-aware AI response (Backend Worker, 2 days)**
- `intent_signal="create"` + `entity_type="rule"` → AI opens with: "I see you want to create a new DQ rule. Based on table X's profile, I'd suggest..."
- `intent_signal="debug"` → AI opens with the failure context pre-loaded

**Verify:**
- POST /ai/workspace/conversations/ with workspace_context → conversation system prompt contains context
- Open DQ workspace, click AI → AI message references the table and intent

---

## Sprint 7 — ai/domain/emissions.py: GHG vocabulary (3 days)
**Goal:** AI knows GHG Protocol vocabulary, scope 1/2/3, emission factors.
**Spec:** To be written as `tasks/SPRINT-7-DOMAIN-EMISSIONS.md`

Required by `ARCHITECTURE.md` and `ai-contract.md §8`. Currently `ai/domain/` is empty.

**What to build (Backend Worker):**
```python
# backend/ai/domain/emissions.py
class EmissionsDomainAI(DomainAIOperations):
    app_identifier = "emissions"
    app_display_name = "Carbon Footprint"

    def get_domain_context(self) -> DomainContext:
        return DomainContext(
            app_identifier="emissions",
            domain_knowledge={
                "protocol": "GHG Protocol Corporate Standard",
                "scopes": {
                    "scope_1": "Direct emissions from owned/controlled sources",
                    "scope_2": "Indirect emissions from purchased energy",
                    "scope_3": "All other indirect emissions in value chain",
                },
                "ar_version": "IPCC AR6",
                "units": ["tCO2e", "kgCO2e", "MtCO2e"],
                "calculation_methods": ["location-based", "market-based"],
            },
            domain_config={
                "default_gwp_version": "AR6",
                "boundary_approaches": ["operational", "equity share", "financial control"],
            },
        )
```

- `CarbonIntelligence` calls `get_domain_context()` and injects into system prompt for all emissions AI calls
- Add 10 tests in `ai/tests/test_domain_emissions.py`

---

## Sprint 8 — Streaming SSE: human speed (2–3 weeks)
**Goal:** AI responses arrive token by token, typing effect — not as a single blob.
**Spec:** To be written as `tasks/SPRINT-8-STREAMING.md`

This is the "Pulse fills in the form at human speed" piece from the original vision.

**Architecture:**
```
CarbonIntelligence.send_message_stream()
    → engine_runtime.dispatch_task_stream()  [new: yields chunks]
    → TurnPipelineRunner.run(stream_callback=...)
    → Django StreamingHttpResponse (SSE: text/event-stream)
    → Frontend EventSource → animates tokens into message bubble
    → When complete: trigger form-fill if intent_signal="create"
```

**Scope for this sprint:** `chat` and `dq_suggest` only.
**Workers:** Backend Worker (SSE endpoint) + Frontend Worker (EventSource + typing animation)

---

## Sprint 9 — Feedback persistence: the learning flywheel (2 weeks)
**Goal:** Every accept/reject/correct from the user feeds AI's knowledge.
**Spec:** To be written as `tasks/SPRINT-9-FEEDBACK.md`

Without this, AI doesn't learn. With this, every user interaction makes AI smarter
for that org's specific data patterns.

| Task | Worker | Detail |
|---|---|---|
| Add `outcome` + `correction_text` to `AIMessage` + migration | Backend Worker | outcome: accepted/rejected/corrected/ignored |
| `POST /ai/workspace/conversations/{id}/messages/{id}/feedback/` | Backend Worker | Updates outcome on message |
| Accept/Reject/Correct buttons on AI message bubbles | Frontend Worker | Only on AI messages, not user messages |
| Async learning job | Backend Worker | Reads accepted/corrected messages → updates KG weights + long-term memory |

---

## After Sprint 9: system is complete for DQ+AI

At this point:
- User clicks AI in DQ workspace → AI knows context (Sprint 6)
- AI suggests a rule using GHG-aware vocabulary for emissions (Sprint 7)
- Suggestion streams in token by token into the form (Sprint 8)
- User approves → rule created → tested → result reported
- AI remembers the user accepted this style of rule (Sprint 9)
- Next time: AI suggests even better (feedback loop active)

---

## Future backlog (no sprint yet)

| Item | Notes |
|---|---|
| Monaco Editor for DQ rule JSON | Sprint 1B Phase C — professional code editor |
| OrganizationalBoundary + BaseYear frontend | Backend done, no UI |
| ai/domain/water.py | When water domain app starts |
| Chunk size optimization | MUI 643kB — needs manual chunking |
| Fix 53 react-hooks/exhaustive-deps warnings | No errors, cleanup sprint |
| Production v1.3 tag + deploy | After Sprint 3 (AI Workspace Phase 2) |

---

## Worker delegation

```bash
# Start a worker session:
.ai-toolkit/scripts/activate.sh backend-worker   # or frontend-worker, devops-worker

# Worker reads in order:
# 1. project.config.md
# 2. ARCHITECTURE.md        ← system overview
# 3. ROADMAP.md             ← which sprint we're on
# 4. tasks/SPRINT-N-*.md    ← exact spec for their sprint
# 5. .ai-toolkit/shared/ai-contract.md  (for any AI work)
```

Each sprint spec names the exact files to touch and the verification gate.
Workers NEVER touch files outside their sprint spec.
