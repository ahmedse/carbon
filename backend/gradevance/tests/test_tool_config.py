from django.test import override_settings
from rest_framework.test import APIRequestFactory

from gradevance.lti.tool_config import LtiToolConfigView


@override_settings(GRADEVANCE_LTI_ENABLED=False)
def test_tool_config_public():
    factory = APIRequestFactory()
    resp = LtiToolConfigView.as_view()(factory.get("/lti/tool-config/"))
    assert resp.status_code == 200
    assert resp.data["client_name"] == "GradeVance"
    assert "initiate_login_uri" in resp.data
    assert resp.data["ready"] is False
