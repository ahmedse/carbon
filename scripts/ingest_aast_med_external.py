#!/usr/bin/env python3
"""Read the Drive bodies and YouTube captions linked from the 13 listed courses.

One row per linked activity in ``domain_packs/aast-med/bank/course-ext-13``.
The row says what happened. A body is stored only when the host answered with
the document text. A failure is a row with a status and a cause, never a
guess and never the Moodle intro.

    python scripts/ingest_aast_med_external.py --course NMD1000
    python scripts/ingest_aast_med_external.py --all

Only public export links are read. Nothing is written to Moodle, Google, or
YouTube. Run it when the bank should be refreshed. The Pulse turn never runs it.
"""
from __future__ import annotations

import argparse
import html
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

_PACK = Path(__file__).resolve().parents[1] / "domain_packs" / "aast-med"
_KEYS = _PACK / "bank" / "course-keys-13"
_OUT = _PACK / "bank" / "course-ext-13"
_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}t"
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
_ANDROID = {"clientName": "ANDROID", "clientVersion": "20.10.38", "hl": "en", "gl": "US"}
_GOOGLE_ID = re.compile(r"/d/([A-Za-z0-9_-]{16,})|/file/d/([A-Za-z0-9_-]{16,})|[?&]id=([A-Za-z0-9_-]{16,})")


def _shortnames() -> list[str]:
    import yaml

    data = yaml.safe_load((_PACK / "courses.yaml").read_text(encoding="utf-8")) or {}
    return [str(r["shortname"]) for r in data.get("enabled_courses") or []]


def _get(url: str, timeout: int = 30) -> tuple[int, str, str, bytes]:
    request = urllib.request.Request(url, headers=_UA)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.headers.get("content-type", ""), response.geturl(), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("content-type", "") if exc.headers else "", getattr(exc, "geturl", lambda: url)(), exc.read() if hasattr(exc, "read") else b""
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, "", url, str(exc).encode()[:120]


def _post_json(url: str, payload: dict, timeout: int = 30) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={**_UA, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read() if hasattr(exc, "read") else b""
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, str(exc).encode()[:120]


def _clean(text: str) -> str:
    return " ".join(text.replace("\ufeff", " ").split())


def _office_text(data: bytes) -> str:
    z = zipfile.ZipFile(io.BytesIO(data))
    names = z.namelist()
    if any(n.startswith("ppt/slides/") for n in names):
        slides = sorted(
            (n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)),
            key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)),
        )
        return _clean(" ".join(t.text or "" for n in slides for t in ET.fromstring(z.read(n)).iter(_A)))
    if "word/document.xml" in names:
        return _clean(" ".join(t.text or "" for t in ET.fromstring(z.read("word/document.xml")).iter(_W)))
    return ""


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        return ""
    return _clean(" ".join((page.extract_text() or "") for page in reader.pages))


def _xml_caption_text(raw: bytes) -> str:
    root = ET.fromstring(raw)
    lines = [html.unescape(node.text or "") for node in root.iter("text")]
    if not any(lines):
        parts = []
        for paragraph in root.iter("p"):
            bits = [paragraph.text or ""]
            for child in paragraph:
                bits.append(child.text or "")
                bits.append(child.tail or "")
            parts.append("".join(bits))
        lines = [html.unescape(p) for p in parts]
    return _clean(" ".join(lines))


def _json3_caption_text(raw: bytes) -> str:
    data = json.loads(raw.decode("utf-8", errors="replace"))
    bits = []
    for event in data.get("events") or []:
        for seg in event.get("segs") or []:
            bits.append(str(seg.get("utf8") or ""))
    return _clean("".join(bits).replace("\n", " "))


def _caption_from_body(raw: bytes) -> str:
    if not raw:
        return ""
    head = raw.lstrip()[:1]
    if head == b"{":
        try:
            return _json3_caption_text(raw)
        except json.JSONDecodeError:
            return ""
    if raw.startswith(b"WEBVTT"):
        lines = []
        for line in raw.decode("utf-8", errors="replace").splitlines():
            if not line.strip() or "-->" in line or line.startswith("WEBVTT") or line[:1].isdigit():
                continue
            lines.append(line)
        return _clean(" ".join(lines))
    try:
        return _xml_caption_text(raw)
    except ET.ParseError:
        return ""


def _export(url: str) -> tuple[str, str, str]:
    """(status, cause, text)."""
    code, ctype, final, body = _get(url, timeout=60)
    if code == 0:
        return "unavailable", "network", ""
    if code != 200:
        return "unavailable", f"http_{code}", ""
    if "accounts.google.com" in final or "ServiceLogin" in final:
        return "unavailable", "not_public", ""
    if "text/plain" in ctype:
        text = _clean(body.decode("utf-8", errors="replace"))
        return ("ok", "", text) if text else ("empty", "no_text", "")
    if body[:2] == b"PK":
        try:
            text = _office_text(body)
        except (zipfile.BadZipFile, ET.ParseError):
            return "unavailable", "format", ""
        return ("ok", "", text) if text else ("empty", "no_text", "")
    if "text/html" in ctype:
        return "unavailable", "not_public", ""
    return "unavailable", "format", ""


def google_presentation(source_id: str) -> tuple[str, str, str]:
    status, cause, text = _export(f"https://docs.google.com/presentation/d/{source_id}/export/txt")
    if status in {"ok", "empty"} or cause == "http_410":
        return status, cause, text
    pptx = _export(f"https://docs.google.com/presentation/d/{source_id}/export/pptx")
    if pptx[0] in {"ok", "empty"}:
        return pptx
    return status, cause, text


def google_document(source_id: str) -> tuple[str, str, str]:
    return _export(f"https://docs.google.com/document/d/{source_id}/export?format=txt")


def google_file(source_id: str) -> tuple[str, str, str]:
    code, ctype, final, body = _get(f"https://drive.google.com/uc?export=download&id={source_id}", timeout=60)
    if code == 200 and "text/html" in ctype and b"confirm=" in body:
        token = re.search(br"confirm=([0-9A-Za-z_-]+)", body)
        if token:
            code, ctype, final, body = _get(
                f"https://drive.google.com/uc?export=download&id={source_id}&confirm={token.group(1).decode()}",
                timeout=60,
            )
    if code != 200:
        return "unavailable", f"http_{code or 'network'}", ""
    if "accounts.google.com" in final:
        return "unavailable", "not_public", ""
    if "text/html" in ctype:
        return "unavailable", "not_public", ""
    if body[:2] == b"PK":
        try:
            text = _office_text(body)
        except (zipfile.BadZipFile, ET.ParseError):
            return "unavailable", "format", ""
        return ("ok", "", text) if text else ("empty", "no_text", "")
    if body[:4] == b"%PDF":
        try:
            text = _pdf_text(body)
        except Exception:
            return "unavailable", "format", ""
        return ("ok", "", text) if text else ("empty", "no_text", "")
    return "unavailable", "no_extractor", ""


def youtube_caption(video_id: str) -> tuple[str, str, str]:
    """ANDROID player timedtext. Watch-page caption URLs return HTTP 200 with an empty body."""
    code, raw = _post_json(
        "https://www.youtube.com/youtubei/v1/player?prettyPrint=false",
        {"context": {"client": _ANDROID}, "videoId": video_id},
    )
    if code != 200 or not raw:
        return "unavailable", f"player_http_{code or 'network'}", ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return "unavailable", "player_parse", ""
    play = str((data.get("playabilityStatus") or {}).get("status") or "")
    tracks = (
        (data.get("captions") or {}).get("playerCaptionsTracklistRenderer") or {}
    ).get("captionTracks") or []
    if not tracks:
        if play and play not in {"OK", "LIVE_STREAM"}:
            return "unavailable", f"player_{play.lower()}", ""
        return "empty", "no_caption_track", ""
    track = next((t for t in tracks if str(t.get("languageCode") or "").startswith("en")), tracks[0])
    base = str(track.get("baseUrl") or "")
    if not base:
        return "empty", "no_caption_track", ""
    code, _ctype, _final, body = _get(base)
    if code != 200:
        return "unavailable", f"caption_http_{code or 'network'}", ""
    if not body:
        return "empty", "caption_blank", ""
    try:
        text = _caption_from_body(body)
    except ET.ParseError:
        return "unavailable", "caption_parse", ""
    return ("ok", "", text) if text else ("empty", "caption_blank", "")


def unresolved_docs_link(key: dict) -> dict:
    """Status row for a docs.google.com URL with no source id in the key bank."""
    source_id = ""
    extra = str(key.get("url") or key.get("externalurl") or "")
    found = _GOOGLE_ID.search(extra)
    if found:
        source_id = next(g for g in found.groups() if g)
    return {
        "course": str(key.get("course") or ""),
        "cmid": int(key["cmid"]),
        "family": "google",
        "source_kind": "link:docs.google.com",
        "source_id": source_id,
        "name": str(key.get("name") or ""),
        "status": "unavailable" if not source_id else "",
        "cause": "unresolved_link" if not source_id else "",
        "text": "",
    }


_KINDS = {
    "google-presentation": ("google", google_presentation),
    "google-document": ("google", google_document),
    "google-file": ("google", google_file),
    "youtube": ("youtube", youtube_caption),
}


def _write(shortname: str, rows: list[dict]) -> None:
    _OUT.mkdir(parents=True, exist_ok=True)
    (_OUT / f"{shortname}.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in rows),
        encoding="utf-8",
    )


def ingest(shortname: str, pause: float) -> dict[str, int]:
    keys = [json.loads(l) for l in (_KEYS / f"{shortname}.jsonl").read_text(encoding="utf-8").splitlines() if l.startswith("{")]
    rows, tally = [], {}
    for key in keys:
        ref = str(key.get("ref") or "")
        prefix, _, source_id = ref.partition(":")
        if key.get("kind") != "url" or not key.get("cmid"):
            continue
        if prefix == "link" and source_id.startswith("docs.google.com"):
            copied = unresolved_docs_link(key)
            if copied["source_id"]:
                kind = "google-presentation"
                if "/document/" in source_id or "/document/" in str(key.get("url") or ""):
                    kind = "google-document"
                elif "/file/" in source_id or "/file/" in str(key.get("url") or ""):
                    kind = "google-file"
                family, reader = _KINDS[kind]
                status, cause, text = reader(copied["source_id"])
                copied.update(
                    {
                        "family": family,
                        "source_kind": kind,
                        "status": status,
                        "cause": cause,
                        "text": text,
                    }
                )
            rows.append(copied)
            tally[f"{copied['family']}:{copied['status']}"] = tally.get(f"{copied['family']}:{copied['status']}", 0) + 1
            if copied["source_id"]:
                time.sleep(pause)
            continue
        if prefix not in _KINDS or not source_id:
            continue
        family, reader = _KINDS[prefix]
        status, cause, text = reader(source_id)
        rows.append({
            "course": shortname,
            "cmid": int(key["cmid"]),
            "family": family,
            "source_kind": prefix,
            "source_id": source_id,
            "name": str(key.get("name") or ""),
            "status": status,
            "cause": cause,
            "text": text,
        })
        tally[f"{family}:{status}"] = tally.get(f"{family}:{status}", 0) + 1
        time.sleep(pause)
    _write(shortname, rows)
    return tally


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--course", action="append")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--pause", type=float, default=0.35)
    args = parser.parse_args()
    courses = _shortnames() if args.all else (args.course or [])
    if not courses:
        parser.error("give --course or --all")
    for shortname in courses:
        print(shortname, ingest(shortname, args.pause), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
