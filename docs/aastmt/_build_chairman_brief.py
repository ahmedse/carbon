#!/usr/bin/env python3
"""Build the Chairman decision brief (OOXML, stdlib only)."""

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
    return f"<w:r>{rpr(**kwargs)}<w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r>"


def p(
    inner: str,
    *,
    before: int = 0,
    after: int = 120,
    align: str = "left",
    rtl: bool = False,
    keep: bool = False,
    spacing: int = 276,
) -> str:
    jc = f'<w:jc w:val="{align}"/>'
    bidi = '<w:bidi w:val="1"/>' if rtl else ""
    kn = "<w:keepNext/>" if keep else ""
    return (
        "<w:p>"
        "<w:pPr>"
        f"{kn}{bidi}{jc}"
        f'<w:spacing w:before="{before}" w:after="{after}" w:line="{spacing}" w:lineRule="auto"/>'
        "</w:pPr>"
        f"{inner}"
        "</w:p>"
    )


def empty(after: int = 80) -> str:
    return p("", after=after)


def heading(text: str) -> str:
    return p(
        run(text.upper(), size=21, bold=True, color=NAVY, caps=True),
        before=280,
        after=100,
        keep=True,
        spacing=240,
    )


def body(text: str, *, after: int = 140) -> str:
    return p(run(text, size=21, color=BODY), after=after, spacing=276)


def bullet(text: str) -> str:
    return p(
        run("–  ", size=21, color=GOLD, bold=True) + run(text, size=21, color=BODY),
        after=60,
        spacing=260,
    )


def shade_cell(
    text_xml: str,
    *,
    width: int,
    fill: str | None = None,
    color: str | None = None,
    bold: bool = False,
    size: int = 18,
    align: str = "left",
    valign: str = "center",
) -> str:
    shd = f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>' if fill else ""
    return (
        "<w:tc>"
        "<w:tcPr>"
        f'<w:tcW w:w="{width}" w:type="dxa"/>'
        f'<w:vAlign w:val="{valign}"/>'
        f"{shd}"
        '<w:tcMar><w:top w:w="60" w:type="dxa"/><w:left w:w="80" w:type="dxa"/>'
        '<w:bottom w:w="60" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tcMar>'
        "</w:tcPr>"
        + p(
            run(text_xml, size=size, bold=bold, color=color or BODY),
            after=0,
            align=align,
            spacing=240,
        )
        + "</w:tc>"
    )


def table(headers: list[str], rows: list[list[str]], widths: list[int]) -> str:
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
    head_cells = "".join(
        shade_cell(h, width=w, fill=NAVY, color=WHITE, bold=True, size=16)
        for h, w in zip(headers, widths)
    )
    body_rows = []
    for i, row in enumerate(rows):
        fill = CREAM if i % 2 == 0 else WHITE
        cells = "".join(
            shade_cell(c, width=w, fill=fill, size=17, bold=(j == 0))
            for j, (c, w) in enumerate(zip(row, widths))
        )
        body_rows.append(f"<w:tr>{cells}</w:tr>")
    return (
        "<w:tbl>"
        "<w:tblPr>"
        f'<w:tblW w:w="{total}" w:type="dxa"/>'
        '<w:tblLayout w:type="fixed"/>'
        f"{borders}"
        "</w:tblPr>"
        f"<w:tblGrid>{grid}</w:tblGrid>"
        f"<w:tr>{head_cells}</w:tr>"
        + "".join(body_rows)
        + "</w:tbl>"
    )


def memo_row(label: str, value: str, w1: int = 1800, w2: int = 7700) -> str:
    return (
        "<w:tr>"
        + shade_cell(label, width=w1, fill=PALE, color=NAVY, bold=True, size=17)
        + shade_cell(value, width=w2, fill=WHITE, size=17)
        + "</w:tr>"
    )


def memo_table() -> str:
    rows = [
        memo_row("To", "The Chairman, College of Artificial Intelligence"),
        memo_row("Campus", "AASTMT — Alamein"),
        memo_row(
            "From",
            "Dr. Ahmed  ·  College of Medicine, AASTMT  ·  Industrial supervisor (proposed)",
        ),
        memo_row("Date", "30 September 2026"),
        memo_row("Ref.", "CAI-ALM/GP/2026-27"),
        memo_row(
            "Subject",
            "Graduation-project studios, academic year 2026/27 — decision requested",
        ),
        memo_row("Classification", "Internal  ·  For decision"),
    ]
    return (
        "<w:tbl>"
        "<w:tblPr>"
        '<w:tblW w:w="9500" w:type="dxa"/>'
        '<w:tblLayout w:type="fixed"/>'
        "<w:tblBorders>"
        f'<w:top w:val="single" w:sz="4" w:space="0" w:color="{RULE}"/>'
        f'<w:left w:val="nil"/>'
        f'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="{RULE}"/>'
        f'<w:right w:val="nil"/>'
        f'<w:insideH w:val="single" w:sz="4" w:space="0" w:color="{RULE}"/>'
        f'<w:insideV w:val="nil"/>'
        "</w:tblBorders>"
        "</w:tblPr>"
        '<w:tblGrid><w:gridCol w:w="1800"/><w:gridCol w:w="7700"/></w:tblGrid>'
        + "".join(rows)
        + "</w:tbl>"
    )


def decision_box() -> str:
    items = [
        "Assign 8–12 graduating students to the four studios below — not thirty loose chatbot titles.",
        "Name one independent academic co-examiner per studio.",
        "Invite the College of Medicine to name, by week 3: one clinical pharmacologist (Studio 3) and one coding clinician or OSCE lead (Studio 4). If only one doctor is available, Studio 3 proceeds; Studio 4 uses gold already on campus.",
        "Issue, in month one, a research-ethics covering letter: teaching data only; not a medical device; not for patient care.",
        "Confirm IP: students own thesis code (MIT or Apache-2.0). The Academy and the industrial laboratory retain a non-exclusive licence to teach from it.",
    ]
    inner = p(
        run("DECISION REQUESTED", size=20, bold=True, color=NAVY, caps=True),
        after=80,
        spacing=240,
    ) + "".join(
        p(
            run(f"{i}.  ", size=20, bold=True, color=GOLD)
            + run(t, size=20, color=BODY),
            after=70,
            spacing=260,
        )
        for i, t in enumerate(items, 1)
    )
    return (
        "<w:tbl>"
        "<w:tblPr>"
        '<w:tblW w:w="9500" w:type="dxa"/>'
        "<w:tblBorders>"
        f'<w:top w:val="single" w:sz="12" w:space="0" w:color="{GOLD}"/>'
        f'<w:left w:val="single" w:sz="24" w:space="0" w:color="{GOLD}"/>'
        f'<w:bottom w:val="single" w:sz="12" w:space="0" w:color="{GOLD}"/>'
        f'<w:right w:val="single" w:sz="4" w:space="0" w:color="{RULE}"/>'
        "</w:tblBorders>"
        "</w:tblPr>"
        '<w:tblGrid><w:gridCol w:w="9500"/></w:tblGrid>'
        "<w:tr>"
        "<w:tc>"
        "<w:tcPr>"
        '<w:tcW w:w="9500" w:type="dxa"/>'
        f'<w:shd w:val="clear" w:color="auto" w:fill="{CREAM}"/>'
        '<w:tcMar><w:top w:w="140" w:type="dxa"/><w:left w:w="180" w:type="dxa"/>'
        '<w:bottom w:w="140" w:type="dxa"/><w:right w:w="180" w:type="dxa"/></w:tcMar>'
        "</w:tcPr>"
        f"{inner}"
        "</w:tc>"
        "</w:tr>"
        "</w:tbl>"
    )


def document_xml() -> str:
    parts: list[str] = []

    # Letterhead
    parts.append(
        p(
            run(
                "الأكاديمية العربية للعلوم والتكنولوجيا والنقل البحري",
                size=20,
                bold=True,
                color=NAVY,
                font="Arial",
                cs=True,
            ),
            align="right",
            rtl=True,
            after=40,
            spacing=240,
        )
    )
    parts.append(
        p(
            run(
                "فرع العلمين  ·  كلية الذكاء الاصطناعي",
                size=17,
                color=SLATE,
                font="Arial",
                cs=True,
            ),
            align="right",
            rtl=True,
            after=80,
            spacing=220,
        )
    )
    parts.append(
        p(
            run(
                "ARAB ACADEMY FOR SCIENCE, TECHNOLOGY & MARITIME TRANSPORT",
                size=18,
                bold=True,
                color=NAVY,
                caps=True,
            ),
            after=20,
            spacing=220,
        )
    )
    parts.append(
        p(
            run("Alamein Campus  ·  College of Artificial Intelligence", size=18, color=SLATE),
            after=40,
            spacing=220,
        )
    )
    parts.append(
        p(
            run("DECISION BRIEF", size=36, bold=True, color=NAVY),
            before=80,
            after=20,
            spacing=240,
        )
    )
    parts.append(
        p(
            run(
                "Graduation-project programme   ·   Academic year 2026 / 27",
                size=20,
                color=GOLD,
                italic=True,
            ),
            after=160,
            spacing=240,
        )
    )

    parts.append(memo_table())
    parts.append(empty(160))
    parts.append(decision_box())

    parts.append(heading("1.  Why this form"))
    parts.append(
        body(
            "Industry will not hire a demonstration chatbot. Examiners should not have to. "
            "This year the College should run four studios, each attacking one industrial failure, "
            "on a frozen teaching pack, with a claim an independent examiner can rerun from the student repository."
        )
    )
    parts.append(
        body(
            "The College of Medicine will co-supervise two studios. Doctors write and freeze teaching gold. "
            "They do not open patient records. Commercial platforms are laboratories. Rebuilding a company is not the title."
        )
    )

    parts.append(heading("2.  This year — four studios"))
    parts.append(
        table(
            ["Studio", "The problem", "N", "Medicine"],
            [
                [
                    "1  Energy",
                    "Forecasts that remain honest when last actuals are 24–72 hours late — and that refuse when coverage would be a guess.",
                    "2–3",
                    "—",
                ],
                [
                    "2  Campus assistant",
                    "Every operational figure cited to evidence. No silent write. A naïve retrieval baseline fails the same bank.",
                    "3",
                    "—",
                ],
                [
                    "3  Safe prescribing",
                    "An alert cites a versioned pack row, or it is silent. Incomplete and renal-blind scripts fail as a second test. Not a medical device.",
                    "2–3",
                    "Clinical pharmacology",
                ],
                [
                    "4  Clinical encoding",
                    "A code without a span in the original note is refused. An Arabic note is not coded from an English paraphrase the model invented.",
                    "2–3",
                    "Coder or OSCE lead",
                ],
            ],
            [1700, 5000, 800, 2000],
        )
    )
    parts.append(empty(80))
    parts.append(
        body(
            "A thirty-card catalogue exists for later years and for fallbacks. We will not run thirty theses. "
            "If a data pack is not bound by week 4, the studio swaps to a named fallback. We do not delay the year."
        )
    )

    parts.append(heading("3.  What already exists"))
    parts.append(
        bullet(
            "College of Medicine Moodle already hosts a page-grounded Ask assistant: cite the current page or stay silent; refuse clinical advice, assignment writing, and the question bank."
        )
    )
    parts.append(
        bullet(
            "Teaching packs already exist for an abdominal OSCE note, a urinalysis OSPE, and an appendicitis case. Today they score by keyword. That keyword scorer is the baseline a student must beat."
        )
    )
    parts.append(
        bullet(
            "Alamein campus energy, fuel, and water inventories exist as a teaching tenant. Studio 2 reads them. It does not touch production finance or payroll."
        )
    )
    parts.append(
        bullet(
            "The industrial supervisor will bind packs, host the mid-year jury, and keep the commercial stack off the critical path of the viva."
        )
    )

    parts.append(heading("4.  The academic rule"))
    parts.append(
        body(
            "A number, a code, an alert, a mark, or a system write is not allowed until a pack, a span, "
            "a consent, or an evidence identifier can carry it. The student must fail that test in public. "
            "A naïve or published baseline must fail the same test, on the same bank, in the same viva."
        )
    )
    parts.append(
        body(
            "Headline metrics reproduce on ordinary tools: Postgres or DuckDB, any language model, the student’s scorer, and the pack. "
            "If the examiner cannot rerun the number, it is not a number."
        )
    )

    parts.append(heading("5.  What this is not"))
    parts.append(bullet("A campus ChatGPT, or a fine-tune on student or clinical prose."))
    parts.append(bullet("A medical device, a substitute for a clinician, or access to the hospital EHR or laboratory system."))
    parts.append(bullet("Identifiable student scripts, live e-prescriptions, or production payroll."))
    parts.append(bullet("A brief to rebuild a vendor product as the graduation title."))

    parts.append(heading("6.  Thirty weeks"))
    parts.append(
        table(
            ["Gate", "Week", "Must be true"],
            [
                ["Bind", "0–3", "Pack bound. Open-core repository. IP and conflict-of-interest signed. Ethics letter requested. Co-examiner named."],
                ["Claim", "6", "A baseline that fails. Scorer v1. Claim sheet signed. Bank hash recorded."],
                ["Applied", "14", "Applied depth on frozen bank v1. Mid-year jury."],
                ["Systems", "22", "Systems depth. Adversarial round. Bank v2 frozen."],
                ["Freeze", "26", "The reported number is the worst of three dated runs. Write-up starts."],
                ["Viva", "28–30", "The examiner reruns the headline metric from the student repository."],
            ],
            [1400, 1200, 6900],
        )
    )

    parts.append(heading("7.  Medicine — ethics, in one paragraph"))
    parts.append(
        body(
            "No electronic health record. Teaching gold only. Twenty percent of gold is double-annotated; agreement is reported. "
            "Every medicine studio carries a device-scope statement: not for patient care. "
            "If the College can name only one doctor, that doctor should be a clinical pharmacologist and Studio 3 proceeds. "
            "Studio 4 then uses the existing OSCE-note pack or the Medicine Moodle gold — both already written. "
            "We do not invent a clinical product to fill a gap in supervision."
        )
    )

    parts.append(heading("8.  Next step if approved"))
    parts.append(
        body(
            "Week 0–3: bind packs, name co-examiners, request the ethics letter, sign IP. "
            "I will convene two short doctor workshops for Studio 3 (a fifty-drug safety pack; about two hundred teaching prescriptions). "
            "Studio 4 workshops proceed only if a coder is named."
        )
    )
    parts.append(
        body(
            "I can present this in fifteen minutes. I do not need a committee to design the bank. I need cover to assign students, to ask Medicine for time, and to issue the ethics letter."
        )
    )

    parts.append(empty(200))
    parts.append(p(run("Respectfully,", size=21, color=BODY), after=400))
    parts.append(
        p(
            run("Dr. Ahmed", size=22, bold=True, color=NAVY),
            after=20,
            spacing=240,
        )
    )
    parts.append(
        p(
            run("College of Medicine, AASTMT", size=19, color=SLATE),
            after=0,
            spacing=220,
        )
    )
    parts.append(
        p(
            run("Industrial supervisor, proposed graduation studios — College of AI, Alamein", size=19, color=SLATE),
            after=200,
            spacing=220,
        )
    )
    parts.append(
        p(
            run(
                "Attachment: none required. A full thirty-card catalogue is held by the supervisor and can be tabled on request. This brief is the document to decide from.",
                size=16,
                italic=True,
                color=SLATE,
            ),
            after=0,
            spacing=240,
        )
    )

    sect = (
        "<w:sectPr>"
        '<w:headerReference w:type="default" r:id="rId1"/>'
        '<w:footerReference w:type="default" r:id="rId2"/>'
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1134" w:bottom="1280" w:left="1134" '
        'w:header="560" w:footer="560" w:gutter="0"/>'
        '<w:cols w:space="708"/>'
        '<w:docGrid w:linePitch="360"/>'
        "</w:sectPr>"
    )

    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{NS_W}" xmlns:r="{NS_R}">'
        f"<w:body>{''.join(parts)}{sect}</w:body>"
        f"</w:document>"
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
      <w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr>
    </w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
  </w:style>
</w:styles>
"""


def header_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:hdr xmlns:w="{NS_W}">
  <w:p>
    <w:pPr>
      <w:pBdr>
        <w:bottom w:val="single" w:sz="12" w:space="4" w:color="{GOLD}"/>
      </w:pBdr>
      <w:tabs><w:tab w:val="right" w:pos="9500"/></w:tabs>
      <w:spacing w:after="80" w:before="0"/>
    </w:pPr>
    <w:r>{rpr(size=15, bold=True, color=NAVY, caps=True)}<w:t>AASTMT  ·  ALAMEIN  ·  COLLEGE OF AI</w:t></w:r>
    <w:r>{rpr(size=15, color=SLATE)}<w:tab/><w:t>DECISION BRIEF  ·  CAI-ALM/GP/2026-27</w:t></w:r>
  </w:p>
</w:hdr>
"""


def footer_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="{NS_W}" xmlns:r="{NS_R}">
  <w:p>
    <w:pPr>
      <w:pBdr>
        <w:top w:val="single" w:sz="6" w:space="6" w:color="{RULE}"/>
      </w:pBdr>
      <w:tabs><w:tab w:val="right" w:pos="9500"/></w:tabs>
      <w:spacing w:before="80"/>
    </w:pPr>
    <w:r>{rpr(size=14, color=SLATE)}<w:t>Internal  ·  Not for publication  ·  Teaching data only  ·  Not a medical device</w:t></w:r>
    <w:r>{rpr(size=14, color=SLATE)}<w:tab/><w:t>Page </w:t></w:r>
    <w:r>{rpr(size=14, color=SLATE)}<w:fldChar w:fldCharType="begin"/></w:r>
    <w:r>{rpr(size=14, color=SLATE)}<w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>
    <w:r>{rpr(size=14, color=SLATE)}<w:fldChar w:fldCharType="end"/></w:r>
    <w:r>{rpr(size=14, color=SLATE)}<w:t> of </w:t></w:r>
    <w:r>{rpr(size=14, color=SLATE)}<w:fldChar w:fldCharType="begin"/></w:r>
    <w:r>{rpr(size=14, color=SLATE)}<w:instrText xml:space="preserve"> NUMPAGES </w:instrText></w:r>
    <w:r>{rpr(size=14, color=SLATE)}<w:fldChar w:fldCharType="end"/></w:r>
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
  <dc:title>Graduation-project studios 2026/27 — Chairman decision brief</dc:title>
  <dc:subject>College of AI, AASTMT Alamein</dc:subject>
  <dc:creator>Dr. Ahmed, College of Medicine, AASTMT</dc:creator>
  <cp:lastModifiedBy>Dr. Ahmed, College of Medicine, AASTMT</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">2026-09-30T09:00:00Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">2026-09-30T09:00:00Z</dcterms:modified>
  <dc:description>Decision brief for four graduation-project studios, academic year 2026/27.</dc:description>
  <cp:revision>1</cp:revision>
</cp:coreProperties>
"""


def app_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
  <Application>AASTMT College of AI</Application>
  <Pages>2</Pages>
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
