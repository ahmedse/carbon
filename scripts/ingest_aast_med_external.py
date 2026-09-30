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
_UA = {"User-Agent": "Mozilla/5.0"}
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}t"
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"


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
        return exc.code, exc.headers.get("content-type", ""), exc.geturl(), b""
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, "", url, str(exc).encode()[:120]


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


def _export(url: str) -> tuple[str, str, str]:
    """(status, cause, text)."""
    code, ctype, final, body = _get(url)
    if code == 0:
        return "unavailable", "network", ""
    if code in (401, 403, 404):
        return "unavailable", f"http_{code}", ""
    if code != 200:
        return "unavailable", f"http_{code}", ""
    if "accounts.google.com" in final or "ServiceLogin" in final:
        return "unavailable", "not_public", ""
    if ctype.startswith("text/plain"):
        text = _clean(body.decode("utf-8", errors="replace"))
        return ("ok", "", text) if text else ("empty", "no_text", "")
    if ctype.startswith("text/html"):
        return "unavailable", "not_public", ""
    return "unavailable", "format", ""


def google_presentation(source_id: str) -> tuple[str, str, str]:
    return _export(f"https://docs.google.com/presentation/d/{source_id}/export/txt")


def google_document(source_id: str) -> tuple[str, str, str]:
    return _export(f"https://docs.google.com/document/d/{source_id}/export?format=txt")


def google_file(source_id: str) -> tuple[str, str, str]:
    code, ctype, final, body = _get(f"https://drive.google.com/uc?export=download&id={source_id}", timeout=60)
    if code != 200 or "accounts.google.com" in final:
        return "unavailable", "not_public" if code == 200 else f"http_{code or 'network'}", ""
    if ctype.startswith("text/html"):
        return "unavailable", "not_public", ""
    if body[:2] == b"PK":
        try:
            text = _office_text(body)
        except (zipfile.BadZipFile, ET.ParseError):
            return "unavailable", "format", ""
        return ("ok", "", text) if text else ("empty", "no_text", "")
    return "unavailable", "no_extractor", ""


def youtube_caption(video_id: str) -> tuple[str, str, str]:
    code, _ctype, _final, body = _get(f"https://www.youtube.com/watch?v={video_id}")
    if code != 200:
        return "unavailable", f"http_{code or 'network'}", ""
    page = body.decode("utf-8", errors="replace")
    match = re.search(r'"captionTracks":\s*(\[.*?\])', page)
    if not match:
        return "empty", "no_caption_track", ""
    try:
        tracks = json.loads(match.group(1))
    except json.JSONDecodeError:
        return "unavailable", "track_parse", ""
    if not tracks:
        return "empty", "no_caption_track", ""
    track = next((t for t in tracks if t.get("languageCode", "").startswith("en")), tracks[0])
    code, _c, _f, xml = _get(track["baseUrl"].replace("\\u0026", "&"))
    if code != 200 or not xml:
        return "unavailable", f"caption_http_{code or 'network'}", ""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return "unavailable", "caption_parse", ""
    lines = [html.unescape(node.text or "") for node in root.iter("text")]
    text = _clean(" ".join(lines))
    return ("ok", "", text) if text else ("empty", "caption_blank", "")


_KINDS = {
    "google-presentation": ("google", google_presentation),
    "google-document": ("google", google_document),
    "google-file": ("google", google_file),
    "youtube": ("youtube", youtube_caption),
}


def ingest(shortname: str, pause: float) -> dict[str, int]:
    keys = [json.loads(l) for l in (_KEYS / f"{shortname}.jsonl").read_text(encoding="utf-8").splitlines() if l.startswith("{")]
    rows, tally = [], {}
    for key in keys:
        ref = str(key.get("ref") or "")
        prefix, _, source_id = ref.partition(":")
        if key.get("kind") != "url" or prefix not in _KINDS or not source_id or not key.get("cmid"):
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
    _OUT.mkdir(parents=True, exist_ok=True)
    (_OUT / f"{shortname}.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in rows),
        encoding="utf-8",
    )
    return tally


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--course", action="append")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--pause", type=float, default=0.4)
    args = parser.parse_args()
    courses = _shortnames() if args.all else (args.course or [])
    if not courses:
        parser.error("give --course or --all")
    for shortname in courses:
        print(shortname, ingest(shortname, args.pause), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
