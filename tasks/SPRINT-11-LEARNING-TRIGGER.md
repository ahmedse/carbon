# Sprint 11 — Learning trigger + scheduler + flywheel console (1 week)

**Goal:** Make the Sprint 10 learning bridge actually fire in production. Today
`learn_from_feedback` must be run by hand; Sprint 11 (a) triggers learning the
moment a user posts feedback, (b) runs a periodic safety-net sweep, and (c) gives
the AI admin a flywheel console with status + a manual run button.

**Deferred-from:** Sprint 10 (`tasks/SPRINT-10-LEARNING.md`) — "real-time trigger on
feedback POST, scheduler wiring, learn-facts frontend console."

---

## Background (verified against code)

- `CarbonIntelligence.record_feedback` (`backend/ai/intelligence.py`) is the **only**
  entry point for feedback. It persists `AIMessage.outcome` + `correction_text` and
  returns the serialized message. It does **not** currently call the learning bridge.
- `ai.learning.learn_from_message(message)` (Sprint 10) consumes one judged message into
  the engine (`KgFeedbackRecord` + `LongTermMemory`), sets `learned_at` on success, and
  leaves `learned_at` NULL on failure (retryable). It no-ops on non-learnable outcomes.
- `ai.learning.learn_all_pending(limit)` batches all `outcome IN (accepted, rejected,
  corrected) AND learned_at IS NULL` rows; returns a stats dict.
- **Durability hazard:** the store seam is `AI_STORE_BACKEND`, defaulting to `"inmemory"`
  (`backend/config/settings.py:469`). `record_feedback` / `LongTermMemory.store_fact`
  write via `db.add()` on the store session, so `"inmemory"` **silently drops writes**
  while `learn_from_message` still marks the message `learned_at` — i.e. the fact is lost
  but the message is never retried. The web/scheduler `.env` does not set it today, so
  both processes currently run non-durable.
- The existing `scheduler` docker service runs `run_cognition_loop` (Phase D precedent:
  `AsyncIOScheduler` + `loop.add_signal_handler` SIGINT/SIGTERM + `asyncio.Event().wait()`).
- The Pulse console already shows the durable outputs (`MemoryPanel` → `MemoryLongTerm`,
  `FeedbackPanel` → `KgFeedbackRecord`) but has **no** surface for the flywheel's
  pending/processed state and no way to trigger the sweep on demand.

---

## Tasks

| Task | Worker | Detail |
|---|---|---|
| Real-time trigger in `record_feedback` | Backend Worker | Call `learn_from_message` after `message.save(...)`, best-effort (try/except → `logger.warning`), so a learning failure never 500s the feedback response |
| `run_learning_loop` command | Backend Worker | `--run-once` / `--status` / default interval scheduler; mirrors `run_cognition_loop.py` |
| Flywheel status + run API | Backend Worker | `GET ai/pulse/learning-status/` (view_console) + `POST ai/pulse/learning-status/run/` (manage_console) |
| Durable store config | Backend Worker | `AI_STORE_BACKEND=django` in `backend/.env` + `.env.example`; `learning-scheduler` sidecar in `docker-compose.yml` |
| Tests | Backend Worker | `backend/ai/tests/test_learning_trigger.py` |
| Learn-facts console | Frontend Worker | `LearningFlywheelPanel` (status cards + recent facts + Run-sweep button), `aiPulse.js` helpers, route + sidebar entry |

---

## Acceptance criteria

1. **Real-time:** POSTing feedback to
   `/carbon-api/ai/workspace/conversations/{id}/messages/{id}/feedback/` writes a
   `KgFeedbackRecord` (and, for accepted/corrected, a `MemoryLongTerm` fact) in the same
   request, with `learned_at` set. A learning failure still returns the feedback 200/400
   and leaves `learned_at` NULL for the sweep to retry.
2. **Scheduler:** `python manage.py run_learning_loop --run-once` processes pending rows
   and prints JSON; `--status` prints `{"pending": N}`; the default mode runs an interval
   job until SIGINT/SIGTERM. `docker-compose.yml` runs it as a `learning-scheduler` sidecar.
3. **Console:** `GET ai/pulse/learning-status/` returns `{backend, pending, processed,
   by_outcome, facts, feedback_records}`; `POST ai/pulse/learning-status/run/` returns the
   sweep stats + refreshed status. The frontend panel renders status + a Run-sweep button
   gated on `ai:manage_console`.
4. **Durability:** `AI_STORE_BACKEND=django` is set in `.env`/`.env.example` so the real-time
   trigger and the sweep persist to Postgres.
5. **Gates:** `manage.py check` clean, no migration drift, `pytest ai dq accounts -q`
   (baseline 806 + new tests) green, `npm run lint` + `npm test` + `npm run build` green.

---

## Out of scope

- Auto-retry backoff / dead-letter queue for the sweep (the interval job is the retry).
- Surfacing `AIMessage`/`AIConversation` in the generic Pulse `PANEL_REGISTRY`.
- Weight-learning (KG edge weight updates) beyond `record_feedback`'s golden-pair logic.
