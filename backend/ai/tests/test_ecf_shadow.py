"""ECF-4 — Shadow logger for resolve_entity vs legacy list/get parity."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai.engine.agent.tools import (
    build_shadow_diff,
    emit_resolve_entity_shadow,
    log_resolve_entity_shadow,
    _legacy_resolve_via_list_get,
)


class TestBuildShadowDiff:
    def test_shape(self):
        diff = build_shadow_diff({"found": True}, {"found": False, "path": "list_employees"})
        assert diff == {
            "new_result": {"found": True},
            "legacy_result": {"found": False, "path": "list_employees"},
        }


class TestLogResolveEntityShadow:
    def test_emits_structured_json(self, caplog):
        import logging

        with caplog.at_level(logging.INFO, logger="pulse.ecf.shadow"):
            diff = log_resolve_entity_shadow(
                entity_type="employee",
                query="1046",
                new_result={"found": True, "action": "match"},
                legacy_result={"found": False, "path": "list_employees"},
            )

        assert diff["new_result"]["found"] is True
        assert diff["legacy_result"]["found"] is False
        assert any("ECF_SHADOW" in r.message for r in caplog.records)
        payload = None
        for r in caplog.records:
            if "ECF_SHADOW" in r.message:
                # message is "ECF_SHADOW {...}"
                payload = json.loads(r.message.split("ECF_SHADOW ", 1)[1])
                break
        assert payload is not None
        assert payload["event"] == "ecf_shadow_diff"
        assert payload["query"] == "1046"
        assert "shadow_diff" in payload
        assert payload["shadow_diff"]["new_result"]["found"] is True

    def test_fail_open_on_logger_error(self):
        bad_logger = MagicMock()
        bad_logger.info.side_effect = RuntimeError("boom")
        bad_logger.exception = MagicMock()
        with patch("ai.engine.agent.tools._shadow_logger", bad_logger):
            diff = log_resolve_entity_shadow(
                entity_type="employee",
                query="x",
                new_result={"found": False},
                legacy_result={"found": False},
            )
        assert "new_result" in diff
        bad_logger.exception.assert_called()


class TestLegacyResolve:
    @pytest.mark.asyncio
    async def test_get_employee_numeric_hit(self):
        executor = SimpleNamespace(
            instance_config={
                "tools": {
                    "slug_resolution": [
                        {
                            "detail_endpoint": "get_employee",
                            "list_endpoint": "list_employees",
                            "match_fields": ["employee_no", "name_en_given", "name_en_family"],
                        }
                    ]
                }
            },
            get_catalog_entry=lambda name: {
                "get_employee": {"path": "/carbon-api/people/employees/{id}/"},
                "list_employees": {"path": "/carbon-api/people/employees/"},
            }.get(name),
            call_api_direct=AsyncMock(
                return_value={
                    "status_code": 200,
                    "data": {"id": 247, "employee_no": "1046", "full_name": "Sanavulla Shaik"},
                }
            ),
        )
        out = await _legacy_resolve_via_list_get(executor, "1046")
        assert out["found"] is True
        assert out["path"] == "get_employee"
        assert out["record"]["employee_no"] == "1046"

    @pytest.mark.asyncio
    async def test_list_scan_name_hit(self):
        executor = SimpleNamespace(
            instance_config={
                "tools": {
                    "slug_resolution": [
                        {
                            "detail_endpoint": "get_employee",
                            "list_endpoint": "list_employees",
                            "match_fields": ["employee_no", "name_en_given", "name_en_family"],
                        }
                    ]
                }
            },
            get_catalog_entry=lambda name: {
                "get_employee": {"path": "/carbon-api/people/employees/{id}/"},
                "list_employees": {"path": "/carbon-api/people/employees/"},
            }.get(name),
            call_api_direct=AsyncMock(
                return_value={
                    "status_code": 200,
                    "data": {
                        "total": 530,
                        "count": 2,
                        "truncated": True,
                        "results": [
                            {"id": 9, "employee_no": "1009", "name_en_given": "Reena", "name_en_family": "Sekaran"},
                            {"id": 1, "employee_no": "1001", "name_en_given": "Wellie", "name_en_family": "Eslit"},
                        ],
                    },
                }
            ),
        )
        out = await _legacy_resolve_via_list_get(executor, "Reena")
        assert out["found"] is True
        assert out["path"] == "list_employees"
        assert out.get("truncated") is True
        assert out["record"]["name_en_given"] == "Reena"


class TestEmitShadowWhenFlagOn:
    @pytest.mark.asyncio
    async def test_emits_when_ecf_enabled(self, caplog):
        import logging

        executor = SimpleNamespace(
            instance_config={
                "tools": {
                    "slug_resolution": [
                        {
                            "detail_endpoint": "get_employee",
                            "list_endpoint": "list_employees",
                            "match_fields": ["employee_no", "name_en_given", "name_en_family"],
                        }
                    ]
                }
            },
            get_catalog_entry=lambda name: {
                "get_employee": {"path": "/carbon-api/people/employees/{id}/"},
                "list_employees": {"path": "/carbon-api/people/employees/"},
            }.get(name),
            call_api_direct=AsyncMock(
                return_value={
                    "status_code": 404,
                    "data": {"detail": "Employee not found"},
                }
            ),
        )
        # After 404 on get, legacy falls through to list — mock second call.
        executor.call_api_direct = AsyncMock(
            side_effect=[
                {"status_code": 404, "data": {"detail": "not found"}},
                {
                    "status_code": 200,
                    "data": {
                        "total": 10,
                        "count": 1,
                        "results": [
                            {"id": 247, "employee_no": "1046", "name_en_given": "Sanavulla"},
                        ],
                    },
                },
            ]
        )

        with patch(
            "ai.engine.agent.tools.get_settings",
            lambda: SimpleNamespace(ECF_ENABLED=True),
        ), caplog.at_level(logging.INFO, logger="pulse.ecf.shadow"):
            diff = await emit_resolve_entity_shadow(
                executor=executor,
                entity_type="employee",
                query="1046",
                new_result={"found": True, "action": "match", "matched_field": "identifier"},
            )

        assert diff is not None
        assert diff["new_result"]["found"] is True
        assert diff["legacy_result"]["found"] is True
        assert any("ECF_SHADOW" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_noop_when_flag_off(self, caplog):
        import logging

        executor = SimpleNamespace(
            instance_config={},
            get_catalog_entry=lambda *_: None,
            call_api_direct=AsyncMock(),
        )
        with patch(
            "ai.engine.agent.tools.get_settings",
            lambda: SimpleNamespace(ECF_ENABLED=False),
        ), caplog.at_level(logging.INFO, logger="pulse.ecf.shadow"):
            out = await emit_resolve_entity_shadow(
                executor=executor,
                entity_type="employee",
                query="1046",
                new_result={"found": True},
            )
        assert out is None
        assert not any("ECF_SHADOW" in r.message for r in caplog.records)
        executor.call_api_direct.assert_not_called()

    @pytest.mark.asyncio
    async def test_fail_open_when_legacy_raises(self):
        executor = SimpleNamespace(
            instance_config={
                "tools": {
                    "slug_resolution": [
                        {
                            "detail_endpoint": "get_employee",
                            "list_endpoint": "list_employees",
                            "match_fields": ["employee_no"],
                        }
                    ]
                }
            },
            get_catalog_entry=lambda name: {"path": "/x/{id}/"} if name == "get_employee" else {"path": "/x/"},
            call_api_direct=AsyncMock(side_effect=RuntimeError("host down")),
        )
        with patch(
            "ai.engine.agent.tools.get_settings",
            lambda: SimpleNamespace(ECF_ENABLED=True),
        ):
            # Should not raise — legacy path returns error dict, then logs.
            diff = await emit_resolve_entity_shadow(
                executor=executor,
                entity_type="employee",
                query="1046",
                new_result={"found": True},
            )
        assert diff is not None
        assert diff["legacy_result"].get("found") is False
        assert "error" in diff["legacy_result"]
