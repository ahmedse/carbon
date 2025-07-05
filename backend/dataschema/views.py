# File: dataschema/views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.files.storage import default_storage
from django.db.models import Q

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

    def get_project_and_module_id(self):
        return self.get_project_and_module_id_from_request(self.request)

    def get_queryset(self):
        tenant = user_tenant(self.request)
        project_id, module_id = self.get_project_and_module_id()
        if not project_id or not tenant:
            return self.queryset.none()
        base = self.queryset.model.objects
        if hasattr(self.queryset.model, "module"):
            qs = base.filter(module__project_id=project_id, module__project__tenant=tenant, is_archived=False)
            if module_id:
                qs = qs.filter(module_id=module_id)
            return qs
        elif hasattr(self.queryset.model, "data_table"):
            qs = base.filter(data_table__module__project_id=project_id, data_table__module__project__tenant=tenant, is_archived=False)
            if module_id:
                qs = qs.filter(data_table__module_id=module_id)
            return qs
        elif hasattr(self.queryset.model, "data_field"):
            qs = base.filter(data_field__data_table__module__project_id=project_id, data_field__data_table__module__project__tenant=tenant)
            if module_id:
                qs = qs.filter(data_field__data_table__module_id=module_id)
            return qs
        else:
            return base.none()

    def perform_create(self, serializer):
        project_id, module_id = self.get_project_and_module_id()
        tenant = user_tenant(self.request)
        try:
            project = Project.objects.get(id=project_id, tenant=tenant)
        except Project.DoesNotExist:
            raise PermissionError("Project not found or does not belong to your tenant.")
        if hasattr(serializer.Meta.model, "module"):
            if not module_id:
                raise PermissionError("Module ID is required.")
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

    def get_required_permission(self):
        # Allow read with view_schema, require manage_schema for write
        if self.action in ["list", "retrieve", "fields"]:
            return "view_schema"
        return self.required_permission

    def perform_destroy(self, instance):
        print(f"[DEBUG] inside perform_destroy: {instance}")
        if instance.fields.exists():
            # Archive if it has fields
            instance.is_archived = True
            instance.save()
        else:
            print(f"[DEBUG] inside perform_destroy: {instance}")
            # Delete if no fields
            instance.delete()

    def get_queryset(self):
        qs = super().get_queryset()
        # Optionally support ?module_id= for filtering
        module_id = self.request.query_params.get('module_id')
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
    
    def perform_destroy(self, instance):
        # Check if any DataRow in the table has a value for this field
        has_data = instance.data_table.rows.filter(values__has_key=instance.name).exists()
        if has_data:
            # Archive if used in any DataRow
            instance.is_archived = True
            instance.save()
        else:
            # Delete if not used
            instance.delete()

# --- DataRow ---
class DataRowViewSet(TenantProjectModuleBaseViewSet):
    queryset = DataRow.objects.all()
    serializer_class = DataRowSerializer
    required_permission = "manage_data"

    def get_queryset(self):
        qs = super().get_queryset()
        data_table_id = self.request.query_params.get("data_table")
        if data_table_id:
            qs = qs.filter(data_table_id=data_table_id)

        # Field-specific filtering (for any field in the JSON "values")
        for key, value in self.request.query_params.items():
            if key.startswith('field__') and value:
                field_name = key[7:]  # strip 'field__'
                qs = qs.filter(**{f"values__{field_name}__icontains": value})

        # Generic search in all values fields
        search = self.request.query_params.get("search")
        if search:
            fields = DataField.objects.filter(data_table_id=data_table_id, type__in=['string', 'text'])
            if not fields.exists():
                print("[DEBUG] No searchable fields for search, returning empty queryset")
                return qs.none()  # return early, don't continue
            search_q = Q()
            for field in fields:
                search_q |= Q(**{f"values__{field.name}__icontains": search})
            qs = qs.filter(search_q)

        print(
            # "[DEBUG] DataRowViewSet.get_queryset: returning %d rows for table_id=%s (query: %s)"% (qs.count(), data_table_id, str(qs.query))
        )
        return qs

    def perform_create(self, serializer):
        project_id, module_id = self.get_project_and_module_id()
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
        print("[DEBUG] Upload called for row id:", pk)
        row = self.get_object()
        field_name = request.data.get("field")
        uploaded_file = request.FILES.get("file")
        print("[DEBUG] field_name:", field_name, "uploaded_file:", uploaded_file)
        if not field_name or not uploaded_file:
            print("[DEBUG] Missing field or file.")
            return Response({"detail": "Missing field or file."}, status=400)
        field = row.data_table.fields.filter(name=field_name, is_active=True, is_archived=False, type="file").first()
        if not field:
            print("[DEBUG] Invalid field for file upload.")
            return Response({"detail": "Invalid field for file upload."}, status=400)
        allowed_types = ["application/pdf", "image/jpeg", "image/png"]
        max_size = 5 * 1024 * 1024  # 5 MB
        if uploaded_file.content_type not in allowed_types:
            print("[DEBUG] Invalid file type:", uploaded_file.content_type)
            return Response({"detail": "Invalid file type."}, status=400)
        if uploaded_file.size > max_size:
            print("[DEBUG] File too large:", uploaded_file.size)
            return Response({"detail": "File too large."}, status=400)
        base_path = getattr(settings, "DATASCHEMA_UPLOAD_PATH", "dataschema_uploads/")
        filename = default_storage.save(
            f"{base_path.rstrip('/')}/{row.data_table.id}/{field_name}/{uploaded_file.name}",
            uploaded_file
        )
        file_url = default_storage.url(filename)
        print("[DEBUG] Saved file to:", file_url)
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