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
from accounts.permissions import HasScopedRole, ReadScopedWriteAdmin
from accounts.rbac_utils import get_allowed_module_ids, user_has_global_role
from core.models import Module

class ScopedViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet for RBAC: sets self.project and self.module for HasScopedRole.
    Subclasses must set required_role or override get_required_role().
    """
    permission_classes = [IsAuthenticated, HasScopedRole]
    required_role = None  # override or use get_required_role

    def get_permissions(self):
        module_id = self.request.query_params.get('module_id') or self.request.data.get('module_id')
        self.module = None
        if module_id:
            try:
                self.module = Module.objects.get(pk=module_id)
            except Module.DoesNotExist:
                self.module = None
        self.required_role = self.get_required_role()
        return super().get_permissions()

    def get_required_role(self):
        return self.required_role

# --- DataTable (Schema) ---
class DataTableViewSet(ScopedViewSet):
    """
    Schema tables - Read: data-owners in scope, Write: global admins only.
    """
    queryset = DataTable.objects.all()
    serializer_class = DataTableSerializer
    permission_classes = [IsAuthenticated, ReadScopedWriteAdmin]
    required_role = ("admin", "admins_group", "dataowners_group", "auditors_group")

    def get_queryset(self):
        user = self.request.user
        module_id = self.request.query_params.get("module_id")
        pk = self.kwargs.get('pk')

        qs = DataTable.objects.filter(is_archived=False)
        if not (user.is_superuser or user_has_global_role(user, ["admin", "admins_group"])):
            allowed = get_allowed_module_ids(
                user, ["admin", "admins_group", "dataowners_group", "auditors_group"]
            )
            qs = qs.filter(module_id__in=allowed)
        if module_id:
            qs = qs.filter(module_id=module_id)
        if pk:
            qs = qs.filter(pk=pk)
        return qs

    def get_serializer_class(self):
        if self.action in ["retrieve", "list"]:
            return DataTableDetailSerializer
        return DataTableSerializer

# --- DataField (Schema) ---
class DataFieldViewSet(ScopedViewSet):
    """
    Schema fields - Read: data-owners in scope, Write: global admins only.
    """
    queryset = DataField.objects.all()
    serializer_class = DataFieldSerializer
    permission_classes = [IsAuthenticated, ReadScopedWriteAdmin]
    required_role = ("admin", "admins_group", "auditors_group", "dataowners_group")

    def get_queryset(self):
        qs = DataField.objects.all()
        if self.module:
            qs = qs.filter(data_table__module=self.module, is_archived=False)
        else:
            qs = qs.filter(is_archived=False)
        table_id = (
            self.request.query_params.get("data_table") or
            self.request.query_params.get("table_id") or
            self.request.data.get("data_table") or
            self.request.data.get("table_id")
        )
        if table_id:
            qs = qs.filter(data_table_id=table_id)
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
        module_id = self.request.query_params.get("module_id")
        data_table_id = self.request.query_params.get("data_table")

        qs = DataRow.objects.filter(is_archived=False)
        if not (user.is_superuser or user_has_global_role(user, ["admin", "admins_group"])):
            allowed = get_allowed_module_ids(
                user, ["admin", "admins_group", "dataowners_group", "auditors_group"]
            )
            qs = qs.filter(data_table__module_id__in=allowed)
        if module_id:
            qs = qs.filter(data_table__module_id=module_id)
        if data_table_id:
            qs = qs.filter(data_table_id=data_table_id)
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
        module_id = self.request.query_params.get("module_id")
        qs = SchemaChangeLog.objects.all()
        if module_id:
            qs = qs.filter(data_table__module_id=module_id)
        return qs