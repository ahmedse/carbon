# dataschema/tests/test_validation.py

import pytest
from dataschema.serializers import DataRowSerializer
from dataschema.models import DataTable, DataField
from core.models import Module, Project
from accounts.models import Tenant

@pytest.fixture
def setup_table(db):
    tenant = Tenant.objects.create(name="Tenant")
    project = Project.objects.create(name="Project", tenant=tenant)
    module = Module.objects.create(name="Module", project=project)
    table = DataTable.objects.create(title="Test Table", name="test_table", module=module)
    field_str = DataField.objects.create(data_table=table, name="name", label="Name", type="string", required=True)
    field_num = DataField.objects.create(data_table=table, name="age", label="Age", type="number", required=True)
    field_sel = DataField.objects.create(
        data_table=table, name="color", label="Color", type="select", required=False, options=[{"value": "red"}, {"value": "blue"}]
    )
    field_multi = DataField.objects.create(
        data_table=table, name="tags", label="Tags", type="multiselect", required=False, options=[{"value": "a"}, {"value": "b"}]
    )
    return table, field_str, field_num, field_sel, field_multi

def test_valid_row(setup_table):
    table, fstr, fnum, fsel, fmulti = setup_table
    data = {
        "data_table": table.id,
        "values": {"name": "Ali", "age": 30, "color": "red", "tags": ["a"]}
    }
    serializer = DataRowSerializer(data=data)
    assert serializer.is_valid(), serializer.errors

def test_missing_required(setup_table):
    table, fstr, fnum, fsel, fmulti = setup_table
    data = {
        "data_table": table.id,
        "values": {"name": "Ali"}  # missing 'age'
    }
    serializer = DataRowSerializer(data=data)
    assert not serializer.is_valid()
    assert "age" in serializer.errors

def test_type_validation(setup_table):
    table, fstr, fnum, fsel, fmulti = setup_table
    data = {
        "data_table": table.id,
        "values": {"name": "Ali", "age": "not_a_number"}
    }
    serializer = DataRowSerializer(data=data)
    assert not serializer.is_valid()
    assert "age" in serializer.errors

def test_select_validation(setup_table):
    table, fstr, fnum, fsel, fmulti = setup_table
    data = {
        "data_table": table.id,
        "values": {"name": "Ali", "age": 42, "color": "green"}
    }
    serializer = DataRowSerializer(data=data)
    assert not serializer.is_valid()
    assert "color" in serializer.errors

def test_multiselect_validation(setup_table):
    table, fstr, fnum, fsel, fmulti = setup_table
    data = {
        "data_table": table.id,
        "values": {"name": "Ali", "age": 1, "tags": ["a", "x"]}  # include required fields!
    }
    serializer = DataRowSerializer(data=data)
    assert not serializer.is_valid()
    assert "tags" in serializer.errors