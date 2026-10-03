"""Content-engine acquisition — get bytes onto local disk for a later reader.

Two acquisition paths, one job record:

* ``local``  — a file dragged/uploaded from the operator's machine. This is the
  primary path and it works with **zero network**.
* ``drive``  — a Google Drive / Docs / Slides item exported or downloaded into
  the inbox. This path is **default OFF**, requires explicit enablement plus
  credentials, and may only be called from a staff-triggered Index job — never
  from a Pulse Chat turn.

This module only *acquires bytes*. It never parses, renders, or executes what
it writes. Distillation ("read" + chunk) is a later stage that receives
``local_path`` and ``mime``; a reader may be injected as
``read_file(path, mime) -> ReaderResult`` and, when supplied, its result is
attached under ``job["reader_result"]``. No other worker's module is imported.

Drive refs reuse the bank id scheme from ``scripts/ingest_aast_med_external.py``
(``google-file:<id>``, ``google-presentation:<id>``, ``google-document:<id>``)
and the ``docs.google.com`` / ``drive.google.com`` share-link shapes. The
existing script fetchers return extracted *text*, not bytes; this module is the
bytes-to-disk seam. When a shared byte fetcher exists it can be passed in via
``fetcher=`` (``fetcher(url, *, timeout, max_bytes) -> (status, body, detail)``)
so the download logic is not forked.
"""
from __future__ import annotations

import os
import re
import shutil
import socket
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

# ── Status model ─────────────────────────────────────────────────────────────

STATUS_OK = "ok"
STATUS_UNAVAILABLE = "unavailable"
STATUS_TOO_LARGE = "too_large"
STATUS_TIMEOUT = "timeout"
STATUS_BLOCKED = "blocked"

#: The only statuses a job record may carry.
STATUSES = frozenset(
    {STATUS_OK, STATUS_UNAVAILABLE, STATUS_TOO_LARGE, STATUS_TIMEOUT, STATUS_BLOCKED}
)

#: Value the caller must pass as ``trigger`` for the Drive path to run. Only a
#: staff-triggered Index job sets this; a Chat turn never does.
INDEX_TRIGGER = "index_job"

# ── Configuration ────────────────────────────────────────────────────────────

ENABLE_ENV = "PULSE_CONTENT_DRIVE_ENABLED"
CREDENTIALS_ENV = "PULSE_CONTENT_DRIVE_CREDENTIALS"
INBOX_ENV = "PULSE_CONTENT_INBOX"
TIMEOUT_ENV = "PULSE_CONTENT_DRIVE_TIMEOUT_S"
MAX_BYTES_ENV = "PULSE_CONTENT_DRIVE_MAX_BYTES"

DEFAULT_TIMEOUT_S = 30.0
DEFAULT_MAX_BYTES = 25 * 1024 * 1024  # 25 MiB
_TRUTHY = frozenset({"1", "true", "yes", "on"})

#: Drive/Docs hosts a download URL is ever allowed to touch.
DRIVE_ALLOWED_HOSTS = frozenset({"docs.google.com", "drive.google.com"})

PPTX_MIME = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── Mime / ref helpers ───────────────────────────────────────────────────────

_MIME_BY_SUFFIX = {
    ".txt": "text/plain",
    ".text": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".json": "application/json",
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".html": "text/html",
    ".htm": "text/html",
    ".xml": "application/xml",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": DOCX_MIME,
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": PPTX_MIME,
    ".rtf": "application/rtf",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".odp": "application/vnd.oasis.opendocument.presentation",
}
_EXT_BY_MIME = {
    "text/plain": ".txt",
    "text/markdown": ".md",
    "application/json": ".json",
    "text/csv": ".csv",
    "text/html": ".html",
    "application/xml": ".xml",
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    DOCX_MIME: ".docx",
    "application/vnd.ms-powerpoint": ".ppt",
    PPTX_MIME: ".pptx",
}

# A Drive id is a long opaque token; the same shape the ingest script records.
_DRIVE_ID_RE = re.compile(r"[A-Za-z0-9_-]{16,}\Z")
_ID_IN_URL_RE = re.compile(r"/(?:file/)?d/([A-Za-z0-9_-]{16,})|[?&]id=([A-Za-z0-9_-]{16,})")
_PREFIX_RE = re.compile(r"\A(google-presentation|google-document|google-file):(.+)\Z")

FetchResult = tuple[str, bytes, str]


class DriveRefError(ValueError):
    """A ref that cannot be mapped to an allowlisted Drive download."""


@dataclass(frozen=True)
class DriveRef:
    """A resolved, allowlisted Drive download request."""

    kind: str  # google-presentation | google-document | google-file
    file_id: str
    ref: str  # normalized "kind:id"
    download_url: str
    export_mime: str | None  # None => take the response content-type
    extension: str


def guess_mime(path: str | os.PathLike[str]) -> str:
    """Best-effort mime from a filename suffix; neutral octet-stream otherwise."""
    return _MIME_BY_SUFFIX.get(Path(path).suffix.lower(), "application/octet-stream")


def _drive_enabled(explicit: bool | None = None) -> bool:
    if explicit is not None:
        return bool(explicit)
    return os.environ.get(ENABLE_ENV, "").strip().lower() in _TRUTHY


def _drive_credentials(explicit: str | None = None) -> str | None:
    """Return a non-empty credentials handle, or None (never anonymous)."""
    value = explicit if explicit is not None else os.environ.get(CREDENTIALS_ENV)
    value = (value or "").strip()
    return value or None


def _timeout(explicit: float | None = None) -> float:
    if explicit is not None:
        return float(explicit)
    raw = os.environ.get(TIMEOUT_ENV, "").strip()
    try:
        return float(raw) if raw else DEFAULT_TIMEOUT_S
    except ValueError:
        return DEFAULT_TIMEOUT_S


def _max_bytes(explicit: int | None = None) -> int:
    if explicit is not None:
        return int(explicit)
    raw = os.environ.get(MAX_BYTES_ENV, "").strip()
    try:
        return int(raw) if raw else DEFAULT_MAX_BYTES
    except ValueError:
        return DEFAULT_MAX_BYTES


def inbox_dir(explicit: str | os.PathLike[str] | None = None) -> Path:
    """The local drag-inbox directory (created on demand)."""
    if explicit is not None:
        return Path(explicit)
    override = os.environ.get(INBOX_ENV, "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / ".inbox"


# ── Job record ───────────────────────────────────────────────────────────────


def _new_job(source: str, ref: str) -> dict[str, Any]:
    return {
        "job_id": f"job-{uuid.uuid4().hex[:16]}",
        "source": source,
        "ref": ref,
        "local_path": None,
        "mime": None,
        "status": STATUS_UNAVAILABLE,
        "error": None,
    }


def _fail(job: dict[str, Any], status: str, error: str) -> dict[str, Any]:
    job["status"] = status
    job["error"] = error
    return job


def _maybe_read(job: dict[str, Any], reader: Callable[[str, str], Any] | None) -> None:
    """Hand the local path to an injected reader; never let it break acquisition."""
    if reader is None or job.get("status") != STATUS_OK:
        return
    try:
        job["reader_result"] = reader(job["local_path"], job["mime"])
    except Exception as exc:  # noqa: BLE001 — reader failure must not fail acquisition
        job["reader_error"] = f"{type(exc).__name__}: {exc}"


def _unique_dest(directory: Path, stem: str, ext: str, *, source: Path | None = None) -> Path:
    safe_stem = "".join(c for c in stem if c.isalnum() or c in "-_.") or "file"
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory / f"{safe_stem}{ext}"
    if source is not None and dest.exists() and dest.resolve() == source.resolve():
        return dest
    if dest.exists():
        dest = directory / f"{safe_stem}-{uuid.uuid4().hex[:8]}{ext}"
    return dest


# ── Local drag-inbox (primary, offline) ──────────────────────────────────────


def local_acquire(
    path: str | os.PathLike[str],
    *,
    inbox: str | os.PathLike[str] | None = None,
    copy: bool = True,
    dest_name: str | None = None,
    mime: str | None = None,
    ref: str | None = None,
    reader: Callable[[str, str], Any] | None = None,
) -> dict[str, Any]:
    """Take a locally dropped/uploaded file and record an acquisition job.

    Copies the file into the inbox (``copy=True`` by default) so the reader sees
    a stable path that later stages may move or delete. A file already inside
    the inbox is returned in place. No network is ever touched here.
    """
    src = Path(path).expanduser()
    try:
        src = src.resolve()
    except OSError:
        src = Path(path).expanduser()
    job = _new_job("local", ref or f"local:{src.name}")
    job["path"] = str(src)

    if not src.exists():
        return _fail(job, STATUS_UNAVAILABLE, "no_such_file")
    if not src.is_file():
        return _fail(job, STATUS_UNAVAILABLE, "not_a_file")

    directory = inbox_dir(inbox).expanduser()
    try:
        dest = src
        if not src.is_relative_to(directory.resolve()):
            name = dest_name or src.name
            if Path(name).name != name or name in {"", ".", ".."}:
                return _fail(job, STATUS_BLOCKED, "unsafe_dest_name")
            if copy:
                dest = _unique_dest(directory, Path(name).stem, Path(name).suffix, source=src)
                shutil.copy2(src, dest)
            else:
                dest = (directory / name).resolve()
    except OSError as exc:
        return _fail(job, STATUS_UNAVAILABLE, f"io:{type(exc).__name__}")

    job["local_path"] = str(dest)
    job["path"] = str(dest)
    job["mime"] = mime or guess_mime(dest)
    job["status"] = STATUS_OK
    _maybe_read(job, reader)
    return job


# ── Google Drive acquisition (default OFF, staff Index job only) ─────────────


def _drive_url(kind: str, file_id: str) -> str:
    if kind == "google-presentation":
        return f"https://docs.google.com/presentation/d/{file_id}/export/pptx"
    if kind == "google-document":
        return f"https://docs.google.com/document/d/{file_id}/export?format=docx"
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def _drive_ref(kind: str, file_id: str) -> DriveRef:
    if kind == "google-presentation":
        return DriveRef(kind, file_id, f"{kind}:{file_id}", _drive_url(kind, file_id), PPTX_MIME, ".pptx")
    if kind == "google-document":
        return DriveRef(kind, file_id, f"{kind}:{file_id}", _drive_url(kind, file_id), DOCX_MIME, ".docx")
    return DriveRef(kind, file_id, f"{kind}:{file_id}", _drive_url(kind, file_id), None, ".bin")


def resolve_drive_ref(ref: str) -> DriveRef:
    """Map a ``kind:id`` ref or a Google share URL to an allowlisted download.

    Raises :class:`DriveRefError` when the host is not allowlisted or no id is
    present. This is pure mapping — it never touches the network.
    """
    text = (ref or "").strip()
    if not text:
        raise DriveRefError("empty_ref")

    # 1. Explicit id scheme: google-presentation:<id> / google-document: / google-file:
    match = _PREFIX_RE.match(text)
    if match:
        kind, file_id = match.group(1), match.group(2)
        if not _DRIVE_ID_RE.match(file_id):
            raise DriveRefError("bad_drive_id")
        return _drive_ref(kind, file_id)

    # 2. The bank's ``link:`` wrapper over a docs.google.com share URL.
    if text.startswith("link:"):
        text = text[len("link:"):].strip()

    # 3. Share URL (scheme optional): host must be on the allowlist.
    if not text.lower().startswith(("http://", "https://")):
        if text.lower().startswith(("docs.google.com", "drive.google.com")):
            text = "https://" + text
        else:
            raise DriveRefError("unrecognized_ref")
    parsed = urlsplit(text)
    host = (parsed.hostname or "").lower()
    if host not in DRIVE_ALLOWED_HOSTS:
        raise DriveRefError(f"domain_not_allowed:{host or 'none'}")
    found = _ID_IN_URL_RE.search(f"{parsed.path}?{parsed.query}")
    if not found:
        raise DriveRefError("no_drive_id")
    file_id = next(g for g in found.groups() if g)
    path = parsed.path
    if "/presentation/d/" in path:
        kind = "google-presentation"
    elif "/document/d/" in path:
        kind = "google-document"
    else:
        kind = "google-file"
    return _drive_ref(kind, file_id)


def _default_fetch(
    url: str, *, timeout: float, max_bytes: int, headers: Mapping[str, str] | None = None
) -> FetchResult:
    """Minimal allowlisted GET. Never executed unless the Drive path is enabled."""
    request = urllib.request.Request(url, headers=dict(headers or _UA))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            final_host = (urlsplit(response.geturl()).hostname or "").lower()
            if final_host not in DRIVE_ALLOWED_HOSTS:
                return STATUS_BLOCKED, b"", f"redirect_host_not_allowed:{final_host or 'none'}"
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                return STATUS_TOO_LARGE, b"", f"size_gt:{max_bytes}"
            if response.status != 200:
                return STATUS_UNAVAILABLE, b"", f"http_{response.status}"
            ctype = (response.headers.get("content-type") or "").split(";")[0].strip()
            return STATUS_OK, body, ctype
    except urllib.error.HTTPError as exc:
        return STATUS_UNAVAILABLE, b"", f"http_{exc.code}"
    except (socket.timeout, TimeoutError):
        return STATUS_TIMEOUT, b"", "timeout"
    except (urllib.error.URLError, OSError) as exc:
        return STATUS_UNAVAILABLE, b"", f"network:{type(exc).__name__}"


def drive_acquire(
    ref: str,
    *,
    trigger: str | None = None,
    enabled: bool | None = None,
    credentials: str | None = None,
    fetcher: Callable[..., FetchResult] | None = None,
    inbox: str | os.PathLike[str] | None = None,
    timeout: float | None = None,
    max_bytes: int | None = None,
    reader: Callable[[str, str], Any] | None = None,
) -> dict[str, Any]:
    """Export/download an allowlisted Drive item into the inbox.

    Gate order — nothing past step 1 touches the network:

    1. resolve + allowlist the ref (blocked on a non-Google host or bad id);
    2. require ``trigger == INDEX_TRIGGER`` (a Chat turn is blocked);
    3. require explicit enablement (``PULSE_CONTENT_DRIVE_ENABLED``);
    4. require credentials (``PULSE_CONTENT_DRIVE_CREDENTIALS``);
    5. only then download, enforcing timeout, size cap and a redirect guard.

    With no credentials/enablement it returns ``unavailable`` naming the exact
    missing prerequisite and never attempts anonymous scraping.
    """
    job = _new_job("drive", str(ref or ""))
    try:
        spec = resolve_drive_ref(str(ref or ""))
    except DriveRefError as exc:
        return _fail(job, STATUS_BLOCKED, str(exc))
    job["ref"] = spec.ref
    job["mime"] = spec.export_mime or ""

    if trigger != INDEX_TRIGGER:
        return _fail(
            job,
            STATUS_BLOCKED,
            "chat_turn_forbidden: drive acquisition runs only from a staff Index job",
        )
    if not _drive_enabled(enabled):
        return _fail(
            job,
            STATUS_UNAVAILABLE,
            f"missing enablement: set {ENABLE_ENV}=1",
        )
    if not _drive_credentials(credentials):
        return _fail(
            job,
            STATUS_UNAVAILABLE,
            f"missing credentials: set {CREDENTIALS_ENV} to an OAuth client/service-account JSON",
        )

    cap = _max_bytes(max_bytes)
    fetch = fetcher or _default_fetch
    try:
        result = fetch(spec.download_url, timeout=_timeout(timeout), max_bytes=cap)
    except (socket.timeout, TimeoutError):
        return _fail(job, STATUS_TIMEOUT, "timeout")
    except Exception as exc:  # noqa: BLE001 — a bad fetcher must not crash the job
        return _fail(job, STATUS_UNAVAILABLE, f"fetch_error:{type(exc).__name__}")

    try:
        status, body, detail = result
    except (TypeError, ValueError):
        return _fail(job, STATUS_UNAVAILABLE, "bad_fetcher_result")

    if status == STATUS_OK:
        body = body or b""
        if len(body) > cap:
            return _fail(job, STATUS_TOO_LARGE, f"size_gt:{cap}")
        mime = spec.export_mime or (detail or "").split(";")[0].strip() or guess_mime(
            spec.file_id + spec.extension
        )
        ext = _EXT_BY_MIME.get(mime, spec.extension)
        dest = _unique_dest(inbox_dir(inbox).expanduser(), f"{spec.kind}-{spec.file_id}", ext)
        try:
            dest.write_bytes(body)
        except OSError as exc:
            return _fail(job, STATUS_UNAVAILABLE, f"io:{type(exc).__name__}")
        job["local_path"] = str(dest)
        job["mime"] = mime
        job["status"] = STATUS_OK
        _maybe_read(job, reader)
        return job

    normalized = status if status in STATUSES else STATUS_UNAVAILABLE
    return _fail(job, normalized, str(detail or status or "drive_error"))


# ── External web / media acquisition (default OFF, staff Index job only) ─────

#: Enablement + a mandatory host allowlist. The allowlist is empty by default,
#: so even with the switch on, no host is reachable until staff name one.
WEB_ENABLE_ENV = "PULSE_CONTENT_WEB_ENABLED"
WEB_ALLOWED_HOSTS_ENV = "PULSE_CONTENT_WEB_ALLOWED_HOSTS"
WEB_TIMEOUT_ENV = "PULSE_CONTENT_WEB_TIMEOUT_S"
WEB_MAX_BYTES_ENV = "PULSE_CONTENT_WEB_MAX_BYTES"

#: Media refs reuse the same bytes-to-disk capture; a transcript is a separate
#: injected seam (no local transcriber ships here).
MEDIA_SUFFIXES = frozenset({".mp4", ".mov", ".avi", ".mkv", ".webm"})


class WebRefError(ValueError):
    """A ref that cannot be mapped to an allowlisted external fetch."""


def _web_enabled(explicit: bool | None = None) -> bool:
    if explicit is not None:
        return bool(explicit)
    return os.environ.get(WEB_ENABLE_ENV, "").strip().lower() in _TRUTHY


def _web_allowed_hosts(explicit: Any = None) -> set[str]:
    """Host allowlist from an explicit iterable or the comma-separated env."""
    if explicit is not None:
        return {str(host).strip().lower() for host in explicit if str(host).strip()}
    raw = os.environ.get(WEB_ALLOWED_HOSTS_ENV, "")
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _web_timeout(explicit: float | None = None) -> float:
    if explicit is not None:
        return float(explicit)
    raw = os.environ.get(WEB_TIMEOUT_ENV, "").strip()
    try:
        return float(raw) if raw else DEFAULT_TIMEOUT_S
    except ValueError:
        return DEFAULT_TIMEOUT_S


def _web_max_bytes(explicit: int | None = None) -> int:
    if explicit is not None:
        return int(explicit)
    raw = os.environ.get(WEB_MAX_BYTES_ENV, "").strip()
    try:
        return int(raw) if raw else DEFAULT_MAX_BYTES
    except ValueError:
        return DEFAULT_MAX_BYTES


def resolve_web_ref(ref: str, *, allowed_hosts: Any = None) -> dict[str, str]:
    """Map an ``http(s)`` ref to an allowlisted fetch target. Pure mapping.

    Raises :class:`WebRefError` on a non-http scheme, a missing host, or a host
    that is not on the configured allowlist. It never touches the network.
    """
    text = str(ref or "").strip()
    if text.startswith("link:"):
        text = text[len("link:"):].strip()
    if not text.lower().startswith(("http://", "https://")):
        raise WebRefError("not_http_url")
    parsed = urlsplit(text)
    host = (parsed.hostname or "").lower()
    if not host:
        raise WebRefError("no_host")
    if host not in _web_allowed_hosts(allowed_hosts):
        raise WebRefError(f"domain_not_allowed:{host}")
    return {"ref": text, "host": host, "url": text}


def _default_web_fetch(
    url: str, *, timeout: float, max_bytes: int, allowed_hosts: set[str]
) -> FetchResult:
    """Minimal allowlisted GET. Never executed unless the web path is enabled."""
    request = urllib.request.Request(url, headers=dict(_UA))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            final_host = (urlsplit(response.geturl()).hostname or "").lower()
            if final_host not in allowed_hosts:
                return STATUS_BLOCKED, b"", f"redirect_host_not_allowed:{final_host or 'none'}"
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                return STATUS_TOO_LARGE, b"", f"size_gt:{max_bytes}"
            if response.status != 200:
                return STATUS_UNAVAILABLE, b"", f"http_{response.status}"
            ctype = (response.headers.get("content-type") or "").split(";")[0].strip()
            return STATUS_OK, body, ctype
    except urllib.error.HTTPError as exc:
        return STATUS_UNAVAILABLE, b"", f"http_{exc.code}"
    except (socket.timeout, TimeoutError):
        return STATUS_TIMEOUT, b"", "timeout"
    except (urllib.error.URLError, OSError) as exc:
        return STATUS_UNAVAILABLE, b"", f"network:{type(exc).__name__}"


def _remote_acquire(
    source: str,
    ref: str,
    *,
    trigger: str | None = None,
    enabled: bool | None = None,
    allowed_hosts: Any = None,
    fetcher: Callable[..., FetchResult] | None = None,
    inbox: str | os.PathLike[str] | None = None,
    timeout: float | None = None,
    max_bytes: int | None = None,
    reader: Callable[[str, str], Any] | None = None,
    transcriber: Callable[[str, str], Any] | None = None,
) -> dict[str, Any]:
    """Capture an allowlisted external web/media body into the inbox.

    Gate order — nothing past step 1 touches the network:

    1. resolve + allowlist the ref (blocked on a non-http scheme or a host that
       is not on the configured allowlist);
    2. require ``trigger == INDEX_TRIGGER`` (a Chat turn is blocked);
    3. require explicit enablement (``PULSE_CONTENT_WEB_ENABLED``);
    4. only then download, enforcing timeout, size cap and a redirect guard.

    The host allowlist is empty by default, so a capture is impossible until
    staff both enable the path and name the hosts. Media has no local
    transcriber: bytes land, and a transcript is attached only when a
    ``transcriber`` seam is injected.
    """
    job = _new_job(source, str(ref or ""))
    try:
        spec = resolve_web_ref(str(ref or ""), allowed_hosts=allowed_hosts)
    except WebRefError as exc:
        return _fail(job, STATUS_BLOCKED, str(exc))
    job["ref"] = spec["ref"]

    if trigger != INDEX_TRIGGER:
        return _fail(
            job,
            STATUS_BLOCKED,
            "chat_turn_forbidden: remote capture runs only from a staff Index job",
        )
    if not _web_enabled(enabled):
        return _fail(job, STATUS_UNAVAILABLE, f"missing enablement: set {WEB_ENABLE_ENV}=1")

    hosts = _web_allowed_hosts(allowed_hosts)
    cap = _web_max_bytes(max_bytes)
    tmo = _web_timeout(timeout)
    try:
        if fetcher is not None:
            result = fetcher(spec["url"], timeout=tmo, max_bytes=cap)
        else:
            result = _default_web_fetch(
                spec["url"], timeout=tmo, max_bytes=cap, allowed_hosts=hosts
            )
    except (socket.timeout, TimeoutError):
        return _fail(job, STATUS_TIMEOUT, "timeout")
    except Exception as exc:  # noqa: BLE001 — a bad fetcher must not crash the job
        return _fail(job, STATUS_UNAVAILABLE, f"fetch_error:{type(exc).__name__}")

    try:
        status, body, detail = result
    except (TypeError, ValueError):
        return _fail(job, STATUS_UNAVAILABLE, "bad_fetcher_result")

    if status != STATUS_OK:
        normalized = status if status in STATUSES else STATUS_UNAVAILABLE
        return _fail(job, normalized, str(detail or status or "web_error"))

    body = body or b""
    if len(body) > cap:
        return _fail(job, STATUS_TOO_LARGE, f"size_gt:{cap}")

    path_suffix = Path(urlsplit(spec["url"]).path).suffix.lower()
    mime = (detail or "").split(";")[0].strip() or guess_mime("file" + path_suffix)
    ext = _EXT_BY_MIME.get(mime) or path_suffix or ".bin"
    dest = _unique_dest(inbox_dir(inbox).expanduser(), f"{source}-{spec['host']}", ext)
    try:
        dest.write_bytes(body)
    except OSError as exc:
        return _fail(job, STATUS_UNAVAILABLE, f"io:{type(exc).__name__}")

    job["local_path"] = str(dest)
    job["mime"] = mime
    job["bytes"] = len(body)
    job["status"] = STATUS_OK
    _maybe_read(job, reader)
    if transcriber is not None:
        try:
            job["transcript"] = transcriber(str(dest), mime)
        except Exception as exc:  # noqa: BLE001 — transcription is a seam, not a gate
            job["transcript_error"] = f"{type(exc).__name__}: {exc}"
    return job


def web_acquire(ref: str, **kwargs: Any) -> dict[str, Any]:
    """Capture an arbitrary external web body (default OFF, Index job only)."""
    return _remote_acquire("web", ref, **kwargs)


def media_acquire(ref: str, **kwargs: Any) -> dict[str, Any]:
    """Capture a remote media body (bytes only; transcript is an injected seam)."""
    return _remote_acquire("media", ref, **kwargs)


# ── Unified entry point ──────────────────────────────────────────────────────


def acquire(
    source: Any = None,
    *,
    reader: Callable[[str, str], Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Acquire *source* into the inbox and return one job record.

    ``source`` may be:

    * a local filesystem path (→ :func:`local_acquire`, offline);
    * a Drive ref / share URL (→ :func:`drive_acquire`);
    * ``{"kind"|"source": "local"|"drive", "path"|"ref": ...}``.

    The Drive path keeps its ``trigger`` / ``enabled`` / ``credentials`` guards
    regardless of how the source is supplied.
    """
    if isinstance(source, Mapping):
        kind = str(source.get("kind") or source.get("source") or "").strip().lower()
        if kind == "drive":
            return drive_acquire(
                str(source.get("ref") or source.get("path") or ""), reader=reader, **kwargs
            )
        if kind == "local":
            return local_acquire(
                source.get("path") or source.get("local_path") or "", reader=reader, **kwargs
            )
        return _fail(_new_job("local", str(source)), STATUS_UNAVAILABLE, "unknown_source_kind")

    text = str(source or "")
    if text and Path(text).expanduser().is_file():
        return local_acquire(text, reader=reader, **kwargs)
    lowered = text.lower()
    if (
        _PREFIX_RE.match(text)
        or lowered.startswith("google-")
        or "docs.google.com" in lowered
        or "drive.google.com" in lowered
    ):
        return drive_acquire(text, reader=reader, **kwargs)
    if "://" in text or lowered.startswith(("link:", "http:", "https:")):
        return web_acquire(text, reader=reader, **kwargs)
    job = _new_job("local", text)
    job["path"] = text
    return _fail(job, STATUS_UNAVAILABLE, "unresolvable_source")


__all__ = [
    "INDEX_TRIGGER",
    "STATUSES",
    "STATUS_OK",
    "STATUS_UNAVAILABLE",
    "STATUS_TOO_LARGE",
    "STATUS_TIMEOUT",
    "STATUS_BLOCKED",
    "DriveRef",
    "DriveRefError",
    "WebRefError",
    "WEB_ENABLE_ENV",
    "WEB_ALLOWED_HOSTS_ENV",
    "WEB_TIMEOUT_ENV",
    "WEB_MAX_BYTES_ENV",
    "MEDIA_SUFFIXES",
    "acquire",
    "drive_acquire",
    "web_acquire",
    "media_acquire",
    "resolve_web_ref",
    "guess_mime",
    "inbox_dir",
    "local_acquire",
    "resolve_drive_ref",
]
