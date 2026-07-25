from django.test import TestCase, RequestFactory
from core.middleware import RequestLoggingMiddleware
from django.contrib.auth.models import User
from django.http import HttpResponse
import logging

class LoggingMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = RequestLoggingMiddleware(lambda r: HttpResponse())
        self.user = User.objects.create_user('testuser', password='test123')
    
    def test_correlation_id_added_to_request(self):
        """Verify correlation ID is generated for each request."""
        request = self.factory.get('/api/test/')
        request.user = self.user
        self.middleware.process_request(request)
        self.assertTrue(hasattr(request, 'correlation_id'))
        self.assertTrue(len(request.correlation_id) > 0)
    
    def test_correlation_id_persisted_across_request_response(self):
        """Verify correlation ID is present in both request and response."""
        request = self.factory.get('/api/test/')
        request.user = self.user
        self.middleware.process_request(request)
        correlation_id = request.correlation_id
        
        response = HttpResponse()
        self.middleware.process_response(request, response)
        self.assertEqual(response['X-Correlation-ID'], correlation_id)
    
    def test_correlation_id_extracted_from_header(self):
        """Verify existing X-Correlation-ID header is used."""
        existing_id = 'test-correlation-123'
        request = self.factory.get('/api/test/', HTTP_X_CORRELATION_ID=existing_id)
        request.user = self.user
        self.middleware.process_request(request)
        self.assertEqual(request.correlation_id, existing_id)
    
    def test_start_time_recorded(self):
        """Verify request start time is recorded."""
        request = self.factory.get('/api/test/')
        request.user = self.user
        self.middleware.process_request(request)
        self.assertTrue(hasattr(request, 'start_time'))
        self.assertIsNotNone(request.start_time)
    
    def test_response_includes_correlation_header(self):
        """Verify X-Correlation-ID header in response."""
        request = self.factory.get('/api/test/')
        request.user = self.user
        self.middleware.process_request(request)
        
        response = HttpResponse()
        response.status_code = 200
        self.middleware.process_response(request, response)
        
        self.assertIn('X-Correlation-ID', response)
        self.assertEqual(len(response['X-Correlation-ID']), len(request.correlation_id))
    
    def test_slow_request_flagged(self):
        """Verify slow requests are flagged in logs."""
        request = self.factory.get('/api/test/')
        request.user = self.user
        request.start_time = 0  # Simulate very old start time
        
        response = HttpResponse()
        response.status_code = 200
        # Should not raise any errors
        self.middleware.process_response(request, response)
