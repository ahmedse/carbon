# File: accounts/context_mixin.py

class ContextExtractorMixin:
    """
    Mixin to extract project_id and module_id from request data, query params, or the object itself.
    """
    def get_project_and_module_id_from_request(self, request):
        # Try both data and query params
        project_id = (
            request.data.get("project_id")
            or request.query_params.get("project_id")
        )
        module_id = (
            request.data.get("module_id")
            or request.query_params.get("module_id")
        )
        try:
            project_id = int(project_id) if project_id is not None else None
        except Exception:
            project_id = None
        try:
            module_id = int(module_id) if module_id is not None else None
        except Exception:
            module_id = None

        # Try extracting from instance (for detail views)
        try:
            if hasattr(self, 'get_object'):
                obj = self.get_object()
                # For anything with .module
                if hasattr(obj, 'module') and hasattr(obj.module, 'project_id'):
                    if project_id is None:
                        project_id = obj.module.project_id
                    if module_id is None:
                        module_id = obj.module.id
                # For DataField or DataRow (nested deeper)
                if hasattr(obj, 'data_table') and hasattr(obj.data_table, 'module'):
                    if project_id is None:
                        project_id = obj.data_table.module.project_id
                    if module_id is None:
                        module_id = obj.data_table.module.id
        except Exception:
            pass
        return project_id, module_id

    # Optionally for legacy code:
    def get_project_id_from_request(self, request):
        project_id, _ = self.get_project_and_module_id_from_request(request)
        return project_id