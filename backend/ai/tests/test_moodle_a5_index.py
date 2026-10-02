"""A5 index: extra JSONL only. Ask does not call Google."""
import ast
import hashlib
import hmac
import json
import time
from pathlib import Path

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from ai.moodle_bank import load_extra, write_extra_index
from ai.moodle_page import topic_answer
from ai.tests.test_moodle_topic import _MISS, _med520_home, _page

_SECRET = "a5-index-hmac"
_INDEX_URL = "/carbon-api/ai/moodle/index/"
_ASK_URL = "/carbon-api/ai/moodle/ask/"
_EXTRA_TEXT = "AASTMT Pulse extra file for MED520 tutor notes only."


def _signed(body: bytes) -> dict[str, str]:
    ts = str(int(time.time()))
    sig = hmac.new(_SECRET.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return {
        "HTTP_X_PULSE_TIMESTAMP": ts,
        "HTTP_X_PULSE_SIGNATURE": sig,
    }


def test_a5_index_button_does_not_call_google_from_ask():
    root = Path(__file__).resolve().parents[1]
    ask_src = (root / "moodle_host_api.py").read_text(encoding="utf-8")
    page_src = (root / "moodle_page.py").read_text(encoding="utf-8")
    bank_src = (root / "moodle_bank.py").read_text(encoding="utf-8")
    for src in (ask_src, page_src):
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "google" not in alias.name.lower()
                    assert "youtube" not in alias.name.lower()
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "google" not in node.module.lower()
                assert "urllib" not in node.module.lower()
    assert "googleapis" not in ask_src.lower()
    assert "www.googleapis.com" not in bank_src.lower()
    assert "/moodle/ask/" in _ASK_URL
    assert "/moodle/index/" in _INDEX_URL
    assert "google" not in _INDEX_URL


@pytest.mark.django_db
@override_settings(MOODLE_PULSE_HMAC_SECRET=_SECRET)
def test_a5_moodle_edit_not_live_until_index(tmp_path, monkeypatch):
    monkeypatch.setattr("ai.moodle_bank._EXTRA", tmp_path)
    snapshot = _page(_med520_home())
    assert topic_answer("educate me about aastmt pulse extra file", snapshot) == _MISS
    extras = [
        {
            "itemid": 7,
            "filename": "tutor-note.md",
            "title": "Tutor note",
            "sectionnum": -1,
            "passages": [{"text": _EXTRA_TEXT}],
        }
    ]
    body = json.dumps({"shortname": "MED520", "extras": extras, "skip_remote": ["drive", "youtube"]}).encode()
    client = APIClient()
    resp = client.generic("POST", _INDEX_URL, body, content_type="application/json", **_signed(body))
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["indexed"] == 1
    assert data["skipped"] == ["drive", "youtube"]
    bank = load_extra("MED520", extra_root=tmp_path)
    assert "MED520:extra:7:tutor-note.md" in bank
    got = topic_answer("educate me about aastmt pulse extra file", snapshot)
    assert "MED520:extra:7:tutor-note.md" in (got or "")
    assert write_extra_index("NMD1601", extras, extra_root=tmp_path) == 0
