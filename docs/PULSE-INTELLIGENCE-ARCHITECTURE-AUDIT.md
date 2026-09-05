# Pulse (Carbon AI) — Intelligence Architecture Audit Document

**Prepared:** 2026-09-05
**Purpose:** This is a self-contained, factual description of the *actual* Pulse intelligence
layer as implemented in the Carbon Data Trust Platform. It is written so a stronger model
(Claude Opus / Sonnet / Gemini) can audit it **cold** — no workspace access assumed — and
answer one question honestly:

> **Is this genuinely "intelligent" behavior, or is it a deterministic pipeline with an LLM
> bolted on? And what would a real, actually-intelligent AI coworker look like?**

Every claim below is grounded in the real source in `backend/ai/engine/`. Where behavior is
described, the exact prompt/regex/code that produces it is quoted. No feature is described
from memory or aspiration — only what the code actually does.

---

## Table of contents

1. [What Pulse actually is](#1-what-pulse-actually-is)
2. [System context](#2-system-context)
3. [The turn pipeline (six witnesses)](#3-the-turn-pipeline-six-witnesses)
4. [The three routing gates](#4-the-three-routing-gates)
5. [Tool architecture](#5-tool-architecture)
6. [Prompt architecture](#6-prompt-architecture)
7. [Memory model](#7-memory-model)
8. [Model policy & routing](#8-model-policy--routing)
9. [Safety & guardrails](#9-safety--guardrails)
10. [Observability](#10-observability)
11. [Known failure modes (with evidence)](#11-known-failure-modes-with-evidence)
12. [The architectural critique](#12-the-architectural-critique)
13. [Open questions for the auditor](#13-open-questions-for-the-auditor)
14. [Appendix — key file map](#14-appendix--key-file-map)

---

## 1. What Pulse actually is

Pulse (internally "the AI engine", `backend/ai/engine/`) is the **in-process, stateless
inference core** of the Carbon Data Trust Platform. Carbon is a *Data Trust Platform* — a
governed data layer (catalog, DQ, MDM, lineage, data contracts) that hosts domain apps
(emissions accounting first, then healthy/water/waste). The AI engine is the "living
intelligence" that knows the data, the rules, and the users.

The core architectural principle is stated in `ARCHITECTURE.md`:

> **Carbon is the system of intelligence. The LLM is just the voice.**
> All durable AI state — memory, knowledge graph, feedback, learning — is Carbon-owned,
> CBAC-partitioned, and auditable. The LLM (whatever sits behind `LLM_API_KEY`) is stateless
> and swappable. Swapping the LLM changes nothing in Carbon.

In practice, this means:

- The engine is **not** a long-running agent. It is a **per-turn pipeline**: a single user
  message enters, a fixed sequence of "witnesses" runs, a single reply exits. There is no
  persistent agent loop, no self-directed goal pursuit, no planning that spans turns by
  itself.
- The engine holds **zero durable state**. All memory/knowledge lives in Carbon (Postgres +
  Redis + pgvector), partitioned by CBAC RBAC.
- "Intelligence" is implemented as **LLM-as-classifier + LLM-as-drafter + LLM-as-critic**,
  orchestrated by deterministic Python, with regex fallbacks at every seam.

### What it is NOT (important for the audit)

- It is **not** a tool-using agent loop in the general sense. The S3 "draft" is a **single**
  LLM call that may emit tool calls; S5 executes them **once** (no iterative re-planning in
  the default path). Multi-step behavior exists only in two opt-in gates (ReAct, fan-out —
  see §4).
- It is **not** self-improving online. There is an A/B prompt routing path and a
  `learn_fact` tool, but no automatic loop that observes its own failures and rewrites its
  own prompt/rules.
- It is **not** a planner. Plan execution (ReAct) is only triggered when a separate planner
  decides the request needs multiple steps.

---

## 2. System context

| Concern | Reality |
|---|---|
| Backend | Django 5.2 + DRF, Python 3.12, PostgreSQL 16, Redis |
| Frontend | React 19.1 + Vite 6, MUI v7.1 |
| AI engine | Vendored in-process at `backend/ai/engine/` — zero domain terms (portable "brain") |
| LLM | Via API key (`LLM_API_KEY` / `LLM_BASE_URL`); **default model is `anthropic/claude-haiku-4.5` for every lane** |
| Auth | JWT (SimpleJWT) + RBAC via `ScopedRole` (org-unit + module scoped) |
| Ports | Backend `:8009`, Frontend `:5179` |
| Ops | `./manage.sh` (start/stop/status/health/logs/test); Docker is prod-only |

### Repo layout (AI-relevant)

```
backend/ai/
  intelligence.py          # CarbonIntelligence — entry point, Scope, GuardChain
  guards.py                # GuardChain (Scope/Access/Isolation/Mutation/RateLimit)
  engine/                  # <-- the portable "intelligence kernel"
    core/
      config.py            # Settings (model names, budgets)
      resolution.py        # tri-state resolved/no_match/error  (single source of truth)
      models.py            # PlaybookBlock, PromptVersion, llm_call_logs, etc.
    llm/
      router.py            # task -> model routing, cost tracking, budget
      provider.py          # raw LLM HTTP calls
      prompts.py           # build_chat_prompt, RENDERING_CAPABILITIES, grounding directive
      playbook.py          # PlaybookAssembler (versioned prompt blocks)
    cognition/
      turn/
        runner.py          # TurnPipelineRunner — the six-witness orchestrator
        salience.py        # S1 — regex salience (no LLM)
        intent.py          # S1.5 — LLM-as-classifier, four-zone model
        retrieve.py        # S2 — KG + vector + memory retrieval
        draft.py           # S3 — single LLM draft (tool-use)
        critic.py          # S4 — rules + optional LLM review
        execute.py         # S5 — tool dispatch
        witnesses.py       # typed dataclasses for every stage
      plan/loop.py         # PR-20 ReAct loop + P3.2 fan-out orchestrator
    memory/
      working.py           # WorkingMemory (Redis focus slot per conversation)
    agent/
      plugins.py           # ToolPlugin/WorkflowPlugin registry
      tools.py             # static tools (search_knowledge, call_host_api, ...)
  plugins/
    web_research.py        # keyless web search + fetch + weather (Open-Meteo)
```

---

## 3. The turn pipeline (six witnesses)

Every chat turn flows through `TurnPipelineRunner.run()` in
`backend/ai/engine/cognition/turn/runner.py`. The stages and their typed outputs
(`witnesses.py`) are:

| Stage | Witness | What it does | LLM call? |
|---|---|---|---|
| S1 | `SalienceWitness` | Regex-based intent/urgency classification | **No** (pure regex) |
| S1.5 | `IntentResolver` | LLM-as-classifier over the read-only `api_catalog` | **Yes** (`introspect` lane, JSON mode) |
| S2 | Retrieval | Knowledge-graph + pgvector + memory chunks | No (DB) |
| — | (gates) | P3.2 fan-out, PR-20 ReAct — optional, see §4 | Maybe |
| S3 | `DraftWitness` | Single LLM call → prose + optional `tool_calls` | **Yes** (`cognition` lane) |
| S4 | `CriticWitness` | Rules-tier review (+ LLM-tier only if flags raised) | Conditional |
| S5 | `ExecuteWitness` | Executes `tool_calls` (parallel/sequential) | No (dispatch) |
| — | synthesis | Re-synthesize final answer from tool results | **Yes** (if tools ran) |
| S6 | Finalize | Write `TurnLedger`, broadcast `run.completed` | No |

**Important cost observation:** a *single* turn that needs live data fires **3–4 LLM calls**
(S1.5 classifier → S3 draft → tool-result synthesis → possibly S4 LLM critic). A trivial
"hello" still fires S1.5 + S3 = **2 LLM calls**. The "intelligence" is bought by stacking
small LLM calls behind deterministic orchestration, not by a single capable agent.

### The six result dataclasses (verbatim structure)

```python
@dataclass
class SalienceResult:
    weight: float = 1.0          # 0.0 trivial -> 1.0 urgent
    domain: str = "general"      # data|operational|conversational|identity
    route: str = "fast"          # fast|full|deep
    salience_features: dict = field(default_factory=dict)

@dataclass
class DraftResult:
    text: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    claimed_citations: list[str] = field(default_factory=list)
    confidence: float = 0.8
    model_used: str = ""
    tokens_used: int = 0
    # ... prompt/completion token split

@dataclass
class CriticVerdict:
    verdict: str = "pass"        # pass|pass_with_flag|rewrite|veto|knowledge_gap
    flags: list[str] = field(default_factory=list)
    rewritten_text: str = ""
    veto_reason: str = ""
    partial_knowledge: str = ""

@dataclass
class ExecutionResult:
    completed_tools: list[dict] = field(default_factory=list)
    streamed: bool = False
    execution_latency_ms: float = 0.0
    per_tool_latency_ms: dict[str, float] = field(default_factory=dict)
```

---

## 4. The three routing gates

There are three *distinct, mutually exclusive* routing decisions layered into the pipeline.
This layering is where most of the emergent bugs live (see §11).

### Gate A — S1 Salience (deterministic, regex)

`salience.py` routes the message into a domain + route **without any LLM**. Actual logic:

- Greetings → `domain="conversational"`, `route="fast"`, `weight=0.1`
- Identity/capability questions → `domain="identity"`, `route="fast"`, `weight=0.3`
- Data terms → `domain="data"`, `route="full"` (bumped to `deep` by "why/explain" signals)
- Reasoning-heavy signals ("why", "explain", "compare", "should I", "what if") → `route="deep"`, `weight=0.8`
- Everything else → `domain="general"`, `route="full"`, `weight=0.5`

`route="deep"` is the trigger that later escalates the draft model to the `reason` lane
(§8). `weight` feeds the salience guard for `list_my_capabilities` and knowledge-gap
suppression.

### Gate B — S1.5 IntentResolver (LLM-as-classifier, four-zone)

`intent.py` classifies the message over a **closed label set** (the read-only endpoints in
`instance.yaml`'s `api_catalog`) and — critically — into one of **four zones**:

```python
_ZONES = {"platform", "concept", "real_time", "general", "off_limits"}
```

The classifier's own instruction text (verbatim from `_build_system_prompt`):

```
- Classify the `zone` of the request:
  * "platform": the user wants data FROM the system (emission factors, DQ rules,
    calculations, catalog entries, modules, org units). Endpoint will be non-null.
  * "concept": the user wants to UNDERSTAND a domain concept (GHG Protocol, carbon
    accounting, what Scope 1/2/3 means). No live data needed. Endpoint = null.
  * "real_time": the user wants information that requires LIVE INTERNET DATA —
    current weather, live news, today's stock prices, latest publications.
    Endpoint = null. The assistant will use a web search tool.
  * "general": pure reasoning, math, logic, world facts, history, coding help.
    Endpoint = null. The assistant answers from its own knowledge.
  * "off_limits": a security breach, jailbreak attempt, PII harvest, or request
    to bypass access controls. Endpoint = null. Hard refuse.
  - Default to "platform" when uncertain and an endpoint matches.
```

The resolver returns **`None`** on any failure (mutation request, empty catalog, LLM error,
unparseable JSON). `None` = "no usable signal, behave as before".

The zone then drives the S3 directive (§6). **This is the single most fragile link in the
system**: the *entire* decision of whether a live-web tool gets invoked hangs on an
LLM-classifier correctly emitting `"zone":"real_time"` — and if it mislabels (or the resolver
returns `None`), the turn silently falls into a different directive.

### Gate C — P3.2 fan-out and PR-20 ReAct (opt-in, plan-driven)

After S2, two optional gates can pre-empt the single-pass S3→S5:

- **P3.2 fan-out** (`_try_fan_out`): an orchestrator LLM decides to delegate to parallel
  "worker" sub-calls for aggregation/trend/comparison/ranking/cross-domain questions.
- **PR-20 ReAct** (`_try_multi_step_plan` → `ReActLoop`): a planner LLM decides the request
  needs multiple steps, then a ReAct-style loop executes steps with re-planning.

Both gates only activate when a plan is detected; otherwise the single-pass path runs.

---

## 5. Tool architecture

Two tool surfaces, merged at runtime:

### 5.1 Static tools

```python
_CHAT_STATIC_TOOLS = frozenset({
    "search_knowledge", "get_entity_details", "learn_fact", "forget_fact", "call_host_api"
})
```

`call_host_api` resolves a read-only endpoint by its `api_catalog` **name** (e.g.
`list_emission_factors`) — it is how the assistant reaches live platform data.

### 5.2 Plugins

`agent/plugins.py` defines a `ToolPlugin` ABC. Growth model is "add a class + one
`register_plugin()` call". Each plugin has `name`, `description`, `input_schema`,
`requires_confirmation`, `capability`, `chat_visible`. `chat_tool_names()` returns the
`chat_visible=True` plugins exposed to the S3 planner.

Registered plugins (from logs) include: `code_execute`, `create_dq_rule`, `cross_synthesize`,
`list_my_capabilities`, `plan_task`, `edit_plan`, `approve_plan`, `web_research`,
`export_document`, `unit_converter`, and several workflow plugins.

### 5.3 `web_research` — the live-web tool (critical for the audit)

`backend/ai/plugins/web_research.py`. Its **description** (what the LLM sees in the tool
schema) is:

```
Search the open internet (keyless) or fetch a specific web page.
Use it to research topics, standards, protocols, or systems that are
not in the internal knowledge base — e.g. 'research the top carbon
footprint standards (GHG Protocol, ISO 14064, PAS 2050)'. Returns
ranked results with titles, URLs and snippets you can cite.
```

Note: **the description never mentions weather or forecast.** The tool *can* answer weather
(see below), but the model has no schema signal that it does.

Internally, `execute()` branches on a regex detector:

```python
_WEATHER_PATTERN = re.compile(
    r"\b(?:weather|forecast|temperature|temp)\b|"
    r"how\s+(?:hot|cold|warm|cool)\s+is\s+it|"
    r"is\s+it\s+(?:raining|snowing|sunny|cloudy)",
    re.IGNORECASE,
)
```

If `_is_weather_query(query)` is true, it routes to `_weather()` → Open-Meteo keyless
geocoding + forecast (no API key), and returns a **tri-state** result
(`resolved`/`no_match`/`error`). Critically:

```python
if _is_weather_query(query):
    weather = await self._weather(client, query)
    if is_resolved(weather):
        return weather["data"]
    return weather        # no_match / error surfaced, NEVER falls through to search
```

Location extraction is a regex chain (`_extract_weather_location`) that strips weather
phrases/time words/prepositions to feed the Open-Meteo geocoder. The geocoder is
**exact-match** — typos and region names ("north coast egypt") return empty.

### 5.4 Tri-state resolution (single source of truth)

`core/resolution.py` — every deterministic boundary returns one of:

```python
resolved(data, confidence=1.0, source="")
no_match(reason, hint="", candidates=[])
error(cause, detail="")
```

with predicates `is_resolved/is_no_match/is_error/truthiness_guard`. The design intent
(per `uncertainty-provenance.md`): epistemic status is **never silently discarded**; a
`no_match` must escalate, never act.

---

## 6. Prompt architecture

The system prompt is **composed at runtime** from multiple sources, then **layered with
zone-specific directives**.

### 6.1 Base assembly — `build_chat_prompt()`

`llm/prompts.py`. Order of assembly:

1. **Runtime header** — instance name, current time, current user (name/email/roles), page.
2. **Playbook blocks** — `PlaybookAssembler` assembles versioned `PlaybookBlock`s (persona,
   scope_boundary, domain_rule, tool_heuristic, lesson, compliance, tone_voice), ordered by
   block type then priority. (This replaced a prior LLM-prompt-synthesis approach.)
3. **A/B candidate routing** — 20% of conversations (md5 hash) get a candidate `PromptVersion`.
4. **API catalog section** — terse `name (METHOD): description` list.
5. **Grounding directive** (below).
6. **Access inventory** — strict no-leak list of apps/work-areas/modules the user can reach.
7. **RENDERING_CAPABILITIES** — rich-markdown instructions (always appended).

### 6.2 The grounding directive (verbatim intent)

```text
## Live data grounding (non-negotiable)

This platform holds LIVE operational data that is NOT part of your training knowledge —
do not answer about it from general knowledge or textbook reference values. When the user
asks about any domain below (... "here", "in the system", "our", "my", "on the platform",
"what we have", "show me", "list"), call the matching endpoint via `call_host_api` and
answer from the returned data only:

- emission factors → `list_emission_factors`
- ...

ANSWER WITH DEPTH, NOT A DUMP. ...
```

### 6.3 The zone-aware directive layer (the crux)

In `runner.py`, **after** the base prompt is built, the runner appends a directive chosen by
the S1.5 zone:

```python
_is_platform_zone = (
    _intent_resolution is None                          # resolver didn't run → safe default
    or _intent_resolution.zone in ("platform", "off_limits")
)
if draft_tools and _is_platform_zone:
    system_prompt += "GROUNDING RULES — follow them exactly: ..."   # long; mentions
    #  "Use web_research when the task needs internet facts" once, in passing.

elif draft_tools and _intent_resolution is not None:
    _zone = _intent_resolution.zone
    if _zone == "real_time":
        system_prompt += (
            "This question requires live information. Use the web_research tool to fetch "
            "current data. Always attribute the source in your answer. ..."
        )
    elif _zone in ("concept", "general"):
        system_prompt += (
            "Answer this question from your knowledge. No platform tool call is needed. ..."
        )
```

**This is the architectural smoking gun.** The live-web mandate fires *only* when:

1. the resolver returned **non-None**, **and**
2. `zone == "real_time"`.

If either fails — the classifier mislabels weather as `concept`/`general` (very common when
the message has a greeting + a trailing sub-question like "is it suitable for beach
swimming?"), or the resolver returns `None` — the turn gets the **opposite** directive
("answer from your knowledge, no tool call"), and the model dutifully refuses to fetch data
it was told it doesn't need. See §11 (Weather bug).

### 6.4 RENDERING_CAPABILITIES

Always-appended block telling the model it can emit Markdown tables, fenced code, Mermaid
diagrams, KaTeX math, and charts — including strict Mermaid syntax rules. (This exists
because earlier the model would say "I can't draw diagrams".)

---

## 7. Memory model

Four memory surfaces, all Carbon-owned:

1. **Working memory** (`memory/working.py`) — a Redis-backed **single focus slot per
   conversation**:

   ```python
   @dataclass
   class WorkingFocus:
       entity: str
       entity_type: str
   ```

   `get_focus`/`set_focus(conversation_id, entity, entity_type)`. The focus is injected into
   the prompt as a fragment: `"Currently active: <entity> (type: <entity_type>)"`. This is a
   *slot*, not a structure — only one entity is "active" at a time.

2. **Knowledge graph** — entities/facts, searched via `search_knowledge`.
3. **Long-term memory** — `learn_fact`/`forget_fact` tools (user-confirmed).
4. **Episodic / preferences** — session preference store (`PreferenceClassifier`), injected
   as prompt constraints.

---

## 8. Model policy & routing

`llm/router.py` maps tasks → models:

```python
_TASK_MODEL_MAP = {
    "chat":       settings.LLM_NORMAL_MODEL or settings.LLM_MODEL,
    "deep":       settings.LLM_MODEL,
    "reason":     settings.LLM_REASON_MODEL or settings.LLM_ESCALATION_MODEL or settings.LLM_MODEL,
    "cognition":  settings.LLM_COGNITION_MODEL or settings.LLM_MODEL,
    "introspect": settings.LLM_INTROSPECT_MODEL or settings.LLM_NORMAL_MODEL or settings.LLM_MODEL,
    "eval":       settings.EVAL_MODEL or settings.LLM_MODEL,
    "embed":      settings.LLM_EMBEDDING_MODEL,
}
```

Settings defaults (`core/config.py`):

```python
LLM_MODEL = "anthropic/claude-haiku-4.5"          # deep mode / fallback
LLM_NORMAL_MODEL = "anthropic/claude-haiku-4.5"
LLM_COGNITION_MODEL = "anthropic/claude-haiku-4.5"
LLM_INTROSPECT_MODEL = ""                          # falls back
LLM_REASON_MODEL = ""                              # empty = fall back to LLM_MODEL
LLM_ESCALATION_MODEL = ""                          # empty = honest-uncertainty path
```

**Implication:** by default **every lane uses Claude Haiku 4.5**. The `reason` lane (the
"genuinely hard problem" escalation) is **empty** — so "deep" salience and `knowledge_gap`
escalations fall straight back to Haiku. There is no stronger model in the loop unless the
operator sets `LLM_REASON_MODEL`. Cost guard: `LLM_DAILY_BUDGET_USD = 5.0` per instance, with
a `PULSE_ALLOW_EXPENSIVE_MODELS` override gate.

---

## 9. Safety & guardrails

1. **GuardChain** (`ai/guards.py`) — runs *before* every AI call: ScopeGuard, AccessGuard,
   DataIsolationGuard, MutationGuard, RateLimiter.
2. **RULE_21** — mutating tools default to `requires_confirmation=True`; S5 stages a
   confirmation instead of writing.
3. **Critic (S4)** — rules-tier always runs (citation grounding, mutation confirmation).
   `knowledge_gap` detection is a **regex** over the draft text:

   ```python
   _KNOWLEDGE_GAP_RE = re.compile(
       r"I('m| am) (not sure|...)|I don't have (specific|...information|knowledge)|"
       r"I (cannot|can't) (provide|give|confirm|answer)|I need (more|...) (context|...)", ...)
   ```

   A matched knowledge-gap escalates to the `reason` lane (which, per §8, is Haiku by
   default) or returns an "honest uncertainty" response.
4. **Fail-visible contract** — LLM unavailable → deterministic fallback, never a fabricated
   answer, status `pulse_unavailable` (not 500).

---

## 10. Observability

- **`TurnLedger`** — one aggregate per turn, with a row written per stage
  (`s1_salience`, `intent`, `retrieval`, `draft`, `critic`, `execution`, `final`) including
  latency + tokens + verdict.
- **`llm_call_logs`** — every LLM call logged with token counts + estimated cost.
- **Trajectory** — written fire-and-forget for ReAct/fan-out turns.
- **Known gap:** the `IntentResolver` log line does **not** log `zone`:

  ```python
  logger.info("IntentResolver: action=%s delivery=%s intent=%r top=%s conf=%.2f (conv=%s)",
      resolution.action, resolution.delivery, resolution.intent,
      resolution.candidates[0].name if resolution.candidates else None,
      resolution.confidence, conversation_id[:8])
  ```

  So the single most important routing decision (zone) was **unobservable** in logs — which
  is exactly why the weather bug (next) was hard to diagnose.

---

## 11. Known failure modes (with evidence)

### 11.1 The weather bug (the trigger for this audit)

**User query:** `"hi, what is the weather in north cost egypt toay, is it suitable for beach swiming ?"`

**Observed result:** a generic refusal — *"I can't directly fetch weather data … check
AccuWeather/Weather.com/Windy"* — with **zero** `web_research` tool call. This is a *distinct*
failure from an earlier one (where `web_research` was called but the geocoder got a garbage
query like `weather El Alamein Egypt current` and returned `no_match`).

**Root cause (proven by code trace, not by logs alone):** the chain that must hold is:

```
resolver zone == "real_time"  →  real_time directive  →  draft emits web_research call
    →  S5 executes  →  _is_weather_query routes to _weather()
```

Any break in the first three links silently produces the refusal. The two most likely breaks:

1. **Zone misclassification.** A greeting ("hi") + a trailing advisory sub-question ("is it
   suitable for beach swimming?") biases the classifier toward `concept`/`general` (or the
   resolver returns `None`). The runner then injects *"Answer from your knowledge. No
   platform tool call is needed."* — the model dutifully answers "I can't fetch weather."
2. **Weather-less tool description.** Even if the `real_time` directive fires, the
   `web_research` schema `description` never mentions weather/forecast, so the model has no
   schema signal that this tool answers weather and defaults to refusal.

Both root causes are **architectural**: the decision to invoke a live tool is delegated to an
LLM classifier whose output is (a) not validated against any authoritative signal, (b) not
observable, and (c) not matched by the tool schema.

**Fix applied 2026-09-05 (deterministic routing, not a keyword patch):** in `runner.py`,
immediately before S5, if the authoritative plugin detector `_is_weather_query(...)` is true
and the draft did **not** already emit a `web_research` call, the runner forces a synthetic
`web_research` tool call (clearing the refusal prose) and marks the turn tool-backed. A new
`_normalize_weather_question()` LLM-helper resolves the *full* question (greeting + typo +
region + trailing sub-question) into a geocoder-ready `City, Country`. This bypasses the
fragile zone classifier for weather specifically — but the general pattern (LLM-zone gating
tool access) remains.

### 11.2 Documented cross-cutting bugs (from repo memory)

- **False-denial**: an earlier prompt told the model "Never say 'I have memory' / 'I don't
  have memory'" — which *forced* hedges like "if memory is enabled in the future…". Fixed by
  positive framing.
- **Grounding over-correction**: "real data" was over-corrected into raw `SELECT *` dumps;
  fixed by a "ANSWER, DON'T DUMP" synthesis rule.
- **Anaphora follow-ups** resolve to the right endpoint but still revert to textbook lecture
  instead of re-querying live data (S3 injection directive not honored on follow-ups).
- **Mutation/read loop**: "create a DQ rule" was matched to `list_dq_rules` at low confidence
  → endless clarify/disambiguate loop; fixed by a mutation-request regex gate that skips the
  resolver.
- **`web_research` planner query corruption**: an earlier planner passed
  `"weather El Alamein Egypt current"` into the geocoder → `no_match`.

---

## 12. The architectural critique

This section is the honest assessment the auditor is asked to verify or refute.

### What the current design does well

- **Fail-visible everywhere.** Tri-state results, deterministic fallbacks, no fabricated
  answers. This is genuinely good and rare.
- **Clean separation.** Stateless engine, Carbon-owned memory, pluggable LLM, domain terms
  isolated to `instance.yaml`. The "LLM is just the voice" principle is sound.
- **Observable.** Ledger + call logs give a per-stage audit trail.

### Why it does not feel like intelligence

The following are *structural* consequences of the code, not stylistic complaints:

1. **The LLM is a classifier, not a reasoner.** The most consequential decision — *which
   behavior to activate* (S1.5 zone) — is an LLM multiple-choice answer, then the rest of the
   pipeline is deterministic. The system's "intelligence" is proportional to how well a
   small model guesses a category; the actual work is pre-scripted.

2. **The routing signal is unvalidated and unobservable.** Zone is guessed by the LLM,
   never checked against an authoritative signal (the plugin already knows `_is_weather_query`),
   and was not even logged. A category error silently flips the prompt to the *opposite*
   directive ("no tool needed").

3. **No closed loop.** The system never observes "the user asked for weather, I refused, the
   user was unhappy" and adjusts. `learn_fact` is user-initiated; there is no automatic
   failure → diagnosis → self-correction cycle. The A/B prompt routing exists but is manual.

4. **Model ceiling is flat.** Every lane defaults to Claude Haiku 4.5; the "reason" escalation
   lane is empty. Hard problems get the same model as greetings, just with more stacked calls.

5. **"Agent" is an aspiration, not a loop.** The default path is one draft + one execute.
   ReAct/fan-out are opt-in gates triggered by a planner, not a persistent agent with goals,
   a world model, or cross-turn autonomy.

6. **Every capability is a special-case patch.** Weather needed: a regex detector, a
   location normalizer, a pending-intent slot, a rewrite, a forced tool call, and a
   deterministic gate — *just to reliably call one keyless API*. Each new "real" capability
   (stocks, news, calendar, email) would repeat this pattern. The framework does not
   generalize the *act of using the web to answer a live question*; it hand-rolls it per tool.

### The central question restated

> Pulse routes **deterministically around** an LLM, using the LLM for (a) classification and
> (b) prose. Is that "intelligence", or is it a **rules engine with an LLM UI**? And if the
> goal is a genuine *coworker* — something that remembers context, forms goals, plans across
> turns, and gets better — what is the minimal architecture that actually delivers that,
> without losing the fail-visible/auditable properties Carbon has worked hard to get right?

---

## 13. Open questions for the auditor

Please address these specifically (with reasoning grounded in the code above):

1. **Routing:** Should tool access be gated by an LLM *category* at all, or should the
   deterministic detectors (`_is_weather_query`) + tool schemas be the source of truth, with
   the LLM only deciding *how* to use a tool it's already been allowed?
2. **Zone model:** Is a 4-zone classifier the right abstraction, or is it a leaky
   taxonomy that forces every new capability into a hand-carved slot? What replaces it?
3. **The "coworker" gap:** What is the smallest architectural change that turns the current
   per-turn pipeline into something with (a) durable cross-turn state, (b) goal formation and
   planning, (c) self-correction from observed failures — while keeping the ledger/guardrails?
4. **Model policy:** Is stacking N Haiku calls behind deterministic orchestration the right
   cost/latency/quality tradeoff vs. a single strong model with a real tool loop? Where
   should the strong model sit?
5. **Memory:** Is a single-slot "working focus" adequate for anything resembling a coworker?
   What memory structure is actually needed for cross-turn goal tracking?
6. **Generalization:** How should the system represent "answer a live-web question" once,
   instead of hand-rolling weather + stocks + news + … as separate plugins?

---

## 14. Appendix — key file map

| Concern | File |
|---|---|
| Turn orchestrator (six witnesses + all zone/gate logic) | `backend/ai/engine/cognition/turn/runner.py` |
| S1 salience (regex) | `backend/ai/engine/cognition/turn/salience.py` |
| S1.5 intent + four-zone classifier | `backend/ai/engine/cognition/turn/intent.py` |
| S3 draft | `backend/ai/engine/cognition/turn/draft.py` |
| S4 critic | `backend/ai/engine/cognition/turn/critic.py` |
| S5 execute | `backend/ai/engine/cognition/turn/execute.py` |
| Stage dataclasses | `backend/ai/engine/cognition/turn/witnesses.py` |
| ReAct + fan-out | `backend/ai/engine/cognition/plan/loop.py` |
| System prompt assembly | `backend/ai/engine/llm/prompts.py` |
| Playbook block assembly | `backend/ai/engine/llm/playbook.py` |
| Task→model routing | `backend/ai/engine/llm/router.py` |
| Settings (models, budget) | `backend/ai/engine/core/config.py` |
| Tri-state resolution | `backend/ai/engine/core/resolution.py` |
| Tool plugin registry | `backend/ai/engine/agent/plugins.py` |
| Static tools | `backend/ai/engine/agent/tools.py` |
| Working memory (focus slot) | `backend/ai/engine/memory/working.py` |
| web_research (search/fetch/weather) | `backend/ai/plugins/web_research.py` |
| Platform architecture (top-level) | `ARCHITECTURE.md` |
