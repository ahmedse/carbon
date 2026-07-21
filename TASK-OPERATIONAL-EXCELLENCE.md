# TASK: Data Trust Core — Operational Excellence (Track E)

**Status:** Ready for worker execution  
**Track:** E (Operational Excellence - Logging, Performance, Resilience)  
**Dependencies:** Tracks A, B, C, D complete (80% Phase 1 done)  
**Estimated Scope:** Medium complexity, 3 deliverables

---

## Context

The Data Trust Core backend has all functional capabilities in place:
- ✅ **Track A (DQ Execution):** 81 tests, 6 rule types, profiling + metrics
- ✅ **Track B (Governance Audit):** Full audit trail with queryable events
- ✅ **Track C (API Documentation):** Swagger docs, soft-delete, error handling
- ✅ **Track D (Reference Data Governance):** Temporal validity + lifecycle management

**Current Operational State:**
- ⚠️ **Logging:** Basic Python logging (text format), no correlation IDs, no performance metrics
- ⚠️ **Performance:** No query optimization analysis, potential N+1 queries in list endpoints
- ⚠️ **Resilience:** Limited error recovery, no chunking for large datasets

**User's Strategic Request:**
> "what next toward completing the data trust core modules? in backend first."

**Phase 1 Exit Criteria (from roadmap):**
- "Structured JSON logs for all operations"
- "No N+1 queries in list endpoints"
- "Profiling a 100k-row table doesn't crash on memory spike"

This is the **final track** to achieve 100% Phase 1 backend completion before frontend integration or Phase 2.

---

## Objectives

1. **Structured Logging:** Implement JSON logging with correlation IDs, user context, and performance metrics
2. **Performance Optimization:** Eliminate N+1 queries, add database indices, implement query optimization
3. **Resilience & Error Recovery:** Handle large datasets gracefully, add retry logic, improve error messages

---

## Deliverables

### **E1: Structured Logging & Observability**

**Goal:** Enable production debugging and performance monitoring through structured logs.

#### Current Logging Configuration

**[`backend/config/settings.py:253-289`](backend/config/settings.py:253-289):**
```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": get_env("ROOT_LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": True},
        "rest_framework": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "ai_copilot": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}
```

**Problems:**
- Text format (hard to parse, no structured querying)
- No request correlation IDs (can't trace user actions across requests)
- No timing metrics (can't identify slow operations)
- Inconsistent logging across modules (some use logger, some use print)

#### Implementation: JSON Logging with python-json-logger

**Install python-json-logger:**
```bash
pip install python-json-logger
# Add to requirements.txt
```

**Enhanced Logging Configuration:**
```python
# backend/config/settings.py
import os
from pythonjsonlogger import jsonlogger

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s %(pathname)s %(lineno)d",
        },
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if os.getenv("LOG_FORMAT", "json") == "json" else "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/carbon.log",
            "maxBytes": 10 * 1024 * 1024,  # 10MB
            "backupCount": 5,
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": get_env("ROOT_LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django.request": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False,
        },
        "catalog": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "mdm": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "dq": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
```

#### Correlation ID Middleware

**Create middleware to inject correlation IDs:**
```python
# backend/core/middleware.py
import uuid
import logging
import time
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(MiddlewareMixin):
    """Add correlation ID to each request and log request/response."""
    
    def process_request(self, request):
        # Generate or extract correlation ID
        correlation_id = request.headers.get('X-Correlation-ID', str(uuid.uuid4()))
        request.correlation_id = correlation_id
        request.start_time = time.time()
        
        # Log incoming request
        logger.info(
            "Request started",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.path,
                "user": str(request.user) if hasattr(request, 'user') else 'anonymous',
                "user_id": request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None,
                "remote_addr": self.get_client_ip(request),
            }
        )
        return None
    
    def process_response(self, request, response):
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            logger.info(
                "Request completed",
                extra={
                    "correlation_id": getattr(request, 'correlation_id', 'unknown'),
                    "method": request.method,
                    "path": request.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                    "slow_request": duration > 5.0,  # Flag requests > 5s
                }
            )
            # Add correlation ID to response headers
            response['X-Correlation-ID'] = request.correlation_id
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
```

**Register middleware:**
```python
# backend/config/settings.py
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.RequestLoggingMiddleware',  # Add here
    'django.contrib.sessions.middleware.SessionMiddleware',
    # ... rest of middleware
]
```

#### Enhanced Logging in ViewSets

**Add structured logging to key operations:**
```python
# Example: backend/dq/views.py
import logging

logger = logging.getLogger(__name__)

class ProfileTriggerView(APIView):
    def post(self, request):
        table_id = request.data.get('data_table_id')
        correlation_id = getattr(request, 'correlation_id', 'unknown')
        
        logger.info(
            "DQ profiling triggered",
            extra={
                "correlation_id": correlation_id,
                "user_id": request.user.id,
                "table_id": table_id,
                "action": "dq_profile_start",
            }
        )
        
        start = time.time()
        try:
            result = profile_table(table_id)
            duration = time.time() - start
            
            logger.info(
                "DQ profiling completed",
                extra={
                    "correlation_id": correlation_id,
                    "table_id": table_id,
                    "duration_ms": round(duration * 1000, 2),
                    "row_count": result.get('row_count', 0),
                    "field_count": result.get('field_count', 0),
                    "action": "dq_profile_success",
                }
            )
            return Response(result)
        except Exception as e:
            logger.error(
                "DQ profiling failed",
                extra={
                    "correlation_id": correlation_id,
                    "table_id": table_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "action": "dq_profile_error",
                },
                exc_info=True
            )
            raise
```

**Acceptance Criteria:**
- [ ] JSON logging enabled (can be toggled via `LOG_FORMAT` env var)
- [ ] All API requests include correlation ID in logs and response headers
- [ ] Requests >5s flagged with `slow_request: true` in logs
- [ ] All DQ operations (profile, run) log start/completion with timing
- [ ] All governance events (create/update/delete) log with user context
- [ ] Log files rotate at 10MB with 5 backups
- [ ] Can query logs: `grep correlation_id logs/carbon.log | jq`

---

### **E2: Performance Optimization**

**Goal:** Eliminate N+1 queries and optimize database access patterns for production-scale data.

#### Query Optimization Analysis

**Current N+1 Query Risks:**

1. **AssetProfile list with domain/steward:**
```python
# backend/catalog/views.py - AssetProfileViewSet.get_queryset()
# Problem: Each asset fetches domain + steward separately
qs = AssetProfile.objects.filter(...)
# Solution: Use select_related
qs = AssetProfile.objects.select_related('domain', 'data_table', 'steward').filter(...)
```

2. **ReferenceSet list with values count:**
```python
# backend/mdm/views.py - ReferenceSetViewSet.get_queryset()
# Problem: Serializer calls ref_set.values.count() for each set (N queries)
# Solution: Annotate in queryset
from django.db.models import Count
qs = ReferenceSet.objects.annotate(
    values_count=Count('values', filter=Q(values__is_active=True))
).select_related('domain', 'steward')
```

3. **DQResult list with rule details:**
```python
# backend/dq/views.py - DQResultViewSet.get_queryset()
# Problem: Each result fetches rule + data_table separately
# Solution:
qs = DQResult.objects.select_related('rule', 'data_table').filter(...)
```

#### Database Indices

**Add migrations for frequently queried fields:**
```python
# backend/catalog/migrations/0004_add_performance_indices.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0003_alter_governancepolicy_options_and_more'),
    ]
    
    operations = [
        migrations.AddIndex(
            model_name='assetprofile',
            index=models.Index(fields=['is_active', 'domain'], name='assetprof_active_domain_idx'),
        ),
        migrations.AddIndex(
            model_name='assetprofile',
            index=models.Index(fields=['quality_status'], name='assetprof_quality_idx'),
        ),
        migrations.AddIndex(
            model_name='governanceevent',
            index=models.Index(fields=['-timestamp', 'entity_type'], name='govevent_time_type_idx'),
        ),
    ]

# backend/mdm/migrations/0005_add_performance_indices.py
class Migration(migrations.Migration):
    dependencies = [
        ('mdm', '0004_reference_set_lifecycle'),
    ]
    
    operations = [
        migrations.AddIndex(
            model_name='referenceset',
            index=models.Index(fields=['is_active', 'domain'], name='refset_active_domain_idx'),
        ),
        migrations.AddIndex(
            model_name='referencevalue',
            index=models.Index(fields=['reference_set', 'is_active'], name='refval_set_active_idx'),
        ),
        migrations.AddIndex(
            model_name='referencevalue',
            index=models.Index(fields=['valid_from', 'valid_to'], name='refval_validity_idx'),
        ),
    ]

# backend/dq/migrations/0003_add_performance_indices.py
class Migration(migrations.Migration):
    dependencies = [
        ('dq', '0002_alter_dqrule_params'),
    ]
    
    operations = [
        migrations.AddIndex(
            model_name='dqresult',
            index=models.Index(fields=['-executed_at', 'rule'], name='dqresult_time_rule_idx'),
        ),
        migrations.AddIndex(
            model_name='dqresult',
            index=models.Index(fields=['passed'], name='dqresult_passed_idx'),
        ),
    ]
```

#### Caching for Immutable Reference Data

**Implement simple caching for active reference sets:**
```python
# backend/mdm/views.py
from django.core.cache import cache
from django.conf import settings

class ReferenceSetViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        # Cache key: reference_sets_{user_id}
        cache_key = f"reference_sets_{self.request.user.id}"
        cache_timeout = 300  # 5 minutes
        
        cached_ids = cache.get(cache_key)
        if cached_ids is not None and not settings.DEBUG:
            return ReferenceSet.objects.filter(id__in=cached_ids)
        
        # Compute queryset (with RBAC filtering)
        qs = self._compute_queryset()
        cache.set(cache_key, list(qs.values_list('id', flat=True)), cache_timeout)
        return qs
    
    def perform_create(self, serializer):
        instance = serializer.save(...)
        # Invalidate cache on write
        cache.delete_pattern('reference_sets_*')
        emit_governance_event(...)
    
    def perform_update(self, serializer):
        instance = serializer.save()
        cache.delete_pattern('reference_sets_*')
        emit_governance_event(...)
```

**Acceptance Criteria:**
- [ ] All list ViewSets use `select_related()` for foreign keys
- [ ] All count queries use `annotate(Count())` instead of serializer-level iteration
- [ ] Database indices added for: `is_active`, `domain`, `quality_status`, `timestamp`, `valid_from/valid_to`
- [ ] Reference set list completes in <500ms (with 1000 sets)
- [ ] Asset profile list completes in <2s (with 10k assets)
- [ ] No N+1 queries detected by Django Debug Toolbar in list endpoints
- [ ] Cache invalidation works (updates immediately visible after write)

---

### **E3: Resilience & Error Recovery**

**Goal:** Handle edge cases gracefully (large datasets, transient errors, partial failures).

#### Chunked Processing for Large Datasets

**Problem:** Profiling 100k-row table loads all rows into memory → OOM crash

**Solution: Implement chunked iterator:**
```python
# backend/dq/services.py
def _rows(table, chunk=False):
    """Return DataRows for a table. If chunk=True yield lists of CHUNK_SIZE."""
    qs = DataRow.objects.filter(data_table=table, is_archived=False)
    if not chunk:
        return list(qs.iterator())  # Use iterator() to avoid caching
    
    CHUNK_SIZE = 1000
    # Yield in chunks
    batch = []
    for row in qs.iterator(chunk_size=CHUNK_SIZE):
        batch.append(row)
        if len(batch) >= CHUNK_SIZE:
            yield batch
            batch = []
    if batch:
        yield batch

def profile_table(table_id):
    """Profile table metrics with chunked processing for large tables."""
    table = DataTable.objects.get(id=table_id)
    
    # Use chunked processing for row count > 10k
    row_count = DataRow.objects.filter(data_table=table, is_archived=False).count()
    use_chunks = row_count > 10000
    
    if use_chunks:
        logger.info(f"Using chunked processing for table {table_id} ({row_count} rows)")
        # Process in chunks, aggregate results
        field_metrics = {}
        for chunk in _rows(table, chunk=True):
            chunk_metrics = _compute_chunk_metrics(chunk, table.fields)
            _merge_metrics(field_metrics, chunk_metrics)
        return field_metrics
    else:
        # Original in-memory processing
        rows = _rows(table, chunk=False)
        return _compute_metrics(rows, table.fields)
```

#### Transient Error Handling

**Add retry logic for DB connection errors:**
```python
# backend/core/utils.py
import time
import logging
from functools import wraps
from django.db import OperationalError

logger = logging.getLogger(__name__)

def retry_on_db_error(max_retries=3, backoff=2.0):
    """Decorator to retry operations on transient DB errors."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    if attempt < max_retries - 1:
                        sleep_time = backoff ** attempt
                        logger.warning(
                            f"DB error in {func.__name__}, retrying in {sleep_time}s",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt + 1,
                                "error": str(e),
                            }
                        )
                        time.sleep(sleep_time)
                    else:
                        logger.error(
                            f"DB error in {func.__name__}, max retries exhausted",
                            extra={"function": func.__name__, "error": str(e)}
                        )
                        raise
        return wrapper
    return decorator

# Usage in DQ service:
@retry_on_db_error(max_retries=3)
def profile_table(table_id):
    # ... profiling logic
```

#### Graceful Degradation for Missing Data

**Improve error messages with actionable guidance:**
```python
# backend/dq/views.py
class ProfileTriggerView(APIView):
    def post(self, request):
        table_id = request.data.get('data_table_id')
        
        try:
            table = DataTable.objects.get(pk=table_id)
        except DataTable.DoesNotExist:
            return Response(
                {
                    "error": "TableNotFound",
                    "message": f"DataTable with ID {table_id} does not exist",
                    "details": {
                        "table_id": [f"No table found with ID {table_id}. Verify the ID or check if the table was archived."]
                    },
                    "suggested_action": "Use GET /dataschema/tables/ to list available tables",
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if table has data
        row_count = table.rows.filter(is_archived=False).count()
        if row_count == 0:
            return Response(
                {
                    "error": "EmptyTable",
                    "message": f"Table '{table.title}' has no data rows to profile",
                    "details": {
                        "table_id": [f"Table {table_id} exists but contains 0 rows. Add data before profiling."]
                    },
                    "suggested_action": "Import data via POST /dataschema/rows/bulk-import/ first",
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Profile with chunking if needed
        result = profile_table(table_id)
        return Response(result)
```

**Acceptance Criteria:**
- [ ] Profiling 100k-row table completes without OOM (chunked processing)
- [ ] DB connection timeout retried 3 times with exponential backoff
- [ ] Empty table profiling returns 400 with actionable error message
- [ ] Missing table returns 404 with suggestion to list available tables
- [ ] Bulk operations handle partial failures without rolling back successful items
- [ ] Long operations (>30s) return 202 Accepted with status check endpoint (Phase 2: async)

---

## Implementation Guidelines

### Technology Stack (Minimal New Dependencies)
- `python-json-logger` (new) — Structured JSON logging
- Django caching (built-in) — Reference data caching
- Django ORM optimization (built-in) — `select_related`, `prefetch_related`, `annotate`
- Django migrations (built-in) — Database indices

### Testing Protocol
1. **Load Testing:**
   - Create 10k AssetProfiles, measure list endpoint response time (<2s)
   - Create 1k ReferenceS ets, measure list endpoint response time (<500ms)
   - Profile 100k-row table, verify chunked processing (no OOM)

2. **N+1 Query Detection:**
   - Use Django Debug Toolbar to verify 0 N+1 queries in list endpoints
   - Run `python manage.py debug_sql` (custom command) to analyze query patterns

3. **Logging Verification:**
   - Trigger DQ profiling, verify correlation ID in all log lines
   - Trigger slow request (sleep endpoint), verify `slow_request: true` flag
   - Parse logs with `jq`: `jq 'select(.action=="dq_profile_success")' logs/carbon.log`

4. **Coverage Target:** ≥75% for new utility functions (retry decorator, chunking logic)

### File Modification Checklist

**Files to Create:**
- [ ] `backend/core/middleware.py` — RequestLoggingMiddleware
- [ ] `backend/core/utils.py` — retry_on_db_error decorator
- [ ] `backend/catalog/migrations/0004_add_performance_indices.py`
- [ ] `backend/mdm/migrations/0005_add_performance_indices.py`
- [ ] `backend/dq/migrations/0003_add_performance_indices.py`
- [ ] `backend/core/tests/test_logging.py` — Logging tests
- [ ] `backend/core/tests/test_performance.py` — Load tests

**Files to Modify:**
- [ ] `backend/config/settings.py` — Enhanced LOGGING config, middleware registration
- [ ] `backend/dq/services.py` — Chunked processing, retry decorator
- [ ] `backend/catalog/views.py` — select_related optimization
- [ ] `backend/mdm/views.py` — select_related + caching
- [ ] `backend/dq/views.py` — Enhanced error messages, structured logging
- [ ] `requirements.txt` — Add python-json-logger

**No Changes Required:**
- Models (indices added via migrations)
- Serializers (no API changes)
- URL routing (no new endpoints)

---

## Testing Acceptance Criteria

### Automated Tests (Pytest)
Run all tests with coverage:
```bash
cd backend
pytest core/tests/test_logging.py -v
pytest core/tests/test_performance.py -v
pytest --cov=core --cov=catalog --cov=mdm --cov=dq --cov-report=term-missing
```

**Expected Output:**
- All tests pass (0 failures, 0 errors)
- Coverage ≥75% for new code
- No regressions in existing Track A/B/C/D tests

### Manual Verification Checklist

**E1 (Structured Logging):**
1. [ ] Set `LOG_FORMAT=json` in `.env`
2. [ ] Trigger `POST /dq/profile/` → verify JSON logs in `logs/carbon.log`
3. [ ] Check correlation ID in response header: `X-Correlation-ID`
4. [ ] Parse logs: `jq 'select(.action=="dq_profile_success")' logs/carbon.log`
5. [ ] Verify slow request flagged: `jq 'select(.slow_request==true)' logs/carbon.log`

**E2 (Performance):**
1. [ ] Create 1000 AssetProfiles via bulk-create
2. [ ] Load Django Debug Toolbar, access `GET /catalog/assets/`
3. [ ] Verify SQL queries panel shows <10 queries (no N+1)
4. [ ] Measure response time: `curl -w "%{time_total}" /catalog/assets/` (<2s)
5. [ ] Repeat for `GET /mdm/reference-sets/` (<500ms)

**E3 (Resilience):**
1. [ ] Profile empty table → verify 400 error with actionable message
2. [ ] Profile 100k-row table → verify chunked processing logs
3. [ ] Simulate DB timeout (kill connection mid-request) → verify retry logs
4. [ ] Bulk archive with mix of valid/invalid IDs → verify partial success response

---

## Out of Scope (Deferred to Phase 2)

**Explicitly NOT part of this task:**
- ❌ Celery/Redis async task queue — Phase 2
- ❌ Distributed tracing (OpenTelemetry, Jaeger) — Phase 3
- ❌ Metrics collection (Prometheus, Grafana) — Phase 3
- ❌ Application Performance Monitoring (APM) tools — Phase 3
- ❌ Load balancing / horizontal scaling — Infrastructure concern
- ❌ Database replication / read replicas — DBA concern
- ❌ CDN for static assets — Deployment concern

---

## Sequencing Within Track E

Execute deliverables in this order:

1. **E1 First (Logging):** Observability enables debugging E2/E3 issues
2. **E2 Next (Performance):** Optimization makes E3 resilience testing realistic
3. **E3 Last (Resilience):** Error handling builds on performant base

**Rationale:** Structured logging is a cross-cutting concern that benefits all subsequent work.

---

## Success Criteria

**Track E complete when:**
- [ ] JSON logging enabled with correlation IDs in all requests
- [ ] All list endpoints optimized (select_related, no N+1 queries)
- [ ] Database indices added for common query patterns
- [ ] Profiling 100k-row table completes without crash (chunked processing)
- [ ] DB connection errors retried with exponential backoff
- [ ] All error messages actionable (include suggested_action field)
- [ ] All tests pass with ≥75% coverage
- [ ] Load tests validate: assets list <2s, reference sets list <500ms
- [ ] Logs parseable with `jq` for analysis

---

## Phase 1 Completion Milestone

**Completing Track E achieves 100% Phase 1 Backend Roadmap:**
- ✅ Track A: DQ Execution (81 tests)
- ✅ Track B: Governance Audit (6 tests)
- ✅ Track C: API Documentation (95 tests)
- ✅ Track D: Reference Data Governance (48 tests)
- ✅ Track E: Operational Excellence (E1+E2+E3)

**Phase 1 Exit Gate:** Backend is production-ready with:
- Functional completeness (catalog, mdm, dq)
- Observability (structured logs, correlation IDs)
- Performance (optimized queries, indices)
- Resilience (error recovery, chunked processing)
- Documentation (Swagger, error messages)

**Next Steps After Track E:**
1. Frontend integration (DQ/Audit/Lifecycle UIs)
2. Integration testing with real AASTMT data
3. Phase 1 completion audit + handoff report
4. Phase 2 planning (async tasks, lineage, Pulse integration)

---

## Notes for Worker

### Key Constraints
1. **Do NOT introduce breaking changes** — All existing APIs must continue working
2. **Do NOT add new features** — This is purely operational polish
3. **Backward compatibility** — Support both JSON and text logging via env var
4. **Cache carefully** — Invalidate on writes to avoid stale data
5. **Test with real data** — Load test with 10k+ records, not just fixtures

### Common Pitfalls to Avoid
- ❌ Enabling caching without invalidation (stale data bugs)
- ❌ Adding indices without measuring impact (bloated DB)
- ❌ Logging sensitive data (passwords, tokens) in structured logs
- ❌ Chunked processing breaking transaction atomicity
- ❌ Retry logic on non-idempotent operations (duplicate writes)

### Quality Checklist Before Completion
- [ ] Run full test suite: `pytest --cov`
- [ ] Load test with 10k records: `python manage.py loadtest`
- [ ] Check log file rotation works: `ls -lh logs/carbon.log*`
- [ ] Verify correlation IDs consistent across logs
- [ ] Confirm no secrets logged in structured logs
- [ ] Test cache invalidation: update reference set, verify list reflects change immediately

---

## Deliverable Artifacts

Upon completion, provide:

1. **TASK-RESULT-OPERATIONAL-EXCELLENCE.md** — Completion report with:
   - Summary of implemented optimizations
   - Files modified (line counts)
   - Test results (pytest output + coverage)
   - Load test results (response times before/after)
   - Sample structured logs (JSON examples)
   - Known limitations or trade-offs

2. **Code Changes:**
   - RequestLoggingMiddleware
   - Enhanced LOGGING config
   - Database indices (migrations)
   - Query optimizations (select_related, annotate)
   - Chunked processing logic
   - Retry decorator
   - Test files

3. **Performance Benchmarks:**
   - Asset list response time (before/after)
   - Reference set list response time (before/after)
   - Large table profiling memory usage (before/after)
   - Query count analysis (Django Debug Toolbar screenshots)

---

## References

- [`plans/DATA_TRUST_CORE_BACKEND_COMPLETION_ROADMAP.md`](plans/DATA_TRUST_CORE_BACKEND_COMPLETION_ROADMAP.md:209-248) — Track E specification
- [`backend/config/settings.py:253-289`](backend/config/settings.py:253-289) — Current logging config
- [`backend/dq/services.py:16-30`](backend/dq/services.py:16-30) — Current _rows() implementation
- [`backend/catalog/views.py`](backend/catalog/views.py) — AssetProfileViewSet to optimize
- [`backend/mdm/views.py`](backend/mdm/views.py) — ReferenceSetViewSet to optimize
- Django ORM optimization guide: https://docs.djangoproject.com/en/4.2/topics/db/optimization/
- python-json-logger docs: https://github.com/madzak/python-json-logger

---

**END OF TASK SPECIFICATION**
