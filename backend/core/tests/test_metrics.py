# File: backend/core/tests/test_metrics.py
# EPH-6A — Prometheus metrics endpoint + structured-log correlation tests.

import json
import logging

from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient

from core.log_filters import CorrelationIdFilter, clear_correlation_id, set_correlation_id
from pythonjsonlogger import jsonlogger

API_PREFIX = settings.API_PREFIX.strip('/')


class PrometheusEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_prometheus_endpoint_returns_200_text_plain(self):
        resp = self.client.get(f'/{API_PREFIX}/health/prometheus/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/plain', resp['Content-Type'])

    def test_prometheus_body_contains_api_requests_total(self):
        # Fire a request first so the counter series is registered.
        self.client.get(f'/{API_PREFIX}/health/')
        resp = self.client.get(f'/{API_PREFIX}/health/prometheus/')
        self.assertIn(b'carbon_api_requests_total', resp.content)

    def test_prometheus_body_contains_duration_histogram(self):
        self.client.get(f'/{API_PREFIX}/health/')
        resp = self.client.get(f'/{API_PREFIX}/health/prometheus/')
        self.assertIn(b'carbon_api_duration_seconds', resp.content)

    def test_existing_health_metrics_still_work(self):
        resp = self.client.get(f'/{API_PREFIX}/health/metrics/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/plain', resp['Content-Type'])
        self.assertIn(b'carbon_database_up', resp.content)


class CorrelationIdFilterTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_json_log_entry_is_valid_json(self):
        fmt = jsonlogger.JsonFormatter(
            '%(asctime)s %(levelname)s %(name)s %(message)s %(correlation_id)s'
        )
        record = logging.LogRecord(
            'core.test', logging.INFO, __file__, 1, 'hello world', None, None,
        )
        CorrelationIdFilter().filter(record)
        parsed = json.loads(fmt.format(record))
        for key in ('levelname', 'name', 'message', 'correlation_id'):
            self.assertIn(key, parsed)
        self.assertEqual(parsed['message'], 'hello world')

    def test_correlation_id_injected_from_thread_local(self):
        set_correlation_id('corr-12345')
        try:
            record = logging.LogRecord(
                'core.test', logging.INFO, __file__, 1, 'msg', None, None,
            )
            self.assertTrue(CorrelationIdFilter().filter(record))
            self.assertEqual(record.correlation_id, 'corr-12345')
        finally:
            clear_correlation_id()

    def test_correlation_id_defaults_to_empty(self):
        clear_correlation_id()
        record = logging.LogRecord(
            'core.test', logging.INFO, __file__, 1, 'm', None, None,
        )
        CorrelationIdFilter().filter(record)
        self.assertEqual(record.correlation_id, '')

    def test_request_log_includes_correlation_id(self):
        logger = logging.getLogger('core.middleware')
        with self.assertLogs(logger, level='INFO') as cm:
            self.client.get(
                f'/{API_PREFIX}/health/',
                HTTP_X_CORRELATION_ID='trace-999',
            )
        self.assertTrue(
            [r for r in cm.records
             if getattr(r, 'correlation_id', None) == 'trace-999']
        )
