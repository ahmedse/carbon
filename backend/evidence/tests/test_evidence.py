"""Tests for evidence app: views, permissions, soft-delete."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from django.contrib.auth import get_user_model

from evidence.models import Evidence
from dataschema.models import DataRow, DataTable
from core.models import Module
from mdm.models import OrgUnit

User = get_user_model()


@pytest.fixture
def org_unit(db):
    return OrgUnit.objects.create(name='TestOrg', code='TO')


@pytest.fixture
def test_module(db, org_unit):
    return Module.objects.create(name='TestModule', scope=1, org_unit=org_unit)


@pytest.fixture
def data_table(db, test_module):
    return DataTable.objects.create(title='TestTable', name='test-table', module=test_module)


@pytest.fixture
def data_row(db, data_table):
    return DataRow.objects.create(data_table=data_table, values={'val': 1})


@pytest.fixture
def evidence_file(db, data_row, create_user):
    user = create_user('evidence_test_user', 'pass')
    fl = SimpleUploadedFile('test.pdf', b'pdf content', content_type='application/pdf')
    return Evidence.objects.create(
        data_row=data_row,
        file=fl,
        original_filename='test.pdf',
        file_size=10,
        mime_type='application/pdf',
        uploaded_by=user,
    )


class TestEvidenceModel:
    """Evidence model tests."""

    def test_soft_delete(self, evidence_file):
        ev = evidence_file
        assert ev.is_deleted is False
        ev.is_deleted = True
        ev.save()
        ev.refresh_from_db()
        assert ev.is_deleted is True

    def test_str_representation(self, evidence_file):
        assert str(evidence_file).startswith(evidence_file.original_filename)

    def test_evidence_relationships(self, evidence_file, data_row):
        assert evidence_file.data_row == data_row
        assert evidence_file in data_row.evidence.all()


@pytest.mark.django_db
class TestEvidenceAPI:
    """Evidence API endpoint tests (with db access needed for auth checks)."""

    def test_list_unauthenticated(self, api_client):
        resp = api_client.get(reverse('evidence:evidence-list'))
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_authenticated(self, api_client, get_token_for_user, create_user):
        user = create_user('evidence_list_user', 'pass')
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
        resp = api_client.get(reverse('evidence:evidence-list'))
        assert resp.status_code == status.HTTP_200_OK

    def test_superuser_can_retrieve(self, api_client, get_token_for_user,
                                     create_user, evidence_file):
        admin = create_user('evidence_get_admin', 'pass', is_superuser=True)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(admin)}')
        resp = api_client.get(
            reverse('evidence:evidence-detail', kwargs={'pk': evidence_file.pk}))
        assert resp.status_code == status.HTTP_200_OK

    def test_destroy_soft_deletes(self, api_client, get_token_for_user,
                                   create_user, evidence_file):
        admin = create_user('evidence_del_admin', 'pass', is_superuser=True)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(admin)}')
        resp = api_client.delete(
            reverse('evidence:evidence-detail', kwargs={'pk': evidence_file.pk}))
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        evidence_file.refresh_from_db()
        assert evidence_file.is_deleted is True

    def test_bulk_upload_requires_auth(self, api_client):
        resp = api_client.post(reverse('evidence:evidence-bulk-upload'))
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

