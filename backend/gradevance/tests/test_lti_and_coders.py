from gradevance.lti import ags_passback_allowed, map_lti_roles_to_capabilities
from gradevance.services.coders import get_coder, list_coders


def test_lti_role_map_instructor():
    caps = map_lti_roles_to_capabilities(("http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor",))
    assert "gradevance:manage" in caps
    assert "gradevance:mark" in caps


def test_ags_summative_requires_release():
    assert ags_passback_allowed(released=False, mode="summative") is False
    assert ags_passback_allowed(released=True, mode="summative") is True


def test_coder_registry_has_heuristic():
    assert "heuristic_anchor" in list_coders()
    fn = get_coder("heuristic_anchor")
    assert callable(fn)


def test_gold_oracle_registered():
    from gradevance.services import gold_oracle  # noqa: F401

    assert "gold_oracle" in list_coders()
