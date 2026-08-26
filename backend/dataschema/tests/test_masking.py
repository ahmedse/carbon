# dataschema/tests/test_masking.py
"""
EPH-4B: Data Masking Engine tests.
"""
import pytest
from django.urls import reverse

from dataschema.masking import MaskingService


@pytest.fixture
def setup_schema(db):
    from core.models import Module
    from dataschema.models import DataTable, DataField, DataRow
    from catalog.models import AssetProfile

    module = Module.objects.create(name="Masking Test Module")
    table = DataTable.objects.create(title="Masking Table", name="masking_table", module=module)
    name_field = DataField.objects.create(
        data_table=table, name="name", label="Name", type="string"
    )
    pii_field = DataField.objects.create(
        data_table=table, name="ssn", label="SSN", type="string", masking_strategy="redact"
    )
    AssetProfile.objects.create(data_field=pii_field, classification="pii")
    row = DataRow.objects.create(
        data_table=table, values={"name": "John Smith", "ssn": "123-45-6789"}
    )

    return {
        "module": module,
        "table": table,
        "name_field": name_field,
        "pii_field": pii_field,
        "row": row,
    }


def test_mask_value_redact():
    assert MaskingService.mask_value('John Smith', 'redact') == '[REDACTED]'


def test_mask_value_truncate():
    assert MaskingService.mask_value('John Smith', 'truncate') == 'Joh***'


def test_mask_value_hash():
    result = MaskingService.mask_value('abc', 'hash')
    assert result.startswith('h:')
    assert len(result) == 14


def test_mask_value_null():
    assert MaskingService.mask_value('x', 'null') is None


def test_mask_value_none_failsafe():
    assert MaskingService.mask_value('x', 'none') == '[REDACTED]'


@pytest.mark.django_db
def test_pii_field_masked_for_non_pii_user(
    api_client, create_user, create_scoped_role, get_token_for_user, setup_schema
):
    row = setup_schema["row"]
    table = setup_schema["table"]
    user = create_user("analyst")
    create_scoped_role(user, "analysts_group")  # GLOBAL role, lacks catalog:view_pii
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")

    url = reverse("dataschema-row-detail", kwargs={"pk": row.id}) + f"?data_table={table.id}"
    resp = api_client.get(url)
    assert resp.status_code == 200
    assert resp.data["values"]["ssn"] == "[REDACTED]"
    assert resp.data["values"]["name"] == "John Smith"


@pytest.mark.django_db
def test_pii_field_not_masked_for_pii_user(
    api_client, create_user, create_scoped_role, get_token_for_user, setup_schema
):
    row = setup_schema["row"]
    table = setup_schema["table"]
    user = create_user("dataowner")
    create_scoped_role(user, "dataowners_group")  # GLOBAL role, grants catalog:view_pii
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")

    url = reverse("dataschema-row-detail", kwargs={"pk": row.id}) + f"?data_table={table.id}"
    resp = api_client.get(url)
    assert resp.status_code == 200
    assert resp.data["values"]["ssn"] == "123-45-6789"


@pytest.mark.django_db
def test_none_strategy_no_masking(
    api_client, create_user, create_scoped_role, get_token_for_user, setup_schema
):
    pii_field = setup_schema["pii_field"]
    pii_field.masking_strategy = "none"
    pii_field.save(update_fields=["masking_strategy"])

    row = setup_schema["row"]
    table = setup_schema["table"]
    user = create_user("analyst2")
    create_scoped_role(user, "analysts_group")  # GLOBAL role, lacks catalog:view_pii
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")

    url = reverse("dataschema-row-detail", kwargs={"pk": row.id}) + f"?data_table={table.id}"
    resp = api_client.get(url)
    assert resp.status_code == 200
    assert resp.data["values"]["ssn"] == "123-45-6789"
