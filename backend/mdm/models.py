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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.slug = slugify(self.slug or self.name)
        super().save(*args, **kwargs)

    def get_active_values(self):
        return self.values.filter(is_active=True)

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
]


class OrgUnit(models.Model):
    """
    Organisational unit (university, college, department, division, team, facility).
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
