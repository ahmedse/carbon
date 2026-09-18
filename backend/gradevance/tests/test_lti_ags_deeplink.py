from gradevance.lti.ags import AgsPassbackError, build_ags_score_for_run
from gradevance.lti.deep_link import deep_link_assignment_content_item, deep_link_jwt_claims
import pytest


def test_ags_summative_requires_release():
    with pytest.raises(AgsPassbackError):
        build_ags_score_for_run(
            lti_user_id="u1",
            mode="summative",
            released=False,
            advisory_bands={"task_achievement": "B"},
            mean_score_0_100=80.0,
        )


def test_ags_formative_advisory_no_score():
    score = build_ags_score_for_run(
        lti_user_id="u1",
        mode="formative",
        released=False,
        advisory_bands={"task_achievement": "B"},
        mean_score_0_100=80.0,
    )
    assert score.score_given is None
    assert score.grading_progress == "NotReady"
    assert "task_achievement=B" in score.comment


def test_ags_summative_released():
    score = build_ags_score_for_run(
        lti_user_id="u1",
        mode="summative",
        released=True,
        advisory_bands={},
        mean_score_0_100=72.5,
    )
    assert score.score_given == 72.5
    assert score.grading_progress == "FullyGraded"


def test_deep_link_content_item():
    item = deep_link_assignment_content_item(
        title="NAA reflection",
        url="https://eduos.example/apps/gradevance/student",
        assignment_id="a1",
        profile_pack_id="naa_cycle1_exam_prep",
    )
    assert item["type"] == "ltiResourceLink"
    claims = deep_link_jwt_claims(
        iss="https://eduos.example",
        aud="https://lms.example",
        deployment_id="dep1",
        data="opaque",
        content_items=[item],
    )
    assert claims["https://purl.imsglobal.org/spec/lti/claim/message_type"] == "LtiDeepLinkingResponse"
