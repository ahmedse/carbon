# Observability & Logging Standard
# Read by: Backend Worker, DevOps Worker, Debugger/Fixer.
# Purpose: consistent, useful logs so problems are diagnosable without a debugger.

---

## RULE 1 — Use the Logger, Never `print()`

```python
# WRONG — print goes nowhere useful in production, no level, no context
print("inference done", result)

# CORRECT
import logging
logger = logging.getLogger(__name__)          # module-scoped, once per file
logger.info("Inference complete", extra={"run_id": run.id, "engine": engine.name})
```

- One `logger = logging.getLogger(__name__)` per module.
- `print()` is allowed ONLY in management commands / scripts / experiments (user-facing CLI output).
- This codebase has `print()` debt — verify.sh flags it; convert on touch (do the right thing).

---

## RULE 2 — Log Levels (use the right one)

| Level | Use for | Example |
|-------|---------|---------|
| `DEBUG` | Dev-time detail, verbose tracing | payload contents, intermediate values |
| `INFO` | Normal significant events | "forecast run started", "model promoted" |
| `WARNING` | Unexpected but handled | "actuals missing, using fallback" |
| `ERROR` | A failure that needs attention | "inference failed for run X" |
| `CRITICAL` | System-level failure | "cannot reach database" |

- Production default level is WARNING/INFO (see config). DEBUG is never on in prod.
- Don't cry wolf: routine events are INFO, not WARNING. Reserve ERROR for real failures.

---

## RULE 3 — Log Exceptions With Context

```python
try:
    result = service.run(run_id)
except Exception:
    logger.exception("Inference failed", extra={"run_id": run_id})   # includes traceback
    raise   # or handle — but never swallow silently
```

- Use `logger.exception(...)` inside an `except` — it captures the traceback automatically.
- NEVER `except: pass`. NEVER swallow an exception to make an error "go away".
- Include identifying context (ids, names) so a log line is actionable on its own.

---

## RULE 4 — Structured & Correlatable

- Prefer key/value context (`extra={...}`) over string-concatenated blobs.
- Carry a correlation id (run_id / request id) through a pipeline so one operation's logs
  can be stitched together.
- Log at boundaries: request in/out, external call in/out, job start/finish.

---

## RULE 5 — Never Log Secrets or PII

- NEVER log passwords, tokens, API keys, full auth headers, or personal data.
- Redact/omit sensitive fields before logging a payload.
- This includes terminal output and TASK-RESULTS.md — see security.md.

---

## RULE 6 — Log Volume Discipline

- No logging inside tight loops at INFO+ (floods the log, hides signal). Aggregate or DEBUG.
- One clear line per significant event beats ten noisy ones.
- Errors logged once, at the layer that has the context — not re-logged at every catch level.

---

## RULE 7 — Frontend Observability

- Dev: `console.error`/`console.warn` for real problems; strip stray `console.log` before done.
- User-facing errors go through the app's error boundary / notification system, not raw console.
- Network failures: surface a retriable UI state (see design-system 4-states), and log the detail.

---

## What Good Looks Like (checklist)

```
[ ] module logger, no print() in app code
[ ] right level for each event (INFO normal, ERROR = real failure)
[ ] logger.exception in except blocks, with ids in extra=
[ ] no secrets/PII in any log line
[ ] correlation id threaded through multi-step operations
[ ] no INFO logging inside hot loops
```

---

## Anti-Patterns (reject in review)

- `print()` in application code (services, views, models, engines)
- `except: pass` / swallowed exceptions
- Logging a secret, token, or full request header
- WARNING/ERROR for routine events (alert fatigue)
- Logging inside a per-row loop at INFO
- String-blob logs with no identifying context
