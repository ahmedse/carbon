"""Block every request except password change until a forced reset is done."""

from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication

_ALLOWED_SUFFIXES = (
    '/token/',
    '/token/refresh/',
    '/accounts/change-password/',
    '/accounts/logout/',
    '/password-reset/',
    '/password-reset/confirm/',
    '/health/',
    '/health/metrics/',
    '/health/prometheus/',
)


def _allowed(path: str) -> bool:
    normalized = path.rstrip('/') + '/'
    return any(normalized.endswith(suffix) for suffix in _ALLOWED_SUFFIXES)


class PasswordChangeRequiredMiddleware:
    """JWT requests from an account that still holds the shared password stop here."""

    def __init__(self, get_response):
        self.get_response = get_response
        self._jwt = JWTAuthentication()

    def __call__(self, request):
        if request.method == 'OPTIONS' or _allowed(request.path):
            return self.get_response(request)
        try:
            auth = self._jwt.authenticate(request)
        except Exception:
            auth = None
        if auth is not None:
            user = auth[0]
            if getattr(user, 'must_change_password', False):
                return JsonResponse(
                    {
                        'code': 'password_change_required',
                        'detail': 'Set a new password before continuing.',
                    },
                    status=403,
                )
        return self.get_response(request)
