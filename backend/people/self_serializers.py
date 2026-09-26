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
from .leave_days import LeaveDaysField

SUBJECT_TYPE = 'people.LeaveRecord'


class EmployeeSummarySerializer(serializers.ModelSerializer):
    """Lean profile for team lists. No pay and no identity documents."""

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


class EmployeeSelfProfileSerializer(EmployeeSummarySerializer):
    """The caller's own /people/me/ row. Adds own basic pay only.

    Direct reports keep ``EmployeeSummarySerializer`` so a manager list
    does not carry other people's pay.
    """

    class Meta(EmployeeSummarySerializer.Meta):
        fields = list(EmployeeSummarySerializer.Meta.fields) + ['basic_salary']
        read_only_fields = fields


class LeaveBalanceSerializer(serializers.Serializer):
    """One leave-type balance row."""

    leave_type = serializers.CharField()
    entitled = LeaveDaysField()
    carried_forward = LeaveDaysField()
    opening_balance = LeaveDaysField()
    used = LeaveDaysField()
    pending = LeaveDaysField()
    remaining = LeaveDaysField()
    remaining_signed = LeaveDaysField()
    overdrawn = serializers.BooleanField()


class LeaveRecordSerializer(serializers.ModelSerializer):
    """Leave record enriched with its governed correspondence (read-only)."""

    reference_no = serializers.SerializerMethodField()
    correspondence_id = serializers.SerializerMethodField()
    correspondence_status = serializers.SerializerMethodField()
    leave_type = serializers.SerializerMethodField()
    leave_type_label = serializers.SerializerMethodField()
    days = LeaveDaysField(read_only=True)

    class Meta:
        model = LeaveRecord
        fields = [
            'id', 'leave_type', 'leave_type_label', 'start_date', 'end_date',
            'days', 'status',
            'created_at', 'updated_at', 'reference_no', 'correspondence_id',
            'correspondence_status',
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

    def get_correspondence_status(self, obj):
        corr = self._correspondence(obj)
        return corr.status if corr else obj.status


class TeamLeaveRecordSerializer(LeaveRecordSerializer):
    """Leave row for a manager's direct report (Who's Out).

    Surface Correspondence status when the LeaveRecord is still ``draft``
    (ESS pending approval) so the grid matches inbox language (submitted).
    """

    employee_id = serializers.IntegerField(source='employee.id', read_only=True)
    employee_no = serializers.CharField(source='employee.employee_no', read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    status = serializers.SerializerMethodField()

    class Meta(LeaveRecordSerializer.Meta):
        fields = LeaveRecordSerializer.Meta.fields + [
            'employee_id', 'employee_no', 'employee_name',
        ]

    def get_status(self, obj):
        corr_status = self.get_correspondence_status(obj)
        if obj.status == 'draft' and corr_status:
            return corr_status
        return obj.status


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
