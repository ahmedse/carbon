# File: accounts/context_mixin.py

from accounts.models import Context

class ContextExtractorMixin:
    """
    Mixin to extract project context from request data or query params.
    Only allows 'project' as context type.
    """
    def get_project_id_from_request(self, request):
        # Try both data and query params
        context_id = (
            request.data.get("context_id")
            or request.query_params.get("context_id")
        )
        if context_id is not None:
            try:
                return int(context_id)
            except Exception:
                pass
        return None