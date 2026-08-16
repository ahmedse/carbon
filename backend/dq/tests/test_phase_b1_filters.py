"""Regression tests for Phase B1 (F4) — declarative DQ Rules filters.

Before Phase B1, DQRuleViewSet had no DjangoFilterBackend, so
`filterset_fields = ['rule_level','rule_type','severity','is_active',
'dimension','archived']` was dead config. These tests lock in that the
declarative filters now actually filter list results.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from dq.models import DQRule


User = get_user_model()
BASE = '/carbon-api/dq'


class DeclarativeFilterTests(TestCase):
    """F4 — ?severity=&is_active=&dimension=&archived=&rule_level=&rule_type= filter."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='b1_admin', password='pass', is_staff=True, is_superuser=True)
        self.client.force_authenticate(self.admin)

        # Flat-field rules (no definition) so save() does not resync columns.
        def _make(name, **kw):
            defaults = dict(
                rule_level='field_validation', rule_type='range',
                severity='error', is_active=True, dimension='validity',
                archived=False, created_by=self.admin,
            )
            defaults.update(kw)
            return DQRule.objects.create(name=name, **defaults)

        self.a = _make('A error validity active')          # matches core filter
        self.b = _make('B warn validity active', severity='warn')
        self.c = _make('C error completeness active', dimension='completeness')
        self.d = _make('D error validity inactive', is_active=False)
        self.e = _make(
            'E error validity active business',
            rule_level='business_rule', rule_type='threshold')
        self.f = _make('F error validity active archived', archived=True)

    def _ids(self, response):
        # Pagination is disabled under pytest (CarbonPageNumberPagination
        # returns None), so the list endpoint returns a bare list of items.
        return {item['id'] for item in response.data}

    def test_default_list_excludes_archived(self):
        r = self.client.get(f'{BASE}/rules/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(self._ids(r), {self.a.id, self.b.id, self.c.id,
                                        self.d.id, self.e.id})

    def test_severity_is_active_dimension_combined(self):
        r = self.client.get(
            f'{BASE}/rules/', {'severity': 'error', 'is_active': 'true',
                               'dimension': 'validity'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        # a and e both match; b (warn), c (completeness), d (inactive) don't;
        # f is archived and excluded by default.
        self.assertEqual(self._ids(r), {self.a.id, self.e.id})

    def test_rule_level_and_rule_type_combined_no_double_filter(self):
        # rule_level/rule_type are filtered by BOTH the filterset and the manual
        # get_queryset() branch — combined query must intersect to the same set.
        r = self.client.get(
            f'{BASE}/rules/', {'rule_level': 'field_validation',
                               'rule_type': 'range', 'severity': 'error'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(self._ids(r), {self.a.id, self.c.id, self.d.id})

    def test_archived_filter_with_include_archived(self):
        r = self.client.get(
            f'{BASE}/rules/', {'include_archived': '1', 'archived': 'true'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(self._ids(r), {self.f.id})
