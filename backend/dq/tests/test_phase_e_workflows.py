"""Phase 24-E — Declarative DQ workflows + rule template catalog.

Tests:
  * workflow spec registry: all 7 job types registered, kinds/requires correct
  * execute()/refresh()/cancel() dispatch through the registry (no if/elif)
  * the design gate: adding a NEW job type = spec row + handler, no dispatcher
    edit — proven by registering a throwaway spec and running it
  * rule template catalog: employee_no (the design-doc emp-no case),
    instantiation with bindings/overrides, confirmation gate, catalog integrity
"""
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model

from core.models import Module
from dataschema.models import DataTable, DataField, DataRow
from mdm.models import OrgUnit
from dq.models import DQRule, RuleFieldAssignment, DQJob
from dq import jobs as jobs_module
from dq import workflows
from dq import templates
from dq.rule_schema import validate_definition

User = get_user_model()


class WorkflowRegistryTests(TestCase):
    """WORKFLOW_SPECS covers every JOB_TYPES code with correct shape."""

    def test_all_seven_job_types_registered(self):
        from dq.models import JOB_TYPES
        codes = {c[0] for c in JOB_TYPES}
        self.assertEqual(
            set(workflows.list_workflows()), codes,
            'workflow registry must cover every model job_type',
        )

    def test_kinds_and_requires_match_design(self):
        expected = {
            'rule_run': ('deterministic', ['rule']),
            'profile': ('deterministic', ['table']),
            'freshness': ('deterministic', ['table']),
            'schema': ('deterministic', ['table']),
            'nl_check': ('pulse', ['rule']),
            'suggest': ('pulse', ['table']),
            'anomaly': ('pulse', ['table']),
        }
        for code, (kind, requires) in expected.items():
            spec = workflows.get_workflow(code)
            self.assertEqual(spec['kind'], kind, code)
            self.assertEqual(spec['requires'], requires, code)

    def test_every_spec_has_label_and_handler_names(self):
        for code, spec in workflows.WORKFLOW_SPECS.items():
            self.assertTrue(spec['label'], code)
            if spec['kind'] == 'deterministic':
                self.assertTrue(spec.get('run'), code)
                self.assertFalse(spec.get('submit'), code)
            else:
                self.assertTrue(spec.get('submit'), code)
                # nl_check is the only fail-visible workflow
                self.assertEqual(
                    bool(spec.get('on_failed')), code == 'nl_check', code,
                )

    def test_needs_prompt_only_for_nl_check(self):
        for code in workflows.list_workflows():
            self.assertEqual(
                workflows.workflow_needs_prompt(code), code == 'nl_check', code,
            )

    def test_get_workflow_unknown_raises_value_error(self):
        with self.assertRaises(ValueError):
            workflows.get_workflow('bogus')
        self.assertFalse(workflows.has_workflow('bogus'))

    def test_validate_job_payload_matches_spec_requires(self):
        # rule-requiring
        ok, err = workflows.validate_job_payload('rule_run', rule=object())
        self.assertTrue(ok)
        ok, err = workflows.validate_job_payload('rule_run')
        self.assertFalse(ok)
        self.assertIn('rule_id', err)
        # table-requiring
        ok, err = workflows.validate_job_payload('profile', table=object())
        self.assertTrue(ok)
        ok, err = workflows.validate_job_payload('profile')
        self.assertFalse(ok)
        self.assertIn('data_table_id', err)
        # nl_check needs a rule but not a table
        ok, err = workflows.validate_job_payload('nl_check', rule=object())
        self.assertTrue(ok)

    def test_resolve_handler_unknown_name_raises(self):
        with self.assertRaises(ValueError):
            workflows.resolve_handler('_does_not_exist', jobs_module)


class DispatchThroughSpecTests(TestCase):
    """execute()/refresh() dispatch through the registry."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='wf_admin', password='pass', is_staff=True, is_superuser=True)
        cls.org_unit = OrgUnit.objects.create(
            name='WF Test Org', code='WFTO', org_type='division')
        cls.module = Module.objects.create(name='WF Module', org_unit=cls.org_unit)
        cls.table = DataTable.objects.create(
            title='WF Table', name='wf_table', module=cls.module)
        cls.field = DataField.objects.create(
            data_table=cls.table, name='email', label='Email', type='string')
        DataRow.objects.bulk_create([
            DataRow(data_table=cls.table, values={'email': f'u{i}@x.com'}) for i in range(3)
        ])
        cls.rule = DQRule.objects.create(
            name='WF Not Null', rule_type='not_null',
            rule_level='field_validation', is_active=True)
        RuleFieldAssignment.objects.create(
            rule=cls.rule, data_field=cls.field, data_table=cls.table)

    def test_rule_run_dispatches_through_spec(self):
        """execute() reaches the spec's run handler and completes done."""
        job = jobs_module.create_job('rule_run', rule=self.rule, user=self.admin)
        jobs_module.execute(job)
        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        self.assertEqual(job.progress, 100)
        self.assertEqual(job.result['rule_id'], self.rule.id)
        self.assertEqual(job.result['fields_checked'], 1)  # one field assignment
        self.assertGreater(job.result['passed'] + job.result['failed'], 0)

    def test_deterministic_refresh_is_noop_via_spec_kind(self):
        job = jobs_module.create_job('rule_run', rule=self.rule, user=self.admin)
        jobs_module.execute(job)
        job.refresh_from_db()
        with patch('ai.intelligence.CarbonIntelligence.get_task_status') as m:
            jobs_module.refresh(job)
            m.assert_not_called()

    def test_unknown_job_type_cannot_be_created(self):
        with self.assertRaises(ValueError):
            jobs_module.create_job('bogus', user=self.admin)

    # ── THE DESIGN GATE ────────────────────────────────────────────────
    def test_new_job_type_needs_only_a_spec_row_and_handler(self):
        """Adding a job type requires NO dispatcher edit: register a throwaway
        spec + handler, then execute() picks it up (gate from the design doc:
        'adding a job type no longer requires touching the dispatcher')."""
        added = {}

        def _run_echo_job(job):
            job.status = 'done'
            job.progress = 100
            job.result = {'echo': 'hello'}
            job.save(update_fields=['status', 'progress', 'result', 'updated_at'])
            return job

        try:
            workflows.WORKFLOW_SPECS['echo_test'] = {
                'kind': 'deterministic',
                'requires': [],
                'run': '_run_echo_job',
                'label': 'Echo Test',
            }
            added['handler'] = _run_echo_job
            setattr(jobs_module, '_run_echo_job', _run_echo_job)

            job = jobs_module.create_job('echo_test', user=self.admin)
            jobs_module.execute(job)
            job.refresh_from_db()
            self.assertEqual(job.status, 'done')
            self.assertEqual(job.result, {'echo': 'hello'})
        finally:
            workflows.WORKFLOW_SPECS.pop('echo_test', None)
            delattr(jobs_module, '_run_echo_job')

    def test_pulse_submit_dispatch_uses_spec_handler(self):
        """A pulse workflow's submit handler is called via the spec."""
        with patch('ai.intelligence.CarbonIntelligence.submit_dq_validate',
                   return_value={'status': 'pending', 'task_id': 't-1'}):
            job = jobs_module.create_job('nl_check', rule=self.rule, user=self.admin,
                                         payload={'prompt': 'Check emails'})
            jobs_module.execute(job)
        job.refresh_from_db()
        self.assertEqual(job.status, 'running')
        self.assertEqual(job.pulse_task_id, 't-1')


class PulseCompletionViaSpecTests(TestCase):
    """refresh()/execute() persist Pulse results via spec on_completed names."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='wf_pulse_admin', password='pass', is_staff=True, is_superuser=True)
        cls.org_unit = OrgUnit.objects.create(
            name='WF Pulse Org', code='WFPO', org_type='division')
        cls.module = Module.objects.create(name='WF Pulse Module', org_unit=cls.org_unit)
        cls.table = DataTable.objects.create(
            title='WF Pulse Table', name='wf_pulse_table', module=cls.module)
        cls.field = DataField.objects.create(
            data_table=cls.table, name='email', label='Email', type='string')
        DataRow.objects.bulk_create([
            DataRow(data_table=cls.table, values={'email': f'u{i}@x.com'}) for i in range(2)
        ])
        cls.nl_rule = DQRule.objects.create(
            name='WF NL', rule_type='nl_check', rule_level='field_validation',
            is_active=True, params={'prompt': 'Email must contain @ and domain'})
        RuleFieldAssignment.objects.create(
            rule=cls.nl_rule, data_field=cls.field, data_table=cls.table)

    def test_refresh_completed_writes_nl_check_results_via_spec(self):
        from dq.models import DQResult

        job = jobs_module.create_job(
            'nl_check', rule=self.nl_rule, user=self.admin,
            payload={'prompt': 'Check', 'rows': [{'email': 'a@x.com'}, {'email': 'bad'}]})
        job.pulse_task_id = 'task-complete'
        job.status = 'running'
        job.save()
        with patch('ai.intelligence.CarbonIntelligence.get_task_status',
                   return_value={'status': 'completed', 'result': {
                       'results': [
                           {'status': 'pass', 'failing_rows': []},
                           {'status': 'fail', 'failing_rows': [{'email': 'bad'}]},
                       ],
                   }}):
            jobs_module.refresh(job)
        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        results = DQResult.objects.filter(rule=self.nl_rule)
        self.assertEqual(results.count(), 2)
        self.assertEqual(results.filter(status='passed').count(), 1)
        self.assertEqual(results.filter(status='failed').count(), 1)

    def test_refresh_failed_writes_skipped_via_spec_on_failed(self):
        from dq.models import DQResult

        job = jobs_module.create_job(
            'nl_check', rule=self.nl_rule, user=self.admin, payload={'prompt': 'Check'})
        job.pulse_task_id = 'task-fail'
        job.status = 'running'
        job.save()
        with patch('ai.intelligence.CarbonIntelligence.get_task_status',
                   return_value={'status': 'failed', 'error': 'boom'}):
            jobs_module.refresh(job)
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertIn('boom', job.error)
        skipped = DQResult.objects.filter(
            rule=self.nl_rule, status='skipped_unavailable')
        self.assertEqual(skipped.count(), 1)


class RuleTemplateCatalogTests(TestCase):
    """dq/templates.py — the design-doc emp-no case + catalog integrity."""

    def test_employee_no_template_is_the_design_doc_case(self):
        """{"employee_no": {"type": "regex", "params": {"pattern": "^\\d{4,5}$"}}}"""
        tpl = templates.get_rule_template('employee_no')
        self.assertEqual(tpl['definition']['type'], 'regex')
        self.assertEqual(tpl['definition']['params']['pattern'], r'^\d{4,5}$')
        self.assertEqual(tpl['definition']['dimension'], 'validity')
        self.assertTrue(tpl['confirmation_required'])

    def test_list_rule_templates_metadata_shape(self):
        entries = templates.list_rule_templates()
        keys = [e['key'] for e in entries]
        self.assertIn('employee_no', keys)
        self.assertIn('email', keys)
        self.assertIn('non_negative', keys)
        self.assertIn('required', keys)
        for e in entries:
            self.assertTrue(e['label'])
            self.assertIn('confirmation_required', e)

    def test_get_rule_template_unknown_raises_key_error(self):
        with self.assertRaises(KeyError):
            templates.get_rule_template('nope')

    def test_instantiate_with_bindings(self):
        out = templates.instantiate_rule_template(
            'employee_no', table_name='hr_employees', field_name='employee_no')
        self.assertEqual(out['errors'], [])
        self.assertTrue(out['confirmation_required'])
        definition = out['definition']
        self.assertEqual(definition['bindings'], [
            {'table': 'hr_employees', 'field': 'employee_no'},
        ])
        # the instantiated definition is itself valid
        self.assertEqual(validate_definition(definition), [])

    def test_instantiate_with_overrides_merges_params(self):
        out = templates.instantiate_rule_template(
            'employee_no', overrides={'params': {'pattern': r'^\d{6}$'}})
        self.assertEqual(out['errors'], [])
        self.assertEqual(out['definition']['params']['pattern'], r'^\d{6}$')

    def test_instantiate_rejects_bad_override(self):
        out = templates.instantiate_rule_template(
            'employee_no', overrides={'params': {'pattern': r'('}})
        self.assertTrue(out['errors'])
        self.assertEqual(out['definition']['params']['pattern'], '(')

    def test_non_negative_template_is_a_range(self):
        out = templates.instantiate_rule_template('non_negative')
        self.assertEqual(out['errors'], [])
        self.assertEqual(out['definition']['type'], 'range')
        self.assertEqual(out['definition']['params'], {'min': 0})

    def test_required_template_is_not_null(self):
        out = templates.instantiate_rule_template('required')
        self.assertEqual(out['errors'], [])
        self.assertEqual(out['definition']['type'], 'not_null')
        self.assertEqual(out['definition']['dimension'], 'completeness')

    def test_catalog_integrity_all_templates_valid(self):
        failures = templates.validate_template_catalog()
        self.assertEqual(failures, [])
