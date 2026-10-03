"""External web / media acquisition tests — fixtures only, never live network.

The default fetch is monkeypatched to fail loudly, so no test can reach the
network. A saved HTML fixture and a saved media fixture stand in for the real
40 web links and 4 media rows, which stay unread until a staff Index job is
explicitly enabled with a named host allowlist.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[3]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from ai.content_engine import acquire  # noqa: E402
from ai.content_engine import ingest  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PAGE_URL = "https://lectures.example.org/page/keratinocyte.html"
MEDIA_URL = "https://lectures.example.org/media/lecture.mp4"
HOST = "lectures.example.org"


def _boom(*_args, **_kwargs):  # pragma: no cover - only trips on a real fetch
    raise AssertionError("test attempted a network fetch")


@pytest.fixture(autouse=True)
def _offline_and_clean_env(monkeypatch):
    monkeypatch.setattr(acquire.urllib.request, "urlopen", _boom)
    for var in (
        acquire.WEB_ENABLE_ENV,
        acquire.WEB_ALLOWED_HOSTS_ENV,
        acquire.WEB_TIMEOUT_ENV,
        acquire.WEB_MAX_BYTES_ENV,
        acquire.INBOX_ENV,
    ):
        monkeypatch.delenv(var, raising=False)
    yield


def _page_bytes() -> bytes:
    return (FIXTURES / "web_page.html").read_bytes()


def _media_bytes() -> bytes:
    return (FIXTURES / "media_clip.mp4").read_bytes()


# ── default OFF / Index-job gate ─────────────────────────────────────────────


def test_web_off_by_default_is_unavailable_without_network(tmp_path):
    job = acquire.web_acquire(
        PAGE_URL, trigger=acquire.INDEX_TRIGGER, allowed_hosts={HOST}, inbox=tmp_path
    )
    assert job["status"] == acquire.STATUS_UNAVAILABLE
    assert acquire.WEB_ENABLE_ENV in job["error"]
    assert job["local_path"] is None


def test_web_without_index_trigger_is_blocked(tmp_path):
    job = acquire.web_acquire(
        PAGE_URL, trigger=None, enabled=True, allowed_hosts={HOST}, inbox=tmp_path
    )
    assert job["status"] == acquire.STATUS_BLOCKED
    assert "chat_turn_forbidden" in job["error"]


def test_web_without_allowlist_is_blocked_even_when_enabled(tmp_path):
    job = acquire.web_acquire(
        PAGE_URL, trigger=acquire.INDEX_TRIGGER, enabled=True, allowed_hosts=set(), inbox=tmp_path
    )
    assert job["status"] == acquire.STATUS_BLOCKED
    assert "domain_not_allowed" in job["error"]


def test_web_non_http_scheme_is_blocked(tmp_path):
    job = acquire.web_acquire(
        "ftp://lectures.example.org/x.html",
        trigger=acquire.INDEX_TRIGGER,
        enabled=True,
        allowed_hosts={HOST},
        inbox=tmp_path,
    )
    assert job["status"] == acquire.STATUS_BLOCKED
    assert job["error"] == "not_http_url"


def test_web_allowlist_from_env_is_required(monkeypatch, tmp_path):
    monkeypatch.setenv(acquire.WEB_ALLOWED_HOSTS_ENV, HOST)
    spec = acquire.resolve_web_ref(PAGE_URL)
    assert spec["host"] == HOST
    monkeypatch.delenv(acquire.WEB_ALLOWED_HOSTS_ENV)
    with pytest.raises(acquire.WebRefError, match="domain_not_allowed"):
        acquire.resolve_web_ref(PAGE_URL)


# ── happy path with a saved fixture ──────────────────────────────────────────


def test_web_happy_path_captures_fixture_and_reader_yields_text(tmp_path):
    seen: dict = {}

    def fake_fetcher(url, *, timeout, max_bytes):
        seen.update(url=url, timeout=timeout, max_bytes=max_bytes)
        return ("ok", _page_bytes(), "text/html; charset=utf-8")

    job = acquire.web_acquire(
        PAGE_URL,
        trigger=acquire.INDEX_TRIGGER,
        enabled=True,
        allowed_hosts={HOST},
        fetcher=fake_fetcher,
        reader=ingest.read_path,
        inbox=tmp_path / "inbox",
        timeout=5,
        max_bytes=4096,
    )
    assert job["status"] == acquire.STATUS_OK
    assert job["mime"] == "text/html"
    dest = Path(job["local_path"])
    assert dest.suffix == ".html"
    assert dest.read_bytes() == _page_bytes()
    assert seen["timeout"] == 5 and seen["max_bytes"] == 4096
    body = ingest.units_text(job["reader_result"])
    assert "keratinocyte turnover sentence" in body.lower()
    assert "ignored title" not in body


def test_media_acquire_captures_bytes_without_transcriber(tmp_path):
    job = acquire.media_acquire(
        MEDIA_URL,
        trigger=acquire.INDEX_TRIGGER,
        enabled=True,
        allowed_hosts={HOST},
        fetcher=lambda *a, **k: ("ok", _media_bytes(), "video/mp4"),
        inbox=tmp_path / "inbox",
    )
    assert job["status"] == acquire.STATUS_OK
    assert Path(job["local_path"]).suffix == ".mp4"
    assert job["bytes"] == len(_media_bytes())
    # No local transcriber ships: the gap is explicit, never a fake transcript.
    assert "transcript" not in job


def test_media_transcriber_is_an_injected_seam(tmp_path):
    job = acquire.media_acquire(
        MEDIA_URL,
        trigger=acquire.INDEX_TRIGGER,
        enabled=True,
        allowed_hosts={HOST},
        fetcher=lambda *a, **k: ("ok", _media_bytes(), "video/mp4"),
        transcriber=lambda path, mime: "verbatim transcript fixture",
        inbox=tmp_path / "inbox",
    )
    assert job["status"] == acquire.STATUS_OK
    assert job["transcript"] == "verbatim transcript fixture"


# ── statuses / caps ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("fake", "expected"),
    [
        (("too_large", b"", "size_gt"), acquire.STATUS_TOO_LARGE),
        (("timeout", b"", "timeout"), acquire.STATUS_TIMEOUT),
        (("blocked", b"", "redirect_host_not_allowed:evil.example"), acquire.STATUS_BLOCKED),
        (("unavailable", b"", "http_404"), acquire.STATUS_UNAVAILABLE),
    ],
)
def test_web_fetcher_status_is_preserved(tmp_path, fake, expected):
    job = acquire.web_acquire(
        PAGE_URL,
        trigger=acquire.INDEX_TRIGGER,
        enabled=True,
        allowed_hosts={HOST},
        fetcher=lambda *a, **k: fake,
        inbox=tmp_path,
    )
    assert job["status"] == expected
    assert job["local_path"] is None


def test_web_enforces_size_cap_even_if_fetcher_ignores_it(tmp_path):
    job = acquire.web_acquire(
        PAGE_URL,
        trigger=acquire.INDEX_TRIGGER,
        enabled=True,
        allowed_hosts={HOST},
        fetcher=lambda *a, **k: ("ok", b"x" * 100, "text/html"),
        inbox=tmp_path,
        max_bytes=10,
    )
    assert job["status"] == acquire.STATUS_TOO_LARGE
    assert not list(tmp_path.glob("*.html"))


def test_web_timeout_exception_maps_to_timeout(tmp_path):
    def slow(*_a, **_k):
        import socket

        raise socket.timeout("too slow")

    job = acquire.web_acquire(
        PAGE_URL,
        trigger=acquire.INDEX_TRIGGER,
        enabled=True,
        allowed_hosts={HOST},
        fetcher=slow,
        inbox=tmp_path,
    )
    assert job["status"] == acquire.STATUS_TIMEOUT


# ── default fetch redirect guard (no real network) ────────────────────────────


def test_default_web_fetch_blocks_redirect_off_allowlist(monkeypatch):
    class _Resp(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def geturl(self):
            return "https://evil.example.org/moved.html"

        @property
        def headers(self):
            return {}

    monkeypatch.setattr(acquire.urllib.request, "urlopen", lambda *a, **k: _Resp(b"x"))
    status, body, detail = acquire._default_web_fetch(
        PAGE_URL, timeout=1, max_bytes=10, allowed_hosts={HOST}
    )
    assert status == acquire.STATUS_BLOCKED
    assert "redirect_host_not_allowed" in detail
    assert body == b""


# ── unified entry point ──────────────────────────────────────────────────────


def test_acquire_dispatches_http_to_web_and_stays_blocked_on_a_chat_turn(tmp_path):
    job = acquire.acquire(PAGE_URL, inbox=tmp_path, allowed_hosts={HOST})
    assert job["source"] == "web"
    assert job["status"] == acquire.STATUS_BLOCKED
    assert "chat_turn_forbidden" in job["error"]
