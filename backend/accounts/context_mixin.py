# File: accounts/context_mixin.py

class ContextExtractorMixin:
    """
    Robust mixin to extract project_id and module_id from request data, query params, or related objects.
    Handles all cases gracefully and provides debug output for diagnostics.
    """

    def get_project_and_module_id_from_request(self, request):
        project_id = (
            request.data.get("project_id")
            or request.query_params.get("project_id")
        )
        module_id = (
            request.data.get("module_id")
            or request.query_params.get("module_id")
        )

        # Convert to int if possible
        try:
            project_id = int(project_id) if project_id is not None else None
        except Exception:
            project_id = None
        try:
            module_id = int(module_id) if module_id is not None else None
        except Exception:
            module_id = None

        # Try extracting from object (detail views)
        obj = None
        try:
            if hasattr(self, 'get_object'):
                try:
                    obj = self.get_object()
                except Exception as e:
                    # print(f"[CTX_MIXIN DEBUG] get_object() failed: {e}")
                    obj = None
            if obj:
                # DataTable, DataField, or DataRow
                if hasattr(obj, 'module') and hasattr(obj.module, 'project_id'):
                    if project_id is None:
                        project_id = obj.module.project_id
                    if module_id is None:
                        module_id = obj.module.id
                elif hasattr(obj, 'data_table') and hasattr(obj.data_table, 'module'):
                    if project_id is None:
                        project_id = obj.data_table.module.project_id
                    if module_id is None:
                        module_id = obj.data_table.module.id
        except Exception as e:
            # print(f"[CTX_MIXIN DEBUG] Error extracting from object: {e}")
            x=1

        # Try extracting from data_table ID in request data or query params
        try:
            if project_id is None or module_id is None:
                data_table_id = (
                    request.data.get("data_table")
                    or request.query_params.get("data_table")
                )
                if data_table_id:
                    from dataschema.models import DataTable
                    try:
                        table = DataTable.objects.get(id=data_table_id)
                        if project_id is None:
                            project_id = table.module.project_id
                        if module_id is None:
                            module_id = table.module.id
                    except Exception as e:
                        # print(f"[CTX_MIXIN DEBUG] DataTable lookup failed: {e}")
                         x=1
        except Exception as e:
            # print(f"[CTX_MIXIN DEBUG] Error extracting from data_table: {e}")
             x=1

        # Fallback for ?module= or ?project= in query params
        try:
            if module_id is None:
                module_id = request.query_params.get("module")
                module_id = int(module_id) if module_id else None
        except Exception:
            module_id = None
        try:
            if project_id is None:
                project_id = request.query_params.get("project")
                project_id = int(project_id) if project_id else None
        except Exception:
            project_id = None

        # Final debug output
        # print(f"[CTX_MIXIN DEBUG] project_id={project_id}, module_id={module_id}")
        if project_id is None and module_id is None:
            # print("[CTX_MIXIN DEBUG] Could not extract context. This may be due to queryset being empty, missing IDs in the request, or object not found.")
             x=1

        return project_id, module_id

    # Optionally for legacy code:
    def get_project_id_from_request(self, request):
        project_id, _ = self.get_project_and_module_id_from_request(request)
        return project_id