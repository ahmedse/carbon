"""GradeVance typed SoR (RULE_27) — multi-domain assessment + HITL learning.

Pack intelligence lives in ``domain_packs/eduos/`` YAML; these models store
runtime artefacts, published profile pins, and append-only ExpertEdit events.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class Course(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=255)
    discipline = models.CharField(max_length=80, blank=True, default="")
    org_unit = models.ForeignKey(
        "mdm.OrgUnit",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="gradevance_courses",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class Assignment(models.Model):
    MODE_FORMATIVE = "formative"
    MODE_SUMMATIVE = "summative"
    MODE_CALIBRATION = "calibration"
    MODE_CHOICES = [
        (MODE_FORMATIVE, "Formative"),
        (MODE_SUMMATIVE, "Summative"),
        (MODE_CALIBRATION, "Calibration"),
    ]
    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PUBLISHED, "Published"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        Course, null=True, blank=True, on_delete=models.SET_NULL, related_name="assignments"
    )
    title = models.CharField(max_length=255)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default=MODE_FORMATIVE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    # Pin to a domain-pack AssignmentProfile (immutable when published).
    profile_pack_id = models.CharField(max_length=120)
    profile_version = models.PositiveIntegerField(default=1)
    brief = models.JSONField(default=dict, blank=True)
    pipeline_config_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text="Frozen at publish — runtime MUST honor (RULE_32).",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class AssignmentProfileRecord(models.Model):
    """Catalog row for a YAML AssignmentProfile (synced from domain_packs)."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("validated", "Validated"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pack_id = models.CharField(max_length=120)
    version = models.PositiveIntegerField()
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="validated")
    discipline = models.CharField(max_length=80)
    genre = models.CharField(max_length=80)
    level = models.CharField(max_length=80, blank=True, default="")
    mode = models.CharField(max_length=20, default="formative")
    lct_device_ref = models.JSONField(default=dict, blank=True)
    rubric_pack_ref = models.JSONField(default=dict, blank=True)
    pipeline_config = models.JSONField(default=dict, blank=True)
    hitl_config = models.JSONField(default=dict, blank=True)
    brief = models.JSONField(default=dict, blank=True)
    source_path = models.CharField(max_length=512, blank=True, default="")
    content_hash = models.CharField(max_length=64, blank=True, default="")
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("pack_id", "version")
        ordering = ["discipline", "pack_id", "-version"]

    def __str__(self) -> str:
        return f"{self.pack_id}@v{self.version}"


class Submission(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_ANALYZED = "analyzed"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_ANALYZED, "Analyzed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="submissions")
    student_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="gradevance_submissions",
    )
    # Prefer opaque key over raw PII in measurement tables.
    external_student_key = models.CharField(max_length=120, blank=True, default="", db_index=True)
    text = models.TextField()
    word_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUBMITTED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Submission {self.id} ({self.word_count}w)"


class AnalysisRun(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_NEEDS_REVIEW = "needs_review"
    STATUS_COMPLETE = "complete"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_NEEDS_REVIEW, "Needs review"),
        (STATUS_COMPLETE, "Complete"),
        (STATUS_FAILED, "Failed"),
    ]
    GATE_AUTO = "auto"
    GATE_REVIEW = "review"
    GATE_WITHHOLD = "withhold"
    GATE_CHOICES = [
        (GATE_AUTO, "Auto (formative advisory)"),
        (GATE_REVIEW, "Needs human review"),
        (GATE_WITHHOLD, "Withhold"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="runs")
    profile_pack_id = models.CharField(max_length=120)
    profile_version = models.PositiveIntegerField(default=1)
    pipeline_snapshot = models.JSONField(default=dict, blank=True)
    run_manifest = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    gate_decision = models.CharField(max_length=20, choices=GATE_CHOICES, default=GATE_REVIEW)
    mean_confidence = models.FloatField(null=True, blank=True)
    coaching = models.JSONField(default=dict, blank=True)
    advisory_bands = models.JSONField(default=dict, blank=True)
    released = models.BooleanField(
        default=False,
        help_text="Summative marks require explicit release (HITL).",
    )
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Run {self.id} [{self.status}]"


class Segment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(AnalysisRun, on_delete=models.CASCADE, related_name="segments")
    ordinal = models.PositiveIntegerField()
    start_word = models.PositiveIntegerField()
    end_word = models.PositiveIntegerField()
    text = models.TextField()
    stage_guess = models.CharField(max_length=32, blank=True, default="")

    class Meta:
        ordering = ["run_id", "ordinal"]
        unique_together = ("run", "ordinal")

    def __str__(self) -> str:
        return f"S{self.ordinal} w{self.start_word}-{self.end_word}"


class LCTCode(models.Model):
    SOURCE_ENGINE = "engine"
    SOURCE_EXPERT = "expert"
    SOURCE_CHOICES = [(SOURCE_ENGINE, "Engine"), (SOURCE_EXPERT, "Expert")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    segment = models.ForeignKey(Segment, on_delete=models.CASCADE, related_name="codes")
    dimension = models.CharField(max_length=40)  # semantic_gravity | semantic_density
    value = models.CharField(max_length=16)  # SG++, SG+, … / SD+, SD-
    numeric = models.PositiveSmallIntegerField(null=True, blank=True)
    confidence = models.FloatField(default=0.5)
    evidence = models.JSONField(default=dict, blank=True)
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default=SOURCE_ENGINE)

    class Meta:
        ordering = ["segment_id", "dimension"]

    def __str__(self) -> str:
        return f"{self.dimension}={self.value}"


class WaveProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.OneToOneField(AnalysisRun, on_delete=models.CASCADE, related_name="wave")
    points = models.JSONField(default=list, blank=True)
    metrics = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return f"Wave for {self.run_id}"


class RubricEvaluation(models.Model):
    SOURCE_ENGINE = "engine"
    SOURCE_EXPERT = "expert"
    SOURCE_CHOICES = [(SOURCE_ENGINE, "Engine"), (SOURCE_EXPERT, "Expert")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(AnalysisRun, on_delete=models.CASCADE, related_name="rubric_scores")
    criterion_id = models.CharField(max_length=80)
    band = models.CharField(max_length=32, blank=True, default="")
    score_0_100 = models.FloatField(null=True, blank=True)
    rationale = models.TextField(blank=True, default="")
    evidence_bindings = models.JSONField(default=dict, blank=True)
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default=SOURCE_ENGINE)

    class Meta:
        ordering = ["run_id", "criterion_id"]
        unique_together = ("run", "criterion_id", "source")

    def __str__(self) -> str:
        return f"{self.criterion_id}={self.band or self.score_0_100}"


class ReviewItem(models.Model):
    STATUS_OPEN = "open"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_RESOLVED = "resolved"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_IN_PROGRESS, "In progress"),
        (STATUS_RESOLVED, "Resolved"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(AnalysisRun, on_delete=models.CASCADE, related_name="review_items")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    priority = models.PositiveSmallIntegerField(default=50)
    reason = models.CharField(max_length=255, blank=True, default="")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-priority", "created_at"]

    def __str__(self) -> str:
        return f"Review {self.id} [{self.status}]"


class ExpertEdit(models.Model):
    """Append-only learning event (RULE_32). Never update rows — insert only."""

    KIND_SEGMENT = "segment_boundary"
    KIND_LCT = "lct_code"
    KIND_RUBRIC = "rubric_score"
    KIND_COACHING = "coaching"
    KIND_OTHER = "other"
    KIND_CHOICES = [
        (KIND_SEGMENT, "Segment boundary"),
        (KIND_LCT, "LCT code"),
        (KIND_RUBRIC, "Rubric score"),
        (KIND_COACHING, "Coaching"),
        (KIND_OTHER, "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(AnalysisRun, on_delete=models.CASCADE, related_name="expert_edits")
    review_item = models.ForeignKey(
        ReviewItem, null=True, blank=True, on_delete=models.SET_NULL, related_name="edits"
    )
    editor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    edit_kind = models.CharField(max_length=32, choices=KIND_CHOICES)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    rationale = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Edit {self.edit_kind} @ {self.created_at}"


class Proposal(models.Model):
    """Intelligence promotion candidate (P2 closes mining → publish)."""

    STATUS_DRAFT = "draft"
    STATUS_PROPOSED = "proposed"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PROPOSED, "Proposed"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_REJECTED, "Rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=64)  # anchor | boundary_pair | rubric_note | action_template
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    payload = models.JSONField(default=dict, blank=True)
    source_edit_ids = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Proposal {self.kind} [{self.status}]"
