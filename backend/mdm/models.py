from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify

User = get_user_model()


class ReferenceSet(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    domain = models.ForeignKey(
        'catalog.DataDomain',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reference_sets',
    )
    steward = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='stewarded_reference_sets',
    )
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    LIFECYCLE_DRAFT = 'draft'
    LIFECYCLE_ACTIVE = 'active'
    LIFECYCLE_DEPRECATED = 'deprecated'
    LIFECYCLE_ARCHIVED = 'archived'
    LIFECYCLE_STATES = [
        (LIFECYCLE_DRAFT, 'Draft'),
        (LIFECYCLE_ACTIVE, 'Active'),
        (LIFECYCLE_DEPRECATED, 'Deprecated'),
        (LIFECYCLE_ARCHIVED, 'Archived'),
    ]
    lifecycle_state = models.CharField(
        max_length=20,
        choices=LIFECYCLE_STATES,
        default=LIFECYCLE_DRAFT,
        help_text='Lifecycle state of this reference set',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.slug = slugify(self.slug or self.name)
        super().save(*args, **kwargs)

    def get_active_values(self):
        return self.values.filter(is_active=True)

    def get_current_values(self, as_of=None, include_inactive=False):
        """Return values valid on the requested date (today by default)."""
        from django.db.models import Q
        from django.utils import timezone

        target_date = as_of or timezone.now().date()
        qs = self.values.all()
        if not include_inactive:
            qs = qs.filter(is_active=True)
        return qs.filter(
            Q(valid_from__isnull=True) | Q(valid_from__lte=target_date),
            Q(valid_to__isnull=True) | Q(valid_to__gte=target_date),
        )

    VALID_LIFECYCLE_TRANSITIONS = {
        LIFECYCLE_DRAFT: [LIFECYCLE_ACTIVE],
        LIFECYCLE_ACTIVE: [LIFECYCLE_DEPRECATED],
        LIFECYCLE_DEPRECATED: [LIFECYCLE_ACTIVE, LIFECYCLE_ARCHIVED],
        LIFECYCLE_ARCHIVED: [],
    }

    def can_transition_to(self, new_state):
        """Return True if the requested lifecycle transition is permitted."""
        return new_state in self.VALID_LIFECYCLE_TRANSITIONS.get(self.lifecycle_state, [])

    def transition_to(self, new_state, user=None):
        """Advance the lifecycle state with validation and optional audit emission."""
        if new_state == self.lifecycle_state:
            return self
        if not self.can_transition_to(new_state):
            raise ValueError(
                f'Invalid reference set lifecycle transition: {self.lifecycle_state} -> {new_state}'
            )
        old_state = self.lifecycle_state
        self.lifecycle_state = new_state
        if new_state == self.LIFECYCLE_ARCHIVED:
            self.is_active = False
        self.save(update_fields=['lifecycle_state', 'is_active'] if new_state == self.LIFECYCLE_ARCHIVED else ['lifecycle_state'])

        if user is not None:
            from catalog.audit_utils import emit_governance_event
            emit_governance_event(
                entity_type='ReferenceSet',
                entity_id=self.id,
                action='update',
                before={'lifecycle_state': old_state},
                after={'lifecycle_state': self.lifecycle_state},
                user=user,
            )
        return self

    def __str__(self):
        return self.name


class ReferenceValue(models.Model):
    reference_set = models.ForeignKey(ReferenceSet, on_delete=models.CASCADE, related_name='values')
    code = models.CharField(max_length=80)
    label = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'code']
        constraints = [
            models.UniqueConstraint(fields=['reference_set', 'code'], name='uniq_referencevalue_code'),
        ]

    def __str__(self):
        return f"{self.reference_set.name}:{self.code}"


ORG_TYPE_CHOICES = [
    ('university', 'University'),
    ('campus', 'Campus'),
    ('college', 'College'),
    ('department', 'Department'),
    ('division', 'Division'),
    ('team', 'Team'),
    ('facility', 'Facility'),
    ('other', 'Other'),
    ('company', 'Company'),
    ('section', 'Section'),
    ('crew', 'Crew'),
    ('base', 'Base'),
    ('yard', 'Yard'),
    ('store', 'Store'),
    ('cost_center', 'Cost Center'),
]


class OrgUnit(models.Model):
    """
    Organisational unit — academic (university, campus, college, department,
    division, team, facility) and industrial (company, section, crew, base,
    yard, store, cost_center) types.
    Self-referencing tree: any depth, any shape.
    Replaces the old Project concept as the organisational anchor for RBAC,
    governance, lineage, and access-control policies.
    """
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    code = models.CharField(max_length=50, blank=True, help_text="Short code, e.g. ENG-CIVIL")
    org_type = models.CharField(max_length=20, choices=ORG_TYPE_CHOICES, default='other')
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children'
    )
    description = models.TextField(blank=True)
    manager_employee_id = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Soft ref to people.Employee (RULE_3: no cross-app FK from core). Who runs this unit.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = [('parent', 'name')]

    def __str__(self):
        return self.name

    def get_ancestors(self):
        """Return list of ancestors from root to parent."""
        ancestors = []
        current = self.parent
        while current:
            ancestors.insert(0, current)
            current = current.parent
        return ancestors

    def full_path(self):
        return ' / '.join([u.name for u in self.get_ancestors()] + [self.name])

    def get_descendant_ids(self, include_self=True):
        """Return this unit's id plus all descendant ids (breadth-first)."""
        ids = {self.id} if include_self else set()
        frontier = [self.id]
        while frontier:
            children = list(
                OrgUnit.objects.filter(parent_id__in=frontier).values_list('id', flat=True)
            )
            new = [c for c in children if c not in ids]
            ids.update(new)
            frontier = new
        return ids
