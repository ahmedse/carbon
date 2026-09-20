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
                "type": "object",
                "description": "Optional structured table for Excel / Word.",
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
        table = args.get("table") or None
        images = args.get("images") if isinstance(args.get("images"), list) else []

        # Fail-visible substance gate: never ship hollow, mid-run, or title-only packs.
        ok, reason = export_has_substance(content, table, images)
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
                size = path.stat().st_size if path.exists() else 0
                if size < _MIN_BYTES.get(kind, 0):
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        pass
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
                return {"error": f"{label} export failed: {exc}"}

        if not files:
            return {"error": "No document was generated."}

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
        # Normal body typography
        normal = doc.styles["Normal"]
        normal.font.name = "Calibri"
        normal.font.size = Pt(10.5)

        heading = doc.add_heading(title, level=0)
        for run in heading.runs:
            run.font.color.rgb = RGBColor.from_string(_BRAND_TEAL)

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

        if content:
            self._render_markdown_to_docx(doc, content)
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
        from docx.shared import RGBColor

        head_color = RGBColor.from_string(_BRAND_TEAL)

        def add_rich(paragraph, text: str) -> None:
            # Split on ** for inline bold; even segments plain, odd segments bold.
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
            if stripped.startswith("### "):
                h = doc.add_heading(stripped[4:], level=3)
                for r in h.runs:
                    r.font.color.rgb = head_color
            elif stripped.startswith("## "):
                h = doc.add_heading(stripped[3:], level=2)
                for r in h.runs:
                    r.font.color.rgb = head_color
            elif stripped.startswith("# "):
                h = doc.add_heading(stripped[2:], level=1)
                for r in h.runs:
                    r.font.color.rgb = head_color
            elif re.match(r"^[-*•]\s+", stripped):
                add_rich(doc.add_paragraph(style="List Bullet"), re.sub(r"^[-*•]\s+", "", stripped))
            elif re.match(r"^\d+[.)]\s+", stripped):
                add_rich(doc.add_paragraph(style="List Number"), re.sub(r"^\d+[.)]\s+", "", stripped))
            elif stripped.startswith("> "):
                add_rich(doc.add_paragraph(stripped[2:]), "")
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
            # Auto-fit column widths from header + cell content.
            for c in range(1, len(headers) + 1):
                longest = len(str(headers[c - 1]))
                for r in rows:
                    if c - 1 < len(r):
                        longest = max(longest, len(str(r[c - 1])))
                ws.column_dimensions[get_column_letter(c)].width = min(42, longest + 5)
            row += 1

        if content:
            ws2 = wb.create_sheet("Summary")
            ws2.column_dimensions["A"].width = 96
            rr = 1
            for line in content.splitlines():
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

        wb.save(str(path))

    def _write_pdf(self, path: Path, title: str, content: str, table: dict | None) -> None:
        """Minimal PDF 1.4 (Helvetica) — no reportlab dependency."""
        lines: list[str] = [title[:120], ""]
        lines.extend(_deliverable_identity_lines(run_id=_current_run_id()))
        lines.append("")
        if content:
            for raw in content.splitlines():
                stripped = raw.strip()
                if not stripped:
                    continue
                text = re.sub(r"^#+\s+", "", stripped)
                text = re.sub(r"^[-*•]\s+", "• ", text).replace("**", "")
                while len(text) > 90:
                    lines.append(text[:90])
                    text = text[90:]
                lines.append(text[:90])
            lines.append("")
        if table:
            headers = table.get("headers") or []
            rows = table.get("rows") or []
            if headers:
                lines.append(" | ".join(str(h) for h in headers))
                lines.append("-" * min(90, max(8, len(lines[-1]))))
                for row in rows[:40]:
                    cells = [str(row[i]) if i < len(row) else "" for i in range(len(headers))]
                    lines.append(" | ".join(cells)[:90])

        def esc(s: str) -> str:
            return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

        y0 = 800
        leading = 14
        max_lines = min(len(lines), 52)
        content_ops = ["BT", "/F1 11 Tf", "14 TL", f"50 {y0} Td"]
        for i, line in enumerate(lines[:max_lines]):
            if i == 0:
                content_ops.append("/F1 16 Tf")
                content_ops.append(f"({esc(line)}) Tj")
                content_ops.append("/F1 11 Tf")
            else:
                content_ops.append(f"({esc(line)}) Tj")
            content_ops.append(f"0 -{leading} Td")
        content_ops.append("ET")
        stream = "\n".join(content_ops).encode("latin-1", errors="replace")

        objects: list[bytes] = []
        objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
        objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
        objects.append(
            b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
        )
        objects.append(
            f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("ascii")
            + stream
            + b"\nendstream\nendobj\n"
        )
        objects.append(
            b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n"
        )

        out = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for obj in objects:
            offsets.append(len(out))
            out.extend(obj)
        xref_pos = len(out)
        out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        out.extend(b"0000000000 65535 f \n")
        for off in offsets[1:]:
            out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
        out.extend(
            f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n".encode("ascii")
        )
        path.write_bytes(bytes(out))

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
                label = str(row[0])[:18]
                num = None
                for cell in row[1:]:
                    num = _to_number(cell)
                    if num is not None:
                        break
                if num is None:
                    continue
                labels.append(label)
                values.append(abs(num))

        if not values:
            bullets = [
                ln.strip()
                for ln in (content or "").splitlines()
                if re.match(r"^[-*•]\s+", ln.strip())
            ]
            if bullets:
                labels = [re.sub(r"^[-*•]\s+", "", b)[:18] for b in bullets[:6]]
                values = [float(max(1, len(b))) for b in labels]
            else:
                labels = ["Findings", "Actions", "Risks"]
                values = [3.0, 2.0, 1.0]

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

