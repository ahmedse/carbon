"""get_entity_details must route to live endpoints, not dead-end.

Regression cover: asking for the leave balance produced "Entity
'leave_balance' not found" while ``get_my_leave_balance`` sat in the catalog.
"""
from __future__ import annotations

import pytest

from ai.engine.agent.tools import (
    _default_confirmation_message,
    _nearest_catalog_reads,
    _resolve_catalog_alias,
    execute_get_entity_details,
)

CATALOG = {
    "api_catalog": [
        {"name": "get_my_leave_balance", "method": "GET"},
        {"name": "list_my_leave", "method": "GET"},
        {"name": "submit_my_leave", "method": "POST"},
        {"name": "list_leave_entitlements", "method": "GET"},
        {"name": "get_my_payslip", "method": "GET"},
    ],
}


@pytest.mark.parametrize("asked,expected", [
    ("get_my_leave_balance", "get_my_leave_balance"),   # exact
    ("leave_balance", "get_my_leave_balance"),          # stop-words folded
    ("my leave balance", "get_my_leave_balance"),       # spaces + "my"
    ("LeaveBalance", None),                             # single token, no split
    ("payslip", "get_my_payslip"),
    ("leave_entitlements", "list_leave_entitlements"),
])
def test_alias_resolution(asked, expected):
    assert _resolve_catalog_alias(asked, CATALOG) == expected


def test_alias_never_resolves_to_a_mutation():
    # "submit_my_leave" is POST — an entity lookup must not stage a write.
    assert _resolve_catalog_alias("submit_leave", CATALOG) is None


def test_unknown_entity_is_not_aliased():
    assert _resolve_catalog_alias("carbon_footprint", CATALOG) is None


@pytest.mark.parametrize("api,expected", [
    ("submit_my_leave", "Submit your leave?"),
    ("create_leave_record", "Create leave record?"),
    ("compute_payroll_run", "Compute payroll run?"),
    ("", "Go ahead with this action?"),
])
def test_default_confirm_prompt_has_no_method_or_path(api, expected):
    assert _default_confirmation_message(api) == expected


def test_nearest_reads_suggests_live_endpoints():
    assert _nearest_catalog_reads("leave_balance", CATALOG)[0] == "get_my_leave_balance"


@pytest.mark.asyncio
async def test_miss_offers_live_endpoints_instead_of_a_dead_end():
    class _Store:
        async def get_entity(self, instance_id, name):
            return None

    class _Executor:
        instance_config = CATALOG

    result = await execute_get_entity_details(
        "carbon_footprint",
        knowledge_store=_Store(),
        instance_id="nibras",
        executor=None,
    )
    assert result["entity"] is None

    result = await execute_get_entity_details(
        "leave_policy_notes",
        knowledge_store=_Store(),
        instance_id="nibras",
        executor=_Executor(),
    )
    assert result["entity"] is None
    assert "get_my_leave_balance" in result["available_apis"] or \
           "list_my_leave" in result["available_apis"]
