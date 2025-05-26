# File: accounts/context_mixin.py

from accounts.models import Context

class ContextExtractorMixin:
    """
    Mixin to extract the context (project/module) from the request.
    """

    def get_context_info(self, request):
        context_id = request.query_params.get("context_id") or request.headers.get("X-Context-Id")
        return context_id

    def get_context_from_request(self, request):
        context_id = request.query_params.get('context_id') or request.headers.get("X-Context-Id")
        if context_id and str(context_id).isdigit():
            try:
                context = Context.objects.get(id=int(context_id))
                return context
            except Context.DoesNotExist:
                return None
        if request.user.is_superuser:
            return None  # Or handle as you like
        return None