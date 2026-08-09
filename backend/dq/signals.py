# File: dq/signals.py
# Phase 1.6 — Trigger notifications when DQ rules fail

from django.db.models.signals import post_save
from django.dispatch import receiver

from dq.models import DQResult


@receiver(post_save, sender=DQResult)
def notify_dq_violation(sender, instance, created, **kwargs):
    """When a DQ result is created and the rule failed, fire a notification."""
    if not created:
        return  # Only trigger on new results
    
    if instance.passed:
        return  # No violation — no notification needed
    
    try:
        from accounts.models import notify_event
        
        rule_name = instance.rule.name if instance.rule else 'Unknown Rule'
        table_name = instance.rule.data_table.name if instance.rule and instance.rule.data_table else 'Unknown Table'
        
        severity = 'error' if instance.failed_count > 10 else 'warning'
        
        notify_event(
            event_type='dq_violation',
            title=f'DQ Violation: {rule_name}',
            body=f'Rule "{rule_name}" on table "{table_name}" failed. '
                 f'{instance.failed_count} of {instance.checked_count} rows failed (score: {instance.score}).',
            severity=severity,
            link=f'/dq/results/{instance.id}/',
        )
    except Exception:
        pass  # Never let notification failure break DQ execution
