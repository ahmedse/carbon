#!/usr/bin/env python3
"""Fill course-meat-13 file rows from this Docker Moodle's local resource files.

The external ingest reads Drive and YouTube. This one reads ``mod/resource``
files that are already on disk in the Moodle dataroot and writes their text
into ``domain_packs/aast-med/bank/course-meat-13/<SHORT>.jsonl``. A row is
corrected in place only when the stored file yields real text. A legacy
``.ppt``, a video, or a scanned PDF is left as it was, with a printed reason,
so coverage never claims a passage that does not exist.

    python scripts/ingest_aast_med_local_files.py --manifest /tmp/missing_files_resolved.json \\
        --docker med-moodle-webserver-1 --dataroot /var/www/moodledata

The manifest is a list of ``{shortname, cmid, name, files:[{filename,
contenthash, filesize}]}`` rows, resolved from ``mdl_files`` for the resource
activities that have no bank text. Nothing is written to Moodle.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

_SCRIPTS = Path(__file__).resolve().parent
_PACK = _SCRIPTS.parent / "domain_packs" / "aast-med" / "bank" / "course-meat-13"
_GOLD = _SCRIPTS.parent / "domain_packs" / "aast-med" / "gold"

sys.path.insert(0, str(_SCRIPTS))
from ingest_aast_med_external import _clean, _office_text, _pdf_text  # noqa: E402

_OFFICE = {".pptx", ".pptm", ".docx"}
_SENTENCE = re.compile(r"(?<=[.!?؟])\s+")
_MIN_DEDUPE = 30


def _existing_texts(shortname: str, skip_refs: set[str]) -> list[str]:
    """Passage text already stored for a course, excluding the rows being filled."""
    path = _PACK / f"{shortname}.jsonl"
    out: list[str] = []
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("{"):
            continue
        row = json.loads(line)
        if str(row.get("ref") or "") in skip_refs:
            continue
        text = str(row.get("text") or "").strip()
        if text:
            out.append(text)
    return out


def _gold_quotes(shortname: str) -> list[str]:
    """The committed citation-ownership ledger: every cited sentence for a course.

    The gold pins each quote to one passage. A newly read deck must not carry a
    quote the gold assigns elsewhere, or a citation would have two owners.
    """
    quotes: list[str] = []
    paths = [_GOLD / "courses" / f"{shortname}.yaml"]
    if shortname == "NMD1103":
        paths.append(_GOLD / "c6.yaml")
    for path in paths:
        if not path.is_file():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for case in data.get("hits") or []:
            quote = str(case.get("quote") or "")
            if quote:
                quotes.append(quote)
    return quotes


def _dedupe(text: str, others: list[str], gold_quotes: list[str]) -> str:
    """Drop any whole sentence another passage or the gold already owns.

    A quote must map to one passage. When a newly read deck repeats a sentence
    that a PDF, an earlier deck, or the gold already carries, the new passage
    keeps the rest and does not re-own the sentence. Only whole sentences are
    removed, so word and sentence boundaries stay intact.
    """
    for quote in gold_quotes:
        if quote in text:
            text = text.replace(quote, " ")
    kept = []
    for sentence in _SENTENCE.split(text):
        sentence = " ".join(sentence.split())
        if not sentence:
            continue
        if len(sentence) >= _MIN_DEDUPE and any(sentence in other for other in others):
            continue
        kept.append(sentence)
    return " ".join(kept)


def _stored_path(contenthash: str) -> str:
    return f"filedir/{contenthash[:2]}/{contenthash[2:4]}/{contenthash}"


def _bytes_from_docker(container: str, dataroot: str, contenthash: str) -> bytes:
    command = ["docker", "exec", container, "base64", "-w0", f"{dataroot}/{_stored_path(contenthash)}"]
    out = subprocess.run(command, check=True, capture_output=True)
    return base64.b64decode(out.stdout)


def _extract(filename: str, data: bytes) -> tuple[str, str]:
    """(status, text). Status is ok, empty, or unavailable with a reason."""
    suffix = Path(filename).suffix.lower()
    if suffix in _OFFICE:
        try:
            text = _office_text(data)
        except Exception as exc:  # noqa: BLE001 - a bad archive is a status, not a crash.
            return f"unavailable:format:{type(exc).__name__}", ""
        return ("ok", text) if text else ("empty:no_text", "")
    if suffix == ".pdf":
        try:
            text = _pdf_text(data)
        except Exception as exc:  # noqa: BLE001
            return f"unavailable:format:{type(exc).__name__}", ""
        return ("ok", text) if text else ("empty:no_text", "")
    if suffix in {".ppt", ".mp4", ".mov", ".avi"}:
        return "unavailable:legacy_video", ""
    return "unavailable:no_extractor", ""


def _update_course(shortname: str, texts: dict[str, str]) -> int:
    path = _PACK / f"{shortname}.jsonl"
    others = _existing_texts(shortname, set(texts))
    gold_quotes = _gold_quotes(shortname)
    lines = path.read_text(encoding="utf-8").splitlines()
    written = 0
    out: list[str] = []
    for line in lines:
        if not line.startswith("{"):
            out.append(line)
            continue
        row = json.loads(line)
        ref = str(row.get("ref") or "")
        text = texts.get(ref)
        if row.get("kind") == "file" and text and not str(row.get("text") or "").strip():
            cleaned = _dedupe(text, others, gold_quotes)
            if not cleaned:
                out.append(line)
                continue
            row["text"] = cleaned
            written += 1
            out.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
        else:
            out.append(line)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--docker", default="med-moodle-webserver-1")
    parser.add_argument("--dataroot", default="/var/www/moodledata")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    if args.limit:
        manifest = manifest[: args.limit]

    per_course: dict[str, dict[str, str]] = {}
    tally: dict[str, int] = {}
    for entry in manifest:
        shortname = str(entry.get("shortname") or "")
        files = entry.get("files") or []
        if not shortname or not files:
            continue
        record = files[0]
        filename = str(record.get("filename") or "")
        contenthash = str(record.get("contenthash") or "")
        if not filename or not contenthash:
            continue
        if Path(filename).suffix.lower() not in _OFFICE | {".pdf"}:
            # Do not pull a video or a legacy .ppt we cannot read.
            status, text = _extract(filename, b"")
        else:
            data = _bytes_from_docker(args.docker, args.dataroot, contenthash)
            status, text = _extract(filename, data)
        tally[status.split(":")[0] + ":" + status.split(":")[-1]] = (
            tally.get(status.split(":")[0] + ":" + status.split(":")[-1], 0) + 1
        )
        if status == "ok" and text:
            per_course.setdefault(shortname, {})["file:" + filename] = text
            print(f"  ok {shortname} {filename} {len(text)} chars", flush=True)
        else:
            print(f"  {status} {shortname} {filename} ({record.get('filesize')} bytes)", flush=True)

    for shortname, texts in per_course.items():
        written = _update_course(shortname, texts)
        print(f"{shortname}: wrote {written} file rows", flush=True)
    print("tally:", json.dumps(tally, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
