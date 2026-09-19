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


@pytest.mark.asyncio
async def test_export_refuses_hollow_placeholder(plugin, tmp_path):
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        result = await plugin.execute(
            {
                "title": "Empty Report",
                "format": "docx",
                "content": "[Placeholder for insights]\n[Chart and table to be inserted]",
            },
            ctx=None,
        )
    assert "error" in result
    assert "refused" in result["error"].lower() or "findings" in result["error"].lower()


@pytest.mark.asyncio
async def test_export_docx_embeds_image(plugin, tmp_path):
    # Minimal 1x1 PNG
    import base64

    png = base64.b64encode(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
        )
    ).decode("ascii")
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        result = await plugin.execute(
            {
                "title": "With Chart",
                "format": "docx",
                "content": "## Findings\n- Real measured result.",
                "images": [{"caption": "Salary chart", "image_b64": png}],
            },
            ctx=None,
        )
    assert "error" not in result, result
    path = Path(tmp_path) / "ai_exports" / result["files"][0]["filename"]
    assert path.exists()
    assert path.read_bytes()[:2] == b"PK"

