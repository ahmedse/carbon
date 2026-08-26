"""Tests for AuditMiddleware — audit logging for mutating requests."""

import pytest
from django.test import override_settings, TestCase, RequestFactory, Client
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from core.middleware import AuditMiddleware
from core.models import RequestAuditLog

User = get_user_model()


@override_settings(CORE_REQUEST_AUDIT_ENABLED=True)
class TestAuditMiddlewareWithDB(TestCase):
    """Test AuditMiddleware with real database and authenticated API client."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.api_client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.token = self._get_token(self.user)

    @staticmethod
    def _get_token(user):
        """Generate JWT token for user."""
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)

    def test_post_request_creates_audit_log(self):
        """Test that POST request creates audit log with correct fields."""
        # Clear existing logs
        RequestAuditLog.objects.all().delete()

        # Make authenticated POST request to token endpoint
        response = self.api_client.post(
            '/carbon-api/token/',
            {'username': 'testuser', 'password': 'testpass'},
            format='json'
        )

        # Check response is successful
        self.assertIn(response.status_code, [200, 201])

        # Verify audit log was created
        audit_logs = RequestAuditLog.objects.filter(method='POST', path='/carbon-api/token/')
        self.assertEqual(audit_logs.count(), 1)

        log = audit_logs.first()
        self.assertEqual(log.method, 'POST')
        self.assertEqual(log.path, '/carbon-api/token/')
        self.assertIsNotNone(log.status_code)
        self.assertIsNotNone(log.duration_ms)
        self.assertIsNotNone(log.correlation_id)
        self.assertIsNotNone(log.ip_address)

    def test_get_request_does_not_create_audit_log(self):
        """Test that GET request does NOT create audit log."""
        RequestAuditLog.objects.all().delete()

        # Make GET request
        response = self.api_client.get('/carbon-api/health/', format='json')

        # Verify NO audit log was created (only mutating requests are audited)
        audit_logs = RequestAuditLog.objects.filter(method='GET')
        self.assertEqual(audit_logs.count(), 0)

    def test_skipped_paths_do_not_create_audit_log(self):
        """Test that requests to skipped paths don't create audit logs."""
        RequestAuditLog.objects.all().delete()

        skipped_paths = [
            '/health/',
            '/static/test.js',
            '/mediafiles/test.png',
            '/admin/',
        ]

        for path in skipped_paths:
            # These paths might not exist, but the middleware should skip them anyway
            # We test by creating a fake POST request and passing it through middleware
            middleware = AuditMiddleware(lambda r: HttpResponse())
            request = self.factory.post(path)
            request.user = self.user
            request.method = 'POST'
            request.path = path
            
            middleware.process_request(request)
            response = HttpResponse()
            response.status_code = 200
            middleware.process_response(request, response)

        # Verify NO audit logs for skipped paths
        self.assertEqual(RequestAuditLog.objects.count(), 0)

    def test_unauthenticated_post_logs_user_none(self):
        """Test that unauthenticated POST logs user=None."""
        RequestAuditLog.objects.all().delete()

        # Make unauthenticated POST request
        response = self.api_client.post(
            '/carbon-api/token/',
            {'username': 'nonexistent', 'password': 'wrong'},
            format='json'
        )

        # Verify audit log was created with user=None
        audit_logs = RequestAuditLog.objects.filter(method='POST', path='/carbon-api/token/')
        self.assertEqual(audit_logs.count(), 1)

        log = audit_logs.first()
        # Unauthenticated request should have user=None
        self.assertIsNone(log.user)

    def test_ip_extraction_from_x_forwarded_for(self):
        """Test that IP is correctly extracted from X-Forwarded-For header."""
        RequestAuditLog.objects.all().delete()

        # Create middleware and request
        middleware = AuditMiddleware(lambda r: HttpResponse())
        request = self.factory.post('/test-endpoint/')
        request.user = self.user
        request.method = 'POST'
        request.path = '/test-endpoint/'
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.7, 10.0.0.1'

        middleware.process_request(request)
        response = HttpResponse()
        response.status_code = 200
        middleware.process_response(request, response)

        # Verify IP was extracted correctly (first entry in X-Forwarded-For)
        audit_logs = RequestAuditLog.objects.filter(path='/test-endpoint/')
        self.assertEqual(audit_logs.count(), 1)
        self.assertEqual(audit_logs.first().ip_address, '203.0.113.7')

    def test_response_contains_correlation_id_header(self):
        """Test that response contains X-Correlation-ID header."""
        # Make authenticated POST request
        response = self.api_client.post(
            '/carbon-api/token/',
            {'username': 'testuser', 'password': 'testpass'},
            format='json'
        )

        # Verify X-Correlation-ID header is present
        self.assertIn('X-Correlation-ID', response)
        correlation_id = response['X-Correlation-ID']
        self.assertIsNotNone(correlation_id)
        self.assertGreater(len(correlation_id), 0)

    def test_correlation_id_persisted_to_audit_log(self):
        """Test that correlation ID from request is persisted to audit log."""
        RequestAuditLog.objects.all().delete()

        # Make authenticated POST request with custom correlation ID
        custom_correlation_id = 'test-corr-123-456-789'
        response = self.api_client.post(
            '/carbon-api/token/',
            {'username': 'testuser', 'password': 'testpass'},
            HTTP_X_CORRELATION_ID=custom_correlation_id,
            format='json'
        )

        # Verify audit log has correlation ID
        audit_logs = RequestAuditLog.objects.filter(method='POST', path='/carbon-api/token/')
        self.assertEqual(audit_logs.count(), 1)
        log = audit_logs.first()
        self.assertEqual(log.correlation_id, custom_correlation_id)

    @override_settings(CORE_REQUEST_AUDIT_ENABLED=False)
    def test_audit_disabled_does_not_create_log(self):
        """Test that when CORE_REQUEST_AUDIT_ENABLED=False, no logs are created."""
        RequestAuditLog.objects.all().delete()

        # Make authenticated POST request
        response = self.api_client.post(
            '/carbon-api/token/',
            {'username': 'testuser', 'password': 'testpass'},
            format='json'
        )

        # Verify NO audit log was created
        audit_logs = RequestAuditLog.objects.filter(method='POST', path='/carbon-api/token/')
        self.assertEqual(audit_logs.count(), 0)

    def test_middleware_failure_does_not_break_response(self):
        """Test that middleware failure does NOT propagate (response is still returned)."""
        RequestAuditLog.objects.all().delete()

        # Create middleware and request
        middleware = AuditMiddleware(lambda r: HttpResponse())
        request = self.factory.post('/test-endpoint/')
        request.user = self.user
        request.method = 'POST'
        request.path = '/test-endpoint/'

        middleware.process_request(request)
        response = HttpResponse()
        response.status_code = 200

        # Monkey-patch to make RequestAuditLog.objects.create raise an exception
        import core.models
        original_create = core.models.RequestAuditLog.objects.create
        def failing_create(*args, **kwargs):
            raise RuntimeError("Simulated database error")
        
        core.models.RequestAuditLog.objects.create = failing_create

        try:
            # Call process_response - should not raise despite the error
            result = middleware.process_response(request, response)
            # Verify response is returned normally (not None, not 500 error)
            self.assertIsNotNone(result)
            self.assertEqual(result.status_code, 200)
        finally:
            # Restore original create method
            core.models.RequestAuditLog.objects.create = original_create

    def test_put_request_creates_audit_log(self):
        """Test that PUT requests are audited."""
        RequestAuditLog.objects.all().delete()

        middleware = AuditMiddleware(lambda r: HttpResponse())
        request = self.factory.put('/api/resource/123/')
        request.user = self.user
        request.method = 'PUT'
        request.path = '/api/resource/123/'

        middleware.process_request(request)
        response = HttpResponse()
        response.status_code = 200
        middleware.process_response(request, response)

        audit_logs = RequestAuditLog.objects.filter(method='PUT')
        self.assertEqual(audit_logs.count(), 1)

    def test_patch_request_creates_audit_log(self):
        """Test that PATCH requests are audited."""
        RequestAuditLog.objects.all().delete()

        middleware = AuditMiddleware(lambda r: HttpResponse())
        request = self.factory.patch('/api/resource/123/')
        request.user = self.user
        request.method = 'PATCH'
        request.path = '/api/resource/123/'

        middleware.process_request(request)
        response = HttpResponse()
        response.status_code = 200
        middleware.process_response(request, response)

        audit_logs = RequestAuditLog.objects.filter(method='PATCH')
        self.assertEqual(audit_logs.count(), 1)

    def test_delete_request_creates_audit_log(self):
        """Test that DELETE requests are audited."""
        RequestAuditLog.objects.all().delete()

        middleware = AuditMiddleware(lambda r: HttpResponse())
        request = self.factory.delete('/api/resource/123/')
        request.user = self.user
        request.method = 'DELETE'
        request.path = '/api/resource/123/'

        middleware.process_request(request)
        response = HttpResponse()
        response.status_code = 204
        middleware.process_response(request, response)

        audit_logs = RequestAuditLog.objects.filter(method='DELETE')
        self.assertEqual(audit_logs.count(), 1)

    def test_query_string_is_captured(self):
        """Test that query string is captured in audit log."""
        RequestAuditLog.objects.all().delete()

        middleware = AuditMiddleware(lambda r: HttpResponse())
        request = self.factory.post('/api/resource/?filter=active&limit=10')
        request.user = self.user
        request.method = 'POST'
        request.path = '/api/resource/'
        request.META['QUERY_STRING'] = 'filter=active&limit=10'

        middleware.process_request(request)
        response = HttpResponse()
        response.status_code = 201
        middleware.process_response(request, response)

        audit_logs = RequestAuditLog.objects.filter(path='/api/resource/')
        self.assertEqual(audit_logs.count(), 1)
        self.assertEqual(audit_logs.first().query_string, 'filter=active&limit=10')

    def test_metrics_endpoint_is_skipped(self):
        """Test that requests containing /metrics are skipped."""
        RequestAuditLog.objects.all().delete()

        middleware = AuditMiddleware(lambda r: HttpResponse())
        request = self.factory.post('/api/metrics/custom')
        request.user = self.user
        request.method = 'POST'
        request.path = '/api/metrics/custom'

        middleware.process_request(request)
        response = HttpResponse()
        response.status_code = 200
        middleware.process_response(request, response)

        # Verify no audit log was created
        self.assertEqual(RequestAuditLog.objects.count(), 0)

    def test_authenticated_user_is_captured(self):
        """Test that authenticated user is correctly captured in audit log."""
        RequestAuditLog.objects.all().delete()

        middleware = AuditMiddleware(lambda r: HttpResponse())
        request = self.factory.post('/api/resource/')
        request.user = self.user
        request.method = 'POST'
        request.path = '/api/resource/'

        middleware.process_request(request)
        response = HttpResponse()
        response.status_code = 201
        middleware.process_response(request, response)

        audit_logs = RequestAuditLog.objects.filter(path='/api/resource/')
        self.assertEqual(audit_logs.count(), 1)
        self.assertEqual(audit_logs.first().user.id, self.user.id)
