# File: accounts/context_mixin.py

from accounts.models import Context

class ContextExtractorMixin:
    """
    Mixin to extract project context from request data, query params, or the object itself.
    Only allows 'project' as context type.
    """
    def get_project_id_from_request(self, request):
        # Try both data and query params
        context_id = (
            request.data.get("context_id")
            or request.query_params.get("context_id")
        )
        print("[DEBUG] get_project_id_from_request resolved:", context_id)
        if context_id is not None:
            try:
                return int(context_id)
            except Exception:
                pass
        # Try extracting from instance (for detail views)
        try:     
            print("[DEBUG] get_project_id_from_request resolved:", context_id)       
            if hasattr(self, 'get_object'):
                obj = self.get_object()
                # For DataTable or anything with .module
                if hasattr(obj, 'module') and hasattr(obj.module, 'project_id'):
                    return obj.module.project_id
                # For DataField or DataRow (nested deeper)
                if hasattr(obj, 'data_table') and hasattr(obj.data_table, 'module') and hasattr(obj.data_table.module, 'project_id'):                    
                    return obj.data_table.module.project_id
        except Exception:
            pass
        return None