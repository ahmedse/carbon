"""AGS HTTP client unit tests (mocked network)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from gradevance.lti.ags import AgsPassbackError, AgsScore, build_ags_score_for_run
from gradevance.lti.ags_client import (
    ags_score_json,
    fetch_ags_access_token,
    post_ags_score,
    scores_url_for_lineitem,
)


def test_scores_url_for_lineitem():
    assert scores_url_for_lineitem("https://lms/li/1") == "https://lms/li/1/scores"
    assert scores_url_for_lineitem("https://lms/li/1/") == "https://lms/li/1/scores"


def test_ags_score_json_omits_null_given():
    s = AgsScore(
        user_id="u1",
        score_given=None,
        score_maximum=100.0,
        activity_progress="InProgress",
        grading_progress="NotReady",
        comment="adv",
    )
    body = ags_score_json(s)
    assert "scoreGiven" not in body
    assert body["comment"] == "adv"


@override_settings(GRADEVANCE_LTI_AGS_DRY_RUN=True)
def test_post_ags_dry_run():
    score = build_ags_score_for_run(
        lti_user_id="u1",
        mode="summative",
        released=True,
        advisory_bands={},
        mean_score_0_100=88.0,
    )
    result = post_ags_score(lineitem_url="https://lms.example/lineitems/9", score=score)
    assert result.dry_run is True
    assert result.ok is True
    assert result.url.endswith("/scores")
    assert result.body["would_post"]["scoreGiven"] == 88.0


@override_settings(
    GRADEVANCE_LTI_AGS_DRY_RUN=False,
    GRADEVANCE_LTI_TOKEN_URL="https://lms.example/token",
    GRADEVANCE_LTI_CLIENT_ID="cid",
    GRADEVANCE_LTI_CLIENT_SECRET="sec",
)
def test_post_ags_live_mocked():
    score = build_ags_score_for_run(
        lti_user_id="u1",
        mode="summative",
        released=True,
        advisory_bands={},
        mean_score_0_100=70.0,
    )
    token_resp = MagicMock(status_code=200)
    token_resp.json.return_value = {"access_token": "tok"}
    post_resp = MagicMock(status_code=204)
    post_resp.json.side_effect = ValueError("empty")
    post_resp.text = ""

    with patch("gradevance.lti.ags_client.requests.post") as mock_post:
        mock_post.side_effect = [token_resp, post_resp]
        result = post_ags_score(
            lineitem_url="https://lms.example/lineitems/9",
            score=score,
            dry_run=False,
        )
    assert result.ok is True
    assert result.status_code == 204
    assert mock_post.call_count == 2


@override_settings(
    GRADEVANCE_LTI_TOKEN_URL="",
    GRADEVANCE_LTI_CLIENT_ID="cid",
    GRADEVANCE_LTI_CLIENT_SECRET="sec",
)
def test_fetch_token_missing_url():
    with pytest.raises(AgsPassbackError, match="incomplete"):
        fetch_ags_access_token()
