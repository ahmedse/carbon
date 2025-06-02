# File: dataschema/views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.files.storage import default_storage

from .models import DataTable, DataField, DataRow, SchemaChangeLog
from .serializers import (
    DataTableSerializer, DataTableDetailSerializer,
    DataFieldSerializer, DataRowSerializer,
    SchemaChangeLogSerializer
)

from accounts.permissions import HasRBACPermission
from accounts.context_mixin import ContextExtractorMixin
from core.models import Module, Project

def user_tenant(request):
    return getattr(request.user, 'tenant', None)

class TenantProjectModuleBaseViewSet(ContextExtractorMixin, viewsets.ModelViewSet):
    permission_classes = [HasRBACPermission]
    queryset = None

    def get_project_id(self):
        return self.get_project_id_from_request(self.request)

    def get_queryset(self):
        tenant = user_tenant(self.request)
        project_id = self.get_project_id()
        if not project_id or not tenant:
            return self.queryset.none()
        base = self.queryset.model.objects
        if hasattr(self.queryset.model, "module"):
            return base.filter(module__project_id=project_id, module__project__tenant=tenant, is_archived=False)
        elif hasattr(self.queryset.model, "data_table"):
            return base.filter(data_table__module__project_id=project_id, data_table__module__project__tenant=tenant, is_archived=False)
        elif hasattr(self.queryset.model, "data_field"):
            return base.filter(data_field__data_table__module__project_id=project_id, data_field__data_table__module__project__tenant=tenant)
        else:
            return base.none()

    def perform_create(self, serializer):
        project_id = self.get_project_id()
        tenant = user_tenant(self.request)
        try:
            project = Project.objects.get(id=project_id, tenant=tenant)
        except Project.DoesNotExist:
            raise PermissionError("Project not found or does not belong to your tenant.")
        if hasattr(serializer.Meta.model, "module"):
            module_id = self.request.data.get("module")
            try:
                module = Module.objects.get(id=module_id, project=project)
            except Module.DoesNotExist:
                raise PermissionError("Module not found or does not belong to this project.")
            serializer.save(module=module, created_by=self.request.user, updated_by=self.request.user)
        else:
            serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        instance.is_archived = True
        instance.save()

# --- DataTable ---
class DataTableViewSet(TenantProjectModuleBaseViewSet):
    queryset = DataTable.objects.all()
    serializer_class = DataTableSerializer
    required_permission = "manage_schema"

    def get_queryset(self):
        qs = super().get_queryset()
        module_id = self.request.query_params.get('module')
        if module_id:
            qs = qs.filter(module_id=module_id)
        return qs

    def get_serializer_class(self):
        if self.action in ["retrieve", "list"]:
            return DataTableDetailSerializer
        return DataTableSerializer

    @action(detail=True, methods=["get"], url_path="fields")
    def fields(self, request, pk=None):
        table = self.get_object()
        fields_qs = DataField.objects.filter(data_table=table, is_archived=False)
        serializer = DataFieldSerializer(fields_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        obj = self.get_object()
        if not request.user.is_superuser and not request.user.has_perm('manage_schema'):
            return Response({"detail": "Only admin can archive tables."}, status=403)
        obj.is_archived = True
        obj.save()
        SchemaChangeLog.objects.create(
            data_table=obj, action="archive", before=DataTableSerializer(obj).data, user=request.user
        )
        return Response({"status": "archived"})

# --- DataField ---
class DataFieldViewSet(TenantProjectModuleBaseViewSet):
    queryset = DataField.objects.all()
    serializer_class = DataFieldSerializer
    required_permission = "manage_schema"

    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        obj = self.get_object()
        if not request.user.is_superuser and not request.user.has_perm('manage_schema'):
            return Response({"detail": "Only admin can archive fields."}, status=403)
        obj.is_archived = True
        obj.save()
        SchemaChangeLog.objects.create(
            data_table=obj.data_table, data_field=obj, action="archive", before=DataFieldSerializer(obj).data, user=request.user
        )
        return Response({"status": "archived"})

# --- DataRow ---
class DataRowViewSet(TenantProjectModuleBaseViewSet):
    queryset = DataRow.objects.all()
    serializer_class = DataRowSerializer
    required_permission = "manage_data"

    def perform_create(self, serializer):
        project_id = self.get_project_id()
        tenant = user_tenant(self.request)
        try:
            project = Project.objects.get(id=project_id, tenant=tenant)
        except Project.DoesNotExist:
            raise PermissionError("Project not found or does not belong to your tenant.")
        data_table_id = self.request.data.get("data_table")
        try:
            data_table = DataTable.objects.get(id=data_table_id, module__project=project)
        except DataTable.DoesNotExist:
            raise PermissionError("DataTable not found or does not belong to this project.")
        serializer.save(data_table=data_table, created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        instance.is_archived = True
        instance.save()

    # PATCH support for partial update
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        try:
            return self.update(request, *args, **kwargs)
        except Exception as e:
            return Response({"detail": f"Update failed: {str(e)}"}, status=400)

    @action(detail=True, methods=['post'], url_path='upload', parser_classes=[MultiPartParser, FormParser])
    def upload(self, request, pk=None):
        row = self.get_object()
        field_name = request.data.get("field")
        uploaded_file = request.FILES.get("file")
        if not field_name or not uploaded_file:
            return Response({"detail": "Missing field or file."}, status=400)
        field = row.data_table.fields.filter(name=field_name, is_active=True, is_archived=False, type="file").first()
        if not field:
            return Response({"detail": "Invalid field for file upload."}, status=400)
        allowed_types = ["application/pdf", "image/jpeg", "image/png"]
        max_size = 5 * 1024 * 1024  # 5 MB
        if uploaded_file.content_type not in allowed_types:
            return Response({"detail": "Invalid file type."}, status=400)
        if uploaded_file.size > max_size:
            return Response({"detail": "File too large."}, status=400)
        # Use the path from settings, defaulting as needed
        base_path = getattr(settings, "DATASCHEMA_UPLOAD_PATH", "dataschema_uploads/")
        filename = default_storage.save(
            f"{base_path.rstrip('/')}/{row.data_table.id}/{field_name}/{uploaded_file.name}",
            uploaded_file
        )
        file_url = default_storage.url(filename)
        values = row.values or {}
        values[field_name] = file_url
        row.values = values
        row.save(update_fields=["values", "updated_at"])
        return Response({"url": file_url})

# --- SchemaChangeLog (ReadOnly) ---
class SchemaChangeLogViewSet(TenantProjectModuleBaseViewSet, viewsets.ReadOnlyModelViewSet):
    queryset = SchemaChangeLog.objects.all()
    serializer_class = SchemaChangeLogSerializer
    required_permission = "manage_schema"

    def get_queryset(self):
        base = super().get_queryset()
        return base.select_related("data_table", "data_field", "user")