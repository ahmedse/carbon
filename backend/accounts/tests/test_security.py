"""
E1-T5 — Security regression tests.
Covers: connections config masking (GET never leaks secrets, POST stores,
PATCH preserves masked), token isolation, user detail isolation.
"""

import pytest
from django.urls import reverse
from connections.models import DataSource
from connections.services import MASK_VALUE


# ── Connections masking ──────────────────────────────────────────────────

@pytest.mark.django_db
def test_datasource_get_never_leaks_stored_secrets(api_client, create_user,
                                                    get_token_for_user):
    """GET /connections/sources/ — connection_config values must be MASK_VALUE,
    never the real stored secrets."""
    admin = create_user("conn_admin", is_superuser=True)
    token = get_token_for_user(admin)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    source = DataSource.objects.create(
        name="Secret DB", slug="secret-db", source_type="database",
        connection_config={"host": "db.internal", "password": "real-pw-123", "port": 5432},
    )

    url = reverse("datasource-detail", args=[source.id])
    resp = api_client.get(url)
    assert resp.status_code == 200, resp.content[:200]

    config = resp.data["connection_config"]
    # Every value must be MASK_VALUE — never the real secret
    assert config["host"] == MASK_VALUE
    assert config["password"] == MASK_VALUE
    assert config["port"] == MASK_VALUE
    assert "real-pw-123" not in str(resp.content)


@pytest.mark.django_db
def test_datasource_list_never_leaks_secrets(api_client, create_user,
                                              get_token_for_user):
    """GET /connections/sources/ (list) — every source's config is masked."""
    admin = create_user("conn_admin", is_superuser=True)
    token = get_token_for_user(admin)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    DataSource.objects.create(
        name="SrcA", slug="src-a", source_type="api",
        connection_config={"api_key": "sk-live-abc123", "endpoint": "/v2/data"},
    )
    DataSource.objects.create(
        name="SrcB", slug="src-b", source_type="database",
        connection_config={"host": "10.0.0.1", "password": "db-pass"},
    )

    resp = api_client.get(reverse("datasource-list"))
    assert resp.status_code == 200
    for item in resp.data:
        for val in item["connection_config"].values():
            assert val == MASK_VALUE, f"Found unmasked value: {val}"


@pytest.mark.django_db
def test_datasource_post_stores_real_config(api_client, create_user,
                                             get_token_for_user):
    """POST /connections/sources/ — real config is stored, response is masked."""
    admin = create_user("conn_admin", is_superuser=True)
    token = get_token_for_user(admin)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    resp = api_client.post(reverse("datasource-list"), {
        "name": "New Source", "source_type": "api",
        "connection_config": {"api_key": "sk-secret-999", "region": "us-east-1"},
    }, format="json")
    assert resp.status_code == 201, resp.content[:200]

    # Response must be masked
    cfg = resp.data["connection_config"]
    assert cfg["api_key"] == MASK_VALUE
    assert cfg["region"] == MASK_VALUE

    # DB must hold the real values
    obj = DataSource.objects.get(id=resp.data["id"])
    assert obj.connection_config["api_key"] == "sk-secret-999"
    assert obj.connection_config["region"] == "us-east-1"


@pytest.mark.django_db
def test_datasource_patch_masked_preserves_stored_secret(api_client,
                                                          create_user,
                                                          get_token_for_user):
    """PATCH with MASK_VALUE placeholders must NOT overwrite stored secrets
    with literal '***'. The serializer merges masked entries into the stored
    config rather than replacing them."""
    admin = create_user("conn_admin", is_superuser=True)
    token = get_token_for_user(admin)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    source = DataSource.objects.create(
        name="PatchTest", slug="patch-test", source_type="database",
        connection_config={"host": "db.internal", "password": "real-pw-xyz"},
    )

    # PATCH sending only a MASK_VALUE placeholder for password —
    # should keep the stored secret, not overwrite with literal "***"
    resp = api_client.patch(
        reverse("datasource-detail", args=[source.id]),
        {"connection_config": {"password": MASK_VALUE}}, format="json",
    )
    assert resp.status_code == 200, resp.content[:200]

    source.refresh_from_db()
    assert source.connection_config["password"] == "real-pw-xyz", \
        f"Secret was overwritten: {source.connection_config['password']}"

    # host was not mentioned in PATCH — should still be intact
    assert source.connection_config["host"] == "db.internal"


@pytest.mark.django_db
def test_datasource_patch_partial_update_changes_specified_only(api_client,
                                                                 create_user,
                                                                 get_token_for_user):
    """PATCH with real new values updates only the specified keys."""
    admin = create_user("conn_admin", is_superuser=True)
    token = get_token_for_user(admin)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    source = DataSource.objects.create(
        name="PartialTest", slug="partial-test", source_type="database",
        connection_config={"host": "old-host", "password": "old-pw", "db": "old-db"},
    )

    resp = api_client.patch(
        reverse("datasource-detail", args=[source.id]),
        {"connection_config": {"host": "new-host"}}, format="json",
    )
    assert resp.status_code == 200

    source.refresh_from_db()
    assert source.connection_config["host"] == "new-host"
    assert source.connection_config["password"] == "old-pw"  # unchanged
    assert source.connection_config["db"] == "old-db"         # unchanged


# ── Token & user isolation ────────────────────────────────────────────

@pytest.mark.django_db
def test_user_cannot_access_token_of_another_user(api_client, create_user,
                                                   get_token_for_user):
    """User A's token cannot be used to access User B's detail."""
    user1 = create_user("alice")
    user2 = create_user("bob")
    token = get_token_for_user(user1)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    resp = api_client.get(reverse("user-detail", args=[user2.id]))
    assert resp.status_code in [403, 404]