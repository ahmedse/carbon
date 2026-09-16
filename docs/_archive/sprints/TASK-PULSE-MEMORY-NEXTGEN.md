# Pulse Memory — Next-Generation Enterprise Architecture Plan

**Authored by:** QA Validator (post deep-simulation evidence + live user session transcript)  
**Evidence base:** 110 live API scenarios, 6-turn memory test, 3 deep reasoning probes, real user conversation transcript (2026-08-24)  
**Status:** Proposed — dispatch to Master Architect + Backend Worker  

---

## 1. DIAGNOSIS — What We Know From Evidence

### What works today
| Layer | Module | What it does |
|-------|--------|---|
| Working memory | `memory/working.py` | Tracks active named entity per conversation (GAP-2 fix) |
| Short-term | `memory/short_term.py` | Rolling message window (token-budgeted) passed to LLM |
| Episodic | `memory/episodic.py` | Event records with decay, causal chains, persistence |
| Long-term | `memory/long_term.py` | Persistent facts with temporal validity + contradiction detection |
| Preference | `learning/preferences.py` | In-session verbosity/format/depth signals (GAP-4 fix) |

### What is broken or missing (from evidence)

**GAP-M1: Numeric fact store (T4 failure)**  
User stated: FC=12, EU=5. User corrected: EU=7.  
The LLM had to compare 7 vs 8 to answer "which is smallest" and got it wrong.  
Root cause: numeric facts are stored as prose in the conversation window. The LLM does the math. LLM arithmetic is unreliable.  
Fix needed: structured key-value fact ledger per conversation, with deterministic comparison outside the LLM.

**GAP-M2: Intent/preference contradiction detection (T5 failure)**  
User stated T2: "start with smallest." User stated T5: "I said I prefer largest."  
Pulse accepted T5 without noting the contradiction.  
Root cause: no intent log. Preferences are stored as style signals (brevity, format) but not as explicit user goals/intentions.  
Fix needed: intent ledger that detects when new statements contradict prior stated goals.

**GAP-M3: Cross-session user profile (not tested, architecturally missing)**  
Every new conversation starts fresh. Pulse doesn't remember that "Ahmed manages Alamein campus energy" from the last session.  
Fix needed: user profile with domain expertise, role, org context — persisted between sessions, CBAC-scoped.

**GAP-M4: Memory attribution (not implemented)**  
When Pulse uses a memory fact in its response, the user can't see why or which memory it drew from. Non-auditable.  
Fix needed: memory citation in metadata (like knowledge citations already work).

---

## 1b. NEW GAPS — From Real User Session Transcript (2026-08-24)

A live user conversation revealed three additional critical failures, all worse than the memory test gaps because they are **visible to the user and erode trust**:

### GAP-M5: Capability Truthfulness (P0 — trust-breaking)

**Evidence from transcript:**
```
Turn 1 — Pulse: "I have memory... I can store important information permanently."
Turn 6 — Pulse: "I haven't stored this information. Currently, I don't have memory enabled."
```
Pulse claimed long-term memory capabilities it cannot deliver. Same session. Six turns apart.

**Root cause:** The system prompt or LLM's training causes it to describe a theoretical memory capability. But the actual `LongTermMemory.store_fact()` path is never called from the chat flow — there is no `memorize_fact` tool wired to the workspace chat pipeline. So the LLM *talks about* memory it cannot *execute*.

**Why this is P0:** A coworker that promises something and then says "I don't have that capability" in the same conversation cannot be trusted. Every subsequent claim Pulse makes is suspect.

**Fix required:**
- The system prompt must truthfully declare what memory operations are currently executable vs theoretical
- OR: wire a `memorize_fact` tool to the chat pipeline so the capability is real
- The honesty constraint from GAP-1 (HonestUncertaintyHandler) must extend to capability claims: Pulse must only promise what it can execute right now

**Principle: Never claim a capability you cannot demonstrate in the same turn.**

---

### GAP-M6: Pending Action State / Confirmation Flow (P0 — broken UX)

**Evidence from transcript:**
```
Turn 3 — Pulse: "Would you like me to store the fact that you are Ahmed, from Egypt, Alexandria?"
Turn 4 — User: "yes"
Turn 5 — Pulse: "I wasn't able to generate a response. This may be a temporary issue."
         + dumps the full capabilities table
```

Pulse asked a yes/no question. User answered "yes." Pulse treated "yes" as a fresh, decontextualized query — the FallbackHandler/KnowledgeGap path fired because "yes" alone is short and looks uncertain to the S4 Critic.

**Root cause:**
1. When Pulse proposes a deferred action ("shall I store this?"), no **pending action state** is created. The next user message arrives with no memory of the open question.
2. "yes", "ok", "do it", "go ahead", "please" are single-word responses that look like knowledge gap queries to the current pipeline. They are not — they are confirmations of a prior Pulse question.
3. The existing two-phase consent mechanism (in the Flight Director, for tool mutations) handles this for explicit tool calls. It does not exist for in-conversation promises.

**Fix required — `dialogue/pending_action.py`:**
```python
class PendingActionStore:
    """Tracks open Pulse questions awaiting user confirmation.
    
    When Pulse asks "shall I [action]?", a PendingAction is stored with:
    - the promised action (callable name + args)
    - the expiry (expires after N turns or timeout)
    - the question Pulse asked
    
    Pre-S1: check if user message is a confirmation of a pending action.
    If yes: execute the action directly, do not send to LLM.
    Confirmation signals: "yes", "ok", "sure", "please", "do it", "go ahead",
                         "yes please", "store it", "remember it", affirmatives.
    """
    def set_pending(self, conv_id, action_fn, action_args, question_text, expires_turns=2)
    def check_confirmation(self, conv_id, user_message) -> PendingAction | None
    def clear(self, conv_id)
```

This is domain-agnostic. "yes" after "shall I create a DQ rule?" and "yes" after "shall I store your name?" both go through the same path.

---

### GAP-M7: Capability Tool Misfiring on Confusion (P1 — UX noise)

**Evidence from transcript:**
```
Turn 5 — After failing to handle "yes":
Pulse dumps the full "Your Access" work areas table
(Emissions & Carbon Data, Data Analysis & Reporting, Data Quality, ...)
```

When the pipeline doesn't know what to do, the `list_my_capabilities` tool fires and produces the capabilities table. This is the "graceful fallback" going to the wrong fallback. The user was not asking what they can access — they were confirming a memory action.

**Root cause:** The `list_my_capabilities` tool is in the curated tool set exposed to S3 Draft. When the LLM is confused about what to do with a short message, it defaults to "show capabilities" because that's always safe. It's not wrong in isolation but catastrophically wrong in context.

**Fix required:**
- `PendingActionStore.check_confirmation()` runs pre-S1. If a confirmation is detected, the pipeline short-circuits to execute the pending action and never reaches S3 Draft or the capability tool.
- The capability tool should only fire when the user explicitly asks about access/capabilities, never as a confusion fallback. Add a salience check: `list_my_capabilities` requires `domain = "identity"` or explicit trigger phrase.

---

### Summary: New Gap Severity

| Gap | What broke | Severity | Visible to user? |
|-----|-----------|----------|-----------------|
| GAP-M5 | Claimed memory it can't use → then denied having it | 🔴 P0 | Yes — direct contradiction |
| GAP-M6 | "yes" after Pulse's own question → fallback fired | 🔴 P0 | Yes — broken flow |
| GAP-M7 | Capabilities table dumped on confusion | 🟡 P1 | Yes — noisy/wrong |

---

## 2. RESEARCH GROUNDING

### What the research says

**MemGPT (Packer et al., 2023)**  
Key insight: LLMs have a fixed context window; genuine long-term memory requires an OS-like page-in/page-out mechanism. Main memory (context window) ↔ external storage (database). The LLM itself manages what to load.  
Applicable: the "eviction and retrieval" design in our episodic memory already follows this model. What's missing is structured fact representation vs raw text.

**Generative Agents (Park et al., 2023)**  
Key insight: three memory operations — storage (stream), retrieval (recency + importance + relevance), and reflection (synthesis into higher-order facts). The reflection step is what creates durable knowledge from ephemeral experience.  
Applicable: we have storage. We have retrieval. We are missing **reflection** — the consolidation pass that turns "user said EU=7" (episodic) into "Electricity Usage table has 7 fields" (semantic fact, corrected).

**HippoRAG (2024)**  
Key insight: use a knowledge graph as the long-term memory substrate. Facts are graph nodes. Retrieval is graph traversal + vector similarity. This handles "which table is smallest" with deterministic graph queries, not LLM inference.  
Applicable: the KG store already exists. What's missing is a **conversation-scoped fact subgraph** that captures user-stated facts as typed nodes with numeric attributes.

**A-MEM / MemoryBank (2024)**  
Key insight: memory itself should be agentic — the system decides what to remember, how to index it, and when to update or invalidate it. Not just "write everything, retrieve by similarity."  
Applicable: the LongTermMemory `supersede_fact()` method already implements invalidation. What's missing is the **agent-driven write decision**: after each turn, an async pass extracts structured facts from the conversation and writes them to the fact store.

### What enterprise requires beyond research

- **CBAC scoping**: every memory fact must carry `host_user_id` + `org_unit_id` — no cross-tenant bleed
- **Auditability**: every memory write is logged with source conversation + turn ID
- **Deletability (GDPR)**: user can request memory erasure; fact store supports `valid_to` tombstones
- **Explainability**: response metadata includes `memory_citations` alongside `knowledge_citations`
- **Version history**: corrections (T3: EU=7 not 5) create a new fact version, old fact is tombstoned with `valid_to`, both are queryable

---

## 2b. NON-NEGOTIABLE — STRICT LLM / PULSE CAPABILITY SEPARATION

**Rule: Pulse may only claim a capability that a tool result or deterministic engine
behaviour can demonstrate in the same turn. Native LLM abilities are NEVER marketed as
Pulse's own capabilities.**

Two capability vocabularies — never conflated:

| Source | What it is | Examples | May Pulse claim it? |
|--------|-----------|----------|---------------------|
| **LLM (native)** | Model-intrinsic ability — no tool, no DB, no engine | NL understanding, prose generation, world knowledge, translation, summarisation, arithmetic | Only if demonstrated in-turn. NEVER claim *persistent* or *stateful* abilities from this alone. |
| **Pulse (tool-grounded)** | Ability backed by a registered tool + executor + verified result | `learn_fact`/`forget_fact` (memory), `create_dq_rule`, `call_host_api`, `search_knowledge`, `list_my_capabilities`, navigation | YES — but only AFTER the tool ran and returned success. |

**Binding rules:**
1. **No capability claim without a demonstration.** "I can remember X" is a lie unless a
   memory tool ran and confirmed the write in THIS conversation. "I remember X from last
   session" is a lie unless a persisted memory read returned X.
2. **`list_my_capabilities` is machine-grounded, never LLM self-description.** It enumerates
   the user's RBAC-scoped access manifest + registered tools. The LLM must NOT append prose
   capabilities ("and I can also translate text") that the manifest doesn't list.
3. **The system prompt declares memory honestly.** It states exactly which memory operations
   are executable now (propose `learn_fact` → user confirms) vs. not yet wired (cross-session
   profile) — never "I have persistent memory" as a blanket claim.
4. **A capability is only "real" when it is in the curated chat tool set AND its executor
   returns a confirmed result.** An executable tool NOT exposed to the chat planner
   (`learn_fact`/`forget_fact` today) is, from the user's perspective, *not a capability* —
   the LLM must not describe it as available.

**Consequence for LLM arithmetic/recall:** the LLM's ability to "remember" prose from earlier
in the conversation is a *native* ability and is unreliable; it is NOT Pulse's memory system.
Pulse must never describe in-context LLM recall as "my memory". Structured, verifiable memory
= the fact ledger / store (M1+), and only those may be described as "what I remember".

---

## 3. THE ARCHITECTURE — 4-TIER MEMORY KERNEL

```
┌──────────────────────────────────────────────────────────────────┐
│  Tier 1: Working Memory (per-turn, in-process)                   │
│  ├── EntityFocus      active named entity + type                 │
│  ├── FactLedger       structured key-value facts this session    │  ← NEW
│  └── SessionPrefs     verbosity / format / depth                 │
├──────────────────────────────────────────────────────────────────┤
│  Tier 2: Episodic Memory (per-conversation, DB-persisted)        │
│  ├── MessageWindow    rolling token-budgeted history             │
│  ├── IntentLog        what user said they want to do (goals)     │  ← NEW
│  ├── EventLog         significant events (errors, milestones)    │
│  └── ContradictionGuard  detects when new input conflicts intent │  ← NEW
├──────────────────────────────────────────────────────────────────┤
│  Tier 3: Semantic Memory (cross-session, DB-persisted + KG)      │
│  ├── FactStore        LongTermMemory (exists, extend)            │
│  ├── UserProfile      expertise, role, org, preferences          │  ← NEW
│  └── DomainGraph      org entities as KG subgraph                │  ← extend
├──────────────────────────────────────────────────────────────────┤
│  Tier 4: Reflection Engine (async, post-turn)                    │
│  ├── FactExtractor    LLM pass: extract structured facts         │  ← NEW
│  ├── Consolidator     episodic → semantic promotion              │  ← NEW
│  └── ProfileUpdater   update user profile from conversation      │  ← NEW
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. PHASE PLAN — 4 PHASES

### Phase M0: Trust Repair (P0 — MUST ship before any other memory work)

**What it fixes:** GAP-M5 (capability lies), GAP-M6 (broken confirmation flow), GAP-M7 (capability dump on confusion)  
**Why first:** Building richer memory on top of a system that contradicts itself about memory is pointless. Every new capability you add becomes untrustworthy if the system already broke trust on the same topic.  
**Timeline:** 1 sprint

**Fix 1 — Capability truthfulness (GAP-M5)**

The system prompt must not claim memory capabilities that aren't wired. Two options:

*Option A (honest degradation):* Remove all claims about "long-term memory" from the LLM's capability description until `memorize_fact` is wired as a real tool. Replace with: "I can remember context within our conversation. I cannot currently store facts permanently across sessions."

*Option B (wire the tool):* Add `memorize_fact` to the curated tool set in `runner.py`. Implement it in `host_executor.py` as a call to `LongTermMemory.store_fact()`. Now the claim is true.

**Option B is correct** — it makes the capability real rather than hiding it. Option A is a regression.

**Implementation finding (verified 2026-08-24):** the tool ALREADY exists and is fully
wired — `engine/agent/tools.py` defines `learn_fact` + `forget_fact` with executors
`execute_learn_fact` / `execute_forget_fact` (registered in `TOOL_EXECUTORS`), and
`engine/agent/executor.py` already has the propose→confirm flow (`create_pending_execution`,
`cancel_pending_learn_facts`, `confirm_execution`, `decline_execution`) backed by the
`ToolExecution` table (RULE_21: propose, never auto-write). The ONLY missing link is that
`learn_fact` / `forget_fact` are **absent from the `_draft_tools` allow list in
`runner.py`** (the `allow` set ~line 66). So the chat planner never sees the memory tools,
falls back to prose ("I can store this permanently"), and can't back it up. Fix 1 = add
`learn_fact` + `forget_fact` to that `allow` set + make the persona/system prompt describe
memory truthfully ("I can propose to remember something; it is stored only after you
confirm"). No new tool, no new executor, no new DB model.

**Fix 2 — Pending action store (GAP-M6)**

New module: `engine/cognition/dialogue/pending_action.py`  
- Stores open Pulse proposals ("shall I X?") with the action + expiry  
- Pre-S1 check: is the user message a confirmation? ("yes", "ok", "sure", "do it", "please", "go ahead", "store it", "remember it", "yes please")  
- If confirmation detected: execute pending action directly, bypass S3/LLM entirely, return confirmation message ("Done — I've stored: [fact]")  
- If no pending action: "yes" routes normally through pipeline  

**Fix 3 — Capability tool salience guard (GAP-M7)**

In `runner.py`, the `list_my_capabilities` tool must only be included in `draft_tools` when:
- `salience.domain == "identity"` OR
- User message explicitly contains "what can you do", "what do you have access to", "show me capabilities", "what features"

It must NOT be in the default tool set for `domain = "general"` or `domain = "conversational"`. Current code exposes it always — that's why it fires as a confusion fallback.

---

### Phase M1: Structured Fact Ledger + Contradiction Guard (P0 — fixes observed failures)

**What it fixes:** T4 (arithmetic), T5 (contradiction)  
**Timeline:** 1 sprint

**New module: `memory/fact_ledger.py`**

```python
class FactLedger:
    """In-conversation structured fact store. Thread-safe, in-process.
    
    Stores typed facts extracted from user messages as structured records,
    not prose. Enables deterministic comparison (no LLM arithmetic) and
    contradiction detection.
    """
    # Fact types: NUMERIC (name, value, unit), BOOLEAN (claim, truth),
    #             PREFERENCE (goal, direction), ENTITY (name, type, attributes)
    
    def record_numeric(self, conv_id, name, value, unit=None, source_turn=None)
    def record_preference(self, conv_id, intent, value, source_turn=None)
    def get_numeric(self, conv_id, name) -> NumericFact | None
    def compare_numeric(self, conv_id, names, direction="min") -> str  # deterministic
    def check_preference_conflict(self, conv_id, intent, new_value) -> ConflictResult
    def update_numeric(self, conv_id, name, new_value, source_turn=None)  # creates version
```

**New module: `cognition/dialogue/fact_extractor.py`**

```python
class TurnFactExtractor:
    """Extracts structured facts from a user message and writes to FactLedger.
    
    Runs post-S1 (after salience, before S3 draft).
    Patterns:
    - "[entity] has [N] fields/records/rows"  → NUMERIC
    - "I want to [verb] [X] first/before/instead" → PREFERENCE
    - "actually [entity] has [N]..."  → NUMERIC update (with correction flag)
    - "I said I prefer [X]" → PREFERENCE (triggers contradiction check)
    Domain-agnostic: extracts any entity+numeric pattern, not Carbon-specific.
    """
    def extract(self, conv_id, user_message) -> list[ExtractedFact]
```

**Modified: `runner.py`**
- Post-S1: `TurnFactExtractor().extract()` → writes to `FactLedger`
- Pre-S3: `FactLedger.to_prompt_fragment()` → appended to system prompt (structured facts section)
- Pre-S3: `FactLedger.check_preference_conflict()` → if conflict, prepend `"Note: earlier in this conversation you said [X]. You now say [Y] — I'll follow your latest instruction but wanted to flag this."`

**Tests required:**
- `test_fact_ledger.py`: numeric store/retrieve, correction versioning, comparison (no LLM)
- `test_fact_extractor.py`: pattern extraction, entity-agnostic assertions
- `test_contradiction_guard.py`: intent conflict detection across turns
- All tests must use placeholder entities (not "Fuel Consumption", "carbon")

---

### Phase M2: Intent Log + Cross-Session User Profile (P1 — coworker continuity)

**What it fixes:** preference forgetting across sessions, user role/expertise lost between conversations  
**Timeline:** 1 sprint

**New module: `memory/intent_log.py`**

```python
class IntentLog:
    """Per-conversation explicit goal/intent tracking.
    
    Distinct from preferences (how) — records what user said they want to
    accomplish this session (what). Persisted to DB within conversation scope.
    
    Examples:
    - "I want to start with the smallest table" → intent(verb=start, target=smallest_table)
    - "I need to have all rules ready for the audit" → intent(verb=complete, deadline=audit)
    """
    async def record_intent(self, conv_id, verb, target, deadline=None)
    async def get_active_intents(self, conv_id) -> list[Intent]
    async def check_conflict(self, conv_id, new_verb, new_target) -> ConflictResult
```

**New module: `memory/user_profile.py`**

```python
class UserProfile:
    """Cross-session user profile — persisted in DB, CBAC-scoped.
    
    Captures:
    - Domain expertise level (detected from conversation signals)
    - Role/function (self-stated or inferred)
    - Org context (campus, project, team)
    - Communication preferences (persistent, not just session)
    - Known entities (tables, modules, data they work on regularly)
    
    Updated asynchronously by the Reflection Engine after each conversation ends.
    Never blocks the turn pipeline.
    """
    async def get_profile(self, host_user_id) -> ProfileData
    async def update_from_conversation(self, host_user_id, conversation_id)
    async def to_system_prompt_fragment(self, host_user_id) -> str
```

**DB model: `ai.models.UserProfile` (new)**
- `host_user_id` FK, `org_unit_id`, `expertise_level`, `role`, `org_context_json`, `preferences_json`, `known_entities_json`, `updated_at`

---

### Phase M3: Reflection Engine (P1 — memory grows with use)

**What it fixes:** episodic → semantic promotion, so the system gets smarter over conversations  
**Timeline:** 1 sprint

**New module: `cognition/reflection/engine.py`**

```python
class ReflectionEngine:
    """Async post-conversation pass that promotes episodic facts to semantic memory.
    
    Runs after conversation status transitions to 'completed'.
    Three passes:
    1. FactPromotion: extract structured facts from conversation → LongTermMemory
    2. ProfileUpdate: update UserProfile from conversation signals
    3. PlaybookRefinement: if user corrected Pulse 3+ times on same topic → update skill playbook
    
    Never runs during a turn (non-blocking).
    Idempotent: safe to re-run on same conversation.
    """
```

**Reflection trigger:** in `workspace_api.py`, when a conversation transitions to `completed`, dispatch `ReflectionEngine.run(conversation_id)` via existing async task queue (Redis).

**Memory citation in responses:**
- Extend `AgentResponse` with `memory_citations: list[MemoryCitation]`
- `MemoryCitation`: `{fact_id, content, source_conversation_id, source_turn}`
- Surface in workspace API response alongside existing `knowledge_citations`

---

## 5. QUALITY GATES

Every memory component must satisfy:

1. **Domain-agnostic test**: test files use "Alpha Table", "Beta Dataset", "Widget" — never "carbon", "DQ", "emission"
2. **CBAC isolation**: no memory fact can be read by a different `host_user_id` or `org_unit_id`
3. **Deterministic comparison**: `FactLedger.compare_numeric()` must produce correct results for any input without calling the LLM
4. **Non-blocking**: all DB writes happen async; no turn latency increase > 20ms from memory operations
5. **Graceful degradation**: if any memory module fails, the turn completes without it (never blocks)
6. **Auditability**: every fact write includes `source_conversation_id` + `source_turn_index`
7. **GDPR tombstone**: `LongTermMemory.delete_user_facts(host_user_id)` sets `valid_to = now()` on all facts

---

## 6. METRICS — HOW WE KNOW IT WORKS

**After Phase M0 — trust repair:**

| Scenario | Before | Target |
|----------|--------|--------|
| "memorise I am Ahmed from Egypt" → "yes" | Fallback + capability dump | ✅ Executes store, confirms "Done" |
| Turn 1: "I have memory" / Turn 6: "I have no memory" | Contradiction | ✅ Both turns consistent |
| Capability table on confusion | Fires unexpectedly | ✅ Only on explicit capability query |

**After Phase M1 — structured fact ledger:**

| Check | Current | Target |
|-------|---------|--------|
| T4: EU=7, arithmetic to find smallest | ❌ Wrong | ✅ Deterministic |
| T5: contradiction flagged | ❌ Missed | ✅ Flagged |
| 6-turn test score | 4/6 = 67% | ✅ 6/6 = 100% |

**After Phase M2 + M3 — user profile + reflection:**
- New conversation: Pulse greets Ahmed without asking who he is
- 3rd conversation: Pulse knows Ahmed is an ESG analyst at AASTMT working on Alamein campus energy
- Corrections in session 1 improve skill responses in session 2

---

## 7. DISPATCH INSTRUCTIONS

**To Master Architect:**
Design the implementation for each phase. Each phase is independently deployable. Phase M1 is P0 (fixes observable failures). Phases M2 and M3 are P1.

**Constraints:**
- All new modules in `engine/memory/` or `engine/cognition/` — no imports from `catalog/`, `dq/`, `emissions/`
- `FactLedger` is in-process (no DB for per-turn operations) — same design as `WorkingMemory`
- `IntentLog` is DB-persisted (must survive connection drops mid-conversation)
- `UserProfile` reads must add < 5ms to turn latency (cached after first load per conversation)
- Phase M1 must not break any of the 1,015 existing tests

**Reference the existing patterns:**
- `memory/working.py` — singleton, thread-safe `_lock`, `get_working_memory()` accessor
- `memory/long_term.py` — `supersede_fact()` for versioning, `valid_from/valid_to` for temporal validity
- `cognition/dialogue/entity_extractor.py` — regex-based extraction, domain-agnostic
- `cognition/turn/runner.py` — where to wire new pre/post turn hooks
