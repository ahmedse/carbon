# File: dataschema/views.py
"""
ViewSets for dataschema with role-based, scoped RBAC.
Roles:
    - admin: Everything in the project (schema+data, all modules).
    - audit: Everything for data rows in all modules of the project (no schema).
    - dataowner: Everything for data rows, but ONLY in allowed modules (no schema).
RBAC enforced via HasScopedRole from accounts app.
"""

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
from .models import DataTable, DataField, DataRow, SchemaChangeLog
from .serializers import (
    DataTableSerializer, DataTableDetailSerializer,
    DataFieldSerializer, DataRowSerializer,
    SchemaChangeLogSerializer
)
from accounts.permissions import HasScopedRole, ReadScopedWriteAdmin
from accounts.rbac_utils import get_allowed_module_ids, user_has_global_role
from core.models import Module
import pandas as pd
import io
import json

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

    @action(detail=False, methods=['post'], url_path='bulk-import')
    def bulk_import(self, request):
        """
        Bulk import data rows from CSV/Excel file.
        
        Request (multipart/form-data):
            - file: uploaded CSV/Excel file
            - data_table: table ID (required)
            - column_mapping: JSON string mapping CSV headers to field names (optional)
            - mode: 'create' (default, only mode supported in Phase 1)
        
        Response:
            {
                "created": int,
                "failed": int,
                "errors": [{"row": int, "data": dict, "error": str}, ...]
            }
        """
        # Extract request parameters
        file = request.FILES.get('file')
        data_table_id = request.data.get('data_table')
        column_mapping_str = request.data.get('column_mapping')
        mode = request.data.get('mode', 'create')
        
        # Validate required parameters
        if not file:
            return Response(
                {'error': 'file parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not data_table_id:
            return Response(
                {'error': 'data_table parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get DataTable instance
        try:
            data_table = DataTable.objects.get(pk=data_table_id)
        except DataTable.DoesNotExist:
            return Response(
                {'error': f'DataTable with id={data_table_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Parse file (CSV or Excel)
        try:
            file_content = file.read()
            if file.name.endswith('.csv'):
                df = pd.read_csv(io.BytesIO(file_content))
            elif file.name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(io.BytesIO(file_content))
            else:
                return Response(
                    {'error': 'File must be CSV (.csv) or Excel (.xlsx, .xls)'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': f'Failed to parse file: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Apply column mapping if provided
        if column_mapping_str:
            try:
                column_mapping = json.loads(column_mapping_str)
                df = df.rename(columns=column_mapping)
            except json.JSONDecodeError:
                return Response(
                    {'error': 'column_mapping must be valid JSON'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Initialize results
        results = {
            'created': 0,
            'failed': 0,
            'errors': []
        }
        
        # Process each row
        for idx, row in df.iterrows():
            row_data = row.to_dict()
            
            # Remove NaN values (pandas represents empty cells as NaN)
            row_data = {k: v for k, v in row_data.items() if pd.notna(v)}
            
            # Remove 'id' column if present (Phase 1: create only)
            row_data.pop('id', None)
            
            try:
                # Validate and create row
                serializer = DataRowSerializer(data={
                    'data_table': data_table.id,
                    'values': row_data
                })
                serializer.is_valid(raise_exception=True)
                serializer.save(created_by=request.user)
                results['created'] += 1
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'row': idx + 2,  # +2 because: 0-indexed + header row
                    'data': row_data,
                    'error': str(e)
                })
        
        return Response(results, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='download-template')
    def download_template(self, request):
        """
        Generate blank CSV template for a table.
        
        Query parameters:
            - data_table: table ID (required)
            - include_example: 'true' to include example row (optional)
        
        Returns:
            CSV file with field names as headers
        """
        data_table_id = request.query_params.get('data_table')
        include_example = request.query_params.get('include_example') == 'true'
        
        if not data_table_id:
            return Response(
                {'error': 'data_table query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            data_table = DataTable.objects.get(pk=data_table_id)
        except DataTable.DoesNotExist:
            return Response(
                {'error': f'DataTable with id={data_table_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get active fields ordered by position
        fields = data_table.fields.filter(is_active=True, is_archived=False).order_by('order')
        
        # Generate CSV header (use field names, not labels)
        headers = [f.name for f in fields]
        csv_rows = [','.join(f'"{h}"' for h in headers)]
        
        # Optionally add example row
        if include_example:
            example_values = []
            for f in fields:
                if f.type == 'string':
                    example_values.append('"example text"')
                elif f.type == 'text':
                    example_values.append('"example multiline text"')
                elif f.type == 'number':
                    example_values.append('123')
                elif f.type == 'date':
                    example_values.append('"2026-01-01"')
                elif f.type == 'boolean':
                    example_values.append('true')
                elif f.type == 'select':
                    options = f.options or []
                    if options:
                        example_values.append(f'"{options[0].get("value", "")}"')
                    else:
                        example_values.append('""')
                elif f.type == 'multiselect':
                    example_values.append('""')  # Empty for simplicity
                elif f.type == 'file':
                    example_values.append('""')  # Not supported in CSV import
                else:
                    example_values.append('""')
            csv_rows.append(','.join(example_values))
        
        csv_content = '\r\n'.join(csv_rows)
        
        # Return as file download
        response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{data_table.name}_template.csv"'
        return response

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