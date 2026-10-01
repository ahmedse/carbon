#!/usr/bin/env python3
"""Arabic president memo. Composed in Arabic from the English source. Names stay English."""

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = Path(__file__).resolve().parent / "2026-09-30-carbon-test-memo-ar.docx"
ACCENT = RGBColor(0x00, 0x5C, 0xA8)
NAVY = RGBColor(0x1A, 0x1A, 0x2E)
MUTED = RGBColor(0x55, 0x55, 0x55)
LIGHT = "EEF4FB"
LRM = "\u200e"


def rtl_run(run, rtl=True):
    rPr = run._r.get_or_add_rPr()
    el = OxmlElement("w:rtl")
    el.set(qn("w:val"), "1" if rtl else "0")
    rPr.append(el)


def cs_font(run, name="Arial"):
    rPr = run._r.get_or_add_rPr()
    fonts = rPr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rPr.insert(0, fonts)
    for key in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(key), name)


def rtl_p(paragraph, align=WD_ALIGN_PARAGRAPH.RIGHT):
    pPr = paragraph._p.get_or_add_pPr()
    if pPr.find(qn("w:bidi")) is None:
        bidi = OxmlElement("w:bidi")
        bidi.set(qn("w:val"), "1")
        pPr.append(bidi)
    paragraph.alignment = align


def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def borders(table, color="CCCCCC"):
    for row in table.rows:
        for cell in row.cells:
            tcPr = cell._tc.get_or_add_tcPr()
            tcBorders = OxmlElement("w:tcBorders")
            for side in ("top", "left", "bottom", "right"):
                border = OxmlElement(f"w:{side}")
                border.set(qn("w:val"), "single")
                border.set(qn("w:sz"), "4")
                border.set(qn("w:space"), "0")
                border.set(qn("w:color"), color)
                tcBorders.append(border)
            tcPr.append(tcBorders)


def tbl_bidi(table):
    tblPr = table._tbl.find(qn("w:tblPr"))
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        table._tbl.insert(0, tblPr)
    if tblPr.find(qn("w:bidiVisual")) is None:
        tblPr.append(OxmlElement("w:bidiVisual"))


def doc_rtl(doc):
    for section in doc.sections:
        sect = section._sectPr
        if sect.find(qn("w:bidi")) is None:
            bidi = OxmlElement("w:bidi")
            bidi.set(qn("w:val"), "1")
            sect.append(bidi)


def paint(paragraph, parts, *, size=12):
    for text, bold, rtl, color in parts:
        r = paragraph.add_run(text)
        r.bold = bold
        r.font.size = Pt(size)
        r.font.color.rgb = color or NAVY
        cs_font(r)
        rtl_run(r, rtl=rtl)


def para(doc, parts, *, size=12, before=0, after=8, indent=False, align=WD_ALIGN_PARAGRAPH.RIGHT):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    if indent:
        p.paragraph_format.right_indent = Cm(0.4)
    rtl_p(p, align=align)
    paint(p, parts, size=size)
    return p


def ar(text, *, bold=False, color=None):
    return (text, bold, True, color)


def en(text, *, bold=False, color=None):
    return (f"{LRM}{text}{LRM}", bold, False, color)


def heading(doc, text):
    p = para(doc, [ar(text, bold=True, color=ACCENT)], size=12, before=13, after=5)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "005CA8")
    pBdr.append(bottom)
    pPr.append(pBdr)


def cell(cell_, parts, *, size=11, fill=None, accent=False):
    p = cell_.paragraphs[0]
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(3)
    rtl_p(p)
    if fill:
        shade(cell_, fill)
    color = ACCENT if accent else None
    paint(p, [(t, b, rtl, color or c) for t, b, rtl, c in parts], size=size)


def main():
    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)
    section.top_margin = Cm(2.1)
    section.bottom_margin = Cm(2.1)
    doc_rtl(doc)
    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(12)
    style.element.get_or_add_pPr().append(OxmlElement("w:bidi"))

    para(doc, [ar("مذكرة داخلية", bold=True, color=ACCENT)], size=20, after=2)
    para(
        doc,
        [en("Arab Academy for Science, Technology & Maritime Transport", color=MUTED)],
        size=10,
        after=10,
    )

    table = doc.add_table(rows=4, cols=2)
    table.style = "Table Grid"
    tbl_bidi(table)
    rows = [
        ([ar("إلى", bold=True)], [ar("الأستاذ الدكتور / إسماعيل عبد الغفار، رئيس الأكاديمية")]),
        ([ar("من", bold=True)], [en("Dr. Ahmed Saied")]),
        ([ar("التاريخ", bold=True)], [ar("٣٠ سبتمبر ٢٠٢٦")]),
        (
            [ar("الموضوع", bold=True)],
            [
                ar("دعوة سيادتكم إلى الاطلاع على نظام ", bold=True),
                en("Carbon", bold=True),
                ar(" في فترة الاختبار، من دون إعلان أي رقم", bold=True),
            ],
        ),
    ]
    for i, (label, value) in enumerate(rows):
        a, b = table.rows[i].cells
        a.width = Cm(2.5)
        b.width = Cm(13.5)
        cell(a, label, size=10, fill=LIGHT, accent=True)
        cell(b, value, size=11)
    borders(table)

    para(doc, [ar("سيادة الرئيس،")], before=16, after=10)

    para(
        doc,
        [
            ar(
                "أرفع إلى سيادتكم هذه المذكرة بوصفكم رئيس الأكاديمية. "
                "ليست دليلاً للتشغيل، وليست بياناً يُذاع."
            ),
        ],
    )

    heading(doc, "المنصة، ثم التطبيق، ثم الزميل")
    para(
        doc,
        [
            ar("أنشأنا للمنصة اسماً هو "),
            en("Data Trust Platform", bold=True),
            ar(
                ". معناها بسيط: الرقم لا يُرفع إلى تقرير حتى يُعرف مصدره، "
                "ويُفحص، ويُسمّى من يسأل عنه. "
                "يرى الفرع ما يخصّه. وترون أنتم الصورة بعد جمعها. "
                "هذا هو الأساس. أما "
            ),
            en("Carbon"),
            ar(" فليس الأساس، بل أول عمل قام عليه."),
        ],
    )
    para(
        doc,
        [
            en("Carbon Footprint", bold=True),
            ar(
                " يحفظ ما تستهلكه الفروع: الكهرباء، والوقود، والسفر. "
                "إن شاءت الأكاديمية يوماً أن تعلن بصمة، "
                "فلتُعلن من هذا السجل، لا من جدول يُعدّ على حدة. "
                "وما يُحفظ اليوم لا يُبدَّل؛ إن وُجد خطأ أُضيف تصحيح إلى جانبه."
            ),
        ],
    )
    para(
        doc,
        [
            en("Pulse", bold=True),
            ar(
                " يعمل معكم داخل المنصة، على السجل نفسه. "
                "ليس برنامجاً يُسأل في الخارج ثم يُصدَّق. "
                "إن غاب الرقم عن السجل، صرّح بغيابه. ولا يضع رقماً من عنده. "
                "يسأل فيجيب. فإن لزم تغيير في النظام، خرج الأمر عن السؤال: "
                "خطة، ثم موافقة، ثم تنفيذ يُقرّ خطوةً خطوة."
            ),
        ],
    )

    heading(doc, "طبيعة هذه الفترة")
    para(
        doc,
        [
            ar(
                "نفتح الباب للاستخدام، ولا نعلن بصمة الأكاديمية. "
                "ما ترونه في "
            ),
            en("Chairman Overview"),
            ar(
                " هو ما استطاعت المنصة جمعه حتى اليوم. "
                "ليس رقم فرع، وليس الرقم الذي تخرج به الأكاديمية إلى الناس. "
                "والصفحة لا تخفي ذلك. "
                "أما السنة الظاهرة للإدخال فليست السنة التي نطلب إعلانها."
            ),
        ],
    )

    heading(doc, "رجاء سيادتكم")
    para(
        doc,
        [
            ar("أن تدخلوا "),
            en("Carbon Footprint"),
            ar(" ثم "),
            en("Chairman Overview"),
            ar(
                "، وتنظروا: أتصحّ هذه الصورة لرئيس؟ "
                "إن أشكل عليكم سطر، فاسألوا "
            ),
            en("Pulse"),
            ar(
                ". ولا توردوا رقماً رأيتموه على الشاشة في كلمة تُلقى، "
                "ولا في خطاب، ولا في ورقة تُرفع إلى المجلس."
            ),
        ],
    )
    para(
        doc,
        [
            ar(
                "حساب سيادتكم للقراءة فحسب. "
                "أسلمكم بيانات الدخول بنفسي، ولا أثبتها في هذه الورقة."
            ),
        ],
    )
    para(
        doc,
        [
            ar("يتولى المتابعة مع الفروع "),
            en("Eng. Mostafa Kamel"),
            ar(" و"),
            en("Dr. Mostafa Saad"),
            ar(". إدخال البيانات شأنهم، لا شأن مكتبكم."),
        ],
    )

    para(doc, [ar("وتفضلوا بقبول فائق الاحترام،")], before=16, after=4)
    para(doc, [en("Dr. Ahmed Saied", bold=True)], after=12)
    para(
        doc,
        [ar("للتداول الداخلي. لا تُرفق بيانات الدخول بهذه المذكرة.", color=MUTED)],
        size=9,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        after=0,
    )

    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
