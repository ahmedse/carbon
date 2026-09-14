"""Django model for durable, classed knowledge items (P4-01).

A :class:`KnowledgeItem` is the durable record of a single *piece of curated
knowledge* — an approved policy, a process definition, a business fact, a
procedural heuristic, an episodic observation, or a user preference.  Every
item carries the metadata the engine needs to resolve a knowledge corpus
deterministically:

  - ``knowledge_class`` — the closed vocabulary of knowledge kinds;
  - ``source`` / ``owner_id`` / ``scope`` — provenance and partitioning;
  - ``version`` + ``supersedes_id`` — a loose-linked revision chain (a plain id
    string, not a self-FK, so the layer stays relocatable);
  - ``effective_start`` / ``effective_end`` — the validity window;
  - ``review_status`` / ``sensitivity`` — governance + handling classification;
  - ``is_mandatory`` — marks a *constraint that always holds*: such an item is
    never dropped by the engine's conflict rules (see
    :mod:`ai.engine.knowledge.classes`).

This module is host-side: it imports Django only.  The engine never imports it
(RULE_20 / ADR-0007); it consumes the engine-side
:class:`~ai.engine.knowledge.classes.KnowledgeItemProjection` instead.
"""

from __future__ import annotations

from django.db import models

from .base import AppScopeMixin, generate_uuid

# ── Closed ``knowledge_class`` vocabulary ──────────────────────────────────
CLASS_POLICY = "policy"
CLASS_PROCESS_DEFINITION = "process_definition"
CLASS_BUSINESS_FACT = "business_fact"
CLASS_PROCEDURAL_HEURISTIC = "procedural_heuristic"
CLASS_EPISODIC_OBSERVATION = "episodic_observation"
CLASS_USER_PREFERENCE = "user_preference"

KNOWLEDGE_CLASSES = (
    CLASS_POLICY,
    CLASS_PROCESS_DEFINITION,
    CLASS_BUSINESS_FACT,
    CLASS_PROCEDURAL_HEURISTIC,
    CLASS_EPISODIC_OBSERVATION,
    CLASS_USER_PREFERENCE,
)

KNOWLEDGE_CLASS_CHOICES = (
    (CLASS_POLICY, "Policy"),
    (CLASS_PROCESS_DEFINITION, "Process definition"),
    (CLASS_BUSINESS_FACT, "Business fact"),
    (CLASS_PROCEDURAL_HEURISTIC, "Procedural heuristic"),
    (CLASS_EPISODIC_OBSERVATION, "Episodic observation"),
    (CLASS_USER_PREFERENCE, "User preference"),
)

# ── Closed ``review_status`` vocabulary ────────────────────────────────────
REVIEW_DRAFT = "draft"
REVIEW_REVIEW = "review"
REVIEW_APPROVED = "approved"
REVIEW_DEPRECATED = "deprecated"
REVIEW_SUPERSEDED = "superseded"

REVIEW_STATUSES = (
    REVIEW_DRAFT,
    REVIEW_REVIEW,
    REVIEW_APPROVED,
    REVIEW_DEPRECATED,
    REVIEW_SUPERSEDED,
)

REVIEW_STATUS_CHOICES = (
    (REVIEW_DRAFT, "Draft"),
    (REVIEW_REVIEW, "Review"),
    (REVIEW_APPROVED, "Approved"),
    (REVIEW_DEPRECATED, "Deprecated"),
    (REVIEW_SUPERSEDED, "Superseded"),
)

# ── Closed ``sensitivity`` vocabulary ──────────────────────────────────────
SENSITIVITY_PUBLIC = "public"
SENSITIVITY_INTERNAL = "internal"
SENSITIVITY_CONFIDENTIAL = "confidential"
SENSITIVITY_RESTRICTED = "restricted"

SENSITIVITIES = (
    SENSITIVITY_PUBLIC,
    SENSITIVITY_INTERNAL,
    SENSITIVITY_CONFIDENTIAL,
    SENSITIVITY_RESTRICTED,
)

SENSITIVITY_CHOICES = (
    (SENSITIVITY_PUBLIC, "Public"),
    (SENSITIVITY_INTERNAL, "Internal"),
    (SENSITIVITY_CONFIDENTIAL, "Confidential"),
    (SENSITIVITY_RESTRICTED, "Restricted"),
)


class KnowledgeItem(AppScopeMixin):
    """A durable, classed, curated piece of knowledge.

    Inherits :class:`AppScopeMixin` for CBAC partitioning.  ``id`` is a UUID
    string pk via :func:`~ai.models.base.generate_uuid`.  ``owner_id`` and
    ``supersedes_id`` are plain string principals (not FKs) matching the
    loose-coupling style of :class:`~ai.models.human_task.HumanTask`.
    """

    id = models.CharField(max_length=36, primary_key=True, default=generate_uuid)

    # ── Identity + provenance ────────────────────────────────────────────
    knowledge_class = models.CharField(
        max_length=32, db_index=True, choices=KNOWLEDGE_CLASS_CHOICES,
    )
    source = models.CharField(max_length=255)
    owner_id = models.CharField(max_length=255, blank=True, default="")
    scope = models.JSONField(default=dict)  # org-unit / module scope metadata
    version = models.CharField(max_length=64, default="1")

    # ── Validity window ──────────────────────────────────────────────────
    effective_start = models.DateTimeField(null=True, blank=True)
    effective_end = models.DateTimeField(null=True, blank=True)
    ingested_at = models.DateTimeField(auto_now_add=True)

    # ── Governance ───────────────────────────────────────────────────────
    review_status = models.CharField(
        max_length=16, db_index=True, default=REVIEW_DRAFT,
        choices=REVIEW_STATUS_CHOICES,
    )
    sensitivity = models.CharField(
        max_length=16, default=SENSITIVITY_INTERNAL,
        choices=SENSITIVITY_CHOICES,
    )

    # ── Revision chain + payload ─────────────────────────────────────────
    supersedes_id = models.CharField(max_length=36, blank=True, default="")
    content = models.TextField()
    is_mandatory = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"
        indexes = [
            models.Index(
                fields=["knowledge_class", "review_status"],
                name="ai_ki_class_status_idx",
            ),
            models.Index(
                fields=["knowledge_class", "effective_end"],
                name="ai_ki_class_effend_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.knowledge_class}:{self.id}"
