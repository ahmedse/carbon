# TASK-QA-AI-PULSE-SIMULATION
# Enterprise AI Pulse QA + Simulation Master Plan (Categorized, Executable)

- **Role:** QA/Validator (evidence only — NO product-code fixes)
- **Recommended model:** DeepSeek V4-Flash (per `project.config.md` WORKER_MODEL_POLICY)
- **Domain:** Backend (Django/DRF) + Frontend (React/MUI) — validation only
- **Task ID:** QA-AI-PULSE-SIMULATION
- **Parent:** AI Workspace track (Sprints 13–17) + AI Pulse console (Phase 22–23) + Rich Export (Phases A+B)
- **Goal:** Prove — with Playwright + curl + DOM evidence — that EVERY implemented AI
  feature actually works end-to-end as a regular user would use it: responses, formats,
  figures/graphs, tables, links, fly-to, thinking, memory, learning, tooling, RAG — all of it.
- **Execution model:** This is the MASTER PLAN. It contains ~340 scenario stubs organized
  into 13 categories + 4 layers. Each scenario is executed, observed, and logged into
  `docs/TASK-RESULT-QA-AI-PULSE-SIMULATION.md` with ✅/❌/⚠ + evidence.

---

## 0. Preconditions (do these BEFORE any scenario)

1. **Servers up** (verified with `./manage.sh status`):
   - Backend: `http://127.0.0.1:8009` (Django, API prefix `/carbon-api/`)
   - Frontend: `http://127.0.0.1:5179` (Vite dev, base `/`)
   - PostgreSQL + Redis running.
2. **Migrations applied** (prior 500 root cause):
   ```bash
   cd /home/ahmed/aast/carbon/backend
   /home/ahmed/aast/carbon/.venv/bin/python manage.py migrate --plan
   /home/ahmed/aast/carbon/.venv/bin/python manage.py migrate
   ```
3. **Restart backend** so uncommitted working-tree fixes are live:
   ```bash
   cd /home/ahmed/aast/carbon && ./manage.sh restart backend
   ```
4. **Credentials** (from `e2e/fixtures/users.ts` PERSONAS + local known accounts):
   - admin: `ahmed` / `AdminPa_132` (superuser, full AI access) — live browser persona
   - scoped: `alamien_dataowner` / `data123` (branch=alamien, non-admin)
   - viewer: `alamien_viewer` / `viewer123` (read-only, negative case)
5. **Baseline gates** (from summary): FRONTEND `npx eslint` clean + `npx vitest run`
   (586 baseline passed / 9 pre-existing failures: AIArtifacts 2, AIMessageBubble.feedback 3,
   AISharedThreads 4 — DO NOT FIX). BACKEND `cd backend && /home/ahmed/aast/carbon/.venv/bin/python
   -m pytest ai appregistry --ignore=ai/tests/test_store_execute.py -q` (510 passed;
   test_store_execute.py is broken WIP, ALWAYS ignore).
6. **Evidence kit:** browser (Playwright via `run_playwright_code`), curl with real JWT,
   screenshots per failed scenario, DOM assertions (testids, computed styles).

---

## 1. Feature Inventory (the FULL surface under test)

### 1.1 Admin Pulse console — 20 routes (5 groups)
| Group | Panels (routes under `/admin/ai/…`) |
|-------|--------------------------------------|
| Overview | `/admin/ai` (PulseOverviewPage — provider health + task envelope), `/admin/ai/workspace` (AIWorkspacePage — embeds shell), `/admin/ai/conversations` (AIConversationsPage — browse all) |
| Intelligence Core | `/admin/ai/knowledge` (KnowledgeBasePanel), `/admin/ai/memory` (MemoryPanel), `/admin/ai/graph` (KnowledgeGraphPanel — force-directed + Graph/Table toggle), `/admin/ai/budget-usage` (BudgetUsagePanel), `/admin/ai/engine-settings` (EngineSettingsPanel) |
| Agents & Tooling | `/admin/ai/agents` (AgentsPanel), `/admin/ai/mcp` (McpServersPanel), `/admin/ai/tools` (ToolsPanel), `/admin/ai/skills` (SkillsPanel), `/admin/ai/archetypes` (PulseArchetypesPanel), `/admin/ai/prompts` (PromptsPanel) |
| Feedback & Learning | `/admin/ai/feedback` (FeedbackPanel), `/admin/ai/learning` (LearningJobsPanel), `/admin/ai/learning-flywheel` (LearningFlywheelPanel) |
| Observability | `/admin/ai/monitoring` (MonitoringPanel), `/admin/ai/audit` (AuditPanel), `/admin/ai/logs` (AILogsPanel) |

All gated by `AdminRoute requiredCapability={AI_VIEW_CONSOLE}`.

### 1.2 Pulse read APIs (`src/api/aiPulse.js`, base `ai/pulse/`)
- `inventory/` — 13+ panels with model-backed row counts
- `data/<key>/` — merged redacted rows per panel
- `archetypes/` — vendored engine archetype bundles (filesystem)
- `usage/` — budget, spend, tokens, calls, per-model, 7-day
- `settings/` — engine config + capability inventory (secrets redacted)
- `graph/` — normalized KG nodes+edges+stats (truncated flag)
- `learning-status/` — flywheel status (durable backend, pending/processed, outcomes, facts, feedback ledger)
- `learning-status/run/` — POST on-demand sweep (the ONLY write action in the read-only console)
- `apps/` — domain app manifests (entry_points, starter_prompts)

### 1.3 Workspace API (`src/api/aiWorkspace.js`, base `ai/workspace/`)
- Conversations CRUD: create (5 types: `chat`, `dq_validate`, `dq_suggest`, `nl_query`, `anomaly`), list (filters: status/limit/q/is_archived/is_pinned/conversation_type), retrieve, PATCH (title/is_pinned/is_archived/visibility), DELETE.
- Messages: list (cursor pagination before/after, has_more), send, stream (SSE), edit, regenerate, stop, delete, feedback (accepted/rejected/corrected).
- Enterprise: summarize (deterministic fallback), export (json/markdown), acceptSuggestion/rejectSuggestion, confirmToolExecution/declineToolExecution (RULE_21 no auto-mutation!), listModels, profile/patchProfile, usage summary + per-conversation, artifacts (list/create/delete), suggestions (workspace-level + conversation-level + proactive accept/dismiss), resumeConversation, facts (list/forget), episodes (list), relationship.

### 1.4 Platform AI ops (`ai/protocol.py`)
- `dq.validate`, `dq.suggest`, `query.nl`, `query.explain`, `schema.analyze`, `fix.suggest`, `chat`
- Domain ops (`ai/domain/emissions.py`): `anomaly.detect`, `anomaly.explain`, `report.draft` (⚠ emissions.py known-gap note from config — verify existence)

### 1.5 Rich export surface (Phases A+B — recently shipped, commit a0cfc11)
- Rich clipboard copy (`copyRich` via `handleCopyWithFormatting`) — selection-aware rich copy from container
- Plain/markdown copy in More menu
- Export message submenu: Markdown / Rich HTML / Word (docx)
- Save images menu: PNG / SVG / zip
- Conversation export menu: Markdown / Rich HTML / Word / JSON (`buildConversationDocx/Html`)
- Long-content UX (`LongContent`): LONG_CONTENT_THRESHOLD=1600, COLLAPSE_MAX_HEIGHT=320, Show more/less

### 1.6 Feedback UX (FINAL state — color the thumb only)
- Accept → filled `ThumbUpAltIcon`, bg `rgba(46,125,50,0.10)`, fg `success.main`
- Reject → filled `ThumbDownAltIcon`, bg `rgba(211,47,47,0.10)`, fg `error.main`
- NO text chip, NO "Accepted"/"Rejected" label. Buttons stay CLICKABLE. All other tools remain.
- testids: `message-outcome-accepted`/`message-outcome-rejected` (colored), `accept-response`/`reject-response` (uncolored).

### 1.7 Engine internals (observe, do not modify)
- Six-witness pipeline (TurnPipelineRunner), LLM router, KG, memory, skills, MCP servers.
- DeepSeek V4-Flash default / V4-Pro for hard reasoning (RULE_24).
- DjangoStore CBAC partition: app_identifier / org_unit_id / host_user_id / visibility.
- RULE_23: NO implementation leakage in user-facing copy (no "Pulse"/engine jargon).

---

## 2. The 4-Layer Validation Model (this plan maps every scenario into a layer)

| Layer | Focus | Tools |
|-------|-------|-------|
| **L1 Structural** | verify.sh full, build, lint, antipatterns, migrations | terminal |
| **L2 Security/RBAC** | 401 / 403 / cross-org isolation / capability gate | curl + real JWT |
| **L3 Functional** | every API endpoint + UI behavior vs spec, shapes, pagination, error format | curl + Playwright |
| **L4 UX Audit** | W1–W10 per page × per role | browser |

Severity: P0 blocking / P1 high / P2 medium / P3 polish. Verdict rules per `qa-framework.md`.

---

## 3. CATEGORY A — Conversation Workspace Lifecycle (WS-*)

Goal: prove conversation CRUD, filtering, tab UX, keyboard shortcuts, offline banner.

| ID | Scenario | Steps / Assertions |
|----|----------|--------------------|
| WS-01 | Route + render | login admin → `/admin/ai/workspace` → heading "AI Workspace" + URL ends `/admin/ai/workspace` (W1/W7) |
| WS-02 | New chat tab | click "New chat" → new tab appears with type label `chat`, status dot |
| WS-03 | Create API | POST conversation `{conversation_type:'chat'}` → 201, `status:'pending'`, id present |
| WS-04 | Create all 5 types | POST each of chat/dq_validate/dq_suggest/nl_query/anomaly → 201 with correct type |
| WS-05 | List default | GET conversations/ → 200, envelope `{count,page_size,page,results}`, results non-empty |
| WS-06 | Filter is_archived | GET `?is_archived=true` → only archived |
| WS-07 | Filter is_pinned | GET `?is_pinned=true` → only pinned |
| WS-08 | Filter type | GET `?conversation_type=dq_suggest` → only that type |
| WS-09 | Search q | GET `?q=<title-substr>` → title match only |
| WS-10 | Retrieve | GET conversations/{id}/ → 200, shape matches created |
| WS-11 | Rename | PATCH `{title:'Sim Renamed'}` → 200; UI tab label updates |
| WS-12 | Pin | PATCH `{is_pinned:true}` → 200; UI tab reorders to pinned section |
| WS-13 | Archive active tab (REGRESSION) | MoreVert → Archive on ACTIVE tab → NO MUI "value provided to the Tabs component is invalid" error; active falls back to next visible |
| WS-14 | Restore | toggle Archived → Restore → back in active list |
| WS-15 | Keyboard Ctrl+W | archive active conversation via keyboard → succeeds |
| WS-16 | Keyboard Ctrl+Shift+T | restore last archived via keyboard → succeeds |
| WS-17 | Delete | DELETE conversations/{id}/ → 204; tab removed |
| WS-18 | Offline banner | simulate offline → `AIOfflineBanner` renders; restore → clears (W4) |
| WS-19 | Persistence RULE_17 | refresh page → active tab + tab selection persisted (localStorage `carbon-ai-active-conversation`) |
| WS-20 | Empty state | new user with 0 conversations → sensible empty-state CTA (W3) |
| WS-21 | Sidebar search | type in search box → tab list filters; clear → all return |

## 4. CATEGORY B — Messaging, Streaming & Modes (MSG-*)

Goal: prove send/stream/stop/edit/regenerate + send modes + SSE frame behavior.

| ID | Scenario | Steps / Assertions |
|----|----------|--------------------|
| MSG-01 | Send + stream (P0 probe) | type in `Message input` → `Send message` → working indicator → assistant bubble renders. **Invariant: NO ScopeGuard "empty user_identifier" error.** assistant message `status:'complete'` via listMessages |
| MSG-02 | Stream token deltas | capture SSE frames during chat → delta frames arrive before onDone |
| MSG-03 | Stream progress frames | non-chat (dq_validate) → progress frames then onDone |
| MSG-04 | Stop/interrupt | send, click stop while working → bubble status chip `Interrupted`; message.status === 'stopped' |
| MSG-05 | Stop API | POST .../stop/ → 200; generation halts |
| MSG-06 | Edit message | PATCH message content → 200, content updated |
| MSG-07 | Regenerate | POST .../messages/{id}/regenerate/ → 200, new assistant reply generated |
| MSG-08 | Delete message | DELETE message → 204; bubble removed |
| MSG-09 | Queue mode | send-mode `queue` while idle → message waits/flushes on completion |
| MSG-10 | Steer mode | send-mode `steer` → steering path engages |
| MSG-11 | Stop mode default | default send-mode renders; labels match (RULE_23: no jargon) |
| MSG-12 | Rate limit | burst sends → graceful 429 or serialized handling, no crash |
| MSG-13 | Long input | paste 5000-char message → sends without truncation; bubble renders full text |
| MSG-14 | Empty input guard | click send with empty/whitespace input → no request fires, no error |
| MSG-15 | Concurrency | two conversations open, send in both → responses land in the correct bubbles |
| MSG-16 | Offline send | offline → send disabled or banner; online → retry succeeds |

## 5. CATEGORY C — Response Formats, Figures, Tables, Links (FMT-*)

Goal: the user's core demand — "formats, figures and graphs, tables, links, flying to".
Observe EVERY assistant response for correct rendering.

| ID | Scenario | Steps / Assertions |
|----|----------|--------------------|
| FMT-01 | Markdown headings | assistant answer with #/##/### → rendered heading hierarchy, no raw `#` |
| FMT-02 | Bold/italic/quote | **bold**, *italic*, > blockquote → styled correctly |
| FMT-03 | GFM table | prompt "compare in a table" → MUI Table rendered (striped, scrollable), cells aligned, header row distinct |
| FMT-04 | Table borders | table has visible borders in dark+light mode (enforceTableBorders path) |
| FMT-05 | Code block | fenced code → monospace block with language label; copy button if present |
| FMT-06 | Inline code | `code` inline → styled inline, no XSS |
| FMT-07 | Mermaid diagram | ask for a flowchart → mermaid rendered (or placeholder if engine disabled); SVG present in DOM |
| FMT-08 | Mermaid export | mermaid message → export HTML/docx materializes mermaid as PNG data URI |
| FMT-09 | Math/KaTeX | inline $x^2$ and block $$ → rendered math (KaTeX) not raw LaTeX |
| FMT-10 | Links external | markdown link → `target=_blank` + `rel`; new tab, no navigation away |
| FMT-11 | Links internal (fly-to) | internal safe routes (`/carbon/my-data/...`, catalog pages) → SPA `<Link>` navigates in-app (W10 no 404) |
| FMT-12 | Fly-to table | answer mentions `#table:<name>` or table link → click → lands on the table page (correct module/table id) |
| FMT-13 | Fly-to rule | `#rule:<name>` link → lands on rule detail |
| FMT-14 | Fly-to field | `#field:<name>` → lands on field/schema |
| FMT-15 | Fly-to module | `#module:<name>` → lands on module page |
| FMT-16 | Bad link target | model returns invalid internal route → NO crash; graceful fallback (external tab or error toast) |
| FMT-17 | Lists | bullet + numbered lists render with proper indentation |
| FMT-18 | Mixed layout | long answer with heading+table+code+list → layout sane, no overlap, no horizontal page overflow |
| FMT-19 | RTL/Arabic content | Arabic answer (if model returns) → RTL-aware rendering, no garbled glyphs |
| FMT-20 | XSS probe | answer contains `<script>`/`<img onerror>` in markdown → rendered as text/escaped, no execution (RULE_5) |
| FMT-21 | Markdown injection via user | user message with markdown → user bubble renders as plain text (no HTML execution) |
| FMT-22 | SVG images | assistant returns SVG → renders inline; Save images menu offers PNG/SVG |
| FMT-23 | PNG images | PNG in response → renders; Save → PNG downloads |
| FMT-24 | Image zip save | multiple images → Save images → zip downloads with all items |
| FMT-25 | Footnote/reference styling | citations/footnotes render legibly (provenance-adjacent) |

## 6. CATEGORY D — Typed Result Cards (TYP-*)

Goal: every conversation type produces its typed card with correct actions.

| ID | Scenario | Steps / Assertions |
|----|----------|--------------------|
| TYP-01 | dq_suggest card | send dq_suggest → "AI suggests N DQ rules" card + Accept/Reject buttons per suggestion |
| TYP-02 | dq_suggest accept | click Accept on a suggestion → acceptSuggestion API 200; card reflects acceptance |
| TYP-03 | dq_suggest reject | Reject with reason → rejectSuggestion 200; card reflects |
| TYP-04 | nl_query result | send nl_query → SQL block + result grid card rendered |
| TYP-05 | nl_query grid | result grid shows real columns/rows, no empty unless genuinely 0 rows |
| TYP-06 | anomaly card | anomaly conversation → anomalies card, each anomaly clickable/inspectable |
| TYP-07 | anomaly explain | click anomaly → anomaly.explain output, severity markers |
| TYP-08 | dq_validate result | dq_validate → validation result card with pass/fail counts |
| TYP-09 | Card actions | accept/reject on cards calls confirmToolExecution path or suggestion accept (RULE_21: NO auto-mutation — assert mutation happens only after explicit confirm) |
| TYP-10 | InvestigateTab | Investigate tab renders investigation cards (`InvestigationCard`) with `onChatAbout` |
| TYP-11 | NLRuleTestCard | NL rule test card renders rule results table |
| TYP-12 | Card empty state | card with 0 results → sensible empty message, not blank |
| TYP-13 | Card dark mode | each card type readable in dark mode |
| TYP-14 | Card responsive | cards adapt at 768px (no horizontal scroll) |

## 7. CATEGORY E — Feedback & Learning Loop (FB-*)

Goal: the FINAL color-thumb UX + the full feedback → learning flywheel pipeline.

| ID | Scenario | Steps / Assertions |
|----|----------|--------------------|
| FB-01 | Accept color (P0 for UX) | click Accept → ONLY the accept button changes: filled `ThumbUpAltIcon`, bg `rgba(46,125,50,0.10)`, fg `success.main`; testid `message-outcome-accepted` present |
| FB-02 | Reject color | click Reject → ONLY reject button: filled `ThumbDownAltIcon`, bg `rgba(211,47,47,0.10)`, fg `error.main`; testid `message-outcome-rejected` present |
| FB-03 | NO text label (P0) | assert NO 'Accepted'/'Rejected' text anywhere in the bubble row |
| FB-04 | Other buttons intact | after feedback: Copy, Save images, More menu, and the OTHER thumb ALL still rendered + clickable |
| FB-05 | Re-clickable | click Accept then Reject on same message → state flips; vice versa |
| FB-06 | No double-fire | rapid double-click Accept → single feedback record (idempotent), no duplicate row |
| FB-07 | Feedback API | POST recordFeedback {outcome:'accepted'} → 200; listMessages shows `outcome` field persisted |
| FB-08 | Correct flow | click Correct → dialog opens → type correction → save → outcome corrected; correction text persisted |
| FB-09 | Correct dialog cancel | open Correct dialog → cancel → no state change, no API call |
| FB-10 | Feedback admin panel | `/admin/ai/feedback` lists feedback records with outcome breakdown (after FB-07/08) |
| FB-11 | Learning jobs panel | `/admin/ai/learning` shows judged messages / jobs |
| FB-12 | Flywheel status | `/admin/ai/learning-flywheel` shows durable backend, pending/processed, by_outcome, facts counts, feedback ledger |
| FB-13 | Run sweep (write action) | POST `learning-status/run/` → 200; sweep result {processed, accepted, rejected, corrected, errors}; status refreshes |
| FB-14 | Sweep idempotent | run sweep twice → no double-processing of same message (counts sane) |
| FB-15 | Feedback → long-term memory | accept a message → flywheel sweep → a fact appears in `/admin/ai/memory` or facts list |
| FB-16 | Reject → not learned | reject a message → after sweep → NO fact for that content |
| FB-17 | Correct → fact corrected | correct a message → after sweep → corrected fact present |
| FB-18 | Accept suggestion via card | TYP-01 accept → feedback/learning ledger reflects suggestion acceptance |
| FB-19 | Feedback panel RBAC | scoped user → `/admin/ai/feedback` 403 (console capability gated) |

## 8. CATEGORY F — Memory, Episodes, Relationships (MEM-*)

Goal: prove memory surface — facts, episodes, relationship tab, forget.

| ID | Scenario | Steps / Assertions |
|----|----------|--------------------|
| MEM-01 | Memory tab | `/admin/ai/memory` renders MemoryPanel (model-backed rows, not fabricated) |
| MEM-02 | Facts API | listFacts({category}) → 200, categorized facts |
| MEM-03 | Fact category filter | filter by category → only that category returned |
| MEM-04 | Relationship tab | AIWorkspace → Relationship tab → what assistant remembers about user, rendered from getRelationship |
| MEM-05 | Relationship empty | fresh user → relationship shows sensible empty state |
| MEM-06 | Forget fact | forgetFact(id) → 200; fact removed from list; UI updates |
| MEM-07 | Forget not-found | forgetFact(bogus-id) → 404, no crash |
| MEM-08 | Episodes API | listEpisodes({event_type}) → 200, episodes with event_type |
| MEM-09 | Episode filter | filter by event_type → only matching episodes |
| MEM-10 | Memory persistence | fact created in session → still present after backend restart (DjangoStore durable) |
| MEM-11 | Memory CBAC | scoped user's facts do NOT include admin's facts (isolation) |
| MEM-12 | Memory tab persistence | memory group internal tab selection persists (RULE_17, `carbon-ai-memory-tab`) |
| MEM-13 | Memory panel empty | empty memory → panel shows empty state, not spinner forever |

## 9. CATEGORY G — Knowledge Base, RAG & Knowledge Graph (KB-* / KG-*)

Goal: RAG behavior + the force-directed graph panel.

| ID | Scenario | Steps / Assertions |
|----|----------|--------------------|
| KB-01 | Knowledge panel | `/admin/ai/knowledge` renders KnowledgeBasePanel (model-backed rows) |
| KB-02 | Knowledge data API | getPulseData('knowledge') → 200, {key,label,count,models,results} |
| KB-03 | RAG grounding | ask a question answerable from seeded docs → answer references KB content |
| KB-04 | RAG citation | answer shows provenance/why-this-answer with sources from KB |
| KB-05 | RAG no-match | ask something not in KB → honest "not found" style answer, no fabrication |
| KG-01 | Graph panel | `/admin/ai/graph` renders force-directed graph (canvas/svg nodes+edges) |
| KG-02 | Graph API | getPulseGraph → 200 {nodes, edges, stats{node_count, edge_count, truncated, node_types, relationship_counts}} |
| KG-03 | Graph stats | node_count > 0 (seeded); edge_count matches nodes |
| KG-04 | Truncation flag | large graph → `truncated` flag honest; UI shows truncation notice |
| KG-05 | Hover tooltip | hover node → tooltip with label/relationship |
| KG-06 | Click-to-inspect | click node → side panel with node detail |
| KG-07 | Legend | node-type legend rendered |
| KG-08 | Graph/Table toggle | toggle to Table → reuses PulseDataPanel with graph rows |
| KG-09 | Graph responsive | graph panel adapts at 768px (no overflow) |
| KG-10 | Graph dark mode | graph legible in dark mode |

## 10. CATEGORY H — Agents, Tools, MCP, Skills, Archetypes, Prompts (AGT-*)

Goal: the entire "Agents & Tooling" group — read-only panels + the tool-execution contract.

| ID | Scenario | Steps / Assertions |
|----|----------|--------------------|
| AGT-01 | Agents panel | `/admin/ai/agents` renders model-backed agents |
| AGT-02 | Agents data API | getPulseData('agents') → 200 |
| AGT-03 | MCP servers panel | `/admin/ai/mcp` renders MCP servers list |
| AGT-04 | Tools panel | `/admin/ai/tools` renders tools catalog |
| AGT-05 | Skills panel | `/admin/ai/skills` renders skills catalog |
| AGT-06 | Archetypes panel | `/admin/ai/archetypes` → getPulseArchetypes → bundles with name+kind |
| AGT-07 | Prompts panel | `/admin/ai/prompts` renders prompts & playbook |
| AGT-08 | Tool confirm gate (RULE_21 P0) | message triggers a tool → execution waits; confirmToolExecution(executionId) → 200 and tool runs; declineToolExecution → 200 and tool does NOT run |
| AGT-09 | No auto-mutation (P0) | assert NO tool side effect occurs before explicit confirm (check DB/logs unchanged pre-confirm) |
| AGT-10 | Tool decline path | decline → UI shows declined state; no mutation |
| AGT-11 | Tool inventory | listModels → 200, model list includes default (DeepSeek V4-Flash) and pro option |
| AGT-12 | Panel spinner | each panel shows loading spinner while fetching (W2) |
| AGT-13 | Panel empty | panel with 0 rows → empty hint, not blank |
| AGT-14 | Panel error | force API error → friendly error paper, no crash (W4) |
| AGT-15 | Capability gate | non-AI-capable user → all `/admin/ai/*` routes 403 (AdminRoute capability check) |
| AGT-16 | Redaction | EngineSettingsPanel — secrets redacted server-side; assert no raw secret values in DOM |

## 11. CATEGORY I — Budget, Usage, Engine Settings (USG-*)

Goal: honest, non-fabricated cost/usage data.

| ID | Scenario | Steps / Assertions |
|----|----------|--------------------|
| USG-01 | Usage panel | `/admin/ai/budget-usage` renders BudgetUsagePanel |
| USG-02 | Usage API | getUsage → 200 {budget_usd, spent_today_usd, tokens_today, calls_today, tokens_total, calls_total, cost_total, remaining_usd, budget_exceeded, by_model, by_day} |
| USG-03 | by_model shape | by_model has per-model entries with tokens/cost |
| USG-04 | by_day shape | by_day 7-day entries |
| USG-05 | budget_exceeded | set budget low / exceed → flag flips true; UI shows warning (no crash) |
| USG-06 | Usage per conversation | getUsageByConversation({period}) → 200 per-conversation rows |
| USG-07 | Usage tab in shell | AIWorkspace → Usage tab (AIUsageTab) — table rows, totals |
| USG-08 | Usage dark mode | usage tables readable in dark mode |
| USG-09 | Token attribution | assistant message carries token_usage_json; usage chip tooltip shows model/tokens/cost/latency (S19 legacy) |
| USG-10 | Settings API | getSettings → 200 {llm, limits, cache, rate_limit, routing, mcp_servers, tools_catalog, agents} — redacted |
| USG-11 | Engine settings panel | `/admin/ai/engine-settings` renders inventory; no raw secrets in DOM |
| USG-12 | Usage empty | no calls yet → zeros shown honestly, no fabricated numbers |

## 12. CATEGORY J — Provenance, Transparency, Thinking (TR-*)

Goal: "thinkings" — observe how the assistant explains itself.

| ID | Scenario | Steps / Assertions |
|----|----------|--------------------|
| TR-01 | Why-this-answer tooltip | hover "Why this answer" → provenance lines (Conversation/App/Org units) |
| TR-02 | Provenance API | provenance fields present in message metadata (app_identifier, org_unit_id, host_user_id, visibility) |
| TR-03 | Usage chip | usage chip tooltip → model/tokens/cost/latency breakdown |
| TR-04 | Status chips | Interrupted / Error chips render on stopped/failed messages |
| TR-05 | No jargon (RULE_23 P0) | assert UI copy contains NO "Pulse", "TurnPipeline", "witness", "engine", "DjangoStore" jargon — user-facing text only |
| TR-06 | Thinking honesty | hard-reasoning task → model routes to V4-Pro (verify via usage by_model or metadata) |
| TR-07 | Default model | normal chat → routed to V4-Flash (RULE_24) |
| TR-08 | Working notice | during generation → "working" notice visible, not silent (W2) |
| TR-09 | Error honesty | failed generation → friendly error message + retry affordance, no raw stack |
| TR-10 | Token discipline | off-peak (if applicable) → token usage within budget (RULE_26) |

## 13. CATEGORY K — Rich Copy & Export (Phases A+B) (EXP-*)

Goal: prove the just-shipped rich export stack end-to-end.

| ID | Scenario | Steps / Assertions |
|----|----------|--------------------|
| EXP-01 | Rich copy button | hover bubble → Copy → rich clipboard payload (HTML+text); paste into Word retains bold/table/image |
| EXP-02 | Selection-aware copy | select part of a long answer → container copy captures ONLY selection, rich format |
| EXP-03 | Plain copy | More → Copy plain text → text-only clipboard |
| EXP-04 | Markdown copy | More → Copy markdown → md string |
| EXP-05 | Export message md | Export message → Markdown (.md) → download triggered; content has md syntax |
| EXP-06 | Export message HTML | Export → Rich HTML → .html download; opens with formatting (tables + images) |
| EXP-07 | Export message docx | Export → Word (.docx) → file downloads; openable; tables bordered (enforceTableBorders); mermaid → PNG image |
| EXP-08 | Save images PNG | Save images → PNG → download(s) with correct names (slugified) |
| EXP-09 | Save images SVG | Save images → SVG → svg serialized with computed styles |
| EXP-10 | Save images zip | Save images → zip → archive with all media items (lazy jszip import works) |
| EXP-11 | Conversation md | conversation export → Markdown → all messages included, ordered |
| EXP-12 | Conversation HTML | conversation export → Rich HTML → full thread formatted |
| EXP-13 | Conversation docx | conversation export → Word → all messages, tables, images |
| EXP-14 | Conversation JSON | export → JSON → parseable; messages array with roles/content |
| EXP-15 | Export empty conversation | export conversation with no messages → graceful (empty doc / toast), no crash |
| EXP-16 | Long-content toggle | answer >1600 chars → Show more; click → expands; Show less → collapses |
| EXP-17 | Long-content threshold | answer <1600 chars → no toggle shown |
| EXP-18 | Copy long content | select text inside collapsed content → copy still works |
| EXP-19 | Docx image from data URI | imageRunFromDataUri path — image present in docx after export |
| EXP-20 | Filename slug | exportFilename slugifies titles (no spaces/special chars breaking downloads) |
| EXP-21 | Export keyboard | export menus reachable via keyboard (tab + enter) |
| EXP-22 | Export dark mode | export dialogs/menus readable in dark mode |
| EXP-23 | Export no broken links | exported HTML internal links rewritten correctly (rewriteLinks) |
| EXP-24 | Export tables borders | docx/html tables have borders (enforceTableBorders) — no borderless export |

## 14. CATEGORY L — Mentions, Follow-ups, Context (MNT-*)

Goal: the input-bar intelligence.

| ID | Scenario | Steps / Assertions |
|----|----------|--------------------|
| MNT-01 | # mention menu | focus input, type `#` → menu lists #table/#rule/#field/#module (aria-label `Mention kinds`) |
| MNT-02 | #table insertion | select #table → token inserted into input |
| MNT-03 | #table resolution | send with #table:<name> → resolved to concrete table_id (payload has table_id) |
| MNT-04 | #rule resolution | #rule → rule id resolved |
| MNT-05 | #field resolution | #field → field resolved |
| MNT-06 | #module resolution | #module → module resolved |
| MNT-07 | Follow-up chips | assistant message with follow_up_questions → click chip → new user message with that text |
| MNT-08 | No chips | no follow-ups → no empty chip row |
| MNT-09 | Context panel | AIContextPanel reflects in-flight mention state; merged with input-bar mentions |
| MNT-10 | Domain entry points | catalog pages (SchemaDetail/DataProductDetail) render AIDomainEntryPoints from manifest; dispatch transferTask with app_identifier (Gap C regression) |
| MNT-11 | Entry point dq_validate | click dq_validate entry point on a table → task_payload carries table_id (Gap A regression: no "default dq_validate chip with no table_id" bug) |
| MNT-12 | Entry point report_draft | module-scoped report_draft → payload has module_id + period_id |
| MNT-13 | Entry point chat | chat entry point → transfer opens chat with entity context |
| MNT-14 | Mention unknown | `#table:NonExistent` → graceful resolution (null table_id) — no 500 (defensive ?? null) |

## 15. CATEGORY M — Platform & Domain AI Ops (OPS-*)

Goal: every ops op works as a regular user would invoke it.

| ID | Scenario | Steps / Assertions |
|----|----------|--------------------|
| OPS-01 | dq.validate | run → 200, validation result with pass/fail per rule |
| OPS-02 | dq.suggest | run → 200, N suggestions |
| OPS-03 | query.nl | "show emissions by month" → 200, SQL + result |
| OPS-04 | query.explain | explain a query → 200, explanation text |
| OPS-05 | schema.analyze | analyze schema → 200, analysis |
| OPS-06 | fix.suggest | suggest fix for a failing rule → 200, suggestion |
| OPS-07 | chat | plain chat → 200, assistant reply |
| OPS-08 | anomaly.detect | emissions anomalies → 200, anomaly list (domain) |
| OPS-09 | anomaly.explain | explain anomaly → 200 |
| OPS-10 | report.draft | draft emissions report → 200, report content (⚠ verify `ai/domain/emissions.py` exists — known gap) |
| OPS-11 | Domain manifests API | getPulseData('apps') / listDomainManifests → 200 {apps, count}, each with entry_points + starter_prompts |
| OPS-12 | Ops error format | invalid payload → 400 with `{detail}` envelope (api-contract) |
| OPS-13 | Ops unauthenticated | no token → 401 on every ops endpoint |
| OPS-14 | Ops scoped | scoped user → ops restricted to own org subtree (no cross-org data in results) |
| OPS-15 | Ops latency | each op returns within acceptable time; latency recorded for report |

## 16. CATEGORY N — Security / RBAC Matrix (SEC-*)

Goal: Layer 2 — the full matrix, with REAL JWTs.

| ID | Check | Expected |
|----|-------|----------|
| SEC-01 | No token → GET conversations/ | 401 |
| SEC-02 | No token → POST conversations/ | 401 |
| SEC-03 | No token → GET conversations/{id}/ | 401 |
| SEC-04 | No token → POST messages/send/ | 401 |
| SEC-05 | No token → GET /ai/pulse/inventory/ | 401 |
| SEC-06 | No token → POST /ai/pulse/learning-status/run/ | 401 |
| SEC-07 | viewer → POST conversations/ (create) | 403 (read-only) |
| SEC-08 | viewer → POST messages/send/ | 403 |
| SEC-09 | dataowner → GET conversations/ | 200; only own org subtree — no admin/other-branch conversations |
| SEC-10 | dataowner → GET conversations/{admin-owned}/ | 404/403 — never 200 |
| SEC-11 | dataowner → PATCH/DELETE conversations/{admin-owned}/ | 404/403 — never 200 |
| SEC-12 | dataowner → GET admin's facts | scoped — no leak |
| SEC-13 | dataowner → POST /ai/pulse/learning-status/run/ | 403 (console write is admin-only) |
| SEC-14 | dataowner → GET /ai/pulse/settings/ | 403 (console read is capability-gated) |
| SEC-15 | admin → all above reads | 200/201 |
| SEC-16 | Cross-org: two dataowners | A's conversations/facts never visible to B |
| SEC-17 | XSS: user payload with <script> | stored as text; no execution on re-render |
| SEC-18 | IDOR: message of another conversation | 404/403 |
| SEC-19 | IDOR: suggestion of another conversation | 404/403 |
| SEC-20 | Secret redaction | no API response includes raw secrets (grep evidence) |

## 17. CATEGORY O — Layer 4 UX Audit (UX-*)

Goal: 10-point checklist on key pages × roles. Capture screenshots only on failure.

| # | Check | Pages |
|---|-------|-------|
| UX-W1 | RENDER — no console errors | workspace, all 20 admin/ai pages, catalog pages with entry points |
| UX-W2 | LOADING — spinner while fetching | all Pulse panels |
| UX-W3 | EMPTY — sensible empty state | workspace (0 conv), memory (0 facts), panels (0 rows) |
| UX-W4 | ERROR — friendly error, no crash | offline, API 500, bad route |
| UX-W5 | DARK_MODE — toggle, no hardcoded colors | workspace + panels + export menus |
| UX-W6 | BREADCRUMB — present + correct | workspace → /admin/ai/workspace |
| UX-W7 | TITLE — page-specific | each /admin/ai/* page has distinct document.title |
| UX-W8 | RESPONSIVE — 768px, no horizontal overflow | workspace, graph, budget, export menus |
| UX-W9 | KEYBOARD — focus visible, tab order, Ctrl+W / Ctrl+Shift+T | workspace |
| UX-W10 | NO_404_LINKS — no broken internal links | fly-to links, entry points, breadcrumbs, sidebar |

Additional UX scenarios:
| ID | Scenario | Steps / Assertions |
|----|----------|--------------------|
| UX-11 | Console errors clean | browser console 0 errors across 30-min usage session |
| UX-12 | Zoom 150% | no layout break at 150% zoom |
| UX-13 | Long titles | conversation title 200 chars → truncates gracefully |
| UX-14 | Rapid tab switching | open/close 10 tabs quickly → no MUI Tabs invalid-value error |
| UX-15 | Refresh mid-stream | refresh during generation → recovered state (message status or banner), no crash |

---

## 4. Execution & Simulation Protocol

### 4.1 Tooling
1. **Browser (primary):** Playwright against `http://127.0.0.1:5179/carbon/`. Login `ahmed`/`AdminPa_132`.
2. **API (secondary):** curl with real JWT (get via `/carbon-api/auth/token/`). Check `HTTP <code>` on every call.
3. **Evidence:** per scenario → screenshot on failure only; DOM assertions via `run_playwright_code`
   (testids, computed styles via `getComputedStyle`), network + console capture.

### 4.2 Data seeding (before simulation)
- Seed ≥1 conversation of each type with ≥1 completed message (via UI or API).
- Seed ≥60 messages in one conversation (API loop) for pagination (MSG/cursor tests).
- Seed 2 dataowners in different branches for cross-org (SEC-16).
- Ensure KB has seeded docs for RAG tests.

### 4.3 Order of execution
1. L1 structural gate (verify.sh full + npm run build).
2. L2 security (SEC-01..20) — fastest, highest signal.
3. L3 functional — categories in order: WS → MSG → FMT → TYP → FB → MEM → KB/KG → AGT → USG → TR → EXP → MNT → OPS.
4. L4 UX audit (UX-W1..W10 + UX-11..15).
5. Compile `docs/TASK-RESULT-QA-AI-PULSE-SIMULATION.md`.

### 4.4 Recording format (per scenario, in the result doc)
```
| ID | Result | Evidence |
| WS-03 | ✅ | POST conversations/ → HTTP 201, {id:…, status:'pending'} |
| SEC-09 | ❌ P1 | dataowner GET conversations/ returned admin conv {id:99} → RBAC leak |
```

---

## 5. Output Contract — `docs/TASK-RESULT-QA-AI-PULSE-SIMULATION.md`

1. **Executive Summary** (2–4 sentences + verdict).
2. **Layer 1** — verify.sh full tail + `npm run build` tail + pytest summary.
3. **Layer 2** — SEC matrix with HTTP codes + RBAC evidence.
4. **Layer 3** — all categories A–M scenario tables ✅/❌/⚠.
5. **Layer 4** — UX-W1..W10 + UX-11..15.
6. **Findings table** — ID | severity (P0–P3) | symptom | reproduction steps | evidence | suggested owner.
7. **Gate verdict** — exactly one of `PASSED` / `PASSED WITH FINDINGS` / `FAILED` (per `qa-framework.md` rules).
8. **Handoff** — defects listed for Debugger/Fixer (who writes a regression test FIRST).

---

## 6. DO NOT TOUCH

- Any product code under `backend/` or `carbon-frontend/src/` (validation only; may add test
  artifacts like e2e specs or the result doc).
- `backend/ai/tests/test_store_execute.py` (broken WIP — never run it).
- The 9 pre-existing frontend test failures (AIArtifacts 2, AIMessageBubble.feedback 3, AISharedThreads 4).
- Do NOT run `manage.py flush` / drop DB / change migrations.
- NEVER run docker. NEVER fall back to SQLite.

## 7. Hard Rules (from `project.config.md` + memory)

- PostgreSQL only. Redis on 127.0.0.1:6379.
- Report real-time output; never silent-tail-pipe a run.
- Evidence over description: every ✅ needs terminal/HTTP/DOM proof.
- Keep user-facing chat responses short and direct.
- RULE_21 no auto-mutation — verify confirm gate in AGT-08/09 (P0 if broken).
- RULE_23 no implementation leakage — TR-05 (P0 if jargon appears).
- Feedback UX is color-the-thumb ONLY — FB-01..05 (P0 if text/labels return).
