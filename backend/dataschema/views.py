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
from .models import DataTable, DataField, DataRow, SchemaChangeLog, TableRelation
from .serializers import (
    DataTableSerializer, DataTableDetailSerializer,
    DataFieldSerializer, DataRowSerializer,
    SchemaChangeLogSerializer, TableRelationSerializer
)
from accounts.permissions import HasScopedRole, ReadScopedWriteAdmin
from accounts.rbac_utils import get_allowed_module_ids, user_has_global_role, get_visible_module_ids, VISIBILITY_ROLES
from accounts.models import ScopedRole
from core.models import Module
from core.feedback import AppFeedback
from .services import BulkImportService


def _log_schema_change(user, action, *, data_table=None, data_field=None,
                       before=None, after=None, notes=""):
    """Best-effort write to SchemaChangeLog. Never blocks the request on failure."""
    try:
        SchemaChangeLog.objects.create(
            data_table=data_table,
            data_field=data_field,
            action=action,
            before=before,
            after=after,
            user=user if getattr(user, "is_authenticated", False) else None,
            notes=notes,
        )
    except Exception:  # pragma: no cover - logging must not break CRUD
        import logging
        logging.getLogger("dataschema.views").exception("Failed to write SchemaChangeLog")


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
    required_role = ("admin", "admins_group", "dataowners_group", "auditors_group", "viewers_group", "analysts_group")

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return DataTable.objects.none()
        user = self.request.user
        module_id = self.request.query_params.get("module_id")
        pk = self.kwargs.get('pk')

        qs = DataTable.objects.select_related(
            'module'
        ).prefetch_related(
            'fields', 'rows'
        ).filter(is_archived=False)
        visible = get_visible_module_ids(user)
        if visible is not None:
            qs = qs.filter(module_id__in=visible)
        if module_id:
            qs = qs.filter(module_id=module_id)
        if pk:
            qs = qs.filter(pk=pk)
        return qs

    def get_serializer_class(self):
        if self.action in ["retrieve", "list"]:
            return DataTableDetailSerializer
        return DataTableSerializer

    def perform_create(self, serializer):
        obj = serializer.save()
        _log_schema_change(
            self.request.user, "add", data_table=obj,
            after=DataTableSerializer(obj).data,
        )

    def perform_update(self, serializer):
        before = DataTableSerializer(serializer.instance).data
        obj = serializer.save()
        _log_schema_change(
            self.request.user, "edit", data_table=obj,
            before=before, after=DataTableSerializer(obj).data,
        )

    def destroy(self, request, *args, **kwargs):
        """
        Delete validation: prevent deletion if table is locked or has rows.
        Superuser may override row dependency with ?force=true.
        """
        instance = self.get_object()

        # Governance policy enforcement
        from catalog.policy_engine import check_policy
        allowed, blocked_by = check_policy('table_delete', org_unit_id=instance.module.org_unit_id if instance.module else None, data_table=instance)
        if not allowed:
            raise AppFeedback(
                code="policy_blocked",
                title="Action blocked by governance policy",
                detail=f"Delete is blocked by: {', '.join(blocked_by)}",
                reasons=[f"Active policy '{name}' prevents this action." for name in blocked_by],
                remediation=["Contact a platform administrator to review or disable the policy."],
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Locked guard
        if getattr(instance, "is_locked", False) and not request.user.is_superuser:
            raise AppFeedback(
                code="table_locked",
                title="Table is locked",
                detail=f"'{instance.title}' is locked to prevent accidental changes.",
                reasons=["This table has been locked by an administrator."],
                remediation=[
                    "Ask an administrator to unlock it before deleting.",
                    "Unlocking is available in the table settings.",
                ],
                context={"table_id": instance.id, "is_locked": True},
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Dependency guard: rows
        row_count = instance.rows.filter(is_archived=False).count()
        if row_count > 0:
            force = request.query_params.get("force", "").lower() == "true"
            if not (force and request.user.is_superuser):
                raise AppFeedback(
                    code="table_has_rows",
                    title="Cannot delete table",
                    detail=f"'{instance.title}' still contains {row_count} row(s) of data.",
                    reasons=[
                        f"This table has {row_count} row(s) of data.",
                        "Deleting it would permanently remove all of that data.",
                    ],
                    remediation=[
                        "Delete or archive the rows in this table first.",
                        "Then retry deleting the table.",
                    ],
                    context={"table_id": instance.id, "row_count": row_count},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        # Log before deletion
        before = DataTableSerializer(instance).data
        _log_schema_change(
            request.user, "delete", data_table=instance, before=before,
            notes=f"Deleted table '{instance.title}' (id={instance.id})",
        )

        return super().destroy(request, *args, **kwargs)

# --- DataField (Schema) ---
class DataFieldViewSet(ScopedViewSet):
    """
    Schema fields - Read: data-owners in scope, Write: global admins only.
    """
    queryset = DataField.objects.all()
    serializer_class = DataFieldSerializer
    permission_classes = [IsAuthenticated, ReadScopedWriteAdmin]
    required_role = ("admin", "admins_group", "auditors_group", "dataowners_group", "viewers_group", "analysts_group")

    def get_queryset(self):
        module = getattr(self, 'module', None)
        qs = DataField.objects.all()
        if module:
            qs = qs.filter(data_table__module=module, is_archived=False)
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

    def perform_create(self, serializer):
        obj = serializer.save()
        _log_schema_change(
            self.request.user, "add", data_table=obj.data_table, data_field=obj,
            after=DataFieldSerializer(obj).data,
        )

    def perform_update(self, serializer):
        before = DataFieldSerializer(serializer.instance).data
        obj = serializer.save()
        _log_schema_change(
            self.request.user, "edit", data_table=obj.data_table, data_field=obj,
            before=before, after=DataFieldSerializer(obj).data,
        )

    def perform_destroy(self, instance):
        # Dependency check: DQ rule assignments
        rule_assignments = instance.rule_assignments.count()
        if rule_assignments > 0:
            raise AppFeedback(
                code="field_has_rules",
                title="Cannot delete field",
                detail=f"'{instance.name}' is assigned to {rule_assignments} DQ rule(s).",
                reasons=["Remove the DQ rule assignments from this field first."],
                remediation=[],
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        # Dependency check: reference set bindings
        if instance.reference_set_id:
            raise AppFeedback(
                code="field_bound_to_reference_set",
                title="Cannot delete field",
                detail=f"'{instance.name}' is bound to reference set '{instance.reference_set.name}'.",
                reasons=["Remove the reference set binding first."],
                remediation=[],
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        # Dependency check: catalog profile
        if hasattr(instance, 'catalog_profile') and instance.catalog_profile:
            raise AppFeedback(
                code="field_has_catalog_profile",
                title="Cannot delete field",
                detail=f"'{instance.name}' has a catalog profile.",
                reasons=["Delete the catalog profile first."],
                remediation=[],
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        # Existing audit + delete
        before = DataFieldSerializer(instance).data
        parent_table = instance.data_table
        _log_schema_change(
            self.request.user, "delete", data_table=parent_table, data_field=instance,
            before=before,
            notes=f"Deleted field '{instance.name}' (id={instance.id})",
        )
        instance.delete()

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
        return ["admin", "admins_group", "auditors_group", "dataowners_group", "viewers_group", "analysts_group"]

    def _check_table_not_locked(self, data_table, request):
        """Raise AppFeedback if the data table is locked and user is not superuser.

        Used to guard against writing data rows on locked tables.
        The is_locked flag is propagated from period-lock enforcement (E2-B3).
        """
        if getattr(data_table, "is_locked", False) and not request.user.is_superuser:
            raise AppFeedback(
                code="table_locked",
                title="Table is locked",
                detail=f"'{data_table.title}' is locked. Data modifications are blocked.",
                reasons=["This table has been locked because its reporting period is locked."],
                remediation=[
                    "Ask an administrator to unlock the reporting period.",
                    "Unlocking is available in the period settings.",
                ],
                context={"table_id": data_table.id, "is_locked": True},
                status_code=status.HTTP_403_FORBIDDEN,
            )
    
    def log_request(self, request, method, endpoint_desc):
        """Centralized request logging for debugging"""
        import logging
        logger = logging.getLogger('dataschema.views')
        logger.error(f"""
╔════════════════════════════════════════════════════════════════════════╗
║ {method} REQUEST → {endpoint_desc}                                     ║
╠════════════════════════════════════════════════════════════════════════╣
║ USER: {request.user.username} | ID: {request.user.id}
║ PARAMS: {dict(request.query_params)}
║ BODY: {dict(request.data) if hasattr(request, 'data') else 'N/A'}
║ CONTENT-TYPE: {request.content_type}
╚════════════════════════════════════════════════════════════════════════╝
        """)
    
    def log_error(self, method, status_code, error_msg, context=None):
        """Centralized error logging"""
        import logging
        logger = logging.getLogger('dataschema.views')
        ctx = context or {}
        logger.error(f"""
╔════════════════════════════════════════════════════════════════════════╗
║ ❌ ERROR: {method} | Status: {status_code}
╠════════════════════════════════════════════════════════════════════════╣
║ {error_msg}
║ CONTEXT: {ctx}
╚════════════════════════════════════════════════════════════════════════╝
        """)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return DataRow.objects.none()
        user = self.request.user
        module_id = self.request.query_params.get("module_id")
        data_table_id = self.request.query_params.get("data_table")

        qs = DataRow.objects.filter(is_archived=False)
        visible = get_visible_module_ids(user)
        if visible is not None:
            qs = qs.filter(data_table__module_id__in=visible)
        if module_id:
            qs = qs.filter(data_table__module_id=module_id)
        if data_table_id:
            qs = qs.filter(data_table_id=data_table_id)
        return qs

    def create(self, request, *args, **kwargs):
        """Guard against writes to locked tables, then delegate to parent."""
        data_table_id = request.data.get('data_table')
        if data_table_id:
            try:
                data_table = DataTable.objects.get(pk=data_table_id)
            except DataTable.DoesNotExist:
                pass
            else:
                self._check_table_not_locked(data_table, request)
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Soft-delete: set is_archived=True. Guard against writes on locked tables."""
        instance = self.get_object()
        self._check_table_not_locked(instance.data_table, request)
        instance.is_archived = True
        instance.save(update_fields=['is_archived', 'updated_at'])
        _log_schema_change(
            self.request.user, "archive", data_table=instance.data_table,
            notes=f"Archived row {instance.id} (table '{instance.data_table.title}')",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def update(self, request, *args, **kwargs):
        """Override to add lock guard + comprehensive logging for PATCH/PUT operations"""
        instance = self.get_object()
        self._check_table_not_locked(instance.data_table, request)

        import logging
        logger = logging.getLogger('dataschema.views')
        
        row_id = kwargs.get('pk')
        logger.error(f"""
╔════════════════════════════════════════════════════════════════════════╗
║ 🔵 PATCH/PUT REQUEST → update()
╠════════════════════════════════════════════════════════════════════════╣
║ ROW ID: {row_id}
║ USER: {request.user.username} (ID: {request.user.id})
║ QUERY PARAMS: {dict(request.query_params)}
║ REQUEST DATA: {dict(request.data)}
║ CONTENT-TYPE: {request.content_type}
╚════════════════════════════════════════════════════════════════════════╝
        """)
        
        try:
            result = super().update(request, *args, **kwargs)
            logger.error(f"✅ UPDATE SUCCESS - Row {row_id}")
            return result
        except Exception as e:
            logger.error(f"""
╔════════════════════════════════════════════════════════════════════════╗
║ ❌ UPDATE FAILED - Row {row_id}
╠════════════════════════════════════════════════════════════════════════╣
║ ERROR: {str(e)}
║ TYPE: {type(e).__name__}
╚════════════════════════════════════════════════════════════════════════╝
            """, exc_info=True)
            raise
    
    def partial_update(self, request, *args, **kwargs):
        """Override to add lock guard + comprehensive logging for PATCH operations"""
        instance = self.get_object()
        self._check_table_not_locked(instance.data_table, request)

        import logging
        logger = logging.getLogger('dataschema.views')
        
        row_id = kwargs.get('pk')
        logger.error(f"""
╔════════════════════════════════════════════════════════════════════════╗
║ 🟡 PATCH REQUEST → partial_update()
╠════════════════════════════════════════════════════════════════════════╣
║ ROW ID: {row_id}
║ USER: {request.user.username} (ID: {request.user.id})
║ QUERY PARAMS: {dict(request.query_params)}
║ REQUEST DATA: {dict(request.data)}
║ CONTENT-TYPE: {request.content_type}
╚════════════════════════════════════════════════════════════════════════╝
        """)
        
        try:
            result = super().partial_update(request, *args, **kwargs)
            logger.error(f"✅ PATCH SUCCESS - Row {row_id}")
            return result
        except Exception as e:
            logger.error(f"""
╔════════════════════════════════════════════════════════════════════════╗
║ ❌ PATCH FAILED - Row {row_id}
╠════════════════════════════════════════════════════════════════════════╣
║ ERROR: {str(e)}
║ TYPE: {type(e).__name__}
╚════════════════════════════════════════════════════════════════════════╝
            """, exc_info=True)
            raise

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a single data row by ID, respecting RBAC scoping.
        
        Query parameters:
            - data_table: table ID (required for scope verification)
        
        Returns:
            Row data with all fields, metadata (created_at, updated_at, created_by, updated_by),
            and evidence_count.
        """
        data_table_id = request.query_params.get("data_table")
        row_id = kwargs.get('pk')
        
        if not data_table_id:
            return Response(
                {'error': 'data_table query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not row_id:
            return Response(
                {'error': 'Row ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get the row and verify it belongs to the specified table
            row = DataRow.objects.get(pk=row_id, data_table_id=data_table_id, is_archived=False)
        except DataRow.DoesNotExist:
            return Response(
                {'error': 'Row not found or does not belong to the specified table'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check RBAC: user must have access to the row's table's module
        user = request.user
        if not (user.is_superuser or user_has_global_role(user, ["admin", "admins_group"])):
            # Check global visibility roles (viewers, analysts, auditors, dataowners with global scope)
            has_global_visibility = ScopedRole.objects.filter(
                user=user, is_active=True, org_unit=None, module=None,
                group__name__in=VISIBILITY_ROLES,
            ).exists()
            if has_global_visibility:
                # User has global visibility — allow access to any module
                pass
            else:
                allowed = get_allowed_module_ids(
                    user, ["admin", "admins_group", "dataowners_group", "auditors_group",
                           "viewers_group", "analysts_group"]
                )
                if row.data_table.module_id not in allowed:
                    return Response(
                        {'error': 'You do not have permission to access this row'},
                        status=status.HTTP_403_FORBIDDEN
                    )
        
        # Serialize and return
        serializer = self.get_serializer(row)
        return Response(serializer.data)

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

        # Delegate to service (raises ValueError with user-facing message on error)
        try:
            results = BulkImportService.import_rows(
                data_table, file,
                column_mapping=column_mapping_str,
                created_by=request.user,
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

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
        
        csv_content = BulkImportService.generate_template(
            data_table, include_example=include_example
        )
        
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
        data_table_id = self.request.query_params.get("data_table")
        qs = SchemaChangeLog.objects.all()
        if module_id:
            qs = qs.filter(data_table__module_id=module_id)
        if data_table_id:
            qs = qs.filter(data_table_id=data_table_id)
        return qs


# --- TableRelation (Schema relations/lineage) ---
class TableRelationViewSet(ScopedViewSet):
    """
    CRUD for table relations (lineage, foreign keys, lookups).
    Read: data-owners in scope, Write: global admins only.
    """
    queryset = TableRelation.objects.select_related('from_table', 'from_field', 'to_table', 'to_field', 'created_by').order_by('-created_at')
    serializer_class = TableRelationSerializer
    permission_classes = [IsAuthenticated, ReadScopedWriteAdmin]
    required_role = ("admin", "admins_group", "dataowners_group")

    def get_queryset(self):
        qs = TableRelation.objects.select_related('from_table', 'from_field', 'to_table', 'to_field', 'created_by')
        from_table_id = self.request.query_params.get('from_table')
        to_table_id = self.request.query_params.get('to_table')
        if from_table_id:
            qs = qs.filter(from_table_id=from_table_id)
        if to_table_id:
            qs = qs.filter(to_table_id=to_table_id)
        return qs.distinct()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)