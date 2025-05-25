# accounts/context_mixin.py

from accounts.models import Context

class ContextExtractorMixin:
    def get_context_info(self, request):
        context_type = request.query_params.get("context_type") or request.headers.get("X-Context-Type")
        context_name = (
            request.query_params.get(context_type)
            or request.headers.get("X-Context-Name")
        )
        return (context_type, context_name)

    def get_context_from_request(self, request):
        context_type, context_name = self.get_context_info(request)
        if context_type and context_name:
            kwargs = {context_type: context_name, "type": context_type}
            return Context.objects.filter(**kwargs).first()
        return None