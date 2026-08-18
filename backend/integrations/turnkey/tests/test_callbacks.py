"""Required gates for the TurnKey inbound callbacks (DESIGN-PLATFORM.md §6.8)."""
import pytest
from django.utils import timezone

from datahub.models import DataContractViolation, DatasetVersion
from dq.models import DQJob
from integrations.turnkey.models import DriftAlert, PredictionRecord, input_hash_of
from integrations.turnkey.tests.conftest import signed_post

CALLBACK_PREDICTIONS = '/carbon-api/integrations/turnkey/callback/predictions/'
CALLBACK_DRIFT = '/carbon-api/integrations/turnkey/callback/drift-alerts/'


@pytest.fixture
def linked_version(make_dataset, make_table, make_version, make_config, make_link, module_a):
    def _build(purpose='inference', **link_kwargs):
        dataset = make_dataset(module_a)
        table = make_table(module_a)
        version = make_version(dataset, table)
        config = make_config()
        link = make_link(version, config, purpose=purpose, **link_kwargs)
        return {'dataset': dataset, 'table': table, 'version': version,
                'config': config, 'link': link}
    return _build


def test_callback_signature_required(api_client, linked_version):
    """Unsigned POST → 401 (HMAC gate)."""
    ctx = linked_version()
    response = api_client.post(
        CALLBACK_PREDICTIONS,
        data={'model_link': str(ctx['link'].id), 'prediction': {'y': 1}},
        format='json',
    )
    assert response.status_code == 401

    response = api_client.post(
        CALLBACK_DRIFT,
        data={'model_link': str(ctx['link'].id), 'turnkey_alert_id': 'a1'},
        format='json',
    )
    assert response.status_code == 401


def test_prediction_callback_creates_record(db, api_client, linked_version, make_table):
    """Valid signed POST → PredictionRecord created, input row traced by hash."""
    ctx = linked_version()
    from dataschema.models import DataRow
    row = DataRow.objects.create(
        data_table=ctx['table'], values={'product': 'A', 'sales': 42},
    )
    input_data = {'Product': 'A', 'Sales': 42}
    payload = {
        'model_link': str(ctx['link'].id),
        'prediction': {'forecast': 43.5, 'confidence': 0.92},
        'input_hash': input_hash_of(input_data),
        'input_data': input_data,
    }
    response = signed_post(api_client, CALLBACK_PREDICTIONS, payload)
    assert response.status_code == 201
    record = PredictionRecord.objects.get(model_link=ctx['link'])
    assert record.input_hash == input_hash_of(input_data)
    assert record.input_data_row_id == row.id
    assert record.prediction == {'forecast': 43.5, 'confidence': 0.92}


def test_prediction_callback_unknown_link(db, api_client):
    """Unknown model_link → 400 (not a 500)."""
    import uuid
    payload = {
        'model_link': str(uuid.uuid4()),
        'prediction': {'forecast': 1},
    }
    response = signed_post(api_client, CALLBACK_PREDICTIONS, payload)
    assert response.status_code == 400


def test_drift_callback_triggers_dq(db, api_client, linked_version, make_dataset):
    """Drift alert → DriftAlert created + DQ job created + contract violation."""
    ctx = linked_version()
    # Give the dataset a contract with a quality SLA (min_health_score).
    from datahub.models import DataContract
    DataContract.objects.create(
        dataset=ctx['dataset'],
        required_fields=['product'],
        min_completeness=0.9,
        min_validity=0.9,
        min_health_score=0.8,
    )

    payload = {
        'model_link': str(ctx['link'].id),
        'turnkey_alert_id': 'alert-001',
        'metric': 'mape',
        'value': 0.95,
        'threshold': 0.10,
        'severity': 'high',
    }
    response = signed_post(api_client, CALLBACK_DRIFT, payload)
    assert response.status_code == 201

    alert = DriftAlert.objects.get(turnkey_alert_id='alert-001')
    assert alert.metric == 'mape'
    assert alert.value == 0.95
    assert alert.dq_job_triggered is True
    assert alert.severity == 'high'

    # 1) health_detail drift_alert marked on the linked version.
    ctx['version'].refresh_from_db()
    assert ctx['version'].health_detail.get('drift_alert') is True
    assert ctx['version'].health_detail.get('drift_alert_id') == 'alert-001'

    # 2) a DQ anomaly job was created on the linked DataTable.
    job = DQJob.objects.filter(
        job_type='anomaly', data_table=ctx['table'],
    ).order_by('-created_at').first()
    assert job is not None
    assert job.payload.get('source') == 'turnkey_drift'
    assert job.payload.get('turnkey_alert_id') == 'alert-001'

    # 3) contract violation recorded (quality) — 0.95 > min_health_score 0.8.
    violation = DataContractViolation.objects.get(
        dataset_version=ctx['version'], violation_type='quality',
    )
    assert violation.detail['metric'] == 'mape'
    assert violation.detail['turnkey_alert_id'] == 'alert-001'

    # Idempotency: re-delivery of the same alert does not re-trigger jobs.
    before = DQJob.objects.filter(job_type='anomaly').count()
    response = signed_post(api_client, CALLBACK_DRIFT, payload)
    assert response.status_code == 201
    assert DQJob.objects.filter(job_type='anomaly').count() == before
    assert DriftAlert.objects.count() == 1


def test_drift_callback_no_contract_is_safe(db, api_client, linked_version):
    """Drift alert without a DataContract → alert still created, no violation."""
    ctx = linked_version()
    payload = {
        'model_link': str(ctx['link'].id),
        'turnkey_alert_id': 'alert-no-contract',
        'metric': 'rmse',
        'value': 3.4,
        'threshold': 1.0,
        'severity': 'medium',
    }
    response = signed_post(api_client, CALLBACK_DRIFT, payload)
    assert response.status_code == 201
    assert DriftAlert.objects.filter(turnkey_alert_id='alert-no-contract').exists()
    assert DataContractViolation.objects.filter(
        dataset_version=ctx['version']).count() == 0
