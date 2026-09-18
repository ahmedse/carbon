import pytest

from gradevance.lti import LtiLaunchContext
from gradevance.lti.provision import provision_user_from_launch


@pytest.mark.django_db
def test_provision_instructor_idempotent():
    ctx = LtiLaunchContext(
        iss="https://lms.example",
        sub="abc123",
        deployment_id="dep1",
        roles=("http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor",),
    )
    a = provision_user_from_launch(ctx, email="t@example.com", name="Ada Lovelace")
    b = provision_user_from_launch(ctx, email="t@example.com", name="Ada Lovelace")
    assert a.created is True
    assert b.created is False
    assert a.user_id == b.user_id
    assert a.username.startswith("lti:")
    assert "gradevance_lead" in a.groups
    assert "gradevance:manage" in a.capabilities


@pytest.mark.django_db
def test_provision_learner():
    ctx = LtiLaunchContext(
        iss="https://lms.example",
        sub="stu-9",
        deployment_id="dep1",
        roles=("Learner",),
    )
    r = provision_user_from_launch(ctx)
    assert "gradevance_students" in r.groups
    assert "gradevance:submit" in r.capabilities
