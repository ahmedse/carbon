"""Carbon AI Intelligence — Emissions (Carbon Footprint) Domain.

AI CONTRACT §8: domain-specific AI operations for the emissions app.
"""

from __future__ import annotations

from ai.domain_protocol import (
    DomainAIOperations,
    DomainContext,
    register_domain,
)


class EmissionsDomainAI(DomainAIOperations):
    """Emissions (carbon footprint) domain AI operations."""

    app_identifier = "emissions"
    app_display_name = "Carbon Footprint"

    def get_domain_context(self) -> DomainContext:
        return DomainContext(
            app_identifier="emissions",
            domain_knowledge={
                "protocol": "GHG Protocol Corporate Standard",
                "scopes": {
                    "scope_1": "Direct emissions from owned/controlled sources",
                    "scope_2": "Indirect emissions from purchased energy",
                    "scope_3": "All other indirect emissions in value chain",
                },
                "ar_version": "IPCC AR6",
                "units": ["tCO2e", "kgCO2e", "MtCO2e"],
                "calculation_methods": ["location-based", "market-based"],
            },
            domain_config={
                "default_gwp_version": "AR6",
                "boundary_approaches": ["operational", "equity share", "financial control"],
            },
        )


register_domain("emissions", EmissionsDomainAI)
