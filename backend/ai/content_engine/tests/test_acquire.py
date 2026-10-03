"""Acquisition tests — offline by construction.

Every test stubs the fetcher seam (``_default_fetch`` is monkeypatched to fail
loudly), so nothing here can reach the network. The four contract rules the
task names are covered explicitly:

* no turn path imports ``acquire.py``;
* with no credentials, Drive acquisition is ``unavailable`` and touches no network;
* the local drag path works offline, including ``.txt`` / ``.md`` / ``.json``;
* the domain allowlist rejects a non-Google host.
"""
from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

# ``ai`` is a package rooted at ``backend``; make it importable however pytest
# collects this file.
BACKEND = Path(__file__).resolve().parents[3]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from ai.content_engine import acquire  # noqa: E402

FILE_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz01234"
DRIVE_REF = f"google-presentation:{FILE_ID}"


def _boom(*_args, **_kwargs):  # pragma: no cover - only trips on a real fetch
    raise AssertionError("test attempted a network fetch")


@pytest.fixture(autouse=True)
def _offline_and_clean_env(monkeypatch):
    """Fail the test if anything reaches the default network fetcher, and clear
    Drive/inbox env so behavior is deterministic."""
    monkeypatch.setattr(acquire, "_default_fetch", _boom)
    for var in (
        acquire.ENABLE_ENV,
        acquire.CREDENTIALS_ENV,
        acquire.INBOX_ENV,
        acquire.TIMEOUT_ENV,
        acquire.MAX_BYTES_ENV,
    ):
        monkeypatch.delenv(var, raising=False)
    yield


# ── Rule (a): no turn path imports acquire.py ────────────────────────────────


def test_no_turn_path_imports_acquire():
    engine_root = BACKEND / "ai" / "engine"
    offenders = [
        path.relative_to(BACKEND).as_posix()
        for path in sorted(engine_root.rglob("*.py"))
        if "content_engine" in path.read_text(encoding="utf-8", errors="ignore")
    ]
    assert offenders == [], f"turn path imports content_engine: {offenders}"


def test_module_never_executes_or_renders():
    source = (BACKEND / "ai" / "content_engine" / "acquire.py").read_text(encoding="utf-8")
    for forbidden in ("subprocess", "os.system", "os.exec", "__import__", "eval(", "exec("):
        assert forbidden not in source, f"acquire.py contains forbidden token: {forbidden}"


# ── Rule (c): local drag path works offline ──────────────────────────────────


def test_local_acquire_copies_into_inbox_offline(tmp_path):
    src = tmp_path / "drop" / "lecture.md"
    src.parent.mkdir()
    src.write_text("# Lecture\n\nbody", encoding="utf-8")

    job = acquire.local_acquire(src, inbox=tmp_path / "inbox")

    assert job["status"] == acquire.STATUS_OK
    assert job["source"] == "local"
    assert job["mime"] == "text/markdown"
    assert job["error"] is None
    assert set(job) >= {
        "job_id",
        "source",
        "ref",
        "local_path",
        "mime",
        "status",
        "error",
    }
    assert job["path"] == job["local_path"]
    dest = Path(job["local_path"])
    assert dest.parent == tmp_path / "inbox"
    assert dest.read_text(encoding="utf-8") == "# Lecture\n\nbody"
    assert dest != src


@pytest.mark.parametrize(
    ("name", "mime"),
    [("a.txt", "text/plain"), ("b.md", "text/markdown"), ("c.json", "application/json")],
)
def test_local_acquire_course_content_mimes(tmp_path, name, mime):
    src = tmp_path / name
    src.write_text("{}" if name.endswith(".json") else "x", encoding="utf-8")
    job = acquire.local_acquire(src, inbox=tmp_path / "inbox")
    assert job["status"] == acquire.STATUS_OK
    assert job["mime"] == mime


def test_local_acquire_missing_file_is_unavailable(tmp_path):
    job = acquire.local_acquire(tmp_path / "nope.txt", inbox=tmp_path / "inbox")
    assert job["status"] == acquire.STATUS_UNAVAILABLE
    assert job["error"] == "no_such_file"


def test_local_acquire_unsafe_dest_name_is_blocked(tmp_path):
    src = tmp_path / "ok.txt"
    src.write_text("x", encoding="utf-8")
    job = acquire.local_acquire(src, inbox=tmp_path / "inbox", dest_name="../escape.txt")
    assert job["status"] == acquire.STATUS_BLOCKED
    assert job["error"] == "unsafe_dest_name"


def test_local_acquire_file_already_in_inbox_is_kept_in_place(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    src = inbox / "already.md"
    src.write_text("hi", encoding="utf-8")
    job = acquire.local_acquire(src, inbox=inbox)
    assert job["status"] == acquire.STATUS_OK
    assert Path(job["local_path"]) == src.resolve()


def test_acquire_dispatches_local_path_offline(tmp_path):
    src = tmp_path / "notes.txt"
    src.write_text("hi", encoding="utf-8")
    job = acquire.acquire(str(src), inbox=tmp_path / "inbox")
    assert job["status"] == acquire.STATUS_OK
    assert job["source"] == "local"


# ── Rule (b): Drive default OFF / no credentials => unavailable, no network ──


def test_drive_off_by_default_is_unavailable_without_network(tmp_path):
    job = acquire.drive_acquire(
        DRIVE_REF, trigger=acquire.INDEX_TRIGGER, inbox=tmp_path
    )
    assert job["status"] == acquire.STATUS_UNAVAILABLE
    assert acquire.ENABLE_ENV in job["error"]
    assert job["local_path"] is None


def test_drive_enabled_but_missing_credentials_is_unavailable(tmp_path):
    job = acquire.drive_acquire(
        DRIVE_REF, trigger=acquire.INDEX_TRIGGER, enabled=True, inbox=tmp_path
    )
    assert job["status"] == acquire.STATUS_UNAVAILABLE
    assert acquire.CREDENTIALS_ENV in job["error"]
    assert job["local_path"] is None


def test_drive_without_credentials_never_calls_fetcher(tmp_path):
    calls: list[tuple] = []

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return ("ok", b"body", "text/plain")

    job = acquire.drive_acquire(
        DRIVE_REF,
        trigger=acquire.INDEX_TRIGGER,
        enabled=True,
        credentials=None,
        fetcher=spy,
        inbox=tmp_path,
    )
    assert job["status"] == acquire.STATUS_UNAVAILABLE
    assert calls == []


def test_drive_chat_turn_is_blocked_without_network(tmp_path):
    job = acquire.drive_acquire(
        DRIVE_REF, trigger=None, enabled=True, credentials="creds.json", inbox=tmp_path
    )
    assert job["status"] == acquire.STATUS_BLOCKED
    assert "chat_turn_forbidden" in job["error"]


def test_acquire_dispatches_drive_but_stays_blocked_on_a_chat_turn(tmp_path):
    job = acquire.acquire(f"google-file:{FILE_ID}", inbox=tmp_path)
    assert job["status"] == acquire.STATUS_BLOCKED
    assert "chat_turn_forbidden" in job["error"]


# ── Rule (d): domain allowlist ───────────────────────────────────────────────


def test_allowlist_rejects_non_google_domain(tmp_path):
    with pytest.raises(acquire.DriveRefError, match="domain_not_allowed"):
        acquire.resolve_drive_ref(f"https://evil.example.com/file/d/{FILE_ID}/view")

    job = acquire.drive_acquire(
        f"https://evil.example.com/file/d/{FILE_ID}/view",
        trigger=acquire.INDEX_TRIGGER,
        enabled=True,
        credentials="creds.json",
        inbox=tmp_path,
    )
    assert job["status"] == acquire.STATUS_BLOCKED
    assert "domain_not_allowed" in job["error"]


def test_allowlist_lookalike_host_is_rejected():
    with pytest.raises(acquire.DriveRefError):
        acquire.resolve_drive_ref(f"https://docs.google.com.evil.example/d/{FILE_ID}")


def test_unknown_scheme_ref_is_blocked(tmp_path):
    job = acquire.drive_acquire(
        "ftp://drive.google.com/thing", trigger=acquire.INDEX_TRIGGER, inbox=tmp_path
    )
    assert job["status"] == acquire.STATUS_BLOCKED


# ── Ref → export mime mapping ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("ref", "kind", "mime", "url_fragment"),
    [
        (f"google-presentation:{FILE_ID}", "google-presentation", acquire.PPTX_MIME, "/export/pptx"),
        (f"google-document:{FILE_ID}", "google-document", acquire.DOCX_MIME, "format=docx"),
        (f"google-file:{FILE_ID}", "google-file", None, "drive.google.com/uc?export=download"),
        (
            f"https://docs.google.com/presentation/d/{FILE_ID}/edit",
            "google-presentation",
            acquire.PPTX_MIME,
            "/export/pptx",
        ),
        (
            f"https://docs.google.com/document/d/{FILE_ID}/edit",
            "google-document",
            acquire.DOCX_MIME,
            "format=docx",
        ),
        (
            f"https://drive.google.com/file/d/{FILE_ID}/view",
            "google-file",
            None,
            "drive.google.com/uc?export=download",
        ),
        (
            f"link:docs.google.com/document/d/{FILE_ID}/edit",
            "google-document",
            acquire.DOCX_MIME,
            "format=docx",
        ),
    ],
)
def test_resolve_ref_maps_kind_mime_and_url(ref, kind, mime, url_fragment):
    spec = acquire.resolve_drive_ref(ref)
    assert spec.kind == kind
    assert spec.export_mime == mime
    assert url_fragment in spec.download_url


# ── Drive happy path and failure statuses (fetcher injected, no real network) ─


def test_drive_happy_path_writes_bytes(tmp_path):
    seen: dict = {}

    def fake_fetcher(url, *, timeout, max_bytes):
        seen.update(url=url, timeout=timeout, max_bytes=max_bytes)
        return ("ok", b"PK\x03\x04slide-bytes", acquire.PPTX_MIME)

    job = acquire.drive_acquire(
        DRIVE_REF,
        trigger=acquire.INDEX_TRIGGER,
        enabled=True,
        credentials="creds.json",
        fetcher=fake_fetcher,
        inbox=tmp_path / "inbox",
        timeout=5,
        max_bytes=1024,
    )
    assert job["status"] == acquire.STATUS_OK
    assert job["mime"] == acquire.PPTX_MIME
    dest = Path(job["local_path"])
    assert dest.suffix == ".pptx"
    assert dest.read_bytes() == b"PK\x03\x04slide-bytes"
    assert acquire.DRIVE_ALLOWED_HOSTS and "docs.google.com" in seen["url"]
    assert seen["timeout"] == 5 and seen["max_bytes"] == 1024


@pytest.mark.parametrize(
    ("fake", "expected"),
    [
        (("too_large", b"", "size_gt"), acquire.STATUS_TOO_LARGE),
        (("timeout", b"", "timeout"), acquire.STATUS_TIMEOUT),
        (("blocked", b"", "redirect_host_not_allowed:accounts.google.com"), acquire.STATUS_BLOCKED),
        (("unavailable", b"", "http_404"), acquire.STATUS_UNAVAILABLE),
    ],
)
def test_drive_fetcher_status_is_preserved(tmp_path, fake, expected):
    job = acquire.drive_acquire(
        DRIVE_REF,
        trigger=acquire.INDEX_TRIGGER,
        enabled=True,
        credentials="creds.json",
        fetcher=lambda *a, **k: fake,
        inbox=tmp_path,
    )
    assert job["status"] == expected
    assert job["local_path"] is None


def test_drive_enforces_size_cap_even_if_fetcher_ignores_it(tmp_path):
    def ignoring_fetcher(*_a, **_k):
        return ("ok", b"x" * 100, "text/plain")

    job = acquire.drive_acquire(
        DRIVE_REF,
        trigger=acquire.INDEX_TRIGGER,
        enabled=True,
        credentials="creds.json",
        fetcher=ignoring_fetcher,
        inbox=tmp_path,
        max_bytes=10,
    )
    assert job["status"] == acquire.STATUS_TOO_LARGE
    assert not list(tmp_path.glob("*.pptx"))


def test_drive_timeout_exception_maps_to_timeout(tmp_path):
    def slow(*_a, **_k):
        raise socket.timeout("too slow")

    job = acquire.drive_acquire(
        DRIVE_REF,
        trigger=acquire.INDEX_TRIGGER,
        enabled=True,
        credentials="creds.json",
        fetcher=slow,
        inbox=tmp_path,
    )
    assert job["status"] == acquire.STATUS_TIMEOUT


# ── Optional injected reader ─────────────────────────────────────────────────


def test_injected_reader_receives_path_and_mime(tmp_path):
    src = tmp_path / "course.json"
    src.write_text('{"k": 1}', encoding="utf-8")
    seen: dict = {}

    def reader(path, mime):
        seen.update(path=path, mime=mime)
        return {"reader": "fake", "path": path, "mime": mime}

    job = acquire.local_acquire(src, inbox=tmp_path / "inbox", reader=reader)
    assert job["status"] == acquire.STATUS_OK
    assert seen["path"] == job["local_path"]
    assert seen["mime"] == "application/json"
    assert job["reader_result"]["reader"] == "fake"


def test_reader_failure_does_not_fail_acquisition(tmp_path):
    src = tmp_path / "x.txt"
    src.write_text("x", encoding="utf-8")

    def bad_reader(_path, _mime):
        raise RuntimeError("reader exploded")

    job = acquire.local_acquire(src, inbox=tmp_path / "inbox", reader=bad_reader)
    assert job["status"] == acquire.STATUS_OK
    assert "reader exploded" in job["reader_error"]


def test_all_statuses_are_in_the_declared_set(tmp_path):
    assert acquire.STATUS_OK in acquire.STATUSES
    assert acquire.STATUS_UNAVAILABLE in acquire.STATUSES
    assert acquire.STATUS_TOO_LARGE in acquire.STATUSES
    assert acquire.STATUS_TIMEOUT in acquire.STATUSES
    assert acquire.STATUS_BLOCKED in acquire.STATUSES
