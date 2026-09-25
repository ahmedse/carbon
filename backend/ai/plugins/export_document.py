"""``export_document`` — generate Word / Excel / PDF / PNG artifacts.

Deliverable primitive for the workspace agent: after a study, audit, or
research task the agent can produce real downloadable files instead of only
chat prose. ``format`` selects the output (``docx``, ``xlsx``, ``pdf``,
``png``, ``both`` = docx+xlsx, or ``pack`` = all four). Content is accepted
as markdown ``content`` and/or a ``table`` (headers + rows → sheet / Word
table / PDF table / PNG chart).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils.timezone import now

from ai.engine.agent.plugins import ToolPlugin

logger = logging.getLogger("carbon.ai.plugins.export_document")

_SAFE_FMT = {"docx", "xlsx", "pdf", "png"}

_MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
    "png": "image/png",
}

# format aliases → concrete set of generators to run
_FORMAT_SETS = {
    "docx": ("docx",),
    "xlsx": ("xlsx",),
    "pdf": ("pdf",),
    "png": ("png",),
    "both": ("docx", "xlsx"),
    "pack": ("docx", "xlsx", "pdf", "png"),
}


def _slugify(value: str) -> str:
    value = re.sub(r"[^\w\s-]", "", value or "").strip().lower()
    value = re.sub(r"[-\s]+", "-", value)
    return value[:60] or "document"


_BRAND_TEAL = "0B5F4E"
_BRAND_BAND = "EAF3F0"
_BRAND_MUTED = "6B7280"

# Identity block stamped on every deliverable (Operator-facing, RULE_23).
# Never brand host platform names (Carbon) on Pulse outputs.
_PULSE_COWORKER = "Pulse — AI Coworker"


def _deliverable_identity_lines(*, run_id: str | None = None) -> list[str]:
    """Header lines identifying who prepared the file and when."""
    stamp = now().strftime("%B %d, %Y · %H:%M UTC")
    lines = [
        f"Prepared by {_PULSE_COWORKER}",
        f"Generated {stamp}",
    ]
    rid = (run_id or "").strip()
    if rid:
        lines.append(f"Agent run {rid[:8]}…  ·  Confidential — authorized recipients only")
    else:
        lines.append("Confidential — authorized recipients only")
    return lines


def _pdf_font_path() -> Path | None:
    """A TTF that covers Latin + Arabic. Helvetica does not."""
    for raw in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        path = Path(raw)
        if path.is_file():
            return path
    return None


def _shape_pdf_text(text: str) -> str:
    """Presentation forms + visual order when the line has Arabic letters."""
    if not any("\u0600" <= ch <= "\u06ff" for ch in (text or "")):
        return text
    import arabic_reshaper
    from bidi.algorithm import get_display

    return get_display(arabic_reshaper.reshape(text or ""))


def _wrap_pdf_line(text: str, font: str, size: int, max_width: float) -> list[str]:
    from reportlab.pdfbase import pdfmetrics

    shaped = _shape_pdf_text(text)
    if pdfmetrics.stringWidth(shaped, font, size) <= max_width:
        return [shaped]
    words = shaped.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if pdfmetrics.stringWidth(trial, font, size) <= max_width:
            current = trial
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines or [shaped]


def _render_pdf_lines(path: Path, lines: list[str]) -> None:
    """Unicode PDF. Helvetica + latin-1 replace is what turned Arabic into '?'."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    font_path = _pdf_font_path()
    if font_path is None:
        raise ValueError("No Unicode TTF on this host — cannot write a PDF.")
    pdfmetrics.registerFont(TTFont("PulseBody", str(font_path)))
    page_w, page_h = letter
    left, right = 50, 50
    max_w = page_w - left - right
    c = canvas.Canvas(str(path), pagesize=letter)
    y = page_h - 56
    leading = 14
    for i, raw in enumerate(lines):
        size = 16 if i == 0 else 11
        for piece in _wrap_pdf_line(raw, "PulseBody", size, max_w):
            if y < 48:
                c.showPage()
                y = page_h - 56
            c.setFont("PulseBody", size)
            c.setFillColorRGB(0.05, 0.07, 0.09)
            c.drawString(left, y, piece)
            y -= leading if size == 11 else 20
    c.save()


def _current_run_id() -> str | None:
    try:
        from ai.plans_service import get_current_plan_run
        return get_current_plan_run()
    except Exception:  # noqa: BLE001
        return None


def _looks_numeric(text: str) -> bool:
    """True for values that read as a number (currency/percent/commas allowed)."""
    return bool(re.match(r"^[\s$€£]*[-+]?[\d,]+(?:\.\d+)?\s*%?$", (text or "").strip()))


def _to_number(value: Any) -> float | None:
    """Parse a display string like '8,032,225.88' or '78.0' to a float, else None."""
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value or "").strip().replace(",", "").replace("$", "").replace("€", "").replace("£", "")
    if s.endswith("%"):
        s = s[:-1]
    try:
        return float(s)
    except ValueError:
        return None


_GFM_ROW_RE = re.compile(r"^\|(.+)\|$")
_GFM_SEP_CELL_RE = re.compile(r"^:?-{2,}:?$")


def _split_gfm_row(line: str) -> list[str] | None:
    """Split a GFM table row ``| a | b |`` into cells. None if not a row."""
    stripped = (line or "").strip()
    if not stripped.startswith("|"):
        return None
    # Trailing pipe optional (some models omit it).
    body = stripped[1:]
    if body.endswith("|"):
        body = body[:-1]
    cells = [c.strip() for c in body.split("|")]
    if len(cells) < 2:
        return None
    return cells


def _is_gfm_separator(cells: list[str]) -> bool:
    return bool(cells) and all(_GFM_SEP_CELL_RE.match(c.replace(" ", "")) for c in cells)


def coerce_table(value):
    """Accept a row list as well as ``{headers, rows}``.

    A list of objects uses the keys as headers. A list of lists uses the
    first row as headers. Anything else is left for the caller to reject.
    """
    if value is None or isinstance(value, dict):
        return value
    if not isinstance(value, list) or not value:
        return value
    if all(isinstance(row, dict) for row in value):
        headers: list[str] = []
        for row in value:
            for key in row:
                if str(key) not in headers:
                    headers.append(str(key))
        rows = [[row.get(h, "") for h in headers] for row in value]
        return {"headers": headers, "rows": rows}
    if all(isinstance(row, list) for row in value):
        headers = [str(cell) for cell in value[0]]
        rows = [list(row) for row in value[1:]]
        return {"headers": headers, "rows": rows}
    return value


def parse_gfm_tables(content: str) -> tuple[str, list[dict]]:
    """Pull GFM pipe tables out of markdown ``content``.

    Returns ``(prose_without_tables, tables)`` where each table is
    ``{"headers": [...], "rows": [[...], ...]}``. Used so Word/Excel never
    show literal ``|---|`` delimiter lines (operator-facing deliverables).
    """
    if not (content or "").strip():
        return "", []
    lines = content.splitlines()
    prose: list[str] = []
    tables: list[dict] = []
    i = 0
    while i < len(lines):
        header = _split_gfm_row(lines[i])
        sep = _split_gfm_row(lines[i + 1]) if i + 1 < len(lines) else None
        if header and sep and _is_gfm_separator(sep) and len(sep) == len(header):
            rows: list[list[str]] = []
            i += 2
            while i < len(lines):
                row = _split_gfm_row(lines[i])
                if row is None or _is_gfm_separator(row):
                    break
                # Pad / trim to header width.
                if len(row) < len(header):
                    row = row + [""] * (len(header) - len(row))
                rows.append(row[: len(header)])
                i += 1
            tables.append({"headers": header, "rows": rows})
            prose.append("")  # keep a blank gap where the table was
            continue
        prose.append(lines[i])
        i += 1
    return "\n".join(prose), tables


class ExportDocument(ToolPlugin):
    name = "export_document"
    description = (
        "Generate downloadable deliverables from findings: Word (.docx), "
        "Excel (.xlsx), PDF, and/or a PNG chart. Use format 'pack' for all "
        "four (board packs). Provide a title, optional markdown content, "
        "and/or a table (headers + rows — also drives the PNG chart). "
        "Returns download links for the plan Artifacts strip."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Document title (used as heading and filename stem).",
            },
            "format": {
                "type": "string",
                "enum": ["docx", "xlsx", "pdf", "png", "both", "pack"],
                "description": (
                    "Which formats to generate. Default: both (docx+xlsx). "
                    "'pack' = docx+xlsx+pdf+png."
                ),
            },
            "content": {
                "type": "string",
                "description": (
                    "Markdown body with REAL findings only: '# Heading', "
                    "'## Subheading', '- bullet', '1. item', blank-line "
                    "paragraphs. NEVER use placeholder tokens such as "
                    "'[Placeholder…]', 'to be inserted', or empty stubs. "
                    "Rendered into Word (and an Excel Summary sheet)."
                ),
            },
            "table": {
                "type": ["object", "array"],
                "description": (
                    "Optional table for Excel / Word. Prefer "
                    "{headers, rows}. A list of row objects, or a list of "
                    "lists whose first row is the headers, is accepted too."
                ),
                "properties": {
                    "headers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Column headers.",
                    },
                    "rows": {
                        "type": "array",
                        "items": {"type": "array", "items": {"type": "string"}},
                        "description": "Rows of cell values (strings/numbers).",
                    },
                },
                "required": ["headers", "rows"],
            },
            "images": {
                "type": "array",
                "description": (
                    "Optional chart/figure PNGs as base64 (no data: URI prefix). "
                    "Embedded into Word; ignored by Excel/PDF text writers."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "caption": {"type": "string"},
                        "image_b64": {"type": "string"},
                    },
                    "required": ["image_b64"],
                },
            },
        },
        "required": ["title"],
    }
    requires_confirmation = False
    capability: str | None = None
    app_identifier: str | None = None

    async def execute(self, args: dict, *, ctx) -> dict:
        from ai.engine.cognition.plan.export_bind import export_has_substance

        title = (args.get("title") or "").strip()
        if not title:
            return {"error": "A title is required — e.g. 'Carbon Standards Study'."}

        fmt = (args.get("format") or "both").strip().lower()
        wanted = _FORMAT_SETS.get(fmt) or _FORMAT_SETS["both"]

        content = (args.get("content") or "").strip()
        table = coerce_table(args.get("table") or None)
        if table is not None and not isinstance(table, dict):
            return {"error": "table must be {headers, rows} or a list of rows."}
        images = args.get("images") if isinstance(args.get("images"), list) else []

        # Fail-visible substance gate: never ship hollow, mid-run, or title-only packs.
        requires_table = any(ext in {"xlsx", "png"} for ext in wanted)
        ok, reason = export_has_substance(
            content,
            table,
            images,
            require_table=requires_table,
            require_numeric_table="png" in wanted,
        )
        if not ok:
            return {"error": reason}

        out_dir = Path(settings.MEDIA_ROOT) / "ai_exports"
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.exception("export_document mkdir failed")
            return {"error": f"Could not create export folder: {exc}"}

        stem = _slugify(title)
        stamp = now().strftime("%Y%m%d-%H%M%S")
        files: list[dict] = []
        created_paths: list[Path] = []

        def _cleanup_created() -> None:
            for created in created_paths:
                try:
                    created.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Could not remove failed export %s", created)

        writers = {
            "docx": (self._write_docx, "Word"),
            "xlsx": (self._write_xlsx, "Excel"),
            "pdf": (self._write_pdf, "PDF"),
            "png": (self._write_png_chart, "PNG chart"),
        }
        # Shell-only Office files (title band, no body) stay tiny — refuse them.
        _MIN_BYTES = {"docx": 2500, "xlsx": 1800, "pdf": 400, "png": 200}

        for kind in wanted:
            writer, label = writers[kind]
            filename = f"{stem}-{stamp}.{kind}"
            path = out_dir / filename
            try:
                if kind == "docx":
                    writer(path, title, content, table, images=images)
                else:
                    writer(path, title, content, table)
                created_paths.append(path)
                size = path.stat().st_size if path.exists() else 0
                if size < _MIN_BYTES.get(kind, 0):
                    _cleanup_created()
                    return {
                        "error": (
                            f"{label} export refused — file was empty/shell-only "
                            f"({size} bytes). Re-run after steps produce real findings."
                        ),
                    }
                files.append({
                    "filename": filename,
                    "format": kind,
                    "path": f"/media/ai_exports/{filename}",
                    "size_bytes": size,
                })
            except Exception as exc:  # fail-visible, never fabricate a file
                logger.exception("export_document %s failed", kind)
                if path.exists() and path not in created_paths:
                    created_paths.append(path)
                _cleanup_created()
                return {"error": f"{label} export failed: {exc}"}

        if not files:
            return {"error": "No document was generated."}

        headers = (table or {}).get("headers") or []
        rows = (table or {}).get("rows") or []
        semantic_manifest = {
            "source": "structured_table",
            "headers": [str(value) for value in headers],
            "row_count": len(rows),
            "numeric_series": any(
                isinstance(row, (list, tuple))
                and any(_to_number(cell) is not None for cell in row[1:])
                for row in rows
            ),
        }
        for entry in files:
            entry["semantic_manifest"] = semantic_manifest

        # W5-C: persist into the plan's artifact store so the plan UI lists it
        # with a first-class download link. The frozen engine ToolContext has
        # no ``run_id``, so the owning plan is resolved from the thread-local
        # set by ``plans_service`` around the engine run. Sibling import
        # (same ``ai`` app) — not an upward domain-app import (RULE_20).
        artifact_ids: list = []
        try:
            from asgiref.sync import sync_to_async

            from ai.plans_service import (
                PlansService,
                get_current_plan_run,
            )

            run_id = get_current_plan_run()
            if run_id:
                # W6-C: the engine executes this plugin inside the run's event
                # loop, and ``resolve_export_step_index`` / ``store_artifact``
                # are sync Django-ORM calls — a direct call raises
                # ``SynchronousOnlyOperation`` (async-unsafe) and the whole
                # handoff silently no-ops (fail-visible catch below), so the
                # plan never gets its RunArtifact rows. Bridge through
                # ``sync_to_async`` (dedicated sub-thread, contextvars copied)
                # so the artifact store actually lands.
                step_index = await sync_to_async(
                    PlansService.resolve_export_step_index
                )(run_id)
                for entry in files:
                    local_path = out_dir / entry["filename"]
                    if not local_path.exists():
                        continue
                    stored = await sync_to_async(PlansService.store_artifact)(
                        run_id=run_id,
                        step_index=step_index,
                        name=entry["filename"],
                        content_bytes=local_path.read_bytes(),
                        mime_type=_MIME.get(entry["format"], "application/octet-stream"),
                    )
                    entry["artifact_id"] = stored["artifact_id"]
                    entry["download_url"] = stored["download_url"]
                    artifact_ids.append(stored["artifact_id"])
        except Exception:  # fail-visible — artifact storage must never break the export
            logger.exception("export_document store_artifact failed")

        return {
            "requires_confirmation": False,
            "action": "download",
            "title": title,
            "files": files,
            "artifact_ids": artifact_ids,
            "semantic_manifest": semantic_manifest,
            "message": (
                f"Exported “{title}” as "
                + ", ".join(f.get("format", "").upper() for f in files)
                + ". Use the download button(s) below."
            ),
        }

    # ── generators ─────────────────────────────────────────────────────────

    def _write_docx(
        self,
        path: Path,
        title: str,
        content: str,
        table: dict | None,
        images: list | None = None,
    ) -> None:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Pt, RGBColor

        doc = Document()
        # Compact operator typography — Title/Heading defaults are oversized.
        normal = doc.styles["Normal"]
        normal.font.name = "Calibri"
        normal.font.size = Pt(10.5)
        for style_name, size in (
            ("Title", 16),
            ("Heading 1", 13),
            ("Heading 2", 12),
            ("Heading 3", 11),
        ):
            try:
                style = doc.styles[style_name]
                style.font.name = "Calibri"
                style.font.size = Pt(size)
                style.font.color.rgb = RGBColor.from_string(_BRAND_TEAL)
            except KeyError:
                pass

        heading = doc.add_heading(title, level=1)
        for run in heading.runs:
            run.font.color.rgb = RGBColor.from_string(_BRAND_TEAL)
            run.font.size = Pt(16)

        for i, line in enumerate(_deliverable_identity_lines(run_id=_current_run_id())):
            para = doc.add_paragraph()
            run = para.add_run(line)
            run.italic = i > 0
            run.bold = i == 0
            run.font.size = Pt(9 if i else 10)
            run.font.color.rgb = RGBColor.from_string(
                _BRAND_TEAL if i == 0 else _BRAND_MUTED
            )
            para.alignment = WD_ALIGN_PARAGRAPH.LEFT

        prose, md_tables = parse_gfm_tables(content or "")
        if prose.strip():
            self._render_markdown_to_docx(doc, prose)
        for md_table in md_tables:
            self._render_table_docx(doc, md_table)
        if table:
            self._render_table_docx(doc, table)
        if images:
            self._embed_images_docx(doc, images)
        doc.save(str(path))

    @staticmethod
    def _embed_images_docx(doc, images: list) -> None:
        """Embed base64 PNG/JPEG figures into the Word document."""
        import base64
        import io

        from docx.shared import Inches, Pt, RGBColor

        for img in images[:6]:
            if not isinstance(img, dict):
                continue
            raw_b64 = str(img.get("image_b64") or "").strip()
            if not raw_b64:
                continue
            if "," in raw_b64 and raw_b64.lower().startswith("data:"):
                raw_b64 = raw_b64.split(",", 1)[1]
            try:
                blob = base64.b64decode(raw_b64, validate=False)
            except Exception:
                continue
            if len(blob) < 32:
                continue
            caption = str(img.get("caption") or "Figure").strip() or "Figure"
            cap = doc.add_paragraph()
            run = cap.add_run(caption)
            run.bold = True
            run.font.size = Pt(10)
            run.font.color.rgb = RGBColor.from_string(_BRAND_TEAL)
            try:
                doc.add_picture(io.BytesIO(blob), width=Inches(5.8))
            except Exception:
                logger.warning("export_document: skipped unreadable image (%s)", caption)

    @staticmethod
    def _shade_cell(cell, hex_fill: str) -> None:
        """Apply a solid background fill to a table cell (python-docx has no API)."""
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn

        tc_pr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), hex_fill)
        tc_pr.append(shd)

    def _render_table_docx(self, doc, table: dict) -> None:
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Pt, RGBColor

        headers = table.get("headers") or []
        rows = table.get("rows") or []
        if not headers:
            return
        doc.add_paragraph()
        t = doc.add_table(rows=1, cols=len(headers))
        t.style = "Table Grid"
        # Header row — teal fill, white bold text.
        for i, h in enumerate(headers):
            cell = t.rows[0].cells[i]
            cell.text = ""
            run = cell.paragraphs[0].add_run(str(h))
            run.bold = True
            run.font.size = Pt(10)
            run.font.color.rgb = RGBColor.from_string("FFFFFF")
            self._shade_cell(cell, _BRAND_TEAL)
        for ridx, row in enumerate(rows):
            is_total = bool(row) and str(row[0]).strip().upper().startswith("TOTAL")
            cells = t.add_row().cells
            for i in range(len(headers)):
                val = str(row[i]) if i < len(row) else ""
                cells[i].text = ""
                para = cells[i].paragraphs[0]
                run = para.add_run(val)
                run.font.size = Pt(9.5)
                if is_total:
                    run.bold = True
                if i > 0 and _looks_numeric(val):
                    para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                if is_total:
                    self._shade_cell(cells[i], _BRAND_BAND)
                elif ridx % 2 == 1:
                    self._shade_cell(cells[i], "F5F8F7")

    @staticmethod
    def _render_markdown_to_docx(doc, content: str) -> None:
        """Render markdown *prose* (headings, lists, paragraphs). GFM tables
        must already be stripped via ``parse_gfm_tables`` — any leftover pipe
        row is skipped so ``|---|`` never lands as a paragraph.
        """
        from docx.shared import Pt, RGBColor

        head_color = RGBColor.from_string(_BRAND_TEAL)

        def add_rich(paragraph, text: str) -> None:
            for idx, seg in enumerate(re.split(r"\*\*", text)):
                if not seg:
                    continue
                run = paragraph.add_run(seg)
                if idx % 2 == 1:
                    run.bold = True

        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # Never dump raw GFM table syntax into the Word body.
            if _split_gfm_row(stripped) is not None:
                continue
            if stripped.startswith("### "):
                h = doc.add_heading(stripped[4:], level=3)
                for r in h.runs:
                    r.font.color.rgb = head_color
                    r.font.size = Pt(11)
            elif stripped.startswith("## "):
                h = doc.add_heading(stripped[3:], level=2)
                for r in h.runs:
                    r.font.color.rgb = head_color
                    r.font.size = Pt(12)
            elif stripped.startswith("# "):
                h = doc.add_heading(stripped[2:], level=1)
                for r in h.runs:
                    r.font.color.rgb = head_color
                    r.font.size = Pt(13)
            elif re.match(r"^[-*•]\s+", stripped):
                add_rich(doc.add_paragraph(style="List Bullet"), re.sub(r"^[-*•]\s+", "", stripped))
            elif re.match(r"^\d+[.)]\s+", stripped):
                add_rich(doc.add_paragraph(style="List Number"), re.sub(r"^\d+[.)]\s+", "", stripped))
            elif stripped.startswith("> "):
                add_rich(doc.add_paragraph(), stripped[2:])
            else:
                add_rich(doc.add_paragraph(), stripped)

    def _write_xlsx(self, path: Path, title: str, content: str, table: dict | None) -> None:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter

        wb = Workbook()
        ws = wb.active
        ws.title = "Report"
        teal_fill = PatternFill("solid", fgColor=_BRAND_TEAL)
        band_fill = PatternFill("solid", fgColor=_BRAND_BAND)
        thin = Side(style="thin", color="D0D7DE")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        headers = (table or {}).get("headers") or []
        rows = (table or {}).get("rows") or []
        prose = content or ""
        md_tables: list[dict] = []
        if content:
            prose, md_tables = parse_gfm_tables(content)
            if not headers and md_tables:
                headers = list(md_tables[0].get("headers") or [])
                rows = list(md_tables[0].get("rows") or [])
                md_tables = md_tables[1:]
        ncols = max(3, len(headers))

        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
        title_cell = ws.cell(row=1, column=1, value=title)
        title_cell.font = Font(bold=True, size=15, color="FFFFFF")
        title_cell.fill = teal_fill
        title_cell.alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[1].height = 26

        id_lines = _deliverable_identity_lines(run_id=_current_run_id())
        for i, line in enumerate(id_lines):
            cell = ws.cell(row=2 + i, column=1, value=line)
            cell.font = Font(
                bold=(i == 0),
                italic=(i > 0),
                size=10 if i == 0 else 9,
                color=_BRAND_TEAL if i == 0 else _BRAND_MUTED,
            )

        row = 2 + len(id_lines) + 1
        if headers:
            for c, h in enumerate(headers, start=1):
                cell = ws.cell(row=row, column=c, value=str(h))
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = teal_fill
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = border
            header_row = row
            row += 1
            for ridx, r in enumerate(rows):
                is_total = bool(r) and str(r[0]).strip().upper().startswith("TOTAL")
                for c in range(len(headers)):
                    raw = r[c] if c < len(r) else ""
                    num = _to_number(raw) if c > 0 else None
                    cell = ws.cell(row=row, column=c + 1, value=num if num is not None else raw)
                    cell.border = border
                    if num is not None:
                        cell.alignment = Alignment(horizontal="right")
                        cell.number_format = "#,##0.00"
                    if is_total:
                        cell.font = Font(bold=True)
                        cell.fill = band_fill
                    elif ridx % 2 == 1:
                        cell.fill = band_fill
                row += 1
            ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
            for c in range(1, len(headers) + 1):
                longest = len(str(headers[c - 1]))
                for r in rows:
                    if c - 1 < len(r):
                        longest = max(longest, len(str(r[c - 1])))
                ws.column_dimensions[get_column_letter(c)].width = min(42, longest + 5)
            row += 1

        if prose.strip():
            ws2 = wb.create_sheet("Summary")
            ws2.column_dimensions["A"].width = 96
            rr = 1
            for line in prose.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                is_head = bool(re.match(r"^#+\s+", stripped))
                text = re.sub(r"^#+\s+", "", stripped)
                text = re.sub(r"^[-*•]\s+", "•  ", text).replace("**", "")
                cell = ws2.cell(row=rr, column=1, value=text[:4000])
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                if is_head:
                    cell.font = Font(bold=True, size=12, color=_BRAND_TEAL)
                rr += 1

        for tidx, md_t in enumerate(md_tables, start=2):
            th = md_t.get("headers") or []
            if not th:
                continue
            sheet = wb.create_sheet(f"Table{tidx}"[:31])
            for c, h in enumerate(th, start=1):
                cell = sheet.cell(row=1, column=c, value=str(h))
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = teal_fill
            for ridx, r in enumerate(md_t.get("rows") or [], start=2):
                for c in range(len(th)):
                    sheet.cell(row=ridx, column=c + 1, value=r[c] if c < len(r) else "")

        wb.save(str(path))

    def _write_pdf(self, path: Path, title: str, content: str, table: dict | None) -> None:
        """Unicode PDF with an embedded TTF. Helvetica cannot carry Arabic."""
        lines: list[str] = [title[:120], ""]
        lines.extend(_deliverable_identity_lines(run_id=_current_run_id()))
        lines.append("")
        if content:
            prose, md_tables = parse_gfm_tables(content)
            for raw in prose.splitlines():
                stripped = raw.strip()
                if not stripped:
                    continue
                text = re.sub(r"^#+\s+", "", stripped)
                text = re.sub(r"^[-*•]\s+", "• ", text).replace("**", "")
                lines.append(text)
            lines.append("")
            for md_t in md_tables:
                headers_md = md_t.get("headers") or []
                if headers_md:
                    lines.append(" | ".join(str(h) for h in headers_md))
                    lines.append("-" * min(90, max(8, len(lines[-1]))))
                    for row in (md_t.get("rows") or [])[:40]:
                        cells = [str(row[i]) if i < len(row) else "" for i in range(len(headers_md))]
                        lines.append(" | ".join(cells))
                    lines.append("")
        if table:
            headers = table.get("headers") or []
            rows = table.get("rows") or []
            if headers:
                lines.append(" | ".join(str(h) for h in headers))
                lines.append("-" * min(90, max(8, len(lines[-1]))))
                for row in rows[:40]:
                    cells = [str(row[i]) if i < len(row) else "" for i in range(len(headers))]
                    lines.append(" | ".join(cells))

        _render_pdf_lines(path, lines)

    def _write_png_chart(self, path: Path, title: str, content: str, table: dict | None) -> None:
        """PNG bar chart from the first numeric column of ``table`` (Pillow)."""
        from PIL import Image, ImageDraw, ImageFont

        width, height = 960, 540
        img = Image.new("RGB", (width, height), "#F7FAF9")
        draw = ImageDraw.Draw(img)
        try:
            font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
            font = ImageFont.truetype("DejaVuSans.ttf", 14)
            font_small = ImageFont.truetype("DejaVuSans.ttf", 11)
        except OSError:
            font_title = font = font_small = ImageFont.load_default()

        draw.rectangle([0, 0, width, 56], fill="#0B5F4E")
        draw.text((24, 16), (title or "Chart")[:80], fill="white", font=font_title)

        headers = (table or {}).get("headers") or []
        rows = (table or {}).get("rows") or []
        labels: list[str] = []
        values: list[float] = []
        if headers and rows:
            for row in rows[:12]:
                if not row:
                    continue
                num = None
                numeric_index = None
                for index, cell in enumerate(row[1:], start=1):
                    num = _to_number(cell)
                    if num is not None:
                        numeric_index = index
                        break
                if num is None:
                    continue
                dimensions = [
                    str(cell).strip()
                    for cell in row[:numeric_index]
                    if str(cell).strip()
                ]
                label = (dimensions[-1] if dimensions else str(row[0]))[:24]
                labels.append(label)
                values.append(abs(num))

        if not values:
            raise ValueError(
                "PNG chart requires a grounded numeric series in the export table."
            )

        plot_left, plot_top, plot_right, plot_bottom = 80, 100, width - 40, height - 60
        plot_w = plot_right - plot_left
        plot_h = plot_bottom - plot_top
        draw.rectangle([plot_left, plot_top, plot_right, plot_bottom], outline="#D0D7DE", width=1)

        vmax = max(values) or 1.0
        n = len(values)
        gap = 12
        bar_w = max(18, (plot_w - gap * (n + 1)) // max(n, 1))
        for i, (lab, val) in enumerate(zip(labels, values)):
            x0 = plot_left + gap + i * (bar_w + gap)
            bar_h = int((val / vmax) * (plot_h - 8))
            y0 = plot_bottom - bar_h
            draw.rectangle([x0, y0, x0 + bar_w, plot_bottom], fill="#0B5F4E")
            draw.text((x0, plot_bottom + 8), lab[:10], fill="#374151", font=font_small)
            draw.text((x0, y0 - 18), f"{val:,.0f}", fill="#0B5F4E", font=font)

        draw.text(
            (24, height - 28),
            "Pulse — AI Coworker chart · derived from export table",
            fill="#6B7280",
            font=font_small,
        )
        img.save(str(path), format="PNG")

