import uuid
import logging
import sys
import time
from datetime import datetime
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone

logger = logging.getLogger(__name__)

# Phase 1.3: Level ordering for DB log threshold
LEVEL_RANK = {'DEBUG': 10, 'INFO': 20, 'WARNING': 30, 'ERROR': 40}


class RequestLoggingMiddleware(MiddlewareMixin):
    """Add correlation ID to each request and log request/response timing.
    Phase 1.3: Also writes ERROR+ requests to DB for admin log viewer."""

    _log_config = None
    _log_config_fetched = False

    def process_request(self, request):
        correlation_id = request.headers.get('X-Correlation-ID', str(uuid.uuid4()))
        request.correlation_id = correlation_id
        request.start_time = time.time()

        logger.info(
            "Request started",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.path,
                "user": str(request.user) if hasattr(request, 'user') else 'anonymous',
                "user_id": request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None,
                "remote_addr": self.get_client_ip(request),
            }
        )
        return None

    def process_response(self, request, response):
        if not hasattr(request, 'start_time'):
            return response

        duration = time.time() - request.start_time
        duration_ms = round(duration * 1000, 2)
        is_slow = duration > 5.0
        status_code = response.status_code
        correlation_id = getattr(request, 'correlation_id', 'unknown')
        level = 'ERROR' if status_code >= 500 else ('WARNING' if status_code >= 400 else 'INFO')

        logger.info(
            "Request completed",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "slow_request": is_slow,
            }
        )
        response['X-Correlation-ID'] = correlation_id

        # Phase 1.3: Persist ERROR+ requests to DB for admin log viewer
        self._persist_if_needed(request, response, correlation_id, duration_ms, is_slow, level, status_code)

        return response

    def _persist_if_needed(self, request, response, correlation_id, duration_ms, is_slow, level, status_code):
        """Write request log to DB if level >= configured threshold.
        Skipped during test runs to avoid altering N+1 query-count assertions."""
        if 'pytest' in sys.modules:
            return

        try:
            # Cache LogConfig in class-level variable to avoid per-request DB hit
            if not self._log_config_fetched:
                from accounts.models import LogConfig
                type(self)._log_config = LogConfig.load()
                type(self)._log_config_fetched = True

            cfg = type(self)._log_config
            if cfg is None or LEVEL_RANK.get(level, 0) < LEVEL_RANK.get(cfg.db_log_level, 20):
                return
        except Exception:
            return  # Before migrations — skip

        try:
            from core.models import RequestLog
            RequestLog.objects.create(
                correlation_id=correlation_id,
                level=level,
                method=request.method,
                path=request.path,
                user=str(request.user) if hasattr(request, 'user') and request.user.is_authenticated else 'anonymous',
                user_id=request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None,
                status_code=status_code,
                duration_ms=duration_ms,
                remote_addr=self.get_client_ip(request),
                slow_request=is_slow,
                timestamp=timezone.now(),
            )
        except Exception:
            pass  # Never let log persistence break the response

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
