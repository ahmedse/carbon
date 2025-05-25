from django.db import models
from django.contrib.auth import get_user_model
from accounts.models import Context

User = get_user_model()

TIME_UNIT_CHOICES = [
    ('day', 'Day'),
    ('week', 'Week'),
    ('month', 'Month'),
    ('quarter', 'Quarter'),
    ('year', 'Year'),
    # Add more if needed
]

class ReadingItemDefinition(models.Model):
    DATA_TYPE_CHOICES = [
        ('number', 'Number'),
        ('string', 'String'),
        ('date', 'Date'),
        ('file', 'File'),
        ('select', 'Select'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    data_type = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES)
    validation_rules = models.JSONField(default=dict, blank=True)
    required = models.BooleanField(default=True)
    units = models.CharField(max_length=50, blank=True)
    time_unit = models.CharField(max_length=16, choices=TIME_UNIT_CHOICES, default='month')
    options = models.JSONField(default=list, blank=True)  # For select-type
    category = models.CharField(max_length=50, blank=True)
    tags = models.JSONField(default=list, blank=True)
    evidence_rules = models.JSONField(default=dict, blank=True)
    editable = models.BooleanField(default=True)
    context = models.ForeignKey(Context, on_delete=models.CASCADE, related_name='reading_items')
    module = models.CharField(max_length=100)  # Module selection for filtering
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)    

    def __str__(self):
        return self.name

class ReadingTemplate(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, default='active')
    fields = models.ManyToManyField(ReadingItemDefinition, through='ReadingTemplateField')
    context = models.ForeignKey(Context, on_delete=models.CASCADE, related_name='reading_templates')
    module = models.CharField(max_length=100)  # Module selection for filtering
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} v{self.version}"

class ReadingTemplateField(models.Model):
    template = models.ForeignKey(ReadingTemplate, on_delete=models.CASCADE)
    field = models.ForeignKey(ReadingItemDefinition, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('template', 'field')
        ordering = ['order']

class ReadingEntry(models.Model):
    template = models.ForeignKey(ReadingTemplate, on_delete=models.CASCADE)
    template_version = models.PositiveIntegerField()
    context = models.ForeignKey(Context, on_delete=models.CASCADE, related_name='reading_entries')
    item = models.ForeignKey(ReadingItemDefinition, on_delete=models.CASCADE, related_name='entries')
    data = models.JSONField(default=dict)  # {field_id: value}
    # If reading always covers a single point in time (e.g., daily reading), you can set both to the same date.
    period_start = models.DateField()
    period_end = models.DateField()
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='draft')
    audit_log = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"Entry {self.id} for Template {self.template_id} Item {self.item_id}"

class EvidenceFile(models.Model):
    reading_entry = models.ForeignKey(ReadingEntry, on_delete=models.CASCADE, related_name='evidence_files')
    reading_item = models.ForeignKey(ReadingItemDefinition, on_delete=models.CASCADE)
    context = models.ForeignKey(Context, on_delete=models.CASCADE, related_name='evidence_files')
    file = models.FileField(upload_to='evidence/')
    file_type = models.CharField(max_length=50)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    covers_period_start = models.DateField(null=True, blank=True)
    covers_period_end = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Evidence for Entry {self.reading_entry_id} - {self.file.name}"
    
class ContextAssignment(models.Model):
    context = models.ForeignKey(Context, on_delete=models.CASCADE, related_name='assignments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=50, choices=[('auditor', 'Auditor'), ('data_owner', 'Data Owner')])
    submitted_at = models.DateTimeField(auto_now_add=True)