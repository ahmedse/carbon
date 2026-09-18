"""Unit tests for export_document PDF / PNG / pack formats."""

from __future__ import annotations

from pathlib import Path

import pytest
from django.test import override_settings

from ai.plugins.export_document import ExportDocument


@pytest.fixture
def plugin():
    return ExportDocument()


@pytest.mark.asyncio
async def test_export_pack_writes_four_formats(plugin, tmp_path):
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        result = await plugin.execute(
            {
                "title": "Board Pack Demo",
                "format": "pack",
                "content": "## Summary\n- Headcount up\n- GOSI stable\n",
                "table": {
                    "headers": ["Metric", "Value"],
                    "rows": [["Headcount", "529"], ["GOSI", "184220"]],
                },
            },
            ctx=None,
        )

    assert "error" not in result, result
    formats = {f["format"] for f in result["files"]}
    assert formats == {"docx", "xlsx", "pdf", "png"}
    out = Path(tmp_path) / "ai_exports"
    for entry in result["files"]:
        path = out / entry["filename"]
        assert path.exists()
        assert path.stat().st_size > 40
    pdf = next(f for f in result["files"] if f["format"] == "pdf")
    assert (out / pdf["filename"]).read_bytes()[:5] == b"%PDF-"
    png = next(f for f in result["files"] if f["format"] == "png")
    assert (out / png["filename"]).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.asyncio
async def test_export_pdf_only(plugin, tmp_path):
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        result = await plugin.execute(
            {"title": "PDF Only", "format": "pdf", "content": "Hello PDF"},
            ctx=None,
        )
    assert "error" not in result
    assert [f["format"] for f in result["files"]] == ["pdf"]


@pytest.mark.asyncio
async def test_export_png_fallback_without_table(plugin, tmp_path):
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        result = await plugin.execute(
            {
                "title": "Chart Fallback",
                "format": "png",
                "content": "- Alpha finding\n- Beta finding\n",
            },
            ctx=None,
        )
    assert "error" not in result
    assert result["files"][0]["format"] == "png"
