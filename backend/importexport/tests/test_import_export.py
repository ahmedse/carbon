# importexport/tests/test_import_export.py
import csv
import io
import os

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User, ScopedRole
from core.models import Module
from dataschema.models import DataTable, DataField, DataRow
from importexport.models import ImportJob, ExportJob, ExportProject
from mdm.models import OrgUnit


class ImportExportIntegrationTests(TestCase):
    """E2-B5: import/export execution round-trip tests."""

    def setUp(self):
        # Auth setup
        self.user = User.objects.create_user(username='impexp_user', password='pass123')
        Group.objects.get_or_create(name='admins_group')
        ScopedRole.objects.create(
            user=self.user,
            group=Group.objects.get(name='admins_group'),
            is_active=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        # Org → Module → DataTable with fields
        self.org = OrgUnit.objects.create(name='HQ', slug='hq')
        self.module = Module.objects.create(name='Test Module', scope=1, org_unit=self.org)
        self.table = DataTable.objects.create(
            module=self.module, name='test_table', title='Test Table'
        )
        self.field_name = DataField.objects.create(
            data_table=self.table, name='item', label='Item',
            type='string', order=1, required=True, is_active=True,
        )
        self.field_qty = DataField.objects.create(
            data_table=self.table, name='qty', label='Quantity',
            type='number', order=2, is_active=True,
        )

    # ------------------------------------------------------------------
    # 1. CSV import creates DataRows → status=done, row_count correct
    # ------------------------------------------------------------------
    def test_csv_import_creates_rows_and_status_done(self):
        csv_content = b'item,qty\r\n"Widget",10\r\n"Gadget",20\r\n'
        file_obj = SimpleUploadedFile('test.csv', csv_content, content_type='text/csv')

        response = self.client.post(
            reverse('importjob-list'),
            {'data_table': self.table.id, 'file': file_obj, 'format': 'csv'},
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['status'], 'done')
        self.assertEqual(data['row_count'], 2)
        self.assertEqual(data['error_count'], 0)

        # Verify DataRows created
        rows = DataRow.objects.filter(data_table=self.table).order_by('id')
        self.assertEqual(rows.count(), 2)
        self.assertEqual(rows[0].values['item'], 'Widget')
        self.assertEqual(rows[0].values['qty'], 10)
        self.assertEqual(rows[1].values['item'], 'Gadget')
        self.assertEqual(rows[1].values['qty'], 20)

    # ------------------------------------------------------------------
    # 2. Import with bad file → status=failed
    # ------------------------------------------------------------------
    def test_import_bad_file_status_failed(self):
        file_obj = SimpleUploadedFile(
            'bad.xlsx', b'not-valid-excel', content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        response = self.client.post(
            reverse('importjob-list'),
            {'data_table': self.table.id, 'file': file_obj, 'format': 'excel'},
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['status'], 'failed')
        self.assertGreater(data['error_count'], 0)
        self.assertTrue(len(data['log']) > 0)

    # ------------------------------------------------------------------
    # 3. Export generates CSV file → download serves it
    # ------------------------------------------------------------------
    def test_export_generates_csv_and_download_serves_it(self):
        # Seed 2 rows
        DataRow.objects.create(data_table=self.table, values={'item': 'Foo', 'qty': 5})
        DataRow.objects.create(data_table=self.table, values={'item': 'Bar', 'qty': 15})

        project = ExportProject.objects.create(
            name='Test Export', data_table=self.table, format='csv',
            owner=self.user,
        )

        response = self.client.post(
            reverse('exportproject-run', kwargs={'pk': project.id}),
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['status'], 'ready')
        self.assertEqual(data['row_count'], 2)
        self.assertIsNotNone(data['download_url'])

        # Download the file
        job_id = data['id']
        dl_response = self.client.get(
            reverse('exportjob-download', kwargs={'pk': job_id}),
        )
        self.assertEqual(dl_response.status_code, 200)
        self.assertEqual(
            dl_response['Content-Type'],
            'text/csv',
        )

        # Parse CSV content
        content = b''.join(dl_response.streaming_content).decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        self.assertEqual(len(rows), 2)
        items = {r['item'] for r in rows}
        self.assertIn('Foo', items)
        self.assertIn('Bar', items)

    # ------------------------------------------------------------------
    # 4. Export with filters → correct rows
    # ------------------------------------------------------------------
    def test_export_with_filters_returns_correct_rows(self):
        DataRow.objects.create(data_table=self.table, values={'item': 'Alpha', 'qty': 1})
        DataRow.objects.create(data_table=self.table, values={'item': 'Beta', 'qty': 2})
        DataRow.objects.create(data_table=self.table, values={'item': 'Alpha', 'qty': 3})

        project = ExportProject.objects.create(
            name='Filtered Export', data_table=self.table, format='csv',
            filters={'item': 'Alpha'}, owner=self.user,
        )

        response = self.client.post(
            reverse('exportproject-run', kwargs={'pk': project.id}),
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['status'], 'ready')
        self.assertEqual(data['row_count'], 2)  # only Alpha rows

        # Download and verify only Alpha rows
        dl_response = self.client.get(
            reverse('exportjob-download', kwargs={'pk': data['id']}),
        )
        content = b''.join(dl_response.streaming_content).decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertEqual(r['item'], 'Alpha')

    # ------------------------------------------------------------------
    # 5. Import job download endpoint
    # ------------------------------------------------------------------
    def test_import_job_download_endpoint(self):
        csv_content = b'item,qty\r\n"Sprocket",7\r\n'
        file_obj = SimpleUploadedFile('sprockets.csv', csv_content, content_type='text/csv')

        # Create import via API
        create_resp = self.client.post(
            reverse('importjob-list'),
            {'data_table': self.table.id, 'file': file_obj, 'format': 'csv'},
        )
        job_id = create_resp.json()['id']

        # Download the uploaded file
        dl_response = self.client.get(
            reverse('importjob-download', kwargs={'pk': job_id}),
        )
        self.assertEqual(dl_response.status_code, 200)
        self.assertEqual(
            dl_response['Content-Type'],
            'text/csv',
        )

    # ------------------------------------------------------------------
    # 6. Export round-trip (import → export → compare)
    # ------------------------------------------------------------------
    def test_round_trip_import_export_compare(self):
        # Step 1: Import 3 rows
        csv_content = b'item,qty\r\n"Round",1\r\n"Trip",2\r\n"Test",3\r\n'
        file_obj = SimpleUploadedFile('roundtrip.csv', csv_content, content_type='text/csv')

        import_resp = self.client.post(
            reverse('importjob-list'),
            {'data_table': self.table.id, 'file': file_obj, 'format': 'csv'},
        )
        self.assertEqual(import_resp.status_code, 201)
        self.assertEqual(import_resp.json()['status'], 'done')
        self.assertEqual(import_resp.json()['row_count'], 3)

        # Step 2: Export as CSV
        project = ExportProject.objects.create(
            name='Round-Trip', data_table=self.table, format='csv',
            owner=self.user,
        )
        export_resp = self.client.post(
            reverse('exportproject-run', kwargs={'pk': project.id}),
        )
        self.assertEqual(export_resp.status_code, 201)
        export_data = export_resp.json()
        self.assertEqual(export_data['row_count'], 3)
        self.assertEqual(export_data['status'], 'ready')

        # Step 3: Download and compare
        dl_response = self.client.get(
            reverse('exportjob-download', kwargs={'pk': export_data['id']}),
        )
        content = b''.join(dl_response.streaming_content).decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))
        exported_rows = list(reader)
        self.assertEqual(len(exported_rows), 3)

        items = sorted(r['item'] for r in exported_rows)
        self.assertEqual(items, ['Round', 'Test', 'Trip'])
        qtys = sorted(int(r['qty']) for r in exported_rows)
        self.assertEqual(qtys, [1, 2, 3])
