#!/usr/bin/env python3
"""Chairman brief: academic programme, outcomes, full project list."""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent / (
    "CAI-Alamein-Graduation-Studios-2026-27-Chairman-Decision-Brief.docx"
)

NAVY = "0B1F3A"
GOLD = "B8952C"
SLATE = "4A5560"
RULE = "D0D5DD"
CREAM = "F7F5EF"
PALE = "EEF2F6"
NOW = "E8F0E4"
WHITE = "FFFFFF"
BODY = "1C2430"

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_PR = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_DC = "http://purl.org/dc/elements/1.1/"
NS_CP = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
NS_DCT = "http://purl.org/dc/terms/"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"

# theme, project, the AI, outcome, impact
# Distilled from Stanford CS224N/CS224G, ETH LLM-safety theses, CMU HCI,
# PoliMi/energy conformal theses — then seated on labs you already run.
GRID: list[tuple[str, str, str, str, str]] = [
    (
        "Assistants",
        "Grounded copilot (cite or stay silent)",
        "A domain assistant that may speak a fact only if it can point to a retrieved passage or a host field. This is the EDU-RAG / grounded-QA line Stanford students are already publishing.",
        "On a frozen question set: extra-fact rate under a declared cap. Empty store → refuse. Ordinary search-and-summarise invents more.",
        "Every enterprise copilot fails this. Your Pulse grounding layer and campus / Moodle files are the host.",
    ),
    (
        "Agents",
        "Tool agent under human control",
        "A tool-using agent that can stage a write and must wait for a person. ETH’s safety group calls this control and oversight. Stanford CS224N is full of agents that do not do what they think.",
        "Zero unconfirmed host writes on a planted attack set (≥100 tries, including injections).",
        "This is the 2026 agent problem. Your Chat ≠ Agent split is the teaching design.",
    ),
    (
        "Evaluation",
        "Red-team and rubric eval as the thesis",
        "Build the test, not another chatbot. Automated red-team (ETH) plus a human rubric that an LLM-as-judge must match (Stanford RubricEval).",
        "Known-bad prompts fail. A stub cannot raise the score. Agreement with two human raters is reported.",
        "The most transferable AI skill. Your Pulse goldens and aast-med L0–L5 banks are the first corpus.",
    ),
    (
        "Education",
        "Course-grounded AI tutor",
        "An assistant over one real course: answers from the current materials only. Will not write the assignment. Stanford’s EDU-RAG and “pedagogically grounded reasoning” projects are this problem.",
        "Citation of a real passage meets a declared bar on two shortnames. Assignment-write probes refused 100%.",
        "Scales to a whole LMS. Medicine Moodle Ask is already the live host.",
    ),
    (
        "Medical AI",
        "Teach, do not treat",
        "A staff-facing medical assistant: may cite a teaching safety list. Must refuse “what dose for this patient”. CS224G lists Law & Medicine as a first-class area; CS224N has medical sycophancy and safety work.",
        "Care items refused 100%. Teaching items cited to a doctor-frozen list. A chatty clinical model fails the same bank.",
        "Doctors will supervise this. Your contraindication line and staff Ask contract are the seed. Not a device.",
    ),
    (
        "Education",
        "Span-grounded rubric scoring",
        "Score a student note against a rubric: a point needs a supporting span. Negation must not score. Stanford RubricEval + clinician-in-the-loop (CMU HCI) is the academic frame.",
        "Beats keyword matching on negation. κ with a doctor on a double-marked sample.",
        "Assessment AI examiners will accept. Your GradeVance OSCE pack is the baseline that already exists.",
    ),
    (
        "Medical AI",
        "Structured extraction from teaching notes",
        "Turn a teaching prescription or discharge into slots or codes. No slot without a phrase in the note. CS224G “data extraction”; CS224N clinical NER/RE — on teaching gold, not EHR.",
        "Slot / code accuracy vs double-annotated gold. Invented slots = 0.",
        "The NLP task hospitals later buy. Your encoding and completeness packs are the teaching stand-in.",
    ),
    (
        "Assistants",
        "Arabic–English grounded generation",
        "Same facts, both languages. An Arabic question must not be answered from an English paraphrase the model invented. Stanford CS224N has cross-lingual grounded-structure work; MENA data is scarce.",
        "Language match ≥98%. Every number still cited. English-only pipeline fails the Arabic bank.",
        "Publishable and regional. Your Pulse bilingual operator path is the seed.",
    ),
    (
        "Engineering",
        "Leak-free forecast under delayed sensors",
        "Multi-horizon forecast when last actuals arrive late. Must not use the future to predict the future. This is the load-forecasting literature, not a UCI homework series.",
        "Beats a recursive baseline on a leak-free holdout. Examiner can replay the cutoff.",
        "The method is general (grid, plant, water, campus). Your Gigacast engines and a public series if the campus licence is late.",
    ),
    (
        "Engineering",
        "Conformal forecast that abstains",
        "Same series, with conformal / selective prediction — the 2024–25 PoliMi and load-forecasting thesis line. Coverage must hold when data is stale or the day is a holiday.",
        "Coverage within a declared band of nominal on hard windows. Softmax-as-confidence fails.",
        "Operators pay for “I do not know”. Your Gigacast uncertainty / XAI line is the lab.",
    ),
]


def rpr(
    *,
    size: int = 22,
    bold: bool = False,
    color: str = BODY,
    font: str = "Calibri",
    italic: bool = False,
    caps: bool = False,
    cs: bool = False,
) -> str:
    bits = [
        f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:cs="{font}" w:eastAsia="{font}"/>',
        f'<w:sz w:val="{size}"/>',
        f'<w:szCs w:val="{size}"/>',
        f'<w:color w:val="{color}"/>',
    ]
    if bold:
        bits.append("<w:b/><w:bCs/>")
    if italic:
        bits.append("<w:i/><w:iCs/>")
    if caps:
        bits.append('<w:caps w:val="true"/>')
    if cs:
        bits.append("<w:rtl/>")
        bits.append('<w:cs w:val="true"/>')
    return "<w:rPr>" + "".join(bits) + "</w:rPr>"


def run(text: str, **kwargs) -> str:
    return f'<w:r>{rpr(**kwargs)}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def p(
    inner: str,
    *,
    before: int = 0,
    after: int = 100,
    align: str = "left",
    rtl: bool = False,
    keep: bool = False,
    spacing: int = 252,
) -> str:
    jc = f'<w:jc w:val="{align}"/>'
    bidi = '<w:bidi w:val="1"/>' if rtl else ""
    kn = "<w:keepNext/>" if keep else ""
    return (
        "<w:p><w:pPr>"
        f"{kn}{bidi}{jc}"
        f'<w:spacing w:before="{before}" w:after="{after}" w:line="{spacing}" w:lineRule="auto"/>'
        f"</w:pPr>{inner}</w:p>"
    )


def empty(after: int = 60) -> str:
    return p("", after=after)


def heading(n: str, title: str) -> str:
    return p(
        run(f"{n}   ", size=20, bold=True, color=GOLD)
        + run(title.upper(), size=20, bold=True, color=NAVY, caps=True),
        before=240,
        after=80,
        keep=True,
        spacing=240,
    )


def body(text: str, *, after: int = 110) -> str:
    return p(run(text, size=21, color=BODY), after=after)


def bullet(text: str) -> str:
    return p(
        run("–  ", size=21, bold=True, color=GOLD) + run(text, size=21, color=BODY),
        after=40,
        spacing=250,
    )


def page_break() -> str:
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def shade_cell(
    text: str,
    *,
    width: int,
    fill: str | None = None,
    color: str | None = None,
    bold: bool = False,
    size: int = 17,
    align: str = "left",
) -> str:
    shd = f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>' if fill else ""
    return (
        "<w:tc><w:tcPr>"
        f'<w:tcW w:w="{width}" w:type="dxa"/>'
        '<w:vAlign w:val="center"/>'
        f"{shd}"
        '<w:tcMar><w:top w:w="50" w:type="dxa"/><w:left w:w="70" w:type="dxa"/>'
        '<w:bottom w:w="50" w:type="dxa"/><w:right w:w="70" w:type="dxa"/></w:tcMar>'
        "</w:tcPr>"
        + p(run(text, size=size, bold=bold, color=color or BODY), after=0, align=align, spacing=230)
        + "</w:tc>"
    )


def table(
    headers: list[str],
    rows: list[list[str]],
    widths: list[int],
    *,
    size: int = 16,
    row_fill=None,
) -> str:
    total = sum(widths)
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    borders = (
        "<w:tblBorders>"
        f'<w:top w:val="single" w:sz="4" w:space="0" w:color="{RULE}"/>'
        f'<w:left w:val="single" w:sz="4" w:space="0" w:color="{RULE}"/>'
        f'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="{RULE}"/>'
        f'<w:right w:val="single" w:sz="4" w:space="0" w:color="{RULE}"/>'
        f'<w:insideH w:val="single" w:sz="4" w:space="0" w:color="{RULE}"/>'
        f'<w:insideV w:val="single" w:sz="4" w:space="0" w:color="{RULE}"/>'
        "</w:tblBorders>"
    )
    head = "".join(
        shade_cell(h, width=w, fill=NAVY, color=WHITE, bold=True, size=size)
        for h, w in zip(headers, widths)
    )
    body_rows = []
    for i, row in enumerate(rows):
        fill = row_fill(i, row) if row_fill else (CREAM if i % 2 == 0 else WHITE)
        cells = "".join(
            shade_cell(c, width=w, fill=fill, size=size, bold=(j == 0 or j == 1))
            for j, (c, w) in enumerate(zip(row, widths))
        )
        body_rows.append(f"<w:tr>{cells}</w:tr>")
    return (
        "<w:tbl><w:tblPr>"
        f'<w:tblW w:w="{total}" w:type="dxa"/>'
        '<w:tblLayout w:type="fixed"/>'
        f"{borders}</w:tblPr>"
        f"<w:tblGrid>{grid}</w:tblGrid>"
        f"<w:tr>{head}</w:tr>"
        + "".join(body_rows)
        + "</w:tbl>"
    )


def box(title: str, lines: list[str], *, accent: str = GOLD) -> str:
    inner = p(
        run(title, size=18, bold=True, color=NAVY, caps=True),
        after=70,
        spacing=230,
    ) + "".join(
        p(
            run(f"{i}.  ", size=20, bold=True, color=accent)
            + run(t, size=20, color=BODY),
            after=50,
            spacing=250,
        )
        for i, t in enumerate(lines, 1)
    )
    return (
        "<w:tbl><w:tblPr>"
        '<w:tblW w:w="9500" w:type="dxa"/>'
        "<w:tblBorders>"
        f'<w:top w:val="single" w:sz="8" w:space="0" w:color="{accent}"/>'
        f'<w:left w:val="single" w:sz="20" w:space="0" w:color="{accent}"/>'
        f'<w:bottom w:val="single" w:sz="8" w:space="0" w:color="{RULE}"/>'
        f'<w:right w:val="single" w:sz="4" w:space="0" w:color="{RULE}"/>'
        "</w:tblBorders></w:tblPr>"
        '<w:tblGrid><w:gridCol w:w="9500"/></w:tblGrid>'
        "<w:tr><w:tc><w:tcPr>"
        '<w:tcW w:w="9500" w:type="dxa"/>'
        f'<w:shd w:val="clear" w:color="auto" w:fill="{CREAM}"/>'
        '<w:tcMar><w:top w:w="120" w:type="dxa"/><w:left w:w="160" w:type="dxa"/>'
        '<w:bottom w:w="120" w:type="dxa"/><w:right w:w="160" w:type="dxa"/></w:tcMar>'
        f"</w:tcPr>{inner}</w:tc></w:tr></w:tbl>"
    )


def document_xml() -> str:
    parts: list[str] = []

    parts.append(
        p(
            run("AASTMT Alamein  ·  College of Artificial Intelligence", size=16, bold=True, color=NAVY),
            after=20,
        )
    )
    parts.append(
        p(run("Suggested graduation projects", size=32, bold=True, color=NAVY), before=20, after=8)
    )
    parts.append(
        p(
            run("Ten AI theses  ·  what leading labs actually assign  ·  seated on work already here", size=19, color=GOLD),
            after=12,
        )
    )
    parts.append(
        p(
            run(
                "Distilled from Stanford CS224N / CS224G (grounded RAG, agents, RubricEval, education and medical AI), ETH LLM safety (control, red-team), CMU HCI (clinician–AI), and current conformal load-forecast theses. Each row is one AI thesis. The last column names the local seed — not the title.",
                size=19,
                color=BODY,
            ),
            after=140,
        )
    )

    def grid_fill(_i: int, row: list[str]) -> str:
        t = row[0]
        if t in ("Assistants", "Agents"):
            return PALE
        if t in ("Education", "Evaluation"):
            return NOW
        if t == "Medical AI":
            return CREAM
        return WHITE

    parts.append(
        table(
            ["Theme", "Project", "What the AI does", "Outcome (the test)", "Impact"],
            [[a, b, c, d, e] for a, b, c, d, e in GRID],
            [1300, 1800, 2300, 2200, 1900],
            size=16,
            row_fill=grid_fill,
        )
    )

    sect = (
        "<w:sectPr>"
        '<w:headerReference w:type="default" r:id="rId1"/>'
        '<w:footerReference w:type="default" r:id="rId2"/>'
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1360" w:right="1080" w:bottom="1200" w:left="1080" '
        'w:header="520" w:footer="520" w:gutter="0"/>'
        '<w:cols w:space="708"/>'
        '<w:docGrid w:linePitch="360"/>'
        "</w:sectPr>"
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{NS_W}" xmlns:r="{NS_R}">'
        f"<w:body>{''.join(parts)}{sect}</w:body></w:document>"
    )


def styles_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{NS_W}">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Arial"/>
        <w:sz w:val="22"/><w:szCs w:val="22"/>
        <w:color w:val="{BODY}"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr><w:spacing w:after="100" w:line="252" w:lineRule="auto"/></w:pPr>
    </w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/><w:qFormat/>
  </w:style>
</w:styles>
"""


def header_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:hdr xmlns:w="{NS_W}">
  <w:p>
    <w:pPr>
      <w:pBdr><w:bottom w:val="single" w:sz="12" w:space="3" w:color="{GOLD}"/></w:pBdr>
      <w:tabs><w:tab w:val="right" w:pos="9746"/></w:tabs>
      <w:spacing w:after="60" w:before="0"/>
    </w:pPr>
    <w:r>{rpr(size=14, bold=True, color=NAVY, caps=True)}<w:t>AASTMT ALAMEIN  ·  COLLEGE OF AI</w:t></w:r>
    <w:r>{rpr(size=14, color=SLATE)}<w:tab/><w:t>Suggested projects  ·  2026/27</w:t></w:r>
  </w:p>
</w:hdr>
"""


def footer_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="{NS_W}">
  <w:p>
    <w:pPr>
      <w:pBdr><w:top w:val="single" w:sz="6" w:space="4" w:color="{RULE}"/></w:pBdr>
      <w:tabs><w:tab w:val="right" w:pos="9746"/></w:tabs>
      <w:spacing w:before="60"/>
    </w:pPr>
    <w:r>{rpr(size=13, color=SLATE)}<w:t>AI first  ·  Teaching data only  ·  Not a medical device</w:t></w:r>
    <w:r>{rpr(size=13, color=SLATE)}<w:tab/><w:t>Page </w:t></w:r>
    <w:r>{rpr(size=13, color=SLATE)}<w:fldChar w:fldCharType="begin"/></w:r>
    <w:r>{rpr(size=13, color=SLATE)}<w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>
    <w:r>{rpr(size=13, color=SLATE)}<w:fldChar w:fldCharType="end"/></w:r>
    <w:r>{rpr(size=13, color=SLATE)}<w:t> of </w:t></w:r>
    <w:r>{rpr(size=13, color=SLATE)}<w:fldChar w:fldCharType="begin"/></w:r>
    <w:r>{rpr(size=13, color=SLATE)}<w:instrText xml:space="preserve"> NUMPAGES </w:instrText></w:r>
    <w:r>{rpr(size=13, color=SLATE)}<w:fldChar w:fldCharType="end"/></w:r>
  </w:p>
</w:ftr>
"""


def content_types() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="{NS_CT}">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
  <Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""


def rels_root() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{NS_PR}">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""


def rels_doc() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{NS_PR}">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
</Relationships>
"""


def settings_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="{NS_W}">
  <w:displayBackgroundShape/>
  <w:defaultTabStop w:val="720"/>
  <w:characterSpacingControl w:val="doNotCompress"/>
</w:settings>
"""


def core_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="{NS_CP}" xmlns:dc="{NS_DC}" xmlns:dcterms="{NS_DCT}" xmlns:xsi="{NS_XSI}">
  <dc:title>A proposal for this year’s graduation projects — three studios</dc:title>
  <dc:subject>College of AI, AASTMT Alamein</dc:subject>
  <dc:creator>Dr. Ahmed, College of Medicine, AASTMT</dc:creator>
  <cp:lastModifiedBy>Dr. Ahmed, College of Medicine, AASTMT</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">2026-09-30T09:00:00Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">2026-09-30T09:15:00Z</dcterms:modified>
  <dc:description>Academic decision brief: AI coworkers, medical teaching solutions, engineering solutions.</dc:description>
  <cp:revision>2</cp:revision>
</cp:coreProperties>
"""


def app_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
  <Application>AASTMT College of AI</Application>
  <Company>Arab Academy for Science, Technology &amp; Maritime Transport</Company>
</Properties>
"""


def main() -> None:
    files = {
        "[Content_Types].xml": content_types(),
        "_rels/.rels": rels_root(),
        "word/document.xml": document_xml(),
        "word/styles.xml": styles_xml(),
        "word/header1.xml": header_xml(),
        "word/footer1.xml": footer_xml(),
        "word/_rels/document.xml.rels": rels_doc(),
        "word/settings.xml": settings_xml(),
        "docProps/core.xml": core_xml(),
        "docProps/app.xml": app_xml(),
    }
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data.encode("utf-8"))
    print(OUT)


if __name__ == "__main__":
    main()
