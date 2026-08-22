"""Tests for MaterializationCheckpoint and incremental run_pipeline watermark."""
import pytest

from healthy.services import HealthyPipelineService


@pytest.mark.django_db
def test_first_run_creates_checkpoint(create_user):
    from healthy.models import MaterializationCheckpoint
    user = create_user('chk_user_1')
    HealthyPipelineService().run_pipeline('churn', user=user, auto_approve=True)
    assert MaterializationCheckpoint.objects.filter(pipeline_key='churn').exists()


@pytest.mark.django_db
def test_checkpoint_advances_after_run(create_user):
    from healthy.models import MaterializationCheckpoint
    user = create_user('chk_user_2')
    HealthyPipelineService().run_pipeline('returns', user=user, auto_approve=True)
    cp = MaterializationCheckpoint.objects.get(pipeline_key='returns')
    assert cp.last_ran_at is not None


@pytest.mark.django_db
def test_result_includes_checkpoint(create_user):
    from healthy.models import MaterializationCheckpoint
    user = create_user('chk_user_3')
    result = HealthyPipelineService().run_pipeline('ar-aging', user=user, auto_approve=True)
    assert 'checkpoint' in result
    assert isinstance(result['checkpoint'], MaterializationCheckpoint)


@pytest.mark.django_db
def test_full_flag_ignores_existing_checkpoint(create_user):
    """full=True must not raise and must return a checkpoint."""
    from healthy.models import MaterializationCheckpoint
    user = create_user('chk_user_4')
    HealthyPipelineService().run_pipeline('churn', user=user, auto_approve=True)
    cp = MaterializationCheckpoint.objects.get(pipeline_key='churn')
    cp.last_row_id = 99999
    cp.save()
    result = HealthyPipelineService().run_pipeline('churn', user=user,
                                                   auto_approve=True, full=True)
    assert result['checkpoint'].pipeline_key == 'churn'


@pytest.mark.django_db
def test_second_run_uses_delta(create_user):
    """Checkpoint after second run must be >= checkpoint after first run."""
    from healthy.models import MaterializationCheckpoint
    user = create_user('chk_user_5')
    HealthyPipelineService().run_pipeline('sales-lines', user=user, auto_approve=True)
    cp_after_first = MaterializationCheckpoint.objects.get(pipeline_key='sales-lines').last_row_id
    HealthyPipelineService().run_pipeline('sales-lines', user=user, auto_approve=True)
    cp_after_second = MaterializationCheckpoint.objects.get(pipeline_key='sales-lines').last_row_id
    assert cp_after_second >= cp_after_first


@pytest.mark.django_db
def test_unknown_pipeline_raises():
    with pytest.raises(ValueError, match='Unknown healthy pipeline'):
        HealthyPipelineService().run_pipeline('does-not-exist')
