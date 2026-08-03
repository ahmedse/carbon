# TASK.md — APP-CARBON-G2: Verification Workflow
# Phase I, Group 2 | Parallel-safe with G1, G3
# Worker: backend-worker | Model: DeepSeek (medium cost)

## Summary
Add a verification workflow: ReportingPeriod gets status + submit/verify/reject actions. VerificationRecord tracks who verified what and when. Two additive fields on existing model + one new model. One migration.

## Files to Read First (BEFORE writing anything)
1. `.ai-toolkit/project.config.md`
2. `.ai-toolkit/shared/base-rules.md`
3. `.ai-toolkit/roles/backend-worker.md`
4. `.ai-toolkit/shared/data-layer.md`
5. `.ai-toolkit/shared/api-contract.md`
6. `backend/emissions/models.py` — NOTE: read the existing `ReportingPeriod` class carefully
7. `backend/emissions/views.py` — NOTE: find the existing `ReportingPeriodViewSet`
8. `backend/emissions/serializers.py`
9. `backend/config/urls.py`

## Registry Check
Run `./.ai-toolkit/scripts/scan.sh`. Grep registry for "verification" — confirm no existing VerificationRecord. Grep for "ReportingPeriod" — note current fields.

## Files to Edit
| File | Action | What |
|------|--------|------|
| `backend/emissions/models.py` | ADD | `VerificationRecord` model + ADD `status`, `submitted_at` to `ReportingPeriod` |
| `backend/emissions/serializers.py` | ADD | `VerificationRecordSerializer` + ADD `status`, `submitted_at` to `ReportingPeriodSerializer` |
| `backend/emissions/views.py` | EDIT | Add `submit`, `verify`, `reject` `@action` methods to `ReportingPeriodViewSet` |
| `backend/config/urls.py` | EDIT | Register verification router |

## DO NOT TOUCH
- Any frontend file
- `catalog/`, `mdm/`, `dq/`, `dataschema/`, `accounts/`, `core/`
- `backend/emissions/services.py` (no service changes needed)
- `backend/emissions/management/` commands

## Deliverable 1 — VerificationRecord Model
Add to `backend/emissions/models.py`:

```python
class VerificationRecord(models.Model):
    """Tracks verification actions on reporting periods."""
    reporting_period = models.ForeignKey(
        'ReportingPeriod', on_delete=models.CASCADE, related_name='verifications'
    )
    verifier = models.ForeignKey(
        'accounts.User', on_delete=models.PROTECT
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('in_review', 'In Review'),
            ('verified', 'Verified'),
            ('rejected', 'Rejected'),
        ],
        default='pending',
    )
    notes = models.TextField(blank=True, default='')
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('reporting_period', 'verifier')]

    def __str__(self):
        return f"Verification #{self.id} — {self.reporting_period.name} ({self.get_status_display()})"
```

## Deliverable 2 — Add fields to ReportingPeriod
Find the existing `ReportingPeriod` class in `models.py`. Add these two fields (do NOT modify any existing fields):

```python
status = models.CharField(
    max_length=20,
    choices=[
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ],
    default='draft',
)
submitted_at = models.DateTimeField(null=True, blank=True)
```

## Deliverable 3 — Serializers
Add `VerificationRecordSerializer`:
```python
class VerificationRecordSerializer(serializers.ModelSerializer):
    verifier_name = serializers.CharField(source='verifier.username', read_only=True)

    class Meta:
        model = VerificationRecord
        fields = '__all__'
        read_only_fields = ['created_at', 'verifier_name']
```

Add `status` and `submitted_at` to the existing `ReportingPeriodSerializer` `fields` list. Add them to `read_only_fields` as well (status changes only via actions, not direct PATCH).

Import `VerificationRecord` at top of serializers.py.

## Deliverable 4 — ViewSet Actions
Add to the existing `ReportingPeriodViewSet` class (do NOT create a new class):

```python
@action(detail=True, methods=['post'])
def submit(self, request, pk=None):
    """Submit period for verification."""
    period = self.get_object()
    if period.status != 'draft':
        return Response({'detail': 'Only draft periods can be submitted.'}, status=400)
    period.status = 'submitted'
    period.submitted_at = timezone.now()
    period.save()
    return Response(ReportingPeriodSerializer(period).data)

@action(detail=True, methods=['post'])
def verify(self, request, pk=None):
    """Verify a submitted period (admin/admins_group only)."""
    if not (request.user.is_superuser or request.user.groups.filter(name='admins_group').exists()):
        return Response({'detail': 'Only admins can verify.'}, status=403)
    period = self.get_object()
    if period.status != 'submitted':
        return Response({'detail': 'Only submitted periods can be verified.'}, status=400)
    period.status = 'verified'
    period.save()
    VerificationRecord.objects.create(
        reporting_period=period,
        verifier=request.user,
        status='verified',
        verified_at=timezone.now(),
    )
    return Response(ReportingPeriodSerializer(period).data, status=201)

@action(detail=True, methods=['post'])
def reject(self, request, pk=None):
    """Reject a submitted period (admin/admins_group only)."""
    if not (request.user.is_superuser or request.user.groups.filter(name='admins_group').exists()):
        return Response({'detail': 'Only admins can reject.'}, status=403)
    period = self.get_object()
    if period.status != 'submitted':
        return Response({'detail': 'Only submitted periods can be rejected.'}, status=400)
    period.status = 'rejected'
    period.save()
    notes = request.data.get('notes', '')
    VerificationRecord.objects.create(
        reporting_period=period,
        verifier=request.user,
        status='rejected',
        notes=notes,
        verified_at=timezone.now(),
    )
    return Response(ReportingPeriodSerializer(period).data, status=201)
```

Imports needed at top of views.py: `from .models import VerificationRecord`, `from django.utils import timezone`.

## Deliverable 5 — Router
In `backend/config/urls.py`, add a router for verifications alongside the existing emissions routers:
```python
verification_router = DefaultRouter()
verification_router.register(r'verifications', VerificationRecordViewSet, basename='verification')
```
Add `path('', include(verification_router.urls))` to emissions urlpatterns.

Create `VerificationRecordViewSet` in views.py (ReadOnlyModelViewSet — verifications are created by actions, not direct POST):
```python
class VerificationRecordViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = VerificationRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = VerificationRecord.objects.select_related('reporting_period', 'verifier')
        period_id = self.request.query_params.get('period_id')
        if period_id:
            qs = qs.filter(reporting_period_id=period_id)
        return qs
```

## Migration
```bash
./manage.sh manage makemigrations emissions
```
One migration: `0007_verification_record.py` (or next number). Must contain: VerificationRecord model + AlterField for ReportingPeriod (adding status, submitted_at).

## Verification Gate

```bash
# 1. Migration
./manage.sh migrate
./manage.sh manage makemigrations --check
# Must: "No changes detected"

# 2. Import check
./manage.sh manage check
# Must exit 0

# 3. Restart
./manage.sh restart backend

# 4. Get token
TOKEN=$(curl -s -X POST http://localhost:8009/carbon-api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"ahmed","password":"AdminPa_132"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access'])")

# 5. Find a period ID
PID=$(curl -s http://localhost:8009/carbon-api/emissions/periods/ \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['results'][0]['id'] if d.get('results') else 'none')")
echo "Period ID: $PID"

# 6. Submit it
curl -s -X POST "http://localhost:8009/carbon-api/emissions/periods/$PID/submit/" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# Expect: status='submitted', submitted_at not null

# 7. Verify it
curl -s -X POST "http://localhost:8009/carbon-api/emissions/periods/$PID/verify/" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# Expect: status='verified'

# 8. Check verifications
curl -s "http://localhost:8009/carbon-api/emissions/verifications/?period_id=$PID" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# Expect: 1 result with status='verified', verifier_name='ahmed'
```

## Handoff
Write `plans/carbon-phase/phase-03-targets/TASK-RESULTS-G2.md`.
