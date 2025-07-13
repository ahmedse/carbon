# File: dataschema/views.py
"""
ViewSets for dataschema with role-based, scoped RBAC.
Roles:
    - admin: Everything in the project (schema+data, all modules).
    - audit: Everything for data rows in all modules of the project (no schema).
    - dataowner: Everything for data rows, but ONLY in allowed modules (no schema).
RBAC enforced via HasScopedRole from accounts app.
"""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import DataTable, DataField, DataRow, SchemaChangeLog
from .serializers import (
    DataTableSerializer, DataTableDetailSerializer,
    DataFieldSerializer, DataRowSerializer,
    SchemaChangeLogSerializer
)
from accounts.permissions import HasScopedRole
from accounts.rbac_utils import get_allowed_module_ids, user_has_project_role
from core.models import Module, Project

def get_tenant(request):
    return getattr(request.user, 'tenant', None)

class ScopedViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet for RBAC: sets self.project and self.module for HasScopedRole.
    Subclasses must set required_role or override get_required_role().
    """
    permission_classes = [IsAuthenticated, HasScopedRole]
    required_role = None  # override or use get_required_role

    def get_permissions(self):
        project_id = self.request.query_params.get('project_id') or self.request.data.get('project_id')
        module_id = self.request.query_params.get('module_id') or self.request.data.get('module_id')
        tenant = get_tenant(self.request)
        self.project = self.module = None
        if project_id and tenant:
            try:
                self.project = Project.objects.get(pk=project_id, tenant=tenant)
            except Project.DoesNotExist:
                self.project = None
        if module_id and self.project:
            try:
                self.module = Module.objects.get(pk=module_id, project=self.project)
            except Module.DoesNotExist:
                self.module = None
        self.required_role = self.get_required_role()
        return super().get_permissions()

    def get_required_role(self):
        return self.required_role

# --- DataTable (Schema) ---
class DataTableViewSet(ScopedViewSet):
    """
    Only 'admin' or 'admins_group' can access schema (tables).
    """
    queryset = DataTable.objects.all()
    serializer_class = DataTableSerializer
    required_role = ("admin", "admins_group", "dataowners_group")

    def get_queryset(self):
        user = self.request.user
        project_id = self.request.query_params.get("project_id")
        module_id = self.request.query_params.get("module_id")

        if not project_id:
            return DataTable.objects.none()

        qs = DataTable.objects.filter(module__project_id=project_id, is_archived=False)
        # Admins: all tables in project
        if user_has_project_role(user, project_id, ["admin", "admins_group"]):
            if module_id:
                qs = qs.filter(module_id=module_id)
            return qs

        # dataowners_group: only tables in modules user has access to
        allowed_module_ids = get_allowed_module_ids(user, project_id, ["dataowners_group"])
        if module_id:
            if int(module_id) in allowed_module_ids:
                qs = qs.filter(module_id=module_id)
            else:
                return DataTable.objects.none()
        else:
            qs = qs.filter(module_id__in=allowed_module_ids)
        return qs

    def get_serializer_class(self):
        if self.action in ["retrieve", "list"]:
            return DataTableDetailSerializer
        return DataTableSerializer

# --- DataField (Schema) ---
class DataFieldViewSet(ScopedViewSet):
    """
    Only 'admin' or 'admins_group' can access schema (fields).
    """
    queryset = DataField.objects.all()
    serializer_class = DataFieldSerializer
    required_role = ("admin", "admins_group", "auditors_group", "dataowners_group")

    def get_queryset(self):
        qs = DataField.objects.all()
        if self.project:
            qs = qs.filter(data_table__module__project=self.project, is_archived=False)
            if self.module:
                qs = qs.filter(data_table__module=self.module)
            # Filter by data_table if specified
            table_id = (
                self.request.query_params.get("data_table") or
                self.request.query_params.get("table_id") or
                self.request.data.get("data_table") or
                self.request.data.get("table_id")
            )
            if table_id:
                qs = qs.filter(data_table_id=table_id)
        else:
            qs = qs.none()
        return qs

# --- DataRow (Data) ---
class DataRowViewSet(ScopedViewSet):
    """
    - 'admin'/'admins_group' can CRUD all data rows for the project.
    - 'audit' can CRUD all data rows for the project.
    - 'dataowner' can CRUD data rows ONLY in allowed modules (where user has dataowner role).
    """
    queryset = DataRow.objects.all()
    serializer_class = DataRowSerializer

    def get_required_role(self):
        return ["admin", "admins_group", "auditors_group", "dataowners_group"]

    def get_queryset(self):
        user = self.request.user
        project_id = self.request.query_params.get("project_id")
        module_id = self.request.query_params.get("module_id")

        if not project_id:
            return DataRow.objects.none()
        qs = DataRow.objects.filter(data_table__module__project_id=project_id, is_archived=False)
        if module_id:
            qs = qs.filter(data_table__module_id=module_id)
        return qs

# --- SchemaChangeLog (ReadOnly, admin/admins_group only) ---
class SchemaChangeLogViewSet(ScopedViewSet, viewsets.ReadOnlyModelViewSet):
    """
    Read-only: Only 'admin' or 'admins_group' can view schema change logs.
    """
    queryset = SchemaChangeLog.objects.all()
    serializer_class = SchemaChangeLogSerializer
    required_role = ("admin", "admins_group")

    def get_queryset(self):
        project_id = self.request.query_params.get("project_id")
        module_id = self.request.query_params.get("module_id")
        qs = SchemaChangeLog.objects.all()
        if project_id:
            qs = qs.filter(data_table__module__project_id=project_id)
        if module_id:
            qs = qs.filter(data_table__module_id=module_id)
        return qs