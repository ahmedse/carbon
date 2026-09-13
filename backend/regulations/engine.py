# regulations/engine.py
# AuditEngine — orchestrates AuditRun execution.
# Looks up evaluators from the registry, enumerates scope items, persists findings.
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class AuditEngine:
    """Runs an AuditProgram and persists AuditFindings.

    Usage:
        run = AuditRun.objects.create(program=prog, run_date=date.today(), run_by=user)
        engine = AuditEngine()
        engine.execute(run)
    """

    def execute(self, audit_run) -> "AuditRun":
        from .models import AuditFinding
        from .registry import get_evaluator

        audit_run.status = 'running'
        audit_run.save(update_fields=['status'])

        obligations = audit_run.program.obligations.filter(is_active=True).select_related('scheme')
        totals = {'total': 0, 'compliant': 0, 'non_compliant': 0, 'partial': 0, 'na': 0, 'error': 0}

        for obligation in obligations:
            evaluator_cls = get_evaluator(obligation.formula_type)
            if evaluator_cls is None:
                logger.warning("No evaluator for formula_type=%r (obligation %s)", obligation.formula_type, obligation.code)
                AuditFinding.objects.update_or_create(
                    run=audit_run,
                    obligation=obligation,
                    scope_type='custom',
                    scope_id=0,
                    defaults={
                        'scope_label': 'n/a',
                        'result': 'error',
                        'computed_value': {'error': f'No evaluator registered for formula_type={obligation.formula_type!r}'},
                        'severity': obligation.severity,
                    },
                )
                totals['error'] += 1
                totals['total'] += 1
                continue

            evaluator = evaluator_cls(obligation)

            try:
                scope_items = evaluator.get_scope_items(audit_run)
            except Exception as exc:
                logger.exception("get_scope_items failed for %s", obligation.code)
                AuditFinding.objects.update_or_create(
                    run=audit_run,
                    obligation=obligation,
                    scope_type='custom',
                    scope_id=0,
                    defaults={
                        'scope_label': 'n/a',
                        'result': 'error',
                        'computed_value': {'error': f'get_scope_items raised: {exc}'},
                        'severity': obligation.severity,
                    },
                )
                totals['error'] += 1
                totals['total'] += 1
                continue

            for scope_type, scope_id, scope_label in scope_items:
                try:
                    result = evaluator.evaluate(scope_type, scope_id, audit_run)
                except Exception as exc:
                    logger.exception("evaluate failed for %s / %s:%s", obligation.code, scope_type, scope_id)
                    result = {
                        'status': 'error',
                        'actual': None,
                        'expected': None,
                        'delta': None,
                        'error': str(exc),
                    }

                status = result.get('status', 'error')
                AuditFinding.objects.update_or_create(
                    run=audit_run,
                    obligation=obligation,
                    scope_type=scope_type,
                    scope_id=scope_id,
                    defaults={
                        'scope_label': scope_label,
                        'result': status,
                        'computed_value': result,
                        'severity': result.get('severity_override', obligation.severity),
                    },
                )
                totals[status] = totals.get(status, 0) + 1
                totals['total'] += 1

        audit_run.status = 'complete'
        audit_run.completed_at = timezone.now()
        audit_run.summary = totals
        audit_run.save(update_fields=['status', 'completed_at', 'summary'])
        logger.info("AuditRun %d complete: %s", audit_run.pk, totals)
        return audit_run
