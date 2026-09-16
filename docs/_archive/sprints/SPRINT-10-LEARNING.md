# Sprint 10 — Learning job: close the feedback flywheel

**Owner:** Master Architect · **Status:** 🔨 Spec written — ready for Backend Worker dispatch
**Goal:** The persisted `AIMessage.outcome` (Sprint 9) is **consumed** — a batch job
translates each judged message into engine feedback records + long-term memory, so the
AI actually learns from accept / reject / correct.

---

## Scope

| Piece | What | Included |
|---|---|---|
| `AIMessage.learned_at` + migration | idempotency marker ("has this been consumed?") | ✅ Phase 10-A |
| `ai/learning.py` — outcome→signal bridge | map outcome → engine `signal_type`, call engine feedback + memory | ✅ Phase 10-B |
| `learn_from_feedback` management command | batch job over unprocessed messages | ✅ Phase 10-C |
| Tests | pure mapping + end-to-end bridge + command idempotency | ✅ Phase 10-D |
| Real-time trigger on feedback POST | fire learning right after `record_feedback` | ⭕ deferred (Sprint 11) |
| Scheduler wiring / frontend console | cron/APScheduler + learn-facts UI | ⭕ deferred (Sprint 11) |

Do **not** touch the Sprint 9 endpoint, `record_feedback` (CarbonIntelligence), or the
frontend. This sprint is backend-only and **reuses** existing engine code — it writes
nothing new that already exists.

---

## Current state (verified facts — do not re-discover)

1. **Engine feedback logic already exists** — `backend/ai/engine/knowledge_graph/feedback.py`:
   - `quality_score_for(signal_type)` → `explicit_positive=1.0`, `export=0.9`,
     `explicit_negative=0.1`, `correction=0.0`, `rephrase=0.3`, `contradiction=0.2`,
     `abandonment=0.2`, default neutral `0.7`.
   - `record_feedback(db, *, instance_id, conversation_id, message_id, signal_type,
     user_id, original_utterance, resolved_utterance, generated_sql, corrected_sql,
     user_comment)` — **async**, creates `KgFeedbackRecord`, and auto-creates a
     `KgGoldenPair` when `signal_type == "correction" and corrected_sql`.
2. **Engine long-term memory already exists** — `backend/ai/engine/memory/long_term.py`:
   `LongTermMemory(db_session).store_fact(instance_id, category, content, source, confidence,
   host_user_id, visibility, ...)` — **async**, with semantic dedup + contradiction detection
   (the dedup/contradiction *queries* are `try/except`-tolerant). **Note:** the final
   `_vector.upsert(...)` was originally **not** guarded — this sprint wraps it in a
   `try/except` (see hazard #6) so a missing vector backend degrades gracefully instead of
   leaving `learned_at` unset.
3. **Engine models are Django models** in the single `ai` app namespace:
   - `from ai.models import KgFeedbackRecord, KgGoldenPair, MemoryLongTerm, AIMessage, AIConversation`
   - `KgFeedbackRecord` fields: `instance_id, conversation_id, message_id, signal_type,
     user_id, original_utterance, resolved_utterance, generated_sql, corrected_sql,
     user_comment, quality_score` + `AppScopeMixin` (`app_identifier="carbon"`,
     `visibility="private"`, `org_unit_id`/`host_user_id` null by default).
   - `MemoryLongTerm` fields: `instance_id, category, content, source, confidence, ...`.
   - ⚠️ A **separate** `Feedback` model also exists (`ai/models/core.py:142`) with just
     `message_id/rating/correction_text`. **Do NOT use it** — it is a vendored leftover with
     no quality scoring or golden-pair linkage. Use `record_feedback` → `KgFeedbackRecord`.
4. **Store seam** — `backend/ai/store.py`:
   - `get_store()` returns the configured `Store` (selected by `settings.AI_STORE_BACKEND`).
   - **Default is `"inmemory"`** (`backend/config/settings.py:469`). `"django"` = `DjangoStore`
     (persists via Django ORM). The learning job MUST run with `AI_STORE_BACKEND="django"`
     for durable learning; the `inmemory` backend drops writes. Production must set it.
   - `get_store().get_session_factory(instance_id)` → a session factory; calling it yields an
     async `Session` with `add / commit / select / flush` (DjangoStore wraps Django ORM via
     `sync_to_async`).
   - `DEFAULT_APP_IDENTIFIER = "carbon"` is exported from `ai.store` — use it as `instance_id`.
5. **Sync→async bridge precedent** — `backend/ai/management/commands/run_cognition_loop.py`
   runs async engine code from a sync command via `asyncio.run(...)`. Use the same pattern.
6. **`AIMessage` (Sprint 9)** already has `outcome` (accepted/rejected/corrected/ignored, null
   when unset) and `correction_text` (default `""`). It does **NOT** yet have `learned_at`.

---

## Phase 10-A — idempotency field + migration

File: `backend/ai/models/workspace.py`

Add to `AIMessage` (after `correction_text`):

```python
    learned_at = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        help_text="Set once this message's outcome has been consumed by the learning job.",
    )
```

Generate the migration (`makemigrations ai`). No data migration needed.

---

## Phase 10-B — the bridge module `ai/learning.py`

**New file:** `backend/ai/learning.py`

> **Import style (CRITICAL):** this module lives under `ai/` and talks to engine internals,
> so use **`ai.*` imports throughout** (matching `ai/store.py`, `ai/engine/*`,
> `ai/workspace_api.py`). Do **not** use `backend.ai.*` here. The exact imports:
>
> ```python
> import asyncio
> import logging
>
> from django.utils import timezone
>
> from ai.models import AIMessage
> from ai.store import DEFAULT_APP_IDENTIFIER, get_store
> from ai.engine.knowledge_graph.feedback import record_feedback
> from ai.engine.memory.long_term import LongTermMemory
> ```

### 10-B1 — pure mapping (unit-testable, no I/O)

```python
# outcome -> engine feedback signal_type. "ignored" is intentionally absent:
# an explicit dismiss carries no learnable signal.
OUTCOME_SIGNAL_MAP = {
    "accepted": "explicit_positive",
    "rejected": "explicit_negative",
    "corrected": "correction",
}

LEARNABLE_OUTCOMES = list(OUTCOME_SIGNAL_MAP.keys())  # ["accepted", "rejected", "corrected"]
```

### 10-B2 — `learn_from_message(message)` (sync entry, bridges to async)

```python
def learn_from_message(message) -> bool:
    """Consume one judged AIMessage into the engine. Returns True on success.

    No-op (returns False) when message.outcome is not learnable.
    Marks message.learned_at on success; leaves it null on failure (retry).
    """
    signal_type = OUTCOME_SIGNAL_MAP.get(message.outcome)
    if signal_type is None:
        return False
    asyncio.run(_learn_async(message, signal_type))
    message.learned_at = timezone.now()
    message.save(update_fields=["learned_at"])
    return True
```

### 10-B3 — `_learn_async(message, signal_type)`

```python
async def _learn_async(message, signal_type) -> None:
    instance_id = DEFAULT_APP_IDENTIFIER
    conversation_id = str(message.conversation_id)
    message_id = str(message.id)
    user_id = str(message.conversation.user_id) if message.conversation.user_id else ""
    content = message.content or ""

    factory = get_store().get_session_factory(instance_id)
    session = factory()
    async with session:
        # 1) Record the feedback signal (KgFeedbackRecord + golden-pair logic).
        await record_feedback(
            db=session,
            instance_id=instance_id,
            conversation_id=conversation_id,
            message_id=message_id,
            signal_type=signal_type,
            user_id=user_id,
            original_utterance=content,
            resolved_utterance=content,
            generated_sql="",
            corrected_sql=None,       # chat/text answers carry no SQL; never fabricate
            user_comment=message.correction_text or None,
        )

        # 2) Persist long-term memory facts.
        memory = LongTermMemory(session)
        if signal_type == "correction" and message.correction_text:
            await memory.store_fact(
                instance_id=instance_id,
                category="correction",
                content=message.correction_text,
                source="feedback",
                confidence=1.0,
                host_user_id=str(message.conversation.user_id) if message.conversation.user_id else None,
                visibility="private",
            )
        elif signal_type == "explicit_positive" and content:
            await memory.store_fact(
                instance_id=instance_id,
                category="learned",
                content=content[:1000],
                source="feedback",
                confidence=1.0,
                host_user_id=str(message.conversation.user_id) if message.conversation.user_id else None,
                visibility="private",
            )
```

> **`rejected` deliberately writes no memory fact** — a rejection is negative signal on
> the `KgFeedbackRecord` (score 0.1), not a durable fact to remember.

### 10-B4 — `learn_all_pending(limit=None)` (batch)

```python
def learn_all_pending(limit=None) -> dict:
    """Process all unlearned judged messages. Returns a stats dict."""
    qs = (
        AIMessage.objects
        .filter(outcome__in=LEARNABLE_OUTCOMES, learned_at__isnull=True)
        .select_related("conversation")
        .order_by("created_at")
    )
    if limit:
        qs = qs[:limit]

    stats = {"processed": 0, "accepted": 0, "rejected": 0, "corrected": 0, "errors": 0}
    for message in qs:
        try:
            if learn_from_message(message):
                stats["processed"] += 1
                stats[message.outcome] += 1
        except Exception:
            logger.exception("learning failed for message %s", message.id)
            stats["errors"] += 1
    return stats
```

---

## Phase 10-C — management command

**New file:** `backend/ai/management/commands/learn_from_feedback.py`

Mirror `run_cognition_loop.py` (BaseCommand). Add `--limit N` (default: no limit) and
`--dry-run` (count + list candidates without writing; do **not** set `learned_at` or call
the engine).

```python
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Consume unprocessed AIMessage feedback into the engine (KG + long-term memory)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        from ai.learning import learn_all_pending, LEARNABLE_OUTCOMES
        from ai.models import AIMessage
        if options["dry_run"]:
            qs = AIMessage.objects.filter(outcome__in=LEARNABLE_OUTCOMES, learned_at__isnull=True)
            self.stdout.write(f"pending: {qs.count()}")
            return
        stats = learn_all_pending(limit=options["limit"])
        self.stdout.write(json.dumps(stats))
```

(Remember `import json`.)

---

## Phase 10-D — tests

**New file:** `backend/ai/tests/test_learning.py`

Use `from django.test import override_settings` and a fixture that resets the store before
each test (the store singleton is cached):

```python
import pytest
from django.test import override_settings
from ai.store import reset_store

@pytest.fixture(autouse=True)
def _django_store(settings):
    settings.AI_STORE_BACKEND = "django"
    reset_store()
    yield
    reset_store()
```

Cover:
1. **Pure mapping** — `OUTCOME_SIGNAL_MAP == {"accepted": "explicit_positive",
   "rejected": "explicit_negative", "corrected": "correction"}` and `LEARNABLE_OUTCOMES`
   excludes `"ignored"`.
2. **accepted** → `learn_from_message` returns True, sets `learned_at`, creates one
   `KgFeedbackRecord` with `signal_type="explicit_positive"` + one `MemoryLongTerm`
   with `category="learned"` and `content == message.content`.
3. **corrected** → `KgFeedbackRecord` `signal_type="correction"` with
   `user_comment == correction_text`, plus a `MemoryLongTerm` `category="correction"`
   with `content == correction_text`.
4. **rejected** → `KgFeedbackRecord` `signal_type="explicit_negative"`, **no**
   `MemoryLongTerm` created.
5. **ignored / unset outcome** → `learn_from_message` returns False, `learned_at` stays null,
   no `KgFeedbackRecord` created.
6. **failure leaves retryable** — patch `ai.learning._learn_async` to raise; assert
   `learn_from_message` raises (or is caught by the caller) and `learned_at` remains null.
7. **`learn_all_pending` idempotency** — seed 3 judged messages (accepted/corrected/rejected)
   + 1 ignored + 1 unset; run `learn_all_pending()` → `processed == 3`, stats correct; run
   again → `processed == 0` (all marked learned).
8. **management command** — `call_command("learn_from_feedback", "--limit", "2")` processes
   at most 2; `--dry-run` reports count without writing (`learned_at` stays null).

> Import models via `from ai.models import AIMessage, AIConversation, KgFeedbackRecord,
> MemoryLongTerm`. Create fixtures via Django ORM (no HTTP) — see `test_message_feedback.py`
> for the `User` + `AIConversation` + `AIMessage` fixture pattern.

---

## Verification gates (run ALL, fix until green)

```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai dq accounts -q
```

- `makemigrations --check` reports **no drift**.
- Baseline **798 passed** (after Sprint 9) + new learning tests.
- If the command smoke-tests cleanly, also run:
  `cd backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py learn_from_feedback --dry-run`

---

## Critical hazards

1. **`AI_STORE_BACKEND` default is `inmemory`.** The learning job must run with
   `AI_STORE_BACKEND=django` or engine writes are silently dropped. Tests override it via
   `settings.AI_STORE_BACKEND = "django"` + `reset_store()`. **Flag to Master if production
   env does not set it** — do not silently hardcode it in code.
2. **Do NOT use the vendored `Feedback` model** (`ai/models/core.py`) — use
   `record_feedback` → `KgFeedbackRecord` (quality-scored + golden-pair capable).
3. **Dual-namespace hazard:** `ai/learning.py` uses `ai.*` imports only. Never mix
   `backend.ai.*` in this file.
4. **Never fabricate `corrected_sql`.** Chat/text corrections have no SQL; pass
   `corrected_sql=None` and `user_comment=correction_text`. Golden-pair creation for text
   is intentionally skipped (that path is SQL-only).
5. **Idempotency is mandatory** — the `learned_at IS NULL` filter plus set-on-success
   (not set-on-failure) is what makes re-runs safe. Do not mark `learned_at` before the
   engine write succeeds.
6. **Vector store may be absent** (chromadb not installed). The dedup/contradiction queries
   already tolerate this, but the final `await self._vector.upsert(...)` in `store_fact` was
   **not** guarded — it raised `ImportError` *after* the fact was committed, which would leave
   `learned_at` unset and retry the message forever. **Fix (done):** wrap the final upsert in
   `try/except Exception` + `logger.warning`, mirroring the dedup/contradiction guards. Do NOT
   add a hard chroma dependency and do NOT skip the durable fact write (which commits before
   the upsert).
7. **`asyncio.run` bridge** mirrors `run_cognition_loop.py`; do not run inside an already
   running loop (the management command / pytest are sync, so this is safe).
