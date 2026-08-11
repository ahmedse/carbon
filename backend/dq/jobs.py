"""
dq/jobs.py — Phase 3 (TASK-DQ-CORE-P3-JOBS): DQ job runner.

Lifecycle model (design decisions in TASK-DQ-CORE-P3-JOBS.md):
  * Deterministic jobs (rule_run, profile, freshness, schema) execute INLINE
    during POST /dq/jobs/ — no Celery/Redis/daemon/scheduler (hard rule).
    Status: queued -> running -> done | failed.
  * Pulse jobs (nl_check, suggest, anomaly) are submitted to Pulse via
    CarbonIntelligence (ai/intelligence.py); pulse_task_id is stored, status
    `refresh(job)` polls GET /tasks/{id} from the job detail endpoint
    (retrieve()).
    Status: queued -> running -> done | failed | canceled.
  * Pulse-unavailable polling: N consecutive pulse_unavailable responses mark
    the job failed (best-effort; Pulse is an external AI system, we never
    block a request on it). Phase 4 (fail-visible): a failed nl_check job
    also writes an honest DQResult(status='skipped_unavailable') so scores
    show the gap instead of silently auto-passing.

All exceptions are caught here — the runner NEVER raises out. State changes
persist so any later read sees a consistent terminal status.
"""
import logging

from .models import DQJob, JOB_TYPES
from . import services

logger = logging.getLogger(__name__)

# Max consecutive pulse_unavailable polls before a Pulse job is failed.
PULSE_UNAVAILABLE_LIMIT = 20


def create_job(job_type, *, rule=None, table=None, payload=None, user=None) -> DQJob:
    """Create (but do not run) a DQJob. Use execute() to start it."""
    if job_type not in dict(JOB_TYPES):
        raise ValueError(f'Unknown job_type: {job_type}')
    return DQJob.objects.create(
        job_type=job_type,
        rule=rule,
        data_table=table,
        payload=payload or {},
        created_by=user,
    )


def execute(job: DQJob) -> DQJob:
    """Run a job to a terminal state (done/failed), or submit to Pulse.

    Deterministic jobs run inline and persist their result summary.
    Pulse jobs submit to Pulse and enter running (polled via refresh()).
    Never raises — failures are recorded on the job itself.
    """
    if job.status == 'canceled':
        return job  # nothing to do

    try:
        if job.job_type == 'rule_run':
            return _run_rule_job(job)
        if job.job_type == 'profile':
            return _run_profile_job(job)
        if job.job_type == 'freshness':
            return _run_freshness_job(job)
        if job.job_type == 'schema':
            return _run_schema_job(job)
        if job.job_type in ('nl_check', 'suggest', 'anomaly'):
            return _submit_pulse_job(job)
        job.status = 'failed'
        job.error = f'Unknown job_type: {job.job_type}'
        job.save(update_fields=['status', 'error', 'updated_at'])
        return job
    except Exception as exc:  # runner never raises
        logger.exception('DQJob %s (%s) failed', job.pk, job.job_type)
        job.status = 'failed'
        job.error = str(exc)[:2000]
        job.save(update_fields=['status', 'error', 'updated_at'])
        return job


def refresh(job: DQJob) -> DQJob:
    """Poll a Pulse job (nl_check/suggest/anomaly) and advance its status.

    Deterministic jobs are already terminal — refresh() is a no-op for them.
    Call from DQJobViewSet.retrieve() before serializing.
    """
    if job.job_type not in ('nl_check', 'suggest', 'anomaly'):
        return job
    if job.status in ('done', 'failed', 'canceled'):
        return job

    from ai.intelligence import CarbonIntelligence

    if not job.pulse_task_id:
        job.status = 'failed'
        job.error = 'Pulse job has no pulse_task_id'
        job.save(update_fields=['status', 'error', 'updated_at'])
        if job.job_type == 'nl_check':
            _write_skipped_result(job, job.error)
        return job

    response = CarbonIntelligence().get_task_status(job.pulse_task_id)

    if response.get('status') == 'pulse_unavailable':
        # Count consecutive unavailable polls; after the limit, give up.
        streak = job.payload.get('unavailable_streak', 0) + 1
        payload = dict(job.payload)
        payload['unavailable_streak'] = streak
        job.payload = payload
        if streak >= PULSE_UNAVAILABLE_LIMIT:
            job.status = 'failed'
            job.error = (
                f'Pulse unreachable for {streak} consecutive polls '
                f'(task {job.pulse_task_id})'
            )
            job.progress = 0
            job.save(update_fields=[
                'status', 'error', 'payload', 'progress', 'updated_at',
            ])
            if job.job_type == 'nl_check':
                _write_skipped_result(job, job.error)
        else:
            job.save(update_fields=['payload', 'updated_at'])
        return job

    task_status = response.get('status')  # pending | working | completed | failed
    if task_status in ('pending', 'working', 'running'):
        job.status = 'running'
        job.progress = response.get('progress', job.progress)
        job.save(update_fields=['status', 'progress', 'updated_at'])
        return job

    if task_status == 'completed':
        job.status = 'done'
        job.progress = 100
        job.result = response.get('result') or {}
        if job.job_type == 'nl_check':
            _write_nl_check_results(job)
        elif job.job_type == 'suggest':
            _persist_suggestions(job)
        elif job.job_type == 'anomaly':
            _write_anomaly_results(job)
        job.save(update_fields=['status', 'progress', 'result', 'updated_at'])
        return job

    if task_status == 'failed':
        job.status = 'failed'
        job.error = str(response.get('error') or 'Pulse task failed')
        job.save(update_fields=['status', 'error', 'updated_at'])
        if job.job_type == 'nl_check':
            _write_skipped_result(job, job.error)
        return job

    # Unknown status from Pulse — leave running; next poll decides.
    logger.warning('Unexpected Pulse task status %r for job %s', task_status, job.pk)
    return job


def cancel(job: DQJob) -> DQJob:
    """Best-effort cancel. queued/running -> canceled (Pulse is not notified)."""
    if job.status in ('queued', 'running'):
        job.status = 'canceled'
        job.save(update_fields=['status', 'updated_at'])
    return job


# ── deterministic handlers ─────────────────────────────────────────────────

def _run_rule_job(job: DQJob) -> DQJob:
    job.status = 'running'
    job.progress = 10
    job.save(update_fields=['status', 'progress', 'updated_at'])

    if job.rule_id is None:
        raise ValueError('rule_run job requires a rule')

    results = services.run_single_rule(job.rule_id, user=job.created_by)

    passed = sum(1 for r in results if r.get('passed'))
    failed = sum(1 for r in results if not r.get('passed'))
    job.status = 'done'
    job.progress = 100
    job.result = {
        'rule_id': job.rule_id,
        'rule_name': job.rule.name if job.rule_id else None,
        'fields_checked': len(results),
        'passed': passed,
        'failed': failed,
        'results': results,
    }
    job.save(update_fields=['status', 'progress', 'result', 'updated_at'])
    return job


def _run_profile_job(job: DQJob) -> DQJob:
    job.status = 'running'
    job.progress = 10
    job.save(update_fields=['status', 'progress', 'updated_at'])

    if job.data_table_id is None:
        raise ValueError('profile job requires a data_table')

    summary = services.profile_table(job.data_table_id)
    job.status = 'done'
    job.progress = 100
    job.result = summary
    job.save(update_fields=['status', 'progress', 'result', 'updated_at'])
    return job


def _run_freshness_job(job: DQJob) -> DQJob:
    job.status = 'running'
    job.progress = 10
    job.save(update_fields=['status', 'progress', 'updated_at'])

    summary = services.check_freshness(
        table_id=job.data_table_id, notify=False,
    )
    job.status = 'done'
    job.progress = 100
    job.result = summary
    job.save(update_fields=['status', 'progress', 'result', 'updated_at'])
    return job


def _run_schema_job(job: DQJob) -> DQJob:
    job.status = 'running'
    job.progress = 10
    job.save(update_fields=['status', 'progress', 'updated_at'])

    summary = services.snapshot_schema(
        table_id=job.data_table_id, notify=False,
    )
    job.status = 'done'
    job.progress = 100
    job.result = summary
    job.save(update_fields=['status', 'progress', 'result', 'updated_at'])
    return job


# ── Pulse handlers ─────────────────────────────────────────────────────────

def _prompt_for_rule(rule) -> str:
    """Extract the NL prompt from a DQRule (definition JSON, then legacy params)."""
    try:
        definition = rule.definition
        if isinstance(definition, dict):
            params = definition.get('params', {})
            if isinstance(params, dict) and params.get('prompt'):
                return str(params['prompt'])
    except Exception:
        pass
    try:
        if isinstance(rule.params, dict) and rule.params.get('prompt'):
            return str(rule.params['prompt'])
    except Exception:
        pass
    return ''


def _submit_pulse_job(job: DQJob) -> DQJob:
    """Submit an nl_check/suggest job to Pulse; store pulse_task_id, go running.

    Pulse may answer synchronously (§1.2, status completed with result) or
    asynchronously (§1.3, status pending + poll_url). Either way we store the
    task id; refresh() advances non-terminal jobs from GET /dq/jobs/{id}/.
    """
    from ai.intelligence import CarbonIntelligence

    intelligence = CarbonIntelligence()

    if job.job_type == 'nl_check':
        if job.rule_id is None:
            raise ValueError('nl_check job requires a rule')
        prompt = job.payload.get('prompt') or _prompt_for_rule(job.rule)
        if not prompt:
            raise ValueError('nl_check job requires a prompt (payload.prompt or rule definition)')
        response = intelligence.submit_dq_validate(
            rules=[{
                'id': job.rule_id,
                'prompt': prompt,
                'fields': job.payload.get('fields', []),
                'severity': job.rule.severity if job.rule_id else 'error',
            }],
            rows=job.payload.get('rows', []),
            context={
                'table_name': job.data_table.name if job.data_table_id else '',
                'row_count_hint': len(job.payload.get('rows', [])),
                'job_id': job.pk,
            },
        )
    elif job.job_type == 'suggest':
        table_payload, err = services.build_suggest_payload(job.data_table_id)
        if err:
            job.status = 'failed'
            job.error = err.get('message', 'Could not build suggest payload')
            job.save(update_fields=['status', 'error', 'updated_at'])
            return job
        response = intelligence.submit_dq_suggest(table_payload)
    elif job.job_type == 'anomaly':
        return _submit_anomaly_job(job)
    else:
        raise ValueError(f'Unknown Pulse job_type: {job.job_type}')

    return _record_pulse_submission(job, response)


def _submit_anomaly_job(job: DQJob) -> DQJob:
    """Submit an anomaly.detect job to Pulse (Phase 4).

    Carbon-side guard first: with fewer than MIN_ANOMALY_PROFILES profile
    snapshots the job completes done with result.state='insufficient_history'
    and Pulse is never called (nothing fabricated — fail-visible).
    """
    from ai.intelligence import CarbonIntelligence

    if job.data_table_id is None:
        raise ValueError('anomaly job requires a data_table')

    payload, err = services.build_anomaly_payload(job.data_table_id)
    if err:
        if err.get('code') == 'insufficient_history':
            job.status = 'done'
            job.progress = 100
            job.result = {
                'state': 'insufficient_history',
                'message': err.get('message', ''),
                'anomalies': [],
            }
            job.save(update_fields=['status', 'progress', 'result', 'updated_at'])
            return job
        job.status = 'failed'
        job.error = err.get('message', 'Could not build anomaly payload')
        job.save(update_fields=['status', 'error', 'updated_at'])
        return job

    response = CarbonIntelligence().submit_anomaly_detect(payload)
    return _record_pulse_submission(job, response)


def _record_pulse_submission(job: DQJob, response: dict) -> DQJob:
    """Persist the outcome of a Pulse submission (sync-complete or accepted)."""
    if response.get('status') == 'pulse_unavailable':
        job.status = 'failed'
        job.error = str(response.get('error', {}).get('message', 'Pulse unavailable'))
        job.save(update_fields=['status', 'error', 'updated_at'])
        # Fail-visible (design decision #1): a failed nl_check job leaves an
        # honest skipped result so scores show the gap.
        if job.job_type == 'nl_check':
            _write_skipped_result(job, job.error)
        return job

    task_id = response.get('task_id') or ''
    job.pulse_task_id = str(task_id)

    task_status = response.get('status')  # completed | pending | working | failed
    if task_status == 'completed':
        job.status = 'done'
        job.progress = 100
        job.result = response.get('result') or {}
        if job.job_type == 'nl_check':
            _write_nl_check_results(job)
        elif job.job_type == 'suggest':
            _persist_suggestions(job)
        elif job.job_type == 'anomaly':
            _write_anomaly_results(job)
    elif task_status == 'failed':
        job.status = 'failed'
        job.error = str(response.get('error') or 'Pulse task failed')
        job.progress = 0
    else:  # pending | working | unknown — poll later via refresh()
        job.status = 'running'
        job.progress = 5

    job.save(update_fields=['status', 'progress', 'pulse_task_id', 'result', 'error', 'updated_at'])
    return job


def _write_nl_check_results(job: DQJob) -> None:
    """Persist Pulse dq.validate results as normal DQResult rows.

    Design decision #4 (TASK-DQ-CORE-P3-JOBS): every completed job still
    writes normal DQResult rows so history, trends, and catalog rollups keep
    working unchanged — nl_check just moved from inline-in-run_dq to job-only.

    Phase 4 (fail-visible, design decision #1): an entry whose status is
    'error' is recorded as DQResult(status='skipped_unavailable', passed=None)
    — never silently converted to a pass.
    """
    from .models import DQResult

    pulse_results = job.result.get('results', []) if isinstance(job.result, dict) else []
    if not pulse_results:
        return

    total = len(job.payload.get('rows', [])) or 0
    for entry in pulse_results:
        if not isinstance(entry, dict):
            continue
        status_flag = entry.get('status')

        field = None
        if job.rule_id:
            first_assn = job.rule.field_assignments.select_related('data_field').first()
            if first_assn:
                field = first_assn.data_field

        if status_flag == 'error':
            # Fail-visible: Pulse produced an error — honest skipped result.
            DQResult.objects.create(
                rule=job.rule,
                data_field=field,
                passed=None,
                status='skipped_unavailable',
                checked_count=0,
                failed_count=0,
                sample_failures=[{'explanation': entry.get('explanation', 'Pulse returned error status')}],
                score=0,
            )
            continue

        failing_rows = entry.get('failing_rows') or []
        failed = len(failing_rows)
        checked = total or (len(failing_rows) + (0 if status_flag == 'fail' else 1))
        passed = status_flag != 'fail'
        score = 100 if checked == 0 else round((checked - failed) / checked * 100)
        sample = [{'row': r, 'explanation': entry.get('explanation', '')} for r in failing_rows[:20]]

        DQResult.objects.create(
            rule=job.rule,
            data_field=field,
            status='passed' if passed else 'failed',
            passed=passed,
            checked_count=checked,
            failed_count=failed,
            sample_failures=sample,
            score=score,
        )


def _write_skipped_result(job: DQJob, reason: str) -> None:
    """Record an honest 'skipped — Pulse unavailable' DQResult for a failed
    nl_check job so metrics/scores show the gap (fail-visible, design
    decision #1 — never a fabricated pass or fail)."""
    from .models import DQResult

    if job.rule_id is None:
        return
    field = None
    first_assn = job.rule.field_assignments.select_related('data_field').first()
    if first_assn:
        field = first_assn.data_field
    DQResult.objects.create(
        rule=job.rule,
        data_field=field,
        passed=None,
        status='skipped_unavailable',
        checked_count=0,
        failed_count=0,
        sample_failures=[{'explanation': reason}],
        score=0,
    )


def _suggestion_to_definition(s: dict, table_name: str) -> dict:
    """Build a v1 rule definition from a Pulse suggestion that lacks one.

    dq.suggest is an NL rule suggester, so suggestions default to
    business-level nl_check rules bound to the table. If Pulse ever returns a
    full `definition` it is used verbatim (validated the same way).
    """
    prompt = s.get('prompt', '') or ''
    name = s.get('name') or (prompt[:80] if prompt else 'Suggested rule')
    severity = (s.get('suggested_severity') or 'warn').lower()
    if severity == 'warning':
        severity = 'warn'
    if severity not in ('info', 'warn', 'error'):
        severity = 'warn'
    return {
        'schema_version': 1,
        'name': name,
        'level': 'business',
        'dimension': 'accuracy',
        'type': 'nl_check',
        'severity': severity,
        'active': True,
        'bindings': [{'table': table_name}],
        'params': {'prompt': prompt},
        'description': s.get('rationale', ''),
    }


def _persist_suggestions(job: DQJob) -> None:
    """Turn completed dq.suggest results into persisted DQSuggestion rows.

    Each suggestion is validated with rule_schema.validate_definition; valid
    ones land as DQSuggestion(status='pending'), invalid ones are quarantined
    into job.result.invalid (never fabricated into suggestion rows — nothing
    auto-creates rules).
    """
    from .models import DQSuggestion
    from .rule_schema import validate_definition

    suggestions = job.result.get('suggestions', []) if isinstance(job.result, dict) else []
    if not suggestions or job.data_table_id is None:
        return

    table_name = job.data_table.name
    stored = 0
    invalid_entries = []
    for s in suggestions:
        if not isinstance(s, dict):
            invalid_entries.append({
                'suggestion': s,
                'errors': [{'field': '_root', 'code': 'invalid_type',
                            'message': 'suggestion must be a JSON object'}],
            })
            continue
        definition = s.get('definition')
        if not isinstance(definition, dict) or not definition.get('type'):
            definition = _suggestion_to_definition(s, table_name)
        errors = validate_definition(definition)
        if errors:
            invalid_entries.append({'suggestion': s, 'errors': errors})
            continue
        DQSuggestion.objects.create(
            data_table=job.data_table,
            payload=definition,
            rationale=s.get('rationale', ''),
            confidence=s.get('confidence'),
            status='pending',
            job=job,
            created_by=job.created_by,
        )
        stored += 1

    job.result = {
        **(job.result or {}),
        'suggestions_stored': stored,
        'suggestions_invalid': len(invalid_entries),
        'invalid': invalid_entries,
    }
    job.save(update_fields=['result', 'updated_at'])


def _write_anomaly_results(job: DQJob) -> None:
    """Persist Pulse anomaly.detect results as DQAnomaly rows and notify.

    Fail-visible: nothing is fabricated — if Pulse returned no anomalies, no
    rows are written. Each anomaly emits a dq_anomaly notification following
    the dq/signals.py pattern (check_freshness/snapshot_schema style).
    """
    from .models import DQAnomaly

    anomalies = job.result.get('anomalies', []) if isinstance(job.result, dict) else []
    if not anomalies or job.data_table_id is None:
        return

    stored = 0
    for entry in anomalies:
        if not isinstance(entry, dict):
            continue
        expected_range = entry.get('expected_range')
        if not isinstance(expected_range, dict):
            expected_range = {
                'low': entry.get('expected_low'),
                'high': entry.get('expected_high'),
            }
        observed = entry.get('observed')
        if observed is None:
            logger.warning(
                'Pulse anomaly missing observed value for job %s: %r', job.pk, entry,
            )
            continue  # no fabricated values — skip this entry
        severity = (entry.get('severity') or 'warn').lower()
        if severity == 'critical':
            severity = 'error'
        if severity not in ('info', 'warn', 'error'):
            severity = 'warn'
        metric = entry.get('metric') or entry.get('field') or 'unknown'
        DQAnomaly.objects.create(
            data_table=job.data_table,
            metric=metric,
            group_key=entry.get('group_key') or None,
            expected_range=expected_range,
            observed=observed,
            score=entry.get('score') or 0.0,
            explanation=entry.get('explanation', ''),
            severity=severity,
            job=job,
        )
        stored += 1
        try:
            from accounts.models import notify_event
            notify_event(
                event_type='dq_anomaly',
                title=f'DQ anomaly detected: {job.data_table.name} — {metric}',
                body=(
                    f'Observed {metric}={observed} on table "{job.data_table.name}" '
                    f'(expected range {expected_range}). {entry.get("explanation", "")}'
                ),
                severity='error' if severity == 'error' else 'warning',
                link=f'/dq/anomalies/?data_table={job.data_table_id}',
            )
        except Exception:  # notification must never break result persistence
            logger.exception('Failed to send dq_anomaly notification for job %s', job.pk)

    job.result = {
        **(job.result or {}),
        'anomalies_stored': stored,
    }
    job.save(update_fields=['result', 'updated_at'])
