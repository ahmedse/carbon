# Design — Unified Centralized Notes + 1-Level Comments, Right-Side Multi-Tab Drawer

> **Status:** ✅ **Phases 1–3 IMPLEMENTED & GREEN (2026-08-27)** — backend 29 notes tests + full catalog 156 passed; frontend 901 tests passed, lint clean, live E2E verified (rail → panel → composer → lazy comments → reactions → governance audit events). Round 2: rail badge removed; composer disabled + hint on global (no-context) view. Phase 3 (entity-context wiring on DETAIL pages) DONE — all 14 detail pages migrated to the **Contextual Inspector Drawer** (ADR-0019) with context-driven tabs (`src/inspector/tabs/`). Phase 4 (final QA) pending.
> **Placement decision (per user feedback, 2026-08-27):** drawer is docked at the **right edge of the content area** — rendered inside the editor pane (`Allotment` editor view), so **Pulse (copilot) stays the outermost right pane** when open: `Content | NotesDrawer | Pulse`. Multi-tab container ships with **one tab (Notes) for now**; more tabs (governance history, …) plug in later. Compact sizing per feedback: rail 32px, min drawer 240px / default 340px, small fonts/icons, dense rows.
> **Date:** 2026-08-27 · **Author:** Master Architect
> **Scope:** Carbon Data Trust Platform (Django+DRF backend · React 19 + MUI v7 + Vite 6 frontend)

---

## 1. The request, abstracted

> "A notes system with **1-level commenting** (notes have comments; comments have no replies),
> **unified & centralized** (one model, one place). Frontend: a **multi-tab drawer**,
> **default collapsed** on the **right of the content area**, present on **every page**
> (in the master layout). **Resizable** (to a limit), **pin/collapse**, **multi-tab** where the
> **first tab is fixed = Notes**. Notes list: **newest at top**, **older collapsed as accordion**.
> Each shows **user, date, time, and small feedback (reactions)** on notes *and* comments.
> **Lazy loading**: comments load lazily when a page/entity loads — newest thread first."

This is Layer B of the earlier design (`docs/DESIGN-LOCK-REASON-AND-NOTES.md`) **elevated from
"tab on detail pages" to a platform-wide drawer**, plus two new mechanics the earlier doc only
mentioned: **1-level comments** and **reactions**, plus a **lazy-load contract**.

---

## 2. Principles (what "enterprise" means here — reuse the existing backbone)

1. **One model, one API, one drawer.** No per-page notes tables. Polymorphic
   `entity_type` + `entity_id` (the Collibra/ServiceNow pattern from the earlier research).
2. **Comments are a flat 1-level thread** (Jira-comment-style, no nesting). Nesting adds
   moderation + rendering complexity with ~0 value for stewardship notes.
3. **Reactions are small, togglable, one-per-user-per-target** (Slack-lite: 👍 ❓ ⭐).
   Never free-text feedback (that's what comments are for).
4. **Lazy by contract.** Notes list loads on drawer open; comments load **only** when a note
   is expanded. The API must make this cheap (counts in list, comments separate endpoint).
5. **Audited, append-only.** Note/comment edits emit `GovernanceEvent` (Layer A backbone already
   exists: `emit_governance_event`). Never silently overwrite; never cascade-delete with entity.
6. **Respect existing shell conventions.** Allotment-style resizing, localStorage persistence,
   RTL mirroring, `apiFetch` JWT wrapper, compact-ui density, i18n strings.
7. **Progressive adoption.** Pages opt in via a tiny context hook. Pages that don't opt in
   still get the drawer (global view) — zero forced migrations.

---

## 3. Backend design

### 3.1 Models (`backend/catalog/models.py` — one migration)

```python
class Note(models.Model):                       # polymorphic, centralized
    entity_type = models.CharField(max_length=40)   # 'org_unit' | 'module' | 'table' | 'user' | 'dq_rule' ...
    entity_id = models.PositiveIntegerField()       # plain int → no cascade (post-mortem safety, F5)
    body = models.TextField()
    author = models.ForeignKey(User, null=True, blank=True,
                               on_delete=models.SET_NULL, related_name='notes')  # F4
    visibility = models.CharField(max_length=10,
        choices=[('public', 'Public'), ('internal', 'Internal')], default='public')  # F11
    is_active = models.BooleanField(default=True)   # soft delete — keep context
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['entity_type', 'entity_id', '-created_at'])]
        ordering = ['-created_at']                  # newest first (the list contract)

class NoteComment(models.Model):                # 1-level only — FK to Note, NO parent
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='comments')
    body = models.TextField()
    author = models.ForeignKey(User, null=True, blank=True,
                               on_delete=models.SET_NULL, related_name='note_comments')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']               # flat chronological thread

class NoteReaction(models.Model):               # small feedback, one per user per target
    REACTIONS = [('like', '👍 Like'), ('question', '❓ Question'), ('star', '⭐ Important')]
    note = models.ForeignKey(Note, null=True, blank=True, on_delete=models.CASCADE,
                             related_name='reactions')
    comment = models.ForeignKey(NoteComment, null=True, blank=True, on_delete=models.CASCADE,
                                related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='note_reactions')
    reaction = models.CharField(max_length=10, choices=REACTIONS)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # exactly one target (note XOR comment) — enforce in clean()
            models.UniqueConstraint(fields=['user', 'note', 'reaction'],
                                    condition=Q(note__isnull=False), name='uniq_user_note_reaction'),
            models.UniqueConstraint(fields=['user', 'comment', 'reaction'],
                                    condition=Q(comment__isnull=False), name='uniq_user_comment_reaction'),
        ]
```

**Audit hook (already exists, zero new infra):** Note/comment `create`/`update`/`delete`
→ `emit_governance_event('note', id, 'create', ..., user=request.user)`. Deletes are **soft**
(`is_active=False`) so the drawer can show "removed by author" instead of a hole.

### 3.2 API surface (`backend/catalog/urls.py` — router)

| Endpoint | Method | Purpose | Lazy? |
|---|---|---|---|
| `/carbon-api/catalog/notes/?entity_type=org_unit&entity_id=3` | GET | Paginated list, **newest first**; each item carries `comments_count`, `reaction_counts`, `my_reaction` — **no comment bodies** | list loads on drawer open |
| `/carbon-api/catalog/notes/` | POST | Create note `{entity_type, entity_id, body, visibility}` | |
| `/carbon-api/catalog/notes/{id}/` | GET/PATCH/DELETE | Detail / edit (author or admin) / soft-delete | |
| `/carbon-api/catalog/notes/{id}/comments/?page=1` | GET | **Lazy**: comment thread for one note, chronological, paginated | loads on note expand |
| `/carbon-api/catalog/notes/{id}/comments/` | POST | Add 1-level comment `{body}` | |
| `/carbon-api/catalog/notes/{id}/reactions/` | POST | Toggle reaction `{reaction}` on a **note** → returns new counts | |
| `/carbon-api/catalog/notes/comments/{id}/reactions/` | POST | Toggle reaction on a **comment** → returns new counts | |

**List serializer shape (compact — the drawer contract):**

```json
{
  "id": 42, "body": "Auditor asked for FY26 evidence…",
  "author": {"id": 3, "username": "ahmed", "full_name": "Ahmed …"},
  "visibility": "public",
  "created_at": "2026-08-27T10:15:00+02:00",
  "updated_at": null,
  "comments_count": 4,
  "reaction_counts": {"like": 3, "question": 1, "star": 0},
  "my_reaction": "like",          // null if none
  "can_edit": true                // author or admin
}
```

**Comment serializer:** `{id, body, author, created_at, updated_at, reaction_counts, my_reaction, can_edit}`.

**Permissions:** read = authenticated (internal visibility filtered to author+admin);
create/comment = authenticated; edit/delete = author or admin. **Edit/delete of comments allowed
only for author or admin** — never public deletion of others' remarks (Jira rule).
**Reactions:** authenticated, toggle = one request (POST again removes).

**Lazy/performance:** `comments_count` via `annotate(Count('comments', filter=Q(is_active=True)))`
— no N+1. List page size 20. Comments page size 50 (threads are short; single fetch in practice).

### 3.3 Entity label resolution (frontend-driven, NOT backend lookup)

The drawer must show "Notes — كلية الطب". Two options:

- **A (recommended): frontend context.** Pages already hold the entity object; they pass
  `{entityType, entityId, label}` to a shared context (exactly how `AIDomainEntryPoints` gets
  `table`/`module` today). Zero backend lookups, works offline-first, handles renamed entities.
- **B: backend label registry.** `ENTITY_REGISTRY = {'org_unit': OrgUnit, ...}` mapping
  `entity_type` → model + `name` field. Useful for the global view and server-rendered surfaces,
  but adds coupling. **Add later if the global view needs it.**

---

## 4. Frontend design

### 4.1 Where it lives — the master layout (`shell/Shell.jsx`)

Current layout: `ActivityBar | SidebarDrawer | Allotment[ EditorArea | CopilotPane ] | StatusBar`.

Add a **`NotesDrawer` docked INSIDE the editor pane** — at the right edge of the content area,
so it is **not** pushed beyond the Pulse (copilot) panel:

```
ActivityBar | Sidebar | Allotment[ Content | NotesDrawer(rail ⇄ panel) | Copilot ]
```

(`renderContentPane()` in Shell wraps `EditorArea` + `NotesDrawer` in a flex row; the copilot
pane remains the outermost right view. In RTL the flex order mirrors it to the content's left edge.)

- **Collapsed (default)** = slim **rail** (32px) on the content's right edge — **matches the
  left-menu pattern**: a single arrow button (`ChevronLeft`/`ChevronRight` by RTL) with a
  tooltip ("Notes") that opens the drawer; tabs live inside the expanded panel (Notes is the
  first tab). **No count badge on the arrow** (per user mandate — the rail is a pure toggle,
  like the sidebar collapse arrow).
- **Expanded** = **resizable panel** (default 340px, min `min(240, 35%vw)`, max ~50% viewport —
  same clamp pattern as the sidebar `drawerWidthClamped`). Resize is **direct manipulation**:
  dragging the edge LEFT widens the drawer (content gets smaller) and RIGHT narrows it (LTR;
  mirrored in RTL).
- **Pin (fix)**: pushpin toggle → pinned stays open across navigation; unpinned auto-collapses
  to the rail when the context entity changes (feels like a "peek").
- **Resize handle**: identical mouse-move pattern to the sidebar handle
  (`onMouseDown` → `mousemove` → clamp → persist). Width persisted in
  `localStorage['carbon-notes-width']`; open/tab in `carbon-notes-open` / `carbon-notes-tab`.
- **RTL:** anchor flips (right↔left) using the existing `isRtl` from `useLanguage()`
  (the Shell already does this for sidebar + copilot).
- **Multi-tab:** the panel hosts a `Tabs` bar; **Notes is the single tab for now** (fixed, first).
  Future tabs (governance history, activity, AI) are added to the registry without layout changes.

**Component tree:**

```
NotesProvider (context)                        — new, wraps Shell content
└─ NotesDrawer
   ├─ NotesRail            (collapsed: arrow button + tooltip; opens drawer — NO badge)
   └─ NotesPanel           (expanded)
      ├─ TabBar            (Tabs: [Notes(fixed)] + future tabs; closeable except Notes)
      ├─ NotesTab          (the fixed first tab)
      │  ├─ ContextHeader  (entity chip — "All notes" on global view)
      │  ├─ NoteComposer   (body + submit — visibility is IMPLICIT, no picker;
      │  │                  disabled + hint "Open a record to attach a note" on the
      │  │                  global view where there is no entity context)
      │  ├─ NoteList       (newest first, page 1; "Load more"; compact cards)
      │  │  └─ NoteCard    (author, time, body, reactions, comments toggle)
      │  │     └─ CommentThread (lazy: skeleton → flat thread + add-comment)
      │  └─ OlderAccordion ("Show N older notes" — the requested accordion)
      └─ FutureTabSlot     (registry-driven — Activity, AI, … later)

**Compact sizing** (whole drawer): rail 32px / arrow 15px; panel header ~22px; tab bar 24px
(0.6rem); avatars 14–16px; body text 0.68rem; reactions 0.6rem with 0.72em emoji icons;
comment avatars 14px / body 0.62rem; note card padding 0.5.

**Visibility is implicit**: the composer has **no visibility picker**. The server derives it
from the author's scope — admin → `internal`, everyone else → `public` — and the client can
never set or patch it (serializer `read_only_fields`). The card still shows an "internal"
badge for admin-authored notes (server-derived).
```

### 4.2 The Notes tab — mapping the user's exact mental model

| User requirement | Implementation |
|---|---|
| Newest notes at top | Backend `ordering = ['-created_at']`; UI renders page-1 list top-down. "Load more" appends older. |
| Older collapsed as accordion | After the first page of expanded cards (or a cap, e.g. first 5), the remainder live inside a single MUI `<Accordion>` — "Show N older notes". Matches the "old collapsed" ask without per-card accordions. |
| User, date, time | Avatar initials + full name + absolute `created_at` (tooltip ISO) + relative time for <24h. Compact-ui density. |
| Small feedback on notes AND comments | Reaction row: tiny icon buttons (`👍 3 ❓ 1 ⭐ 0`), one tap toggles (`my_reaction` highlighted), optimistic update. Same component for note and comment. |
| Comments lazy, newest thread first | Comments **not** in list payload. On expand → `GET …/comments/` once, cached in context state (per note id). Newest thread: the thread shows newest comment first in a "Latest" mini-section, full chronological below — or simply chronological with the composer on top. **Decision: chronological flat thread + composer on top** (enterprise readability); "newest first" applies to the note list, not the thread. |
| When loading a page/entity → lazy | `useEffect` in `NotesProvider`: on context change, if drawer has never fetched for this entity, fetch list (page 1) with skeleton; comments fetch strictly on expand. `AbortController` on unmount/context-change. |
| Unified on every page | Drawer rendered once in Shell — present on all routes by construction. Pages opt into entity context via hook. |

### 4.3 Entity context hook (progressive adoption)

```jsx
// src/notes/NotesContext.jsx
const NotesCtx = createContext(null);
export function NotesProvider({ children }) { … state: {entityType, entityId, label, notes, commentsCache} … }
export const useNotes = () => useContext(NotesCtx);

// In any page (opt-in, ~3 lines):
const { setContext } = useNotes();
useEffect(() => {
  setContext({ entityType: 'org_unit', entityId: unit.id, label: unit.name });
  return () => setContext(null);          // back to global view on leave
}, [unit?.id]);
```

Pages to wire first: `MDMPage.jsx` (selected org unit), `SchemaDetailPage.jsx` (table),
`DataProductDetailPage.jsx` (module), `RuleDetailPage.jsx` (dq_rule), `UsersPage.jsx` (user),
`ReportingPeriodsPage.jsx` (period). Every other page → **global view** ("All notes" across
entities the user can see, newest first) — the drawer is never empty, and adoption is incremental.

### 4.4 State & data layer

- New `src/notes/` feature folder: `NotesContext.jsx`, `NotesDrawer.jsx`, `NotesRail.jsx`,
  `NotesPanel.jsx`, `NotesTab.jsx`, `NoteCard.jsx`, `CommentThread.jsx`, `ReactionBar.jsx`,
  `NoteComposer.jsx`, `notesApi.js` (thin wrapper over `authFetch` — JWT refresh included),
  `notesUtils.js` (time formatting, optimistic reaction merge).
- `notesApi.js` uses the existing `authFetch` from `src/api/api.js` — no new fetch plumbing.
- Optimistic updates: reactions toggle locally first, reconcile on response.
- i18n: new `notes` namespace in the existing i18n setup (platform is bilingual en/ar, RTL-aware).

### 4.5 Keyboard + a11y

- `Ctrl+Shift+N` toggles the drawer (pattern matches existing `Ctrl+B` / `Ctrl+\` shortcuts in Shell).
- Rail buttons have `aria-label` + tooltip; expanded panel is a `role="complementary"` region;
  accordion/expands use MUI a11y defaults; focus returns to the toggle on collapse.

---

## 5. Flaws to avoid (extends F1–F12 of the earlier doc — this feature's specific traps)

| # | Flaw | Avoid by |
|---|---|---|
| N1 | Comments embedded in note-list payload → heavy pages | `comments_count` only; comments on a separate lazy endpoint |
| N2 | Nested comment replies | Model has no `parent` FK — 1-level enforced at the schema level |
| N3 | Free-text feedback instead of reactions | `NoteReaction` enum + counts; text goes in comments |
| N4 | Reactions require a second round-trip per user | Toggle POST; `my_reaction` in every list item |
| N5 | Re-fetching comments on every expand | Per-note comment cache in context; invalidate on new comment |
| N6 | Cascade-deleting notes when entity is deleted | `entity_id` plain int, no FK (F5); soft-delete notes |
| N7 | Notes lost when user deleted | `author` FK `SET_NULL` (F4) |
| N8 | Internal notes visible to everyone | `visibility` filter in queryset (author + admin only) |
| N9 | Editing/deleting others' comments | Permission: author-or-admin only |
| N10 | Drawer covering content without resize | Persistent flex sibling + drag handle + min/max clamp (not an overlay) |
| N11 | Drawer state lost per navigation | localStorage persistence (open/width/tab) — same as sidebar/copilot |
| N12 | Notes not audited | `emit_governance_event` on create/update/delete — Governance Audit page shows them |
| N13 | N+1 on counts | `annotate(Count(..., filter=Q(is_active=True)))` |
| N14 | RTL broken | Anchor + handle mirror via existing `isRtl` (Shell precedent) |
| N15 | Fetching on every context change | Fetch once per `entity_type:entity_id` (cache in context), `AbortController` |

---

## 6. Work breakdown (phases)

### Phase 1 — Backend (backend-worker)
1. `catalog/models.py`: `Note`, `NoteComment`, `NoteReaction` (+ `clean()` note XOR comment).
2. Migration `catalog/000X_notes_comments_reactions.py`.
3. `catalog/serializers.py`: `NoteListSerializer` (compact, counts, my_reaction),
   `NoteDetailSerializer` (with comment preview), `NoteCommentSerializer`, `ReactionToggleSerializer`.
4. `catalog/views.py`: `NoteViewSet` (list/create/update/soft-delete, `visibility` filter,
   pagination 20), `NoteCommentViewSet` (nested route, lazy thread), `NoteReactionToggleView`
   (note + comment). Wire `emit_governance_event`.
5. `catalog/urls.py`: router registrations + nested routes.
6. Tests: `catalog/tests/test_notes.py` — CRUD, permissions (author/admin/other),
   visibility filter, 1-level enforcement (no parent field), reaction toggle uniqueness,
   soft delete + audit event emitted, lazy list has no comment bodies, counts correct.

### Phase 2 — Frontend drawer (frontend-worker)
1. `src/notes/NotesContext.jsx` + `NotesProvider` mounted in `Shell.jsx` (wraps content Box).
2. `NotesDrawer` (rail ⇄ panel), resize handle, pin/collapse, tabs registry, RTL, persistence.
3. `NotesTab` + `NoteList` + `NoteCard` + `ReactionBar` + `OlderAccordion` + `NoteComposer`.
4. `CommentThread` with lazy fetch + cache + add-comment.
5. `notesApi.js`, i18n `notes` namespace, `Ctrl+Shift+N` shortcut, StatusBar indicator.
6. Tests: component tests (open/collapse/pin/resize/tab-switch), lazy-comment fetch
   (mock api), reaction optimistic toggle, RTL mirror.

### Phase 3 — Entity context wiring (frontend-worker, incremental)
Wire `setContext` into MDMPage, SchemaDetailPage, DataProductDetailPage, RuleDetailPage,
UsersPage, ReportingPeriodsPage. Global view for everything else.

### Phase 4 — QA + polish (qa-validator)
- Backend: run full catalog suite + new tests; verify `annotate` query count (Django Debug
  Toolbar) — no N+1 on a 20-item list.
- Frontend: vitest + manual E2E (open drawer on 3 page types, lazy comments, reactions,
  pin across navigation, RTL AR locale, resize clamps).
- Verify Governance Audit page lists note events.

---

## 7. Open decisions (flagged for the user)

1. **"Newest thread" on comment expand** — I chose *chronological flat thread + composer on top*.
   Alternative: newest comment pinned at top (Slack style). Can switch in `CommentThread` only.
2. **Reaction set** — `👍 ❓ ⭐` chosen (small, governance-flavored). Trivial to extend later
   (it's an enum).
3. **Global view when no entity** — "All notes" feed (newest across visible entities). Alternative:
   empty state "Select an entity to see its notes". Recommended: feed (drawer never dead).
4. **Pin semantics** — pinned = survives navigation; unpinned auto-collapses on entity change.
   Alternative: pin = always-open toggle only. Recommended: first.

---

## 8. Estimated footprint

- **Backend:** 3 models + 1 migration + 2 viewsets + 1 reaction view + 4 serializers + ~1 test file (~200 LOC test).
- **Frontend:** 1 context + 10 components (~900 LOC) + 1 api module + i18n keys.
- **No changes** to existing pages required for the drawer to appear everywhere (progressive adoption).

---

## 9. Recommendation

Build **Phases 1–2 first** (backend + drawer with global view + MDM wiring as the pilot page),
then **Phase 3** wires the remaining detail pages, then **Phase 4** QA. The drawer + lazy contract
are the risky parts — prove them on MDM before fanning out.
