# File: importexport/tests/test_api.py
# Comprehensive API tests: ExportProject CRUD + run, ImportJob CRUD + download,
# ExportJob list/detail + download (status gated), RBAC, validation

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User, ScopedRole
from django.contrib.auth.models import Group
from core.models import Module
from dataschema.models import DataTable, DataField, DataRow
from importexport.models import ExportProject, ImportJob, ExportJob
from mdm.models import OrgUnit


class ExportProjectAPITests(TestCase):
    """ExportProject CRUD lifecycle and run action."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(username='exp_admin', password='pass', is_staff=True)
        self.user = User.objects.create_user(username='exp_user', password='pass')
        Group.objects.get_or_create(name='admins_group')
        ScopedRole.objects.create(user=self.admin, group=Group.objects.get(name='admins_group'), is_active=True)

        self.org = OrgUnit.objects.create(name='Export Org', code='EX')
        self.module = Module.objects.create(name='Export Module', scope=1, org_unit=self.org)
        self.table = DataTable.objects.create(module=self.module, name='exp_table', title='Export Table')
        DataField.objects.create(data_table=self.table, name='col1', label='Col1', type='string', order=1)
        DataField.objects.create(data_table=self.table, name='col2', label='Col2', type='number', order=2)
        DataRow.objects.create(data_table=self.table, values={'col1': 'A', 'col2': 1})
        DataRow.objects.create(data_table=self.table, values={'col1': 'B', 'col2': 2})

        self.list_url = reverse('exportproject-list')

    def _auth(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    # ── CRUD ──────────────────────────────────────────────────

    def test_list_export_projects(self):
        ExportProject.objects.create(name='P1', data_table=self.table, format='csv', owner=self.admin)
        ExportProject.objects.create(name='P2', data_table=self.table, format='excel', owner=self.admin)
        self._auth(self.admin)
        resp = self.client.get(self.list_url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) >= 2

    def test_create_export_project(self):
        self._auth(self.admin)
        resp = self.client.post(self.list_url, {
            'name': 'Monthly Export', 'data_table': self.table.id,
            'format': 'csv', 'description': 'Monthly data dump',
            'is_active': True,
        }, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['name'] == 'Monthly Export'
        assert resp.data['format'] == 'csv'
        assert resp.data['owner_name'] == 'exp_admin'
        assert resp.data['job_count'] == 0

    def test_retrieve_export_project(self):
        proj = ExportProject.objects.create(name='Detail Proj', data_table=self.table, format='json', owner=self.admin)
        self._auth(self.admin)
        resp = self.client.get(reverse('exportproject-detail', kwargs={'pk': proj.id}))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['name'] == 'Detail Proj'
        assert resp.data['slug'] == 'detail-proj'

    def test_patch_export_project(self):
        proj = ExportProject.objects.create(name='Old Proj', data_table=self.table, format='csv', owner=self.admin)
        self._auth(self.admin)
        resp = self.client.patch(
            reverse('exportproject-detail', kwargs={'pk': proj.id}),
            {'name': 'Updated Proj', 'filters': {'col1': 'A'}},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK
        proj.refresh_from_db()
        assert proj.name == 'Updated Proj'
        assert proj.filters == {'col1': 'A'}

    def test_delete_export_project(self):
        proj = ExportProject.objects.create(name='Del', data_table=self.table, format='csv', owner=self.admin)
        self._auth(self.admin)
        resp = self.client.delete(reverse('exportproject-detail', kwargs={'pk': proj.id}))
        assert resp.status_code == status.HTTP_204_NO_CONTENT

    # ── Run action ────────────────────────────────────────────

    def test_run_export_project_creates_job(self):
        proj = ExportProject.objects.create(name='Run Me', data_table=self.table, format='csv', owner=self.admin)
        self._auth(self.admin)
        resp = self.client.post(reverse('exportproject-run', kwargs={'pk': proj.id}))
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['status'] == 'ready'
        assert resp.data['row_count'] == 2
        assert resp.data['export_project'] == proj.id

    def test_run_updates_job_count(self):
        proj = ExportProject.objects.create(name='Count Me', data_table=self.table, format='csv', owner=self.admin)
        self._auth(self.admin)
        self.client.post(reverse('exportproject-run', kwargs={'pk': proj.id}))
        resp = self.client.get(reverse('exportproject-detail', kwargs={'pk': proj.id}))
        assert resp.data['job_count'] == 1

    # ── RBAC ──────────────────────────────────────────────────

    def test_non_admin_cannot_create(self):
        self._auth(self.user)
        resp = self.client.post(self.list_url, {
            'name': 'Hack', 'data_table': self.table.id, 'format': 'csv'
        }, format='json')
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_non_admin_cannot_delete(self):
        proj = ExportProject.objects.create(name='Protected', data_table=self.table, format='csv', owner=self.admin)
        self._auth(self.user)
        resp = self.client.delete(reverse('exportproject-detail', kwargs={'pk': proj.id}))
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_gets_401(self):
        self.client.credentials()
        resp = self.client.get(self.list_url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class ImportJobAPITests(TestCase):
    """ImportJob create, list, retrieve, download, validation."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(username='imp_admin', password='pass', is_staff=True)
        self.user = User.objects.create_user(username='imp_user', password='pass')
        Group.objects.get_or_create(name='admins_group')
        ScopedRole.objects.create(user=self.admin, group=Group.objects.get(name='admins_group'), is_active=True)

        self.org = OrgUnit.objects.create(name='Import Org', code='IM')
        self.module = Module.objects.create(name='Import Module', scope=1, org_unit=self.org)
        self.table = DataTable.objects.create(module=self.module, name='imp_table', title='Import Table')
        DataField.objects.create(data_table=self.table, name='item', label='Item', type='string', order=1, required=True)
        DataField.objects.create(data_table=self.table, name='qty', label='Qty', type='number', order=2)

        self.valid_csv = SimpleUploadedFile('data.csv', b'item,qty\r\n"Widget",10\r\n', content_type='text/csv')
        self.bad_file = SimpleUploadedFile('bad.xlsx', b'not-real-excel', content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        self.list_url = reverse('importjob-list')

    def _auth(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    # ── Create ────────────────────────────────────────────────

    def test_import_csv_creates_rows(self):
        self._auth(self.admin)
        resp = self.client.post(self.list_url, {
            'data_table': self.table.id, 'file': self.valid_csv, 'format': 'csv',
        })
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.data
        assert data['status'] == 'done'
        assert data['row_count'] == 1
        assert data['error_count'] == 0
        assert DataRow.objects.filter(data_table=self.table).count() == 1

    def test_import_bad_file_status_failed(self):
        self._auth(self.admin)
        resp = self.client.post(self.list_url, {
            'data_table': self.table.id, 'file': self.bad_file, 'format': 'excel',
        })
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.data
        assert data['status'] == 'failed'
        assert data['error_count'] > 0
        assert len(data['log']) > 0

    def test_import_missing_fields_returns_400(self):
        self._auth(self.admin)
        resp = self.client.post(self.list_url, {'file': self.valid_csv})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in resp.data

    def test_import_missing_file_returns_400(self):
        self._auth(self.admin)
        resp = self.client.post(self.list_url, {'data_table': self.table.id})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in resp.data

    # ── List and retrieve ─────────────────────────────────────

    def test_list_import_jobs(self):
        # Create via API
        self._auth(self.admin)
        self.client.post(self.list_url, {'data_table': self.table.id, 'file': self.valid_csv, 'format': 'csv'})
        resp = self.client.get(self.list_url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) >= 1

    def test_retrieve_import_job(self):
        self._auth(self.admin)
        create_resp = self.client.post(self.list_url, {
            'data_table': self.table.id, 'file': self.valid_csv, 'format': 'csv',
        })
        job_id = create_resp.data['id']
        resp = self.client.get(reverse('importjob-detail', kwargs={'pk': job_id}))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['status'] == 'done'

    # ── Download import file ──────────────────────────────────

    def test_download_import_file(self):
        self._auth(self.admin)
        create_resp = self.client.post(self.list_url, {
            'data_table': self.table.id, 'file': self.valid_csv, 'format': 'csv',
        })
        job_id = create_resp.data['id']
        resp = self.client.get(reverse('importjob-download', kwargs={'pk': job_id}))
        assert resp.status_code == status.HTTP_200_OK
        content = b''.join(resp.streaming_content)
        assert b'Widget' in content

    def test_download_no_file_returns_404(self):
        job = ImportJob.objects.create(
            data_table=self.table, file='', format='csv', status='done',
            row_count=0, error_count=0,
        )
        self._auth(self.admin)
        resp = self.client.get(reverse('importjob-download', kwargs={'pk': job.id}))
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    # ── RBAC ──────────────────────────────────────────────────

    def test_non_admin_cannot_create(self):
        self._auth(self.user)
        resp = self.client.post(self.list_url, {
            'data_table': self.table.id, 'file': self.valid_csv, 'format': 'csv',
        })
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_gets_401(self):
        self.client.credentials()
        resp = self.client.get(self.list_url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class ExportJobAPITests(TestCase):
    """ExportJob list, retrieve, download (status-gated)."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(username='exj_admin', password='pass', is_staff=True)
        Group.objects.get_or_create(name='admins_group')
        ScopedRole.objects.create(user=self.admin, group=Group.objects.get(name='admins_group'), is_active=True)

        self.org = OrgUnit.objects.create(name='ExJob Org', code='EJ')
        self.module = Module.objects.create(name='ExJob Module', scope=1, org_unit=self.org)
        self.table = DataTable.objects.create(module=self.module, name='exj_table', title='ExJob Table')
        DataField.objects.create(data_table=self.table, name='x', label='X', type='string', order=1)
        DataRow.objects.create(data_table=self.table, values={'x': 'hello'})

        self.list_url = reverse('exportjob-list')

    def _auth(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    def _create_ready_job(self):
        """Create an export project and run it to get a ready ExportJob."""
        proj = ExportProject.objects.create(name='Ready Export', data_table=self.table, format='csv', owner=self.admin)
        self._auth(self.admin)
        resp = self.client.post(reverse('exportproject-run', kwargs={'pk': proj.id}))
        return resp.data['id']

    # ── List and retrieve ─────────────────────────────────────

    def test_list_export_jobs(self):
        job_id = self._create_ready_job()
        self._auth(self.admin)
        resp = self.client.get(self.list_url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) >= 1

    def test_retrieve_export_job(self):
        job_id = self._create_ready_job()
        self._auth(self.admin)
        resp = self.client.get(reverse('exportjob-detail', kwargs={'pk': job_id}))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['status'] == 'ready'
        assert resp.data['row_count'] == 1

    # ── Download ──────────────────────────────────────────────

    def test_download_ready_job(self):
        job_id = self._create_ready_job()
        self._auth(self.admin)
        resp = self.client.get(reverse('exportjob-download', kwargs={'pk': job_id}))
        assert resp.status_code == status.HTTP_200_OK
        content = b''.join(resp.streaming_content)
        assert b'hello' in content

    def test_download_pending_job_blocked(self):
        """Pending export cannot be downloaded."""
        job = ExportJob.objects.create(
            data_table=self.table, format='csv', status='pending',
            row_count=0, user=self.admin,
        )
        self._auth(self.admin)
        resp = self.client.get(reverse('exportjob-download', kwargs={'pk': job.id}))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert 'not ready' in resp.data['error'].lower()

    def test_download_failed_job_blocked(self):
        """Failed export cannot be downloaded."""
        job = ExportJob.objects.create(
            data_table=self.table, format='csv', status='failed',
            row_count=0, user=self.admin,
        )
        self._auth(self.admin)
        resp = self.client.get(reverse('exportjob-download', kwargs={'pk': job.id}))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_download_no_file_returns_404(self):
        job = ExportJob.objects.create(
            data_table=self.table, format='csv', status='ready',
            row_count=1, file='', user=self.admin,
        )
        self._auth(self.admin)
        resp = self.client.get(reverse('exportjob-download', kwargs={'pk': job.id}))
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    # ── Auth ──────────────────────────────────────────────────

    def test_authenticated_user_can_list(self):
        user = User.objects.create_user(username='viewer', password='pass')
        self._auth(user)
        resp = self.client.get(self.list_url)
        assert resp.status_code == status.HTTP_200_OK

    def test_unauthenticated_gets_401(self):
        self.client.credentials()
        resp = self.client.get(self.list_url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
