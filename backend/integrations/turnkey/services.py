"""
integrations/turnkey/services.py — TurnKey Bridge business logic.

Thin views delegate here (base-rules: validate → service → serialize).
Responsibilities:

* ``handle_prediction_callback`` — create a PredictionRecord, trace the input
  DataRow via input_hash when possible.
* ``handle_drift_callback``     — create a DriftAlert, mark the linked dataset
  version health as drift-degraded, trigger a DQ anomaly job (dq/jobs.py —
  called, never forked) and record a DataContractViolation when the drift
  metric exceeds the contract's min_health_score equivalent threshold.
* ``register_link`` / ``promote_link`` — outbound TurnKey operations that
  update the TurnKeyModelLink lifecycle (pending → registered → promoted).
* ``submit_feedback`` — close the feedback loop (set actual on a prediction).
"""
import logging

from django.db import transaction
from django.utils import timezone

from catalog.models import DataContract, DataContractViolation, DatasetVersion
from dataschema.models import DataRow
from dq import jobs as dq_jobs

from .client import CarbonTurnKeyClient, TurnKeyClientError
from .models import (
    DriftAlert, PredictionRecord, TurnKeyModelLink, input_hash_of,
)

logger = logging.getLogger(__name__)


# ── helpers ────────────────────────────────────────────────────────────────

def _canonical_values(values: dict) -> dict:
    """Normalize a values dict the same way DataRow.save() does (lowercase keys)."""
    return {str(k).lower(): v for k, v in (values or {}).items()}


def trace_data_row(version: DatasetVersion, input_hash: str, input_data=None) -> DataRow | None:
    """Trace a prediction input back to its source DataRow, if possible.

    Strategy: canonicalize the incoming input (if provided) and verify it
    matches ``input_hash``; then find the first non-archived DataRow in the
    linked version's table whose stored values match. Returns None when the
    input cannot be traced (not an error — the input was simply not from
    Carbon's store).
    """
    if not input_hash:
        return None
    rows = DataRow.objects.filter(
        data_table=version.data_table, is_archived=False,
    )
    if input_data is not None:
        # The sender's hash must match our canonical hash of the payload,
        # otherwise the payload was tampered with or the hash is stale.
        if input_hash_of(input_data) != input_hash:
            return None
        target = _canonical_values(input_data)
        for row in rows:
            if _canonical_values(row.values) == target:
                return row
        return None
    # No payload to compare — fall back to matching rows whose canonical
    # values hash to the given input_hash (bounded scan).
    for row in rows:
        if input_hash_of(_canonical_values(row.values)) == input_hash:
            return row
    return None


def _mark_drift_on_version(version: DatasetVersion, alert_id: str):
    """Record drift_alert=True in the version's health_detail."""
    health_detail = dict(version.health_detail or {})
    health_detail['drift_alert'] = True
    health_detail['drift_alert_id'] = alert_id
    version.health_detail = health_detail
    version.save(update_fields=['health_detail'])


def _trigger_dq_anomaly_job(version: DatasetVersion, alert: DriftAlert):
    """Create + run a DQ anomaly job on the linked version's DataTable.

    Uses dq/jobs.py (the canonical runner) — never fork/duplicate DQ logic.
    """
    job = dq_jobs.create_job(
        'anomaly',
        table=version.data_table,
        payload={
            'source': 'turnkey_drift',
            'turnkey_alert_id': alert.turnkey_alert_id,
            'metric': alert.metric,
            'value': alert.value,
            'threshold': alert.threshold,
            'dataset_version': str(version.id),
        },
    )
    dq_jobs.execute(job)
    return job


def _record_contract_violation(version: DatasetVersion, alert: DriftAlert):
    """Create a DataContractViolation (quality) when drift exceeds the SLA.

    The contract's ``min_health_score`` is the quality threshold: when the
    drift metric value exceeds it, the version is considered in violation.
    """
    try:
        contract = version.dataset.contract
    except DataContract.DoesNotExist:
        return None
    if contract.min_health_score is None:
        return None
    if alert.value <= contract.min_health_score:
        return None
    return DataContractViolation.objects.create(
        contract=contract,
        dataset_version=version,
        violation_type='quality',
        detail={
            'metric': alert.metric,
            'value': alert.value,
            'threshold': alert.threshold,
            'severity': alert.severity,
            'min_health_score': contract.min_health_score,
            'turnkey_alert_id': alert.turnkey_alert_id,
        },
    )


# ── inbound callbacks ──────────────────────────────────────────────────────

@transaction.atomic
def handle_prediction_callback(payload: dict) -> PredictionRecord:
    """Persist a prediction received from TurnKey.

    Required payload keys: model_link (UUID), prediction (dict), input_hash,
    and optionally input_data (dict) used to trace the source DataRow.
    """
    link_id = payload.get('model_link')
    if not link_id:
        raise ValueError('model_link is required')
    try:
        link = TurnKeyModelLink.objects.select_related(
            'dataset_version', 'dataset_version__data_table',
        ).get(pk=link_id)
    except TurnKeyModelLink.DoesNotExist as exc:
        raise ValueError(f'Unknown model_link: {link_id}') from exc

    input_hash = payload.get('input_hash') or ''
    input_data = payload.get('input_data')
    row = None
    if input_hash:
        row = trace_data_row(
            link.dataset_version, input_hash, input_data=input_data,
        )

    return PredictionRecord.objects.create(
        model_link=link,
        input_data_row=row,
        input_hash=input_hash,
        prediction=payload.get('prediction') or {},
    )


@transaction.atomic
def handle_drift_callback(payload: dict) -> DriftAlert:
    """Persist a drift alert and trigger DQ re-evaluation.

    Required payload keys: model_link (UUID), turnkey_alert_id (unique),
    metric, value, threshold, severity.

    Idempotent per turnkey_alert_id: re-delivered alerts are returned without
    re-triggering DQ jobs or duplicate violations.
    """
    link_id = payload.get('model_link')
    alert_id = payload.get('turnkey_alert_id')
    if not link_id:
        raise ValueError('model_link is required')
    if not alert_id:
        raise ValueError('turnkey_alert_id is required')
    try:
        link = TurnKeyModelLink.objects.select_related(
            'dataset_version', 'dataset_version__dataset',
            'dataset_version__dataset__contract',
        ).get(pk=link_id)
    except TurnKeyModelLink.DoesNotExist as exc:
        raise ValueError(f'Unknown model_link: {link_id}') from exc

    alert, created = DriftAlert.objects.get_or_create(
        turnkey_alert_id=alert_id,
        defaults={
            'model_link': link,
            'metric': payload.get('metric', ''),
            'value': float(payload.get('value', 0)),
            'threshold': float(payload.get('threshold', 0)),
            'severity': payload.get('severity', 'medium'),
        },
    )
    if not created:
        # Already processed — idempotent delivery.
        return alert

    version = link.dataset_version
    _mark_drift_on_version(version, alert_id)
    _trigger_dq_anomaly_job(version, alert)
    _record_contract_violation(version, alert)

    alert.dq_job_triggered = True
    alert.save(update_fields=['dq_job_triggered'])
    return alert


# ── outbound link management ───────────────────────────────────────────────

def _client_for(link: TurnKeyModelLink) -> CarbonTurnKeyClient:
    from .models import TurnKeyConfig
    try:
        config = TurnKeyConfig.objects.get(pk=link.turnkey_config_id)
    except TurnKeyConfig.DoesNotExist as exc:
        raise TurnKeyClientError('TurnKey config missing for link') from exc
    return CarbonTurnKeyClient(config.base_url, config.get_api_key())


def register_link(link: TurnKeyModelLink, model_name: str, model_type: str = 'custom') -> TurnKeyModelLink:
    """Register the model in TurnKey (idempotent by name) and record it on the link."""
    with _client_for(link) as client:
        model = client.register_or_get_model(model_name, model_type=model_type)
    link.turnkey_model_id = model['id']
    link.turnkey_model_name = model.get('name') or model_name
    link.status = 'registered'
    link.error_detail = ''
    link.save(update_fields=[
        'turnkey_model_id', 'turnkey_model_name', 'status', 'error_detail',
    ])
    return link


def promote_link(link: TurnKeyModelLink, artifact_path: str = '', metrics: dict | None = None,
                 feature_names: list | None = None) -> TurnKeyModelLink:
    """Push a version (when artifact_path given) and promote to production.

    When no artifact_path is supplied and a version already exists in TurnKey,
    promote the existing turnkey_version_id.
    """
    with _client_for(link) as client:
        if artifact_path and not link.turnkey_version_id:
            version_id = client.push_version(
                link.turnkey_model_id,
                artifact_path=artifact_path,
                metrics=metrics or {},
                feature_names=feature_names or [],
            )
            link.turnkey_version_id = version_id
            link.save(update_fields=['turnkey_version_id'])
        if not link.turnkey_version_id:
            raise TurnKeyClientError(
                'Cannot promote: no TurnKey version exists for this link. '
                'Push a version first (artifact_path).'
            )
        client.promote_to_production(link.turnkey_model_id, link.turnkey_version_id)
    link.status = 'promoted'
    link.save(update_fields=['status'])
    return link


def submit_feedback(prediction: PredictionRecord, actual, user) -> PredictionRecord:
    """Close the feedback loop: record the actual outcome on a prediction."""
    prediction.actual = actual
    prediction.feedback_submitted_at = timezone.now()
    prediction.feedback_by = user
    prediction.save(update_fields=['actual', 'feedback_submitted_at', 'feedback_by'])
    return prediction
