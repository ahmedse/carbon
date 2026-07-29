# API Contract — Unified Shape for Every Endpoint
# Read by: Backend Worker (writing endpoints), Frontend Worker (consuming them).
# Purpose: every endpoint looks the same, so no worker reinvents response shapes.

---

## RULE 0 — Consult the Registry First

Before creating ANY endpoint:
```bash
grep -i "<resource>" .ai-toolkit/registry/api.md
```
If it exists → extend it. If a similar pattern exists → copy it. NEVER duplicate a route.

---

## Response Envelope (consistent everywhere)

### Success — single resource
```json
{ "id": 42, "field": "value", ... }
```

### Success — list (paginated, DRF default)
```json
{
  "count": 137,
  "next": "https://.../api/resource/?page=2",
  "previous": null,
  "results": [ { ... }, { ... } ]
}
```

### Error — ALWAYS this shape (never a bare string)
```json
{ "detail": "Human-readable message" }
// or field-level (DRF validation):
{ "field_name": ["This field is required."] }
```

**NEVER** return a raw string, a stack trace, or an inconsistent ad-hoc shape.

---

## HTTP Status Codes (use the right one, always)

| Code | When |
|------|------|
| 200 | GET/PUT/PATCH success |
| 201 | POST created a resource |
| 202 | Accepted, async work started (return a run_id to poll) |
| 204 | DELETE success, no body |
| 400 | Validation error (client's fault) |
| 401 | Not authenticated |
| 403 | Authenticated but not authorized |
| 404 | Resource not found |
| 409 | Conflict (idempotency / duplicate) |
| 422 | Semantically invalid (if you distinguish from 400) |
| 500 | Server error (never leak internals in the body) |

NEVER return 200 with an `{"error": ...}` body. Use the real status code.

---

## Endpoint Conventions

- **Nouns, not verbs**: `/api/engines/`, `/api/predictions/` — not `/api/getEngines/`.
- **Nested for ownership**: `/api/engines/{id}/predictions/`.
- **Actions as sub-routes** (DRF `@action`): `/api/engines/{id}/run/`, `/api/predictions/{id}/backfill/`.
- **Plural collections**: `/api/datasets/`, not `/api/dataset/`.
- **Filtering via query params**: `?status=active&engine=3` (use `django_filters`).
- **Kebab or snake consistently** — match the existing codebase (this project: check registry/api.md).

---

## ViewSet Pattern (backend)

```python
class ThingViewSet(viewsets.ModelViewSet):
    queryset = Thing.objects.all()
    serializer_class = ThingSerializer
    permission_classes = [IsAuthenticated]        # ALWAYS explicit — never rely on default
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'engine']

    def get_queryset(self):
        # Scope to the requesting user / tenant where applicable
        return super().get_queryset().filter(...)

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        # Thin: validate → call service → return
        result = SomeService().execute(pk)
        return Response(result, status=status.HTTP_202_ACCEPTED)
```

- Views stay THIN: validate → call service → serialize → return.
- Business logic lives in a service (see registry/services.md — reuse existing).
- ALWAYS set `permission_classes` explicitly.

---

## Serializers

- One serializer per representation: `ThingListSerializer` (lean) vs `ThingDetailSerializer` (full).
- List serializers `.defer()` / omit heavy JSON fields (perf — see backend rules).
- NEVER expose internal fields (passwords, secrets, raw tokens, internal flags).
- Validate at the serializer boundary, not in the view.

---

## Async / Long-Running Endpoints

For work > a few seconds (training, inference, heavy reports):
1. POST starts the job → return `202` + `{ "run_id": "..." }`.
2. GET `/status/{run_id}/` → `{ "status": "running|done|failed", "log_lines": [...] }`.
3. Frontend polls the status endpoint. NEVER block the request thread.

(If celery is disabled — see project.config.md — run detached via management command + status polling.)

---

## Versioning & Stability

- Don't break an existing endpoint's response shape — it breaks the frontend silently.
- Additive changes only (new optional fields OK). Removing/renaming a field = a breaking change → ADR.
- If a breaking change is unavoidable, version the route (`/api/v2/...`) and record an ADR.

---

## Frontend Consumption (mirror of the above)

- ALWAYS via the project API helper (`apiFetch`) — never raw `fetch()`.
- Handle all documented status codes (401 → re-auth, 403 → forbidden UI, 4xx → show `detail`).
- Expect the paginated envelope for lists (`results`, `count`, `next`).
- NEVER assume a bare array — read `results`.

---

## Anti-Patterns (reject in review)

- 200 status with an error body
- Bare-string or stack-trace error responses
- New endpoint duplicating one already in registry/api.md
- Missing `permission_classes` on a ViewSet
- Business logic inside the view
- Breaking an existing response shape without an ADR
