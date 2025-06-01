# File: dataschema/views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action


from .models import DataTable, DataField, DataRow, SchemaChangeLog
from .serializers import (
    DataTableSerializer, DataTableDetailSerializer,
    DataFieldSerializer, DataRowSerializer,
    SchemaChangeLogSerializer
)

from accounts.permissions import HasRBACPermission
from accounts.context_mixin import ContextExtractorMixin
from core.models import Module, Project  # For context checks

def user_tenant(request):
    return getattr(request.user, 'tenant', None)

class TenantProjectModuleBaseViewSet(ContextExtractorMixin, viewsets.ModelViewSet):
    """
    Base viewset: always filters by project_id (from context_id) and tenant.
    Child classes set:
      - queryset
      - serializer_class
      - required_permission
    """
    permission_classes = [HasRBACPermission]
    queryset = None  # Set in child

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
        """
        GET /api/dataschema/tables/<table_id>/fields/
        Returns all fields for the given data table.
        """
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

# --- SchemaChangeLog (ReadOnly) ---
class SchemaChangeLogViewSet(TenantProjectModuleBaseViewSet, viewsets.ReadOnlyModelViewSet):
    queryset = SchemaChangeLog.objects.all()
    serializer_class = SchemaChangeLogSerializer
    required_permission = "manage_schema"

    def get_queryset(self):
        base = super().get_queryset()
        return base.select_related("data_table", "data_field", "user")