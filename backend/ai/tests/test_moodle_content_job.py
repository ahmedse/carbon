"""Staff Index-job wiring: readers for extra files, chunk index, graph, Drive.

Locks the additive Index-job behavior: extra uploads read through the shared
content-engine registry, the chunk index and passage-grounded graph persisted to
caller-supplied roots, and Drive default-OFF with a recorded per-source status.
A plain Index call (no build flag) writes no pack artifacts.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

_SECRET = "content-job-hmac"
_INDEX_URL = "/carbon-api/ai/moodle/index/"


def _signed(body: bytes) -> dict[str, str]:
    ts = str(int(time.time()))
    sig = hmac.new(_SECRET.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return {"HTTP_X_PULSE_TIMESTAMP": ts, "HTTP_X_PULSE_SIGNATURE": sig}


@pytest.mark.django_db
@override_settings(MOODLE_PULSE_HMAC_SECRET=_SECRET)
def test_index_job_builds_chunk_index_and_graph(tmp_path, monkeypatch):
    monkeypatch.setattr("ai.moodle_content_job._INDEX_ROOT", tmp_path / "index")
    monkeypatch.setattr("ai.moodle_content_job._GRAPH_ROOT", tmp_path / "graph")
    body = json.dumps({"shortname": "MED520", "extras": [], "build": ["index", "graph"]}).encode()
    client = APIClient()
    resp = client.generic("POST", _INDEX_URL, body, content_type="application/json", **_signed(body))
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["index"]["chunks"] > 0
    assert data["index"]["keyword"] is True
    assert data["index"]["semantic_status"] == "default_off"
    assert data["graph"]["nodes"] > 0
    assert data["graph"]["edges"] > 0
    assert (tmp_path / "index" / "MED520.jsonl").is_file()
    assert (tmp_path / "graph" / "MED520.jsonl").is_file()

    from ai.content_engine import graph as ce_graph

    graph = ce_graph.Graph.load(tmp_path / "graph" / "MED520.jsonl")
    assert all(edge.provenance for edge in graph.edges.values())


@pytest.mark.django_db
@override_settings(MOODLE_PULSE_HMAC_SECRET=_SECRET)
def test_index_job_reads_extra_files_through_the_engine(tmp_path, monkeypatch):
    monkeypatch.setattr("ai.moodle_bank._EXTRA", tmp_path)
    content = base64.b64encode(b"AASTMT Pulse extra file for MED520 tutor notes only.").decode()
    body = json.dumps(
        {"shortname": "MED520", "files": [{"itemid": 21, "filename": "note.md", "content": content}]}
    ).encode()
    client = APIClient()
    resp = client.generic("POST", _INDEX_URL, body, content_type="application/json", **_signed(body))
    assert resp.status_code == 200
    data = resp.json()
    assert data["indexed"] == 1
    assert data["extra_source"] == "readers"
    from ai.moodle_bank import load_extra

    bank = load_extra("MED520", extra_root=tmp_path)
    assert "MED520:extra:21:note.md" in bank
    assert bank["MED520:extra:21:note.md"]["source"] == "extra:note.md"


@pytest.mark.django_db
@override_settings(MOODLE_PULSE_HMAC_SECRET=_SECRET)
def test_index_job_drive_is_default_off_and_recorded(tmp_path, monkeypatch):
    ext = tmp_path / "ext"
    ext.mkdir()
    (ext / "MED520.jsonl").write_text(
        json.dumps(
            {
                "course": "MED520",
                "family": "google",
                "source_kind": "google-presentation",
                "source_id": "AbCdEfGhIjKlMnOpQrSt",
                "cmid": 301,
                "status": "empty",
                "name": "deck",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("ai.moodle_bank._EXT", ext)
    monkeypatch.delenv("PULSE_CONTENT_DRIVE_ENABLED", raising=False)
    monkeypatch.delenv("PULSE_CONTENT_DRIVE_CREDENTIALS", raising=False)
    body = json.dumps({"shortname": "MED520", "drive": True}).encode()
    client = APIClient()
    resp = client.generic("POST", _INDEX_URL, body, content_type="application/json", **_signed(body))
    assert resp.status_code == 200
    data = resp.json()
    assert data["drive"]
    assert data["drive"][0]["status"] == "unavailable"
    assert "PULSE_CONTENT_DRIVE_ENABLED" in (data["drive"][0]["error"] or "")
    assert data["skipped"] == ["youtube"]


@pytest.mark.django_db
@override_settings(MOODLE_PULSE_HMAC_SECRET=_SECRET)
def test_plain_index_call_writes_no_pack_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr("ai.moodle_bank._EXTRA", tmp_path)
    body = json.dumps(
        {
            "shortname": "MED520",
            "extras": [
                {
                    "itemid": 7,
                    "filename": "t.md",
                    "title": "t",
                    "sectionnum": -1,
                    "passages": [{"text": "AASTMT Pulse extra file for MED520 tutor notes only."}],
                }
            ],
        }
    ).encode()
    client = APIClient()
    resp = client.generic("POST", _INDEX_URL, body, content_type="application/json", **_signed(body))
    assert resp.status_code == 200
    data = resp.json()
    assert data["indexed"] == 1
    assert "index" not in data and "graph" not in data
    assert data["skipped"] == ["drive", "youtube"]
