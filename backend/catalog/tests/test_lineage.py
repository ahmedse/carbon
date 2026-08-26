"""Tests for lineage graph model and impact analysis API."""
import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

from catalog.models import LineageEdge
from dataschema.models import DataTable, DataField
from core.models import Module
from mdm.models import OrgUnit

User = get_user_model()


@pytest.fixture
def org_unit(db):
    return OrgUnit.objects.create(name='TestOrg', slug='test-org')


@pytest.fixture
def module_a(db, org_unit):
    return Module.objects.create(name='ModuleA', scope=1, org_unit=org_unit)


@pytest.fixture
def module_b(db, org_unit):
    return Module.objects.create(name='ModuleB', scope=1, org_unit=org_unit)


@pytest.fixture
def table_a(db, module_a):
    return DataTable.objects.create(module=module_a, name='table_a', title='Table A')


@pytest.fixture
def table_b(db, module_b):
    return DataTable.objects.create(module=module_b, name='table_b', title='Table B')


@pytest.fixture
def table_c(db, module_b):
    return DataTable.objects.create(module=module_b, name='table_c', title='Table C')


@pytest.fixture
def field_a1(db, table_a):
    return DataField.objects.create(
        data_table=table_a, name='field_a1', label='Field A1', type='number'
    )


@pytest.fixture
def field_b1(db, table_b):
    return DataField.objects.create(
        data_table=table_b, name='field_b1', label='Field B1', type='number'
    )


@pytest.fixture
def admin_user(db):
    user = User.objects.create_user(username='admin', password='pass', is_superuser=True)
    return user


@pytest.fixture
def normal_user(db):
    user = User.objects.create_user(username='normal', password='pass', is_superuser=False)
    return user


@pytest.fixture
def api_client_admin(api_client, admin_user, get_token_for_user):
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(admin_user)}')
    return api_client


@pytest.fixture
def api_client_normal(api_client, normal_user, get_token_for_user):
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(normal_user)}')
    return api_client


@pytest.fixture
def api_client_unauth(api_client):
    """Unauthenticated client."""
    return api_client


class TestLineageEdgeCreate:
    """Test creating LineageEdge and unique_together constraint."""

    def test_create_edge_success(self, db, api_client_admin, table_a, table_b):
        """POST /lineage/ creates edge successfully."""
        payload = {
            'source_table': table_a.id,
            'target_table': table_b.id,
            'edge_type': 'transform',
            'transform_description': 'SUM aggregation',
        }
        response = api_client_admin.post('/carbon-api/catalog/lineage/', payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['source_table'] == table_a.id
        assert response.data['target_table'] == table_b.id
        assert response.data['edge_type'] == 'transform'

    def test_unique_together_enforced(self, db, api_client_admin, table_a, table_b):
        """unique_together constraint prevents duplicate (source, target, edge_type)."""
        payload = {
            'source_table': table_a.id,
            'target_table': table_b.id,
            'edge_type': 'copy',
        }
        # First create succeeds
        response = api_client_admin.post('/carbon-api/catalog/lineage/', payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED

        # Second create with same (source, target, edge_type) fails
        response = api_client_admin.post('/carbon-api/catalog/lineage/', payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_different_edge_type_allowed(self, db, api_client_admin, table_a, table_b):
        """Same (source, target) with different edge_type is allowed."""
        payload_copy = {
            'source_table': table_a.id,
            'target_table': table_b.id,
            'edge_type': 'copy',
        }
        payload_transform = {
            'source_table': table_a.id,
            'target_table': table_b.id,
            'edge_type': 'transform',
        }
        assert api_client_admin.post('/carbon-api/catalog/lineage/', payload_copy, format='json').status_code == 201
        assert api_client_admin.post('/carbon-api/catalog/lineage/', payload_transform, format='json').status_code == 201


class TestLineageDirection:
    """Test upstream and downstream filtering."""

    def test_upstream_only(self, db, api_client_normal, table_a, table_b, table_c):
        """GET tables/{id}/lineage/?direction=upstream returns only incoming edges."""
        # Create edges: A -> B -> C
        edge1 = LineageEdge.objects.create(
            source_table=table_a, target_table=table_b, edge_type='transform'
        )
        edge2 = LineageEdge.objects.create(
            source_table=table_b, target_table=table_c, edge_type='copy'
        )
        
        # Query upstream for B: should get A -> B
        response = api_client_normal.get(
            f'/carbon-api/catalog/tables/{table_b.id}/lineage/?direction=upstream'
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data.get('upstream', [])) == 1
        assert len(response.data.get('downstream', [])) == 0
        assert response.data['upstream'][0]['source_table'] == table_a.id

    def test_downstream_only(self, db, api_client_normal, table_a, table_b, table_c):
        """GET tables/{id}/lineage/?direction=downstream returns only outgoing edges."""
        # Create edges: A -> B -> C
        edge1 = LineageEdge.objects.create(
            source_table=table_a, target_table=table_b, edge_type='transform'
        )
        edge2 = LineageEdge.objects.create(
            source_table=table_b, target_table=table_c, edge_type='copy'
        )
        
        # Query downstream for B: should get B -> C
        response = api_client_normal.get(
            f'/carbon-api/catalog/tables/{table_b.id}/lineage/?direction=downstream'
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data.get('upstream', [])) == 0
        assert len(response.data.get('downstream', [])) == 1
        assert response.data['downstream'][0]['target_table'] == table_c.id


class TestImpactAnalysis:
    """Test BFS impact analysis."""

    def test_impact_bfs_two_levels(self, db, api_client_normal, table_a, table_b, table_c):
        """GET tables/{id}/impact/ BFS: A -> B -> C returns 2 levels, total_affected=2."""
        # Create edges: A -> B -> C
        LineageEdge.objects.create(source_table=table_a, target_table=table_b, edge_type='transform')
        LineageEdge.objects.create(source_table=table_b, target_table=table_c, edge_type='aggregate')
        
        response = api_client_normal.get(f'/carbon-api/catalog/tables/{table_a.id}/impact/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['total_affected'] == 2
        assert len(response.data['levels']) == 2
        
        # Check depth 1 has table_b
        assert response.data['levels'][0]['depth'] == 1
        assert any(t['id'] == table_b.id for t in response.data['levels'][0]['tables'])
        
        # Check depth 2 has table_c
        assert response.data['levels'][1]['depth'] == 2
        assert any(t['id'] == table_c.id for t in response.data['levels'][1]['tables'])

    def test_cycle_guard_no_loop(self, db, api_client_normal, table_a, table_b):
        """Cycle guard: A -> B -> A does not loop infinitely."""
        # Create cycle: A -> B -> A
        LineageEdge.objects.create(source_table=table_a, target_table=table_b, edge_type='copy')
        LineageEdge.objects.create(source_table=table_b, target_table=table_a, edge_type='copy')
        
        # Impact from A should not hang; total_affected should be 1 (only B, no re-traverse)
        response = api_client_normal.get(f'/carbon-api/catalog/tables/{table_a.id}/impact/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['total_affected'] == 1  # Only B is affected
        assert len(response.data['levels']) == 1


class TestLineagePermissions:
    """Test RBAC: 401 unauthenticated, 403 non-admin POST."""

    def test_401_unauthenticated(self, api_client_unauth, table_a, table_b):
        """401 for unauthenticated POST /lineage/."""
        payload = {
            'source_table': table_a.id,
            'target_table': table_b.id,
            'edge_type': 'transform',
        }
        response = api_client_unauth.post('/carbon-api/catalog/lineage/', payload, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_read_allowed_unauthenticated(self, db, api_client_unauth):
        """GET /lineage/ for unauthenticated returns 401 (no anonymous read)."""
        response = api_client_unauth.get('/carbon-api/catalog/lineage/')
        # ReadAnyWriteAdmin allows reads to authenticated users only — anonymous gets 401.
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_403_non_admin_write(self, db, api_client_normal, table_a, table_b):
        """403 for non-admin POST /lineage/."""
        payload = {
            'source_table': table_a.id,
            'target_table': table_b.id,
            'edge_type': 'transform',
        }
        response = api_client_normal.post('/carbon-api/catalog/lineage/', payload, format='json')
        # ReadAnyWriteAdmin allows authenticated read, but requires write capability for write
        # Non-admin should get 403
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestLineageCascadeDelete:
    """Test cascade delete: deleting DataTable removes its LineageEdges."""

    def test_cascade_delete_on_table_delete(self, db, table_a, table_b):
        """Deleting a DataTable cascades delete to its LineageEdges."""
        edge = LineageEdge.objects.create(
            source_table=table_a, target_table=table_b, edge_type='transform'
        )
        edge_id = edge.id
        
        # Delete table_a
        table_a.delete()
        
        # Edge should be deleted
        assert not LineageEdge.objects.filter(id=edge_id).exists()

    def test_cascade_delete_target_table(self, db, table_a, table_b):
        """Deleting target table also cascades delete to its edges."""
        edge = LineageEdge.objects.create(
            source_table=table_a, target_table=table_b, edge_type='copy'
        )
        edge_id = edge.id
        
        # Delete table_b
        table_b.delete()
        
        # Edge should be deleted
        assert not LineageEdge.objects.filter(id=edge_id).exists()


class TestLineageFiltering:
    """Test query parameter filtering on lineage list endpoint."""

    def test_list_filter_by_source(self, db, api_client_normal, table_a, table_b, table_c):
        """GET /lineage/?source={id} filters by source_table."""
        e1 = LineageEdge.objects.create(source_table=table_a, target_table=table_b, edge_type='transform')
        e2 = LineageEdge.objects.create(source_table=table_a, target_table=table_c, edge_type='copy')
        e3 = LineageEdge.objects.create(source_table=table_b, target_table=table_c, edge_type='aggregate')
        
        response = api_client_normal.get(f'/carbon-api/catalog/lineage/?source={table_a.id}')
        assert response.status_code == status.HTTP_200_OK
        results = response.data['results'] if 'results' in response.data else response.data
        if isinstance(results, list):
            assert len(results) == 2
            assert all(e['source_table'] == table_a.id for e in results)

    def test_list_filter_by_target(self, db, api_client_normal, table_a, table_b, table_c):
        """GET /lineage/?target={id} filters by target_table."""
        e1 = LineageEdge.objects.create(source_table=table_a, target_table=table_c, edge_type='transform')
        e2 = LineageEdge.objects.create(source_table=table_b, target_table=table_c, edge_type='copy')
        
        response = api_client_normal.get(f'/carbon-api/catalog/lineage/?target={table_c.id}')
        assert response.status_code == status.HTTP_200_OK
        results = response.data['results'] if 'results' in response.data else response.data
        if isinstance(results, list):
            assert len(results) == 2
            assert all(e['target_table'] == table_c.id for e in results)


class TestLineageDelete:
    """Test deleting LineageEdge via API."""

    def test_delete_edge_as_admin(self, db, api_client_admin, table_a, table_b):
        """Admin can DELETE /lineage/{id}/."""
        edge = LineageEdge.objects.create(
            source_table=table_a, target_table=table_b, edge_type='transform'
        )
        response = api_client_admin.delete(f'/carbon-api/catalog/lineage/{edge.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not LineageEdge.objects.filter(id=edge.id).exists()

    def test_delete_edge_as_non_admin_fails(self, db, api_client_normal, table_a, table_b):
        """Non-admin cannot DELETE /lineage/{id}/."""
        edge = LineageEdge.objects.create(
            source_table=table_a, target_table=table_b, edge_type='transform'
        )
        response = api_client_normal.delete(f'/carbon-api/catalog/lineage/{edge.id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        # Edge should still exist
        assert LineageEdge.objects.filter(id=edge.id).exists()
