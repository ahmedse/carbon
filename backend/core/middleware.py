import uuid
import logging
import time
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(MiddlewareMixin):
    """Add correlation ID to each request and log request/response timing."""
    
    def process_request(self, request):
        # Generate or extract correlation ID
        correlation_id = request.headers.get('X-Correlation-ID', str(uuid.uuid4()))
        request.correlation_id = correlation_id
        request.start_time = time.time()
        
        # Log incoming request
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
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            logger.info(
                "Request completed",
                extra={
                    "correlation_id": getattr(request, 'correlation_id', 'unknown'),
                    "method": request.method,
                    "path": request.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                    "slow_request": duration > 5.0,
                }
            )
            # Add correlation ID to response headers
            response['X-Correlation-ID'] = request.correlation_id
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
