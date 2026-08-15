"""Carbon AI Intelligence — Water Management Domain.

AI CONTRACT §8: domain-specific AI operations for the water app.

Water domain covers water withdrawal, consumption, discharge, and reuse.
Primary table: ``monthly_water`` (``total_m3`` cubic meters per building),
with ``monthly_chilled_water`` (ton-hours TR) for district cooling.
"""

from __future__ import annotations

from ai.domain_protocol import (
    DomainAIOperations,
    DomainContext,
    register_domain,
)


class WaterDomainAI(DomainAIOperations):
    """Water management domain AI operations."""

    app_identifier = "water"
    app_display_name = "Water Management"

    def get_domain_context(self) -> DomainContext:
        return DomainContext(
            app_identifier="water",
            domain_knowledge={
                "protocol": "GRI 303: Water and Effluents 2018",
                "scopes": {
                    "withdrawal": "Total water withdrawn from all sources",
                    "consumption": "Water consumed and not returned to source",
                    "discharge": "Water discharged to receiving water bodies",
                    "recycled": "Water recycled or reused on-site",
                },
                "units": ["m3", "liters", "ML"],
            },
            domain_config={
                "default_unit": "m3",
                "key_tables": ["monthly_water", "monthly_chilled_water"],
                "measurement_methods": ["metered", "estimated", "vendor-invoice"],
            },
        )


register_domain("water", WaterDomainAI)
