"""
datahub/views.py — THIN views for the Dataset Hub.

Pattern (per base-rules): validate → call service → serialize. No business
logic in views. CBAC gating per design §4.2:
  * reads      → any authenticated (ReadAnyWriteAdmin)
  * dataset/contract writes → datahub:manage
  * version create / ingest → datahub:ingest
  * approve / reject        → datahub:approve (AdminOrSuperuserOnly)

Querysets are scoped at the boundary: visible module ids ∪ explicit
DatasetAccessPolicy grants (module-level ScopedRole is the default; an
explicit policy overrides it).
"""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import AdminOrSuperuserOnly, ReadAnyWriteAdmin
from accounts.rbac_utils import get_visible_module_ids

from . import ingest as ingest_service
from . import services as datahub_services
from .models import DataContract, DataContractViolation, Dataset, DatasetVersion
from .serializers import (
    DataContractSerializer, DataContractViolationSerializer,
    DatasetListSerializer, DatasetSerializer, DatasetVersionListSerializer,
    DatasetVersionSerializer,
)

# Statuses hidden from the catalog by default (soft-archived).
ARCHIVED = 'archived'


def dataset_qs_for_user(user):
    """Scope datasets by module visibility ∪ explicit access policies.

    Returns None for unrestricted (superuser / global admin) users.
    """
    visible = get_visible_module_ids(user)
    if visible is None:
        return Dataset.objects.select_related(
            'module', 'domain', 'owner', 'current_version',
        ).prefetch_related('tags')
    group_ids = list(user.groups.values_list('id', flat=True))
    return (
        Dataset.objects.select_related('module', 'domain', 'owner', 'current_version')
        .prefetch_related('tags')
        .filter(
            Q(module_id__in=visible)
            | Q(access_policies__user=user, access_policies__can_view=True)
            | Q(access_policies__group_id__in=group_ids, access_policies__can_view=True)
        )
        .distinct()
    )


def _check_module_visible(user, module_id):
    """Reject writes that target a module the user cannot see (CBAC boundary)."""
    visible = get_visible_module_ids(user)
    if visible is not None and module_id not in visible:
        raise PermissionDenied('You do not have access to datasets in this module.')


# ── Datasets ────────────────────────────────────────────────────────────────

class DatasetViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, ReadAnyWriteAdmin]
    required_write_capability = 'datahub:manage'
    queryset = Dataset.objects.none()
    serializer_class = DatasetSerializer
    lookup_field = 'pk'

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Dataset.objects.none()
        qs = dataset_qs_for_user(self.request.user)
        # Soft-archived datasets hidden by default; pass ?include_archived=true
        include_archived = self.request.query_params.get('include_archived') == 'true'
        if not include_archived:
            qs = qs.exclude(status=ARCHIVED)

        # Catalog filters: module / domain / status / classification
        module_id = self.request.query_params.get('module')
        domain_id = self.request.query_params.get('domain')
        status_filter = self.request.query_params.get('status')
        classification = self.request.query_params.get('classification')
        if module_id:
            qs = qs.filter(module_id=module_id)
        if domain_id:
            qs = qs.filter(domain_id=domain_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if classification:
            qs = qs.filter(classification=classification)
        return qs

    def get_serializer_class(self):
        if self.action in ('list',):
            return DatasetListSerializer
        return DatasetSerializer

    def perform_create(self, serializer):
        module = serializer.validated_data.get('module')
        if module:
            _check_module_visible(self.request.user, module.pk)
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        module = serializer.validated_data.get('module') or self.get_object().module
        _check_module_visible(self.request.user, module.pk)
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        """Soft archive — DELETE never hard-deletes governed datasets."""
        instance = self.get_object()
        instance.status = ARCHIVED
        instance.save(update_fields=['status', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Versions (nested under a dataset) ───────────────────────────────────────

class VersionListCreateView(APIView):
    """GET list of versions; POST create a version from an existing DataTable."""
    permission_classes = [IsAuthenticated, ReadAnyWriteAdmin]
    required_write_capability = 'datahub:ingest'

    def get_dataset(self, request, dataset_id):
        return get_object_or_404(
            dataset_qs_for_user(request.user).exclude(status=ARCHIVED),
            pk=dataset_id,
        )

    def get(self, request, dataset_id):
        dataset = self.get_dataset(request, dataset_id)
        qs = dataset.versions.select_related('created_by', 'approved_by').all()
        qs = qs[:50]  # bounded listing; newest first via Meta ordering
        return Response({
            'count': dataset.versions.count(),
            'results': DatasetVersionListSerializer(qs, many=True).data,
        })

    def post(self, request, dataset_id):
        dataset = self.get_dataset(request, dataset_id)

        from dataschema.models import DataTable

        # Multi-table composition: data_tables=[id1, id2, ...]
        data_table_ids = request.data.get('data_tables')
        if data_table_ids is not None:
            if not isinstance(data_table_ids, (list, tuple)) or not data_table_ids:
                raise ValidationError(
                    {'data_tables': 'Must be a non-empty list of DataTable ids.'})
            tables = list(DataTable.objects.filter(pk__in=data_table_ids))
            if len(tables) != len(set(data_table_ids)):
                raise ValidationError(
                    {'data_tables': 'One or more DataTable ids do not exist.'})
            for table in tables:
                if table.module_id != dataset.module_id:
                    raise PermissionDenied(
                        'A DataTable belongs to a different module.')
            version = ingest_service.create_version(
                dataset, tables, source_type='api', source_ref='manual',
                user=request.user,
            )
            return Response(DatasetVersionSerializer(version).data,
                            status=status.HTTP_201_CREATED)

        # Legacy single-table path (unchanged behavior).
        data_table_id = request.data.get('data_table')
        if not data_table_id:
            raise ValidationError(
                {'data_table': 'This field is required unless data_tables is provided.'})

        table = get_object_or_404(DataTable, pk=data_table_id)
        if table.module_id != dataset.module_id:
            raise PermissionDenied('The DataTable belongs to a different module.')

        version = ingest_service.create_version(
            dataset, table, source_type='api', source_ref='manual',
            user=request.user,
        )
        return Response(DatasetVersionSerializer(version).data,
                        status=status.HTTP_201_CREATED)


class VersionDetailView(APIView):
    """GET a single version with its health breakdown + violations."""
    permission_classes = [IsAuthenticated, ReadAnyWriteAdmin]

    def get(self, request, dataset_id, version_id):
        dataset = get_object_or_404(
            dataset_qs_for_user(request.user), pk=dataset_id,
        )
        version = get_object_or_404(dataset.versions, pk=version_id)
        data = DatasetVersionSerializer(version).data
        data['contract_violations'] = DataContractViolationSerializer(
            version.contract_violations.all(), many=True,
        ).data
        return Response(data)


class ApproveVersionView(APIView):
    """Approve a pending version → becomes dataset.current_version."""
    permission_classes = [IsAuthenticated, AdminOrSuperuserOnly]
    required_capability = 'datahub:approve'

    def post(self, request, dataset_id, version_id):
        dataset = get_object_or_404(
            dataset_qs_for_user(request.user), pk=dataset_id,
        )
        version = get_object_or_404(dataset.versions, pk=version_id)
        if version.status != 'pending':
            return Response(
                {'detail': f"Version is already '{version.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        datahub_services.approve_version(version, request.user)
        return Response(DatasetVersionSerializer(version).data)


class RejectVersionView(APIView):
    """Reject a pending version with a reason."""
    permission_classes = [IsAuthenticated, AdminOrSuperuserOnly]
    required_capability = 'datahub:approve'

    def post(self, request, dataset_id, version_id):
        dataset = get_object_or_404(
            dataset_qs_for_user(request.user), pk=dataset_id,
        )
        version = get_object_or_404(dataset.versions, pk=version_id)
        if version.status != 'pending':
            return Response(
                {'detail': f"Version is already '{version.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reason = (request.data or {}).get('reason', '')
        datahub_services.reject_version(version, request.user, reason=reason)
        return Response(DatasetVersionSerializer(version).data)


# ── Contract ────────────────────────────────────────────────────────────────

class ContractView(APIView):
    """GET or PUT the dataset's active DataContract."""
    permission_classes = [IsAuthenticated, ReadAnyWriteAdmin]
    required_write_capability = 'datahub:manage'

    def get_dataset(self, request, dataset_id):
        return get_object_or_404(
            dataset_qs_for_user(request.user).exclude(status=ARCHIVED),
            pk=dataset_id,
        )

    def get(self, request, dataset_id):
        dataset = self.get_dataset(request, dataset_id)
        contract = DataContract.objects.filter(dataset=dataset).first()
        if contract is None:
            return Response({'detail': 'No contract defined for this dataset.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(DataContractSerializer(contract).data)

    def put(self, request, dataset_id):
        dataset = self.get_dataset(request, dataset_id)
        contract, _ = DataContract.objects.get_or_create(
            dataset=dataset, defaults={'created_by': request.user},
        )
        serializer = DataContractSerializer(contract, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ContractViolationsView(APIView):
    """GET open (and optionally all) contract violations for a dataset."""
    permission_classes = [IsAuthenticated, ReadAnyWriteAdmin]

    def get(self, request, dataset_id):
        dataset = get_object_or_404(
            dataset_qs_for_user(request.user), pk=dataset_id,
        )
        qs = DataContractViolation.objects.filter(
            contract__dataset=dataset,
        ).select_related('dataset_version')
        if request.query_params.get('open_only', 'true') != 'false':
            qs = qs.filter(resolved_at__isnull=True)
        return Response({
            'count': qs.count(),
            'results': DataContractViolationSerializer(qs[:100], many=True).data,
        })


# ── Ingest ──────────────────────────────────────────────────────────────────

class IngestERPView(APIView):
    """POST {rows: [...], source_ref: '...'} — ERP snapshot ingest."""
    permission_classes = [IsAuthenticated, ReadAnyWriteAdmin]
    required_write_capability = 'datahub:ingest'

    def post(self, request, dataset_id):
        dataset = get_object_or_404(
            dataset_qs_for_user(request.user).exclude(status=ARCHIVED),
            pk=dataset_id,
        )
        rows = request.data.get('rows')
        if not isinstance(rows, list) or not rows:
            raise ValidationError({'rows': 'A non-empty list is required.'})
        source_ref = request.data.get('source_ref', 'erp')
        auto_approve = request.data.get('auto_approve') in (True, 'true')
        version = ingest_service.ingest_erp(
            dataset, rows, source_ref=source_ref,
            user=request.user, auto_approve=auto_approve,
        )
        return Response(DatasetVersionSerializer(version).data,
                        status=status.HTTP_201_CREATED)


class IngestUploadView(APIView):
    """Multipart POST {file: <csv>} — CSV/Excel upload ingest."""
    permission_classes = [IsAuthenticated, ReadAnyWriteAdmin]
    required_write_capability = 'datahub:ingest'
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, dataset_id):
        dataset = get_object_or_404(
            dataset_qs_for_user(request.user).exclude(status=ARCHIVED),
            pk=dataset_id,
        )
        file = request.FILES.get('file')
        if file is None:
            raise ValidationError({'file': 'This field is required.'})
        auto_approve = request.data.get('auto_approve') in (True, 'true')
        version = ingest_service.ingest_csv(
            dataset, file, user=request.user, auto_approve=auto_approve,
        )
        return Response(DatasetVersionSerializer(version).data,
                        status=status.HTTP_201_CREATED)
