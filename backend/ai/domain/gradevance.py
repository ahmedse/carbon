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
        "LCT codes are Maton SG± and SD± only (plus/minus). Do not invent SG++/SG--. "
        "Segmentation calibration (boundary F1) is separate from coding κ — point "
        "users to Teach Calibration → Resegment or Run workbench Resegment. "
        "suggest_splits is draft assist only; never claim spans were written. "
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
                    "maton_sg_sd_binary",
                    "segmentation_calibration",
                    "expert_edit",
                    "proposal",
                    "formative_coaching",
                ],
                "modes": ["formative", "summative", "calibration"],
                "hitl": "mandatory_for_summative_release",
                "lct_codes": ["SG+", "SG-", "SD+", "SD-"],
                "pulse_role": "advisory_only",
            },
            domain_config={
                "packs_root": "domain_packs/eduos",
                "learning": "config_promotion_not_silent_finetune",
            },
        )

    def get_tools(self) -> list[ToolDef]:
        """Read-only GradeVance host tools — Teach UIs own mutations."""
        return [
            ToolDef(
                id="gradevance.get_calibration",
                description=(
                    "Fetch held-out coding κ (SG/SD) and segmentation span-overlap F1 "
                    "for a GradeVance profile pack. Use before advising on publish readiness."
                ),
                required_capability="gradevance:view",
                is_mutation=False,
                domain="gradevance",
                input_schema={
                    "type": "object",
                    "properties": {
                        "profile_pack_id": {
                            "type": "string",
                            "description": "Profile pack id (e.g. naa_cycle1_exam_prep).",
                        },
                        "profile_version": {
                            "type": "integer",
                            "description": "Profile version (default 1).",
                        },
                    },
                },
                output_description="Publish gate, SG/SD κ, segmentation_fidelity, segment_pairs sample.",
            ),
            ToolDef(
                id="gradevance.list_review_queue",
                description="List open HITL review items for marker triage.",
                required_capability="gradevance:view",
                is_mutation=False,
                domain="gradevance",
                input_schema={"type": "object", "properties": {}},
                output_description="Open ReviewItem rows with run ids and reasons.",
            ),
            ToolDef(
                id="gradevance.get_qa_summary",
                description="QA console summary — gold status, gates, fairness notes.",
                required_capability="gradevance:view",
                is_mutation=False,
                domain="gradevance",
                input_schema={"type": "object", "properties": {}},
                output_description="QA summary payload for the EduOS GradeVance instance.",
            ),
            ToolDef(
                id="gradevance.list_proposals",
                description="List learning-loop proposals (anchors, rubric notes, segmentation policy).",
                required_capability="gradevance:manage",
                is_mutation=False,
                domain="gradevance",
                input_schema={"type": "object", "properties": {}},
                output_description="Draft/proposed Proposal rows awaiting accept/bump/repin.",
            ),
            ToolDef(
                id="gradevance.suggest_splits",
                description=(
                    "Suggest draft split points (discourse cues) for an essay. "
                    "Advisory only — professor must apply in Teach Resegment painter."
                ),
                required_capability="gradevance:view",
                is_mutation=False,
                domain="gradevance",
                input_schema={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Full essay text to analyze.",
                        },
                        "segments": {
                            "type": "array",
                            "description": "Optional current segments with start_word/end_word.",
                        },
                    },
                    "required": ["text"],
                },
                output_description="suggestions[] with after_word, cue, preview — draft only.",
            ),
        ]


register_domain("gradevance", GradeVanceDomainAI)
