from rest_framework import serializers

from gradevance.models import (
    AnalysisRun,
    Appeal,
    Assignment,
    Course,
    Enrollment,
    ExpertEdit,
    LCTCode,
    ReviewItem,
    RubricEvaluation,
    Segment,
    Submission,
    WaveProfile,
)


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = (
            "id",
            "code",
            "name",
            "discipline",
            "entry_code",
            "org_unit",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class EnrollmentSerializer(serializers.ModelSerializer):
    """Roster row — read ``user`` as username; write via ``user_id`` or ``username``."""

    user = serializers.SerializerMethodField()
    user_id = serializers.IntegerField(write_only=True, required=False)
    username = serializers.CharField(write_only=True, required=False, allow_blank=False)

    class Meta:
        model = Enrollment
        fields = (
            "id",
            "course",
            "user",
            "user_id",
            "username",
            "role",
            "source",
            "active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "source", "created_at", "updated_at", "user", "course")

    def get_user(self, obj):
        return getattr(obj.user, "username", None)


class AssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assignment
        fields = (
            "id",
            "course",
            "title",
            "mode",
            "status",
            "profile_pack_id",
            "profile_version",
            "brief",
            "pipeline_config_snapshot",
            "due_at",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_by", "created_at", "updated_at")


class SubmissionSerializer(serializers.ModelSerializer):
    student_username = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = (
            "id",
            "assignment",
            "student_user",
            "student_username",
            "external_student_key",
            "text",
            "word_count",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "word_count",
            "created_at",
            "updated_at",
            "student_user",
            "student_username",
        )

    def get_student_username(self, obj):
        return getattr(obj.student_user, "username", None)

    def validate_status(self, value):
        allowed = {Submission.STATUS_DRAFT, Submission.STATUS_SUBMITTED}
        if value not in allowed:
            raise serializers.ValidationError("status must be draft or submitted")
        return value


class AppealSerializer(serializers.ModelSerializer):
    assignment_id = serializers.UUIDField(source="run.submission.assignment_id", read_only=True)
    assignment_title = serializers.CharField(
        source="run.submission.assignment.title", read_only=True
    )
    student_username = serializers.SerializerMethodField()

    class Meta:
        model = Appeal
        fields = (
            "id",
            "run",
            "student_user",
            "student_username",
            "reason",
            "status",
            "resolution",
            "resolved_by",
            "assignment_id",
            "assignment_title",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "student_user",
            "status",
            "resolution",
            "resolved_by",
            "created_at",
            "updated_at",
        )

    def get_student_username(self, obj):
        return getattr(obj.student_user, "username", None)

class LCTCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LCTCode
        fields = ("id", "dimension", "value", "numeric", "confidence", "evidence", "source")


class SegmentSerializer(serializers.ModelSerializer):
    codes = LCTCodeSerializer(many=True, read_only=True)

    class Meta:
        model = Segment
        fields = ("id", "ordinal", "start_word", "end_word", "text", "stage_guess", "codes")


class WaveProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = WaveProfile
        fields = ("id", "points", "metrics")


class RubricEvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RubricEvaluation
        fields = (
            "id",
            "criterion_id",
            "band",
            "score_0_100",
            "rationale",
            "evidence_bindings",
            "source",
        )


class AnalysisRunSerializer(serializers.ModelSerializer):
    segments = SegmentSerializer(many=True, read_only=True)
    wave = WaveProfileSerializer(read_only=True)
    rubric_scores = RubricEvaluationSerializer(many=True, read_only=True)
    expert_edits = serializers.SerializerMethodField()

    class Meta:
        model = AnalysisRun
        fields = (
            "id",
            "submission",
            "profile_pack_id",
            "profile_version",
            "pipeline_snapshot",
            "run_manifest",
            "status",
            "gate_decision",
            "mean_confidence",
            "coaching",
            "advisory_bands",
            "released",
            "error_message",
            "created_at",
            "completed_at",
            "segments",
            "wave",
            "rubric_scores",
            "expert_edits",
        )

    def get_expert_edits(self, obj):
        qs = obj.expert_edits.all().order_by("-created_at")[:50]
        return ExpertEditSerializer(qs, many=True).data


class AnalysisRunListSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalysisRun
        fields = (
            "id",
            "submission",
            "profile_pack_id",
            "status",
            "gate_decision",
            "mean_confidence",
            "advisory_bands",
            "released",
            "created_at",
            "completed_at",
        )


class ReviewItemSerializer(serializers.ModelSerializer):
    run_status = serializers.CharField(source="run.status", read_only=True)
    profile_pack_id = serializers.CharField(source="run.profile_pack_id", read_only=True)

    class Meta:
        model = ReviewItem
        fields = (
            "id",
            "run",
            "status",
            "priority",
            "reason",
            "assigned_to",
            "created_at",
            "resolved_at",
            "run_status",
            "profile_pack_id",
        )


class ExpertEditSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpertEdit
        fields = (
            "id",
            "run",
            "review_item",
            "editor",
            "edit_kind",
            "before",
            "after",
            "rationale",
            "created_at",
        )
        read_only_fields = ("id", "editor", "created_at")
