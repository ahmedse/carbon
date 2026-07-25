# Track E — Operational Excellence: Execution Plan

**Date:** 2026-07-25  
**Status:** Ready for Worker Execution  
**Track:** E (Final Phase 1 backend completion)  
**Dependencies:** Tracks A, B, C, D complete ✅

---

## Quick Start for Workers

**Your task:** Make the Carbon backend production-ready through logging, performance, and resilience hardening.

**Deliverables:**
1. **E1:** Structured JSON logging with correlation IDs
2. **E2:** Query optimization (eliminate N+1, add indices)
3. **E3:** Resilience (chunked processing, retry logic, error messages)

**Timeline:** Sequential execution (E1 → E2 → E3)  
**Exit Gate:** 100% Phase 1 backend completion

---

## Phase 1: E1 — Structured Logging & Observability

### What to Build

#### Step 1: Add python-json-logger dependency

**File:** `backend/requirements.txt`

Add this line:
```
python-json-logger==2.0.7
```

Then run:
```bash
cd backend
pip install python-json-logger
```

#### Step 2: Create RequestLoggingMiddleware

**File:** `backend/core/middleware.py` (NEW FILE)

```python
import uuid
import logging
import time
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(MiddlewareMixin):
    """Add correlation ID to each request and log request/response timing."""
    
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
                    "slow_request": duration > 5.0,
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

#### Step 3: Update LOGGING configuration

**File:** `backend/config/settings.py` (MODIFY around line 253)

Replace the entire LOGGING dict with:

```python
import os
from pythonjsonlogger import jsonlogger

# Ensure logs directory exists
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

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
            "filename": os.path.join(LOGS_DIR, "carbon.log"),
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

#### Step 4: Register middleware

**File:** `backend/config/settings.py` (MODIFY MIDDLEWARE list)

Add this line near the top of the MIDDLEWARE list (after CorsMiddleware but before SessionMiddleware):

```python
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.RequestLoggingMiddleware',  # ADD THIS
    'django.contrib.sessions.middleware.SessionMiddleware',
    # ... rest of middleware
]
```

#### Step 5: Add structured logging to DQ operations

**File:** `backend/dq/views.py` (MODIFY ProfileTriggerView.post method)

At the top of the file, add:
```python
import logging
import time

logger = logging.getLogger(__name__)
```

Find the `ProfileTriggerView.post()` method and add logging:

```python
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

#### Step 6: Test E1 Implementation

**Acceptance Criteria:**
- [ ] JSON logging enabled in `logs/carbon.log`
- [ ] All API requests include `X-Correlation-ID` in response headers
- [ ] Requests >5s flagged with `slow_request: true` in logs
- [ ] Logs are valid JSON (parseable with `jq`)
- [ ] Correlation IDs appear consistently across request start/completion logs

**Manual Test:**
```bash
cd backend
python manage.py runserver

# In another terminal:
curl -v http://localhost:8009/carbon-api/dq/profile/ -X POST \
  -H "Content-Type: application/json" \
  -d '{"data_table_id": 1}' \
  -H "Authorization: Bearer YOUR_TOKEN"

# Check logs:
tail -50 logs/carbon.log | jq '.'
```

---

## Phase 2: E2 — Performance Optimization

### What to Build

#### Step 1: Create performance index migrations

**File:** `backend/catalog/migrations/0004_add_performance_indices.py` (NEW FILE)

```python
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
```

**File:** `backend/mdm/migrations/0005_add_performance_indices.py` (NEW FILE)

```python
from django.db import migrations, models

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
```

**File:** `backend/dq/migrations/0003_add_performance_indices.py` (NEW FILE)

```python
from django.db import migrations, models

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

#### Step 2: Apply migrations

```bash
cd backend
python manage.py makemigrations catalog mdm dq
python manage.py migrate
```

#### Step 3: Optimize AssetProfileViewSet queries

**File:** `backend/catalog/views.py` (MODIFY AssetProfileViewSet.get_queryset around line 191)

Verify the `select_related` is already there (from F1.1 implementation):

```python
def get_queryset(self):
    ensure_asset_profiles()
    qs = AssetProfile.objects.select_related(
        'data_table', 'data_field', 'data_field__data_table',
        'domain', 'owner', 'steward', 'glossary_term',
    ).prefetch_related('tags')
    # ... RBAC + query params
```

**No change needed** — F1.1 already includes proper `select_related` and `prefetch_related`.

#### Step 4: Optimize ReferenceSetViewSet queries

**File:** `backend/mdm/views.py` (FIND ReferenceSetViewSet.get_queryset)

Add `select_related` for foreign key fields:

```python
def get_queryset(self):
    qs = ReferenceSet.objects.select_related(
        'domain', 'steward', 'created_by', 'updated_by'
    ).filter(
        is_active=True
    )
    
    # Annotate to avoid N+1 on value counts
    from django.db.models import Count, Q
    qs = qs.annotate(
        values_count=Count('values', filter=Q(values__is_active=True))
    )
    
    # RBAC scoping (add if needed)
    user = self.request.user
    if not (user.is_superuser or user.is_staff):
        org_units = list(
            ScopedRole.objects.filter(user=user, is_active=True)
            .values_list('org_unit_id', flat=True).distinct()
        )
        if org_units:
            qs = qs.filter(Q(domain__org_unit__in=org_units) | Q(domain__isnull=True))
    
    return qs.order_by('name')
```

#### Step 5: Optimize DQResultViewSet queries

**File:** `backend/dq/views.py` (FIND DQResultViewSet.get_queryset)

Add `select_related`:

```python
def get_queryset(self):
    qs = DQResult.objects.select_related(
        'rule', 'data_table', 'created_by'
    ).filter(
        is_archived=False
    )
    
    # Apply filters from query params
    if self.request.query_params.get('rule_id'):
        qs = qs.filter(rule_id=self.request.query_params['rule_id'])
    
    if self.request.query_params.get('passed'):
        qs = qs.filter(passed=self.request.query_params['passed'].lower() == 'true')
    
    return qs.order_by('-executed_at')
```

#### Step 6: Test E2 Implementation

**Acceptance Criteria:**
- [ ] No N+1 queries in list endpoints (verify with Django Debug Toolbar)
- [ ] Asset list endpoint returns in <2s (with 1000+ assets)
- [ ] Reference set list endpoint returns in <500ms (with 1000+ sets)
- [ ] Database indices successfully created

**Manual Test:**
```bash
cd backend
python manage.py shell

# Create 1000 reference sets
from mdm.models import ReferenceSet, OrgUnit
from django.contrib.auth.models import User

domain = OrgUnit.objects.first()
user = User.objects.first()

for i in range(1000):
    ReferenceSet.objects.create(
        name=f"RefSet_{i}",
        code=f"RS_{i}",
        domain=domain,
        created_by=user
    )

# Exit shell and test endpoint
exit()

time curl http://localhost:8009/carbon-api/mdm/reference-sets/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Phase 3: E3 — Resilience & Error Recovery

### What to Build

#### Step 1: Create retry decorator utility

**File:** `backend/core/utils.py` (NEW FILE or APPEND if exists)

```python
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
                            extra={
                                "function": func.__name__,
                                "error": str(e),
                                "max_attempts": max_retries
                            }
                        )
                        raise
        return wrapper
    return decorator
```

#### Step 2: Implement chunked processing for large tables

**File:** `backend/dq/services.py` (MODIFY profile_table function)

Find the existing `profile_table()` function and enhance it:

```python
from core.utils import retry_on_db_error
import logging

logger = logging.getLogger(__name__)

def _rows_chunked(table, chunk_size=1000):
    """Yield DataRows in chunks for memory-efficient processing."""
    qs = DataRow.objects.filter(data_table=table, is_archived=False)
    batch = []
    for row in qs.iterator(chunk_size=chunk_size):
        batch.append(row)
        if len(batch) >= chunk_size:
            yield batch
            batch = []
    if batch:
        yield batch

@retry_on_db_error(max_retries=3)
def profile_table(table_id):
    """Profile table metrics with chunked processing for large tables."""
    from dataschema.models import DataTable
    
    table = DataTable.objects.get(id=table_id)
    
    # Use chunked processing for row count > 10k
    row_count = DataRow.objects.filter(data_table=table, is_archived=False).count()
    use_chunks = row_count > 10000
    
    if use_chunks:
        logger.info(
            f"Using chunked processing for table {table_id}",
            extra={
                "table_id": table_id,
                "row_count": row_count,
                "use_chunks": True,
            }
        )
        # Process in chunks, aggregate results
        field_metrics = {}
        chunk_num = 0
        for chunk in _rows_chunked(table):
            chunk_num += 1
            chunk_metrics = _compute_chunk_metrics(chunk, table.fields)
            _merge_metrics(field_metrics, chunk_metrics)
            
            logger.debug(
                f"Processed chunk {chunk_num} for table {table_id}",
                extra={
                    "table_id": table_id,
                    "chunk_num": chunk_num,
                    "chunk_size": len(chunk),
                }
            )
        
        return field_metrics
    else:
        # Original in-memory processing for small tables
        rows = list(DataRow.objects.filter(data_table=table, is_archived=False).iterator())
        return _compute_metrics(rows, table.fields)
```

#### Step 3: Enhance error messages

**File:** `backend/dq/views.py` (MODIFY ProfileTriggerView.post)

```python
def post(self, request):
    from dataschema.models import DataTable
    from rest_framework.response import Response
    from rest_framework import status
    
    table_id = request.data.get('data_table_id')
    
    # Validate table exists
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
                "message": f"Table '{table.name}' has no data rows to profile",
                "details": {
                    "table_id": [f"Table {table_id} exists but contains 0 rows. Add data before profiling."]
                },
                "suggested_action": "Import data via POST /dataschema/rows/bulk-import/ first",
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Profile with error handling
    try:
        result = profile_table(table_id)
        return Response(result)
    except Exception as e:
        logger.error(
            "Unexpected error during profiling",
            extra={
                "table_id": table_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True
        )
        return Response(
            {
                "error": "ProfilingFailed",
                "message": f"An error occurred while profiling table {table_id}",
                "details": {"error": [str(e)]},
                "suggested_action": "Check server logs for details or contact administrator",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
```

#### Step 4: Test E3 Implementation

**Acceptance Criteria:**
- [ ] Profiling 100k-row table completes without OOM
- [ ] DB connection errors retried with exponential backoff
- [ ] Empty table returns 400 with actionable error message
- [ ] Missing table returns 404 with helpful guidance
- [ ] Retry logic properly logs backoff attempts

**Manual Test:**
```bash
cd backend
python manage.py shell

# Create empty table
from dataschema.models import DataTable
from core.models import Module
from mdm.models import OrgUnit

org_unit = OrgUnit.objects.first()
module = Module.objects.create(org_unit=org_unit, name="Test", scope=2)
empty_table = DataTable.objects.create(module=module, name="empty_test")

exit()

# Test empty table error
curl -X POST http://localhost:8009/carbon-api/dq/profile/ \
  -H "Content-Type: application/json" \
  -d '{"data_table_id": '"$(python -c 'from dataschema.models import DataTable; print(DataTable.objects.latest(\"id\").id)')"'}' \
  -H "Authorization: Bearer YOUR_TOKEN" | jq '.'
```

---

## Test & Verification

### Automated Tests

Create test files to verify all three deliverables:

**File:** `backend/core/tests/test_logging.py` (NEW FILE)

```python
from django.test import TestCase, RequestFactory
from core.middleware import RequestLoggingMiddleware
from django.contrib.auth.models import User
import logging

class LoggingMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = RequestLoggingMiddleware(lambda r: None)
        self.user = User.objects.create_user('testuser', password='test123')
    
    def test_correlation_id_added_to_request(self):
        request = self.factory.get('/api/test/')
        request.user = self.user
        self.middleware.process_request(request)
        self.assertTrue(hasattr(request, 'correlation_id'))
        self.assertTrue(len(request.correlation_id) > 0)
    
    def test_correlation_id_in_response_headers(self):
        from django.http import HttpResponse
        request = self.factory.get('/api/test/')
        request.user = self.user
        self.middleware.process_request(request)
        response = HttpResponse()
        self.middleware.process_response(request, response)
        self.assertIn('X-Correlation-ID', response)
```

**File:** `backend/core/tests/test_performance.py` (NEW FILE)

```python
from django.test import TestCase, TransactionTestCase
from catalog.models import AssetProfile, DataDomain
from mdm.models import ReferenceSet
from django.test.utils import override_settings
from django.db import connection
from django.test.utils import CaptureQueriesContext
import time

class QueryOptimizationTest(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create test data
        domain = DataDomain.objects.create(name="TestDomain")
        for i in range(100):
            AssetProfile.objects.create(
                name=f"Asset_{i}",
                domain=domain,
                classification="public"
            )
    
    def test_asset_list_no_n_plus_one(self):
        """Verify asset list endpoint doesn't have N+1 queries."""
        from catalog.views import AssetProfileViewSet
        from django.test import RequestFactory
        from django.contrib.auth.models import User
        
        factory = RequestFactory()
        request = factory.get('/catalog/assets/')
        request.user = User.objects.first() or User.objects.create_superuser('admin', password='test')
        
        viewset = AssetProfileViewSet()
        viewset.request = request
        
        with CaptureQueriesContext(connection) as ctx:
            list(viewset.get_queryset())
        
        # Should be minimal queries (not 100+ for N+1)
        self.assertLess(len(ctx), 10, f"Too many queries: {len(ctx)}")
    
    def test_reference_set_list_performance(self):
        """Verify reference set list completes quickly."""
        from mdm.views import ReferenceSetViewSet
        from django.test import RequestFactory
        from django.contrib.auth.models import User
        
        # Create many sets
        for i in range(500):
            ReferenceSet.objects.create(name=f"RS_{i}", code=f"rs_{i}")
        
        factory = RequestFactory()
        request = factory.get('/mdm/reference-sets/')
        request.user = User.objects.first() or User.objects.create_superuser('admin', password='test')
        
        viewset = ReferenceSetViewSet()
        viewset.request = request
        
        start = time.time()
        list(viewset.get_queryset())
        duration = time.time() - start
        
        # Should complete in <1 second
        self.assertLess(duration, 1.0, f"Query took {duration}s, should be <1s")
```

### Run Tests

```bash
cd backend
pytest core/tests/test_logging.py -v
pytest core/tests/test_performance.py -v
pytest --cov=core --cov=catalog --cov=mdm --cov=dq --cov-report=term-missing
```

---

## Completion Checklist

### E1: Structured Logging
- [ ] `backend/core/middleware.py` created
- [ ] `backend/requirements.txt` updated with python-json-logger
- [ ] LOGGING config updated in `settings.py`
- [ ] Middleware registered in MIDDLEWARE list
- [ ] DQ profiling logs structured JSON
- [ ] Correlation IDs appear in logs and response headers
- [ ] E1 tests pass

### E2: Performance Optimization
- [ ] 3 migration files created (catalog, mdm, dq)
- [ ] Migrations applied successfully
- [ ] `select_related` optimization in AssetProfileViewSet (already done in F1)
- [ ] `select_related` + `annotate` in ReferenceSetViewSet
- [ ] `select_related` in DQResultViewSet
- [ ] E2 tests pass
- [ ] Asset list endpoint <2s (load tested with 1000+ assets)
- [ ] Reference set list endpoint <500ms

### E3: Resilience
- [ ] `backend/core/utils.py` created with retry decorator
- [ ] Chunked processing in `profile_table()`
- [ ] Enhanced error messages with `suggested_action` field
- [ ] Empty table profiling returns 400 with actionable error
- [ ] Missing table returns 404 with guidance
- [ ] E3 tests pass
- [ ] 100k-row table profiles without OOM

### Final Verification
- [ ] Full test suite passes: `pytest`
- [ ] Coverage ≥75% for new code
- [ ] No regressions in Tracks A/B/C/D tests
- [ ] Build succeeds: `python manage.py check`
- [ ] Logs directory created with rotation working
- [ ] Structured logs parseable with `jq`

---

## Delivery Artifact

When complete, create: **`TASK-RESULT-OPERATIONAL-EXCELLENCE.md`**

Include:
1. Summary of implemented features (E1, E2, E3)
2. Files created/modified with line counts
3. Test results (pytest output + coverage %)
4. Performance benchmarks (before/after timings)
5. Sample structured logs (JSON examples)
6. Known limitations

---

## References

- [`TASK-OPERATIONAL-EXCELLENCE.md`](TASK-OPERATIONAL-EXCELLENCE.md) — Full spec
- [`backend/config/settings.py`](backend/config/settings.py) — Current settings
- Django ORM docs: https://docs.djangoproject.com/en/4.2/topics/db/optimization/
- python-json-logger: https://github.com/madzak/python-json-logger

---

**Ready to execute. Start with E1 (logging), then E2 (performance), then E3 (resilience).**
