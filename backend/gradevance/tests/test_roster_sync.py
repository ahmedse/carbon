import pytest

from gradevance.lti.roster_sync import sync_nrps_payload


@pytest.mark.django_db
def test_sync_nrps_payload_idempotent():
    payload = {
        "members": [
            {"user_id": "stu-1", "roles": ["Learner"], "name": "Pat", "status": "Active"},
            {"user_id": "tea-1", "roles": ["Instructor"], "status": "Active"},
        ]
    }
    a = sync_nrps_payload(iss="https://lms.example", deployment_id="dep1", payload=payload)
    b = sync_nrps_payload(iss="https://lms.example", deployment_id="dep1", payload=payload)
    assert a.created == 2
    assert b.created == 0
    assert b.existing == 2
    assert all(u.startswith("lti:") for u in a.usernames)
