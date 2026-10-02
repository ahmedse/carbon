"""Two-layer Coverage tests: CoverageTarget / CoverageTask (locked 2 Oct 2026).

Proves: target CRUD, target detail carries its tasks, progress is derived from
real rows only (never a hand-set percent), a task can be done only on host
evidence, and the cycle default is the single open period.
"""
from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from django.contrib.auth.models import Group

from accounts.models import ScopedRole, User
from core.models import Module
from dataschema.models import DataField, DataRow, DataTable
from people.models import Employee
from emissions.models import (
    Calculation,
    CoverageGoal,
    CoverageTarget,
    CoverageTask,
    EmissionFactor,
    InventorySource,
    InventorySourceStatus,
    ReportingPeriod,
)
from emissions.coverage_targets import source_state, target_progress, task_evidence
from emissions.views import eligible_owner_queryset
from mdm.models import OrgUnit


def _factor(**kwargs):
    defaults = {
        'code': 'EG-GRID-TGT',
        'name': 'EG grid target test',
        'category': 'electricity',
        'scope': 2,
        'factor_value': Decimal('0.4584'),
        'activity_unit': 'kWh',
        'source': 'Test EG grid',
        'valid_from': date(2020, 1, 1),
        'is_active': True,
    }
    defaults.update(kwargs)
    return EmissionFactor.objects.create(**defaults)


class CoverageTargetModelTests(TestCase):
    def setUp(self):
        self.org = OrgUnit.objects.create(name='Smart Village', slug='tgt-sv')
        self.period = ReportingPeriod.objects.create(
            name='Calendar year 2026', start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31), status='open', period_type='annual',
        )

    def test_defaults_to_draft_and_string(self):
        target = CoverageTarget.objects.create(
            reporting_period=self.period, org_unit=self.org, scope='1+2',
            name='O1 Smart Village KPI', goal_kind='percent',
            goal_value=Decimal('25.00'), min_quality_tier=4,
        )
        self.assertEqual(target.status, 'draft')
        self.assertIn('O1 Smart Village KPI', str(target))

    def test_unique_binding_constraint(self):
        CoverageTarget.objects.create(
            reporting_period=self.period, org_unit=self.org, scope='1',
            name='Scope 1', goal_kind='percent', goal_value=Decimal('80.00'),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CoverageTarget.objects.create(
                    reporting_period=self.period, org_unit=self.org, scope='1',
                    name='Scope 1', goal_kind='percent', goal_value=Decimal('90.00'),
                )

    def test_percent_over_100_is_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CoverageTarget.objects.create(
                    reporting_period=self.period, org_unit=self.org, scope='2',
                    name='Too big', goal_kind='percent', goal_value=Decimal('101.00'),
                )

    def test_creating_a_target_never_promotes_a_coverage_goal(self):
        goal = CoverageGoal.objects.create(
            org_unit=self.org, name='O1 Smart Village', scope='1+2',
            target_coverage_pct=Decimal('25.00'), min_quality_tier=4,
            completeness_definition='materiality_bounded', target_year=2030,
            status='draft',
        )
        CoverageTarget.objects.create(
            reporting_period=self.period, org_unit=self.org, scope='1+2',
            name='O1 KPI', goal_kind='percent', goal_value=Decimal('25.00'),
            coverage_goal=goal,
        )
        goal.refresh_from_db()
        self.assertEqual(goal.status, 'draft')


class CoverageTargetProgressTests(TestCase):
    def setUp(self):
        self.org = OrgUnit.objects.create(name='Smart Village', slug='tgt-prog')
        self.period = ReportingPeriod.objects.create(
            name='Calendar year 2026', start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31), status='open', period_type='annual',
        )
        self.module = Module.objects.create(name='SV electricity', scope=2, org_unit=self.org)
        self.table = DataTable.objects.create(name='sv_kwh_t', title='SV kWh', module=self.module)
        DataField.objects.create(data_table=self.table, name='kwh', label='kWh', type='number')
        self.target = CoverageTarget.objects.create(
            reporting_period=self.period, org_unit=self.org, scope='2',
            name='Scope 2 KPI', goal_kind='percent', goal_value=Decimal('100.00'),
        )

    def test_empty_universe_is_absent_not_zero(self):
        progress = target_progress(self.target)
        self.assertEqual(progress['counts']['required'], 0)
        self.assertIsNone(progress['measured_pct'])
        self.assertEqual(progress['state'], 'empty')
        self.assertFalse(progress['coverage_complete'])

    def test_missing_stream_is_not_a_percent_claim(self):
        InventorySource.objects.create(
            org_unit=self.org, scope=2, source_name='Smart Village electricity'
        )
        progress = target_progress(self.target)
        self.assertEqual(progress['counts']['missing'], 1)
        self.assertEqual(progress['measured_pct'], '0.00')
        self.assertEqual(progress['state'], 'short')
        self.assertEqual(progress['claim'], 'measured_not_claimed')

    def test_entered_requires_calculation_on_the_same_period(self):
        source = InventorySource.objects.create(
            org_unit=self.org, scope=2, source_name='Smart Village electricity'
        )
        status = InventorySourceStatus.objects.create(
            source=source, reporting_period=self.period, status='covered',
        )
        status.linked_tables.add(self.table)
        # Linked table, but no Calculation on the period -> still not entered.
        self.assertEqual(source_state(source, self.period)['status'], 'missing')
        factor = _factor()
        row = DataRow.objects.create(data_table=self.table, values={'kwh': 100})
        Calculation.create_from_data_row(
            data_row=row, emission_factor=factor, activity_value=100,
            activity_unit='kWh', reporting_year=2026, reporting_period=self.period,
        )
        state = source_state(source, self.period)
        self.assertEqual(state['status'], 'entered')
        self.assertIsNotNone(state['inventory_kg'])
        progress = target_progress(self.target)
        self.assertEqual(progress['counts']['entered'], 1)
        self.assertEqual(progress['measured_pct'], '100.00')
        self.assertEqual(progress['state'], 'met')

    def test_excluded_counts_as_settled_not_entered(self):
        source = InventorySource.objects.create(
            org_unit=self.org, scope=2, source_name='Contractual PPA'
        )
        InventorySourceStatus.objects.create(
            source=source, reporting_period=self.period, status='excluded',
            exclusion_reason='not_material',
        )
        progress = target_progress(self.target)
        self.assertEqual(progress['counts']['excluded'], 1)
        self.assertEqual(progress['counts']['entered'], 0)
        self.assertEqual(progress['measured_pct'], '100.00')

    def test_absolute_goal_reports_kg_only_from_real_calculations(self):
        target = CoverageTarget.objects.create(
            reporting_period=self.period, org_unit=self.org, scope='2',
            name='Absolute kWh KPI', goal_kind='absolute',
            goal_value=Decimal('1000.0000'), goal_unit='kWh',
        )
        progress = target_progress(target)
        self.assertIsNone(progress['measured_kg'])
        self.assertEqual(progress['state'], 'empty')


class CoverageTargetAPITests(TestCase):
    def setUp(self):
        self.org = OrgUnit.objects.create(name='Smart Village', slug='tgt-api')
        self.period = ReportingPeriod.objects.create(
            name='Calendar year 2026', start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31), status='open', period_type='annual',
        )
        self.locked = ReportingPeriod.objects.create(
            name='FY 2025-26', start_date=date(2025, 7, 1),
            end_date=date(2026, 6, 30), status='locked', period_type='annual',
        )
        self.user = User.objects.create_superuser(username='lead_tgt', password='AdminPa_132')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _payload(self, **extra):
        payload = {
            'reporting_period': self.period.id,
            'org_unit': self.org.id,
            'scope': '1+2',
            'name': 'O1 KPI',
            'goal_kind': 'percent',
            'goal_value': '25.00',
            'min_quality_tier': 4,
        }
        payload.update(extra)
        return payload

    def test_create_and_list_default_to_open_period(self):
        resp = self.client.post(
            reverse('carbon:coverage-target-list'), self._payload(), format='json'
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['status'], 'draft')
        self.assertIn('progress', resp.data)
        # A target on a locked period is readable history, created via the ORM.
        CoverageTarget.objects.create(
            reporting_period=self.locked, org_unit=self.org, scope='1',
            name='FY history', goal_kind='percent', goal_value=Decimal('80.00'),
        )
        listed = self.client.get(reverse('carbon:coverage-target-list'))
        self.assertEqual(listed.status_code, 200)
        names = [row['name'] for row in listed.data]
        self.assertEqual(names, ['O1 KPI'])

    def test_board_returns_cycle_dropdown_and_default(self):
        self.client.post(reverse('carbon:coverage-target-list'), self._payload(), format='json')
        resp = self.client.get(reverse('carbon:coverage-target-board'))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['period_default'], self.period.id)
        self.assertFalse(resp.data['coverage_complete'])
        ids = {row['id'] for row in resp.data['periods']}
        self.assertIn(self.period.id, ids)
        self.assertIn(self.locked.id, ids)
        self.assertEqual(len(resp.data['targets']), 1)

    def test_retrieve_includes_tasks(self):
        target = CoverageTarget.objects.create(
            reporting_period=self.period, org_unit=self.org, scope='1+2',
            name='O1 KPI', goal_kind='percent', goal_value=Decimal('25.00'),
        )
        CoverageTask.objects.create(
            target=target, task_type='secure_factor', title='Secure waste factor',
        )
        resp = self.client.get(reverse('carbon:coverage-target-detail', args=[target.id]))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['tasks']), 1)
        self.assertEqual(resp.data['tasks'][0]['task_type'], 'secure_factor')

    def test_update_and_delete(self):
        target = CoverageTarget.objects.create(
            reporting_period=self.period, org_unit=self.org, scope='1',
            name='S1', goal_kind='percent', goal_value=Decimal('50.00'),
        )
        resp = self.client.patch(
            reverse('carbon:coverage-target-detail', args=[target.id]),
            {'status': 'active'}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['status'], 'active')
        resp = self.client.delete(reverse('carbon:coverage-target-detail', args=[target.id]))
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(CoverageTarget.objects.filter(pk=target.id).exists())

    def test_target_on_non_open_period_is_rejected(self):
        resp = self.client.post(
            reverse('carbon:coverage-target-list'),
            self._payload(reporting_period=self.locked.id), format='json',
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['details']['reporting_period'], ['period_not_open'])

    def test_absolute_goal_needs_a_unit(self):
        resp = self.client.post(
            reverse('carbon:coverage-target-list'),
            self._payload(goal_kind='absolute', goal_value='5000.0000'), format='json',
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['details']['goal_unit'], ['absolute_needs_unit'])

    def test_non_admin_write_is_forbidden(self):
        pleb = User.objects.create_user(username='tgt_pleb', password='pass')
        self.client.force_authenticate(pleb)
        resp = self.client.post(
            reverse('carbon:coverage-target-list'), self._payload(), format='json'
        )
        self.assertEqual(resp.status_code, 403)


class CoverageTaskEvidenceTests(TestCase):
    def setUp(self):
        self.org = OrgUnit.objects.create(name='Smart Village', slug='task-ev')
        self.period = ReportingPeriod.objects.create(
            name='Calendar year 2026', start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31), status='open', period_type='annual',
        )
        self.module = Module.objects.create(name='SV', scope=2, org_unit=self.org)
        self.table = DataTable.objects.create(name='sv_t', title='SV', module=self.module)
        self.field = DataField.objects.create(
            data_table=self.table, name='kwh', label='kWh', type='number',
        )
        self.source = InventorySource.objects.create(
            org_unit=self.org, scope=2, source_name='Smart Village electricity'
        )
        self.target = CoverageTarget.objects.create(
            reporting_period=self.period, org_unit=self.org, scope='2',
            name='Scope 2 KPI', goal_kind='percent', goal_value=Decimal('100.00'),
        )
        self.user = User.objects.create_superuser(username='lead_task', password='AdminPa_132')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _task(self, **extra):
        payload = {'target': self.target.id, 'task_type': 'other', 'title': 't'}
        payload.update(extra)
        return self.client.post(reverse('carbon:coverage-task-list'), payload, format='json')

    def _mark_done(self, task_id):
        return self.client.patch(
            reverse('carbon:coverage-task-detail', args=[task_id]),
            {'status': 'done'}, format='json',
        )

    def test_create_and_list_tasks(self):
        resp = self._task(task_type='secure_factor', title='Secure waste factor')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn('evidence', resp.data)
        listed = self.client.get(
            reverse('carbon:coverage-task-list'), {'target': self.target.id}
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.data), 1)

    def test_bind_data_product_cannot_be_done_without_a_table(self):
        created = self._task(task_type='bind_data_product', title='Bind contract')
        task_id = created.data['id']
        resp = self._mark_done(task_id)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('task_evidence', str(resp.data))

    def test_bind_data_product_done_with_a_table(self):
        created = self._task(
            task_type='bind_data_product', title='Bind contract',
            data_table=self.table.id,
        )
        resp = self._mark_done(created.data['id'])
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['status'], 'done')
        self.assertTrue(resp.data['evidence']['met'])

    def test_secure_factor_requires_an_active_factor(self):
        factor = _factor(is_active=False, code='WASTE-1')
        created = self._task(
            task_type='secure_factor', title='Secure factor', factor=factor.id,
        )
        resp = self._mark_done(created.data['id'])
        self.assertEqual(resp.status_code, 400)
        factor.is_active = True
        factor.save(update_fields=['is_active'])
        resp = self._mark_done(created.data['id'])
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_fill_gap_requires_a_real_row(self):
        created = self._task(
            task_type='fill_gap', title='Fill SV gap', stream_source=self.source.id,
        )
        resp = self._mark_done(created.data['id'])
        self.assertEqual(resp.status_code, 400)
        status = InventorySourceStatus.objects.create(
            source=self.source, reporting_period=self.period, status='covered',
        )
        status.linked_tables.add(self.table)
        factor = _factor()
        row = DataRow.objects.create(data_table=self.table, values={'kwh': 10})
        Calculation.create_from_data_row(
            data_row=row, emission_factor=factor, activity_value=10,
            activity_unit='kWh', reporting_year=2026, reporting_period=self.period,
        )
        resp = self._mark_done(created.data['id'])
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_complete_rows_requires_rows_through_the_month(self):
        created = self._task(
            task_type='complete_rows', title='Rows through May',
            data_table=self.table.id, through_month='2026-05-01',
        )
        task_id = created.data['id']
        resp = self._mark_done(task_id)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('rows_not_complete', str(resp.data))
        DataRow.objects.create(
            data_table=self.table, values={'month': '2026-05-01', 'kwh': 12}
        )
        resp = self._mark_done(task_id)
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_other_task_completes_manually(self):
        created = self._task(task_type='other', title='Write the note')
        resp = self._mark_done(created.data['id'])
        self.assertEqual(resp.status_code, 200, resp.data)


class CoverageLookupTests(TestCase):
    """Campus / org-unit / owner lookups and campus_name / owner_name fields."""

    def setUp(self):
        # ADR-0028 allows a single active root: build one university root and
        # hang both campuses under it, so neither campus is a root.
        self.root = OrgUnit.objects.create(
            name='AASTMT', slug='lk-root', org_type='university',
        )
        self.sv = OrgUnit.objects.create(
            name='Smart Village Campus', slug='lk-sv', org_type='campus',
            parent=self.root,
        )
        self.sv_lab = OrgUnit.objects.create(
            name='SV Lab', slug='lk-sv-lab', org_type='department', parent=self.sv,
        )
        self.abu_qir = OrgUnit.objects.create(
            name='Abu Qir Campus', slug='lk-aq', org_type='campus',
            parent=self.root,
        )
        self.period = ReportingPeriod.objects.create(
            name='Calendar year 2026', start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31), status='open', period_type='annual',
        )
        self.owner = User.objects.create_user(
            username='data.sv', password='x', first_name='Data', last_name='Owner',
        )
        self.admin = User.objects.create_superuser(username='lk_admin', password='AdminPa_132')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def _payload(self, **extra):
        payload = {
            'reporting_period': self.period.id,
            'campus': self.sv.id,
            'org_unit': self.sv_lab.id,
            'scope': '1+2',
            'name': 'SV KPI',
            'goal_kind': 'percent',
            'goal_value': '80.00',
            'owner': self.owner.id,
        }
        payload.update(extra)
        return payload

    def test_campuses_lists_only_real_campus_org_units(self):
        resp = self.client.get(reverse('carbon:coverage-target-campuses'))
        self.assertEqual(resp.status_code, 200, resp.data)
        names = [row['name'] for row in resp.data['results']]
        self.assertIn('Smart Village Campus', names)
        self.assertIn('Abu Qir Campus', names)
        # A descendant department is not a campus option.
        self.assertNotIn('SV Lab', names)

    def test_org_units_are_the_selected_campus_descendants(self):
        resp = self.client.get(
            reverse('carbon:coverage-target-org-units'), {'campus': self.sv.id},
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {row['id'] for row in resp.data['results']}
        self.assertEqual(ids, {self.sv.id, self.sv_lab.id})
        campus_row = next(r for r in resp.data['results'] if r['id'] == self.sv.id)
        self.assertTrue(campus_row['is_campus'])
        lab_row = next(r for r in resp.data['results'] if r['id'] == self.sv_lab.id)
        self.assertFalse(lab_row['is_campus'])
        # A different campus's units never leak in.
        self.assertNotIn(self.abu_qir.id, ids)

    def test_org_units_requires_a_campus(self):
        resp = self.client.get(reverse('carbon:coverage-target-org-units'))
        self.assertEqual(resp.status_code, 400)

    def test_owners_search_is_real_and_type_to_search(self):
        resp = self.client.get(reverse('carbon:coverage-target-owners'))
        self.assertEqual(resp.status_code, 200, resp.data)
        usernames = [row['username'] for row in resp.data['results']]
        self.assertIn('data.sv', usernames)
        filtered = self.client.get(
            reverse('carbon:coverage-target-owners'), {'q': 'data.sv'},
        )
        self.assertEqual(
            [row['username'] for row in filtered.data['results']], ['data.sv'],
        )

    def test_serializer_exposes_campus_name_and_owner_name(self):
        target = CoverageTarget.objects.create(
            reporting_period=self.period, campus=self.sv, org_unit=self.sv_lab,
            scope='1+2', name='SV KPI', goal_kind='percent',
            goal_value=Decimal('80.00'), owner=self.owner,
        )
        detail = self.client.get(
            reverse('carbon:coverage-target-detail', args=[target.id]),
        )
        self.assertEqual(detail.data['campus_name'], 'Smart Village Campus')
        self.assertEqual(detail.data['owner_name'], 'Data Owner')
        self.assertEqual(detail.data['org_unit_name'], 'SV Lab')

    def test_owner_name_falls_back_to_username(self):
        bare = User.objects.create_user(username='bare.user', password='x')
        target = CoverageTarget.objects.create(
            reporting_period=self.period, org_unit=self.sv, scope='2',
            name='Bare', goal_kind='percent', goal_value=Decimal('50.00'), owner=bare,
        )
        detail = self.client.get(
            reverse('carbon:coverage-target-detail', args=[target.id]),
        )
        self.assertEqual(detail.data['owner_name'], 'bare.user')

    def test_org_unit_must_be_a_descendant_of_the_campus(self):
        resp = self.client.post(
            reverse('carbon:coverage-target-list'),
            self._payload(campus=self.abu_qir.id, org_unit=self.sv_lab.id),
            format='json',
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('org_unit_not_in_campus', str(resp.data))

    def test_campus_must_be_a_campus_org_unit(self):
        resp = self.client.post(
            reverse('carbon:coverage-target-list'),
            self._payload(campus=self.sv_lab.id, org_unit=self.sv_lab.id),
            format='json',
        )
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('campus_not_a_campus', str(resp.data))


class CoverageOwnerEligibilityTests(TestCase):
    """The owner lookup only offers real people / designated data owners.

    A Carbon Lead must never be able to pick a probe, shell tester or schema
    fixture as a target owner, but the real people and the seeded data-owner
    accounts must stay selectable, and ``?q=`` must filter inside that set.
    """

    def setUp(self):
        self.root = OrgUnit.objects.create(
            name='AASTMT', slug='own-root', org_type='university',
        )
        self.campus = OrgUnit.objects.create(
            name='Smart Village', slug='own-sv', org_type='campus', parent=self.root,
        )
        self.period = ReportingPeriod.objects.create(
            name='Calendar year 2026', start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31), status='open', period_type='annual',
        )
        self.admin = User.objects.create_superuser(
            username='own_admin', password='AdminPa_132',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def _usernames(self, **params):
        resp = self.client.get(reverse('carbon:coverage-target-owners'), params)
        self.assertEqual(resp.status_code, 200, resp.data)
        return [row['username'] for row in resp.data['results']]

    def test_named_people_scoped_data_owners_and_employee_links_are_eligible(self):
        named = User.objects.create_user(
            username='mostafa.kamel', password='x',
            first_name='Mostafa', last_name='Kamel',
        )
        owner_group = Group.objects.create(name='dataowners_group')
        scoped = User.objects.create_user(username='alamein.finance', password='x')
        ScopedRole.objects.create(user=scoped, group=owner_group, org_unit=self.campus)
        employee_user = User.objects.create_user(username='emp_1067', password='x')
        Employee.objects.create(
            org_unit=self.campus, employee_no='E-1',
            full_name='Bilagot Panta Suerte', user=employee_user,
            basic_salary=Decimal('100.000'),
        )

        usernames = self._usernames()
        self.assertIn(named.username, usernames)
        self.assertIn(scoped.username, usernames)
        self.assertIn(employee_user.username, usernames)

    def test_seeded_data_owner_accounts_stay_eligible(self):
        for username in ('data.smartvillage', 'data.abuqir'):
            User.objects.create_user(
                username=username, password='x',
                first_name='Data', last_name='Owner',
            )
        usernames = self._usernames()
        self.assertIn('data.smartvillage', usernames)
        self.assertIn('data.abuqir', usernames)

    def test_probe_and_fixture_accounts_are_excluded(self):
        junk = (
            'dbg_u1', 'debuguser', 'shell_tester', 'schemauser', 'probe-admin2',
            'gov_author_x', 'moodle-2', 'w6f_viewer', 'owner1', 'owner2',
            'admin1', 'analyst1', 'viewer1', 'carbon_lead_user',
        )
        for username in junk:
            User.objects.create_user(username=username, password='x')
        usernames = self._usernames()
        for username in junk:
            self.assertNotIn(username, usernames)

    def test_global_dataowner_duty_without_an_org_unit_is_not_enough(self):
        owner_group = Group.objects.create(name='dataowners_group')
        global_only = User.objects.create_user(username='owner1', password='x')
        ScopedRole.objects.create(user=global_only, group=owner_group)  # no org unit
        self.assertNotIn(global_only.username, self._usernames())

    def test_search_filters_within_the_eligible_set(self):
        User.objects.create_user(
            username='mostafa.kamel', password='x',
            first_name='Mostafa', last_name='Kamel',
        )
        User.objects.create_user(username='dbg_kamel', password='x')
        # A junk account matching the query stays excluded.
        self.assertEqual(self._usernames(q='kamel'), ['mostafa.kamel'])
        self.assertEqual(self._usernames(q='dbg'), [])


class SeedCoverageTargetsTests(TestCase):
    """The local seed command is idempotent and writes no measured value."""

    def setUp(self):
        self.sv = OrgUnit.objects.create(
            name='Smart Village', slug='seed-sv', org_type='campus',
        )
        OrgUnit.objects.create(
            name='Facilities & Utilities', slug='seed-fac',
            org_type='department', parent=self.sv,
        )
        self.period = ReportingPeriod.objects.create(
            name='Calendar year 2026', start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31), status='open', period_type='annual',
        )

    def _run(self):
        out = StringIO()
        call_command('seed_coverage_targets', stdout=out)
        return out.getvalue()

    def test_seed_is_idempotent_and_writes_no_kilogram(self):
        first_run = self._run()
        target_count = CoverageTarget.objects.filter(
            reporting_period=self.period,
        ).count()
        task_count = CoverageTask.objects.count()
        self.assertGreaterEqual(target_count, 3)  # Smart Village specs
        self.assertGreater(task_count, 0)
        self.assertIn('created=', first_run)

        # Re-running must not duplicate a target or a task.
        self._run()
        self.assertEqual(
            CoverageTarget.objects.filter(reporting_period=self.period).count(),
            target_count,
        )
        self.assertEqual(CoverageTask.objects.count(), task_count)

        # No kilogram, no calculation, no stream state written by the seed.
        self.assertEqual(Calculation.objects.count(), 0)
        self.assertEqual(InventorySourceStatus.objects.count(), 0)

        # Progress stays honestly derived: measured, not claimed, no kg.
        for target in CoverageTarget.objects.filter(reporting_period=self.period):
            progress = target_progress(target)
            self.assertEqual(progress['claim'], 'measured_not_claimed')
            self.assertIsNone(progress['measured_kg'])
            self.assertFalse(progress['coverage_complete'])

    def test_seed_leaves_a_missing_owner_null_and_reports_it(self):
        output = self._run()
        # 'data.abuqir' etc. do not exist in this DB — reported, never invented.
        self.assertIn('missing owners', output)
        self.assertFalse(
            CoverageTarget.objects.filter(owner__isnull=False).exists(),
        )

    def _scoped_owner(self, username, org_unit):
        group, _ = Group.objects.get_or_create(name='dataowners_group')
        user = User.objects.create_user(username=username, password='x')
        ScopedRole.objects.create(user=user, group=group, org_unit=org_unit)
        return user

    def test_every_seeded_target_owner_passes_the_eligibility_rule(self):
        """Regression: a seeded owner must never be one the picker rejects.

        The old seed bound one target to the bare ``carbon_lead_user`` fixture,
        which has no name / Employee link / scoped duty and is excluded by
        ``eligible_owner_queryset``. Every seeded row must pass that same rule.
        """
        owner = self._scoped_owner('data.smartvillage', self.sv)
        fixture = User.objects.create_user(username='carbon_lead_user', password='x')
        eligible_ids = set(eligible_owner_queryset().values_list('id', flat=True))
        self.assertIn(owner.id, eligible_ids)
        self.assertNotIn(fixture.id, eligible_ids)

        self._run()

        targets = CoverageTarget.objects.filter(reporting_period=self.period)
        self.assertGreater(targets.count(), 0)
        for target in targets:
            self.assertIsNotNone(target.owner_id, target.name)
            self.assertIn(target.owner_id, eligible_ids, target.name)

    def test_seed_repairs_an_ineligible_owner_in_place(self):
        """An existing seeded row owned by an ineligible fixture is updated,
        never duplicated: identity stays (period, org_unit, scope, name)."""
        owner = self._scoped_owner('data.smartvillage', self.sv)
        fixture = User.objects.create_user(username='carbon_lead_user', password='x')
        identity = {
            'reporting_period': self.period,
            'org_unit': self.sv,
            'scope': '3',
            'scope3_category': 5,
            'name': 'Scope 3 Cat 5 waste coverage — Smart Village',
        }
        existing = CoverageTarget.objects.create(
            campus=self.sv, owner=fixture, goal_kind='percent',
            goal_value=Decimal('80.00'), status='active', **identity,
        )

        self._run()

        existing.refresh_from_db()
        self.assertEqual(existing.owner_id, owner.id)
        self.assertEqual(CoverageTarget.objects.filter(**identity).count(), 1)
        self.assertNotEqual(existing.owner_id, fixture.id)


class CoverageTaskScopeTests(TestCase):
    def test_task_evidence_reports_codes(self):
        org = OrgUnit.objects.create(name='Facilities', slug='task-codes')
        period = ReportingPeriod.objects.create(
            name='CY2026', start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31), status='open',
        )
        target = CoverageTarget.objects.create(
            reporting_period=period, org_unit=org, scope='3', scope3_category=5,
            name='Waste', goal_kind='percent', goal_value=Decimal('100.00'),
        )
        task = CoverageTask(target=target, task_type='bind_data_product', title='x')
        evidence = task_evidence(task)
        self.assertFalse(evidence['met'])
        self.assertIn('data_table_unbound', evidence['codes'])
