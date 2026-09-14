"""Regression tests for DT-BP-001.

The connection "Test" action must persist ``last_test_status`` as the literal
machine value ``'success'`` / ``'failure'`` (not a human message string) and
must always record ``last_tested_at``.
"""

import pytest
from unittest.mock import patch

from connections.models import DataSource
from connections.services import ConnectionService


@pytest.mark.django_db
def test_test_connection_success_persists_success():
    source = DataSource.objects.create(
        name="Testable", source_type="api", connection_config={"host": "x.com"}
    )

    payload, status_code = ConnectionService.test_connection(source)

    assert status_code == 200
    assert payload["status"] == "success"
    assert payload["message"] == "Connection test successful"
    assert payload["last_tested_at"] is not None

    source.refresh_from_db()
    assert source.last_test_status == "success"
    assert source.last_tested_at is not None
    assert source.status == "active"


@pytest.mark.django_db
def test_test_connection_failure_persists_failure():
    source = DataSource.objects.create(
        name="Failing", source_type="api", connection_config={"host": "x.com"}
    )

    # Force an exception on the first save only; the except-path save returns
    # normally so the payload tuple is still returned.
    with patch.object(source, "save", side_effect=[RuntimeError("boom"), None]):
        payload, status_code = ConnectionService.test_connection(source)

    assert status_code == 400
    assert payload["status"] == "failure"
    assert payload["last_tested_at"] is not None
    assert source.last_test_status == "failure"
    assert source.status == "error"
    assert source.last_tested_at is not None
