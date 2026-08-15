# TASK-DQ-LEVEL3-PULSE-SUGGEST

**Task ID:** DQ-LEVEL3-PULSE-SUGGEST  
**Status:** DONE (commits: 5478368)  
**Assigned to:** Worker (backend)  
**Depends on:** DQ-LEVEL2-PULSE (✅ complete — pulse_gateway.py exists)  
**Estimated effort:** 3-4 hours  
**Created:** 2026-08-09  

---

## 0. Context — What Already Exists

### 0.1 pulse_gateway.py (✅ done)
- `PulseGateway` class at `backend/pulse_gateway.py`
- Only has `validate_dq_rules()` for `dq.validate`
- Has `_build_dq_validate_payload()` helper
- Graceful degradation: timeout/unreachable → `pulse_unavailable`

### 0.2 Table profiling (✅ done)
- `profile_table(table_id)` in `dq/services.py` creates `TableProfile` + `FieldProfile` rows
- FieldProfile has: `row_count`, `null_count`, `distinct_count`, `completeness_pct`, `min_value`, `max_value`, `mean_value`, `top_values`
- TableProfile has summary JSON fields: `null_counts`, `distinct_counts`, `min_values`, `max_values`, `mean_values`

### 0.3 DQ API surface (✅ done)
- `POST /carbon-api/dq/profile/` — trigger profiling
- `POST /carbon-api/dq/run/` — run all rules
- `DQRuleViewSet` — CRUD for rules
- All views use `AdminOrSuperuserOnly` or `ReadAnyWriteGlobalAdmin`

### 0.4 Pulse contract (✅ spec written)
- `docs/PULSE_CONTRACT_SPEC.md` §3.2: `dq.suggest` — async, 60s timeout
- Payload: `{table: {name, description, row_count, fields: [{name, type, distinct_count, min, max, mean, stddev}]}}`
- Result: `{suggestions: [{prompt, rationale, suggested_severity, confidence}]}`

---

## 1. What To Build

### 1.1 `backend/pulse_gateway.py` — ADD `suggest_dq_rules()` method

Add to `PulseGateway` class after `validate_dq_rules()`:

```python
def suggest_dq_rules(self, table_profile: dict) -> dict:
    """Submit dq.suggest task. Async — 60s timeout.
    
    Args:
        table_profile: dict with keys name, description, row_count, fields
                       fields is list of {name, type, distinct_count, min, max, mean, stddev}
    
    Returns:
        Pulse response dict or {'status': 'pulse_unavailable', ...}
    """
    task_id = str(uuid.uuid4())
    payload = {
        'auth': {
            'instance_id': 'carbon',
            'api_key': self.api_key,
        },
        'task': {
            'id': task_id,
            'type': 'dq.suggest',
            'payload': {'table': table_profile},
        },
    }

    try:
        resp = requests.post(
            f'{self.base_url}/tasks',
            json=payload,
            timeout=60,  # async — Pulse may need time for LLM generation
            headers={'Content-Type': 'application/json'},
        )
        resp.raise_for_status()
        return resp.json()

    except requests.Timeout:
        logger.warning('Pulse suggest timeout for task %s', task_id)
        return {'status': 'pulse_unavailable', 'error': {'code': 'timeout'}}

    except requests.ConnectionError as exc:
        logger.warning('Pulse unreachable for suggest: %s', exc)
        return {'status': 'pulse_unavailable', 'error': {'code': 'unreachable'}}

    except Exception as exc:
        logger.error('Pulse suggest failed for task %s: %s', task_id, exc)
        return {'status': 'pulse_unavailable', 'error': {'code': 'unexpected', 'message': str(exc)}}
```

**Don't** refactor `validate_dq_rules` to share code. Duplicate the try/except block — each method is independently readable. The two methods diverge in timeout (10s vs 60s) and payload structure.

### 1.2 `backend/dq/services.py` — ADD `suggest_rules_for_table()` function

Add after the `run_dq()` function (before `_compute_quality`):

```python
def suggest_rules_for_table(table_id: int) -> dict:
    """Build a table profile payload and send it to Pulse for rule suggestions.

    If no current TableProfile exists, run profile_table() first.
    Returns:
        {
            'table_id': int,
            'status': 'completed' | 'pulse_unavailable',
            'suggestions': [ {prompt, rationale, suggested_severity, confidence} ],
            'error': None | {...}
        }
    """
    from pulse_gateway import PulseGateway

    table = DataTable.objects.get(id=table_id)
    fields = list(table.fields.filter(is_active=True))

    # Get or create profile
    tp = TableProfile.objects.filter(data_table=table).order_by('-profiled_at').first()
    if not tp:
        logger.info(f'No profile for table {table_id} — profiling now')
        profile_result = profile_table(table_id)
        tp = TableProfile.objects.filter(data_table=table).order_by('-profiled_at').first()
        if not tp:
            return {
                'table_id': table_id,
                'status': 'pulse_unavailable',
                'suggestions': [],
                'error': {'code': 'no_profile', 'message': 'Could not profile table'},
            }

    # Build field summaries from FieldProfile records
    field_profiles = FieldProfile.objects.filter(
        data_field__data_table=table
    ).select_related('data_field')

    fields_payload = []
    for fp in field_profiles:
        field_entry = {
            'name': fp.data_field.name,
            'type': fp.data_field.type,
            'distinct_count': fp.distinct_count,
            'completeness_pct': fp.completeness_pct,
        }
        # Add numeric stats if available
        if fp.min_value:
            field_entry['min'] = fp.min_value
        if fp.max_value:
            field_entry['max'] = fp.max_value
        if fp.mean_value is not None:
            field_entry['mean'] = round(fp.mean_value, 2)
        if fp.top_values:
            field_entry['top_values'] = fp.top_values[:3]

        fields_payload.append(field_entry)

    # Compute approximate stddev from min/max/mean when available
    for fe in fields_payload:
        if 'min' in fe and 'max' in fe and 'mean' in fe:
            try:
                rng = float(fe['max']) - float(fe['min'])
                fe['stddev'] = round(rng / 4, 2)  # Rough estimate
            except (ValueError, TypeError):
                pass

    table_payload = {
        'name': table.name,
        'description': table.title or table.name,
        'row_count': tp.row_count,
        'fields': fields_payload,
    }

    gateway = PulseGateway()
    response = gateway.suggest_dq_rules(table_payload)

    if response.get('status') == 'pulse_unavailable':
        return {
            'table_id': table_id,
            'status': 'pulse_unavailable',
            'suggestions': [],
            'error': response.get('error'),
        }

    suggestions = response.get('result', {}).get('suggestions', [])
    return {
        'table_id': table_id,
        'status': 'completed',
        'suggestions': suggestions,
        'error': None,
    }
```

### 1.3 `backend/dq/views.py` — ADD `DQSuggestView`

Add after `RunDQValidationView`:

```python
class DQSuggestView(APIView):
    """POST /carbon-api/dq/suggest/ — Get AI-suggested DQ rules for a table."""
    permission_classes = [AdminOrSuperuserOnly]

    @swagger_auto_schema(
        operation_description=(
            'Ask Pulse AI to suggest NL-based DQ rules for a table, '
            'using its current profile (field statistics, distributions). '
            'Returns a list of suggestions with prompts, rationale, severity, and confidence.'
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'data_table_id': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description='ID of the DataTable to suggest rules for'
                ),
            },
            required=['data_table_id'],
        ),
        responses={
            200: openapi.Response(description='Suggestions with prompts and rationale'),
            400: 'data_table_id is required',
            404: 'Table not found',
            503: 'Pulse unavailable',
        },
    )
    def post(self, request):
        table_id = request.data.get('data_table_id')
        if not table_id:
            return Response(
                {'error': 'data_table_id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            table = DataTable.objects.get(id=table_id)
        except DataTable.DoesNotExist:
            return Response(
                {'error': f'Table {table_id} not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        _check_table_access(request.user, table)

        try:
            result = suggest_rules_for_table(table_id)
        except Exception as exc:
            logger.error('Suggest failed for table %s: %s', table_id, exc)
            return Response(
                {'error': 'Suggest failed', 'detail': str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if result['status'] == 'pulse_unavailable':
            return Response(
                {
                    'table_id': table_id,
                    'status': 'pulse_unavailable',
                    'suggestions': [],
                    'message': 'Pulse AI is currently unavailable. Please try again later.',
                },
                status=status.HTTP_200_OK,  # 200 not 503 — this is a soft failure
            )

        return Response(result)
```

### 1.4 `backend/dq/urls.py` — ADD route

Add to `urlpatterns`:

```python
path('suggest/', DQSuggestView.as_view(), name='dq-suggest'),
```

Also add `DQSuggestView` to the imports from `.views`.

### 1.5 `backend/dq/serializers.py` — ADD response serializer (optional but nice)

```python
class DQSuggestResponseSerializer(serializers.Serializer):
    table_id = serializers.IntegerField()
    status = serializers.CharField()
    suggestions = serializers.ListField(child=serializers.DictField())
    error = serializers.DictField(required=False)
```

---

## 2. Tests To Write

### 2.1 `backend/dq/tests/test_phase3_suggest.py` — NEW FILE

| # | Test | What it verifies |
|---|------|-----------------|
| 1 | `test_suggest_endpoint_requires_table_id` | 400 if no data_table_id |
| 2 | `test_suggest_endpoint_table_not_found` | 404 for nonexistent table |
| 3 | `test_suggest_needs_profile` | If no profile exists, one is created first |
| 4 | `test_suggest_pulse_unavailable` | Mock Pulse timeout → 200 with pulse_unavailable status |
| 5 | `test_suggest_pulse_returns_suggestions` | Mock Pulse returns 2 suggestions → response includes them |
| 6 | `test_suggest_pulse_empty_suggestions` | Mock Pulse returns [] → response has empty list |
| 7 | `test_suggest_payload_matches_contract` | Gateway builds correct dq.suggest payload |
| 8 | `test_suggest_field_stats_in_payload` | Payload includes min/max/mean/stddev for numeric fields |
| 9 | `test_suggest_pulse_connection_error` | Mock ConnectionError → graceful degradation |

---

## 3. Files Changed (Summary)

| File | Action | Lines |
|------|--------|-------|
| `backend/pulse_gateway.py` | Add `suggest_dq_rules()` method | ~45 |
| `backend/dq/services.py` | Add `suggest_rules_for_table()` function | ~90 |
| `backend/dq/views.py` | Add `DQSuggestView` class | ~70 |
| `backend/dq/urls.py` | Add route + import | 2 |
| `backend/dq/serializers.py` | Add `DQSuggestResponseSerializer` | 6 |
| `backend/dq/tests/test_phase3_suggest.py` | **CREATE** — 9 tests | ~250 |

Total: ~220 lines of code, ~250 lines of tests.

---

## 4. Acceptance Gates

- [ ] **G1**: `POST /carbon-api/dq/suggest/` with valid `data_table_id` returns 200
- [ ] **G2**: If no TableProfile exists, one is auto-created before calling Pulse
- [ ] **G3**: Payload sent to Pulse matches `PULSE_CONTRACT_SPEC.md` §3.2
- [ ] **G4**: When Pulse returns suggestions, they're included in the response
- [ ] **G5**: When Pulse is unreachable, returns 200 with `status: pulse_unavailable` (never 503)
- [ ] **G6**: All 9 new tests pass
- [ ] **G7**: All existing DQ tests still pass — zero regressions
- [ ] **G8**: `pulse_gateway.py` imports nothing from Django ORM

---

## 5. Out of Scope (Not Now)

- UI for reviewing/accepting/rejecting suggestions (frontend work)
- Persisting accepted suggestions as DQRules (that's a separate `POST /dq/rules/` call)
- Re-running suggestions periodically
- Scoring/ranking suggestions
- `classification.infer` task type (Phase 3b)
- `anomaly.detect` task type (Phase 3c)

---

## 6. Reference

- Pulse contract: `docs/PULSE_CONTRACT_SPEC.md` §3.2 (`dq.suggest`)
- Existing gateway: `backend/pulse_gateway.py` (2 methods, add 3rd)
- Existing profiling: `backend/dq/services.py` → `profile_table()`
- Existing views: `backend/dq/views.py` (11 views, add 12th)
- Existing URLs: `backend/dq/urls.py` (9 routes, add 10th)
