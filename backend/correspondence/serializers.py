"""DRF serializers for the Correspondence engine API (Phase OF-7).

Engine-managed fields are read-only; the API is read + action only (subject
creation belongs to OF-8, so there is no generic create/update surface here).
"""

from rest_framework import serializers

from .models import (
    Correspondence,
    CorrespondenceEvent,
    Notification,
    WorkflowPolicy,
    WorkflowPolicyStep,
)


def _user_display_name(user):
    """Prefer linked employee full_name, then Django full name, then username.

    When a person name exists and differs from the login id, return
    ``Name (username)`` so inbox/timeline show both (e.g. who ``emp_1067`` is).
    """
    if user is None:
        return None
    person = None
    try:
        emp = user.employee_profile
    except Exception:
        # OneToOne reverse raises RelatedObjectDoesNotExist when unlinked.
        emp = None
    if emp is not None:
        person = (getattr(emp, 'full_name', None) or '').strip() or None
    if not person:
        person = (user.get_full_name() or '').strip() or None
    username = user.username or ''
    if person and username and person != username:
        return f'{person} ({username})'
    return person or username or None


class CorrespondenceEventSerializer(serializers.ModelSerializer):
    """Append-only timeline entry (``events``)."""

    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = CorrespondenceEvent
        fields = [
            'id', 'seq', 'actor', 'actor_name', 'event_type',
            'from_status', 'to_status', 'payload', 'created_at',
        ]
        read_only_fields = fields

    def get_actor_name(self, obj):
        if not obj.actor_id:
            return None
        return _user_display_name(obj.actor)


class CorrespondenceSerializer(serializers.ModelSerializer):
    """Lean representation for list/inbox. ``subject`` is exposed via plain
    ``subject_type``/``subject_id`` fields (NOT resolved — the domain app does
    that). ``requester``/``corr_type`` remain read-only PKs, complemented by
    human-readable ``requester_name`` / ``corr_type_code`` / ``corr_type_label``
    for display surfaces (e.g. the approver inbox)."""

    requester_name = serializers.SerializerMethodField()
    corr_type_code = serializers.SerializerMethodField()
    corr_type_label = serializers.SerializerMethodField()
    org_unit_name = serializers.SerializerMethodField()
    current_step_role = serializers.SerializerMethodField()

    class Meta:
        model = Correspondence
        fields = [
            'id', 'reference_no', 'corr_type', 'corr_type_code', 'corr_type_label',
            'subject_type', 'subject_id', 'org_unit', 'org_unit_name',
            'requester', 'requester_name', 'current_step_role',
            'title', 'payload', 'status', 'current_step', 'current_approver_ids',
            'approver_chain', 'policy_version', 'policy_id', 'policy_snapshot',
            'signature_ref', 'resolved_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'reference_no', 'policy_id', 'policy_version', 'policy_snapshot',
            'approver_chain', 'current_step', 'current_approver_ids', 'status',
            'resolved_at', 'created_at', 'updated_at',
            'requester', 'org_unit', 'corr_type',
        ]

    def get_requester_name(self, obj):
        if not obj.requester_id:
            return None
        return _user_display_name(obj.requester)

    def get_corr_type_code(self, obj):
        return obj.corr_type.code if obj.corr_type_id else None

    def get_corr_type_label(self, obj):
        return obj.corr_type.label if obj.corr_type_id else None

    def get_org_unit_name(self, obj):
        return obj.org_unit.name if obj.org_unit_id else None

    def get_current_step_role(self, obj):
        chain = obj.approver_chain or []
        step = obj.current_step if isinstance(obj.current_step, int) else -1
        if 0 <= step < len(chain):
            return chain[step].get('role')
        return None


class CorrespondenceDetailSerializer(CorrespondenceSerializer):
    """Full representation for detail/action responses (adds the timeline)."""

    events = CorrespondenceEventSerializer(many=True, read_only=True)

    class Meta(CorrespondenceSerializer.Meta):
        fields = CorrespondenceSerializer.Meta.fields + ['events']


class WorkflowPolicyStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowPolicyStep
        fields = [
            'id', 'order', 'role', 'intent', 'specific_user',
            'skip_if_self', 'auto_approve', 'can_skip', 'condition', 'is_active',
        ]


class WorkflowPolicySerializer(serializers.ModelSerializer):
    steps = WorkflowPolicyStepSerializer(many=True, read_only=True)

    class Meta:
        model = WorkflowPolicy
        fields = [
            'id', 'name', 'corr_type', 'org_unit', 'version', 'is_active',
            'numbering_format', 'effective_from', 'effective_to',
            'created_at', 'updated_at', 'steps',
        ]


class NotificationSerializer(serializers.ModelSerializer):
    """In-app notification (read/read-all only — created by ``fsm.notify``).

    Exposes the related correspondence's ``reference_no`` so managers/requesters
    can jump straight to the request behind an "action needed" / "status
    changed" notification."""

    correspondence_id = serializers.IntegerField(read_only=True)
    reference_no = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'correspondence_id', 'reference_no',
            'type', 'title', 'body', 'is_read', 'created_at',
        ]
        read_only_fields = fields

    def get_reference_no(self, obj):
        if obj.correspondence_id:
            return obj.correspondence.reference_no
        return None
