"""Article argumentative Semantics device is wired (no longer NAA pin)."""
from gradevance.services.packs import find_profile_file_for_id, load_profile


def test_article_profile_uses_article_device():
    loaded = load_profile(find_profile_file_for_id("article_generic_formative", 1))
    assert loaded.device is not None
    assert loaded.device.device["id"] == "article_argumentative_semantics"
    assert len(loaded.device.anchors) >= 3
