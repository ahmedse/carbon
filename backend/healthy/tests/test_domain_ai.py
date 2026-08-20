"""Domain-AI registration tests for the Healthy Foods Factory app."""
from ai.domain_protocol import (
    DomainAIOperations, DomainContext, get_domain, has_domain,
)
from healthy.domain_ai import HealthyDomainAI


def test_healthy_domain_is_registered():
    assert has_domain('healthy') is True
    assert get_domain('healthy') is HealthyDomainAI


def test_healthy_domain_subclasses_protocol():
    assert issubclass(HealthyDomainAI, DomainAIOperations)


def test_healthy_domain_identity():
    assert HealthyDomainAI.app_identifier == 'healthy'
    assert HealthyDomainAI.app_display_name == 'Healthy Foods Factory'


def test_get_domain_context():
    ctx = HealthyDomainAI().get_domain_context()
    assert isinstance(ctx, DomainContext)
    assert ctx.app_identifier == 'healthy'
    assert 'DSD' in ctx.domain_knowledge
    assert 'rep_code' in ctx.domain_knowledge
    assert ctx.domain_config['timezone'] == 'Africa/Cairo'


def test_manifest_dict():
    manifest = HealthyDomainAI().to_manifest_dict()
    assert manifest['app_identifier'] == 'healthy'
    assert manifest['display_name'] == 'Healthy Foods Factory'
    assert 'chat' in manifest['supported_task_types']
    assert isinstance(manifest['starter_prompts'], dict)


def test_validate_task_payload_report_draft():
    ok, _msg = HealthyDomainAI().validate_task_payload('report_draft', {'report': 'x'})
    assert ok is True
    ok, msg = HealthyDomainAI().validate_task_payload('report_draft', {})
    assert ok is False
    assert 'report' in msg
