"""``unit_converter`` — domain-agnostic unit conversion (G-C non-carbon proof).

The FIRST capability added purely through the plugin registry with ZERO edits to
the engine spine (``tools.py`` / ``runner.py``). It proves G-C's exit gate:
*"add a non-carbon tool with zero engine edits."*

Read-only, deterministic, stdlib-only — no network, no Django ORM, no Carbon
apps, no carbon vocabulary. The engine's S3 planner learns of it only because
this plugin declares ``chat_visible=True`` and is registered at startup; the
``runner.py`` chat allow-set now derives plugin tools from the registry, so a
new tool requires no spine edit.

Guardrails honored (non-negotiable):

  * **RULE_20** — zero upward imports: stdlib only + the plugin base.
  * **RULE_21** — read-only: ``requires_confirmation=False``, nothing staged.
  * **Fail-visible** — unknown units/categories return ``{"error": ...}``,
    never a guessed number.
"""
from __future__ import annotations

import logging
from typing import Any

from ai.engine.agent.plugins import ToolPlugin

logger = logging.getLogger("carbon.ai.plugins.unit_converter")

#: Linear conversion tables: unit → multiplier to the SI base of that family.
_LENGTH: dict[str, float] = {
    "meter": 1.0, "kilometer": 1000.0, "centimeter": 0.01, "millimeter": 0.001,
    "mile": 1609.344, "yard": 0.9144, "foot": 0.3048, "inch": 0.0254,
}
_MASS: dict[str, float] = {
    "kilogram": 1.0, "gram": 0.001, "milligram": 1e-6,
    "tonne": 1000.0, "pound": 0.45359237, "ounce": 0.028349523125,
}
_VOLUME: dict[str, float] = {
    "liter": 1.0, "milliliter": 0.001, "gallon": 3.785411784,
    "quart": 0.946352946, "cup": 0.2365882365,
}
_TABLES: dict[str, dict[str, float]] = {
    "length": _LENGTH, "mass": _MASS, "volume": _VOLUME,
}
_ALIASES: dict[str, str] = {
    "m": "meter", "km": "kilometer", "cm": "centimeter", "mm": "millimeter",
    "mi": "mile", "yd": "yard", "ft": "foot", "in": "inch",
    "kg": "kilogram", "g": "gram", "mg": "milligram", "t": "tonne",
    "lb": "pound", "oz": "ounce",
    "l": "liter", "ml": "milliliter", "gal": "gallon", "qt": "quart",
    # plurals
    "meters": "meter", "kilometers": "kilometer", "centimeters": "centimeter",
    "millimeters": "millimeter", "miles": "mile", "yards": "yard",
    "feet": "foot", "inches": "inch",
    "kilograms": "kilogram", "grams": "gram", "milligrams": "milligram",
    "tonnes": "tonne", "pounds": "pound", "ounces": "ounce",
    "liters": "liter", "milliliters": "milliliter", "gallons": "gallon",
    "quarts": "quart", "cups": "cup",
}


def _resolve_unit(raw: str) -> str:
    unit = (raw or "").strip().lower()
    return _ALIASES.get(unit, unit)


def _convert_linear(value: float, from_unit: str, to_unit: str, table: dict[str, float]) -> float:
    base = value * table[from_unit]
    return base / table[to_unit]


def _convert_temperature(value: float, from_unit: str, to_unit: str) -> float:
    f = _resolve_unit(from_unit)
    t = _resolve_unit(to_unit)
    # Normalize to Celsius.
    if f in ("c", "celsius"):
        celsius = value
    elif f in ("f", "fahrenheit"):
        celsius = (value - 32.0) * 5.0 / 9.0
    elif f in ("k", "kelvin"):
        celsius = value - 273.15
    else:
        raise ValueError(f"unknown temperature unit {from_unit!r}")

    if t in ("c", "celsius"):
        return celsius
    if t in ("f", "fahrenheit"):
        return celsius * 9.0 / 5.0 + 32.0
    if t in ("k", "kelvin"):
        return celsius + 273.15
    raise ValueError(f"unknown temperature unit {to_unit!r}")


class UnitConverter(ToolPlugin):
    name = "unit_converter"
    description = (
        "Convert a value between compatible units (length, mass, temperature, "
        "volume). Use it for any unit-conversion request, e.g. 'convert 10 "
        "miles to kilometers' or 'what is 32F in Celsius?'."
    )
    capability_claim = "I can convert between common units (length, mass, temperature, volume)."
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "value": {
                "type": "number",
                "description": "The numeric value to convert.",
            },
            "from_unit": {
                "type": "string",
                "description": "The unit to convert FROM (e.g. 'miles', 'kg', 'F').",
            },
            "to_unit": {
                "type": "string",
                "description": "The unit to convert TO (e.g. 'kilometers', 'lb', 'C').",
            },
        },
        "required": ["value", "from_unit", "to_unit"],
    }
    requires_confirmation = False
    capability: str | None = None
    app_identifier: str | None = None
    chat_visible = True

    async def execute(self, args: dict, *, ctx) -> dict:
        try:
            value = float(args.get("value"))
        except (TypeError, ValueError):
            return {"error": "Provide a numeric 'value' to convert."}

        from_raw = str(args.get("from_unit") or "")
        to_raw = str(args.get("to_unit") or "")
        if not from_raw or not to_raw:
            return {"error": "Provide both 'from_unit' and 'to_unit'."}

        from_unit = _resolve_unit(from_raw)
        to_unit = _resolve_unit(to_raw)

        # Temperature is non-linear — handled separately.
        if from_unit in ("c", "celsius", "f", "fahrenheit", "k", "kelvin") or \
           to_unit in ("c", "celsius", "f", "fahrenheit", "k", "kelvin"):
            try:
                result = _convert_temperature(value, from_unit, to_unit)
            except ValueError as exc:
                return {"error": str(exc)}
            return {
                "result": round(result, 6),
                "from_unit": from_unit,
                "to_unit": to_unit,
                "category": "temperature",
            }

        table: dict[str, float] | None = None
        category = ""
        for cat, tbl in _TABLES.items():
            if from_unit in tbl and to_unit in tbl:
                table = tbl
                category = cat
                break

        if table is None:
            return {
                "error": (
                    f"Units {from_raw!r} and {to_raw!r} are not in the same "
                    f"convertible family (length/mass/volume/temperature)."
                ),
            }

        return {
            "result": round(_convert_linear(value, from_unit, to_unit, table), 6),
            "from_unit": from_unit,
            "to_unit": to_unit,
            "category": category,
        }
