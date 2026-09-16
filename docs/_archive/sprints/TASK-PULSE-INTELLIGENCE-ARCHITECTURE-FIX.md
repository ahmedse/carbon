# TASK: Pulse Intelligence Architecture — Structural Fixes After QA Audit

**To:** Master Architect  
**From:** QA Validator (post deep-simulation execution)  
**Priority:** P0 — Architectural  
**Evidence Base:** 22 real API scenarios executed, responses captured, scored  

---

## CONTEXT: THE VISION (READ THIS FIRST)

Pulse is NOT a Carbon feature. It is a **portable intelligence kernel**.

The goal is a standalone package — `pulse/` — that can be copied to any project (healthcare, logistics, finance, another sustainability app) with minimal bootstrap changes. Domain knowledge (carbon scopes, DQ rule types, table names, field patterns) is **not hardcoded** anywhere in the intelligence layer. It lives in:

- **Knowledge Graph** — entities, relationships, domain facts
- **Skill Playbooks** — reusable reasoning procedures
- **Memory Layers** — episodic (what happened), semantic (what is known), working (what is active right now)
- **Well-defined Friction Points** — contracts between the intelligence layer and the host app

The intelligence layer (reasoning, planning, entity tracking, preference learning, fallback handling) must work **regardless of domain**. You must not fix a "water table" memory issue by adding carbon-specific code. You fix the **entity tracking system** so it works for water tables, invoices, patients, or anything else.

If a fix requires knowing the word "carbon" or "DQ" or "email" to work, it's a hardcoded workaround, not a fix.

---

## EVIDENCE: QA EXECUTION RESULTS

22 scenarios were executed live against the Pulse API (`/carbon-api/ai/workspace/`). These are **real Pulse responses**, not simulated.

### Aggregate Results

| Batch | Scenarios | Pass Rate |
|-------|-----------|-----------|
| Batch 1 | 9 | 56% |
| Batch 2 | 13 | 23% |
| **Combined** | **22** | **38%** |
| **Target** | — | **≥70%** |

---

## FINDINGS: 6 ARCHITECTURAL GAPS (Not Domain Gaps)

### GAP-1: Empty Response on Unknown Query (P0)

**Evidence:**
- Query: `"What's the difference between GHG Protocol methodology and GRI standards?"` → response is `...` (empty string)
- Query: `"Which Water table — Water Usage or Water Quality?"` → response is `...` (empty string)
- HTTP status: 200 OK (API succeeded, intelligence produced nothing)

**Root Cause:** The intelligence layer has no **graceful fallback skill**. When the LLM produces no content (token limit? context gap? routing miss?), nothing intercepts it. The conversation stores an empty assistant message.

**What a Fix Looks Like:**  
A fallback skill that fires when `response.strip() == ""`. It should:
1. Check if the query was ambiguous → ask for clarification
2. Check if topic is outside known skill coverage → say so explicitly
3. Never return empty — always produce a navigable response

**What a Fix Does NOT Look Like:**  
Adding `if 'GHG' in query: return hardcoded_answer`. That's not intelligence.

---

### GAP-2: Working Memory Does Not Track User-Named Entities (P0)

**Evidence — Turn-level failure:**
```
Turn 1: "I want to validate the Water Consumption table"
Turn 2: "Should I profile it first or create rules?"
Pulse response: Generic answer — never mentions "Water Consumption"
```

**Evidence — Disambiguation failure:**
```
Query: "Which Water table — Water Usage or Water Quality?"
Pulse response: (empty — GAP-1 triggered)
```

**Evidence — Explicit scoping works:**
```
Query: "Focus on Water Consumption for now. What's the first step?"
Pulse response: References "Water Consumption" ✅
```

**Root Cause:** When the user names an entity (table, field, module, dataset), Pulse does not extract it into **working memory**. So when Turn 2 says "it" or "that", the entity is gone. The LLM guesses or ignores.

**What a Fix Looks Like:**  
A working memory slot that:
1. Extracts named entities from user messages (tables, fields, modules, datasets, time periods)
2. Tracks the **active entity** (most recently focused)
3. On disambiguation: if multiple entities of the same type exist, asks user to pick one, stores the answer
4. Injects active entity context into every subsequent LLM prompt in that conversation

This is domain-agnostic. "Water Consumption" is just a string. The entity tracker doesn't know it's a table in Carbon — it just knows the user said "focus on this".

**What a Fix Does NOT Look Like:**  
A lookup table of known carbon table names. That's a hardcoded domain map.

---

### GAP-3: Anaphora Resolution Is Not Reliable (P1)

**Evidence:**
```
Turn 1: "Focus on Water Consumption. What's the first step?"  → Pulse mentions "Water Consumption" ✅
Turn 2: "Now should I validate it or profile it?"
Pulse response: Mentions "water" but never "validate" or the entity explicitly → 67% score
```

**Root Cause:** Even when working memory has the entity (partially — see GAP-2), the anaphora resolver ("it", "that", "this table") does not reliably substitute the active entity into the LLM context window.

**What a Fix Looks Like:**  
Before sending to LLM, a pre-processing step resolves pronouns and deictic references:
- "it" → the active entity in working memory
- "that rule" → the last mentioned rule entity
- "those fields" → the active field set
This is a rewrite step: `"validate it"` → `"validate Water Consumption"` before LLM sees it.

---

### GAP-4: In-Session Preference Signals Ignored (P1)

**Evidence:**
```
Query 2: "I'm in a hurry — can you give me 2-minute answers next time?"
Query 3: Response is 589 chars (vs 686 baseline — only 14% shorter, threshold: 30%)
```

**Root Cause:** The learning layer does not monitor conversation messages for **preference signals**. "In a hurry", "keep it brief", "be more detailed", "explain everything", "skip the intro" are all preference signals that should update a session preference vector and change the system prompt for remaining turns.

**What a Fix Looks Like:**  
A preference classifier that runs on every user message:
1. Detects preference signals (tone: brief/verbose, format: bullets/prose, depth: expert/beginner)
2. Writes them to conversation metadata (session scope)
3. The system prompt assembler reads session preferences and adds constraints ("Respond in ≤150 words", "Use bullet points only", etc.)

Domain-agnostic. Works for any topic.

---

### GAP-5: Terminology Representation Is Prose, Not Graph-Structured (P1)

**Evidence:**
- Query: "Email fields with 3% nulls — what DQ rule?" → Pulse says "Not Null Rule" (correct) but score 50% because keyword `not_null` not present
- Query: "I have 5 tables — where to start?" → Pulse says "most critical to business" (correct) but score 40% because keywords `priority`, `risk`, `data_quality` not used
- Query: "40% records failed — next step?" → Pulse says "Analyze the failures" (correct) but score 60% because `root_cause`, `sample` not used

**Root Cause (TWO PARTS):**

Part A — The **scoring methodology** is too rigid (keyword matching). This is a test design issue, not a Pulse issue. Pulse is actually reasoning correctly in all these cases. The assessor should use semantic similarity against the concept graph, not keyword presence.

Part B — Pulse's vocabulary is **inconsistent across responses**. It sometimes says "not null" (human prose) vs `not_null` (platform term). This inconsistency makes it unreliable as a coworker that speaks the platform's language.

**What a Fix Looks Like (Part B):**  
The DQ skill playbook should include a **canonical terminology map** in the knowledge graph. When generating DQ guidance, the skill resolves concepts through this map:
- concept: "nullability check" → platform term: `not_null`
- concept: "format validation" → platform term: `pattern`
- concept: "value range" → platform term: `range_check`

This keeps terminology consistent without hardcoding responses. The map lives in the knowledge graph, not in Python.

**What the Assessor Fix Looks Like (Part A):**  
The QA scoring should compare against concept embeddings, not keyword strings. A response saying "ensure the field is never empty" should score the same as one saying "add a not_null rule".

---

### GAP-6: Knowledge Coverage Is Uneven (P1)

**Evidence:**
- Carbon Scope 1/2/3 classification: **100% ✅** (rich knowledge)
- GHG Protocol vs GRI standards comparison: **0% ❌** (empty response)
- ETL pipeline automation: **60%** (partial knowledge)
- Multi-table disambiguation: **0%** (no handling)

**Root Cause:** Knowledge graph coverage is incomplete. Some subgraphs (GHG scope classification, emissions sources) are fully populated. Others (reporting standards comparison, pipeline operations) are sparse or missing.

**What a Fix Looks Like:**  
An audit of the knowledge graph skill coverage. Each skill should declare what topics it covers and what it explicitly does not cover. A **skill routing layer** should:
1. Know which skills cover which topic domains
2. Route queries to the right skill
3. When no skill covers a topic → trigger GAP-1 fallback gracefully

---

## THE ARCHITECTURAL FIX DIRECTION

The fixes must follow this principle: **decouple intelligence from domain**.

```
WRONG: if "GHG" in query: load_ghg_knowledge()
RIGHT: query → embedding → skill router → matching skill(s) → compose response

WRONG: if "water" in entity: remember_water_table = entity  
RIGHT: entity_extractor(message) → working_memory.set_focus(entity, type=USER_NAMED)

WRONG: if "hurry" in message: set_short_mode = True
RIGHT: preference_classifier(message) → session_prefs.update(verbosity=BRIEF)
```

The intelligence layer must speak in terms of **entities, intents, preferences, skills, and graph nodes** — never in terms of "carbon", "water", "email", or any other domain concept.

---

## STANDALONE PACKAGE TARGET

When these fixes are complete, the `pulse/` package should be extractable and reusable. The directory structure should reflect this:

```
pulse/
  core/
    cognition/         # Reasoning, planning (domain-agnostic)
    memory/
      working.py       # Active entity tracking, anaphora resolution
      episodic.py      # Conversation history, what happened
      semantic.py      # What is known (reads from KG)
    learning/
      preferences.py   # In-session preference classifier + applier
      growth.py        # Skill improvement over time
    dialogue/
      entity_extractor.py   # Named entity tracking from user messages
      anaphora.py            # Pronoun/reference resolution
      fallback.py            # Graceful handling of unknown/empty
  skills/
    base.py            # Skill contract (declare: covers, requires, produces)
    dq/                # DQ-specific playbooks (swappable)
    carbon/            # Carbon-specific knowledge (swappable)
  knowledge/
    graph.py           # Graph query interface (domain-agnostic reads)
    terminology.py     # Canonical term map per skill
  bootstrap/
    new_project.py     # "Copy and initialize" script for new domain
  friction/
    contracts.py       # Input/output schemas at every handoff point
```

The host app (Carbon) only provides:
1. The domain skill files (`skills/carbon/`, `skills/dq/`)
2. The knowledge graph data (populated by domain experts)
3. The bootstrap config (what skills to load, what KG to connect to)

The `core/` directory should never import from `skills/` or any domain module directly.

---

## WHAT TO RETURN

After implementing fixes, return to QA Validator (me) with:

1. **Code evidence** for each GAP fixed:
   - GAP-1: Show the fallback skill implementation
   - GAP-2: Show the entity extractor + working memory setter
   - GAP-3: Show the anaphora resolver pre-processor
   - GAP-4: Show the preference classifier + system prompt applier
   - GAP-5: Show the terminology map in the KG and how it's used
   - GAP-6: Show the skill coverage declarations + skill router

2. **Test evidence** for each fix:
   - A new pytest test per GAP (no hardcoded assertions on carbon/DQ domain terms — test the **mechanism**, not the vocabulary)

3. **Architecture evidence:**
   - Show that `core/` has zero imports from any domain skill or Carbon app module
   - Show that bootstrapping with a fake domain (e.g. a "library" domain with books/authors) works end-to-end through the same intelligence pipeline

4. **Re-run these specific scenarios** (same API calls) so I can re-score:
   - DIM1-S05 (was empty)
   - DIM2-S05 (was empty)  
   - DIM4-S01 (original Water Consumption memory loss)
   - DIM4-S02b (anaphora follow-up)
   - DIM5-S01 (preference adaptation)
   - DIM3-S02..S04 (reasoning — root_cause, sample, uncertainty)

---

## CONSTRAINTS

- No hardcoded domain terms in `core/` or `memory/` or `learning/`
- No `if "carbon" in` or `if "DQ" in` anywhere in the intelligence layer
- Every fix must be expressible as a domain-agnostic unit test
- The preference classifier must be trained/designed for signals in natural language, not keyword matching
- Empty responses are a P0 deploy-blocker — must be eliminated before reassessment
