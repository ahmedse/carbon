"""A3: pack roster for a listed course. Off-list names are refused."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path

import pytest
import yaml
from django.test import override_settings
from rest_framework.test import APIClient

from ai.moodle_bank import course_roster

_GOLD = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold" / "a3-roster.yaml"
_SECRET = "a3-roster-hmac"
_ROSTER_URL = "/carbon-api/ai/moodle/roster/"


def _gold() -> dict:
    return yaml.safe_load(_GOLD.read_text(encoding="utf-8"))


def _signed(body: bytes) -> dict[str, str]:
    ts = str(int(time.time()))
    sig = hmac.new(_SECRET.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return {
        "HTTP_X_PULSE_TIMESTAMP": ts,
        "HTTP_X_PULSE_SIGNATURE": sig,
    }


def test_med520_roster_includes_alopecia_and_herpes():
    gold = _gold()
    result = course_roster(gold["course"])
    assert result["ok"] is True
    assert result["shortname"] == "MED520"
    by_cmid = {int(row["cmid"]): row for row in result["activities"]}
    for expected in gold["in_pack"]:
        row = by_cmid[int(expected["cmid"])]
        assert row["in_pack"] is True
        assert row["status"] == expected["status"]
        assert row["kind"] == expected["kind"]
        assert row["name"] == expected["name"]
        if expected.get("source"):
            assert row["source"] == expected["source"]
        assert "text" not in row
    assert 1111 in by_cmid
    assert 1112 in by_cmid
    assert 1127 in by_cmid


def test_off_list_shortname_is_rejected():
    gold = _gold()
    for shortname in gold["off_list"]:
        result = course_roster(shortname)
        assert result["ok"] is False, shortname
        assert result["error"] == "off_list", shortname
        assert result["activities"] == [], shortname
        assert result["shortname"] == shortname


@pytest.mark.django_db
@override_settings(MOODLE_PULSE_HMAC_SECRET=_SECRET)
def test_roster_http_med520_is_signed_staff_read():
    gold = _gold()
    body = json.dumps({"shortname": gold["course"]}).encode()
    client = APIClient()
    resp = client.generic("POST", _ROSTER_URL, body, content_type="application/json", **_signed(body))
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    by_cmid = {int(row["cmid"]): row for row in data["activities"]}
    assert 1111 in by_cmid
    assert 1127 in by_cmid
    assert 1128 in by_cmid
    assert by_cmid[1111]["in_pack"] is True
    assert by_cmid[1111]["source"] == "alopecia.pdf"
    assert "text" not in by_cmid[1111]


@pytest.mark.django_db
@override_settings(MOODLE_PULSE_HMAC_SECRET=_SECRET)
def test_roster_http_off_list_is_refused():
    body = json.dumps({"shortname": "NMD1601"}).encode()
    client = APIClient()
    resp = client.generic("POST", _ROSTER_URL, body, content_type="application/json", **_signed(body))
    assert resp.status_code == 404
    data = resp.json()
    assert data["ok"] is False
    assert data["error"] == "off_list"
    assert data["activities"] == []


@pytest.mark.django_db
@override_settings(MOODLE_PULSE_HMAC_SECRET=_SECRET)
def test_roster_http_rejects_unsigned():
    client = APIClient()
    resp = client.post(_ROSTER_URL, {"shortname": "MED520"}, format="json")
    assert resp.status_code == 401
    assert resp.json()["ok"] is False
