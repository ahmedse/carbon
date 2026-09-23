"""Staff assurance board. Employees do not get this route."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class AssuranceBoardTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_superuser(
            username='assurance_staff', email='a@example.com', password='pass',
        )
        self.employee = User.objects.create_user(username='assurance_emp', password='pass')
        self.staff_auth = {
            'HTTP_AUTHORIZATION': f'Bearer {RefreshToken.for_user(self.staff).access_token}',
        }
        self.emp_auth = {
            'HTTP_AUTHORIZATION': f'Bearer {RefreshToken.for_user(self.employee).access_token}',
        }

    def test_anonymous_cannot_read_the_board(self):
        resp = self.client.get('/carbon-api/assurance/report/')
        self.assertIn(resp.status_code, (401, 403))

    def test_employee_cannot_read_the_board(self):
        resp = self.client.get('/carbon-api/assurance/report/', **self.emp_auth)
        self.assertEqual(resp.status_code, 403)

    def test_staff_report_includes_nibras_rules(self):
        resp = self.client.get(
            '/carbon-api/assurance/report/?pack=nibras&commit=board-test',
            **self.staff_auth,
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        ids = {row['rule_id'] for row in body['rows']}
        self.assertIn('NR-PAY-01', ids)
        self.assertIn('PL-SSE-01', ids)
        self.assertEqual(body['commit'], 'board-test')
        sse = next(row for row in body['rows'] if row['rule_id'] == 'PL-SSE-01')
        self.assertIn(sse['label'], ('configured', 'passed', 'planned'))

    def test_stream_once_is_event_stream(self):
        resp = self.client.get(
            '/carbon-api/assurance/stream/?once=1&commit=board-test',
            HTTP_ACCEPT='text/event-stream',
            **self.staff_auth,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp['Content-Type'].startswith('text/event-stream'))
        raw = b''.join(resp.streaming_content).decode('utf-8')
        self.assertTrue(raw.startswith('data: '))
        payload = json.loads(raw.split('data: ', 1)[1])
        self.assertIn('rows', payload)
        self.assertEqual(payload['commit'], 'board-test')
