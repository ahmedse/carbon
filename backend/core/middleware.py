"""
Request-level observability middleware for the Data Trust Core platform.

Provides:
- Correlation ID generation and propagation
- Structured request/response logging with performance metrics
- Slow request detection and alerting
"""
import json
import logging
import time
import uuid
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('core.middleware')


class CorrelationIDMiddleware(MiddlewareMixin):
    """
    Injects a unique correlation ID for every request.
    
    - Reads 'X-Correlation-ID' from incoming headers or generates a new UUID
    - Attaches correlation_id to the request object
    - Includes 'X-Correlation-ID' in the response headers
    """
    
    def process_request(self, request):
        correlation_id = request.headers.get('X-Correlation-ID')
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        request.correlation_id = correlation_id
        return None
    
    def process_response(self, request, response):
        correlation_id = getattr(request, 'correlation_id', None)
        if correlation_id:
            response['X-Correlation-ID'] = correlation_id
        return response


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Logs structured request/response information with performance metrics.
    
    Features:
    - JSON-structured log entries for observability tooling
    - Request duration tracking
    - Slow request detection (>2s warning, >5s error)
    - User and authentication context
    - Correlation ID propagation
    """
    
    SLOW_REQUEST_WARNING_MS = 2000  # 2 seconds
    SLOW_REQUEST_ERROR_MS = 5000    # 5 seconds
    
    def process_request(self, request):
        request._start_time = time.time()
        return None
    
    def process_response(self, request, response):
        if not hasattr(request, '_start_time'):
            return response
        
        duration_ms = (time.time() - request._start_time) * 1000
        correlation_id = getattr(request, 'correlation_id', 'unknown')
        user = getattr(request, 'user', None)
        
        log_data = {
            'event': 'http_request',
            'correlation_id': correlation_id,
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
            'duration_ms': round(duration_ms, 2),
            'user': user.username if user and user.is_authenticated else 'anonymous',
            'ip': self._get_client_ip(request),
        }
        
        # Add query params for GET requests (avoid logging sensitive data in POST bodies)
        if request.method == 'GET' and request.GET:
            log_data['query_params'] = dict(request.GET)
        
        # Detect slow requests
        if duration_ms > self.SLOW_REQUEST_ERROR_MS:
            logger.error(
                'Slow request detected',
                extra={'structured': log_data, 'performance_issue': 'critical'}
            )
        elif duration_ms > self.SLOW_REQUEST_WARNING_MS:
            logger.warning(
                'Slow request detected',
                extra={'structured': log_data, 'performance_issue': 'warning'}
            )
        else:
            logger.info(
                'Request completed',
                extra={'structured': log_data}
            )
        
        return response
    
    def _get_client_ip(self, request):
        """Extract client IP from request headers or META."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')


class StructuredLoggingFilter(logging.Filter):
    """
    Logging filter that formats structured data as JSON.
    
    If the log record has a 'structured' attribute (dict), it will be
    serialized as JSON and appended to the message.
    """
    
    def filter(self, record):
        if hasattr(record, 'structured') and isinstance(record.structured, dict):
            try:
                record.structured_json = json.dumps(record.structured)
            except (TypeError, ValueError):
                record.structured_json = str(record.structured)
        else:
            record.structured_json = ''
        return True
