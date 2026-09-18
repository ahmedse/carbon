"""GradeVance domain AI — advisory / coaching assist for EduOS (RULE_21).

Pulse drafts triage notes and coaching suggestions; the host
(``gradevance`` app) owns SoR mutations and summative release.
Never imports ``gradevance.models`` (RULE_3 sibling isolation).
"""

from __future__ import annotations

from typing import Any

from ai.adapter.types import ToolDef
from ai.domain_protocol import (
    DomainAIOperations,
    DomainContext,
    register_domain,
)


class GradeVanceDomainAI(DomainAIOperations):
    app_identifier = "gradevance"
    app_display_name = "GradeVance"

    supported_task_types = [
        "chat",
        "report_draft",
    ]

    entry_points = []

    starter_prompts = {
        "default": [
            {
                "label": "Explain LCT Semantics",
                "prompt": "Explain Semantic Gravity and Semantic Density for reflective writing in plain language for a marker.",
                "task_type": "chat",
            },
            {
                "label": "Draft coaching notes",
                "prompt": "Draft Strengths → Diagnosis → Action coaching notes for a formative reflection (placeholders for bands).",
                "task_type": "report_draft",
            },
            {
                "label": "HITL learning loop",
                "prompt": "How does an expert LCT code correction become a TranslationDevice anchor proposal in GradeVance?",
                "task_type": "chat",
            },
        ],
    }

    system_prompt_extension = (
        "You are assisting with GradeVance on EduOS — multi-domain assessment and "
        "coaching (medicine OSCE/OSPE, articles, reflective practice, and other "
        "faculties via config packs). Measurement (LCT Semantics where enabled) "
        "precedes judgment (declarative rubrics). HITL is mandatory for summative "
        "release; formative coaching may be advisory with an explicit watermark. "
        "Engine intelligence improves via versioned pack promotions from ExpertEdit "
        "events — never silent fine-tunes or silent cohort regrades. "
        "You are advisory only: never release marks, never publish devices/rubrics, "
        "and never invent κ statistics. Packs are discipline×genre specific — do not "
        "treat GradeVance as an Academic English-only product."
    )

    def validate_task_payload(
        self, task_type: str, payload: dict[str, Any]
    ) -> tuple[bool, str]:
        if payload.get("table_id"):
            return False, "GradeVance is a typed-model vertical — 'table_id' is not valid here."
        if task_type == "report_draft" and not (payload.get("module_id") or payload.get("topic")):
            return False, "'report_draft' requires 'module_id' or 'topic' in task_payload."
        return True, ""

    def get_domain_context(self) -> DomainContext:
        return DomainContext(
            app_identifier="gradevance",
            domain_knowledge={
                "concepts": [
                    "translation_device",
                    "rubric_pack",
                    "assignment_profile",
                    "analysis_run",
                    "semantic_gravity",
                    "semantic_density",
                    "expert_edit",
                    "proposal",
                    "formative_coaching",
                ],
                "modes": ["formative", "summative", "calibration"],
                "hitl": "mandatory_for_summative_release",
            },
            domain_config={
                "packs_root": "domain_packs/eduos",
                "learning": "config_promotion_not_silent_finetune",
            },
        )

    def get_tools(self) -> list[ToolDef]:
        return []


register_domain("gradevance", GradeVanceDomainAI)
