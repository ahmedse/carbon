"""EPH-3A — DQ Profiling Service + Scorecard API tests.

Covers:
  * profile_table() populates TableProfile (row_count) and FieldProfile
    (null_count, distinct_count, min/max/mean) via update_or_create
  * compute_scorecard() dimension breakdown + no-results zeros
  * GET /dq/tables/{id}/profile/ 404 when no profile
  * POST /dq/tables/{id}/profile/run/ 202 + task_id
"""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from dq.models import TableProfile, FieldProfile, DQRule, DQResult, RuleFieldAssignment
from dataschema.models import DataTable, DataField, DataRow
from core.models import Module

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser('prof_admin', 'p@b.com', 'pass123')


@pytest.fixture
def module_obj(db):
    return Module.objects.create(name='prof_module')


@pytest.fixture
def data_table(db, module_obj):
    """A table with no rows / no profiles (for 404 + scorecard tests)."""
    return DataTable.objects.create(
        title='Empty Prof Table', name='empty_prof_table', module=module_obj,
    )


@pytest.fixture
def profiled_table(db, module_obj):
    """A table with 3 fields + 3 rows (mirrors the existing profiling fixture)."""
    table = DataTable.objects.create(
        title='Prof Table', name='prof_table', module=module_obj,
    )
    DataField.objects.create(data_table=table, name='name', type='string', is_active=True)
    DataField.objects.create(data_table=table, name='age', type='number', is_active=True)
    DataField.objects.create(data_table=table, name='city', type='string', is_active=True)
    for name, age, city in [
        ('Alice', '30', 'Cairo'),
        (None, '25', 'Alex'),
        ('Bob', None, None),
    ]:
        DataRow.objects.create(
            data_table=table, values={'name': name, 'age': age, 'city': city},
        )
    return table


def _add_result(table, dimension, rule_type, passed):
    """Create a DQRule + table assignment + DQResult for a dimension."""
    rule = DQRule.objects.create(
        name=f'{dimension} rule',
        rule_type=rule_type,
        rule_level='field_validation',
        dimension=dimension,
        is_active=True,
    )
    RuleFieldAssignment.objects.create(rule=rule, data_table=table)
    DQResult.objects.create(
        rule=rule,
        passed=passed,
        status='passed' if passed else 'failed',
    )
    return rule


# ── profile_table() ──────────────────────────────────────────────────────

class TestProfiling:
    def test_profile_creates_table_profile_with_row_count(self, profiled_table):
        from dq.profiling_service import profile_table

        profile_table(profiled_table.id)

        tp = TableProfile.objects.filter(data_table=profiled_table).latest('profiled_at')
        assert tp.row_count == 3

    def test_profile_field_null_count(self, profiled_table):
        from dq.profiling_service import profile_table

        profile_table(profiled_table.id)

        fp = FieldProfile.objects.get(
            data_field__data_table=profiled_table, data_field__name='name',
        )
        assert fp.null_count == 1  # row 2 has name=None

    def test_profile_distinct_count_string(self, profiled_table):
        from dq.profiling_service import profile_table

        profile_table(profiled_table.id)

        fp = FieldProfile.objects.get(
            data_field__data_table=profiled_table, data_field__name='name',
        )
        assert fp.distinct_count == 2  # Alice, Bob

    def test_profile_min_max_mean_numeric(self, profiled_table):
        from dq.profiling_service import profile_table

        profile_table(profiled_table.id)

        fp = FieldProfile.objects.get(
            data_field__data_table=profiled_table, data_field__name='age',
        )
        assert fp.min_value == '25.0'
        assert fp.max_value == '30.0'
        assert fp.mean_value == 27.5


# ── compute_scorecard() ──────────────────────────────────────────────────

class TestScorecard:
    def test_scorecard_dimension_breakdown(self, data_table):
        from dq.scorecard_service import compute_scorecard

        _add_result(data_table, 'completeness', 'not_null', True)
        _add_result(data_table, 'validity', 'range', False)
        _add_result(data_table, 'accuracy', 'regex', True)
        _add_result(data_table, 'uniqueness', 'unique', False)

        scorecard = compute_scorecard(data_table.id)

        assert scorecard['total_rules'] == 4
        assert scorecard['dimensions']['completeness'] == {
            'passed': 1, 'failed': 0, 'score': 1.0,
        }
        assert scorecard['dimensions']['validity'] == {
            'passed': 0, 'failed': 1, 'score': 0.0,
        }
        assert scorecard['dimensions']['accuracy'] == {
            'passed': 1, 'failed': 0, 'score': 1.0,
        }
        assert scorecard['dimensions']['uniqueness'] == {
            'passed': 0, 'failed': 1, 'score': 0.0,
        }
        assert scorecard['quality_score'] == 0.5
        assert scorecard['last_run_at'] is not None

    def test_scorecard_no_results_zeros(self, data_table):
        from dq.scorecard_service import compute_scorecard

        scorecard = compute_scorecard(data_table.id)

        assert scorecard['quality_score'] == 0.0
        assert scorecard['total_rules'] == 0
        assert scorecard['last_run_at'] is None
        for dim in [
            'completeness', 'validity', 'accuracy',
            'uniqueness', 'consistency', 'timeliness',
        ]:
            assert scorecard['dimensions'][dim] == {
                'passed': 0, 'failed': 0, 'score': 0.0,
            }
        assert scorecard['profile_summary']['row_count'] == 0
        assert scorecard['profile_summary']['completeness_pct'] == 0.0


# ── API endpoints ────────────────────────────────────────────────────────

class TestProfileEndpoints:
    def test_profile_404_when_missing(self, api_client, superuser, data_table):
        api_client.force_authenticate(superuser)
        url = reverse('dq-table-profile', args=[data_table.id])
        response = api_client.get(url)
        assert response.status_code == 404

    def test_run_returns_202(self, api_client, superuser, profiled_table):
        api_client.force_authenticate(superuser)
        url = reverse('dq-table-profile-run', args=[profiled_table.id])
        response = api_client.post(url, format='json')
        assert response.status_code == 202
        assert response.data.get('task_id') is not None
        # Profiling actually ran (inline fallback) and persisted a profile.
        assert TableProfile.objects.filter(data_table=profiled_table).exists()
