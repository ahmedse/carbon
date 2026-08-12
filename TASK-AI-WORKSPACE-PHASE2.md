# TASK-AI-WORKSPACE-PHASE2.md
# Master Architect — Phase Spec
# Date: 2026-08-12
# Status: READY FOR WORKERS
# Depends on: TASK-AI-WORKSPACE-PHASE1 (COMPLETE ✅)

---

## Summary

Expand the AI Workspace from chat + dq_validate to a full-featured AI companion. Add `dq_suggest` (AI proposes DQ rules), `nl_query` (ask natural language questions about data), and `anomaly` (detect anomalies in profile history) as first-class conversation types. Enhance message rendering with structured result cards.

---

## Architecture — What Phase 2 Adds

```
                        AI Workspace Tabs
                        ─────────────────
┌─────────────────┐  ┌─── Chat ───────────────────────┐
│ Main Workspace   │  │  Free-form conversation        │
│                  │  │  (Phase 1 — DONE)              │
│ DQ Rule Detail   │  └────────────────────────────────┘
│ [Suggest AI] ────┼─→┌─── DQ Suggest ─────────────────┐
│                  │  │  🤖 "Based on your table       │
│ DQ Workspace     │  │      profile, I suggest:"      │
│ [Ask about data] ┼─→│  • Completeness rule (98%)     │
│                  │  │  • Uniqueness check (87%)      │
│ Emissions Dash   │  │  [Accept] [Reject] [Refine]    │
│ [Ask AI] ────────┼─→└────────────────────────────────┘
└─────────────────┘  ┌─── NL Query ────────────────────┐
                     │  🤖 "SELECT scope, sum(co2)...  │
                     │      → 12 rows returned"        │
                     │  📊 ┌─ Results Table ──────────┐│
                     │     │ scope │ total_co2        ││
                     │     │ 1     │ 45,230           ││
                     │     └──────────────────────────┘│
                     └────────────────────────────────┘
                     ┌─── Anomaly Detection ───────────┐
                     │  🤖 "Anomaly in emissions_fuel: │
                     │      row_count dropped 42%      │
                     │      z-score: 3.8, severity: 🔴 │
                     │  [View Details] [Dismiss]       │
                     └────────────────────────────────┘
```

---

## PHASE 2-A: Backend — New Task Type Support in CarbonIntelligence

**Role:** Backend Worker  
**Model:** DeepSeek-V3  
**Domain:** backend/ai/

### PRE-FLIGHT

| File | Why |
|------|-----|
| `backend/ai/intelligence.py` | CarbonIntelligence — add suggest/nl_query/anomaly message routing |
| `backend/ai/protocol.py` | ABC — ensure DqSuggestRequest, NlQueryRequest, AnomalyDetectRequest carry ConversationContext |
| `backend/ai/models.py` | AIConversation — conversation_type choices already include dq_suggest, nl_query |
| `backend/ai/providers/pulse.py` | Pulse provider — may need payload adjustments |
| `backend/dq/services.py` | DQ services — profile_table, run_single_rule |
| `backend/dq/models.py` | DQJob, DQSuggestion, DQAnomaly — the models AI workspace results map to |
| `.ai-toolkit/shared/ai-contract.md` | AI Contract — §2 operation categories |

### TASKS

#### TASK 1: Add ConversationContext to all protocol request dataclasses

**MODIFY** `backend/ai/protocol.py` — add optional `conversation` field to:

```python
# DqSuggestRequest (already has scope)
conversation: ConversationContext | None = None

# NlQueryRequest (already has scope)  
conversation: ConversationContext | None = None

# AnomalyDetectRequest (already has scope)
conversation: ConversationContext | None = None
```

These already exist in protocol.py from Phase 1-A. Just add the field.

**Verify:**
```bash
./manage.sh test backend.ai.tests.test_protocol
```

---

#### TASK 2: Route conversation types in send_message()

**MODIFY** `backend/ai/intelligence.py` — extend the `send_message()` routing:

```python
# CURRENT (Phase 1):
if conv_type == "dq_validate":
    response = self._send_dq_validate_message(...)
else:
    # Default: chat

# PHASE 2 — add branches:
if conv_type == "dq_validate":
    response = self._send_dq_validate_message(...)
elif conv_type == "dq_suggest":
    response = self._send_dq_suggest_message(...)
elif conv_type == "nl_query":
    response = self._send_nl_query_message(...)
elif conv_type == "anomaly":
    response = self._send_anomaly_message(...)
else:
    # Default: chat
```

#### TASK 2a: Implement _send_dq_suggest_message()

When conversation type is `dq_suggest`:
1. Extract table info from `task_payload_json` (table_id, table_name, row_count, columns)
2. Build `TableProfile` + `DqSuggestRequest` with conversation context
3. Call `provider.suggest_dq(request)`
4. Parse suggestions → save each as a structured assistant message
5. Each suggestion gets its own message bubble with accept/reject metadata
6. Set status to `needs_input` (user must accept/reject/refine)

#### TASK 2b: Implement _send_nl_query_message()

When conversation type is `nl_query`:
1. Use user's message content as the NL question
2. Build `NlQueryRequest` with conversation context
3. Call `provider.query_nl(request)`
4. Save SQL + rows as structured assistant message (metadata_json)
5. Frontend will render rows as a table

#### TASK 2c: Implement _send_anomaly_message()

When conversation type is `anomaly`:
1. Extract table info from `task_payload_json`
2. Load profile history (last N TableProfile snapshots for the table)
3. Build `AnomalyDetectRequest` with conversation context
4. Call `provider.detect_anomalies(request)` — or fall back to chat if provider doesn't support it
5. Save anomalies as structured assistant message

**Rules for ALL:**
- Guard chain runs before every provider call (ScopeGuard + AccessGuard minimum)
- On provider_unavailable → save "AI unavailable" message, set status failed
- On error → save error message, set status failed
- Messages carry structured metadata_json for rich frontend rendering
- Run ALL 5 guards (ScopeGuard, AccessGuard, DataIsolationGuard, MutationGuard must all be called)

**Verify:**
```bash
./manage.sh test backend.ai.tests.test_intelligence
```

---

#### TASK 3: Create backend tests for new conversation types

**CREATE** tests in `backend/ai/tests/test_workspace_messages.py`:

Test cases (≥ 8):
1. `dq_suggest` conversation → routes to suggest provider
2. `nl_query` conversation → routes to nl_query provider
3. `anomaly` conversation → routes to anomaly provider
4. Provider unavailable → conversation status failed, graceful message
5. Empty table profile → useful error in message
6. ConversationContext carries full history on each turn
7. Guard chain rejects calls without scope
8. `needs_input` status set when suggestions returned

**Verify:**
```bash
./manage.sh test backend.ai.tests.test_workspace_messages --keepdb
```

---

### DO NOT TOUCH

- `backend/ai/guards.py` — unchanged
- `backend/ai/providers/pulse.py` — provider ABC methods unchanged (they already exist)
- `backend/dq/` — DQ services/jobs unchanged
- Any frontend files

### GATES

```bash
./manage.sh manage check
./manage.sh test backend.ai.tests --keepdb
./manage.sh test --keepdb
./.ai-toolkit/scripts/verify.sh backend
```

---

## PHASE 2-B: Frontend — Enhanced AI Workspace UI

**Role:** Frontend Worker  
**Model:** DeepSeek-V3  
**Domain:** carbon-frontend/src/shell/  
**Depends on:** Phase 2-A complete

### PRE-FLIGHT

| File | Why |
|------|-----|
| `src/shell/AIWorkspace.jsx` | Main component — you'll update create handlers |
| `src/shell/AIConversationView.jsx` | Conversation view — you'll add structured result rendering |
| `src/shell/AIMessageBubble.jsx` | Message bubble — you'll add result cards |
| `src/shell/AITaskTransferContext.jsx` | Task transfer — supporting new types |
| `src/api/aiWorkspace.js` | API layer — already has createConversation |
| `src/api/dq.js` | DQ API — reference for table profiles, suggestions |
| `src/pages/dq/DQWorkspacePage.jsx` | DQ workspace — you'll add "Ask AI" / "Suggest AI" buttons |

### TASKS

#### TASK 4: Add task transfer triggers to DQ Workspace

**MODIFY** `src/pages/dq/DQWorkspacePage.jsx` — add AI trigger buttons:

1. **Overview tab** → "Ask AI about DQ health" button (nl_query type)
2. **Rules tab** → "Suggest rules with AI" button (dq_suggest type, passes table_id)
3. **Jobs tab** → "Analyze failures with AI" button (nl_query type)
4. **Suggestions tab** — already shows suggestions; add "Refine with AI" button per suggestion (transfer to chat)

**MODIFY** `src/pages/dq/RuleDetailPage.jsx`:
1. **Stats tab** → "Analyze trend with AI" button (nl_query)
2. **Results tab** → "Explain failures with AI" button (nl_query)

**Rules:**
- All use `useAITaskTransfer()` — same pattern as existing DefinitionTab/TestTab "Validate with AI"
- Use `AutoAwesomeIcon` consistently
- `variant="outlined"`, `size="small"`
- Theme tokens only

---

#### TASK 5: Enhanced message rendering — structured result cards

**MODIFY** `src/shell/AIMessageBubble.jsx` — detect `metadata_json` and render structured cards:

When an AI message has metadata, render it specially instead of plain text:

**DQ Suggestion cards:**
```jsx
// When metadata_json.type === "dq_suggestions"
<Box>
  <Typography variant="subtitle2">AI suggests {n} DQ rules:</Typography>
  {suggestions.map(s => (
    <Paper variant="outlined" sx={{ p: 1.5, mb: 1 }}>
      <Stack direction="row" justifyContent="space-between">
        <Box>
          <Typography variant="body2" fontWeight={600}>{s.definition.name}</Typography>
          <Typography variant="caption">{s.rationale}</Typography>
          <Chip size="small" label={`${s.confidence}%`} />
        </Box>
        <Stack direction="row" gap={0.5}>
          <Button size="small" color="success" onClick={handleAccept}>Accept</Button>
          <Button size="small" color="error" onClick={handleReject}>Reject</Button>
        </Stack>
      </Stack>
    </Paper>
  ))}
</Box>
```

**NL Query result table:**
```jsx
// When metadata_json.type === "nl_query_result"
<Box>
  <Typography variant="caption" sx={{ fontFamily: 'monospace', bgcolor: 'action.hover', p: 1, borderRadius: 1, display: 'block', mb: 1 }}>
    {sql}
  </Typography>
  <CarbonDataGrid rows={rows} columns={cols} density="compact" hideFooter={rows.length <= 25} />
  <Typography variant="caption" color="text.secondary">{row_count} rows</Typography>
</Box>
```

**Anomaly cards:**
```jsx
// When metadata_json.type === "anomalies"
<Box>
  <Typography variant="subtitle2">Anomalies detected:</Typography>
  {anomalies.map(a => (
    <Paper variant="outlined" sx={{ p: 1.5, mb: 1, borderLeft: 4, borderColor: a.severity === 'error' ? 'error.main' : 'warning.main' }}>
      <Stack direction="row" justifyContent="space-between">
        <Typography variant="body2" fontWeight={600}>{a.metric}</Typography>
        <Chip size="small" color={a.severity} label={`z=${a.z_score?.toFixed(1)}`} />
      </Stack>
      <Typography variant="caption">{a.explanation}</Typography>
    </Paper>
  ))}
</Box>
```

**Rules:**
- ALL styling uses theme tokens — no raw hex, no raw px
- CarbonDataGrid imported for query result tables
- DQ suggestion accept/reject calls the DQ API (`acceptDQSuggestion`, `rejectDQSuggestion`)
- Anomaly details link to `/dq/rules/:id/results`
- Follow RULE_10: apiFetch for all API calls
- Follow RULE_17: no ad-hoc button rows for actions

---

#### TASK 6: Create conversation from DQ Workspace context

**MODIFY** `src/shell/AITaskTransferContext.jsx` — enhance `transferTask()`:

Add smarter defaults for new types:
- `nl_query`: auto-include table name, row count, column list in payload
- `dq_suggest`: auto-include table profile data (row count, columns with types)
- `anomaly`: auto-include table_id, profile count hint

**CREATE** `src/api/aiWorkspace.js` additions (if not already present):
```javascript
// Accept/reject a DQ suggestion from within AI workspace
export function acceptSuggestion(token, suggestionId) { ... }
export function rejectSuggestion(token, suggestionId, reason) { ... }
```

---

#### TASK 7: Handle needs_input with action buttons

**MODIFY** `src/shell/AIConversationView.jsx`:

When conversation status is `needs_input` and the last AI message has action buttons (accept/reject suggestions, confirm anomalies), render them as prominent action buttons below the message list — NOT just inline chips in the bubble.

Additionally, show a contextual hint above the input bar:
- `dq_suggest + needs_input`: "Accept or reject the suggested rules above, or ask for refinements."
- `anomaly + needs_input`: "Review the detected anomalies. Ask for details or dismiss."
- Default: "AI is waiting for your response…"

---

#### TASK 8: Loading states for long-running tasks

**MODIFY** `src/shell/AIWorkingIndicator.jsx`:

Add contextual messages based on conversation type:
- `dq_suggest`: "AI is analyzing your table profile and generating rule suggestions…"
- `nl_query`: "AI is querying your data…"
- `anomaly`: "AI is scanning profile history for anomalies…"
- `chat`: "AI is thinking…" (current behavior)

**MODIFY** `src/shell/AIConversationView.jsx`:

Add a small polling notice for tasks that might take longer:
- After 5 seconds of `working` state → show "This may take a moment…"
- After 15 seconds → show "Still working… complex analysis in progress"
- After 30 seconds → show "Taking longer than expected. You can switch to another tab and come back."

---

### DO NOT TOUCH

- `src/shell/Shell.jsx` — wire-up unchanged from Phase 1
- `src/shell/useShellState.js` — unchanged
- `src/shell/StatusBar.jsx` — unchanged
- `src/theme/carbonTheme.js` — unchanged
- Backend files

### GATES

```bash
cd carbon-frontend && npm run lint
cd carbon-frontend && npm run build
cd carbon-frontend && npm test
./.ai-toolkit/scripts/verify.sh frontend
```

---

## PHASE ORDER

```
Phase 2-A (Backend) ──complete──→ Phase 2-B (Frontend)
```

Phase 2-B CANNOT start until 2-A's API routes are available.
