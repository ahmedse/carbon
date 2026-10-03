import csv
import io

from django.db.models import Count
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .definitions import validate_fields, validate_key
from .exceptions import InboundError
from .models import InboundBatch, InboundCartridge, InboundTemplate
from .permissions import InboundAccess, can_define
from .serializers import InboundBatchSerializer, InboundCartridgeSerializer, InboundTemplateSerializer
from . import example_templates, registry, services


def _err(exc: InboundError):
    return Response({'detail': exc.message}, status=exc.status)


class InboundBatchViewSet(viewsets.ModelViewSet):
    serializer_class = InboundBatchSerializer
    permission_classes = [IsAuthenticated, InboundAccess]
    http_method_names = ['get', 'post', 'put', 'head', 'options']

    def get_queryset(self):
        qs = InboundBatch.objects.select_related('prepared_by', 'committed_by')
        kind = self.request.query_params.get('kind')
        if kind:
            qs = qs.filter(kind=kind)
        return qs

    def create(self, request, *args, **kwargs):
        kind = request.data.get('kind') or InboundBatch.KIND_TYPED
        target_key = request.data.get('target_key')
        if not target_key:
            return Response({'detail': 'target_key is required'}, status=400)
        try:
            batch = services.create_batch(kind=kind, target_key=target_key, user=request.user)
        except InboundError as exc:
            return _err(exc)
        return Response(InboundBatchSerializer(batch).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def targets(self, request):
        from .permissions import can_use_kind
        kind = request.query_params.get('kind')
        if kind:
            if not can_use_kind(request.user, kind):
                return Response({'detail': 'Not allowed for this destination kind'}, status=403)
            return Response(registry.list_targets(kind=kind))
        rows = []
        for candidate in ('typed_object', 'data_product'):
            if can_use_kind(request.user, candidate):
                rows.extend(registry.list_targets(kind=candidate))
        rows.sort(key=lambda r: r['key'])
        return Response(rows)

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def file(self, request, pk=None):
        batch = self.get_object()
        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'detail': 'file is required'}, status=400)
        encoding = request.data.get('encoding') or None
        try:
            batch = services.attach_file(batch, uploaded, encoding=encoding)
        except InboundError as exc:
            return _err(exc)
        return Response(InboundBatchSerializer(batch).data)

    @action(detail=True, methods=['put'])
    def mapping(self, request, pk=None):
        batch = self.get_object()
        try:
            batch = services.save_mapping(batch, request.data)
        except InboundError as exc:
            return _err(exc)
        return Response(InboundBatchSerializer(batch).data)

    @action(detail=True, methods=['post'])
    def smoke(self, request, pk=None):
        batch = self.get_object()
        try:
            batch = services.run_smoke(batch, request.user)
        except InboundError as exc:
            return _err(exc)
        return Response(InboundBatchSerializer(batch).data)

    @action(detail=True, methods=['get'])
    def rejects(self, request, pk=None):
        batch = self.get_object()
        rows = (batch.smoke or {}).get('reject_rows') or []
        buf = io.StringIO()
        if rows:
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        resp = HttpResponse(buf.getvalue(), content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="batch-{batch.id}-rejects.csv"'
        return resp

    @action(detail=True, methods=['get'])
    def rows(self, request, pk=None):
        """Read-only full-row page. Re-parses the file; writes nothing."""
        batch = self.get_object()
        try:
            page = int(request.query_params.get('page') or 1)
            page_size = int(request.query_params.get('page_size') or services.DEFAULT_PAGE_SIZE)
        except (TypeError, ValueError):
            return Response({'detail': 'page and page_size must be integers'}, status=400)
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = services.DEFAULT_PAGE_SIZE
        page_size = min(page_size, services.MAX_PAGE_SIZE)
        try:
            payload = services.batch_rows(batch, page=page, page_size=page_size)
        except InboundError as exc:
            return _err(exc)
        return Response(payload)

    @action(detail=True, methods=['post'])
    def commit(self, request, pk=None):
        batch = self.get_object()
        allow_partial = bool(request.data.get('allow_partial'))
        try:
            batch = services.run_commit(batch, request.user, allow_partial=allow_partial)
        except InboundError as exc:
            return _err(exc)
        return Response(InboundBatchSerializer(batch).data)


class InboundTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = InboundTemplateSerializer
    permission_classes = [IsAuthenticated, InboundAccess]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        qs = InboundTemplate.objects.all()
        target = self.request.query_params.get('target_key')
        kind = self.request.query_params.get('kind')
        if target:
            qs = qs.filter(target_key=target)
        if kind:
            qs = qs.filter(kind=kind)
        return qs

    def create(self, request, *args, **kwargs):
        name = (request.data.get('name') or '').strip()
        kind = request.data.get('kind')
        target_key = request.data.get('target_key')
        mapping = request.data.get('mapping') or {}
        if not name or not kind or not target_key:
            return Response({'detail': 'name, kind, and target_key are required'}, status=400)
        if not isinstance(mapping, dict):
            return Response({'detail': 'mapping must be an object'}, status=400)
        try:
            registry.get(target_key)
        except KeyError:
            return Response({'detail': f'Unknown target {target_key}'}, status=400)
        obj, _ = InboundTemplate.objects.update_or_create(
            name=name, target_key=target_key,
            defaults={'kind': kind, 'mapping': mapping, 'owner': request.user},
        )
        return Response(InboundTemplateSerializer(obj).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='examples')
    def examples(self, request):
        """Index of shipped example CSVs. Real files only, never DB rows."""
        return Response(example_templates.list_examples())

    @action(detail=False, methods=['get'], url_path=r'examples/(?P<slug>[^/.]+)')
    def example(self, request, slug=None):
        try:
            filename, data = example_templates.read_example(slug)
        except InboundError as exc:
            return _err(exc)
        resp = HttpResponse(data, content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


class CartridgeAccess(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and can_define(request.user)


class InboundCartridgeViewSet(viewsets.ModelViewSet):
    """Declaration CRUD. A row with no registered handler cannot receive a batch."""

    serializer_class = InboundCartridgeSerializer
    permission_classes = [CartridgeAccess]
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        registry.sync_all()
        return InboundCartridge.objects.all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        keys = list(InboundCartridge.objects.values_list('key', flat=True))
        counts = {
            row['target_key']: row['n']
            for row in InboundBatch.objects.filter(target_key__in=keys).values('target_key').annotate(n=Count('id'))
        }
        last = {}
        for batch in InboundBatch.objects.filter(target_key__in=keys).order_by('target_key', '-id'):
            last.setdefault(batch.target_key, batch.status)
        ctx['batch_counts'] = counts
        ctx['last_status'] = last
        ctx['bound'] = {key: registry.is_bound(key) for key in keys}
        return ctx

    def create(self, request, *args, **kwargs):
        try:
            key = validate_key(request.data.get('key') or '')
            fields = validate_fields(request.data.get('fields'))
        except InboundError as exc:
            return _err(exc)
        kind = request.data.get('kind') or InboundBatch.KIND_TYPED
        if kind != InboundBatch.KIND_TYPED:
            return Response({'detail': 'Data product targets come from Catalog tables'}, status=400)
        if InboundCartridge.objects.filter(key=key).exists() or registry.is_bound(key):
            return Response({'detail': 'Cartridge already exists'}, status=409)
        row = InboundCartridge.objects.create(
            key=key,
            kind=kind,
            label=str(request.data.get('label') or '').strip() or key,
            label_ar=str(request.data.get('label_ar') or '').strip(),
            owner_app=key.split('.', 1)[0],
            fields=fields,
            enabled=True,
        )
        return Response(self.get_serializer(row).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        row = self.get_object()
        if 'key' in request.data and request.data.get('key') != row.key:
            return Response({'detail': 'Key cannot change'}, status=400)
        fields = row.fields
        if 'fields' in request.data:
            try:
                fields = validate_fields(request.data.get('fields'))
            except InboundError as exc:
                return _err(exc)
        if 'label' in request.data:
            label = str(request.data.get('label') or '').strip()
            if not label:
                return Response({'detail': 'Label is required'}, status=400)
            row.label = label
        if 'label_ar' in request.data:
            row.label_ar = str(request.data.get('label_ar') or '').strip()
        if 'enabled' in request.data:
            row.enabled = bool(request.data.get('enabled'))
        row.fields = fields
        row.save()
        registry.apply_definition(
            row.key, label=row.label, label_ar=row.label_ar, fields=row.fields, enabled=row.enabled,
        )
        return Response(self.get_serializer(row).data)

    def destroy(self, request, *args, **kwargs):
        row = self.get_object()
        if registry.is_bound(row.key):
            return Response(
                {'detail': 'This cartridge has a handler. Disable it. The owning app registers smoke and commit.'},
                status=409,
            )
        if InboundBatch.objects.filter(target_key=row.key).exists():
            return Response({'detail': 'Batches still use this cartridge'}, status=409)
        row.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
