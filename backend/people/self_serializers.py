"""Self-service serializers for the employee surface (Phase OF-8).

These read-only serializers expose the ``/people/me/`` profile, leave balance
and leave-record views. The leave serializers resolve the linked
``correspondence.Correspondence`` (subject creation lives in the self-service
views) without importing ``people`` back into the engine — layering is one-way.
"""

from rest_framework import serializers

from correspondence.models import Correspondence
from correspondence.serializers import CorrespondenceEventSerializer

from .models import Employee, LeaveRecord

SUBJECT_TYPE = 'people.LeaveRecord'


class EmployeeSummarySerializer(serializers.ModelSerializer):
    """Lean, self-safe profile summary (no salary/identity fields)."""

    # ``Employee`` has no ``job_title`` column in this codebase — the field is
    # derived from the linked ``Position.title`` (None-safe).
    job_title = serializers.SerializerMethodField()
    org_unit = serializers.SerializerMethodField()
    manager = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            'id', 'employee_no', 'full_name', 'job_title', 'is_active',
            'org_unit', 'manager',
        ]
        read_only_fields = fields

    def get_job_title(self, obj):
        return obj.position.title if obj.position_id else None

    def get_org_unit(self, obj):
        if not obj.org_unit_id:
            return None
        return {'id': obj.org_unit_id, 'name': obj.org_unit.name}

    def get_manager(self, obj):
        if not obj.manager_id:
            return None
        return {'id': obj.manager_id, 'name': obj.manager.full_name}


class LeaveBalanceSerializer(serializers.Serializer):
    """One leave-type balance row."""

    leave_type = serializers.CharField()
    entitled = serializers.DecimalField(max_digits=8, decimal_places=2)
    used = serializers.DecimalField(max_digits=8, decimal_places=2)
    pending = serializers.DecimalField(max_digits=8, decimal_places=2)
    remaining = serializers.DecimalField(max_digits=8, decimal_places=2)


class LeaveRecordSerializer(serializers.ModelSerializer):
    """Leave record enriched with its governed correspondence (read-only)."""

    reference_no = serializers.SerializerMethodField()
    correspondence_id = serializers.SerializerMethodField()
    leave_type = serializers.SerializerMethodField()
    leave_type_label = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRecord
        fields = [
            'id', 'leave_type', 'leave_type_label', 'start_date', 'end_date',
            'days', 'status',
            'created_at', 'updated_at', 'reference_no', 'correspondence_id',
        ]
        read_only_fields = fields

    def get_leave_type(self, obj):
        return obj.leave_type.code if obj.leave_type_id else None

    def get_leave_type_label(self, obj):
        return obj.leave_type.label if obj.leave_type_id else None

    def _correspondence(self, obj):
        """Resolve the linked Correspondence (cached per serializer instance)."""
        cache = getattr(self, '_corr_cache', None)
        if cache is None:
            cache = self._corr_cache = {}
        if obj.pk not in cache:
            cache[obj.pk] = Correspondence.objects.filter(
                subject_type=SUBJECT_TYPE, subject_id=obj.pk,
            ).first()
        return cache[obj.pk]

    def get_reference_no(self, obj):
        corr = self._correspondence(obj)
        return corr.reference_no if corr else None

    def get_correspondence_id(self, obj):
        corr = self._correspondence(obj)
        return corr.id if corr else None


class LeaveRecordDetailSerializer(LeaveRecordSerializer):
    """Leave record plus the governed correspondence timeline."""

    events = serializers.SerializerMethodField()

    class Meta(LeaveRecordSerializer.Meta):
        fields = LeaveRecordSerializer.Meta.fields + ['events']

    def get_events(self, obj):
        corr = self._correspondence(obj)
        if not corr:
            return []
        return CorrespondenceEventSerializer(
            corr.events.all().order_by('seq'), many=True,
        ).data
