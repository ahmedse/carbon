# PULSE — Concrete UX Design (Per-Room Wireframes & Component Specs)

> **Status:** CANONICAL · **Owner:** Product Designer + Master Architect · **Last audited:** 2026-08-30
> **This is the build-level companion to [`PULSE-UX.md`](./PULSE-UX.md).**
> Philosophy and principles live there; **this file tells a Frontend Worker exactly what to build,
> pixel-by-pixel, component-by-component, state-by-state.**
>
> Token values are from `.ai-toolkit/shared/compact-ui.md`. RULE_8 (tokens only), RULE_10 (apiFetch
> + SSE only), RULE_23 (outcome copy, zero engine jargon) apply throughout.

---

## Reading guide

Each section covers one **room** (IA from PULSE-UX §4):

| § | Room | Operator's job |
|---|------|----------------|
| 1 | **Shell frame** | nav spine that holds the other rooms |
| 2 | **Conversation** | ask, get a grounded answer, follow up |
| 3 | **Inspector Drawer** | drill into provenance + data behind an answer |
| 4 | **Notification Panel** | receive proactive insights (the bell) |
| 5 | **Pulse Console** | admin — watch the assistant's own health |
| 6 | **Cross-cutting** | states, motion, a11y, copy voice |
| 7 | **Gap map** | what exists, what needs build, what needs extension |

Each room spec follows this template:

1. **Wireframe** — ASCII + annotated measurements
2. **Component tree** — MUI hierarchy + props
3. **Interaction spec** — state machine, hover/click/stream behaviour
4. **Data states** — loading / empty / error / loaded / uncertain (where applicable)
5. **Token map** — exact spacing/color/typography values
6. **Acceptance test** — the specific behaviour a QA reviewer checks

---

## 1. Shell Frame

### 1.1 Wireframe

```
┌────────────────────────────────────────────────────────────────────────────┐
│ AppBar ─ 48px ─────────────────────────────────────────────────────────────│
│  [☰]  Carbon Logo · breadcrumbs (if depth>1)      [🔔N]  [user avatar ▾]  │
├───────────┬────────────────────────────────────────────────────────────────┤
│ Sidebar   │  Main content area (router outlet)                             │
│  48px     │                                                                │
│  icons    │   ← Room 2 (AIWorkspace) slides in here as a drawer/panel,   │
│  only     │     or as a full-page route depending on viewport              │
│           │                                                                │
│  [≡ nav]  │                                                                │
│           │                                                                │
│           │                                                                │
└───────────┴────────────────────────────────────────────────────────────────┘
```

### 1.2 Notification bell (ambient proactivity thread — Wave A4)

**Location:** AppBar, right cluster, before user avatar. **Exists today:** no. **Needs build.**

```
AppBar right cluster:
  [🔔]  ← NotificationBell   →  shows a Badge when unread_count > 0
  [AV]  ← UserMenu
```

#### NotificationBell component spec

```jsx
// src/shell/NotificationBell.jsx  (new, Wave A4)
<Tooltip title="Insights from the assistant">
  <IconButton size="small" onClick={handleOpen} aria-label="Open insights panel">
    <Badge
      badgeContent={unreadCount}   // 0 → no badge (not a "0" badge)
      max={9}
      color="error"                // theme.palette.error (not hardcoded red)
      overlap="circular"
      sx={{ '& .MuiBadge-badge': { fontSize: '0.5rem', minWidth: 14, height: 14 } }}
    >
      <NotificationsOutlinedIcon sx={{ fontSize: 20 }} />
    </Badge>
  </IconButton>
</Tooltip>
```

Token rules:
- `size="small"` (theme default), `iconButton: { padding: 6 }`
- Badge color = `color="error"` (RULE_8 — no hardcoded hex `#FF0000`)
- `unreadCount === 0` → `badgeContent` omitted, badge invisible — never render `(0)`

---

## 2. Room 1 — The Conversation

### 2.1 Wireframe (full workspace)

```
┌──────────────────────────────────────────────────────────────────────┐
│ AIWorkspaceHeader ─ 40px ────────────────────────────────────────────│
│  [≡] AI  ← wordmark   [contract text, caption, centered]  [Chat|Agent] [✕]│
├──────────────────────────────────────────────────────────────────────┤
│ LEFT panel ─ 220px collapsed/expanded ───┬ RIGHT panel ──────────────│
│                                          │                           │
│  ┌──────────────────────────────────┐    │  ┌────────────────────┐   │
│  │ [+ New Chat]          220px wide │    │  │ AIConversationView │   │
│  ├──────────────────────────────────┤    │  │                    │   │
│  │ Today                            │    │  │  (message stream)  │   │
│  │   ○ South Valley review   [⋯]   │    │  │                    │   │
│  │   ○ Scope 2 breakdown     [⋯]   │    │  │                    │   │
│  ├──────────────────────────────────┤    │  │                    │   │
│  │ Yesterday                        │    │  │                    │   │
│  │   ○ Emission factors Q3   [⋯]   │    │  │                    │   │
│  │   ● Alamein campus       [⋯]   │    │  │ ─────────────────  │   │
│  ├──────────────────────────────────┤    │  │ AIInputBar         │   │
│  │ 7 days ago                       │    │  └────────────────────┘   │
│  │   ○ Annual report draft   [⋯]   │    │                           │
│  └──────────────────────────────────┘    │  ← right panel also hosts │
│                                          │    tabs (Usage/Memory/     │
│  LEFT tabs row ─ 36px ───────────────    │    Learnt/Settings…)      │
│  [💬 Chat] [🔍 Explore] [📦 Tasks] …    │                           │
└──────────────────────────────────────────┴───────────────────────────┘
```

### 2.2 Component tree

```
<AIWorkspace>
  ├── <AIWorkspaceHeader>                         exists · no change needed
  │     mode toggle (Chat | Agent)
  │     safety contract caption
  │     PulseLogo + close
  │
  ├── LEFT PANEL
  │   ├── <SessionListPanel>                      new component (extends existing tab sidebar)
  │   │     [+ New Chat] button
  │   │     grouped sessions: Today / Yesterday / 7 days / Older
  │   │       <SessionItem> × N
  │   │         ● active indicator (primary.main left border, 2px)
  │   │         session title (truncated, body2)
  │   │         [⋯] hover actions menu
  │   │             Rename · Pin · Archive · Delete
  │   │         relative timestamp (caption, text.disabled)
  │   └── LEFT TABS (bottom of left panel)
  │         AIConversationTabs (existing)
  │
  └── RIGHT PANEL
      ├── <AIConversationView>                    exists · needs minor extend
      │     <AIOfflineBanner> (conditional)
      │     <OlderMessagesToggle> (> 14 msgs)
      │     message list (flex column)
      │       <AIMessageBubble> × N
      │     <AIWorkingIndicator> (while streaming)
      │     bottom anchor (auto-scroll target)
      │     <AIInputBar>
      │
      └── SIDE TABS (Usage / Memory / Learnt / Settings / …)
            existing AIUsageTab / AIMemoryTab / …
```

### 2.3 SessionItem — detailed spec

```
SessionItem = <Box role="button" tabIndex={0}>
  left 2px border: active = primary.main, inactive = transparent
  padding: py:0.75 px:1.5 (= 6px 12px)

  LAYOUT (flexRow, gap:1, alignItems:center):
    [icon 16px, color text.secondary]  ← ForumOutlinedIcon
    [title: body2, flex 1, noWrap, overflow ellipsis]
    [timestamp: caption 0.5rem, color text.disabled, shrink 0]
    [⋯ hover menu: IconButton size=small, opacity 0 → 1 on row hover]

  HOVER BG: action.hover
  FOCUS VISIBLE: outline 2px primary.main offset 2px  (a11y RULE_9)

  Hover menu items (MenuList):
    Rename  (EditIcon)
    Pin     (PushPinOutlinedIcon)
    Archive (ArchiveOutlinedIcon)  — never auto-archive
    Delete  (DeleteOutlineIcon, color error.main) → confirm dialog
```

Zero-count group headers (`Archived (0)`) are **never rendered** — controlled by `count > 0` guard.

### 2.4 AIConversationView — message stream

#### Layout

```
<Box sx={{ display:'flex', flexDirection:'column', height:'100%', overflow:'hidden' }}>
  <Box sx={{ flex:1, overflowY:'auto', px:2, py:1.5, display:'flex', flexDirection:'column', gap:1.5 }}>
    [messages]
    <AIWorkingIndicator />   ← shown only while streaming
  </Box>
  <Divider />
  <AIInputBar />
</Box>
```

`gap:1.5` = 12px between message bubbles. `px:2` = 16px side padding.

#### User message bubble

```
alignment:  flex-end (right side)
maxWidth:   88%
bg:         action.hover  (not a colored bubble — clean, flat)
padding:    px:1.25 py:0.625 = 10px 5px
borderRadius: 1 = 8px
typography: body2 (0.6875rem)
```

No avatar, no "You" label, no timestamp inline — timestamp appears on hover only (see hover toolbar).

#### AI message bubble — the beat pattern made visual

```
┌────────────────────────────────────────────────────────────────────────────┐
│ BEAT 1: acknowledge chip (< 100ms, optimistic, before backend response)    │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ [⚡ caption chip]  "Checking South Valley…"                    fades │  │
│  │                    disappears once real stream starts               │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│ BEAT 2: think out loud (while streaming, SSE stage events)                 │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ [● animated dot]  "Reading the last 3 months of South Valley…"      │  │
│  │                    stage text changes as pipeline progresses        │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│ BEAT 3: the answer (streaming tokens, then complete)                        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  Markdown / rich content (MarkdownMessage, CarbonDataGrid etc.)     │  │
│  │                                                                      │  │
│  │  [ⓘ What went into this ▸]  ← provenance affordance, always present │  │
│  │  [  ≈ 92% confident        ]  ← confidence bar (Wave C2, real signal)│  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│ BEAT 4: carry forward (rendered at bottom of message, after answer settles)│
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  Next actions (1–3 chip-links):                                     │  │
│  │  [→ View South Valley page]  [→ Compare with Alamein]  [→ DQ rules] │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│ HOVER TOOLBAR (appears on message hover, above top-right corner)           │
│  [📋 Copy] [👍] [👎] [⋮ menu]                    [timestamp caption]      │
└────────────────────────────────────────────────────────────────────────────┘
```

#### AI bubble — component-level detail

```jsx
// Extensions to AIMessageBubble.jsx for the 4-beat shape:

// Beat 1 — acknowledge chip (optimistic, client-side, ephemeral)
// Shown when: message.status === 'pending' (optimistic insert)
<Chip
  size="small"
  icon={<AutoAwesomeIcon />}
  label={optimisticLabel}          // "On it…" / "Checking {entity}…"
  sx={{ fontSize: '0.6rem', height: 18, borderRadius: 1 }}
/>

// Beat 2 — narrated thinking (extends AIWorkingIndicator)
// Shown when: streaming === true  (SSE stage events)
// stage prop receives OUTCOME-language string from backend (RULE_23)
// e.g. "Reading the last 3 months of readings…"  NOT "S2 retrieve"
<AIWorkingIndicator stage={currentStage} />   // existing component, no change needed

// Beat 3 — answer body (existing MarkdownMessage, CarbonDataGrid etc.)
<MarkdownMessage content={message.content} />

// Provenance affordance (ⓘ) — ALWAYS present on AI messages
<ProvenanceButton sources={message.metadata?.sources} onClick={openInspector} />
// ProvenanceButton: small ghost IconButton (InfoOutlinedIcon, 14px)
//   + "What went into this" tooltip
//   onClick → opens Inspector Drawer (Room 3) scoped to this message

// Confidence bar (Wave C2 — backend provides the real signal)
// Only render when: message.metadata?.confidence_label is present
// confidence_label: 'high' | 'medium' | 'low' | 'uncertain'
<ConfidenceIndicator label={message.metadata?.confidence_label} />

// Beat 4 — next actions (extracted from message.metadata.next_actions)
// next_actions: [{ label: string, href: string }]
// Each href is validated as safe internal route (isSafeInternalRoute)
{nextActions.map(a => (
  <Chip
    key={a.href}
    component={Link}
    to={a.href}
    clickable
    size="small"
    label={a.label}
    icon={<ChevronRightIcon />}
    sx={{ fontSize: '0.65rem', height: 18, borderRadius: 1 }}
  />
))}
```

#### ConfidenceIndicator spec (new, Wave C2b)

```
VISUAL:
  'high'      → LinearProgress value=92, color="success", width 48px, 3px height
                label: "High confidence" (tooltip only — not always-visible text)
  'medium'    → color="warning"
  'low'       → color="error"
  'uncertain' → no bar; instead: italic caption "Best available — some gaps"
                distinct calm styling, NOT an error chip

SIZE: 48px wide × 3px tall, borderRadius 4, inline-flex beside the ⓘ
TOKEN: LinearProgress color prop ("success"/"warning"/"error") — never hardcoded hex
A11Y:  aria-label="Answer confidence: {label}", role="meter",
        aria-valuenow and aria-valuemax set — screen-reader readable
```

#### Hover toolbar

```
Positioned: absolute, top: -16px, right: 0
Trigger:    parent onMouseEnter/onFocus → opacity:1; onMouseLeave/blur → opacity:0
            transition: opacity 0.15s ease

Contents (for AI message, left to right):
  [timestamp caption, text.disabled, mr:auto]
  [ContentCopyIcon]   → copy rich text
  [ThumbUpAltOutlinedIcon / ThumbUpAltIcon (toggled)]
  [ThumbDownAltOutlinedIcon / ThumbDownAltIcon (toggled)]
  [MoreVertIcon]      → menu: Edit feedback · Fork here · Download · Report

All: IconButton size=small (padding:4, fontSize 1.125rem)
No always-on button rows (PULSE-UX §7 law: chrome on hover).
```

### 2.5 AIWorkingIndicator — narrated thinking extension

Existing component takes a `stage` string. The only required change: ensure the `stage` received from
the SSE `stage_event` frames is **outcome-language** (backend responsibility, RULE_23). The component
itself needs no changes — it already renders `stage` as a caption.

SSE frame shape (backend MUST produce this, not the UI):
```json
{ "type": "stage_event", "stage": "Reading the last 3 months of South Valley readings…" }
```
Never: `"stage": "S2 retrieve: episodic query"`. RULE_23 is enforced **at serialization**, not in the UI.

### 2.6 AIInputBar — state contract

```
STATES:
  idle        → TextField placeholder "Ask a question or give directions…"
                Enter = send, Shift+Enter = newline
                / → SlashCommandMenu (picker popover above bar)
                # → MentionMenu (table / rule / field / module)

  streaming   → TextField disabled; [⏹ Stop] button replaces [▶ Send]
                [⏹] calls stopGeneration(), which resolves to retry state

  retry       → [⟳ Retry] button visible; placeholder "Retry or ask something new"

  needs_input → placeholder "Respond to the question above…"
                yellow left border on TextField (warning.main, 2px)

  offline     → TextField disabled; AIOfflineBanner shows above bar

SEND BUTTON:
  Contained, primary, size=small (padding '3px 8px', minHeight 24px)
  Disabled when: input is empty OR streaming
  Icon: SendIcon (18px)

STOP BUTTON (streaming only):
  Outlined, color=error, size=small
  Icon: StopCircleIcon (18px)

QUEUED MESSAGE (streaming + user types):
  Input is NOT disabled in 'working' state — user can queue.
  Placeholder changes to "AI is thinking… (Enter to queue)"
  The queued message is held client-side; sent when stream completes.
```

### 2.7 Uncertain / honest-uncertainty state

When `message.metadata.honest_uncertainty === true`:

```
The message renders with:
  - A distinct calm style (no error color):
      sx={{ borderLeft: '2px solid', borderColor: 'warning.light', pl: 1.5 }}
  - A caption: "Best available — some gaps remain" (outcome-shaped, RULE_23)
    icon: HelpOutlineIcon (14px, color warning.main)
  - The answer body still renders (what Pulse knows)
  - The confidence bar shows 'uncertain' state (italic, no fill bar)

This is NOT an error chip. It is NOT styled with error.main.
It says: "here's my honest read, and here's what I'm unsure about."
Never suppress this state or mask it as confidence="high".
```

### 2.8 Data states — AIConversationView

| State | Rendered element | Key behavior |
|-------|-----------------|--------------|
| **loading** | Skeleton (3 rows, varying widths: 90% / 60% / 75%) | Rest of workspace remains interactive |
| **empty** | AIEmptyState (existing) | "Ask a question to get started" + suggestion chips |
| **streaming** | Last message grows token-by-token | Stop button in input bar; scroll locks to bottom |
| **error** | Alert (severity="error") + Retry button | Human sentence only, no stack trace |
| **loaded** | Full message list | OlderMessagesToggle if > 14 msgs |
| **uncertain** | Answer with honest-uncertainty styling | §2.7 above |

---

## 3. Room 2 — The Inspector Drawer

### 3.1 What it is

A **right-side Drawer** (ADR-0019) that opens when the user clicks the provenance affordance (ⓘ) on
any AI message. It shows exactly what the assistant used to construct that answer. Closing it returns
focus to the conversation precisely where it was.

### 3.2 Wireframe

```
┌──────────────────────────────────┬─────────────────────────────────┐
│  Conversation (Room 1)           │ Inspector Drawer ─ 400px wide   │
│  (dimmed slightly while open)    │ ─────────────────────────────── │
│                                  │ [← close]  Sources for message  │
│  [ⓘ hover]  ────────────────────▶│                                  │
│                                  │ ┌ Tabs ─ 36px ────────────────┐ │
│                                  │ │ [Sources] [Data] [Reasoning] │ │
│                                  │ └─────────────────────────────┘ │
│                                  │                                  │
│                                  │ SOURCES TAB                      │
│                                  │  ● South Valley 2024-Q3 records  │
│                                  │    412 readings · 2026-07-15 ↑  │
│                                  │  ● EF Registry v2.1              │
│                                  │    emission factor: 0.82 kg CO₂e │
│                                  │  ● Calculation method: GHG Scope2│
│                                  │                                  │
│                                  │ DATA TAB                         │
│                                  │  [CarbonDataGrid — compact]      │
│                                  │  shows the actual records used   │
│                                  │                                  │
│                                  │ REASONING TAB (Wave D3)         │
│                                  │  narrated trace in outcome lang  │
└──────────────────────────────────┴─────────────────────────────────┘
```

### 3.3 Component tree

```
<InspectorDrawer>                       new, built on MUI Drawer (variant="persistent"/"temporary")
  <DrawerHeader>
    <IconButton onClick={close}>        ← ChevronRightIcon (close)
    <Typography variant="h6">          "Sources for this answer" (outcome copy, RULE_23)
    <IconButton>                        ← OpenInNewIcon (open full-page, optional future)

  <Tabs value={tab} onChange={setTab} sx={{ minHeight:36, borderBottom:1, borderColor:'divider' }}>
    <Tab label="Sources" value="sources"   sx={{ minHeight:36, py:'6px', fontSize:'0.8125rem' }} />
    <Tab label="Data"    value="data"      sx={{ minHeight:36, py:'6px', fontSize:'0.8125rem' }} />
    <Tab label="Trace"   value="trace"     sx={{ minHeight:36, py:'6px', fontSize:'0.8125rem' }} />

  <TabPanel value="sources">
    <SourceList sources={provenance.sources} />
    // Each SourceItem:
    //   icon (InsertDriveFileOutlinedIcon / StorageIcon / by type)
    //   title: body2, bold
    //   meta: caption, text.secondary ("412 readings · refreshed 2026-07-15")
    //   NO internal record ids or engine metadata — outcome fields only (RULE_23)

  <TabPanel value="data">
    <CarbonDataGrid                     // existing component, density="compact"
      rows={provenance.data_rows}
      columns={provenance.data_columns}
      getRowId={(row) => row.id ?? row._idx}
      density="compact"
      autoHeight
      hideFooterPagination={rows.length < 25}
    />
    // Empty: "No row-level data for this answer" (honest, not an error)

  <TabPanel value="trace">             // Wave D3 — skeleton until then
    <ReasoningTrace steps={provenance.reasoning_steps} />
    // Each step: icon + outcome-language sentence + duration caption
    // No engine internals (RULE_23). E.g.: "Read 412 South Valley readings (320ms)"
```

### 3.4 Drawer sizing & animation

```
width:       400px (desktop); 100vw on mobile (< sm breakpoint)
anchor:      "right"
variant:     "temporary" on mobile, "persistent" on desktop
backdrop:    dim main content (backdrop=true on mobile; main gets filter:brightness(0.96) on desktop)
slide:       translateX(0) ← ease-out 200ms (MUI default, respects prefers-reduced-motion)
z-index:     theme.zIndex.drawer (1200)

On close:
  focus returns to the [ⓘ] button that opened it (focus management, a11y RULE_9)
```

### 3.5 Data states — Inspector

| State | Behavior |
|-------|----------|
| **loading** | Skeleton list (3 source rows, varying widths) in Sources tab |
| **empty sources** | "No source detail available for this answer" — calm, not an error |
| **empty data** | "No row-level data for this answer" |
| **error** | "Couldn't load sources" + Retry icon button |
| **loaded** | Source list + data grid + (stub) trace |

---

## 4. Room 3 — The Notification Panel (Proactivity Bell)

### 4.1 What it is

The ambient thread where the coworker speaks **first**. It surfaces `KgProactiveInsight` rows
delivered from the backend via SSE (Wave A3). The bell lives in the AppBar; the panel opens as a
Popover or small Drawer.

### 4.2 Wireframe

```
AppBar                                   ↓ open on bell click
                                   ┌────────────────────────────────────┐
  [🔔 3]  ←  NotificationBell      │ Notification Panel ─ 360px wide   │
                                   │  ─────────────────────────────────│
                                   │  "Insights from the assistant"    │
                                   │  [Mark all read]  [⚙ settings]    │
                                   ├───────────────────────────────────┤
                                   │ 🔴 High   South Valley anomaly     │
                                   │           Emissions 18% above...  │
                                   │           3 min ago · [→ View]    │
                                   │                                    │
                                   │ 🟡 Med    Scope 2 factor updated  │
                                   │           EF for grid electricity │
                                   │           changed — review now.   │
                                   │           1 hr ago · [→ Review]   │
                                   │                                    │
                                   │ ─────────── earlier ───────────── │
                                   │ ✓ read  Alamein monthly ready     │
                                   │          just now · dismissed     │
                                   │                                    │
                                   │ [Load older insights]              │
                                   └────────────────────────────────────┘
                                   (EMPTY STATE shown when 0 insights:)
                                   ┌────────────────────────────────────┐
                                   │  No insights yet.                  │
                                   │  The assistant reviews your data   │
                                   │  nightly and will let you know     │
                                   │  if anything needs attention.      │
                                   └────────────────────────────────────┘
```

### 4.3 Component tree

```
<NotificationBell>                           new, Wave A4
  <IconButton aria-label="Open insights">
    <Badge badgeContent={unreadCount} max={9} color="error">
      <NotificationsOutlinedIcon />

<NotificationPanel>                          new, Wave A4
  MUI Popover (anchorEl = bell button)
  width: 360px, maxHeight: 480px, overflowY: auto
  Paper: variant="outlined", borderRadius: 2, boxShadow: theme.shadows[8]

  <PanelHeader>
    <Typography variant="subtitle2">Insights from the assistant</Typography>
    <Button size="small" onClick={markAllRead}>Mark all read</Button>

  <Divider />

  {insights.length === 0 && <InsightEmptyState />}

  {insights.map(insight => (
    <InsightRow key={insight.id} insight={insight} />
  ))}
```

### 4.4 InsightRow spec

```jsx
<InsightRow>
  LAYOUT: flexRow, gap:1, py:1, px:1.5, alignItems:'flex-start'
  BG:     unread → action.selected; read → transparent
  HOVER:  action.hover
  BORDER: left 3px solid severityColor (token, not hex — see below)

  LEFT: severity dot
    <Box sx={{
      width: 8, height: 8, borderRadius: '50%', mt: 0.75, flexShrink: 0,
      bgcolor: severityToken    // 'error.main' | 'warning.main' | 'info.main'
    }} />
    + aria-label="Severity: {label}" on the row (a11y — not color-only: RULE_9)

  CENTER: flex:1
    <Typography variant="body2" fontWeight={unread ? 600 : 400}>{insight.title}</Typography>
    <Typography variant="caption" color="text.secondary" noWrap>{insight.narrative}</Typography>
    <Typography variant="caption" color="text.disabled">{relativeTime} · {dispositionLabel}</Typography>

  RIGHT:
    {insight.recommended_actions[0] && (
      <Chip
        component={Link}
        to={safeHref}
        clickable size="small"
        label={insight.recommended_actions[0].label}
        icon={<ChevronRightIcon />}
        sx={{ fontSize: '0.65rem', height: 18 }}
      />
    )}
    <IconButton
      size="small"
      onClick={() => dismiss(insight.id)}
      aria-label="Dismiss insight"
      sx={{ opacity: 0, '.InsightRow:hover &': { opacity: 1 } }}  // hover-only
    >
      <CloseIcon fontSize="small" />
    </IconButton>
```

Severity token map (RULE_8 — no hardcoded hex):

| severity value | border + dot token | label (a11y) |
|---|---|---|
| `high` | `error.main` | "High priority" |
| `medium` | `warning.main` | "Medium priority" |
| `low` | `info.main` | "Informational" |

### 4.5 SSE hook — `useInsightStream`

```js
// src/hooks/useInsightStream.js   (new, Wave A4)
// Subscribes to GET /carbon-api/ai/insights/stream/ via apiFetch + ReadableStream.
// JWT-refresh aware (apiFetch handles token rotation).
// On message: dispatch to local state → unread count badge updates live.
// On error: retry with exponential backoff (max 3, then show an inline banner).
// On unmount: abort the fetch.
//
// Never: setInterval polling.   (PULSE-UX §9 law)
```

### 4.6 Data states — Notification Panel

| State | Rendered element |
|-------|-----------------|
| **loading** | 3 skeleton rows (InsightRow shape) |
| **empty** | InsightEmptyState: icon + 2-line explanation + "Ask a question to get started" CTA |
| **error** | "Couldn't load insights" Alert + Retry |
| **loaded** | InsightRow list; unread first |
| **SSE reconnecting** | Small "Reconnecting…" caption at top (not a modal, not blocking) |

---

## 5. Room 4 — The Pulse Console (Admin)

### 5.1 What it is

The only place where the assistant's internal life is visible to the user — deliberately separate,
deliberate destination. Also the only room where some technical detail (skill status, cost, model)
is shown — because the audience is the Admin, not the Operator.

### 5.2 Wireframe

```
┌──────────────────────────────────────────────────────────────────────┐
│ PULSE CONSOLE ── right panel of AIWorkspace (selected via sidebar tab)│
│                                                                      │
│  ┌─ Tabs 36px ────────────────────────────────────────────────────┐  │
│  │ [📊 Usage]  [🧠 Memory]  [🎓 Learning]  [🔗 Graph]  [⚙ Settings]│  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  USAGE TAB                                                           │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Today's calls: 47  |  Tokens: 128k  |  Cost: $0.32           │  │
│  │  ─────────────────────────────────────────────────────────    │  │
│  │  [CarbonDataGrid — call log, compact, last 50 rows]           │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  LEARNING TAB (Wave B3 — makes G1 visible)                          │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Skill pipeline                                                │  │
│  │                                                                │  │
│  │  Drafted  ──→  Under review  ──→  Promoted  ──→  In use       │  │
│  │     12              3               5              5           │  │
│  │                                                                │  │
│  │  [CarbonDataGrid — skill rows, compact]                       │  │
│  │  Columns: name | status | usage_count | success_rate | age    │  │
│  │  Click row → view admission log (Inspector Drawer pattern)    │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  MEMORY TAB                                                          │
│  (existing AIMemoryTab — no change)                                  │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.3 Learning tab pipeline display (Wave B3 — new)

```jsx
<SkillPipelineStats>
  LAYOUT: flexRow, gap:3, mb:2, alignItems:'center'
  EACH STAGE:
    <Box sx={{ textAlign:'center' }}>
      <Typography variant="h4" fontWeight={700}>{count}</Typography>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
    </Box>
  ARROW: Typography variant="caption" color="text.disabled" sx={{ mt:1 }}>→</Typography>

LABELS (outcome-shaped, not engine jargon):
  "Drafted" (pending gate) · "Under review" (gate running) · "Promoted" · "In use"
  Never: "gate_status=pending" · "instance_promoted" · "skills registry"
  The field names exist in the API; the *labels* shown to the admin are outcome-shaped.

COUNTS: from /carbon-api/ai/ops/skills/ (existing ops_api.py endpoint)
        Real counts only — never mock data, never stale.
```

### 5.4 Token map — Console tabs

```
Tab bar:        minHeight:36, fontSize:'0.8125rem'
Stat numbers:   variant="h4" (approximated by theme: 1rem at compact scale)
Stat labels:    caption (0.625rem), color text.secondary
DataGrid:       density="compact", rowHeight:36, columnHeaderHeight:32
Empty state:    caption, centered, color text.disabled, honest message
```

---

## 6. Cross-cutting specs

### 6.1 Motion contract (respects `prefers-reduced-motion`)

```css
/* Drawer slide */
.MuiDrawer-paper {
  transition: transform 200ms ease-out;
}
/* Notification settle */
.InsightRow--entering {
  animation: settle 220ms ease-out;
}
@keyframes settle {
  from { opacity: 0; transform: translateY(-6px); }
  to   { opacity: 1; transform: translateY(0); }
}
/* Reduce: */
@media (prefers-reduced-motion: reduce) {
  .MuiDrawer-paper { transition: none; }
  .InsightRow--entering { animation: none; }
}
```

Rules:
- Motion **clarifies causality**: the Inspector slides from the ⓘ icon, not from thin air.
- Insight row settles *into* the panel — settles, never bounces.
- Streaming tokens appear in-place; no layout shift.
- Never animate for decoration alone.

### 6.2 Accessibility (WCAG AA baseline)

| Concern | Spec |
|---------|------|
| Focus management | Drawer open → focus moves to DrawerHeader close button; Drawer close → focus returns to ⓘ opener |
| Streamed answer | `aria-live="polite"` on the message container; announce completion, not every token |
| Notification badge | `aria-label="Open insights, {N} unread"` on the bell; badge count announced on change |
| Severity | Carries icon + text label, never color alone (see InsightRow §4.4) |
| Confidence bar | `role="meter"`, `aria-valuenow`, `aria-valuemax`, `aria-label` (§2.4) |
| Hover toolbars | All toolbar buttons keyboard-reachable via Tab when message has focus; visible focus ring |
| Consent modals | `role="dialog"`, `aria-labelledby`, focus trapped until dismissed |
| Min touch target | 44 × 44px for all primary actions (IconButton size=small = 32px → wrap in 44px Box if needed) |

### 6.3 Copy voice rules (every string in every room)

| Rule | Example GOOD | Example BAD |
|------|-------------|-------------|
| Outcome, not mechanism | "Reading your South Valley records…" | "S2 retrieve: vector query" |
| Active, plain | "Insights from the assistant" | "KgProactiveInsight delivery" |
| Honest empty | "No insights yet — the assistant reviews your data nightly" | "0 items" |
| Humane error | "Couldn't load sources — try again" | "HTTP 502: upstream failure" |
| Confident uncertainty | "Best available — some gaps remain" | "low_confidence=True" |
| No cute filler | — | "Oops! Something went sideways 🙈" (enterprise context) |

All strings pass a RULE_23 scan before merge: grep the diff for `pulse|engine|salience|witness|S[0-9]|retrieve|trajectory|ledger` — any hit = rejected.

### 6.4 Layout shift prevention

```
Messages: reserve 1.5rem min-height for streaming messages before first token arrives
           → avoids the stream area collapsing then re-expanding
Skeletons: match the shape of the loaded content (same height/width) — no pop-in
DataGrid:  always set autoHeight or a fixed height — never let it paint at 0 then jump
Images:    aspect-ratio or explicit dimensions — no layout shift on image load
```

### 6.5 Perceived performance checklist

| Interaction | Target | Mechanism |
|-------------|--------|-----------|
| Send message → acknowledge | < 100ms | Optimistic message insert (local state before API) |
| First token appears | < 1s | SSE stream; streaming state set immediately on request |
| Inspector open | < 200ms | Drawer slide; data loads inside it (skeleton first) |
| Notification settle | < 250ms | SSE push → local state update → settle animation |
| Session switch | < 150ms | Local cache-first; refetch in background |

---

## 7. Gap map — what exists vs. what needs building

| Component / behaviour | Status | Wave | Notes |
|-----------------------|--------|------|-------|
| `AIWorkspaceHeader` | ✅ exists | — | Chat/Agent toggle, safety contract, PulseLogo |
| `AIConversationView` | ✅ exists | — | Needs Beat 1/3/4 additions (optimistic chip, provenance, next-actions) |
| `AIMessageBubble` | ✅ exists | — | Needs `ProvenanceButton`, `ConfidenceIndicator`, `NextActionsRow` additions |
| `AIWorkingIndicator` | ✅ exists | — | Already takes `stage` prop — no change; backend must send outcome-language stages |
| `AIInputBar` | ✅ exists | — | Slash commands, mentions, stop/retry already there |
| `AIEmptyState` | ✅ exists | — | No change |
| `MarkdownMessage` | ✅ exists (robust Mermaid) | — | No change |
| `SessionListPanel` | ⚠️ partial | D? | Conversation tabs exist; grouped-by-time session list with hover actions needs build |
| `NotificationBell` | ❌ missing | A4 | New; in AppBar |
| `NotificationPanel` + `InsightRow` | ❌ missing | A4 | New; hooks into A3 SSE endpoint |
| `useInsightStream` | ❌ missing | A4 | New SSE hook; no polling |
| `ProvenanceButton` | ❌ missing | D3 | New; tiny ⓘ on AI messages; opens Inspector |
| `ConfidenceIndicator` | ❌ missing | C2b | New; real signal from backend (C2a adds the field) |
| `NextActionsRow` | ❌ missing | A4 | New; chip-links at bottom of AI message Beat 4 |
| `InspectorDrawer` | ⚠️ partial | D3 | `InspectorTabRegistry` + `tabs/` exist; needs Sources/Data/Trace tabs and open-from-provenance wiring |
| `SkillPipelineStats` (Learning tab) | ❌ missing | B3 | New; inside existing `AILearntTab.jsx` |
| `ReasoningTrace` | ❌ missing | D3 | New inside Inspector "Trace" tab |
| Honest-uncertainty styling | ❌ missing | C2b | Extension to `AIMessageBubble` |
| `aria-live` on stream | ⚠️ unknown | A4 | Needs audit of `AIConversationView` scroll anchor |
| Skeleton screens (replace spinners) | ❌ missing | D4 | `Skeleton` components for message list, session list, panel |

**Build order follows the roadmap:** A → B → C → D. The gap-map rows marked A4 are the minimum
viable "feels alive" milestone. C2b and D3 unlock the trust-transparency layer. D4 is the final polish.

---

## 8. Quick-reference token table (all rooms)

| Element | Token / value | Source |
|---------|---------------|--------|
| Header height | `minHeight: 40`, `py: 0.75`, `px: 1.5` | compact-ui |
| Tab bar height | `minHeight: 36` | compact-ui |
| Body text | `variant="body2"` (0.6875rem) | compact-ui |
| Caption | `variant="caption"` (0.625rem) | compact-ui |
| Small chip | `height: 18, fontSize: '0.65rem', borderRadius: 1` | compact-ui |
| Button padding | `padding: '3px 8px'`, `minHeight: 24` | compact-ui |
| Message gap | `gap: 1.5` (12px) | compact-ui spacing |
| Message pad | `px: 2, py: 1.5` (16px 12px) | compact-ui spacing |
| Divider | `borderColor: 'divider'` | theme |
| AI bubble bg | none (transparent) | design §2.4 |
| User bubble bg | `bgcolor: 'action.hover'` | design §2.4 |
| Active session | `borderLeft: '2px solid'`, `borderColor: 'primary.main'` | design §2.3 |
| High severity | `bgcolor: 'error.main'` | design §4.4 |
| Medium severity | `bgcolor: 'warning.main'` | design §4.4 |
| Uncertain border | `borderLeft: '2px solid'`, `borderColor: 'warning.light'` | design §2.7 |
| DataGrid density | `density="compact"`, `rowHeight: 36`, `headerHeight: 32` | compact-ui |
| Drawer width | `400px` (desktop), `100vw` (< sm) | design §3.4 |
| Panel width | `360px` (notifications) | design §4.2 |
