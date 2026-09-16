"""``export_document`` — generate Word (.docx) / Excel (.xlsx) artifacts.

This is the missing "deliverable" primitive for the workspace chat agent:
after a study, audit, or research task the agent can produce a real,
downloadable report instead of only chat prose.  ``format`` selects the
output (``docx``, ``xlsx``, or ``both``); content is accepted either as
markdown ``content`` (rendered to paragraphs / headings / bullets) and/or a
``table`` (headers + rows → a sheet / Word table).

Files are written under ``MEDIA_ROOT/ai_exports/`` and surfaced to chat as a
``download`` action — the UI renders a real download link (never a raw
server path the user must copy).

Guardrails honored (non-negotiable):

  * **RULE_20** — zero upward imports: only stdlib + ``django.conf`` (for
    ``MEDIA_ROOT``) + ``openpyxl`` / ``docx``.  No domain-app models/views.
  * **RULE_21** — file generation is **non-mutating to user data**; it writes
    a fresh artifact into a scratch media folder, so
    ``requires_confirmation=False`` (the user explicitly asked for the export;
    nothing in their records is created or changed).
  * **RULE_23** — outcome copy: result speaks in product terms ("Download the
    XLSX report") and never leaks engine class names.
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

_SAFE_FMT = {"docx", "xlsx"}

_MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _slugify(value: str) -> str:
    value = re.sub(r"[^\w\s-]", "", value or "").strip().lower()
    value = re.sub(r"[-\s]+", "-", value)
    return value[:60] or "document"


# Brand palette for a polished, consistent look across DOCX + XLSX.
_BRAND_TEAL = "0B5F4E"
_BRAND_BAND = "EAF3F0"
_BRAND_MUTED = "6B7280"


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
        "Generate a downloadable Word (.docx) and/or Excel (.xlsx) document "
        "from the conversation's findings — e.g. 'export this study as a Word "
        "report and an Excel comparison table'. Provide a title, optional "
        "markdown content, and/or a table (headers + rows). Returns a download "
        "link surfaced in chat."
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
                "enum": ["docx", "xlsx", "both"],
                "description": "Which formats to generate. Default: both.",
            },
            "content": {
                "type": "string",
                "description": (
                    "Markdown body: '# Heading', '## Subheading', '- bullet', "
                    "'1. item', blank-line-separated paragraphs. Rendered into "
                    "the Word document (and a summary sheet for Excel)."
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
        },
        "required": ["title"],
    }
    requires_confirmation = False
    capability: str | None = None
    app_identifier: str | None = None

    async def execute(self, args: dict, *, ctx) -> dict:
        title = (args.get("title") or "").strip()
        if not title:
            return {"error": "A title is required — e.g. 'Carbon Standards Study'."}

        fmt = (args.get("format") or "both").strip().lower()
        if fmt not in ("docx", "xlsx", "both"):
            fmt = "both"

        content = (args.get("content") or "").strip()
        table = args.get("table") or None

        out_dir = Path(settings.MEDIA_ROOT) / "ai_exports"
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.exception("export_document mkdir failed")
            return {"error": f"Could not create export folder: {exc}"}

        stem = _slugify(title)
        stamp = now().strftime("%Y%m%d-%H%M%S")
        files: list[dict] = []

        if fmt in ("docx", "both"):
            filename = f"{stem}-{stamp}.docx"
            path = out_dir / filename
            try:
                self._write_docx(path, title, content, table)
                files.append({
                    "filename": filename,
                    "format": "docx",
                    "path": f"/media/ai_exports/{filename}",
                })
            except Exception as exc:  # fail-visible, never fabricate a file
                logger.exception("export_document docx failed")
                return {"error": f"Word export failed: {exc}"}

        if fmt in ("xlsx", "both"):
            filename = f"{stem}-{stamp}.xlsx"
            path = out_dir / filename
            try:
                self._write_xlsx(path, title, content, table)
                files.append({
                    "filename": filename,
                    "format": "xlsx",
                    "path": f"/media/ai_exports/{filename}",
                })
            except Exception as exc:
                logger.exception("export_document xlsx failed")
                return {"error": f"Excel export failed: {exc}"}

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

    def _write_docx(self, path: Path, title: str, content: str, table: dict | None) -> None:
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

        sub = doc.add_paragraph()
        sub_run = sub.add_run(
            f"Generated {now().strftime('%B %d, %Y')}  ·  Pulse Agent deliverable"
        )
        sub_run.italic = True
        sub_run.font.size = Pt(9)
        sub_run.font.color.rgb = RGBColor.from_string(_BRAND_MUTED)
        sub.alignment = WD_ALIGN_PARAGRAPH.LEFT

        if content:
            self._render_markdown_to_docx(doc, content)
        if table:
            self._render_table_docx(doc, table)
        doc.save(str(path))

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
        ws.cell(
            row=2, column=1,
            value=f"Generated {now().strftime('%B %d, %Y')} · Pulse Agent deliverable",
        ).font = Font(italic=True, size=9, color=_BRAND_MUTED)

        row = 4
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

