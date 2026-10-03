"""HTML reader: strip tags to text, keep block structure as line breaks.

Script/style/head content is dropped. Text nodes are copied verbatim, so any
sentence in the page survives as a citable unit.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

_BLOCK = {
    "p", "div", "br", "li", "tr", "td", "th", "section", "article", "header",
    "footer", "main", "nav", "aside", "pre", "blockquote", "figure", "figcaption",
    "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table", "dl", "dt", "dd",
}
_SKIP = {"script", "style", "head", "noscript", "template", "title"}


def _result(units: list[dict], status: str, error: str | None) -> dict:
    return {"units": units, "status": status, "reader": "html", "error": error}


def _unit(text: str) -> dict:
    return {
        "text": text,
        "kind": "html",
        "source_ref": "",
        "locator": "n/a",
        "citable": True,
        "course": None,
        "activity_ref": None,
        "status": "ok",
    }


class _Stripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _SKIP:
            self._skip += 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs) -> None:
        if tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            if self._skip:
                self._skip -= 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def read(path: str, mime: str | None = None) -> dict:
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        return _result([], "unreadable", f"{type(exc).__name__}: {exc}")
    if not raw.strip():
        return _result([], "empty", "no_text")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", "replace")

    stripper = _Stripper()
    try:
        stripper.feed(text)
        stripper.close()
    except Exception as exc:  # noqa: BLE001 - malformed markup is a status.
        return _result([], "unreadable", f"{type(exc).__name__}: {exc}")

    body = "".join(stripper.parts)
    lines = [" ".join(line.split()) for line in body.splitlines()]
    text = "\n".join(line for line in lines if line)
    if not text:
        return _result([], "empty", "no_text")
    return _result([_unit(text)], "ok", None)
