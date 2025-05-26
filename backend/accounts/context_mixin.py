# accounts/context_mixin.py

from accounts.models import Context

class ContextExtractorMixin:
    def get_context_info(self, request):
        context_id = request.query_params.get("context_id") or request.headers.get("X-Context-Id")
        return context_id

    def get_context_from_request(self, request):
        context_id = request.query_params.get('context_id') or request.headers.get("X-Context-Id")
        print(f"Extracted context_id: {context_id}")
        if context_id and str(context_id).isdigit():
            try:
                context = Context.objects.get(id=int(context_id))
                print(f"Found context by id: {context}")
                return context
            except Context.DoesNotExist:
                print("Context not found by id.")
                return None
        elif context_id:
            print(f"Ignoring non-numeric context_id: {context_id}")

        if request.user.is_superuser:
            print("Superuser detected: allowing global action.")
            return "global"
        print("No valid context_id provided.")
        return None