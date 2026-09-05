"""Pulse v2 Phase 6 — Carbon business context injection."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]


async def test_assembler_returns_string():
    """assemble() must return a str (possibly empty) even on an empty DB."""
    from ai.context.carbon_context import CarbonContextAssembler

    result = await CarbonContextAssembler().assemble(
        user=MagicMock(),
        app_identifier="emissions",
    )
    assert isinstance(result, str)


async def test_assembler_does_not_raise_on_model_error():
    """assemble() must return '' when every sub-query raises."""
    from ai.context.carbon_context import CarbonContextAssembler

    assembler = CarbonContextAssembler()
    with patch.object(
        assembler, "_get_active_period", AsyncMock(side_effect=Exception("DB down"))
    ):
        with patch.object(
            assembler, "_get_active_factors", AsyncMock(side_effect=Exception("DB down"))
        ):
            with patch.object(
                assembler,
                "_get_active_dq_rules_count",
                AsyncMock(side_effect=Exception("DB down")),
            ):
                result = await assembler.assemble(
                    user=MagicMock(), app_identifier="emissions"
                )

    assert result == ""


async def test_assembler_formats_factors_into_prompt():
    """When a factor is present, the block lists name + value + unit."""
    from ai.context.carbon_context import CarbonContextAssembler

    assembler = CarbonContextAssembler()
    with patch.object(
        assembler,
        "_get_active_period",
        AsyncMock(return_value="FY 2025 (2025-01-01 to 2025-12-31)"),
    ):
        with patch.object(
            assembler,
            "_get_active_factors",
            AsyncMock(
                return_value=[
                    {"name": "Electricity", "factor": "2.5", "unit": "kg CO2e/kWh"}
                ]
            ),
        ):
            with patch.object(
                assembler, "_get_active_dq_rules_count", AsyncMock(return_value=7)
            ):
                result = await assembler.assemble(app_identifier="emissions")

    assert "FY 2025" in result
    assert "Electricity" in result
    assert "2.5" in result
    assert "kg CO2e/kWh" in result
    assert "Active DQ rules" in result
    assert "7" in result
