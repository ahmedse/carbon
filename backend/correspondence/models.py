"""e-Office Correspondence engine models (Phase OF-2).

Governed enumerations (``corr_type``) are ``mdm.ReferenceValue`` FKs — never
CharField choices. ``User`` FKs use the repo's string-FK idiom
(``'accounts.User'``) to avoid top-level import cycles.
"""

from django.db import models


STATUS_CHOICES = [
    ('draft', 'Draft'), ('submitted', 'Submitted'), ('in_review', 'In Review'),
    ('approved', 'Approved'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled'),
    ('sent_back', 'Sent Back'), ('expired', 'Expired'), ('archived', 'Archived'),
]
ACTIONABLE = ('submitted', 'in_review')
TERMINAL = ('approved', 'rejected', 'cancelled', 'expired', 'archived')

# Decision events a manager/approver records — Team History is keyed on these.
ACTOR_HISTORY_EVENTS = (
    'approved', 'rejected', 'sent_back', 'acknowledged', 'reviewed',
)

ROLE_CHOICES = [
    ('manager', 'Manager'), ('hr', 'HR'), ('finance', 'Finance'),
    ('specific_user', 'Specific User'), ('any_admin', 'Any Admin'),
]
INTENT_CHOICES = [('approve', 'Approve'), ('acknowledge', 'Acknowledge'), ('review', 'Review')]


class Correspondence(models.Model):
    """A single governed correspondence instance and its workflow state."""

    reference_no = models.CharField(max_length=40, unique=True, db_index=True)
    corr_type = models.ForeignKey(
        'mdm.ReferenceValue', on_delete=models.PROTECT, related_name='+'
    )
    subject_type = models.CharField(max_length=120, blank=True, default='')
    subject_id = models.PositiveBigIntegerField(null=True, blank=True)
    org_unit = models.ForeignKey('mdm.OrgUnit', on_delete=models.PROTECT)
    requester = models.ForeignKey('accounts.User', on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default='draft', db_index=True
    )
    current_step = models.PositiveSmallIntegerField(default=0)
    current_approver_ids = models.JSONField(default=list, blank=True)
    approver_chain = models.JSONField(default=list, blank=True)
    policy_version = models.CharField(max_length=40, blank=True)
    policy_id = models.PositiveBigIntegerField(null=True, blank=True)
    policy_snapshot = models.JSONField(default=dict, blank=True)
    signature_ref = models.JSONField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'requester']),
            models.Index(fields=['status']),
            models.Index(fields=['corr_type']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return self.reference_no


class WorkflowPolicy(models.Model):
    """Versioned workflow definition for a corr_type/org_unit (null org_unit = global)."""

    name = models.CharField(max_length=120)
    corr_type = models.ForeignKey('mdm.ReferenceValue', on_delete=models.PROTECT)
    org_unit = models.ForeignKey(
        'mdm.OrgUnit', null=True, blank=True, on_delete=models.SET_NULL
    )
    version = models.CharField(max_length=40)
    is_active = models.BooleanField(default=True)
    numbering_format = models.CharField(
        max_length=120, default='{PREFIX}-{YEAR}-{SEQ:04d}'
    )
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('corr_type', 'org_unit', 'version')]
        ordering = ['-version']

    def __str__(self):
        return f'{self.name} v{self.version}'


class WorkflowPolicyStep(models.Model):
    """A single ordered approval step within a workflow policy."""

    policy = models.ForeignKey(
        WorkflowPolicy, on_delete=models.CASCADE, related_name='steps'
    )
    order = models.PositiveSmallIntegerField()
    role = models.CharField(max_length=24, choices=ROLE_CHOICES)
    fallback_role = models.CharField(
        max_length=24, choices=ROLE_CHOICES, blank=True, default='',
        help_text=(
            'Who approves when nobody holds `role` (an employee with no '
            'manager). Left blank, such a request waits for routing rather '
            'than passing unapproved.'
        ),
    )
    intent = models.CharField(max_length=16, choices=INTENT_CHOICES, default='approve')
    specific_user = models.ForeignKey(
        'accounts.User', null=True, blank=True, on_delete=models.SET_NULL
    )
    skip_if_self = models.BooleanField(default=False)
    auto_approve = models.BooleanField(default=False)
    can_skip = models.BooleanField(default=False)
    condition = models.JSONField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']
        unique_together = [('policy', 'order')]

    def __str__(self):
        return f'{self.policy} · step {self.order} ({self.role})'


class CorrespondenceEvent(models.Model):
    """Append-only timeline entry for a correspondence."""

    correspondence = models.ForeignKey(
        Correspondence, on_delete=models.CASCADE, related_name='events'
    )
    seq = models.PositiveSmallIntegerField()
    actor = models.ForeignKey(
        'accounts.User', null=True, blank=True, on_delete=models.SET_NULL
    )
    event_type = models.CharField(max_length=24)
    from_status = models.CharField(max_length=16, null=True, blank=True)
    to_status = models.CharField(max_length=16, null=True, blank=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('correspondence', 'seq')]
        ordering = ['seq']

    def __str__(self):
        return f'{self.correspondence.reference_no} · #{self.seq} {self.event_type}'


class CorrespondenceAttachment(models.Model):
    """File attachment linked to a correspondence."""

    correspondence = models.ForeignKey(
        Correspondence, on_delete=models.CASCADE, related_name='attachments'
    )
    name = models.CharField(max_length=200)
    file = models.FileField(
        upload_to='correspondence/attachments/%Y/%m/', null=True, blank=True
    )
    mime_type = models.CharField(max_length=80, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        'accounts.User', null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class CorrespondenceRegistry(models.Model):
    """Global per-year sequence counter for reference numbering.

    ``reference_no`` is globally unique and the numbering format
    (``{PREFIX}-{YEAR}-{SEQ:04d}``) carries no org/type discriminator, so the
    sequence must be a single global counter per year — NOT per
    ``(corr_type, org_unit, year)`` (which collides across units).
    """

    year = models.PositiveSmallIntegerField(unique=True)
    counter = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f'global · {self.year} · {self.counter}'


class Delegation(models.Model):
    """Delegates approval authority from one user to another for a scope."""

    delegator = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='delegations_made'
    )
    delegate = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='delegations_received'
    )
    corr_type = models.ForeignKey(
        'mdm.ReferenceValue', null=True, blank=True, on_delete=models.SET_NULL
    )
    scope = models.CharField(max_length=16, default='all')
    org_unit = models.ForeignKey(
        'mdm.OrgUnit', null=True, blank=True, on_delete=models.SET_NULL
    )
    from_date = models.DateTimeField(null=True, blank=True)
    to_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.delegator} → {self.delegate} ({self.scope})'


class Notification(models.Model):
    """In-app notification to a user about a correspondence event."""

    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='correspondence_notifications',
    )
    correspondence = models.ForeignKey(
        Correspondence, null=True, blank=True, on_delete=models.CASCADE
    )
    event = models.ForeignKey(
        CorrespondenceEvent, null=True, blank=True, on_delete=models.CASCADE
    )
    type = models.CharField(max_length=24)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_read']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} · {self.title}'
