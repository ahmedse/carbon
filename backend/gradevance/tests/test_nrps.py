from gradevance.lti.nrps import NrpsMember, fetch_nrps_membership, parse_nrps_membership_page
from django.test import override_settings


def test_parse_nrps_membership():
    members = parse_nrps_membership_page(
        {
            "members": [
                {
                    "user_id": "u1",
                    "roles": ["Learner"],
                    "name": "Ada",
                    "email": "a@ex.com",
                    "status": "Active",
                },
                {"userId": "u2", "roles": "Instructor"},
                {"roles": ["Learner"]},  # skipped — no id
            ]
        }
    )
    assert len(members) == 2
    assert members[0] == NrpsMember(
        user_id="u1",
        roles=("Learner",),
        name="Ada",
        email="a@ex.com",
        status="Active",
    )
    assert members[1].user_id == "u2"
    assert members[1].roles == ("Instructor",)


@override_settings(GRADEVANCE_LTI_AGS_DRY_RUN=True)
def test_nrps_fetch_dry_run():
    result = fetch_nrps_membership(memberships_url="https://lms.example/nrps/1")
    assert result.dry_run is True
    assert result.ok is True
    assert result.members == []
