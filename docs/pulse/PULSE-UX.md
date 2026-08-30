# PULSE — The Experience (UI/UX Philosophy & Spec)

> **Status:** CANONICAL · **Owner:** Product Designer + Master Architect · **Last audited:** 2026-08-30
> **Companions:** [`PULSE-MASTER.md`](./PULSE-MASTER.md) (what Pulse *is*) ·
> [`PULSE-0.2-ROADMAP.md`](./PULSE-0.2-ROADMAP.md) (how we build it).
> **This file governs how Pulse must *feel*.** It does **not** restate the toolkit —
> it **extends** `.ai-toolkit/shared/design-principles.md` (the 11 principles),
> `.ai-toolkit/shared/ux-patterns.md` (interaction patterns), and
> `.ai-toolkit/shared/design-system.md` (tokens/primitives) with the Pulse-specific,
> AI-coworker experience layer. **When this file and the toolkit agree, the toolkit is the
> mechanism and this file is the intent. When they appear to conflict, the toolkit wins on
> *how it's built*; this file wins on *how it should feel* — raise the conflict, don't silently diverge.**

---

## 0. The one sentence

> **Pulse should feel like a brilliant, trustworthy colleague sitting next to you — one who
> understands the question, shows its thinking, never bluffs, remembers what matters, and does the
> boring work before you ask — inside an interface so calm and clear you forget it's software.**

Every pixel, every millisecond of latency, every word of copy is judged against that sentence.

---

## 1. The five experience pillars (the words you gave, made testable)

Each pillar is a felt quality **plus** the concrete, checkable behavior that proves it. A phase that
claims a pillar without the proof column is not done.

| Pillar | What the user should feel | Proven by (checkable) |
|--------|---------------------------|-----------------------|
| **Crystal clear** | "I always know what's happening and why." | Every surface answers *where am I / what can I do / what just happened / what's next.* No jargon (RULE_23). One primary action per view. Status never by color alone (Principle 9). |
| **Storylike** | "This has a beginning, middle, and end — it flows." | Every interaction is a 4-beat arc (§3). Progress is narrated, not spun. Answers build on remembered context ("continuing from your South Valley review…"). No dead ends — every end offers the next beat. |
| **Easy** | "It did the hard part for me." | Sensible defaults, minimal input (Principle 7). The 80% path is one action; power is one click deeper (Principle 3). Proactive insights arrive *before* the user hunts for them (G2). |
| **Intuitive** | "I didn't have to learn it." | Consistency is a feature (Principle 6): same action = same place, same look, everywhere. Reuse existing patterns (ux-patterns.md) — never reinvent. Deliberate actions only (Principle 11): row-click highlights, explicit action navigates. |
| **Robust** | "It never surprises me or breaks under me." | All 4 data states on every surface (loading/error/empty/loaded). Optimistic UI reconciles or rolls back visibly. Streams reconnect. Honest uncertainty instead of confident wrongness. Nothing blocks the whole app. |
| **Highly exceptional** | "This is better than any tool I've used." | The delight details in §8: sub-100ms perceived response, presence, transparency you can trust, motion with meaning, copy that respects the reader, accessibility as baseline. |

---

## 2. Who the user is (design from the job, not the screen — Principle 1)

Pulse serves three postures. Every UX decision names which one it's for.

- **The Operator** (daily): asks a question, wants a grounded answer + the next action. Optimizes for
  speed, clarity, zero jargon. *"What changed in South Valley's emissions this month, and what do I do?"*
- **The Analyst** (deep-dive): wants provenance, the reasoning trace, the data behind the number,
  confidence. Optimizes for transparency and drill-down. *"Show me exactly what went into this."*
- **The Admin / Steward** (oversight): watches the assistant itself — what it learned, what it
  delivered, where it's uncertain, what it costs. Optimizes for observability and control.

Progressive disclosure (Principle 3) is how one interface serves all three: the Operator's calm
surface is the default; the Analyst's depth is one click down; the Admin's console is a separate,
deliberate destination.

---

## 3. The narrative spine — every interaction is a 4-beat story

"Storylike" is not decoration. It is a **contract on the shape of every interaction.** Each of the
four beats has a required UI behavior. Skipping a beat is the #1 way Pulse stops feeling alive.

```
   BEAT 1 · ACKNOWLEDGE      BEAT 2 · THINK (visible)     BEAT 3 · ANSWER            BEAT 4 · CARRY FORWARD
   "I heard you, here's       "Here's what I'm doing,       "Here's the grounded       "Here's the next beat,
    what you asked."           in human words."              answer + why to trust it." and I'll remember this."
   ─────────────────────      ─────────────────────        ─────────────────────      ─────────────────────
   • echo intent in plain     • narrated steps, not a       • outcome-shaped answer    • 1–3 next actions
     language (optimistic,      bare spinner (SSE)          • provenance affordance      (deep links)
     < 100ms)                 • steps are human            • confidence / honest-     • continuity cue for the
   • if ambiguous → ONE         ("Reading South Valley       uncertainty (never a        next turn ("noted for
     crisp question, never       records…"), never            fake number)                your review")
     a clarify loop              engine internals (RULE_23)  • no dead end
```

### Beat rules (enforceable)
- **B1 Acknowledge < 100ms.** The user's message and an "on it" state appear instantly (optimistic),
  before the backend responds (Principle 4/8). Silence > 100ms is a bug.
- **B2 Think out loud, in human.** For any op > ~1s, show *narrated* progress via SSE — real steps in
  outcome language ("Checking the last 3 months of readings…"), never `salience→intent→retrieve` or
  latency/token noise (RULE_23, ux-patterns "no technical noise in the stream").
- **B3 Answer with a spine of trust.** The answer is scoped to exactly what was asked (one branch =
  one branch, not the whole org), carries a **provenance affordance** (ⓘ "what went into this"), and a
  **confidence signal**; when Pulse doesn't know, it says so plainly (honest uncertainty), never bluffs.
- **B4 Never a dead end.** Every answer ends with 1–3 concrete next actions (deep-linked) and, when
  relevant, a continuity cue that the moment was remembered. The story never just stops.

---

## 4. Information architecture — three calm rooms, one model

One primary navigation model (ux-patterns "one primary navigation model per app"). Pulse lives in
**three rooms**, each with a single job. No competing navigation, max 2 levels deep.

1. **The Conversation** (Operator's home) — the message stream. Content-first, chrome-on-hover (VSCode
   Copilot Chat density). Sessions grouped by time (Today / Yesterday / 7 days / Older), collapsible,
   per-item hover actions. This is where the 4-beat story plays out.
2. **The Inspector** (Analyst's depth) — a contextual drawer (ADR-0019), never a new page. Opens from a
   provenance affordance or an entity mention. Shows the *why*: sources, the reasoning trace, the data
   grid behind the number, confidence. Closing it returns you exactly where you were.
3. **The Pulse Console** (Admin's oversight) — a deliberate, separate destination. Shows the assistant's
   own life: insights delivered, skills drafted→promoted→reused (Wave B), escalations, budget/cost,
   uncertainty hotspots. This is the only place "Pulse"/engine language may appear (RULE_23).

Plus one **ambient thread** that crosses all rooms:

4. **Proactivity surface** (the bell / notification panel) — where the coworker speaks *first* (G2).
   Unread count, severity styling by token (never color-only), click → disposition + deep link to the
   relevant room. Empty state is honest and calm, not a fake badge.

---

## 5. The 4 data states — non-negotiable on every surface

Straight from `design-system.md` RULE 4 and `ux-patterns.md`, but Pulse raises the bar because AI
surfaces have a **fifth** state most tools forget: *uncertain*.

| State | Pulse behavior |
|-------|----------------|
| **Loading** | Skeleton that mimics the final shape (not a spinner) for lists/cards; for a streaming answer, the narrated think-beat (B2). The rest of the UI stays interactive. |
| **Empty** | Explains *why* it's empty and offers the next action ("No insights yet — Pulse reviews your data nightly. Ask a question to get started."). No-data ≠ no-results — say which. |
| **Error** | A human sentence + a retry/next step. Never a stack trace, never a raw latency/HTTP code in the user's face. The detail goes to the log for the debugger. |
| **Loaded** | The answer/content, scoped and grounded, with provenance + confidence affordances. |
| **Uncertain** *(Pulse-specific)* | When confidence is low or a knowledge gap is hit: distinct, calm styling that says "here's my best read, and here's what I'm unsure about" — **honest uncertainty is a first-class state, not an error.** |

---

## 6. Transparency & trust — the differentiator, made concrete

Trust through transparency (Principle 10) is *the* reason an enterprise user will rely on an AI
coworker. Pulse makes trust **visible but quiet** — available on demand, never noisy (ux-patterns
"provenance is a small ⓘ hover target, not always-visible noise").

- **Provenance ("what went into this").** Every substantive answer carries a small ⓘ affordance that
  opens the Inspector: the sources/records used, the tools invoked (in outcome language), data
  freshness/timestamp. The Operator ignores it; the Analyst lives in it.
- **Confidence, honestly calibrated.** A subtle indicator (bar/label from C2), *derived from the real
  critic signal* — never a number invented in the UI. Low confidence looks different, on purpose.
- **Honest "I don't know."** When Pulse hits a knowledge gap, it says so in plain language and offers
  what it *can* do — this is a feature, not a failure. Bluffing is the cardinal UX sin.
- **AI-generated is labeled.** Anything Pulse authored or suggested is marked (AIGeneratedBadge) so the
  user always knows human vs. machine — quietly, with a token, not a shout.
- **Consent is legible (RULE_21).** Before any mutation, the user sees exactly what will change, in a
  diff/summary they can approve or reject. No side effect from an ambiguous gesture (Principle 11).
  The user is always the one who pulls the trigger.
- **No leakage (RULE_23).** Provenance and progress speak in *outcomes* ("Read 412 South Valley
  readings"), never internals ("S2 retrieve returned 412 rows"). The engine is invisible; the work is visible.

---

## 7. Conversational surface — the density & mechanics contract

Extends the "Conversational & AI Surfaces" block of `ux-patterns.md`. This is the Operator's home; it
must feel like the best chat you've used.

- **Content-first, chrome-on-hover.** The stream shows content only. Copy / retry / feedback / menu
  live in a hover toolbar on the message — never an always-on button row, never a standing "AI/You"
  caption on every message.
- **Status is exceptional, not ambient.** A chip appears only on failure/interrupted — not as constant
  decoration. Latency, tokens, and cost live in a tooltip/menu, never as bare inline chips.
- **Markdown & rich content render properly.** Answers go through the dedicated renderer
  (`MarkdownMessage`), including robust Mermaid/diagram/code handling — never raw markdown dumped into a
  `<p>`. A malformed diagram degrades gracefully to its source, it never crashes the message.
- **Input bar respects flow.** Comfortable min/max rows; Enter = send, Shift+Enter = newline; a
  stop/interrupt control while streaming that swaps to retry on completion.
- **Sessions are first-class.** Grouped by time, collapsible, per-item hover actions (rename / pin /
  archive / delete), relative timestamps. Zero-count toggles (e.g. "Archived (0)") are hidden entirely.
- **Continuity is shown, not just stored.** When Pulse uses remembered context, it says so briefly
  ("Continuing your South Valley review…"). Memory the user can't perceive earns no trust. **And the
  reverse: never show a "context cleared"/divider the user didn't cause** — false separators break the story.

---

## 8. The "highly exceptional" details (delight, earned not bolted on)

These are what move Pulse from *good* to *the best tool they've used*. Each is small; together they are
the feeling.

- **Perceived performance first (Principle 8).** Optimistic first beat < 100ms; skeletons over
  spinners; stream tokens as they arrive so the answer *grows* instead of *popping*. Never block the
  whole screen for a partial load.
- **Motion with meaning.** Motion clarifies causality (where did this come from, where did it go) — the
  Inspector slides from the thing it explains; a new insight settles into the bell. Respect
  `prefers-reduced-motion`. No motion for its own sake; nothing bounces without a reason.
- **Presence & aliveness.** Subtle "thinking" and streaming states; when the coworker delivers a
  proactive insight, it arrives gently (a settle, not a jarring pop). The app feels *awake* because the
  brain behind it now is (Wave A).
- **Copy that respects the reader.** Plain, warm, concise, active voice. Say the outcome, not the
  mechanism. Errors are humane and actionable. Never cute at the cost of clarity (Principle 2).
  One consistent voice across every room.
- **Accessibility as baseline, not a feature (Principle 9 / WCAG AA).** Keyboard-complete (every
  primary action reachable, visible focus ring), screen-reader-sane (streamed answers announced via
  polite live regions, not spammed token-by-token), contrast-safe, status never by color alone, targets
  ≥ 44px. The confidence/severity signals carry text/icon, not just hue.
- **Density done right.** Enterprise-desktop-first, compact per `compact-ui.md`; reflow to cards on
  narrow widths, never hide critical actions. The Analyst can see a lot without it feeling cramped.
- **Zero jarring surprises.** No modal-on-modal, no layout shift as content loads (reserve space), no
  focus stealing, no surprise navigation from a stray click (Principle 11).

---

## 9. What Pulse UX must NEVER do (instant reject in review)

Beyond the toolkit anti-patterns (`ux-patterns.md`), these are Pulse-specific violations:

- ❌ **Leak the engine (RULE_23).** Any "Pulse", "witness", "salience", "S2/S4", raw latency/token/cost,
  or trigger-id in user-facing text. Outcomes only.
- ❌ **Bluff.** A confident answer where the critic flagged a knowledge gap. Uncertainty must show.
- ❌ **Fake a signal.** A confidence number/provenance invented in the UI instead of from the backend.
- ❌ **Silent proactivity.** Insights that exist in the backend but never reach the bell (G2 regression).
- ❌ **Dead end.** An answer with no next action; a spinner with no narration; an error with no recovery.
- ❌ **False context break.** A "context cleared"/divider the user didn't trigger.
- ❌ **Poll where a stream belongs.** Timer-polling a surface that should be SSE (kills "alive").
- ❌ **Auto-mutate (RULE_21).** Any state change without a legible, user-pulled consent step.
- ❌ **Reinvent a pattern** that already exists in `ux-patterns.md` / the app.

---

## 10. UX Acceptance Rubric (paste into every UX-bearing phase's gate)

A UX-bearing phase (any phase touching a user-facing surface — A4, B3, C2b, all of Wave D) is **not
done** until every applicable box is checked *and shown* (screenshot/recording or described network
proof). This is the UX counterpart to the Definition of Done.

```
[ ] 4-beat story intact: acknowledge <100ms · narrated think · grounded answer · next action
[ ] All data states present: loading(skeleton) · empty(why+next) · error(human+retry) · loaded · uncertain
[ ] Provenance affordance present and opens real sources (Inspector), not a placeholder
[ ] Confidence / honest-uncertainty reflects the REAL backend signal (not UI-invented)
[ ] Zero RULE_23 leakage in any visible string (grep the diff for engine terms)
[ ] Theme tokens only (RULE_8) — no hardcoded hex/spacing; density per compact-ui.md
[ ] apiFetch only (RULE_10) — no raw fetch; JWT-refresh aware; SSE where it should stream (no polling)
[ ] Deliberate actions only (Principle 11): row-click highlights, explicit action navigates/mutates
[ ] Consent legible for any mutation (RULE_21): user sees the change before it happens
[ ] Accessible: keyboard-complete, visible focus, live-region for streams, status not color-only, AA contrast
[ ] Motion respects prefers-reduced-motion; no layout shift on load; no modal-on-modal
[ ] Copy is plain, active, outcome-shaped; error copy is humane + actionable
[ ] Reuses existing patterns (ux-patterns.md) — no reinvented interaction
[ ] lint + build green; behavior demonstrated under a REAL backend event (not a mock)
```

---

## 11. Per-wave UX intent (how the story gets richer as the brain connects)

The roadmap is ordered so the UX becomes *true*, not just decorated. Each wave has a UX headline.

| Wave | UX headline | The felt change |
|------|-------------|-----------------|
| **A — Connect the brain** | *"It speaks first, and it remembers."* | Proactive insights reach the bell (G2); continuity survives restart (G3) — the coworker stops having amnesia and starts initiating. |
| **B — Real learning** | *"It gets better, visibly."* | The Admin console shows drafted→promoted→reused skills (G1) — growth becomes something you can *watch*, not take on faith. |
| **C — Deeper cognition** | *"It knows how sure it is."* | Calibrated confidence + honest uncertainty surface in the answer (Faculty 7) — trust becomes legible. |
| **D — Alive UX** | *"It feels as alive as it now is."* | SSE progress, optimistic CRUD, transparency (badges, reasoning trace, confidence bar, suggestion diff), skeletons, presence — the polish, now backed by a real brain. **Last on purpose:** polish on a disconnected brain is a lie. |

---

## 12. Where to look (UX file map)

| You need… | Read |
|-----------|------|
| The 11 product principles (the "why") | `.ai-toolkit/shared/design-principles.md` |
| Interaction patterns (the "how it behaves") | `.ai-toolkit/shared/ux-patterns.md` |
| Tokens, primitives, the 4 states (the "how it looks/builds") | `.ai-toolkit/shared/design-system.md` |
| Enterprise density spec | `.ai-toolkit/shared/compact-ui.md` |
| User stories & journeys format | `.ai-toolkit/shared/user-stories.md` |
| The contextual Inspector decision | `.ai-toolkit/decisions/0019-contextual-inspector-drawer.md` |
| What Pulse *is* (architecture, boundary, gaps) | [`PULSE-MASTER.md`](./PULSE-MASTER.md) |
| The phased build plan + acceptance gates | [`PULSE-0.2-ROADMAP.md`](./PULSE-0.2-ROADMAP.md) |
| Per-room wireframes + component specs (build this) | [`PULSE-UX-DESIGN.md`](./PULSE-UX-DESIGN.md) |
