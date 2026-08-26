# Next-Gen AI-Era Readiness — Phased Plan
# =========================================
# Author: Master Architect · Date: 2026-08-26
# Scope: frontend + backend changes for all NGX phases (no "Contextual AI in UI"
#        — that surface stays in the dedicated AI workspace per product decision).
#
# CURRENT STATE BASELINE (confirmed by codebase audit 2026-08-26)
# ---------------------------------------------------------------
# ✅ SSE streaming works for AI chat   (sendMessageStream / retryMessageStream via
#    fetch+ReadableStream; backend StreamingHttpResponse text/event-stream)
# ✅ Optimistic UI for AI message ops  (AIConversationView.jsx: append / delete /
#    rollback — ONLY inside AI workspace)
# ✅ Redis 5.0.1 available             (for pub/sub cross-process events)
# ✅ Django asgi.py present            (plain get_asgi_application — no Channels)
# ✅ Proactive delivery engine         (delivery.py, notifier.py — in-memory
#    WebSocket subscribers scoped to the AI engine, not Django HTTP layer)
# ✅ NetworkStatusBanner               (online/offline detection complete)
# ✅ DQ / plans SSE backend            (plans_api.py, workspace_api.py already emit
#    text/event-stream frames — NOT yet consumed by dedicated progress UI)
# ❌ No real-time platform event bus   (no cross-component SSE subscription)
# ❌ No optimistic CRUD outside AI workspace
# ❌ No collaborative presence
# ❌ No proactive notification panel linked to backend
# ❌ No AI output transparency signals in UI
# ❌ No skeleton screens (spinners only)
# ❌ No Web Vitals / frontend observability
# ❌ No service worker / offline form resilience
#
# ARCHITECTURE DECISIONS (binding for all phases)
# -----------------------------------------------
# AD-1  Real-time transport = SSE via StreamingHttpResponse (NOT Django Channels).
#       No new dependency. Works through nginx. Backed by Redis pub/sub so events
#       survive multi-process deployment.
#       Single auth-gated endpoint: GET /carbon-api/events/stream/
#       (org-scoped, JWT-authenticated, CBAC-filtered).
#
# AD-2  Optimistic UI pattern follows AIConversationView.jsx precedent:
#       (1) apply local state immediately, (2) fire API call, (3) on success replace
#       local with server state, (4) on failure roll back with notifyFromError().
#
# AD-3  Frontend logger → utils/logger.js wrapping console in DEV, silencing in
#       PROD and POSTing errors to /carbon-api/telemetry/client-error/ (backend
#       Phase NGX-9B).
#
# AD-4  Skeleton screens use MUI <Skeleton> exclusively. No new spinner variants.
#
# AD-5  Presence system is lightweight (SSE heartbeats, NOT operational lock).
#       It shows WHO is viewing — it does NOT block edits or enforce locking.
#
# PHASE SEQUENCE & DEPENDENCIES
# -----------------------------------------------
# NGX-1 (Progress Streaming)  — no dependencies
# NGX-2 (Optimistic CRUD)     — no dependencies
# NGX-3 (Event Bus SSE)       — prerequisite for NGX-4, NGX-5, NGX-6
# NGX-4 (Notification Panel)  — requires NGX-3
# NGX-5 (Presence)            — requires NGX-3
# NGX-6 (Live Data)           — requires NGX-3
# NGX-7 (AI Transparency)     — no hard dependency; can run in parallel with NGX-3
# NGX-8 (Skeleton Screens)    — no dependencies
# NGX-9 (Observability)       — no hard dependencies
# NGX-10 (Offline/SW)         — no hard dependencies; NGX-9 adds value first
#
# DISPATCH ORDER (suggested two-track parallelism):
#   Track A: NGX-1 → NGX-2 → NGX-3 → NGX-4 → NGX-5 → NGX-6
#   Track B: NGX-7 → NGX-8 → NGX-9 → NGX-10
#   (both tracks can run simultaneously once NGX-1/NGX-2/NGX-7 start)

---

## Phase NGX-1 — SSE Progress Streaming for Long Operations
**Workers:** backend-worker + frontend-worker (sequential)
**Status:** READY
**Estimated effort:** 3 days (1.5 backend + 1.5 frontend)

### Context
The backend already emits `text/event-stream` frames for AI chat, DQ rule NL-check
runs (`plans_api.py`), and agent action streams (`workspace_api.py`). The frontend
only consumes those streams for AI workspace conversations. Three other long-running
operations — DQ profile runs, bulk CSV imports, and emissions report generation —
are silent: the user sees an indeterminate spinner with no per-step feedback.

### Backend Sub-phase (NGX-1A) — backend-worker

#### Files to read first
- `backend/ai/plans_api.py` (DQ run SSE pattern lines 340–370 and 500–520)
- `backend/dq/views.py` (run_profile view — currently returns sync 202)
- `backend/importexport/views.py` (bulk import view — currently sync)
- `backend/emissions/views.py` (report generation — currently sync)

#### New / changed files
**1. `backend/dq/stream_views.py`** — NEW
```
GET /carbon-api/dq/runs/{run_id}/stream/

Streams frames over text/event-stream for a DQ profile run.
Uses Redis pub/sub (keyed to run_id) so multiple browser tabs receive
the same stream.  Emits the following frame types:
  { "type": "progress", "stage": "profiling", "pct": 0..100 }
  { "type": "rule",     "rule_id": "...", "passed": bool, "rows_failed": N }
  { "type": "done",     "run_id": "...", "summary": { pass, fail, warn } }
  { "type": "error",    "error": "..." }

Auth: JWT-gated (same as plans_api). The view publishes via Django signals /
celery task updates; a background task publishes Redis events to the channel
`dq:run:{run_id}`.
```

**2. `backend/importexport/stream_views.py`** — NEW
```
GET /carbon-api/importexport/imports/{import_id}/stream/

Frames:
  { "type": "progress", "stage": "parsing|validating|inserting", "pct": 0..100 }
  { "type": "row_error", "row": N, "field": "...", "message": "..." }
  { "type": "done",     "import_id": "...", "inserted": N, "errors": N }
  { "type": "error",    "error": "..." }
```

**3. `backend/emissions/stream_views.py`** — NEW
```
GET /carbon-api/emissions/reports/{report_id}/stream/

Frames:
  { "type": "progress", "stage": "calculating|formatting", "pct": 0..100 }
  { "type": "section",  "section": "scope_1|scope_2|scope_3", "status": "done" }
  { "type": "done",     "report_id": "...", "download_url": "..." }
  { "type": "error",    "error": "..." }
```

**4. `backend/core/stream_utils.py`** — NEW (shared helper)
```python
def redis_sse_stream(channel: str, heartbeat_secs: int = 15):
    """
    Generator: subscribes to Redis pub/sub channel, yields SSE-formatted lines,
    emits heartbeat comments every heartbeat_secs to keep the connection alive
    through proxies, exits cleanly on 'done' or 'error' frame type.
    """
```

#### Verification gate
```bash
python manage.py check
python -m pytest dq -q --maxfail=5
python -m pytest importexport -q --maxfail=5
# Confirm endpoints registered:
python manage.py show_urls | grep stream
```

---

### Frontend Sub-phase (NGX-1B) — frontend-worker

#### Files to read first
- `carbon-frontend/src/api/aiWorkspace.js` lines 418–680 (streamJsonPost implementation)
- `carbon-frontend/src/components/Page/` (existing loading states)
- `carbon-frontend/src/pages/dq/DQWorkspacePage.jsx`
- `carbon-frontend/src/components/import/BulkImportWizard.jsx`
- `carbon-frontend/src/pages/emissions/ReportGeneratorPage.jsx`

#### New / changed files

**1. `carbon-frontend/src/hooks/useStreamingJob.js`** — NEW
```
Generic hook for consuming any Carbon SSE job stream.

useStreamingJob(url, { onChunk?, onProgress?, onDone?, onError?, autoStart? })

Returns: { stage, pct, running, done, error, start(), stop() }

Internally:
  - Uses fetch + ReadableStream (same as streamJsonPost — NOT EventSource,
    which cannot send Authorization headers)
  - Sends Authorization: Bearer <token> header
  - Heartbeat timeout: abort if no frame for 30s
  - Cleans up reader on unmount
  - Calls notifyFromError() on error frame
```

**2. `carbon-frontend/src/components/Page/StreamingProgressBar.jsx`** — NEW
```
A slim, reusable progress indicator fed by useStreamingJob.

Props: { url, label, frameLabels?: { stage → string }, onDone?, onError? }

Renders:
  - LinearProgress (determinate when pct known, indeterminate otherwise)
  - Current stage label (uses frameLabels map or falls back to stage key)
  - Cancel button (calls stopGeneration or a job-cancel endpoint)
  - On done: shows checkmark + summary chip
  - Handles all 4 states: loading / streaming / done / error
```

**3. `carbon-frontend/src/pages/dq/DQWorkspacePage.jsx`** — MODIFY
```
Wire StreamingProgressBar into the "Run Profile" flow.
Replace indeterminate spinner with useStreamingJob pointing to
/carbon-api/dq/runs/{run_id}/stream/ once run_id is returned by the
POST /carbon-api/dq/runs/ response.
Show per-rule pass/fail chips as they arrive via { type: "rule" } frames.
```

**4. `carbon-frontend/src/components/import/BulkImportWizard.jsx`** — MODIFY
```
Step 3 (Processing) replaces the current indeterminate spinner with
StreamingProgressBar. Row-level errors from { type: "row_error" } frames
are accumulated in a local list and shown in a collapsible error accordion.
```

**5. `carbon-frontend/src/pages/emissions/ReportGeneratorPage.jsx`** — MODIFY
```
After POST creates the report job, replace redirect/polling with
StreamingProgressBar. On { type: "done" } frame, show download button
immediately without a page reload.
```

#### Verification gate
```bash
cd carbon-frontend
npm run lint                          # 0 new errors
npx vitest run src/__tests__/useStreamingJob.test.js
npm run build
```

---

## Phase NGX-2 — Platform-Wide Optimistic CRUD
**Workers:** frontend-worker
**Status:** READY
**Estimated effort:** 2 days

### Context
Optimistic UI exists only in `AIConversationView.jsx` (Phase 19-B pattern).
Every other page does full round-trip on create/update/delete — the user sees
a spinner, then the list reloads. At enterprise scale this is slow and jarring.
The pattern: apply change locally → fire API → on success replace local with
server state → on failure roll back + `notifyFromError()`.

### Files to read first
- `carbon-frontend/src/shell/AIConversationView.jsx` lines 700–780 (existing optimistic pattern)
- `carbon-frontend/src/hooks/useApi.js`
- `carbon-frontend/src/pages/dq/tabs/RulesTab.jsx`
- `carbon-frontend/src/pages/catalog/DataProductsPage.jsx`
- `carbon-frontend/src/pages/carbon/MyDataPage.jsx`

### New files

**1. `carbon-frontend/src/hooks/useOptimisticList.js`** — NEW
```
Generic hook for optimistic list management.

useOptimisticList(initialItems, { idField = 'id' })

Returns:
  items           — current visible list (with pending items included)
  optimisticAdd(item)    → rollback() + serverConfirm(serverItem)
  optimisticUpdate(id, patch)  → rollback() + serverConfirm(serverItem)
  optimisticRemove(id)   → rollback() + serverConfirm()
  pendingIds      — Set of IDs currently in-flight (for rendering indicators)

Contract:
  1. optimisticAdd(item) appends item with a temp UUID; returns { rollback, confirm }
  2. caller fires API, on resolve calls confirm(serverItem) to swap UUID→real ID
  3. on reject calls rollback() which removes the temp item + calls notifyFromError()
  4. optimisticUpdate marks the item with { _pending: true } for dim rendering
  5. optimisticRemove marks with { _removing: true } for fade-out animation
```

**2. `carbon-frontend/src/hooks/useOptimisticItem.js`** — NEW
```
Single-item variant for detail page update forms.

useOptimisticItem(initialData)

Returns:
  data, pendingFields, optimisticPatch(fields), rollback(), confirm(serverData)

Renders a thin "saving…" indicator while the PATCH is in flight.
```

### Pages to wire up (apply optimistic pattern)

**Priority A — highest interaction frequency:**
- `pages/dq/tabs/RulesTab.jsx` — enable/disable toggle + delete
- `pages/catalog/DataProductsPage.jsx` — create + delete data products
- `pages/carbon/MyDataPage.jsx` — delete source
- `pages/catalog/MetadataManagementPage.jsx` — tag/domain CRUD

**Priority B — moderate frequency:**
- `pages/admin/UsersPage.jsx` — user enable/disable
- `pages/emissions/EmissionFactorsPage.jsx` — factor delete
- `pages/emissions/ReportingPeriodsPage.jsx` — period activate/close

**Pattern for each wired page:**
```jsx
// Before (current):
const handleDelete = async (id) => {
  setLoading(true);
  await apiDelete(id);
  setData(d => d.filter(x => x.id !== id));
  setLoading(false);
};

// After (optimistic):
const { items, optimisticRemove } = useOptimisticList(data);
const handleDelete = async (id) => {
  const { rollback } = optimisticRemove(id);
  try {
    await apiDelete(token, id);
  } catch (err) {
    rollback();
    notifyFromError(err, 'Delete failed');
  }
};
```

**Rendering in-flight items:**
```jsx
<TableRow
  key={row.id}
  sx={{ opacity: row._removing ? 0.4 : row._pending ? 0.7 : 1,
        transition: 'opacity 150ms ease-out' }}
>
```

### Verification gate
```bash
npm run lint
npx vitest run src/__tests__/useOptimisticList.test.js
npx vitest run src/__tests__/useOptimisticItem.test.js
npm run build
```

---

## Phase NGX-3 — Platform-Wide Real-Time Event Bus (SSE)
**Workers:** backend-worker + frontend-worker (sequential)
**Status:** READY (after AD-1 decision; no Channels dependency)
**Estimated effort:** 3 days (1.5 backend + 1.5 frontend)

### Context
The backend engine has proactive insight delivery (`delivery.py`) but it
dispatches to an in-memory WebSocket registry scoped to the AI engine process.
The Django HTTP layer has no real-time push capability. This phase adds a
platform-wide authenticated SSE endpoint backed by Redis pub/sub, making
real-time events available to all frontend features (notifications, live DQ
scores, presence, pipeline status).

### Backend Sub-phase (NGX-3A) — backend-worker

#### Architecture

```
Publisher (any Django view/task)
  → redis.publish("carbon:events:{org_unit_id}", json.dumps(event))

SSE Endpoint (GET /carbon-api/events/stream/)
  ← Auth: JWT + CBAC (only events for user's org_unit_ids)
  ← Django StreamingHttpResponse (text/event-stream)
  ← redis.subscribe("carbon:events:{oid}" for oid in user.org_unit_ids)
  ← Heartbeat comment (":\n\n") every 20s to keep proxy alive
  ← Graceful close on client disconnect (GeneratorExit)
```

#### Event envelope (canonical)
```json
{
  "type":       "dq.score_changed | insight.new | job.progress | job.done |
                 presence.join | presence.leave | data.refreshed | …",
  "org_unit_id": "uuid",
  "payload":    { … type-specific … },
  "ts":         "2026-08-26T12:00:00Z"
}
```

#### Files to create

**1. `backend/core/events.py`** — NEW
```python
REDIS_EVENT_PREFIX = "carbon:events"

def publish_event(org_unit_id: str, event_type: str, payload: dict):
    """
    Publish a platform event to Redis for real-time SSE delivery.
    Fire-and-forget: catches all exceptions (event delivery is best-effort).
    """

def subscribe_events(org_unit_ids: list[str]) -> Generator[dict, None, None]:
    """
    Redis pub/sub generator. Subscribes to all org_unit channels, yields
    parsed event dicts, emits {'type': 'heartbeat'} every 20s.
    Caller wraps in StreamingHttpResponse.
    """
```

**2. `backend/core/events_api.py`** — NEW
```python
# GET /carbon-api/events/stream/
# Auth: IsAuthenticated + CBAC scope
# Returns: StreamingHttpResponse(content_type="text/event-stream")
#          Cache-Control: no-cache, X-Accel-Buffering: no
#
# On connect: sends {"type": "connected", "instance_id": "..."}
# On disconnect: GeneratorExit cleans up Redis subscription
# Max connection lifetime: 30 minutes (prevents stale connections)
```

**3. Integrate publish_event into existing operations:**
- `dq/tasks.py` → publish `dq.score_changed` when profile run finishes
- `dq/views.py` → publish `job.progress` / `job.done` for DQ runs
- `importexport/views.py` → publish `job.done` for completed imports
- `ai/delivery.py` → replace in-memory push with `publish_event` for
  `insight.new` (keeps in-memory subscribers as fallback for dev)

**4. `backend/core/urls.py`** — MODIFY
```python
path('events/stream/', events_api.EventStreamView.as_view()),
```

#### Verification gate
```bash
python manage.py check
python -m pytest core -q --maxfail=5
# Integration smoke:
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8009/carbon-api/events/stream/ \
     --no-buffer -N | head -5
# Expected: data: {"type":"connected",...}
```

---

### Frontend Sub-phase (NGX-3B) — frontend-worker

#### Files to read first
- `carbon-frontend/src/api/aiWorkspace.js` (`streamJsonPost` — reuse pattern)
- `carbon-frontend/src/auth/AuthContext.jsx`
- `carbon-frontend/src/components/NotificationProvider.jsx`

#### New files

**1. `carbon-frontend/src/hooks/useEventStream.js`** — NEW
```
Singleton SSE connection to /carbon-api/events/stream/.

useEventStream()

Returns: { connected, subscribe(eventType, handler), unsubscribe(eventType, handler) }

Internals:
  - Connects once per auth session (singleton via module-level ref)
  - Re-connects with exponential back-off (1s → 2s → 4s → max 30s) on disconnect
  - Stops reconnecting when user logs out
  - Heartbeat watchdog: if no frame for 45s, tear down + reconnect
  - Auth: same as streamJsonPost (fetch + Authorization header, token refresh)
  - Dispatches parsed frames to registered handlers by event type
  - Clears all handlers on logout

subscribe(eventType, handler):
  eventType may be exact ("dq.score_changed") or prefix-glob ("dq.*")
```

**2. `carbon-frontend/src/shell/EventStreamProvider.jsx`** — NEW
```
Root-level provider that starts the SSE connection after login and tears
it down on logout.  Consumes AuthContext; renders nothing (pure side-effect).
Mount in Shell.jsx INSIDE <AuthProvider> but OUTSIDE <Router>.
```

**3. `carbon-frontend/src/hooks/useEventSubscription.js`** — NEW
```
Convenience hook for components that need to react to one or more event types.

useEventSubscription(eventType | eventType[], handler, deps)
  - Wraps useEventStream().subscribe() / unsubscribe()
  - Cleans up on unmount
  - Re-subscribes when deps change
```

#### Wire EventStreamProvider
- `carbon-frontend/src/shell/Shell.jsx` — add `<EventStreamProvider />` after `<AuthProvider>`

#### Verification gate
```bash
npm run lint
npx vitest run src/__tests__/useEventStream.test.js
npx vitest run src/__tests__/EventStreamProvider.test.jsx
npm run build
```

---

## Phase NGX-4 — Proactive Intelligence Notification Panel
**Workers:** backend-worker + frontend-worker (sequential)
**Prerequisites:** NGX-3 complete
**Status:** PLANNED
**Estimated effort:** 2.5 days (1 backend + 1.5 frontend)

### Context
The AI engine's `delivery.py` delivers proactive insights (DQ anomalies, data
freshness alerts, SBTi deviation warnings) to a WebSocket registry. With the
NGX-3 event bus in place, those insights can now be surfaced in the shell's
notification bell as real-time, actionable cards — turning a passive bell into
an active intelligence feed.

### Backend Sub-phase (NGX-4A) — backend-worker

#### Changes
**1. `backend/ai/delivery.py`** — MODIFY
```
After persisting KgProactiveInsight, call publish_event() with:
  type: "insight.new"
  payload: { id, severity, title, narrative, recommended_actions,
             insight_type, context, expires_at }
Org-unit is resolved from the instance_id → OrgUnit mapping.
```

**2. `backend/ai/ops_api.py`** — ADD endpoints (under /carbon-api/ai/pulse/)
```
GET  /insights/              — paginated list (unread first; filter: severity, type, unread)
POST /insights/{id}/read/    — mark as read
POST /insights/{id}/dismiss/ — soft-delete
GET  /insights/unread-count/ — { count: N } for the bell badge
```

**3. `backend/ai/serializers.py`** — ADD `ProactiveInsightSerializer`
```
Fields: id, severity, title, narrative, recommended_actions, insight_type,
        context, disposition, created_at, expires_at
```

#### Verification gate
```bash
python manage.py check
python -m pytest ai -q --maxfail=5
```

---

### Frontend Sub-phase (NGX-4B) — frontend-worker

#### New / changed files

**1. `carbon-frontend/src/api/insights.js`** — NEW
```
listInsights(token, { unreadOnly?, severity?, page? })
markRead(token, id)
dismissInsight(token, id)
getUnreadCount(token)
```

**2. `carbon-frontend/src/hooks/useInsights.js`** — NEW
```
Wraps listInsights + getUnreadCount.
Subscribes to useEventSubscription('insight.new') to prepend new insights
in real-time without polling.
Returns: { insights, unreadCount, loading, markRead, dismiss, refetch }
```

**3. `carbon-frontend/src/shell/NotificationBell.jsx`** — NEW (replaces placeholder)
```
Shell bell icon with:
  - Badge showing unreadCount (capped at 99+)
  - Popover panel (width 380px, max-height 480px, scrollable)
  - Tab bar: All / Unread / By severity
  - Per-insight card:
      [severity icon] [title] [timestamp]
      [narrative — 2 lines max, expandable]
      [recommended_actions as chips]
      [Mark read] [Dismiss] actions
  - Empty state: "No alerts — all clear"
  - "View all in AI Console" link → /admin/ai/pulse/insights
  - Loading skeleton (3 cards)
  - Error state with retry
```

**4. `carbon-frontend/src/shell/Shell.jsx`** — MODIFY
```
Replace current notification icon with <NotificationBell />.
```

#### Insight card severity mapping
```
critical → error color + ErrorOutlineIcon + red left border
warning  → warning color + WarningAmberIcon + amber left border
info     → info color + InfoOutlinedIcon + blue left border
```

#### Verification gate
```bash
npm run lint
npx vitest run src/__tests__/NotificationBell.test.jsx
npm run build
```

---

## Phase NGX-5 — Real-Time Collaborative Presence
**Workers:** backend-worker + frontend-worker (sequential)
**Prerequisites:** NGX-3 complete
**Status:** PLANNED
**Estimated effort:** 2 days (0.5 backend + 1.5 frontend)
**Constraint (AD-5):** Presence shows who is viewing — does NOT lock or block edits.

### Context
Multiple data owners and analysts work on the same platform simultaneously.
There is no signal when someone else is viewing or editing the same record.
This leads to duplicate work, silent overwrites, and coordination overhead.

### Backend Sub-phase (NGX-5A) — backend-worker

**1. `backend/core/presence_api.py`** — NEW
```
POST /carbon-api/presence/join/
  Body: { entity_type: "table|module|schema|conversation|...",
          entity_id: "uuid" }
  Action: publishes presence.join event via publish_event(); records in
          Redis with 45s TTL (key: "presence:{entity_type}:{entity_id}").
  Returns: { viewers: [{ user_id, display_name, avatar_initials, color }] }

POST /carbon-api/presence/leave/
  Body: { entity_type, entity_id }
  Action: removes from Redis set; publishes presence.leave event.

GET /carbon-api/presence/?entity_type=&entity_id=
  Returns: { viewers: [...] } (current snapshot, for initial hydration)
```

Heartbeat: frontend calls POST /join/ every 30s to refresh TTL (presence is
dropped automatically if the user closes the tab without calling /leave/).

**2. `backend/core/urls.py`** — ADD presence routes

#### Verification gate
```bash
python manage.py check
python -m pytest core -q --maxfail=5
```

---

### Frontend Sub-phase (NGX-5B) — frontend-worker

**1. `carbon-frontend/src/hooks/usePresence.js`** — NEW
```
usePresence(entityType, entityId)

On mount:
  1. POST /presence/join/ → get initial viewers list
  2. Subscribe useEventSubscription('presence.*') to update viewers
  3. Start 30s heartbeat interval to re-POST /join/ and refresh TTL
On unmount:
  1. POST /presence/leave/
  2. Clear heartbeat

Returns: { viewers: [{ user_id, display_name, avatar_initials, color, isMe }] }
Excludes current user from the returned list (we don't show yourself).
```

**2. `carbon-frontend/src/components/entity/PresenceAvatars.jsx`** — NEW
```
Compact avatar stack for presence indicators.

Props: { entityType, entityId, maxVisible? = 3 }

Uses usePresence internally.

Renders:
  - Up to maxVisible Avatar chips (initials + user-assigned color)
  - Overflow: "+2 others" badge
  - Tooltip on each avatar: display_name
  - Entrance/exit transitions (150ms fade-in/fade-out)
  - Renders nothing if viewers list is empty (no wasted space)
  - Size: 24px avatars (xs — compact to sit alongside page headers)
```

**3. Wire into key pages:**
- `EntityDetailShell.jsx` — add `<PresenceAvatars>` in the header row
- `BaseDetailPage.jsx` — add `<PresenceAvatars>` in the header row
- `ModuleWorkspacePage.jsx` — show who else is in the workspace

**4. Concurrent edit detection for forms:**
```
When usePresence returns viewers.length > 0 AND the local user opens an
edit form (not just viewing), show a non-blocking Banner:

  "2 other people are viewing this record. Your changes will overwrite theirs."
  [Continue editing] [View read-only]

Component: carbon-frontend/src/components/entity/ConcurrentEditBanner.jsx
Show only when: entity has an edit form open AND viewers.length > 0
```

#### Verification gate
```bash
npm run lint
npx vitest run src/__tests__/usePresence.test.js
npx vitest run src/__tests__/PresenceAvatars.test.jsx
npm run build
```

---

## Phase NGX-6 — Live Data Updates (DQ Scores, Pipeline Status)
**Workers:** frontend-worker
**Prerequisites:** NGX-3 complete
**Status:** PLANNED
**Estimated effort:** 1.5 days

### Context
DQ scores on MyDataPage and the Catalog display the state at page-load time.
Running a DQ profile updates the score on the backend, but the UI only reflects
it on next page load. With the NGX-3 event bus, `dq.score_changed` events arrive
in real-time and can update stale rows without a full reload.

### New / changed files

**1. `carbon-frontend/src/hooks/useLiveField.js`** — NEW
```
useEventSubscription-based hook for a single live-updating value.

useLiveField(eventType, { filter, extract })

  eventType: "dq.score_changed"
  filter:    (event) => event.payload.module_id === moduleId
  extract:   (event) => event.payload.quality_score

Returns: { value, updatedAt, flash } where flash is true for 2s after update
(used to render a brief highlight animation on the updated cell).
```

**2. `carbon-frontend/src/pages/carbon/MyDataPage.jsx`** — MODIFY
```
DQ% column in the grid:
  - Wrap quality_score display with useLiveField('dq.score_changed', ...)
  - On live update: animate the cell with a 2s green flash
    (sx={{ bgcolor: flash ? alpha(success.main, 0.12) : 'transparent',
           transition: 'background-color 600ms ease-out' }})
  - LAST ENTRY column similarly updated with 'data.refreshed' event
```

**3. `carbon-frontend/src/shell/StatusBar.jsx`** — MODIFY
```
Add live pipeline job indicator:
  - Subscribe to 'job.progress' and 'job.done' events
  - Show a compact chip in the status bar while a job is running:
    [CircularProgress size=12] "DQ run in progress…"
  - On done: briefly show a checkmark chip, then fade out after 3s
  - At most one indicator visible at a time (latest job wins)
```

**4. `carbon-frontend/src/pages/dq/DQWorkspacePage.jsx`** — MODIFY
```
Rules list: subscribe to 'dq.rule_result' events.
When an event arrives for a rule in the current list, update that row's
pass/fail badge in real-time without refetching the full list.
```

**5. Live refresh for DataGrid rows:**
Add a `useEventSubscription('data.refreshed')` call in `FilteredDataGrid.jsx`
that calls `refetch()` when the refreshed entity_type matches the grid's scope.
Include a debounce of 500ms to batch rapid successive events.

#### Verification gate
```bash
npm run lint
npx vitest run src/__tests__/useLiveField.test.js
npm run build
```

---

## Phase NGX-7 — AI Output Transparency & Trust Layer
**Workers:** frontend-worker
**Prerequisites:** None (can start in parallel with NGX-1)
**Status:** READY
**Estimated effort:** 2 days

### Context
AI-generated content in the workspace (suggested DQ rules, report drafts,
schema analysis) has no visual markers distinguishing it from user-authored
content. There is no confidence signal, no reasoning trace, and no diff-view
showing what the AI changed vs the original. Enterprise users need to know
WHAT the AI generated, HOW confident it is, and WHY — before they confirm.

### New / changed files

**1. `carbon-frontend/src/components/ai/AIGeneratedBadge.jsx`** — NEW
```
Compact "AI" badge to mark AI-generated content at a glance.

Props: { confidence?, size? = 'small', tooltip? }

Renders:
  - AutoAwesome icon + "AI" label chip (variant="outlined", color="info")
  - If confidence provided: small percentage label beside icon
  - Tooltip: "Generated by Carbon AI" or custom tooltip prop
  - size="tiny": icon only (for dense table cells)
  - size="small": icon + "AI" text (default)
  - size="medium": icon + "AI" + confidence bar
  - All colors from theme tokens; no hardcoded hex
```

**2. `carbon-frontend/src/components/ai/ConfidenceBar.jsx`** — NEW
```
Horizontal bar showing AI confidence level.

Props: { score: 0..1, showLabel? = true }

Renders a LinearProgress with semantic color:
  ≥ 0.8 → success.main   (high confidence)
  ≥ 0.6 → warning.main   (medium — review recommended)
  < 0.6 → error.main     (low — treat as draft)
Label: "High / Medium / Low confidence"
```

**3. `carbon-frontend/src/components/ai/ReasoningTrace.jsx`** — NEW
```
Collapsible chain-of-thought reasoning display.

Props: { steps: string[], collapsed? = true }

Renders:
  - Collapsed: [info icon] "Show reasoning (N steps)"
  - Expanded: numbered list of reasoning steps in a subtle inset box
    (bgcolor: action.hover, borderLeft: 2px solid info.main)
  - Transition: 200ms expand/collapse
  - Only renders when steps.length > 0
```

**4. `carbon-frontend/src/components/ai/AISuggestionDiff.jsx`** — NEW
```
Diff view for AI-suggested text changes (rule text, schema descriptions,
report sections).

Props: { original: string, suggested: string, onAccept, onReject }

Renders:
  - Side-by-side original vs suggested (or unified diff for long text)
  - Removed lines: error.light background
  - Added lines: success.light background
  - Accept / Reject action buttons
  - Uses diff-match-patch (already in package.json? check; add if needed)
  - Compact variant for table cells: single-line diff with toggle
```

**5. `carbon-frontend/src/components/ai/AIOutputCard.jsx`** — NEW
```
Standardized container wrapping any AI-generated output block.

Props: { confidence?, reasoning?, children, onAccept?, onReject?,
         label? = "AI Suggestion", generatedAt? }

Renders:
  - Left border: 3px solid info.main
  - Header: <AIGeneratedBadge confidence={confidence} /> + timestamp
  - Content: children (slot for DQ rule, report section, schema desc, etc.)
  - Footer: [ReasoningTrace steps={reasoning}] if provided
            [Accept] [Edit] [Reject] if onAccept/onReject provided
  - Background: alpha(info.main, 0.04) — subtle tint
```

**6. Wire into existing AI surfaces:**
- `shell/AIMessageBubble.jsx` — wrap AI replies that carry `confidence` field
  with `AIGeneratedBadge` (size="tiny") in the message meta row
- `pages/dq/tabs/RulesTab.jsx` — AI-suggested rules show `AIOutputCard`
  wrapping the rule text before user confirms
- `pages/catalog/tabs/SchemaStructureTab.jsx` — AI-suggested field
  descriptions use `AISuggestionDiff` before apply
- `pages/emissions/ReportGeneratorPage.jsx` — AI-generated report sections
  show `AIOutputCard` with per-section accept/reject

#### Verification gate
```bash
npm run lint
npx vitest run src/__tests__/AIGeneratedBadge.test.jsx
npx vitest run src/__tests__/AISuggestionDiff.test.jsx
npm run build
```

---

## Phase NGX-8 — Skeleton Screens & Progressive Enhancement
**Workers:** frontend-worker
**Prerequisites:** None (can start in parallel)
**Status:** READY
**Estimated effort:** 2 days

### Context
Every data-fetching view uses `CircularProgress` (indeterminate spinner) while
loading. Spinners create layout shift — the page jumps from empty to populated.
Skeleton screens pre-render the structural chrome (columns, headings, cards) so
the page feels instant and no layout shift occurs. This is the single largest
perceived-performance win achievable purely in the frontend.

### Strategy
Replace `<CircularProgress>` loading states with `<Skeleton>` layouts that match
the real content shape. Priority: high-traffic pages first.

### New / changed files

**1. `carbon-frontend/src/components/Page/SkeletonTable.jsx`** — NEW
```
Skeleton variant of a data table (N rows × M columns).

Props: { rows? = 8, cols? = 5, showHeader? = true, showToolbar? = true }

Renders:
  - Toolbar skeleton (optional): search box + 2 button shapes
  - Header row: Skeleton variant="text" for each column
  - N data rows: mix of text and rectangular Skeletons
  - Compact row height matching DataGrid compact density
```

**2. `carbon-frontend/src/components/Page/SkeletonDetailPage.jsx`** — NEW
```
Skeleton variant of BaseDetailPage 3-column layout.

Renders:
  - Header bar: breadcrumb skeleton + title skeleton
  - Main panel: tab strip skeleton + content block skeleton
  - Metrics panel: 4 metric card skeletons
```

**3. `carbon-frontend/src/components/Page/SkeletonCard.jsx`** — NEW
```
Skeleton variant of StatCard / MetricCard.
Props: { count? = 4 } — renders count cards in a Grid.
```

**4. Migrate loading states — Priority order:**

**P0 (highest traffic):**
- `pages/carbon/MyDataPage.jsx` → SkeletonTable (replaces spinner overlay)
- `pages/dq/DQWorkspacePage.jsx` → SkeletonTable
- `pages/catalog/DataProductsPage.jsx` → SkeletonTable
- `pages/EmissionsDashboard.jsx` → SkeletonCard + SkeletonTable

**P1:**
- All `BaseDetailPage` usages: pass `loading` prop → render `<SkeletonDetailPage>`
- `pages/admin/UsersPage.jsx` → SkeletonTable
- `pages/admin/OrgUnitsPage.jsx` → SkeletonTable
- `pages/catalog/MetadataManagementPage.jsx` → SkeletonTable

**P2 (lower traffic):**
- Remaining pages with spinners identified in audit

**Migration pattern:**
```jsx
// Before:
if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
  <CircularProgress />
</Box>;

// After:
if (loading) return <SkeletonTable rows={8} cols={5} />;
```

**5. Route-level progressive enhancement:**
- Add `loading.jsx` convention for each route group using React.lazy + Suspense
- Suspense fallback = skeleton matching that route's layout

#### Verification gate
```bash
npm run lint
npm run build
# Visual check: load MyDataPage with network throttled to Slow 3G
# Expected: skeleton renders immediately, no layout shift on data load
```

---

## Phase NGX-9 — Frontend Observability
**Workers:** frontend-worker (A) + backend-worker (B) — parallel then converge
**Prerequisites:** None
**Status:** READY
**Estimated effort:** 2 days

### Context
There is no structured frontend logging, no client-side error telemetry, and no
Web Vitals measurement. When users encounter crashes or slowdowns in production,
there is no signal. This phase adds: (1) a structured logger replacing console.*,
(2) ErrorBoundary → backend error reporting, (3) Web Vitals collection, (4) a
backend `/telemetry/` endpoint to receive and store client reports.

---

### Backend Sub-phase (NGX-9A) — backend-worker

**1. `backend/core/telemetry_api.py`** — NEW
```
POST /carbon-api/telemetry/client-error/
  Body: { message, stack?, component?, url, user_agent,
          correlation_id, ts, context: {} }
  Auth: IsAuthenticated (JWT)
  Action: logs at ERROR level with user + org context;
          stores in a lightweight TelemetryEvent model (30-day retention).

POST /carbon-api/telemetry/vitals/
  Body: { metric_name, value, rating, url, ts }
       metric_name: "CLS" | "FID" | "FCP" | "LCP" | "TTFB" | "INP"
       rating: "good" | "needs-improvement" | "poor"
  Auth: IsAuthenticated
  Action: logs + stores in TelemetryEvent.

GET /carbon-api/telemetry/summary/
  Auth: admin only
  Returns: { vitals: {...}, error_count_24h, worst_pages: [...] }
```

**2. `backend/core/models.py`** — ADD `TelemetryEvent`
```python
class TelemetryEvent(models.Model):
    kind       = models.CharField(max_length=20)   # "error" | "vital"
    user       = models.ForeignKey(User, null=True, on_delete=SET_NULL)
    org_unit   = models.ForeignKey(OrgUnit, null=True, on_delete=SET_NULL)
    payload    = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        indexes = [models.Index(fields=['kind', 'created_at'])]
```

#### Verification gate
```bash
python manage.py check
python manage.py makemigrations core --name telemetry_event
python -m pytest core -q --maxfail=5
```

---

### Frontend Sub-phase (NGX-9B) — frontend-worker

**1. `carbon-frontend/src/utils/logger.js`** — NEW
```javascript
/*
 * Structured frontend logger.
 * In DEV: writes to console with emoji prefixes.
 * In PROD: silences INFO/DEBUG; sends ERROR frames to backend telemetry.
 */

export const logger = {
  debug: (msg, ctx) => { /* DEV only */ },
  info:  (msg, ctx) => { /* DEV only */ },
  warn:  (msg, ctx) => { /* DEV only; no backend report */ },
  error: (msg, ctx) => {
    // DEV: console.error(msg, ctx)
    // PROD: POST /carbon-api/telemetry/client-error/ fire-and-forget
    //       include correlation_id from ErrorBoundary if in ctx
  },
};
```

**2. `carbon-frontend/src/shell/ErrorBoundary.jsx`** — MODIFY
```
On componentDidCatch:
  - Still calls logger.error() (which POSTs to telemetry in PROD)
  - Correlation ID already generated (existing code) → include in POST body
  - No change to render() output (existing "Something went wrong" UI is fine)
```

**3. `carbon-frontend/src/utils/webVitals.js`** — NEW
```javascript
import { onCLS, onFID, onFCP, onLCP, onTTFB, onINP } from 'web-vitals';

export function reportWebVitals(token) {
  // Only reports in PROD (import.meta.env.PROD)
  const send = ({ name, value, rating }) =>
    apiFetch('telemetry/vitals/', {
      token,
      method: 'POST',
      body: { metric_name: name, value, rating, url: location.pathname, ts: new Date().toISOString() },
    }).catch(() => {});   // fire-and-forget; never throw

  onCLS(send); onFID(send); onFCP(send);
  onLCP(send); onTTFB(send); onINP(send);
}
```

**4. `carbon-frontend/src/main.jsx`** — MODIFY
```
After auth bootstrap completes, call reportWebVitals(accessToken).
Replace console.debug("main.jsx: Rendering root app...") with logger.debug().
```

**5. Migrate existing console.* calls:**
Replace all 56 `console.log/error/warn` instances with `logger.*` equivalents.
Priority: `api/api.js`, `shell/ErrorBoundary.jsx`, `config.js`, `auth/AuthContext.jsx`.

**6. Add `web-vitals` package:**
```bash
npm install web-vitals
```

#### Verification gate
```bash
npm run lint
npx vitest run src/__tests__/logger.test.js
npm run build
# Build bundle must not include `console.log` outside node_modules:
grep -r 'console\.' dist/assets/ | grep -v "node_modules" | wc -l  # → 0
```

---

## Phase NGX-10 — Offline Resilience & Service Worker
**Workers:** frontend-worker
**Prerequisites:** NGX-9 (logger available for SW debug messages)
**Status:** PLANNED
**Estimated effort:** 2 days

### Context
The app is currently a pure online SPA. A network drop causes a blank screen.
`NetworkStatusBanner.jsx` already detects online/offline transitions. This phase
adds a Service Worker that caches static assets (so the shell loads offline) and
draft form persistence (so unsaved data survives unexpected disconnections).

### Architecture

```
Service Worker (Workbox-based)
  Layer 1: Precache — shell HTML + JS/CSS chunks (cache-first on reload)
  Layer 2: Runtime cache — API responses with stale-while-revalidate (60s)
           EXCEPT: streaming endpoints, auth, telemetry (always network)
  Layer 3: Offline fallback — return /offline.html for navigation requests
           that fail with no cache match
```

### New / changed files

**1. `carbon-frontend/src/service-worker.js`** — NEW (Workbox)
```javascript
import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching';
import { registerRoute } from 'workbox-routing';
import { StaleWhileRevalidate, NetworkFirst } from 'workbox-strategies';
import { ExpirationPlugin } from 'workbox-expiration';

cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);   // Vite injects the asset manifest

// API responses: network-first, 60s cache for read-only GET
registerRoute(
  ({ url }) => url.pathname.startsWith('/carbon-api/') && !url.pathname.includes('/stream/'),
  new NetworkFirst({ cacheName: 'api-cache', plugins: [new ExpirationPlugin({ maxEntries: 50, maxAgeSeconds: 60 })] })
);
```

**2. `carbon-frontend/vite.config.js`** — MODIFY
```javascript
import { VitePWA } from 'vite-plugin-pwa';
// Add VitePWA({ strategies: 'injectManifest', srcDir: 'src', filename: 'service-worker.js' })
// Add to devDependencies: vite-plugin-pwa workbox-precaching workbox-routing
//   workbox-strategies workbox-expiration
```

**3. `carbon-frontend/public/offline.html`** — NEW
```
Minimal offline page matching app shell styles (no external CSS/JS).
Message: "You're offline. Carbon will reconnect automatically."
Shows last-known app version and timestamp.
```

**4. `carbon-frontend/src/hooks/useDraftPersistence.js`** — NEW
```
Persists form draft data to localStorage and restores on mount.

useDraftPersistence(formKey, initialValues)

Returns: { values, setValues, clearDraft, hasDraft }

- Autosaves values to localStorage["draft:{formKey}"] on every change
  with 500ms debounce (avoid thrashing on fast typing)
- On mount: checks for saved draft → if found, shows a non-intrusive
  restore banner: "You have an unsaved draft from {timestamp}. [Restore] [Discard]"
- On submit: clears draft
- Integrates with NetworkStatusBanner: pauses autosave when offline
  (offline state already available via useNetworkStatus())
```

**5. Wire useDraftPersistence into high-value forms:**
- `pages/dataschema/tabs/RowEditTab.jsx` — data entry row edits
- `pages/emissions/ReportingPeriodsPage.jsx` — period creation form
- `pages/catalog/tabs/SchemaStructureTab.jsx` — field metadata edits
- `components/DataRowFormDrawer.jsx` — general row form drawer

**6. SW registration in `carbon-frontend/src/main.jsx`:**
```javascript
import { registerSW } from 'virtual:pwa-register';
if (import.meta.env.PROD) {
  registerSW({
    onNeedRefresh() {
      logger.info('New version available — prompt user to reload');
      // Show a bottom toast: "A new version is available. [Reload]"
      // Use NotificationProvider.notify() after auth
    },
    onOfflineReady() {
      logger.info('App is ready for offline use');
    },
  });
}
```

#### Verification gate
```bash
npm install vite-plugin-pwa workbox-precaching workbox-routing workbox-strategies workbox-expiration
npm run lint
npm run build
# Confirm SW generated:
ls dist/sw.js dist/workbox-*.js
# Confirm offline page:
ls dist/offline.html
# Lighthouse PWA audit (manual gate): score ≥ 80
```

---

## SUMMARY TABLE

| Phase | Name | Workers | Prereqs | Days | Status |
|-------|------|---------|---------|------|--------|
| NGX-1 | SSE Progress Streaming | BE + FE | — | 3 | READY |
| NGX-2 | Optimistic CRUD Platform-Wide | FE | — | 2 | READY |
| NGX-3 | Real-Time Event Bus (SSE) | BE + FE | — | 3 | READY |
| NGX-4 | Proactive Notification Panel | BE + FE | NGX-3 | 2.5 | PLANNED |
| NGX-5 | Collaborative Presence | BE + FE | NGX-3 | 2 | PLANNED |
| NGX-6 | Live Data (DQ scores, jobs) | FE | NGX-3 | 1.5 | PLANNED |
| NGX-7 | AI Output Transparency | FE | — | 2 | READY |
| NGX-8 | Skeleton Screens | FE | — | 2 | READY |
| NGX-9 | Frontend Observability | BE + FE | — | 2 | READY |
| NGX-10 | Offline Resilience / SW | FE | NGX-9 | 2 | PLANNED |
| | **Total** | | | **22 days** | |

## DISPATCH ORDER (two-track)

```
Track A (real-time infrastructure):
  NGX-1 (3d) → NGX-3 (3d) → NGX-4 (2.5d) → NGX-5 (2d) → NGX-6 (1.5d)

Track B (UI quality):
  NGX-7 (2d) → NGX-8 (2d) → NGX-9 (2d) → NGX-10 (2d)

NGX-2 (optimistic CRUD, 2d) can run as a short parallel track at any point.

Minimum clock time (all tracks parallel): ~11 days
Sequential minimum: ~22 days
Recommended: start Track A + Track B + NGX-2 simultaneously.
```

## HARD RULES FOR ALL NGX PHASES

1. Every new hook/component follows design-system.md — tokens only, size="small"
   default, all 4 data states (loading/error/empty/loaded).
2. Every new API call uses apiFetch() — never raw fetch() (exception: streaming
   paths that need manual Authorization header injection, following the
   streamJsonPost pattern).
3. Every event published must carry org_unit_id for CBAC filtering; the SSE
   endpoint must NEVER send events for org units the user cannot access.
4. AI output indicators (NGX-7) follow RULE_23 — no implementation leakage in
   labels. Label "AI" not "Pulse". Label "AI generated" not "pipeline output".
5. Presence (NGX-5) is read-only observability — NEVER block or lock. If
   concurrent edit detection is added, it must be advisory only.
6. Service Worker (NGX-10) must NOT cache streaming endpoints, auth endpoints,
   or telemetry endpoints. Cache invalidation must be automatic on new deploy.
7. All phases ship with: npm run lint (0 new errors) + targeted vitest + npm run build.
