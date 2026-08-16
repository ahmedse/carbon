"""
Tests for ai/intelligence.py — CarbonIntelligence orchestrator.

Wave C. Tests the in-process provider, scope builder, and the
CarbonIntelligence class itself (sync + async submission).
"""

from unittest.mock import MagicMock, patch

from backend.ai.protocol import (
    AIProvider,
    DqValidateRequest,
    DqValidateResponse,
    DqRuleInput,
    ProviderStatus,
    Scope,
)
from backend.ai.intelligence import (
    CarbonIntelligence,
    build_scope,
)


# ── Test helpers ──────────────────────────────────────────────────────────


class _DummyProvider(AIProvider):
    """Minimal AIProvider for factory/swap testing."""

    @property
    def provider_name(self) -> str:
        return "dummy"

    @property
    def provider_version(self) -> str:
        return "0.0.0"

    def health_check(self) -> ProviderStatus:
        return ProviderStatus(name="dummy", version="0.0.0", healthy=True)

    def validate_dq(self, request):
        return DqValidateResponse(status="completed")

    def suggest_dq(self, request):
        raise NotImplementedError

    def query_nl(self, request):
        raise NotImplementedError

    def explain_query(self, request):
        raise NotImplementedError

    def detect_anomalies(self, request):
        raise NotImplementedError

    def explain_anomaly(self, request):
        raise NotImplementedError

    def draft_report(self, request):
        raise NotImplementedError

    def analyze_schema(self, request):
        raise NotImplementedError

    def suggest_fix(self, request):
        raise NotImplementedError

    def chat(self, request):
        raise NotImplementedError


def _dummy_rule(**overrides):
    """Build a mock DQRule for testing."""
    mock = MagicMock()
    mock.pk = 42
    mock.severity = "error"
    mock.definition = {"params": {"prompt": "test prompt"}}
    # field_assignments
    field_mock = MagicMock()
    field_mock.data_field.name = "field_x"
    assn = MagicMock()
    assn.data_field = field_mock.data_field
    mock.field_assignments.select_related.return_value = [assn]
    for k, v in overrides.items():
        setattr(mock, k, v)
    return mock


# ── Scope builder tests ───────────────────────────────────────────────────


class TestBuildScope:
    def test_none_user_returns_empty_scope(self):
        scope = build_scope(None)
        assert scope.org_unit_ids == []
        assert scope.is_superuser is False

    def test_superuser_returns_wildcard_scope(self):
        user = MagicMock(is_superuser=True, is_staff=False, is_authenticated=True)
        user.pk = 13
        scope = build_scope(user)
        assert scope.org_unit_ids == ["*"]
        assert scope.is_superuser is True
        # Regression: ScopeGuard §1 requires a user_identifier on every scope,
        # including superusers (admin). Empty here used to reject every AI call
        # from a superuser with "Scope with empty user_identifier".
        assert scope.user_identifier == "13"

    def test_authenticated_user_with_roles(self):
        user = MagicMock(is_superuser=False, is_staff=False, is_authenticated=True)
        user.pk = 99

        role1 = MagicMock(org_unit_id=1, module_id=None)
        role1.group.name = "viewers_group"
        role2 = MagicMock(org_unit_id=2, module_id=10)
        role2.group.name = "dataowners_group"

        with patch("accounts.models.ScopedRole") as MockScopedRole:
            MockScopedRole.objects.filter.return_value.select_related.return_value = [
                role1, role2,
            ]
            scope = build_scope(user)
            assert "1" in scope.org_unit_ids
            assert "2" in scope.org_unit_ids
            assert "10" in scope.module_ids
            assert scope.is_read_only is False
            assert scope.user_identifier == "99"

    def test_read_only_only_roles_stay_read_only(self):
        user = MagicMock(is_superuser=False, is_staff=False, is_authenticated=True)
        user.pk = 100

        role1 = MagicMock(org_unit_id=1, module_id=None)
        role1.group.name = "viewers_group"
        role2 = MagicMock(org_unit_id=2, module_id=None)
        role2.group.name = "analysts_group"

        with patch("accounts.models.ScopedRole") as MockScopedRole:
            MockScopedRole.objects.filter.return_value.select_related.return_value = [
                role1, role2,
            ]
            scope = build_scope(user)
            assert "1" in scope.org_unit_ids
            assert scope.is_read_only is True
            assert scope.user_identifier == "100"


# ── CarbonIntelligence tests ──────────────────────────────────────────────


class TestCarbonIntelligence:
    def test_lazy_instantiation(self):
        ci = CarbonIntelligence()
        # Provider shouldn't be created until accessed
        assert ci._provider is None
        p = ci.provider
        assert p is not None
        assert ci._provider is p  # cached

    def test_health_check_delegates(self):
        ci = CarbonIntelligence()
        ci._provider = _DummyProvider()
        status = ci.health_check()
        assert status.healthy is True
        assert status.name == "dummy"

    def test_validate_dq_rule_builds_request(self):
        ci = CarbonIntelligence()
        ci._provider = _DummyProvider()
        rule = _dummy_rule()
        rows = [{"field_x": "hello"}]

        response = ci.validate_dq_rule(rule, rows)
        assert response.status == "completed"


class TestSubmitDqValidate:
    def test_sends_correct_envelope(self):
        with patch("backend.ai.intelligence.dispatch_task") as mock_dispatch:
            mock_dispatch.return_value = {
                "status": "completed",
                "task_id": "t-1",
                "result": {"results": []},
            }
            ci = CarbonIntelligence()
            response = ci.submit_dq_validate(
                rules=[{"id": "1", "prompt": "p", "fields": ["a"], "severity": "error"}],
                rows=[{"a": 1}],
                context={"table_name": "tbl"},
            )
            assert response["status"] == "completed"
            # Verify dispatch_task was called with correct task type
            call_args = mock_dispatch.call_args
            assert call_args.kwargs["task_type"] == "dq.validate"
            payload = call_args.kwargs["payload"]
            assert payload["rules"][0]["id"] == "1"
            assert payload["rows"] == [{"a": 1}]
            assert payload["context"]["table_name"] == "tbl"

    def test_returns_pulse_unavailable_on_error(self):
        with patch("backend.ai.intelligence.dispatch_task") as mock_dispatch:
            mock_dispatch.return_value = {"status": "pulse_unavailable", "error": {"code": "not_wired"}}
            ci = CarbonIntelligence()
            response = ci.submit_dq_validate(
                rules=[{"id": "1", "prompt": "p", "fields": [], "severity": "error"}],
                rows=[],
            )
            assert response["status"] == "pulse_unavailable"


class TestSubmitDqSuggest:
    def test_sends_correct_task_type(self):
        with patch("backend.ai.intelligence.dispatch_task") as mock_dispatch:
            mock_dispatch.return_value = {"status": "completed"}
            ci = CarbonIntelligence()
            response = ci.submit_dq_suggest({"name": "t", "fields": []})
            assert response["status"] == "completed"
            assert mock_dispatch.call_args.kwargs["task_type"] == "dq.suggest"
            payload = mock_dispatch.call_args.kwargs["payload"]
            assert payload["table"]["name"] == "t"


class TestSubmitAnomalyDetect:
    def test_sends_correct_task_type(self):
        with patch("backend.ai.intelligence.dispatch_task") as mock_dispatch:
            mock_dispatch.return_value = {"status": "completed"}
            ci = CarbonIntelligence()
            response = ci.submit_anomaly_detect({"history": []})
            assert response["status"] == "completed"
            assert mock_dispatch.call_args.kwargs["task_type"] == "anomaly.detect"
            payload = mock_dispatch.call_args.kwargs["payload"]
            assert payload["profile"]["history"] == []


class TestGetTaskStatus:
    def test_polls_correct_task(self):
        with patch("backend.ai.intelligence.get_task") as mock_get_task:
            mock_get_task.return_value = {"status": "completed", "result": {}}

            ci = CarbonIntelligence()
            result = ci.get_task_status("t-42")
            assert result["status"] == "completed"
            mock_get_task.assert_called_once_with("t-42", timeout=10)

    def test_handles_unavailable(self):
        with patch("backend.ai.intelligence.get_task") as mock_get_task:
            mock_get_task.return_value = {"status": "pulse_unavailable", "error": {"code": "not_found"}}

            ci = CarbonIntelligence()
            result = ci.get_task_status("t-42")
            assert result["status"] == "pulse_unavailable"


# ── Integration: provider swap ────────────────────────────────────────────


class TestProviderSwap:
    def test_carbon_intelligence_satisfies_typing(self):
        """CarbonIntelligence wraps a valid AIProvider."""
        ci = CarbonIntelligence()
        assert isinstance(ci.provider, AIProvider)
        assert callable(ci.health_check)
        assert callable(ci.validate_dq_rule)
        assert callable(ci.submit_dq_validate)
        assert callable(ci.submit_dq_suggest)
        assert callable(ci.submit_anomaly_detect)
        assert callable(ci.get_task_status)
