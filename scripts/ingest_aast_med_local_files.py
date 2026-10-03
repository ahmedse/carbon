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
_REPO = _SCRIPTS.parent
_PACK = _REPO / "domain_packs" / "aast-med" / "bank" / "course-meat-13"
_GOLD = _REPO / "domain_packs" / "aast-med" / "gold"

sys.path.insert(0, str(_REPO / "backend"))
from ai.content_engine import ingest as content_ingest  # noqa: E402
from ai.moodle_content_job import record_ocr_pending  # noqa: E402

# Every extension the shared content-engine registry routes: office (.pptx,
# .pptm, .ppsx, .ppt, .docx), pdf, txt/md/json/csv, html, and images. There is
# no second PDF/office stack; the registry is the single reader dispatcher.
_EXTRACTABLE = content_ingest.ROUTED_SUFFIXES
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
    """(status, text) through the shared content-engine registry.

    Routes office (pptx/pptm/ppsx/ppt/docx), pdf, txt/md/json/csv, html, and
    images to one reader stack; a scanned PDF/image falls back to OCR
    (``signoff:arabic`` when the recovered text is Arabic and needs sign-off).
    """
    return content_ingest.extract_text(data, filename)


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


def _append_course(shortname: str, texts: dict[str, str]) -> tuple[int, list[str]]:
    """Append one filled row per newly-read ref. Never edits or deletes a row.

    The placeholder row stays exactly as it is; a new row carrying the text is
    appended and the stable join key (section + family + name) is copied from
    the placeholder, so coverage counts it. A ref the bank already owns, or a
    passage that dedupes to nothing, is skipped with a printed reason.
    """
    path = _PACK / f"{shortname}.jsonl"
    blob = path.read_text(encoding="utf-8")
    rows = [json.loads(line) for line in blob.splitlines() if line.startswith("{")]
    owned = {
        str(row.get("ref") or "")
        for row in rows
        if str(row.get("text") or "").strip()
    }
    others = _existing_texts(shortname, set(texts))
    gold_quotes = _gold_quotes(shortname)
    appended: list[str] = []
    reasons: list[str] = []
    for ref, text in texts.items():
        if ref in owned:
            reasons.append(f"{ref}:already_owned")
            continue
        template = next(
            (
                row
                for row in rows
                if row.get("kind") == "file" and str(row.get("ref") or "") == ref
            ),
            None,
        )
        if template is None:
            reasons.append(f"{ref}:no_placeholder")
            continue
        cleaned = _dedupe(text, others, gold_quotes)
        if not cleaned:
            reasons.append(f"{ref}:duplicate_only")
            continue
        row = {
            "course": shortname,
            "sectionnum": int(template.get("sectionnum") or 0),
            "section": str(template.get("section") or ""),
            "visible": bool(template.get("visible", True)),
            "kind": "file",
            "name": str(template.get("name") or ""),
            "ref": ref,
            "text": cleaned,
        }
        appended.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
        others.append(cleaned)
    if appended:
        prefix = "" if not blob or blob.endswith("\n") else "\n"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(prefix + "\n".join(appended) + "\n")
    return len(appended), reasons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--docker", default="med-moodle-webserver-1")
    parser.add_argument("--dataroot", default="/var/www/moodledata")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--append",
        action="store_true",
        help="append a new filled row instead of filling a placeholder in place",
    )
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    if args.limit:
        manifest = manifest[: args.limit]

    per_course: dict[str, dict[str, str]] = {}
    pending: dict[str, list[dict]] = {}
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
        if Path(filename).suffix.lower() not in _EXTRACTABLE:
            # Do not pull a video we cannot read.
            status, text = _extract(filename, b"")
        else:
            data = _bytes_from_docker(args.docker, args.dataroot, contenthash)
            status, text = _extract(filename, data)
        tally[status.split(":")[0] + ":" + status.split(":")[-1]] = (
            tally.get(status.split(":")[0] + ":" + status.split(":")[-1], 0) + 1
        )
        if status == "signoff:arabic" and text:
            # Arabic scanned content: keep it verbatim but out of the citable
            # bank until the recorded human sign-off clears it.
            pending.setdefault(shortname, []).append(
                {
                    "filename": filename,
                    "ref": "file:" + filename,
                    "locator": "ocr",
                    "text": text,
                    "signoff": "arabic",
                }
            )
            print(
                f"  {status} {shortname} {filename} ({len(text)} chars, pending sign-off)",
                flush=True,
            )
        elif status == "ok" and text:
            per_course.setdefault(shortname, {})["file:" + filename] = text
            print(f"  ok {shortname} {filename} {len(text)} chars", flush=True)
        else:
            print(f"  {status} {shortname} {filename} ({record.get('filesize')} bytes)", flush=True)

    for shortname, texts in per_course.items():
        if args.append:
            written, reasons = _append_course(shortname, texts)
            for reason in reasons:
                print(f"  skip {shortname} {reason}", flush=True)
        else:
            written = _update_course(shortname, texts)
        print(f"{shortname}: wrote {written} file rows", flush=True)
    for shortname, rows in pending.items():
        stored = record_ocr_pending(shortname, rows)
        print(f"{shortname}: {stored} OCR passages pending Arabic sign-off", flush=True)
    print("tally:", json.dumps(tally, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
