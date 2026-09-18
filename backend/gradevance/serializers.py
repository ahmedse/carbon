from rest_framework import serializers

from gradevance.models import (
    AnalysisRun,
    Assignment,
    Course,
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
        fields = ("id", "code", "name", "discipline", "org_unit", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


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
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_by", "created_at", "updated_at")


class SubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submission
        fields = (
            "id",
            "assignment",
            "student_user",
            "external_student_key",
            "text",
            "word_count",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "word_count", "status", "created_at", "updated_at", "student_user")


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
        )


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
