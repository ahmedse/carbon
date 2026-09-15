# PULSE 0.2 — Phased Roadmap (Execution Plan)

> **Status:** CANONICAL PLAN · **Owner:** Master Architect · **Companion to** [`PULSE-MASTER.md`](./PULSE-MASTER.md)
> **Experience spec (mandatory for every UI phase):** [`PULSE-UX.md`](./PULSE-UX.md)
> **Wireframes + component specs (what to build):** [`PULSE-UX-DESIGN.md`](./PULSE-UX-DESIGN.md)
> **Audience:** Backend / Frontend / Debugger workers running **DeepSeek V4-Flash** (RULE_24).
> **Purpose:** take Pulse from *impressive assistant* to *true coworker* (Pulse 0.2, §6 of the master
> doc) **without letting a weaker model drift, thin out, or shortcut.**

---

## How to use this roadmap (read before any phase)

1. This plan is executed **one phase at a time**. Each phase is one worker session, one domain.
2. The Master Architect copies a phase into `TASKS.md`, hands the worker the activation prompt, and
   reviews `TASK-RESULTS.md` against the phase's **Acceptance Gate** before starting the next phase.
3. A phase is **not done** until its Acceptance Gate is proven with pasted terminal output
   (`.ai-toolkit/shared/definition-of-done.md`). "Probably works" = rejected.
4. Every phase lists a **Shallow-implementation trap** — the exact lazy shortcut a weak model would
   take. If the worker's output matches the trap, the phase is rejected.
5. Phases are ordered by ROI. **Do not reorder.** Wave A unblocks everything; the "alive UX" wave
   (D) is deliberately last because it is worthless until the brain is connected (A/B).

### Global gates (apply to EVERY phase — non-negotiable)

```bash
./.ai-toolkit/scripts/verify.sh all          # check + tests + lint + antipatterns
./.ai-toolkit/scripts/audit-imports.sh        # engine/ imports nothing from Carbon apps (I1)  [see Wave-0]
```
Plus: new logic has a test; bug fix has a regression test; boundary invariants I1–I8 (master §7) hold;
no user-facing "Pulse"/engine jargon (RULE_23).

**Every UI-bearing phase** (A4, B3, C2b, all of Wave D) must ALSO pass the **UX Acceptance Rubric**
([`PULSE-UX.md`](./PULSE-UX.md) §10) — the 4-beat story, the five data states (incl. *uncertain*),
provenance + real confidence, deliberate actions, legible consent, accessibility, theme tokens, and
`apiFetch`/SSE (no polling). A UI phase with green lint/build but a failed UX rubric is **rejected**.

### The seven anti-drift laws (every worker, every phase)

- **L1 — No new durable state in `engine/`.** Persistence is Carbon-owned (RULE_6). If a phase needs
  to persist, it writes through a Carbon store/model, never a module global or a file in `engine/`.
- **L2 — No upward imports.** `engine/` never imports `catalog/mdm/dq/emissions/accounts/core` (RULE_20).
- **L3 — No auto-mutation.** Every write is staged + confirmed (RULE_21).
- **L4 — Grow the periphery, freeze the spine.** New capability = a plugin/tool/skill/lane, never an
  edit to the six-witness spine or a new Django app (I6).
- **L5 — Prove it end-to-end.** A backend change is not done until a real request produces the real
  effect (row written, event delivered, counter incremented) — not just a passing unit test.
- **L6 — No stubs left "for later."** If you touch a dead path, you either make it live or delete it.
  No new inert code.
- **L7 — Telemetry or it didn't happen.** Every "it learned / it delivered / it escalated" claim ships
  a counter or ledger row that proves it at runtime.

---

## Wave 0 — Guardrail bootstrap (Master Architect, before any worker)

**W0.1 — Import-boundary check.** Create `.ai-toolkit/scripts/audit-imports.sh` that greps
`backend/ai/engine/` for `from (catalog|mdm|dq|emissions|accounts|core)` and `import (catalog|…)`
and exits non-zero on any hit. Wire it into `verify.sh` (`all`/`full`). This mechanically enforces
I1/L2 so no worker can silently couple the brain to Carbon.
**Acceptance:** `./.ai-toolkit/scripts/audit-imports.sh` prints `OK: engine boundary clean` and exit 0.

**W0.2 — ADR-0024** (`.ai-toolkit/decisions/0024-pulse-0.2-north-star.md`) pins the Pulse 0.2
definition + invariants so no worker re-litigates them. (Written alongside this plan.)

---

## WAVE A — Connect the Brain (fix G2, G3, G4) · highest ROI

> The brain is built; three circuits aren't plugged in. Wave A plugs them in. Backend-heavy.

### Phase A1 — Redis-backed ephemeral memory (fix G3, part 1)

- **Goal:** short-term + working memory survive restart and are shared across workers.
- **Why:** `short_term.py` / `working.py` are in-process `threading.Lock` dicts → amnesia on deploy,
  split-brain under multi-worker. A coworker cannot forget its focus every restart.
- **Domain:** Backend Worker.
- **FILES TO READ FIRST:** `engine/memory/short_term.py`, `engine/memory/working.py`,
  `engine/memory/manager.py`, `project.config.md` (BACKEND_QUEUE=Redis).
- **TASKS:**
  1. MODIFY `engine/memory/short_term.py` — back the store with Redis (key
     `pulse:st:{instance}:{conversation}`, JSON list, TTL configurable, default 24h). Keep the exact
     public method signatures (`add_message`, `get_context_window`, `clear`, `conversation_count`).
     In-process dict becomes a fallback only when Redis is unavailable (fail-visible log, never silent).
  2. MODIFY `engine/memory/working.py` — same treatment (`pulse:wm:{instance}:{conversation}`).
  3. ADD config keys via `engine/core/config.py` (`PULSE_MEMORY_REDIS_TTL_SECONDS`, default 86400).
- **DO NOT TOUCH:** `long_term.py`, `episodic.py`, the six-witness spine, any Carbon model.
- **Shallow-implementation trap:** ❌ writing to Redis but keeping a module-level dict as the source of
  truth (so it still doesn't survive restart); ❌ changing method signatures (breaks `manager.py`);
  ❌ swallowing Redis errors silently. The store MUST read back from Redis, not the dict.
- **ACCEPTANCE GATE:**
  ```bash
  # unit: round-trips through Redis
  ../.venv/bin/python -m pytest ai/tests/ -k "short_term or working" -q
  # e2e proof: set focus, restart backend, focus persists
  ./manage.sh restart backend && ./manage.sh manage shell -c \
    "from ai.engine.memory.working import get_working_memory as g; print(g().get_focus('PROVE-CONV'))"
  ```
  Gate passes when the focus set before restart is still returned after restart (not `None`).
- **North-star link:** #2 (continuity survives restart).

### Phase A2 — Redis pub/sub bus for engine events (fix G3, part 2 · foundation for G2)

- **Goal:** the engine's WebSocket subscriber registry (`notifier._subscribers`) and run/insight
  events move to Redis pub/sub so any process can publish and any web process can deliver.
- **Why:** today `_subscribers` is a per-process dict — a proactive insight generated by the
  scheduler process can't reach a user connected to a different web worker.
- **Domain:** Backend Worker.
- **FILES TO READ FIRST:** `engine/cognition/notifier.py`, `engine/proactive/delivery.py`.
- **TASKS:**
  1. ADD `engine/core/event_bus.py` — a thin Redis pub/sub publisher/subscriber
     (`publish(channel, payload)`, `subscribe(channel)`), channel scheme
     `pulse:events:{instance}`. No durable state — Redis is transport (RULE_6-compatible: transient).
  2. MODIFY `notifier.py` — `broadcast_run_event` / `push_to_subscribers` publish to the bus in
     addition to the in-process fan-out (keep in-process for same-process Studio sockets).
- **DO NOT TOUCH:** the persisted models (`Notification`, `KgProactiveInsight`) — those already work.
- **Shallow-implementation trap:** ❌ persisting events to Postgres (they're transient — Redis only);
  ❌ replacing the in-process path entirely (Studio sockets in the same process still need it —
  publish to *both*).
- **ACCEPTANCE GATE:**
  ```bash
  ../.venv/bin/python -m pytest ai/tests/ -k "event_bus or notifier" -q
  # cross-process proof: subscribe in one shell, publish from another, message arrives
  ```
- **North-star link:** #1 foundation, #2.

### Phase A3 — Proactive → Django SSE delivery (fix G2) · **highest single ROI**

- **Goal:** proactive insights reach the Carbon backend's HTTP surface via SSE, consumable by React.
- **Why:** G2 — the engine already generates + persists insights (`KgProactiveInsight`); they just
  never reach the UI. This is the highest-leverage fix in the entire program.
- **Domain:** Backend Worker.
- **FILES TO READ FIRST:** `ai/workspace_api.py` (SSE pattern), `engine/proactive/delivery.py`,
  `ai/ops_api.py`, `engine/core/event_bus.py` (from A2), `.ai-toolkit/shared/api-contract.md`.
- **TASKS:**
  1. ADD a DRF SSE endpoint `GET /carbon-api/ai/insights/stream/` (CBAC-scoped, `StreamingHttpResponse`)
     that subscribes to the Redis bus (A2) and yields `insight.new` / `insight.updated` frames for the
     caller's org scope only (RULE_20 isolation).
  2. ADD `GET /carbon-api/ai/insights/` (paginated, CBAC-scoped) returning persisted
     `KgProactiveInsight` rows + disposition, and `POST …/{id}/disposition/` to mark
     read/acted_on/dismissed (RULE_21: user action, not auto).
  3. MODIFY `delivery.py` `_push_websocket` → also publish an `insight.new` frame to the bus.
- **DO NOT TOUCH:** the trigger evaluator, insight generator (they work); frontend (that's A4).
- **Shallow-implementation trap:** ❌ a polling endpoint instead of SSE; ❌ returning ALL instances'
  insights (must filter by `scope.org_unit_ids`); ❌ leaking engine jargon in the payload (RULE_23) —
  send outcome-shaped fields (`title`, `narrative`, `severity`, `recommended_actions`), never
  trigger internals.
- **ACCEPTANCE GATE:**
  ```bash
  ../.venv/bin/python -m pytest ai/tests/ -k "insight" -q
  # live proof: seed an insight, curl the SSE stream, see the frame
  curl -N -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8009/carbon-api/ai/insights/stream/ | head
  ```
  Gate passes when a freshly-delivered insight appears on the stream **scoped to the caller's org**.
- **North-star link:** #1 (proactive insights reach the user).

### Phase A4 — Notification panel wired to real insights (fix G2 · frontend)

- **Goal:** the bell / notification panel in the Carbon UI shows real backend insights live.
- **Why:** completes G2 on the user side. (This is NGX-4, but now it has real content.)
- **Domain:** Frontend Worker.
- **FILES TO READ FIRST:** `carbon-frontend/src/api/api.js` (apiFetch), the existing shell header /
  `NotificationsBell` if present, `carbon-frontend/src/shell/*`.
- **TASKS:**
  1. ADD an SSE hook `useInsightStream()` (via `apiFetch` + `ReadableStream`, JWT refresh aware).
  2. ADD/ްwire a `NotificationPanel` in the shell header: unread count, severity styling, click →
     disposition POST, relevant-page deep link. Outcome copy only (RULE_23).
  3. Empty/error/loading states use theme tokens (RULE_8) and `PageContainer` primitives where applicable.
- **DO NOT TOUCH:** backend endpoints (A3 owns them); any raw `fetch()` (RULE_10).
- **Shallow-implementation trap:** ❌ polling on a timer instead of the SSE hook; ❌ hardcoded colors
  for severity instead of theme tokens; ❌ showing internal fields (trigger id, engine terms).
- **ACCEPTANCE GATE:** `npm run lint && npm run build` green; manual: deliver an insight (A3) → it
  appears in the panel without refresh; clicking marks it read (network tab shows the disposition POST).
- **UX GATE (PULSE-UX §10):** insight *arrives* (Beat 4 proactivity, no refresh); panel has all data
  states incl. honest empty ("No insights yet…"); severity carries text/icon not color-only; click deep-
  links to the relevant room; zero RULE_23 leakage in any visible string; motion settles (respects
  `prefers-reduced-motion`). Show a recording of an insight landing live.
- **North-star link:** #1.

### Phase A5 — Resolve dead subsystems (fix G4)

- **Goal:** every "impressive-looking" inert path is either made live or deleted. No zombie code.
- **Why:** G4 — `detect_performance_drift` is fed an always-empty `cache_profile.drift_metrics`;
  `learned_triggers` seed conditions referencing pseudo-table `system_snapshots:<field>` the host-DB
  evaluator can't query. Inert code lies about capability.
- **Domain:** Backend Worker (+ Debugger mindset).
- **FILES TO READ FIRST:** `engine/proactive/insight_generator.py` (`detect_performance_drift`),
  `engine/cognition/learned_triggers.py`, `engine/proactive/trigger_evaluator.py`.
- **TASKS (decide per path, with the Master):**
  1. **Learned triggers:** make the seeded condition reference a **real** evaluable source (evaluate
     against `SystemSnapshot` history via the engine store, not the host DB), OR remove the
     `system_snapshots:` seeding branch and the trigger-learning job wiring. Whichever ships must
     produce a **fired** trigger in a test.
  2. **Drift metrics:** either add the crawler/config that populates `cache_profile.drift_metrics`
     (out of scope for one phase → likely defer) OR delete `detect_performance_drift` from the
     scheduled path and mark it clearly experimental. No silent always-empty call left scheduled.
- **DO NOT TOUCH:** working proactive paths (threshold/trend/correlation over host data).
- **Shallow-implementation trap:** ❌ "leaving it for later" — L6 forbids new/kept inert code; ❌
  deleting the model/table (keep schema, remove only the inert code path).
- **ACCEPTANCE GATE:** a test proves the kept path fires a real insight, OR a grep proves the inert
  path is no longer scheduled (`grep -rn "detect_performance_drift\|drift_metrics" engine/` shows only
  removed/guarded references). `verify.sh all` green.
- **North-star link:** #4 (no dead subsystems).

---

## WAVE B — Real Learning (fix G1) · make growth true and observable

### Phase B1 — Close the skill promotion arrow

- **Goal:** a draft skill that passes the 4-critic admission gate + marginal-gain check is actually
  transitioned to `status=instance_promoted` (not left at `gate_status=pending` forever).
- **Why:** G1 — consolidation drafts skills; nothing promotes them; the planner only reads promoted.
- **Domain:** Backend Worker.
- **FILES TO READ FIRST:** `engine/skills/gate.py` (4 critics + marginal-gain), `engine/skills/registry.py`
  (`update_status`, `list_promoted`), `engine/cognition/consolidation.py`, `engine/cognition/loop.py`
  (scheduled sweeps).
- **TASKS:**
  1. ADD a `run_admission(instance_id)` sleep-time job that: loads `gate_status=pending` skills, runs
     structural → harmlessness → consistency → marginal-gain, and on full pass calls
     `registry.update_status(id, "instance_promoted", promoted_by="system:gate")`, writing a
     `SkillAdmissionLog` row either way.
  2. WIRE it into the cognition scheduler (`cognition/loop.py`) as `_run_skill_admission`, off-peak.
  3. Keep human override intact (an admin can still reject/promote).
- **DO NOT TOUCH:** the critics' internal logic (they're sound); the hot-path planner (B2 owns reuse).
- **Shallow-implementation trap:** ❌ auto-promoting on structural pass only (must pass all four +
  marginal gain); ❌ promoting without a `SkillAdmissionLog` row (no audit); ❌ running it on the hot
  path (it's sleep-time).
- **ACCEPTANCE GATE:** a test seeds a draft skill that should pass → runs `run_admission` → asserts
  `status == instance_promoted` and a `SkillAdmissionLog` row exists; and one that should fail stays pending.
- **North-star link:** #3.

### Phase B2 — Prove hot-path skill reuse + reuse telemetry

- **Goal:** the planner actually invokes a promoted skill on a matching request, and a counter proves it.
- **Why:** G1 is only closed when learning changes behavior **and we can see it**.
- **Domain:** Backend Worker.
- **FILES TO READ FIRST:** `engine/cognition/plan/planner.py` (`_score_skill`, `list_promoted`,
  `invoke_skill`), `engine/skills/crud.py` (`update_stats`), `engine/cognition/plan/loop.py`.
- **TASKS:**
  1. Ensure a promoted skill matching an utterance is selected and executed via `invoke_skill`
     (trace the path; fix the gap if the planner doesn't reach promoted skills).
  2. On each promoted-skill execution, call `SkillsStore.update_stats(...)` (usage_count++,
     success_rate, latency) — this is the reuse telemetry (L7).
  3. EXPOSE the counter read-only via `ai/ops_api.py` (`skills` panel already exists) so reuse is visible.
- **DO NOT TOUCH:** the admission gate (B1); the six-witness spine.
- **Shallow-implementation trap:** ❌ asserting the skill *could* match but never executing it; ❌
  incrementing usage on match instead of on actual execution; ❌ no observable counter.
- **ACCEPTANCE GATE:** an integration test: promote a skill → send a matching request through the
  pipeline → assert the skill executed AND `usage_count` incremented AND the ops endpoint reflects it.
- **North-star link:** #3.

### Phase B3 — Learning observability panel (admin)

- **Goal:** the admin Pulse console shows drafted → promoted → reused skill counts + admission logs.
- **Why:** makes "is learning cold?" answerable at a glance forever (prevents future regression to theater).
- **Domain:** Frontend Worker (reads existing `ai/ops_api.py` skills/learning endpoints).
- **ACCEPTANCE GATE:** `lint` + `build` green; panel renders real counts from the API; empty state honest.
- **UX GATE (PULSE-UX §10):** the Admin "it gets better, visibly" story (Wave B headline) — drafted→
  promoted→reused shown as a legible progression, not a raw table; all data states incl. honest empty;
  theme tokens only; numbers are the REAL backend counts (never UI-invented).
- **North-star link:** #3.

---

## WAVE C — Deeper Cognition (fix G5, Faculty 7)

### Phase C1 — Adaptive reasoning lane

- **Goal:** a `reason` task lane; genuinely hard problems escalate to a reasoning-grade model.
- **Why:** G5 — routing has no extended-thinking/o-series lane beyond a single knowledge-gap escalation.
- **Domain:** Backend Worker.
- **FILES TO READ FIRST:** `engine/llm/router.py` (`_TASK_MODEL_MAP`), `engine/cognition/turn/salience.py`
  (deep route), `runner.py` (S1 deep routing + knowledge_gap escalation), `project.config.md` (models).
- **TASKS:**
  1. ADD a `reason` lane to `_TASK_MODEL_MAP` (config-driven `LLM_REASON_MODEL`).
  2. Route S1 `deep` salience **and** critic `knowledge_gap` to the `reason` lane when configured.
  3. Log the escalation + a quality signal (critic verdict before/after) so the delta is measurable (L7).
- **DO NOT TOUCH:** cache-prefix discipline (RULE_25) — stable prefix stays first.
- **Shallow-implementation trap:** ❌ hardcoding a model id (must be config); ❌ escalating everything
  (only deep/knowledge_gap); ❌ no measurement of whether escalation helped.
- **ACCEPTANCE GATE:** test asserts a `deep`/`knowledge_gap` turn selects `LLM_REASON_MODEL` when set,
  and falls back cleanly when unset; ledger records the escalation.
- **North-star link:** #5.

### Phase C2 — Surface calibrated confidence (Faculty 7)

- **Goal:** the assistant tells the user how sure it is, and says "I don't know" honestly.
- **Why:** metacognition is what makes it trustworthy; the signal exists (`confidence`,
  `knowledge_gap`, honest-uncertainty) but isn't shown.
- **Domain:** Backend (payload) + Frontend (display) — split into C2a/C2b.
- **FILES TO READ FIRST:** `turn/witnesses.py` (`confidence`, `confidence_label`), `runner.py`
  (honest-uncertainty path), `ai/serializers.py`, frontend `AIMessageBubble`.
- **TASKS:** C2a expose `confidence_label` + `honest_uncertainty` flag in the message serializer
  (outcome-shaped, RULE_23). C2b render a subtle confidence indicator + distinct honest-uncertainty
  styling in `AIMessageBubble` (theme tokens).
- **Shallow-implementation trap:** ❌ inventing a confidence number in the UI; ❌ showing raw critic
  flags/internals to the user.
- **ACCEPTANCE GATE:** backend test asserts the field is present + correct; frontend build green +
  manual: a low-confidence / honest-uncertainty reply renders distinctly.
- **UX GATE (PULSE-UX §5/§6):** *uncertain* is a first-class data state — low-confidence and honest-
  "I don't know" replies render calm-and-distinct (not as an error), the signal is derived from the
  REAL critic output, carries text/icon (not color-only), and leaks zero internals (RULE_23).
- **North-star link:** #6.

---

## WAVE D — Alive UX (the NGX layer) · **last on purpose**

> Only valuable once the brain is connected (A/B). These make Pulse *feel* as alive as it now *is*.
> **Wave D is governed end-to-end by [`PULSE-UX.md`](./PULSE-UX.md)** — its headline is *"it feels as
> alive as it now is"* (PULSE-UX §11). Polish on a disconnected brain is a lie; that's why D is last.
> Each is a standard frontend-with-thin-backend phase; keep them small. Each ships the full **UX
> Acceptance Rubric** (PULSE-UX §10), not just green lint/build.

- **D1 — SSE progress for long ops** (DQ runs, imports, reports): reuse the A2 bus + A3 SSE pattern.
  *UX:* Beat 2 "think out loud" made real — narrated human steps, never a bare spinner, rest of UI interactive.
- **D2 — Optimistic CRUD hooks** (`useOptimisticList`/`useOptimisticItem`) platform-wide.
  *UX:* Beat 1 <100ms acknowledge; visible reconcile-or-rollback; never a form cleared on error.
- **D3 — AI output transparency** (AIGeneratedBadge, ConfidenceBar from C2, ReasoningTrace, SuggestionDiff).
  *UX:* §6 made concrete — provenance on demand, real confidence, legible consent diff, AI-authored labeled.
- **D4 — Polish bundle** (skeleton screens replacing spinners; presence via SSE heartbeats; frontend
  observability/logger + Web Vitals; offline draft persistence + service worker).
  *UX:* §8 delight details — skeletons over spinners, motion with meaning, no layout shift, presence.

Each D-phase: `lint` + `build` green, theme tokens only (RULE_8), `apiFetch` only (RULE_10), no raw
`fetch`, outcome copy only (RULE_23), **and the full UX Acceptance Rubric (PULSE-UX §10)**. Acceptance =
the specific UX behaves under a real backend event.

---

## Sequencing & dependencies

```
W0 (guardrails) ─┬─> A1 ─┐
                 ├─> A2 ─┼─> A3 ─> A4        (Wave A: connect the brain)
                 └─> A5  ┘
A2/A3 ─> B1 ─> B2 ─> B3                       (Wave B: real learning)
router ─> C1 ;  witnesses ─> C2a ─> C2b       (Wave C: deeper cognition)
A2/A3 + C2 ─> D1..D4                           (Wave D: alive UX)
```

**Rule:** Wave A fully green before Wave B. C can run parallel to B (different files). D is last.

## Role & model assignment (RULE_24 — all workers V4-Flash; Master V4-Pro)

| Phase | Role | Notes |
|-------|------|-------|
| W0, all reviews | Master Architect | writes gate scripts + ADR; reviews every gate |
| A1, A2, A3, A5, B1, B2, C1, C2a | Backend Worker | one phase/session |
| A4, B3, C2b, D1–D4 | Frontend Worker | one phase/session |
| any red gate | Debugger/Fixer | root-cause + regression test |

## Definition of "Pulse 0.2 shipped"

All eight north-star items (master §6) proven; invariants I1–I8 hold; `verify.sh all` +
`audit-imports.sh` green; the five gaps G1–G5 each closed with a runtime artifact (delivered insight,
persisted-after-restart focus, incremented reuse counter, no scheduled inert path, logged escalation).
