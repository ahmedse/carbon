# DESIGN — Carbon AI Workspace v4 (Next Generation)

**Status:** Authoritative design spec — supersedes v3 (`DESIGN_AI_WORKSPACE_NEXTGEN.md`)
**Author:** Master Architect
**Date:** 2026-08-16
**Audience:** Frontend Worker, Backend Worker, QA
**Binding contracts:** `.ai-toolkit/shared/ai-contract.md` (v2.0.0), `.ai-toolkit/shared/design-patterns.md`

---

## Why v4?

v3 is a solid architecture spec. What it lacks:

| Gap | Impact |
|-----|--------|
| No **Execute Mode** — AI proposes actions but there is no trust gate | Users cannot confidently let AI touch real data |
| No **Investigate Mode** — "one click, AI runs the full pipeline and returns a brief" | The most wanted workflow is unspecced |
| No **NL → DQ Rule with live test** — the killer feature | Missing entirely |
| No **Smart Context** — AI knows what page you have open, your recent actions, changed data | Responses feel generic, not data-grounded |
| UI/UX is ASCII-only; no component-level design for structured cards | Workers guess at layout |
| Phases 6–10 unspecced | Can't plan beyond context engineering |

v4 keeps everything v3 got right (architecture, streaming protocol, 4-tier memory, 4-fixed-tabs IA) and fills these gaps completely.

---

## 0. TL;DR — What Carbon AI Workspace v4 Is

**A governed, data-grounded AI workspace built into the right panel of the Carbon shell.**

It is not a chatbot. It is a **reasoning partner** that:
1. Knows exactly what data you are looking at (Smart Context).
2. Can investigate on your behalf (Investigate Mode — autonomous pipeline).
3. Can propose and apply real changes only when you deliberately unlock Execute Mode.
4. Learns from your decisions and gets better over time.

The single best analogy: **Cursor for data governance** — context-aware, action-capable,
human-in-the-loop by default.

---

## 1. Benchmark Analysis — What the Best Do

### 1.1 GitHub Copilot / VS Code Chat

| Strength | Flaw |
|----------|------|
| `#file`, `@workspace` context mentions — explicit, auditable | Context is code-only; no live data grounding |
| Queue / Steer / Stop send modes — user never loses agency | No structured output cards; everything is markdown |
| Spaces: persist context sets across sessions | No action execution — suggestions only |
| Streaming with per-token usage chip | Cost/token numbers are obscured |

**Carbon borrows:** mention system, queue/steer/stop, session persistence.
**Carbon improves:** data grounding (KG + live schema), action execution, structured cards.

### 1.2 Cursor (Composer)

| Strength | Flaw |
|----------|------|
| Multi-file diff trail — shows exactly what changed | Code-only; no concept of data rows/rules |
| Checkpoint / undo for every AI action | Expensive; not always appropriate for data |
| Agent mode: AI plans multi-step, shows plan before executing | Plan visibility only in Pro tier |
| Context window telemetry visible | |

**Carbon borrows:** diff-trail (Investigate plan view), checkpoint/undo for DQ rule acceptance, agent-mode plan visibility.
**Carbon improves:** data-domain actions (create rule, fix anomaly, draft report).

### 1.3 Claude (claude.ai Projects)

| Strength | Flaw |
|----------|------|
| Projects: persistent knowledge bases per project | No live data connectivity |
| Artifacts: code/documents rendered inline, editable | No action execution |
| Memory across sessions | Memory is user-facing text; no structured entity graph |
| System prompt per project | |

**Carbon borrows:** Artifacts tab, project-level knowledge (maps to org/module scope), inline document editing for report draft.
**Carbon improves:** Carbon's KG + DjangoStore is a real semantic memory (not free text), CBAC scope enforcement.

### 1.4 Palantir AIP (Workflow Builder)

| Strength | Flaw |
|----------|------|
| AI reviews alerts → proposes resolutions → human approves | Extremely complex to configure |
| Full audit log of every AI-proposed action | Enterprise-only pricing |
| Human-in-the-loop gate is a first-class design pattern | Workflow builder is a separate tool |
| Tool documentation as first-class spec | |

**Carbon borrows:** human-in-the-loop Execute Mode toggle, action audit log (via `GovernanceEvent`), "AI proposes, human approves" as the default pattern.
**Carbon improves:** Carbon is embedded in the workspace — no context switch to a separate tool.

### 1.5 The universal principles from research

From Anthropic's "Building effective agents" (Dec 2024):
1. **Maintain simplicity** — avoid complexity until it demonstrably earns its cost.
2. **Prioritize transparency** — explicitly show planning steps.
3. **Carefully craft the agent-computer interface** — tool documentation is as important as the prompt.

From Nielsen Norman Group on generative AI UX:
1. **Show the AI's uncertainty** — confidence indicators, not false certainty.
2. **Enable correction** — always show an edit path.
3. **Grounding is trust** — cite the source data.
4. **Progressive disclosure** — don't overwhelm; summary first, detail on demand.

Carbon's design follows all seven.

---

## 2. Core Design Contracts (workers must not violate)

```
C1. The user is never blocked.
    Input always present; Generate mode switches the send button to queue/steer/stop.
    NEVER disable the input bar completely.

C2. AI proposes; user decides.
    No data mutation without an explicit user confirmation in the thread.
    Execute Mode toggles the ability to send mutations; it does not auto-execute.

C3. Every answer cites its ground.
    Every assistant message carries provenance: model, scope, context tiers used.
    Every data claim in a structured card links to the source entity.

C4. Smart Context is explicit, not inferred.
    WorkspaceContext is serialized deterministically by the page the user is on.
    AI never reads cookies/URL silently — it receives only what the page hands it.

C5. Structured outputs get structured cards.
    No JSON dumps as primary UI. Every conversation_type has a registered card.

C6. The thread rail is navigation, not state.
    Threads live in the DB. Closing/refreshing the browser must restore the thread list.

C7. Streams are real; faking is forbidden.
    Token deltas only for genuinely streamable outputs (chat, report.draft).
    Progress events for structured outputs. Never fake a token stream for JSON.

C8. The four fixed tabs are a hard ceiling.
    Chat | Investigate | Artifacts | Audit.
    Workers must never add a fifth without an ADR.
```

---

## 3. Updated Information Architecture

### 3.1 Shell layout (right panel)

```
╔═══════════════════════════════════════════════════════════╗
║  MAIN WORKSPACE (left 65–75%)  │  AI WORKSPACE (right 25–35%) ║
╠═══════════════════════════════════════════════════════════╣
║  [Any Carbon page]             │  ┌─────────────────────────┐ ║
║  e.g. Electricity table,       │  │  HEADER (40px)          │ ║
║       DQ Rules list,           │  │  🤖 AI  [New▾][⚙][✕]   │ ║
║       Emissions dashboard      │  ├─────────────────────────┤ ║
║                                │  │  THREAD RAIL (collapsible│ ║
║                                │  │  left sub-panel, 180px) │ ║
║                                │  │                         │ ║
║                                │  │  MAIN PANEL             │ ║
║                                │  │  ┌───────────────────┐  │ ║
║                                │  │  │ FIXED TABS (36px) │  │ ║
║                                │  │  │ Chat│Invest│Art│Aud│  │ ║
║                                │  │  ├───────────────────┤  │ ║
║                                │  │  │ CONTENT AREA      │  │ ║
║                                │  │  │                   │  │ ║
║                                │  │  │                   │  │ ║
║                                │  │  ├───────────────────┤  │ ║
║                                │  │  │ INPUT BAR (88px)  │  │ ║
║                                │  │  └───────────────────┘  │ ║
╚═══════════════════════════════════════════════════════════╝

Resize handle between main workspace and AI workspace (drag, min 280px, max 600px).
Ctrl+\ toggles AI workspace open/closed. Size persisted in localStorage.
```

### 3.2 Thread rail (sub-panel within AI workspace)

```
┌─────────────────────────────────────┐
│ [🔍 Search threads…]  [+]           │
├─────────────────────────────────────┤
│ 📌 PINNED (2)                       │
│   ● DQ: Electricity analysis  •2d   │
│   ● Oct Report draft         •1w    │
├─────────────────────────────────────┤
│ 💬 TODAY (3)                        │
│   ◉ Why did Scope 2 spike?  ⊙ now   │  ← active (blue left border)
│   ○ Fleet anomaly check     ◌ 2h    │
│   ○ NL: Summarize Abu Qeer  ◌ 3h    │
├─────────────────────────────────────┤
│ 🗂 EARLIER (12)  ▶ (collapsed)       │
├─────────────────────────────────────┤
│ 🗄 ARCHIVED  ▶ (collapsed)           │
└─────────────────────────────────────┘

Icons:
  ◉ = working/streaming (animated pulse)
  ● = pinned
  ○ = completed/idle
  ◌ = pending

Right-click row → Pin / Rename / Archive / Delete
Rail collapses to icon-only strip (24px) when AI pane is narrow (<320px).
```

### 3.3 Fixed mode tabs (C8 — never add a fifth)

| # | Tab | Icon | What it shows | When empty |
|---|-----|------|---------------|------------|
| 1 | **Chat** | `ChatIcon` | Active conversation thread | "Start a conversation or transfer a task." |
| 2 | **Investigate** | `SearchIcon` | Running + past investigation plans | "Click 'Investigate' on any table or entity." |
| 3 | **Artifacts** | `FolderIcon` | Promoted outputs (reports, rule sets, query results) | "Promoted content appears here." |
| 4 | **Audit** | `HistoryIcon` | Read-only GovernanceEvent log for AI actions | "No AI actions recorded yet." |

---

## 4. Smart Context System

### 4.1 What "Smart Context" means

The AI workspace always knows:
- **Current page**: what workspace, what entity, what tab.
- **Recent navigation**: last 5 pages visited this session.
- **Recent mutations**: schema changes, DQ rule creates, row edits from this session.
- **Active mentions**: entities explicitly tagged with `#` in the input.

None of this is inferred by screen-scraping. It is serialized by the page the user is on via `WorkspaceContext`.

### 4.2 WorkspaceContext v2

```python
@dataclass
class WorkspaceContext:
    workspace: str           # "dq" | "catalog" | "emissions" | "dataschema" | "admin"
    current_view: str        # page/tab label, e.g. "table_detail", "dq_rules_tab"
    entity_type: str | None  # "table" | "rule" | "field" | "module" | "conversation"
    entity_id: str | None    # PK
    entity_name: str | None  # human-readable label

    # v2 additions
    breadcrumb: list[dict]   # [{type, id, name}, …] — navigation ancestry
    recent_pages: list[dict] # last 5: [{workspace, view, entity_type, entity_id, entity_name, visited_at}]
    recent_mutations: list[dict]  # last 5 mutations this session: [{action, entity_type, entity_id, entity_name, at}]
    form_state: dict | None  # SANITIZED partial form (never passwords/tokens)
```

**Security note:** `recent_mutations` is client-side (session storage only). It never sends IDs the user is not already authorized to read (CBAC still applies server-side). It is informational context, not an authorization bypass.

### 4.3 Context badge in the input bar

When Smart Context detects a focused entity, a chip appears above the input:

```
┌─────────────────────────────────────────────────────────────────┐
│  📊 Table: monthly_electricity (Abu Qeer)  [×]                  │
│  Recent: edited 3 rows · ran DQ check · added 1 field           │
├─────────────────────────────────────────────────────────────────┤
│  Ask about this table…                               [Send ▾]   │
└─────────────────────────────────────────────────────────────────┘
```

Clicking `[×]` clears the smart context for this message (falls back to manual `#mention`).

### 4.4 Context-aware starter prompts

When Smart Context detects the current entity, show 3 context-specific starter chips (instead of generic empty state) in the Chat tab:

| Current page | Starter chips shown |
|---|---|
| Table detail (any) | "Why is quality {score}%?" · "Suggest DQ rules" · "Investigate anomalies" |
| DQ rule detail | "Explain this rule in plain language" · "Find similar rules" · "Test against live data" |
| Emissions dashboard | "Why did Scope 2 spike this month?" · "Draft GHG summary report" · "Find anomalous months" |
| Module/data product | "Summarize data quality" · "What changed this week?" · "Investigate completeness" |
| Any page (fallback) | "What can I ask here?" · "Run a data quality check" · "Show me trends" |

---

## 5. Input Bar — Complete Component Design

### 5.1 Layout (88px height)

```
┌──────────────────────────────────────────────────────────────────────┐
│  [📊 monthly_electricity ×]  [⚡ Execute Mode OFF]                   │  ← context + execute toggle row (24px)
├──────────────────────────────────────────────────────────────────────┤
│  #table electricity…                                                  │  ← textarea (40px, grows to 120px)
│                                                                       │
├──────────────────────────────────────────────────────────────────────┤
│  [@ Mention]  [🎤]  [📎]                       [queue ▾][Send →]    │  ← toolbar row (24px)
└──────────────────────────────────────────────────────────────────────┘

States:
- IDLE: Send → enabled
- COMPOSING: Send → enabled; char count badge if >200
- STREAMING: send button becomes [queue ▾] with Send dropdown
- STOPPING: spinner on send; input greyed placeholder "Stopping…"
- QUEUED: badge "1 queued" next to send; input shows queued content preview
```

### 5.2 Send mode dropdown (streaming state only)

```
┌────────────────────────┐
│ ✓ Queue (send on done) │  ← default; buffers the next message
│   Steer (interrupt)    │  ← sends stop + sends immediately
│   Stop                 │  ← stops generation, no new message
└────────────────────────┘
```

### 5.3 Execute Mode toggle

A prominent toggle in the input bar header row. OFF by default.

```
OFF state:  [⚡ Execute Mode  ○────]   grey text, locked icon
ON state:   [⚡ Execute Mode  ────●]   amber text + amber border on entire input bar

Tooltip when hovering OFF:
  "Execute Mode off — AI can suggest actions but cannot apply them.
   Turn on to allow AI to create rules, fix data, and run queries."

When turned ON: confirmation toast: "Execute Mode enabled — AI may now propose data changes."
When turned OFF: "Execute Mode disabled."
```

**Behavioral effect:**
- OFF (default): structured cards show "Preview" only. Accept/Reject buttons render as "Apply manually" links.
- ON: structured cards show real "Apply" buttons. Clicking Apply triggers the mutation + `GovernanceEvent`.

The toggle state persists in `sessionStorage` only (not `localStorage`) — resets to OFF on new tab/session. This is intentional: users must consciously re-enable each session.

### 5.4 Mention system (`#` trigger)

```
Step 1: user types `#`
  → Popper opens below cursor:
  ┌─────────────────────┐
  │ table  · DataTable  │
  │ rule   · DQ Rule    │
  │ field  · DataField  │
  │ module · Module     │
  └─────────────────────┘

Step 2: user types `#table ele`
  → Popper switches to entity list (debounced fetch 300ms):
  ┌──────────────────────────────────────────────┐
  │ 📊 monthly_electricity   · Abu Qeer · 12 rows │
  │ 📊 electricity_grid_2024 · Refs              │
  └──────────────────────────────────────────────┘

Step 3: user selects
  → `#table ele` → replaced with `@monthly_electricity` (display token)
  → `mentions` array: [{ kind:"table", id:"7", name:"monthly_electricity" }]
  → context chip appears above input (§4.3)

Cancel: Escape, or type a space after `#` with no kind match.
```

---

## 6. Thread View — Complete Component Design

### 6.1 Message bubble anatomy

```
┌──────────────────────────────────────────────────────────────────────┐
│  🤖 AI  ·  2 minutes ago                                [⋮]          │
│                                                                       │
│  [Message content — markdown, code blocks, tables]                   │
│                                                                       │
│  [Follow-up chips — clickable]                                        │
│  "What caused this?" · "Show me the raw data" · "Fix automatically"  │
│                                                                       │
│  gpt-4o · 1,248 tok · $0.003 · 1.84s    ↩ Why this answer?          │
│  👍  👎  ✏️ Correct                                                   │
└──────────────────────────────────────────────────────────────────────┘

⋮ menu items:
  Copy text · Regenerate · Edit (user messages) · Promote to Artifact · Report issue

↩ Why tooltip (popover, not tooltip):
  ┌──────────────────────────────────────────┐
  │  Model:       gpt-4o                     │
  │  Turn:        b54f7ce2                   │
  │  App:         platform                   │
  │  Type:        chat                       │
  │  Scope:       AASTMT / Abu Qeer          │
  │  Guards:      Scope✅ Access✅ Rate✅    │
  │  Context:     History 420 tok            │
  │               KG Retrieval 340 tok       │
  │               Memory 180 tok             │
  └──────────────────────────────────────────┘
```

### 6.2 Streaming state

```
┌──────────────────────────────────────────────────────────────────────┐
│  🤖 AI  ·  just now                                                   │
│                                                                       │
│  The monthly electricity usage for Building 401 shows a 34% spike    │
│  in August, which is consistent with higher AC demand during summer   │
│  peak■                                                                │  ← blinking cursor
│                                                                       │
│  [●●● thinking]  T3 · KG Retrieval · 340 tok injected               │  ← live status line
└──────────────────────────────────────────────────────────────────────┘
```

### 6.3 Interrupted state

```
┌──────────────────────────────────────────────────────────────────────┐
│  🤖 AI  ·  1 minute ago                           [Interrupted 🛑]   │
│                                                                       │
│  The monthly electricity usage for Building 401 shows…               │
│  [partial content, greyed out after this line]                        │
│                                                                       │
│  [Continue →]   [Discard]                                            │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.4 Working indicator (structured operations)

```
┌──────────────────────────────────────────────────────────────────────┐
│  🤖 AI  ·  just now                                                   │
│                                                                       │
│  ████░░░░░░░░  Analyzing table schema  (2/4)                          │  ← real stage from server
│                                                                       │
│  ✅ Loaded profile data                                               │
│  ⏳ Running 8 DQ rules…                                               │
│  ○  Scoring results                                                   │
│  ○  Generating report                                                 │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 7. Structured Output Cards

### 7.1 DQ Validate Card

```
╔══════════════════════════════════════════════════════════════════════╗
║  DQ Check: monthly_electricity              ⬇ Export   🔄 Re-run    ║
╠══════════════════════════════════════════════════════════════════════╣
║  ✅ 6 Passed   ❌ 2 Failed   ⚠️ 1 Warning    Score: 78%             ║
╠══════════════════════════════════════════════════════════════════════╣
║  ❌ not_null · month field             18 violations  [See rows ↗]  ║
║  ❌ range · total_kwh ≥ 0              3 violations   [See rows ↗]  ║
║  ⚠️ unique · month                    1 duplicate    [See rows ↗]  ║
║  ✅ not_null · total_kwh              0 violations               ║
║  ✅ range · total_kwh ≤ 500000        0 violations               ║
║  ✅ allowed_values · building_code    0 violations               ║
╠══════════════════════════════════════════════════════════════════════╣
║  [View all 64 rows]    [Fix violations →]    [Accept findings ✓]    ║
╚══════════════════════════════════════════════════════════════════════╝

"See rows ↗" opens a filtered DataGrid dialog showing violating rows.
"Fix violations →" opens NL Query with pre-filled: "Show me the 18 rows where month is null"
"Accept findings ✓" = record_feedback(accepted) + creates GovernanceEvent
```

### 7.2 DQ Suggest Card

```
╔══════════════════════════════════════════════════════════════════════╗
║  DQ Suggestions: monthly_electricity     Accept All (4)   Reject All ║
╠══════════════════════════════════════════════════════════════════════╣
║  1 of 5  ████████████████░░░░  89% confidence                       ║
║                                                                       ║
║  Rule: "Monthly electricity must not deviate >50% from              ║
║         12-month rolling average"                                    ║
║                                                                       ║
║  Type: threshold · Severity: warning                                  ║
║  Rationale: 3 months in 2024 show unusual spikes                     ║
║                                                                       ║
║  [🔬 Test live]  [✏️ Edit rule text]   [✓ Accept]   [✗ Reject]      ║
╠══════════════════════════════════════════════════════════════════════╣
║  2 of 5  ████████████░░░░░░░░  62% confidence                       ║
║  Rule: "All rows must have a valid month date (no future dates)"     ║
║  [🔬 Test live]  [✏️ Edit rule text]   [✓ Accept]   [✗ Reject]      ║
╠══════════════════════════════════════════════════════════════════════╣
║  3 of 5 · 4 of 5 · 5 of 5  [▼ expand 3 more]                       ║
╠══════════════════════════════════════════════════════════════════════╣
║  Progress: 1 accepted · 1 rejected · 3 pending                      ║
╚══════════════════════════════════════════════════════════════════════╝

"Test live" → triggers the NL→Rule Test flow (§8, the killer feature).
"Accept" → POST /dq/rules/ (create rule) + record_feedback(accepted).
           Requires Execute Mode ON (§5.3).
           If Execute Mode OFF → shows "Enable Execute Mode to apply this rule."
"Edit rule text" → inline contenteditable on the rule text → re-test before accept.
```

### 7.3 NL Query Card

```
╔══════════════════════════════════════════════════════════════════════╗
║  Query Result                             ⬇ CSV    📋 Copy SQL      ║
╠══════════════════════════════════════════════════════════════════════╣
║  SELECT month, total_kwh                                             ║
║  FROM monthly_electricity                                            ║
║  WHERE total_kwh > 200000                                            ║
║  ORDER BY month DESC                                                 ║
║  LIMIT 100;                                                          ║
╠══════════════════════════════════════════════════════════════════════╣
║  12 rows  ·  showing 12/12                                           ║
╠═══════════════╦══════════════════╦══════════════════════════════════╣
║  month        ║  total_kwh       ║                                  ║
╠═══════════════╬══════════════════╬══════════════════════════════════╣
║  2024-08      ║  284,320         ║                                  ║
║  2024-07      ║  271,100         ║                                  ║
║  2024-01      ║  241,890         ║                                  ║
╠══════════════════════════════════════════════════════════════════════╣
║  Ask a follow-up: "Why are summer months higher?"  →               ║
╚══════════════════════════════════════════════════════════════════════╝

"Copy SQL" → clipboard.
"CSV" → downloads as monthly_electricity_query_{timestamp}.csv.
Follow-up pre-fills input bar.
SQL execution error → shows red error state with raw SQL and "Edit and retry" button.
```

### 7.4 Anomaly Card

```
╔══════════════════════════════════════════════════════════════════════╗
║  Anomalies: monthly_electricity          Scanned 64 rows / 3 fields  ║
╠══════════════════════════════════════════════════════════════════════╣
║  🔴 HIGH  total_kwh · Aug 2024           z-score: 3.4               ║
║           284,320 kWh vs avg 158,200 kWh (+79%)                     ║
║           [Investigate ↗]  [Accept Finding]  [Dismiss]              ║
╠══════════════════════════════════════════════════════════════════════╣
║  🟡 MEDIUM  total_kwh · Jul 2024         z-score: 2.1               ║
║           271,100 kWh vs avg 158,200 kWh (+71%)                     ║
║           [Investigate ↗]  [Accept Finding]  [Dismiss]              ║
╠══════════════════════════════════════════════════════════════════════╣
║  🟢 LOW  month · 2023-02                  Duplicate date detected    ║
║           [Investigate ↗]  [Accept Finding]  [Dismiss]              ║
╠══════════════════════════════════════════════════════════════════════╣
║  [Accept all 3]    [Dismiss all]                                     ║
╚══════════════════════════════════════════════════════════════════════╝

"Investigate ↗" → opens NL Query pre-filled: "Show all rows for Aug 2024 and compare to prior year"
"Accept Finding" → creates DQResult (requires dq:manage_rules + Execute Mode ON)
"Dismiss" → record_feedback(rejected)
```

### 7.5 Report Draft Card

```
╔══════════════════════════════════════════════════════════════════════╗
║  GHG Report Draft — FY2024                ✏️ Edit   ⬇ Markdown      ║
╠══════════════════════════════════════════════════════════════════════╣
║  ## AASTMT Smart Village Campus                                      ║
║  ## GHG Emissions Summary FY2024                                     ║
║                                                                       ║
║  ### Scope 2 — Purchased Electricity                                  ║
║  Total: **2,837.8 tCO₂e** (93.5% of total)                          ║
║  *Building 401: 1,425t · Building 2401: 1,413t*                      ║
║                                                                       ║
║  [+] See full report  (12 sections, 820 words)                       ║
╠══════════════════════════════════════════════════════════════════════╣
║  Live data as of: 2026-08-16  ·  Based on: 237 calculations          ║
╠══════════════════════════════════════════════════════════════════════╣
║  [Edit inline]  [Expand full]  [Save as Artifact]  [Export .md]     ║
╚══════════════════════════════════════════════════════════════════════╝

"Edit inline" → contenteditable overlay on card text. Changes tracked.
"Save as Artifact" → POST /ai/workspace/artifacts/ (type: report)
"Export .md" → downloads report.md
```

---

## 8. The Killer Feature — NL → DQ Rule with Live Test

This is the most important differentiator: **write a rule in plain language, AI converts it to a structured rule, tests it against real data, shows you the results, and only saves when you say so.**

### 8.1 Entry points

1. From `DQSuggestionCard` → "Test live" button on any suggestion.
2. From `AIInputBar` → "Suggest and test a rule for @monthly_electricity".
3. From DQ Rules Tab → "Ask AI to write a rule" button (context-transfers to AI workspace).
4. Direct chat: "Create a rule: electricity must not deviate more than 50% from the 3-month rolling average".

### 8.2 The workflow (7-step, fully specified)

```
Step 1 — User writes rule in natural language
  Input: "Electricity for Building 401 in summer months (Jun–Aug)
          must be at least 80% of the prior year's same month"
  → createConversation(type:'nl_rule_test', task_payload:{table_id:7})
  → sendMessageStream(content, workspace_context:{entity:'table', entity_id:7})

Step 2 — AI parses rule (streaming progress frame)
  data: {"type":"progress","stage":"parsing","message":"Parsing rule into structured form…"}

Step 3 — AI emits parsed rule (partial frame)
  data: {"type":"progress","stage":"parsed","partial":{
    "rule_text": "…",
    "rule_type": "threshold",
    "params": {
      "comparison_field": "total_kwh",
      "filter": {"month__in": [6,7,8]},
      "comparison": "prior_year_same_month",
      "operator": ">=",
      "threshold_pct": 80
    },
    "severity": "warning",
    "confidence": 0.84
  }}

  UI renders a live "Rule Preview" card:
  ┌────────────────────────────────────────────────────────┐
  │  ✏️ Rule Preview (edit before testing)                  │
  │  Type: threshold · Severity: warning                   │
  │  "Monthly electricity (Jun–Aug) ≥ 80% of prior year"  │
  │  ↳ fields: total_kwh · filter: Jun/Jul/Aug             │
  │  [Edit parameters ▾]                                   │
  └────────────────────────────────────────────────────────┘

Step 4 — AI runs rule against live data (progress frames)
  data: {"type":"progress","stage":"testing","message":"Running against 64 rows…"}
  data: {"type":"progress","stage":"testing","message":"Evaluated 48 applicable rows…"}

Step 5 — AI returns test results (done frame)
  data: {"type":"done","conversation":{…},"usage":{…},"result":{
    "rule_preview": { … },
    "test_summary": {
      "total_rows": 64,
      "applicable_rows": 18,
      "passed": 15,
      "failed": 3,
      "pass_rate": 0.833
    },
    "violations": [
      {"month":"2022-06","total_kwh":41200,"expected_min":47800,"deficit_pct":13.8},
      {"month":"2021-07","total_kwh":38900,"expected_min":44200,"deficit_pct":12.0},
      {"month":"2021-08","total_kwh":36100,"expected_min":43600,"deficit_pct":17.2}
    ],
    "recommendation": "The rule would have caught 3 real anomalies (2021 post-COVID dip). Threshold of 80% is appropriate; consider adding a 'prior year must exist' guard."
  }}

Step 6 — Full NL Rule Test Card renders:
╔══════════════════════════════════════════════════════════════════════╗
║  Rule Test: "Electricity 80% of prior year (summer)"                ║
╠══════════════════════════════════════════════════════════════════════╣
║  Test Summary                           83.3% pass rate             ║
║  ████████████████░░░░  15/18 applicable rows passed                ║
║  3 violations found in: Jun'22, Jul'21, Aug'21                      ║
╠══════════════════════════════════════════════════════════════════════╣
║  ╔═══════════╦═══════════╦════════════╦═══════════╗                 ║
║  ║ Month     ║ Actual kWh║ Min needed ║ Gap       ║                 ║
║  ╠═══════════╬═══════════╬════════════╬═══════════╣                 ║
║  ║ 2022-06   ║ 41,200    ║ 47,800     ║ -13.8%    ║                 ║
║  ║ 2021-07   ║ 38,900    ║ 44,200     ║ -12.0%    ║                 ║
║  ║ 2021-08   ║ 36,100    ║ 43,600     ║ -17.2%    ║                 ║
║  ╚═══════════╩═══════════╩════════════╩═══════════╝                 ║
║                                                                       ║
║  💡 "3 violations match 2021 COVID-period anomalies. Rule is sound." ║
╠══════════════════════════════════════════════════════════════════════╣
║  [✏️ Adjust threshold]  [🔄 Re-test]  [✓ Save Rule]  [✗ Discard]   ║
╚══════════════════════════════════════════════════════════════════════╝

"Adjust threshold" → inline slider + re-test (no new message needed; local re-score)
"Re-test" → re-runs the test with current params
"Save Rule" → POST /dq/rules/ (requires Execute Mode ON)

Step 7 — Save (Execute Mode ON):
  → DQ rule created, id returned
  → Toast: "Rule created · View in DQ Workspace ↗"
  → "Saved ✓" chip on the card (irreversible confirm)
  → GovernanceEvent logged: "AI created DQ rule {id} for table {name}"
```

### 8.3 Backend implementation notes

This maps to a new `conversation_type: "nl_rule_test"`. The backend handler in `engine_runtime._run_nl_rule_test`:
1. Parses NL using LLM → structured rule params JSON.
2. Constructs a `DQRule`-compatible dict (no DB write yet).
3. Runs it against `DataRow` objects in a read-only transaction.
4. Returns `test_summary + violations + recommendation`.

The actual `POST /dq/rules/` call happens from the frontend after user confirmation — the backend handler is purely read-only until then.

---

## 9. Investigate Mode

### 9.1 What it is

One-click "let the AI run the full pipeline on this entity and return a brief". The AI:
1. Profiles the table (column stats, completeness, uniqueness).
2. Runs all existing DQ rules.
3. Detects anomalies in time series.
4. Queries the KG for related entities and known issues.
5. Synthesizes a plain-language brief with key findings and recommended actions.

The user does not write a message. They click one button.

### 9.2 Entry points

- "Investigate" button on any DataTable detail page header.
- Right-click on a module in the thread rail → "Investigate this module".
- Chat starter chip: "Investigate anomalies".
- Any anomaly card → "Investigate ↗".

### 9.3 Investigate tab UI

```
╔══════════════════════════════════════════════════════════════════════╗
║  Investigations                                        [New ▾]       ║
╠══════════════════════════════════════════════════════════════════════╣
║  ⏳ Running: monthly_electricity · Aug 2026           3/5 steps      ║
║  ████████████░░░░░░░░  Detecting anomalies…                          ║
║                                                                       ║
║  ✅ Completed: fleet_vehicles · Aug 2026              Aug 15         ║
║  ✅ Completed: monthly_electricity · Jul 2026         Aug 2          ║
╠══════════════════════════════════════════════════════════════════════╣
║  [View all 6 investigations]                                         ║
╚══════════════════════════════════════════════════════════════════════╝
```

### 9.4 Investigation report (completed)

```
╔══════════════════════════════════════════════════════════════════════╗
║  Investigation: monthly_electricity                   Aug 15, 2026  ║
║  5 steps · 2 min 14s · gpt-4o · 4,820 tok                          ║
╠══════════════════════════════════════════════════════════════════════╣
║  FINDINGS (3 issues)                                                  ║
║                                                                       ║
║  🔴 HIGH: Unusual spike in Aug 2024 (+79% vs avg)                   ║
║     → Recommend: Investigate source data for meter error             ║
║     [Chat about this ↗]                                              ║
║                                                                       ║
║  🟡 MEDIUM: 18 rows where month is null (6.7% missing)               ║
║     → Recommend: Add not_null rule for month field                   ║
║     [Create rule ↗]  [Chat about this ↗]                            ║
║                                                                       ║
║  🟢 LOW: Building codes use old format (4-digit, not 5)              ║
║     → Recommend: Update reference set                                ║
║     [Chat about this ↗]                                              ║
╠══════════════════════════════════════════════════════════════════════╣
║  PLAN (executed steps)                                                ║
║  ✅ 1. Profile table (64 rows, 5 fields)                             ║
║  ✅ 2. Run 6 DQ rules (6 passed, 0 failed)                           ║
║  ✅ 3. Detect anomalies in time series (2 found)                     ║
║  ✅ 4. Query knowledge graph (2 related entities retrieved)           ║
║  ✅ 5. Synthesize findings                                            ║
╠══════════════════════════════════════════════════════════════════════╣
║  [Save as Artifact]    [Chat → continue investigation]    [Re-run]  ║
╚══════════════════════════════════════════════════════════════════════╝
```

### 9.5 Backend: `conversation_type = "investigate"`

The `investigate` task chains 5 sub-tasks:
1. `profile_table` (existing `dq.services`)
2. `run_dq` (existing `dq.services`)
3. `anomaly.detect` (existing `engine_runtime`)
4. KG entity fetch (T3 retrieval from `context_assembler`)
5. LLM synthesis call → structured `findings` + `recommendations` JSON

All 5 are dispatched as a single `task_type="investigate"` handler. Progress frames emitted between steps (§5.1 stream protocol). On `done`, the `result` JSON has `{findings, plan_steps, metadata}`.

---

## 10. Audit Tab — AI Actions Log

```
╔══════════════════════════════════════════════════════════════════════╗
║  AI Audit Log                    [Filter: All ▾]  [Export CSV]       ║
╠══════════════════════════════════════════════════════════════════════╣
║  2026-08-16 11:42  ahmed  Created DQ rule "electricity-summer-pct"  ║
║                           via NL rule test · monthly_electricity     ║
║                           [View rule ↗]  [View conversation ↗]      ║
╠══════════════════════════════════════════════════════════════════════╣
║  2026-08-16 10:15  ahmed  Accepted DQ suggestion (confidence 89%)   ║
║                           Rule: anomaly threshold on total_kwh       ║
║                           [View rule ↗]                              ║
╠══════════════════════════════════════════════════════════════════════╣
║  2026-08-15 14:30  ahmed  Dismissed anomaly finding (Aug 2024)       ║
║                           [View investigation ↗]                     ║
╠══════════════════════════════════════════════════════════════════════╣
║  [Load more]                                                          ║
╚══════════════════════════════════════════════════════════════════════╝

Source: GovernanceEvent model (already exists; filter entity_type="ai_*")
CBAC: requires platform:view_audit OR ai:view_console.
Read-only. Export = GET /carbon-api/catalog/governance-events/?entity_type__startswith=ai_
```

---

## 11. Context Panel (right sub-panel in Chat tab)

A collapsible panel within the Chat tab. Opens from a `[≡ Context]` button in the conversation header.

```
┌───────────────────────────────────┐
│  Context  ·  Turn 7                │  (per-turn, updates on each send)
├───────────────────────────────────┤
│  SCOPE                            │
│  Org: AASTMT                      │
│  Module: Abu Qeer Electricity     │
│  App: platform                    │
├───────────────────────────────────┤
│  MENTIONS (2)                     │
│  📊 monthly_electricity  [×]      │
│  📋 kwh-not-null-rule     [×]      │
│  [+ Add]                          │
├───────────────────────────────────┤
│  CONTEXT BUDGET (Turn 7)          │
│  History      ████░░  420 tok     │
│  KG Retrieval ███░░░  340 tok     │
│  Memory       ██░░░░  180 tok     │
│  Summary      █░░░░░   90 tok     │
│  Available:         1,970 tok     │
├───────────────────────────────────┤
│  KNOWLEDGE GRAPH                  │
│  monthly_electricity (ENTITY)     │
│    ↳ total_kwh, month, building   │
│  emission_factors (ENTITY)        │
│    ↳ factor_value, unit, year     │
│  "None retrieved" if empty        │
├───────────────────────────────────┤
│  [Summarize thread]  [Clear all]  │
└───────────────────────────────────┘
```

---

## 12. UX Color Palette for AI Workspace

All colors from `carbonTheme.js` — no raw hex.

| Element | Token | Meaning |
|---------|-------|---------|
| Active thread border | `primary.main` | Selected/focused |
| Streaming indicator | `primary.light` | In progress |
| Execute Mode toggle ON | `warning.main` | Caution — mutations possible |
| HIGH severity | `error.main` | Critical finding |
| MEDIUM severity | `warning.main` | Warning finding |
| LOW severity | `success.main` | Informational |
| Pass rate badge | `success.main` | Good |
| Fail/violation | `error.main` | Bad |
| Context chip | `info.light` | Informational |
| Interrupted chip | `warning.dark` | Stopped |
| Audit action | `text.secondary` | Neutral |

---

## 13. Phased Roadmap — v4

Phases 0–5 from v3 are DONE or IN PROGRESS. This is the v4 extension.

---

### Phase 6 (Current) — Context Engineering and KG Surfacing

**Status:** Phases 6A (T3 KG retrieval) and 6B (KG frontend surface + budget telemetry fix) DONE.
Phase 6C (per-turn provenance freeze) DONE.

**Gate:** `pytest ai -q` → 325 passed. Frontend vitest 396 passed.

---

### Phase 7 — Smart Context (Session-Aware Context Injection)

**Role:** Frontend Worker (thin) + Backend Worker (thin)
**Dependencies:** Phase 6C complete

#### 7-A Frontend: WorkspaceContext v2 serializer

**Files:**
```
carbon-frontend/src/shell/useWorkspaceContext.js   (new hook)
carbon-frontend/src/shell/AIInputBar.jsx           (consume context hook)
carbon-frontend/src/shell/AIConversationView.jsx   (pass context to send)
```

**Tasks:**

1. `useWorkspaceContext()` hook — reads current `location`, `AuthContext`, `sessionStorage`:
   - `workspace`: derived from `studioFromPath(location.pathname)`.
   - `current_view`: derived from pathname segments (e.g. `/catalog/tables/7` → `table_detail`).
   - `entity_type`/`entity_id`/`entity_name`: extracted from URL params.
   - `recent_pages`: accumulated in `sessionStorage` (last 5, cleared on logout).
   - `recent_mutations`: accumulated in `sessionStorage` from MutationContext (a new provider, Phase 7-A2).
   - Returns a `WorkspaceContext` object; never returns partial/undefined fields.

2. `MutationContextProvider` — thin provider that any page can call `recordMutation(action, entity)` on. Accumulates in `sessionStorage`.

3. Context badge in `AIInputBar` — shows current entity chip when `entity_id` is set. `[×]` clears it for that message only (not globally).

4. Context-aware starter chips in `AIEmptyState` — when `entity_type` is known, render the 3 starters from §4.4.

#### 7-B Backend: WorkspaceContext v2 parsing

**Files:**
```
backend/ai/protocol.py         (extend WorkspaceContext dataclass)
backend/ai/context_assembler.py (use recent_pages + recent_mutations in T1)
```

**Tasks:**
1. Add `breadcrumb`, `recent_pages`, `recent_mutations` fields to `WorkspaceContext`.
2. `context_assembler._build_workspace_block` injects `recent_pages` as "User was recently on: …" and `recent_mutations` as "User recently: …" — capped to 200 tokens max.
3. Test: verify `recent_mutations` is sanitized (no raw cell values, only entity references).

**Acceptance criteria:**
- Context chip appears on any page where `entity_id` is in the URL.
- Sending a message on the table detail page includes "User is viewing: monthly_electricity" in T1.
- Session context never leaks across users (sessionStorage is per-tab).

**Gate:**
```bash
cd backend && ../.venv/bin/python -m pytest ai/tests/test_context_assembler.py -q
cd carbon-frontend && npm test -- --run && npm run lint && npm run build
```

---

### Phase 8 — Execute Mode + NL → DQ Rule (Killer Feature)

**Role:** Backend Worker then Frontend Worker
**Dependencies:** Phase 7 complete

#### 8-A Backend: `nl_rule_test` conversation type

**Files:**
```
backend/ai/models/workspace.py    (add "nl_rule_test" to CONVERSATION_TYPES)
backend/ai/engine_runtime.py      (add _run_nl_rule_test handler)
backend/ai/intelligence.py        (add nl_rule_test route in send_message_stream)
backend/ai/workspace_api.py       (no change — type is handled by send_message_stream)
backend/ai/tests/test_nl_rule.py  (new)
```

**Tasks:**

1. `_run_nl_rule_test(payload, scope)`:
   - Input: `{table_id, user_message, workspace_context}`.
   - Step 1: LLM call to parse NL → structured rule params (`rule_type`, `params`, `severity`, `confidence`). Prompt: "Given this table schema: {schema} and this natural language rule: {nl}, produce a DQRule-compatible JSON dict."
   - Step 2: Dry-run the rule against `DataRow.objects.filter(data_table_id=table_id)` (read-only; reuse `DQRuleExecutor` with `dry_run=True` flag).
   - Step 3: Return `{rule_preview, test_summary:{total_rows, applicable_rows, passed, failed}, violations:[{…}], recommendation}`.
   - Progress frames: "Parsing rule…", "Testing against N rows…", "Scoring results…".
   - Execute gate: if `scope.is_read_only` → return result without creating anything; frontend creates the rule.

2. `DQRuleExecutor.dry_run` flag — returns violations without writing `DQResult` records.

3. Tests: parse produces valid rule_type; 0-row table returns pass; all-fail table returns 0 pass_rate; LLM unavailable → `pulse_unavailable` fail-visible.

#### 8-B Frontend: Execute Mode + NL Rule Test Card

**Files:**
```
carbon-frontend/src/shell/AIInputBar.jsx               (execute toggle)
carbon-frontend/src/shell/cards/NLRuleTestCard.jsx     (new)
carbon-frontend/src/shell/cards/DQSuggestionCard.jsx   (add "Test live" → NLRuleTestCard)
carbon-frontend/src/shell/AIConversationView.jsx       (render NLRuleTestCard)
carbon-frontend/src/api/aiWorkspace.js                 (createNLRuleTest)
carbon-frontend/src/__tests__/NLRuleTestCard.test.jsx  (new)
```

**Tasks:**

1. **Execute Mode toggle** (§5.3): amber border + sessionStorage state + toast on enable.
2. **`NLRuleTestCard`** (§8.2): renders `rule_preview`, test summary bar, violations grid, threshold slider.
   - "Save Rule" button: disabled if Execute Mode OFF (with tooltip "Enable Execute Mode to save").
   - If Execute Mode ON: `POST /dq/rules/` → success → immutable "Saved ✓" state on card.
3. **"Test live" on `DQSuggestionCard`**: creates a new `nl_rule_test` conversation with the suggestion text pre-filled.
4. **Structured card routing**: `AIConversationView` renders `NLRuleTestCard` when `conversation_type === "nl_rule_test"`.

**Browser checklist:**
- [ ] Type "electricity must not deviate >50% from 3-month average" → NLRuleTestCard renders.
- [ ] Threshold slider → pass rate updates instantly (client-side re-score).
- [ ] Execute Mode OFF → "Save Rule" shows tooltip, does not save.
- [ ] Execute Mode ON → "Save Rule" → POST /dq/rules/ → "Saved ✓".
- [ ] DQSuggestionCard "Test live" → opens NLRuleTestCard in new thread.

**Gate:**
```bash
cd backend && ../.venv/bin/python -m pytest ai -q
cd carbon-frontend && npm test -- --run && npm run lint && npm run build
```

---

### Phase 9 — Investigate Mode

**Role:** Backend Worker then Frontend Worker
**Dependencies:** Phase 8 complete

#### 9-A Backend: `investigate` conversation type

**Files:**
```
backend/ai/models/workspace.py    (add "investigate" to CONVERSATION_TYPES)
backend/ai/engine_runtime.py      (_run_investigate: chains profile + dq + anomaly + kg + synthesize)
backend/ai/intelligence.py        (route investigate in send_message_stream)
backend/ai/tests/test_investigate.py (new)
```

**Tasks:**

1. `_run_investigate(payload, scope)`:
   - Step 1: `profile_table(table_id)` → `TableProfile`.
   - Step 2: `run_dq(table_id)` → `DQResult[]`.
   - Step 3: `dispatch_task("anomaly.detect", {table_id, profile})` → anomalies.
   - Step 4: T3 KG fetch for this table's entity (reuse `context_assembler._retrieve_knowledge_graph`).
   - Step 5: LLM synthesis → `{findings, plan_steps, metadata}`.
   - Progress frames per step (§5.1).
   - `findings` array: `[{severity, title, detail, recommended_action, entity_ref}]`.

2. Tests: empty table returns 0 findings; DQ violations appear as findings; anomaly appears as HIGH finding; LLM outage → `pulse_unavailable`.

#### 9-B Frontend: Investigate tab + InvestigationCard

**Files:**
```
carbon-frontend/src/shell/AIWorkspace.jsx                (Investigate tab)
carbon-frontend/src/shell/InvestigateTab.jsx             (new: list of investigations)
carbon-frontend/src/shell/cards/InvestigationCard.jsx   (new: findings + plan view)
carbon-frontend/src/shell/AIConversationView.jsx        (render InvestigationCard)
```

**Tasks:**

1. **Investigate tab** (§9.3) — list running + completed investigations sorted by `created_at` desc.
2. **`InvestigationCard`** (§9.4) — findings accordion + plan steps.
   - Finding actions: "Chat about this ↗" (opens Chat tab with context), "Create rule ↗" (opens NL Rule Test), "Dismiss".
   - "Re-run" → new investigation conversation.
3. **"Investigate" button** on `DataTable` detail page → `createConversation(type:"investigate", task_payload:{table_id})` → switches to AI workspace Investigate tab.

**Gate:**
```bash
cd backend && ../.venv/bin/python -m pytest ai -q
cd carbon-frontend && npm test -- --run && npm run lint && npm run build
```

---

### Phase 10 — Proactive Suggestions Rail + Resume Catch-up Polish

**Role:** Frontend Worker
**Dependencies:** Phase 9 complete (Phase 5 backend already done)

**Tasks:**

1. **AISuggestionRail** — accept/dismiss actions (currently display-only). Accept → `POST /ai/workspace/conversations/{id}/suggestions/{id}/accept/` (new backend endpoint, thin DRF action that sets `KgProactiveInsight.status="acknowledged"`).
2. **Resume catch-up banner** polish — currently shows raw `summary_lines[]`. Replace with a card: icon + time-since-last-visit + bullet list + "Catch me up" button → starts a Chat conversation summarizing the changes.
3. **Notification badge** on the AI workspace toggle button — shows count of unread suggestions + unread catch-up banners. Clears on open.

**Gate:**
```bash
cd carbon-frontend && npm test -- --run && npm run lint && npm run build
```

---

### Phase 11 — Shared Threads + Multi-user Collaboration (read-only first)

**Role:** Backend Worker
**Dependencies:** Phase 10 complete

**Tasks:**
1. `PATCH /conversations/{id}/ {visibility:"shared"}` → conversation readable by all users in same org unit scope (read-only).
2. Shared conversation list in thread rail under a "Shared with me" section.
3. Non-owner sees read-only thread — no input bar, no "Save Rule" button.
4. `DELETE` on shared conversation requires `ai:manage_console` capability.

---

## 14. Complete File Change Map

```
Phase 7 (Smart Context):
  NEW:  carbon-frontend/src/shell/useWorkspaceContext.js
  NEW:  carbon-frontend/src/shell/MutationContextProvider.jsx
  MOD:  carbon-frontend/src/shell/AIInputBar.jsx
  MOD:  carbon-frontend/src/shell/AIConversationView.jsx
  MOD:  carbon-frontend/src/shell/AIEmptyState.jsx
  MOD:  backend/ai/protocol.py
  MOD:  backend/ai/context_assembler.py
  NEW:  backend/ai/tests/test_workspace_context_v2.py

Phase 8 (Execute Mode + NL→DQ Rule):
  MOD:  backend/ai/models/workspace.py
  MOD:  backend/ai/engine_runtime.py
  MOD:  backend/ai/intelligence.py
  MOD:  backend/dq/executor.py           (dry_run flag)
  NEW:  backend/ai/tests/test_nl_rule.py
  MOD:  carbon-frontend/src/shell/AIInputBar.jsx
  NEW:  carbon-frontend/src/shell/cards/NLRuleTestCard.jsx
  MOD:  carbon-frontend/src/shell/cards/DQSuggestionCard.jsx
  MOD:  carbon-frontend/src/shell/AIConversationView.jsx
  MOD:  carbon-frontend/src/api/aiWorkspace.js
  NEW:  carbon-frontend/src/__tests__/NLRuleTestCard.test.jsx

Phase 9 (Investigate Mode):
  MOD:  backend/ai/models/workspace.py
  MOD:  backend/ai/engine_runtime.py
  MOD:  backend/ai/intelligence.py
  NEW:  backend/ai/tests/test_investigate.py
  MOD:  carbon-frontend/src/shell/AIWorkspace.jsx
  NEW:  carbon-frontend/src/shell/InvestigateTab.jsx
  NEW:  carbon-frontend/src/shell/cards/InvestigationCard.jsx
  MOD:  carbon-frontend/src/shell/AIConversationView.jsx

Phase 10 (Proactive Polish):
  MOD:  carbon-frontend/src/shell/AISuggestionRail.jsx
  MOD:  carbon-frontend/src/shell/AIConversationView.jsx (catch-up card)
  MOD:  carbon-frontend/src/shell/ActivityBar.jsx        (notification badge)
  MOD:  backend/ai/workspace_api.py                      (suggestion accept endpoint)

Phase 11 (Shared Threads):
  MOD:  backend/ai/workspace_api.py
  MOD:  backend/ai/intelligence.py
  MOD:  carbon-frontend/src/shell/AIConversationTabs.jsx
  MOD:  carbon-frontend/src/shell/AIConversationView.jsx
```

---

## 15. Explicit Non-Goals (never build without new ADR)

| Rejected feature | Reason |
|-----------------|--------|
| Real-time co-editing (multi-user typing in same thread) | Complexity >> value at current user scale |
| Autonomous execution without Execute Mode gate | C2 is non-negotiable — data mutations require human in the loop |
| pgvector migration | JSON vector fields sufficient; horizontal scale not yet required |
| AI-generated screenshots / computer-use | Contract §11 prohibits it; WorkspaceContext is the approved approach |
| A 5th fixed tab | C8 is explicit; thread rail handles all navigation |
| LLM model selector exposed to end-users | Model routing belongs to LLM routing config, not user preferences |
| PDF generation server-side | Browser print is sufficient; server PDF adds infrastructure |
| Streaming JSON diffs token-by-token | Faking is forbidden (C7); progress frames are the right pattern |

---

## 16. Risk Register

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Execute Mode ignored/forgotten — users leave it ON | HIGH | Reset to OFF on new session (sessionStorage only) + amber visual warning |
| NL rule parser produces wrong rule type | HIGH | Dry-run test shows violations before save; user must review test results |
| Investigate chains multiple LLM calls → cost spike | MEDIUM | Progress frames show cost per step; `LLM_INVESTIGATE_MAX_TOKENS` budget cap in settings |
| Smart Context leaks recent mutations across sessions | MEDIUM | SessionStorage is per-tab; backend validates scope on every call |
| NLRuleTestCard threshold slider recomputes on every drag | LOW | Debounce 200ms; client-side re-score (no server call until "Save Rule") |
| Investigation caches stale profile | LOW | Re-run always fetches fresh; "Last run" timestamp visible |
| Audit log grows unbounded | LOW | `GovernanceEvent` already has retention policy; filter by `entity_type__startswith="ai_"` |

---

## 17. Verification Gate (every phase must pass)

```bash
# Backend
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python manage.py check
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q
/home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run

# Frontend
cd /home/ahmed/aast/carbon/carbon-frontend
npm test -- --run
npm run lint
npm run build
```

Workers must not submit a phase without all 6 commands passing. The browser checklist per phase must also be verified by QA.

---

## 18. ADR Record for v4 Decisions

| Decision | Rationale | Alternatives rejected |
|----------|-----------|----------------------|
| SessionStorage (not localStorage) for Execute Mode | Each session must consciously re-enable; prevents accidental mutations after leaving the desk | localStorage: too persistent; no toggle: too permissive |
| Client-side threshold slider for NL Rule Test | Instant feedback without LLM cost; local re-score is exact (not an estimate) | Server-side re-score: 500ms+ latency per drag event |
| 4-step Investigate chain dispatched as one conversation | Simpler state management; progress frames show chain status; one conversation = one audit trail | Separate conversations per step: fragmented history |
| `nl_rule_test` as a conversation_type (not a new endpoint) | Reuses entire conversation persistence/streaming/feedback stack; consistent frontend rendering | Separate endpoint: would need parallel session management |
| WorkspaceContext in sessionStorage (not URL params) | No URL pollution; no security risks from sharing URL; can carry richer objects | URL params: leaks entity context in browser history |

---

## 19. Domain App AI Contract — Platform Extension Model

> **See ADR-0010** in `.ai-toolkit/decisions/0010-domain-app-ai-contract.md` for the
> full decision rationale, trade-offs, and rejected alternatives.

Carbon is a **general platform** that hosts domain apps. The AI workspace is a
platform capability. Every domain app participates in the AI workspace by implementing
a **manifest** — without touching any platform code.

### 19.1 The contract in one picture

```
                     ┌─────────────────────────────────────────┐
                     │  PLATFORM (ai/)                          │
                     │                                           │
                     │  AIWorkspace shell (fixed, never changes) │
                     │  4 fixed tabs: Chat│Invest│Art│Audit      │
                     │  Streaming, cards, Execute Mode, KG       │
                     │                                           │
                     │  ┌──────────────────────────────────────┐ │
                     │  │  Manifest API                        │ │
                     │  │  GET /ai/pulse/apps/                 │ │
                     │  │  GET /ai/pulse/apps/{id}/            │ │
                     │  └──────────────────────────────────────┘ │
                     └──────────────────────────────────────────┘
                            ▲                    ▲
                     reads manifest         reads manifest
                            │                    │
          ┌─────────────────┴──┐         ┌───────┴────────────────┐
          │  DOMAIN APP 1       │         │  DOMAIN APP 2 (future)  │
          │  emissions/         │         │  academic_kpi/          │
          │  ai/domain/         │         │  ai/domain/             │
          │    emissions.py     │         │    academic_kpi.py      │
          │  (EmissionsDomainAI)│         │  (AcademicKPIDomainAI)  │
          └─────────────────────┘         └─────────────────────────┘
```

### 19.2 What a domain app declares (the manifest)

Every `DomainAIOperations` subclass is **simultaneously** the domain's AI behavior
implementation AND its manifest for the platform.

| Field | Type | Controls |
|-------|------|---------|
| `supported_task_types` | `list[str]` | Which task types appear in "New ▾" dropdown |
| `entry_points` | `list[dict]` | Buttons rendered on domain pages |
| `starter_prompts` | `dict[entity → list]` | Context-aware chips in empty state |
| `system_prompt_extension` | `str` | Domain vocabulary in T0 (never sent to frontend) |
| `build_workspace_context(user, entity_type, entity_id)` | method | Live T1 enrichment |
| `validate_task_payload(task_type, payload)` | method | Fast pre-dispatch validation |

### 19.3 How to add a new domain app's AI capability

```
1. Create  backend/{app}/ai_manifest.py
           → subclass DomainAIOperations
           → fill manifest fields
           → register_domain(app_identifier, cls) at module bottom

2. Wire    backend/{app}/apps.py AppConfig.ready():
           → import {app}.ai_manifest  # noqa: F401

3. Done.   Zero changes to ai/, workspace_api.py, or any frontend file.
           The manifest API exposes the new app automatically.
           The frontend reads entry_points + starter_prompts at runtime.
```

### 19.4 What the frontend does with the manifest

`AIWorkspace.jsx` calls `GET /carbon-api/ai/pulse/apps/{app_identifier}/` once on load
(or when `app_identifier` changes). The response drives:

1. **Empty state starter chips** — rendered from `starter_prompts[entity_type]`.
2. **"New ▾" dropdown** — lists `supported_task_types` with human labels.
3. **Entry point buttons** on domain pages — each page checks `entry_points` filtered
   by `on_entity === entity_type` and renders the matching buttons.
4. **Payload validation** — frontend calls `validate_task_payload` indirectly via the
   backend on `send_message`; clear error is surfaced in the thread.

The frontend shell itself **never imports domain-specific code**. It only reads the
manifest JSON.

### 19.5 The emissions manifest (current state)

```python
class EmissionsDomainAI(DomainAIOperations):
    app_identifier   = "emissions"
    app_display_name = "Carbon Footprint"

    supported_task_types = [
        "chat", "dq_validate", "dq_suggest", "nl_query",
        "anomaly", "investigate", "nl_rule_test", "report_draft",
    ]

    entry_points = [
        {"label":"Validate DQ",    "task_type":"dq_validate",  "on_entity":"table",  "icon":"FactCheck"},
        {"label":"Suggest Rules",  "task_type":"dq_suggest",   "on_entity":"table",  "icon":"AutoFixHigh"},
        {"label":"Investigate",    "task_type":"investigate",   "on_entity":"table",  "icon":"ManageSearch"},
        {"label":"Draft Report",   "task_type":"report_draft",  "on_entity":"module", "icon":"Description"},
        {"label":"Ask about this", "task_type":"chat",          "on_entity":"*",      "icon":"Chat"},
    ]

    # starter_prompts: table, module, default (see domain/emissions.py)
    # build_workspace_context: resolves table/module → row_count, module_scope
    # validate_task_payload: table_id required for DQ/investigate tasks
```

### 19.6 The future Academic KPI manifest (illustration)

```python
class AcademicKPIDomainAI(DomainAIOperations):
    app_identifier   = "academic_kpi"
    app_display_name = "Academic KPI & Portfolio"

    supported_task_types = ["chat", "nl_query", "investigate", "report_draft"]

    entry_points = [
        {"label":"Analyze KPIs",      "task_type":"investigate",  "on_entity":"dept",    "icon":"Analytics"},
        {"label":"Draft eval report", "task_type":"report_draft", "on_entity":"faculty", "icon":"Description"},
        {"label":"Ask about this",    "task_type":"chat",         "on_entity":"*",       "icon":"Chat"},
    ]

    # Zero platform code changes required.
    # The AI workspace shell renders these automatically.
```

### 19.7 Constraints that protect the platform

- Domain apps cannot add a new **base card type**. They use the platform's card
  repertoire. A new card requires a new platform feature (ADR required).
- `system_prompt_extension` is static string, not a callable. Dynamic T0 content
  belongs in `build_workspace_context` (T1).
- `validate_task_payload` must return fast (< 5ms) — it blocks every send. No DB
  queries allowed; use cached lookups only.
- `build_workspace_context` must be resilient (`try/except` wrapping all DB access) —
  a context enrichment failure must never fail the turn.

### 19.8 Contract API response shape

```json
// GET /carbon-api/ai/pulse/apps/emissions/
{
  "app_identifier": "emissions",
  "display_name": "Carbon Footprint",
  "supported_task_types": ["chat", "dq_validate", "dq_suggest", "nl_query",
                            "anomaly", "investigate", "nl_rule_test", "report_draft"],
  "entry_points": [
    {"label": "Validate DQ",    "task_type": "dq_validate",  "on_entity": "table",  "icon": "FactCheck"},
    {"label": "Suggest Rules",  "task_type": "dq_suggest",   "on_entity": "table",  "icon": "AutoFixHigh"},
    {"label": "Investigate",    "task_type": "investigate",   "on_entity": "table",  "icon": "ManageSearch"},
    {"label": "Draft Report",   "task_type": "report_draft",  "on_entity": "module", "icon": "Description"},
    {"label": "Ask about this", "task_type": "chat",          "on_entity": "*",      "icon": "Chat"}
  ],
  "starter_prompts": {
    "table":   [{"label": "Why is quality score low?", "prompt": "…", "task_type": "chat"}, …],
    "module":  [{"label": "Summarize data quality",    "prompt": "…", "task_type": "chat"}, …],
    "default": [{"label": "What can I ask here?",      "prompt": "…", "task_type": "chat"}]
  },
  "system_prompt_extension": true
}
```

`system_prompt_extension` is a boolean — the actual text is never returned to the
frontend (it is only injected server-side into the T0 prompt tier).
